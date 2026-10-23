"""Browser-test stack (C02): disposable PostgreSQL + the real API in a real uvicorn process,
seeded with deterministic scenarios. Cursor's Playwright setup drives it through this CLI.

    uv run --locked python tests/support/browser_stack.py start [--state-dir DIR]
        -> prints SENTINEL_STACK_MANIFEST=<path> (tokens are only inside that private file)
    uv run --locked python tests/support/browser_stack.py seed --manifest P --scenario NAME --ordinal N
    uv run --locked python tests/support/browser_stack.py restart-api --manifest P
    uv run --locked python tests/support/browser_stack.py restart-db --manifest P
    uv run --locked python tests/support/browser_stack.py status --manifest P
    uv run --locked python tests/support/browser_stack.py stop --manifest P

See docs/api/browser-fixtures.md. Nothing here adds an HTTP route; the API process runs the
unchanged production app with a deterministic fixture investigator (fixture_app.py).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
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

from sentinel import db, devdb  # noqa: E402

import scenarios  # noqa: E402

MANIFEST_VERSION = 1
DEFAULT_APP = "fixture_app:create_app"


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
        return int(Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19])
    except (OSError, IndexError, ValueError):
        try:
            os.kill(pid, 0)
            return 0  # alive, start time unknown on this platform
        except OSError:
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


def terminate_tree(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    else:
        import signal
        try:
            os.killpg(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass


# ---- the stack -----------------------------------------------------------------------------

class Stack:
    def __init__(self, state_dir: Path, manifest: dict | None = None):
        self.state_dir = Path(state_dir)
        self.manifest = manifest or {}
        self._process: subprocess.Popen | None = None

    @property
    def path(self) -> Path:
        return self.state_dir / "stack.json"

    @classmethod
    def load(cls, manifest_path: Path) -> "Stack":
        data = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
        if data.get("version") != MANIFEST_VERSION:
            raise StackError("unsupported manifest version")
        return cls(Path(manifest_path).parent, data)

    def _cluster(self) -> devdb.Cluster:
        bin_dir = devdb.find_pg_bin()
        if bin_dir is None:
            raise StackError("PostgreSQL initdb not found; set SENTINEL_PG_BIN")
        return devdb.Cluster(bin_dir, self.state_dir / "pg" / "data",
                             self.manifest["database"]["port"])

    def _save(self) -> None:
        self.path.write_text(json.dumps(self.manifest, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    @classmethod
    def start(cls, state_dir: Path | None = None, *, app: str = DEFAULT_APP,
              api_port: int | None = None, timeout: float = 60) -> "Stack":
        """Create, migrate, seed and serve. On any failure everything started is torn down."""
        created = state_dir is None
        base = Path(tempfile.mkdtemp(prefix="sentinel-browser-")) if created else Path(state_dir)
        base.mkdir(parents=True, exist_ok=True)
        stack = cls(base, {"version": MANIFEST_VERSION, "app": app,
                           "database": {"port": devdb.free_port(), "name": "browser"},
                           "api": {"port": api_port or devdb.free_port()}})
        cluster = stack._cluster()
        try:
            cluster.init()
            cluster.start()
            stack.manifest["database"]["started"] = True
            url = cluster.create_database("browser")
            db.migrate(url)
            tokens, sessions, seeded = scenarios.seed_all(url)
            stack.manifest.update(database_url=url, tokens=tokens, sessions=sessions,
                                  scenarios=seeded, seeded_ordinals={})
            stack._save()
            stack._start_api(timeout)
            stack._save()
            return stack
        except BaseException:
            stack.stop(remove=created)
            stack.path.unlink(missing_ok=True)  # never leave tokens behind after a failure
            raise

    def _start_api(self, timeout: float) -> None:
        port = self.manifest["api"]["port"]
        if healthy(port):
            raise StackError(f"port {port} already serves an API")
        module, factory = self.manifest["app"].split(":")
        env = {**os.environ, "SENTINEL_DATABASE_URL": self.manifest["database_url"],
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
        if self._process is not None and self._process.poll() is None:
            terminate_tree(pid)
            self._process.wait(timeout=15)
        elif stamp is not None and process_start_time(pid) == stamp:
            terminate_tree(pid)
        # else: the recorded process is already gone (or the PID was reused): touch nothing.
        if not wait_until(lambda: process_start_time(pid) != stamp, 15):
            raise StackError(f"API process {pid} did not stop")
        if port is not None and not wait_until(lambda: healthy(port) is None, 15):
            raise StackError(f"port {port} still serves an API")
        api.update(pid=None, start_time=None)
        self._process = None

    def stop(self, remove: bool = True) -> dict:
        """Stop API and database, verify both, then delete the private state directory."""
        result = {"api_stopped": True, "database_stopped": True, "state_removed": False}
        try:
            self.stop_api()
        finally:
            if self.manifest.get("database", {}).get("started"):
                cluster = self._cluster()
                try:
                    cluster.stop()
                except subprocess.CalledProcessError:
                    pass  # verified below
                result["database_stopped"] = not _cluster_running(cluster)
                self.manifest["database"]["started"] = not result["database_stopped"]
            if remove and result["database_stopped"]:
                shutil.rmtree(self.state_dir, ignore_errors=True)
                result["state_removed"] = not self.state_dir.exists()
            elif self.path.parent.exists():
                self._save()
        return result

    def restart_api(self, timeout: float = 60) -> None:
        """A new uvicorn process (new PID) on the same port and database."""
        self.stop_api()
        self._start_api(timeout)
        self._save()

    def restart_db(self, timeout: float = 60) -> None:
        """Stop and start the PostgreSQL server itself (pg_ctl); the API reconnects."""
        cluster = self._cluster()
        cluster.stop()
        if _cluster_running(cluster):
            raise StackError("database did not stop")
        cluster.start()
        if not wait_until(lambda: _cluster_running(cluster), timeout):
            raise StackError("database did not restart")

    def seed(self, name: str, ordinal: int) -> dict:
        if name not in scenarios.SCENARIOS:
            raise StackError(f"unknown scenario {name!r}")
        used = self.manifest.setdefault("seeded_ordinals", {}).setdefault(name, [])
        if ordinal in used or ordinal < 1:
            raise StackError(f"ordinal {ordinal} already used (or < 1) for {name}")
        record = scenarios.seed_one(self.manifest["database_url"], self.manifest["tokens"],
                                    name, ordinal)
        used.append(ordinal)
        self._save()
        return record

    def status(self) -> dict:
        cluster = self._cluster()
        return {"api": "up" if healthy(self.manifest["api"]["port"]) else "down",
                "database": "up" if _cluster_running(cluster) else "down"}


def _cluster_running(cluster: devdb.Cluster) -> bool:
    status = subprocess.run([str(cluster.bin_dir / "pg_ctl"), "-D", str(cluster.data_dir),
                             "status"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    return status.returncode == 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("start")
    start.add_argument("--state-dir", type=Path)
    start.add_argument("--api-port", type=int)
    start.add_argument("--timeout", type=float, default=60)
    start.add_argument("--app", default=DEFAULT_APP, help=argparse.SUPPRESS)
    for name in ("seed", "restart-api", "restart-db", "status", "stop"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--manifest", type=Path, required=True)
        if name == "seed":
            cmd.add_argument("--scenario", required=True, choices=sorted(scenarios.SCENARIOS))
            cmd.add_argument("--ordinal", type=int, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "start":
            stack = Stack.start(args.state_dir, app=args.app, api_port=args.api_port,
                                timeout=args.timeout)
            print(f"SENTINEL_STACK_MANIFEST={stack.path}")
            print(f"base_url={stack.manifest['api']['base_url']} "
                  f"scenarios={','.join(sorted(stack.manifest['scenarios']))}")
            return 0
        stack = Stack.load(args.manifest)
        if args.command == "seed":
            print(json.dumps(stack.seed(args.scenario, args.ordinal), sort_keys=True))
        elif args.command == "restart-api":
            stack.restart_api()
            print(f"api restarted pid={stack.manifest['api']['pid']}")
        elif args.command == "restart-db":
            stack.restart_db()
            print("database restarted")
        elif args.command == "status":
            print(json.dumps(stack.status()))
        else:
            print(json.dumps(stack.stop()))
        return 0
    except StackError as error:  # messages never contain tokens
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
