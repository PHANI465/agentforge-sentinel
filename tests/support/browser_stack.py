"""Browser-test stack (C02): disposable PostgreSQL + the real API in a real uvicorn process,
seeded with deterministic scenarios. Cursor's Playwright setup drives it through this CLI.

    uv run --locked python tests/support/browser_stack.py start [--parent-dir DIR]
            [--scorer rule|model] [--model-fixtures]
        -> creates a fresh private sentinel-browser-* directory (inside DIR if given) and
           prints SENTINEL_STACK_MANIFEST=<path>; tokens are only inside that private file
    uv run --locked python tests/support/browser_stack.py seed --manifest P --scenario NAME --ordinal N
    uv run --locked python tests/support/browser_stack.py restart-api --manifest P [--scorer rule|model]
    uv run --locked python tests/support/browser_stack.py restart-db --manifest P
    uv run --locked python tests/support/browser_stack.py status --manifest P
    uv run --locked python tests/support/browser_stack.py stop --manifest P

See docs/api/browser-fixtures.md and docs/api/model-browser-fixtures.md. Nothing here adds an
HTTP route; the API process runs the unchanged production app with a deterministic fixture
investigator (fixture_app.py) and the registered scorer selected at start/restart, connected
as a least-privilege runtime role (I01). Setup and seeding keep the operator connection.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

SUPPORT = Path(__file__).resolve().parent
ROOT = SUPPORT.parents[1]
for path in (str(SUPPORT), str(ROOT / "src")):
    if path not in sys.path:
        sys.path.insert(0, path)

from psycopg.conninfo import make_conninfo  # noqa: E402

from sentinel import db, devdb  # noqa: E402
from sentinel.db import roles  # noqa: E402

import scenarios  # noqa: E402

MANIFEST_VERSION = 2
DEFAULT_APP = "fixture_app:create_app"
PREFIX = "sentinel-browser-"
MARKER = ".sentinel-browser-stack"
# The only top-level entries a helper-owned state directory may contain at deletion time.
OWNED_ENTRIES = {"stack.json", MARKER, "pg", "api.log"}
# Paths the helper itself reads, writes or hands to pg_ctl. Each must be a real (not
# redirected) entry resolving inside the owned directory whenever it exists.
CRITICAL_PATHS = ("stack.json", MARKER, "api.log", "pg", "pg/data")
# The API's database role inside the disposable cluster (trust auth on loopback: no password).
RUNTIME_ROLE = "sentinel_browser_runtime"
# CLI scorer names -> SENTINEL_SCORER values; only registered scorers exist.
SCORERS = {"rule": "rule", "model": "model:hgb_balanced@p1"}
# POSIX API stop: graceful request, then (same verified group only) SIGKILL; both bounded.
TERM_GRACE_SECONDS = 10
KILL_WAIT_SECONDS = 10


class StackError(RuntimeError):
    pass


# ---- process identity (targeted termination only) ----------------------------------------

def process_start_time(pid: int) -> int | None:
    """A stable per-process start stamp, so a reused PID is never mistaken for ours."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return None
        try:
            times = [wintypes.FILETIME() for _ in range(4)]
            if not kernel32.GetProcessTimes(handle, *[ctypes.byref(t) for t in times]):
                return None
            exit_code = wintypes.DWORD()
            kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            if exit_code.value != 259:  # STILL_ACTIVE
                return None
            return (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
        finally:
            kernel32.CloseHandle(handle)
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        if fields[0] in ("Z", "X"):  # exited (zombie until its parent waits): not running
            return None
        return int(fields[19])
    except (OSError, IndexError, ValueError):
        try:
            os.kill(pid, 0)
            return 0  # alive, start time unknown: never a verified identity
        except OSError:
            return None


def _group_members(pgid: int) -> set[int] | None:
    """Live (non-zombie) members of a POSIX process group; None if it cannot be inspected.
    Only an entry that affirmatively disappeared while listing is skipped; a permission or
    other I/O failure, or malformed stat data, makes the membership unknown (R30)."""
    try:
        entries = [entry for entry in Path("/proc").iterdir() if entry.name.isdigit()]
    except OSError:
        return None
    members = set()
    for entry in entries:
        try:
            fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
            state, group = fields[0], int(fields[2])
        except (FileNotFoundError, ProcessLookupError):
            continue  # exited while listing
        except (OSError, IndexError, ValueError):
            return None
        if state not in ("Z", "X") and group == pgid:
            members.add(int(entry.name))
    return members


def group_unresolved(pgid: int) -> str | None:
    """Why a recorded API group cannot be shown empty (POSIX), or None once it is."""
    if os.name == "nt":
        return None  # the forced tree kill is the Windows termination; no groups here
    members = _group_members(pgid)
    if members is None:
        return f"API process group {pgid} membership cannot be inspected"
    if members:
        return f"API process group {pgid} still has live members {sorted(members)}"
    return None


def healthy(port: int) -> dict | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=2) as response:
            return json.loads(response.read())
    except (OSError, ValueError):
        return None


def wait_until(predicate, timeout: float, interval: float = 0.2) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def terminate_tree(pid: int, stamp: int | None) -> None:
    """Stop one API process tree whose recorded identity (pid + start stamp) still matches.

    Windows: a forced tree kill. POSIX: the API was launched as the leader of its own process
    group; that group gets SIGTERM, then, if the leader has not exited within
    TERM_GRACE_SECONDS (an app blocked after installing its TERM handler), SIGKILL. Identity
    and group are re-verified immediately before each signal; anything unverifiable, changed
    or not the API's own group raises StackError with nothing (further) signalled, so the
    caller keeps its recovery record. Members surviving an exited leader are reported, never
    assumed to be ours."""
    import signal

    def verify(boundary: str) -> None:
        if not stamp or process_start_time(pid) != stamp:
            raise StackError(f"API process {pid} identity changed or unverifiable {boundary}; "
                             "not signalled, recovery kept")
        if os.name == "nt":
            return
        try:
            group = os.getpgid(pid)
        except OSError:
            raise StackError(f"API process {pid} group cannot be inspected {boundary}; "
                             "not signalled, recovery kept") from None
        if group != pid or group == os.getpgrp():
            raise StackError(f"API process {pid} is not the leader of its own process group; "
                             "not signalled, recovery kept")

    def signal_group(sig) -> None:
        try:
            os.killpg(pid, sig)
        except ProcessLookupError:
            pass  # the group is already gone
        except OSError as error:
            raise StackError(f"API process group {pid} could not be signalled "
                             f"({type(error).__name__}); recovery kept") from None

    def exited() -> bool:
        return process_start_time(pid) != stamp

    def survivors_resolved() -> None:
        problem = group_unresolved(pid)
        if problem:
            raise StackError(f"API process {pid} exited but its group cannot be shown empty "
                             f"({problem}); not signalled, recovery kept")

    verify("before termination")
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
        return
    signal_group(signal.SIGTERM)
    if wait_until(exited, TERM_GRACE_SECONDS):
        survivors_resolved()
        return
    verify("before escalation")
    signal_group(signal.SIGKILL)
    if not wait_until(exited, KILL_WAIT_SECONDS):
        raise StackError(f"API process {pid} did not stop after SIGKILL; recovery kept")
    survivors_resolved()


# ---- ownership (review R11) ----------------------------------------------------------------

def is_redirect(path: Path) -> bool:
    """True for a symlink, a Windows junction/reparse point, or a path that cannot be read."""
    try:
        info = os.lstat(path)
    except OSError:
        return True
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & reparse)


def canonical(path: Path) -> str:
    return os.path.normcase(os.path.realpath(path))


def redirects_below(root: Path) -> list[str]:
    """Links/junctions anywhere under root (never followed)."""
    found = []
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            if is_redirect(Path(directory) / name):
                found.append(os.path.relpath(Path(directory) / name, root))
        dirs[:] = [d for d in dirs if not is_redirect(Path(directory) / d)]
    return found


# ---- the stack -----------------------------------------------------------------------------

class Stack:
    def __init__(self, state_dir: Path, manifest: dict | None = None):
        self.state_dir = Path(state_dir)
        self.manifest = manifest or {}
        self._process: subprocess.Popen | None = None
        self._manifest_removed = False

    @property
    def path(self) -> Path:
        return self.state_dir / "stack.json"

    @classmethod
    def load(cls, manifest_path: Path) -> "Stack":
        """Accept only a manifest inside the helper-owned directory it records."""
        manifest_path = Path(manifest_path)
        directory = manifest_path.parent
        if is_redirect(directory) or is_redirect(manifest_path):
            raise StackError("manifest path is redirected or unreadable")
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise StackError("manifest is unreadable") from None
        if not isinstance(data, dict) or data.get("version") != MANIFEST_VERSION:
            raise StackError("unsupported manifest version")
        recorded = data.get("state_dir")
        if not isinstance(recorded, str) or canonical(directory) != os.path.normcase(recorded):
            raise StackError("manifest is not in the state directory it records")
        stack = cls(Path(recorded), data)
        stack.guard()
        return stack

    def guard(self) -> None:
        """Operation-boundary check, repeated before every PostgreSQL command, helper write
        and deletion (a loaded object is not proof of the current filesystem shape): the
        directory is ours, and every critical child that exists is a real entry resolving
        inside it. Not-yet-created children are allowed. This is not a defence against an
        adversary racing the filesystem between the check and the operation."""
        self.verify_owned()
        root = canonical(self.state_dir)
        for relative in CRITICAL_PATHS:
            path = self.state_dir / relative
            if not os.path.lexists(path):
                continue
            expected = os.path.join(root, os.path.normcase(relative.replace("/", os.sep)))
            if is_redirect(path) or canonical(path) != expected:
                raise StackError(f"redirected or foreign path refused: {relative}")

    def verify_owned(self) -> None:
        """The directory is ours: expected name, canonical path and a matching marker."""
        directory = self.state_dir
        if not directory.name.startswith(PREFIX) or is_redirect(directory):
            raise StackError("state directory is not a helper-owned directory")
        if canonical(directory) != os.path.normcase(self.manifest.get("state_dir", "")):
            raise StackError("state directory does not match the manifest")
        marker = directory / MARKER
        if is_redirect(marker) or not marker.is_file():
            raise StackError("ownership marker is missing")
        try:
            owner = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise StackError("ownership marker is unreadable") from None
        if not (isinstance(owner, dict) and isinstance(self.manifest.get("owner"), str)
                and secrets.compare_digest(str(owner.get("owner", "")), self.manifest["owner"])
                and owner.get("state_dir") == self.manifest["state_dir"]):
            raise StackError("ownership marker does not match the manifest")

    def _remove_owned(self) -> str | None:
        """Delete the verified directory in a fixed order, so every failure leaves a state a
        plain `stop` retry can finish (review R12):
          1. removable contents (pg/, api.log), each re-checked right before deletion;
             on failure the marker and manifest are untouched, so the stack still loads;
          2. the manifest (the only copy of the tokens);
          3. the ownership marker; if this fails, a marker-only directory remains, which
             `stop --manifest` finishes after re-verifying the marker (finish_marker_only);
          4. the now-empty directory.
        Unexpected entries, links or junctions anywhere stop the removal before step 1."""
        try:
            self.guard()
        except StackError as error:
            return f"not removed: {error}"
        entries = set(os.listdir(self.state_dir))
        unexpected = sorted(entries - OWNED_ENTRIES)
        if unexpected:
            return f"not removed: unexpected entries {unexpected}"
        links = redirects_below(self.state_dir)
        if links:
            return f"not removed: links inside state directory {links[:5]}"
        root = canonical(self.state_dir)
        for name in sorted(entries - {"stack.json", MARKER}):
            target = self.state_dir / name
            if is_redirect(target) or os.path.dirname(canonical(target)) != root:
                return f"not removed: {name} no longer resolves inside the state directory"
            try:
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
            except OSError as error:
                return (f"removal incomplete ({name}: {type(error).__name__}); ownership "
                        "marker and manifest kept, retry stop")
        try:
            self.path.unlink(missing_ok=True)
        except OSError as error:
            return f"removal incomplete (manifest: {type(error).__name__}); retry stop"
        self._manifest_removed = True
        try:
            (self.state_dir / MARKER).unlink()
        except OSError as error:
            return (f"finalization incomplete (ownership marker: {type(error).__name__}); "
                    f"only the marker remains, rerun stop --manifest {self.path}")
        try:
            os.rmdir(self.state_dir)
        except OSError as error:
            return f"finalization incomplete (empty directory: {type(error).__name__})"
        return None

    @staticmethod
    def finish_marker_only(directory: Path) -> None:
        """Finish a removal that stopped after the manifest was deleted. Acts only on a
        `sentinel-browser-*` directory containing exactly a valid marker that records this
        very directory; never creates or repairs ownership."""
        directory = Path(directory)
        if not directory.name.startswith(PREFIX) or is_redirect(directory):
            raise StackError("not a helper-owned directory")
        if sorted(os.listdir(directory)) != [MARKER]:
            raise StackError("not a marker-only stack directory")
        marker = directory / MARKER
        if is_redirect(marker):
            raise StackError("ownership marker is redirected")
        try:
            recorded = json.loads(marker.read_text(encoding="utf-8")).get("state_dir")
        except (OSError, ValueError, AttributeError):
            raise StackError("ownership marker is unreadable") from None
        if recorded != canonical(directory):
            raise StackError("ownership marker does not record this directory")
        marker.unlink()
        os.rmdir(directory)

    def _cluster(self) -> devdb.Cluster:
        """The owned cluster, after a fresh path guard (every pg_ctl use goes through here)."""
        self.guard()
        bin_dir = devdb.find_pg_bin()
        if bin_dir is None:
            raise StackError("PostgreSQL initdb not found; set SENTINEL_PG_BIN")
        return devdb.Cluster(bin_dir, self.state_dir / "pg" / "data",
                             self.manifest["database"]["port"])

    def _save(self) -> None:
        self.guard()
        self.path.write_text(json.dumps(self.manifest, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    @classmethod
    def start(cls, parent: Path | None = None, *, app: str = DEFAULT_APP,
              api_port: int | None = None, timeout: float = 60, scorer: str = "rule",
              model_fixtures: bool = False) -> "Stack":
        """Create, migrate, seed and serve in a fresh private directory (never an existing
        one). On failure everything started is stopped; state is removed only if both
        shutdowns are verified, otherwise the recovery manifest is kept (review R12).
        `scorer` is a SENTINEL_SCORER value; the API refuses anything unregistered."""
        if parent is not None:
            Path(parent).mkdir(parents=True, exist_ok=True)
        base = Path(os.path.realpath(tempfile.mkdtemp(prefix=PREFIX, dir=parent)))
        owner = secrets.token_hex(16)
        (base / MARKER).write_text(json.dumps({"owner": owner, "state_dir": canonical(base)}),
                                   encoding="utf-8")
        stack = cls(base, {"version": MANIFEST_VERSION, "app": app, "owner": owner,
                           "state_dir": canonical(base),
                           "database": {"port": devdb.free_port(), "name": "browser"},
                           "api": {"port": api_port or devdb.free_port(), "scorer": scorer,
                                   "database_user": RUNTIME_ROLE},
                           "model_fixtures": model_fixtures})
        stack._save()
        try:
            cluster = stack._cluster()
            cluster.init()
            cluster.start()
            stack.manifest["database"]["started"] = True
            url = cluster.create_database("browser")
            db.migrate(url)
            roles.grant_runtime(url, RUNTIME_ROLE)  # operator setup; the API never owns
            tokens, sessions, seeded = scenarios.seed_all(url, model_fixtures=model_fixtures)
            stack.manifest.update(database_url=url, tokens=tokens, sessions=sessions,
                                  scenarios=seeded, seeded_ordinals={})
            stack._save()
            stack._start_api(timeout)
            stack._save()
            return stack
        except BaseException as error:
            cleanup = stack.stop()
            if cleanup["ok"]:
                raise
            raise StackError(f"startup failed ({type(error).__name__}: {error}); cleanup "
                             f"incomplete {cleanup['errors']}; recovery manifest kept at "
                             f"{stack.path}") from error

    def _start_api(self, timeout: float) -> None:
        port = self.manifest["api"]["port"]
        if healthy(port):
            raise StackError(f"port {port} already serves an API")
        module, factory = self.manifest["app"].split(":")
        self.guard()  # api.log must be a real file inside the owned directory
        api = self.manifest["api"]
        user = api.get("database_user")
        url = self.manifest["database_url"]
        env = {**os.environ,
               "SENTINEL_DATABASE_URL": make_conninfo(url, user=user) if user else url,
               "SENTINEL_SCORER": api.get("scorer", "rule"),
               "SENTINEL_INVESTIGATOR": "deterministic", "SENTINEL_LIVE_CLAUDE": "0",
               "SENTINEL_MODE": "local"}
        log = open(self.state_dir / "api.log", "ab")
        flags = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt"
                 else {"start_new_session": True})
        self._process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", f"{module}:{factory}", "--factory",
             "--app-dir", str(SUPPORT), "--host", "127.0.0.1", "--port", str(port),
             "--log-level", "warning", "--no-access-log"],
            cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log, **flags)
        log.close()
        pid = self._process.pid
        self.manifest["api"].update(pid=pid, start_time=process_start_time(pid),
                                    base_url=f"http://127.0.0.1:{port}")
        self._save()
        ready = wait_until(lambda: healthy(port) is not None or self._process.poll() is not None,
                           timeout)
        if not ready or healthy(port) is None:
            exited = self._process.poll()
            raise StackError("API exited during startup" if exited is not None
                             else f"API not ready within {timeout:.0f} s")

    def stop_api(self) -> None:
        """Stop only the recorded API process tree, after confirming its identity."""
        api = self.manifest.get("api", {})
        pid, stamp, port = api.get("pid"), api.get("start_time"), api.get("port")
        if pid is None:
            return
        launched = self._process is not None and self._process.poll() is None
        if launched or (stamp is not None and process_start_time(pid) == stamp):
            terminate_tree(pid, stamp)  # re-verifies identity; refusal keeps this record
            if self._process is not None:
                try:
                    self._process.wait(timeout=KILL_WAIT_SECONDS)  # reap our own child
                except subprocess.TimeoutExpired:
                    raise StackError(f"API process {pid} did not stop") from None
        # else: the recorded process is already gone (or the PID was reused): touch nothing.
        if not wait_until(lambda: process_start_time(pid) != stamp, 15):
            raise StackError(f"API process {pid} did not stop")
        # The API was launched as the leader of group `pid`. Its exit (or a reused PID, or a
        # closed port) does not prove that group empty; every retry, including from a freshly
        # loaded manifest, re-checks it from the recorded pid before the record is cleared
        # (R29). Nothing is signalled here.
        problem = group_unresolved(pid)
        if problem:
            raise StackError(f"{problem}; not signalled, recovery kept")
        if port is not None and not wait_until(lambda: healthy(port) is None, 15):
            raise StackError(f"port {port} still serves an API")
        api.update(pid=None, start_time=None)
        self._process = None

    def stop(self) -> dict:
        """Stop API and database and verify each. The owned state directory (manifest,
        tokens, process identity, database files) is deleted only when BOTH are verified
        stopped; otherwise it is kept for a retry and the result reports failure."""
        errors: list[str] = []
        api_ok = True
        try:
            self.stop_api()
        except StackError as error:
            api_ok = False
            errors.append(f"api: {error}")
        try:
            state = self.db_state()
            if state in ("running", "unknown"):
                try:
                    self._cluster().stop()
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
                    errors.append("database: pg_ctl stop failed")
                state = self.db_state()
        except StackError as error:
            state = "unknown"
            errors.append(f"database: {error}")
        db_ok = state in DB_STOPPED
        if db_ok:
            self.manifest.setdefault("database", {})["started"] = False
        else:
            errors.append(f"database: state {state}, not verified stopped")
        removed = False
        self._manifest_removed = False
        if api_ok and db_ok:
            problem = self._remove_owned()
            removed = problem is None
            if problem:
                errors.append(problem)
        if not removed and not self._manifest_removed and self.path.exists():
            try:
                self._save()  # the recovery record reflects what may still be running
            except (StackError, OSError) as error:
                errors.append(f"recovery record not rewritten: {error}")
        return {"ok": api_ok and db_ok and removed, "api_stopped": api_ok,
                "database_stopped": db_ok, "state_removed": removed, "errors": errors}

    def restart_api(self, timeout: float = 60, scorer: str | None = None) -> None:
        """A new uvicorn process (new PID) on the same port and database; optionally with
        another registered scorer (test-only lifecycle; stored records keep their own
        scorer identity)."""
        self.stop_api()
        if scorer is not None:
            self.manifest["api"]["scorer"] = scorer
            self._save()
        self._start_api(timeout)
        self._save()

    def restart_db(self, timeout: float = 60) -> None:
        """Stop and start the PostgreSQL server itself (pg_ctl); the API reconnects."""
        self._cluster().stop()
        if self.db_state() != "stopped":
            raise StackError("database not verified stopped")
        self._cluster().start()
        if not wait_until(lambda: self.db_state() == "running", timeout):
            raise StackError("database did not restart")

    def db_state(self) -> str:
        """running | stopped (pg_ctl status 3) | absent | uninitialized | unknown.
        Anything that is not affirmative evidence counts as unknown, never as stopped."""
        cluster = self._cluster()
        data = cluster.data_dir
        if not os.path.lexists(data):
            return "absent"
        if not (data / "PG_VERSION").exists() and not (data / "postmaster.pid").exists():
            return "uninitialized"  # no server can run without PG_VERSION
        return pg_status(cluster)

    def seed(self, name: str, ordinal: int) -> dict:
        if name not in scenarios.ALL_SCENARIOS:
            raise StackError(f"unknown scenario {name!r}")
        if name in scenarios.MODEL_SCENARIOS and not self.manifest.get("model_fixtures"):
            raise StackError(f"{name} needs a stack started with --model-fixtures")
        used = self.manifest.setdefault("seeded_ordinals", {}).setdefault(name, [])
        if ordinal in used or ordinal < 1:
            raise StackError(f"ordinal {ordinal} already used (or < 1) for {name}")
        record = scenarios.seed_one(self.manifest["database_url"], self.manifest["tokens"],
                                    name, ordinal)
        used.append(ordinal)
        self._save()
        return record

    def status(self) -> dict:
        state = self.db_state()
        database = "up" if state == "running" else "unknown" if state == "unknown" else "down"
        return {"api": "up" if healthy(self.manifest["api"]["port"]) else "down",
                "database": database}  # exact C02 shape; the mode is manifest api.scorer


DB_STOPPED = {"stopped", "absent", "uninitialized"}


def pg_status(cluster: devdb.Cluster) -> str:
    """pg_ctl status: 0 running, 3 not running (PostgreSQL 14 docs); 4 (inaccessible data
    directory), other codes, errors and timeouts are unknown."""
    try:
        status = subprocess.run([str(cluster.bin_dir / "pg_ctl"), "-D", str(cluster.data_dir),
                                 "status"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return {0: "running", 3: "stopped"}.get(status.returncode, "unknown")


def _cluster_running(cluster: devdb.Cluster) -> bool:
    return pg_status(cluster) == "running"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("start")
    start.add_argument("--parent-dir", type=Path,
                       help="existing or new parent; a fresh private child is always created")
    start.add_argument("--api-port", type=int)
    start.add_argument("--timeout", type=float, default=60)
    start.add_argument("--app", default=DEFAULT_APP, help=argparse.SUPPRESS)
    start.add_argument("--scorer", choices=sorted(SCORERS), default="rule")
    start.add_argument("--model-fixtures", action="store_true",
                       help="also seed the I01 model scenarios (needs the ml extra)")
    for name in ("seed", "restart-api", "restart-db", "status", "stop"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--manifest", type=Path, required=True)
        if name == "seed":
            cmd.add_argument("--scenario", required=True,
                             choices=sorted(scenarios.ALL_SCENARIOS))
            cmd.add_argument("--ordinal", type=int, required=True)
        if name == "restart-api":
            cmd.add_argument("--scorer", choices=sorted(SCORERS))
    args = parser.parse_args(argv)
    try:
        if args.command == "start":
            stack = Stack.start(args.parent_dir, app=args.app, api_port=args.api_port,
                                timeout=args.timeout, scorer=SCORERS[args.scorer],
                                model_fixtures=args.model_fixtures or args.scorer == "model")
            print(f"SENTINEL_STACK_MANIFEST={stack.path}")
            print(f"base_url={stack.manifest['api']['base_url']} "
                  f"scenarios={','.join(sorted(stack.manifest['scenarios']))} "
                  f"scorer={args.scorer}")
            return 0
        if args.command == "stop" and not os.path.lexists(args.manifest) \
                and args.manifest.parent.is_dir():
            Stack.finish_marker_only(args.manifest.parent)
            print(json.dumps({"ok": True, "api_stopped": True, "database_stopped": True,
                              "state_removed": True, "errors": []}))
            return 0
        stack = Stack.load(args.manifest)
        if args.command == "seed":
            print(json.dumps(stack.seed(args.scenario, args.ordinal), sort_keys=True))
        elif args.command == "restart-api":
            stack.restart_api(scorer=SCORERS[args.scorer] if args.scorer else None)
            print(f"api restarted pid={stack.manifest['api']['pid']} "
                  f"scorer={stack.manifest['api']['scorer']}")
        elif args.command == "restart-db":
            stack.restart_db()
            print("database restarted")
        elif args.command == "status":
            print(json.dumps(stack.status()))
        else:
            result = stack.stop()
            print(json.dumps(result))
            return 0 if result["ok"] else 1
        return 0
    except StackError as error:  # messages never contain tokens
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
