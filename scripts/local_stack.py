"""Local API + Postgres stack for operators (C08; review R24/R26 corrections).

All state lives in one owned directory (default .agent/stack/, git-ignored): an ownership
marker, a private state.json with the recorded process identities, the cluster data, the
API log and the private dev session token. Tokens and connection strings are never printed.

    uv run --locked python scripts/local_stack.py up [--scorer rule|model] [--database NAME]
        [--investigator deterministic|claude-cli|three-role] [--agent-adapter deterministic|claude-cli]
    uv run --locked python scripts/local_stack.py status
    uv run --locked python scripts/local_stack.py smoke [--restart-api]       # rule mode
    uv run --locked python scripts/local_stack.py backup [--out FILE]
    uv run --locked python scripts/local_stack.py restore FILE --database NAME  # API stopped
    uv run --locked python scripts/local_stack.py down

Ownership (R24): a process is touched only when its recorded identity (PID, creation time,
executable) still matches, and a port is "ours" only when every listener is the recorded API
process or one of its descendants (the venv python.exe is a launcher on Windows). Anything
else is refused without a kill, the record is kept, and the command exits nonzero. A stop is
reported only after the process is gone and the port is closed.

Authority: migrations, runtime grants, sessions, profiles and backups use the cluster
owner; the API connects as the least-privilege runtime role `sentinel_local_runtime`. The
scorer is explicit (`rule` by default). The deterministic investigator is the default.

Investigator (G3D-P3): `three-role` runs the coordinator with deterministic role adapters
unless `--agent-adapter claude-cli` is given; an inherited SENTINEL_AGENT_ADAPTER is never
used. The effective configuration is recorded and passed explicitly to the API, and a
restart reuses the record (never the ambient environment), so case pins stay valid.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
DEFAULT_STATE = ROOT / ".agent" / "stack"
MARKER = ".sentinel-local-stack"
DEFAULT_DATABASE = "sentinel"
RUNTIME_ROLE = "sentinel_local_runtime"
API_FACTORY = "sentinel.api:create_app"
SCORERS = {"rule": "rule", "model": "model:hgb_balanced@p1"}
# Deliberate local analyst capabilities: read_case also covers GET /v1/scoring and
# /v1/model-results/{id}; there is no admin capability.
CAPABILITIES = ("ingest_transaction", "read_case", "approve_action", "execute_simulated_action")
INVESTIGATORS = ("deterministic", "claude-cli", "three-role")
AGENT_ADAPTERS = ("deterministic", "claude-cli")
# Ambient settings that would otherwise reach the API and select a configuration the operator
# did not choose; the helper sets each one explicitly instead.
CONFIG_ENV = ("SENTINEL_INVESTIGATOR", "SENTINEL_AGENT_ADAPTER", "SENTINEL_CLAUDE_MODEL")
READY_SECONDS = 60
STOP_SECONDS = 20


class StackError(RuntimeError):
    """Refused or failed; state is kept for a retry. Messages never contain secrets."""


# ---- process and port identity ------------------------------------------------------------

def identity(pid: int) -> dict | None:
    """{"pid", "start", "exe"} for a live process, None if it does not exist. Raises
    StackError("unknown") when a live process cannot be inspected."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.windll.kernel32
        k32.OpenProcess.restype = wintypes.HANDLE
        handle = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            if ctypes.GetLastError() == 87:  # ERROR_INVALID_PARAMETER: no such process
                return None
            raise StackError(f"process {pid} cannot be inspected")
        try:
            code = wintypes.DWORD()
            k32.GetExitCodeProcess(handle, ctypes.byref(code))
            if code.value != 259:  # not STILL_ACTIVE
                return None
            times = [wintypes.FILETIME() for _ in range(4)]
            if not k32.GetProcessTimes(handle, *[ctypes.byref(t) for t in times]):
                raise StackError(f"process {pid} cannot be inspected")
            size = wintypes.DWORD(32768)
            buf = ctypes.create_unicode_buffer(size.value)
            if not k32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                raise StackError(f"process {pid} cannot be inspected")
            return {"pid": pid, "start": (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime,
                    "exe": os.path.normcase(buf.value)}
        finally:
            k32.CloseHandle(handle)
    proc = Path(f"/proc/{pid}")  # POSIX path: untested on this project's machines
    if not Path("/proc/self/stat").exists():
        raise StackError("process identity is unavailable on this platform (no /proc)")
    try:
        start = int(proc.joinpath("stat").read_text().rsplit(")", 1)[1].split()[19])
        exe = os.path.normcase(os.readlink(proc / "exe"))
    except FileNotFoundError:
        return None
    except (OSError, IndexError, ValueError):
        raise StackError(f"process {pid} cannot be inspected") from None
    return {"pid": pid, "start": start, "exe": exe}


def classify(record: dict | None) -> str:
    """owned | gone | reused | unknown for a recorded process identity."""
    if not record or not isinstance(record.get("pid"), int):
        return "gone" if not record else "unknown"
    if record.get("start") is None or not record.get("exe"):
        try:
            return "gone" if identity(record["pid"]) is None else "unknown"
        except StackError:
            return "unknown"
    try:
        current = identity(record["pid"])
    except StackError:
        return "unknown"
    if current is None:
        return "gone"
    same = current["start"] == record["start"] and current["exe"] == record["exe"]
    return "owned" if same else "reused"


def _windows_processes() -> dict[int, int]:
    """pid -> parent pid (toolhelp snapshot)."""
    import ctypes
    from ctypes import wintypes

    class Entry(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_void_p),
                    ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long),
                    ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_wchar * 260)]
    k32 = ctypes.windll.kernel32
    k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    snap = k32.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
    if snap in (None, wintypes.HANDLE(-1).value):
        raise StackError("process list unavailable")
    try:
        entry, parents = Entry(), {}
        entry.dwSize = ctypes.sizeof(Entry)
        ok = k32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            parents[entry.th32ProcessID] = entry.th32ParentProcessID
            ok = k32.Process32NextW(snap, ctypes.byref(entry))
        return parents
    finally:
        k32.CloseHandle(snap)


def _posix_processes() -> dict[int, int]:
    parents = {}
    for entry in Path("/proc").iterdir():
        if entry.name.isdigit():
            try:
                parents[int(entry.name)] = int(
                    (entry / "stat").read_text().rsplit(")", 1)[1].split()[1])
            except (OSError, IndexError, ValueError):
                continue
    return parents


def descendants(root: int) -> set[int]:
    parents = _windows_processes() if os.name == "nt" else _posix_processes()
    found, frontier = set(), {root}
    while frontier:
        children = {pid for pid, parent in parents.items() if parent in frontier} - found
        found |= children
        frontier = children
    return found


def listeners(port: int) -> set[int]:
    """PIDs listening on TCP port (IPv4). Raises StackError when it cannot be determined."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        iphlpapi = ctypes.windll.iphlpapi
        size = wintypes.DWORD(0)
        iphlpapi.GetExtendedTcpTable(None, ctypes.byref(size), False, 2, 3, 0)
        buf = ctypes.create_string_buffer(size.value + 4096)
        size = wintypes.DWORD(len(buf))
        if iphlpapi.GetExtendedTcpTable(buf, ctypes.byref(size), False, 2, 3, 0) != 0:
            raise StackError("listening sockets cannot be inspected")
        count = int.from_bytes(buf.raw[:4], "little")
        pids = set()
        for i in range(count):  # MIB_TCPROW_OWNER_PID: six DWORDs
            row = buf.raw[4 + 24 * i: 4 + 24 * (i + 1)]
            local_port = socket.ntohs(int.from_bytes(row[8:12], "little") & 0xFFFF)
            if local_port == port:
                pids.add(int.from_bytes(row[20:24], "little"))
        return pids
    inodes = set()  # POSIX path: untested on this project's machines
    try:
        for table in ("/proc/net/tcp", "/proc/net/tcp6"):
            for line in Path(table).read_text().splitlines()[1:]:
                fields = line.split()
                if fields[3] == "0A" and int(fields[1].rsplit(":", 1)[1], 16) == port:
                    inodes.add(fields[9])
    except OSError:
        raise StackError("listening sockets cannot be inspected") from None
    pids = set()
    for entry in Path("/proc").iterdir():
        if entry.name.isdigit() and inodes:
            try:
                for fd in (entry / "fd").iterdir():
                    target = os.readlink(fd)
                    if target.startswith("socket:[") and target[8:-1] in inodes:
                        pids.add(int(entry.name))
            except OSError:
                continue
    if inodes and not pids:
        raise StackError("listening socket owner cannot be determined")
    return pids


def port_state(port: int, root: int | None) -> str:
    """free | owned (every listener is root or its descendant) | foreign | unknown."""
    try:
        found = listeners(port)
        if not found:
            return "free"
        if root is None:
            return "foreign"
        family = {root} | descendants(root)
    except StackError:
        return "unknown"
    return "owned" if found <= family else "foreign"


def terminate_tree(pid: int) -> bool:
    """Request termination of one verified process tree. True if the request was accepted."""
    if os.name == "nt":
        return subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                              capture_output=True).returncode == 0
    try:
        os.killpg(pid, signal.SIGTERM)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def wait_until(predicate, seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.2)
    return predicate()


def healthy(port: int) -> dict | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=2) as response:
            return json.loads(response.read())
    except (OSError, ValueError):
        return None


# ---- the owned state directory -------------------------------------------------------------

class Stack:
    def __init__(self, directory: Path):
        self.dir = Path(directory)
        self.path = self.dir / "state.json"

    def canonical(self) -> str:
        return os.path.normcase(os.path.realpath(self.dir))

    def load(self, create: bool = False) -> dict:
        """The verified state. A directory without our marker is never adopted."""
        marker = self.dir / MARKER
        if not self.dir.exists() or (create and not any(self.dir.iterdir())):
            if not create:
                raise StackError(f"no local stack at {self.dir} (run up first)")
            self.dir.mkdir(parents=True, exist_ok=True)
            owner = secrets.token_hex(16)
            marker.write_text(json.dumps({"owner": owner, "dir": self.canonical()}))
            self.save({"version": 2, "owner": owner, "dir": self.canonical(),
                       "database": {}, "api": None})
        if os.path.islink(self.dir) or not marker.is_file() or not self.path.is_file():
            raise StackError(f"{self.dir} is not an owned local stack directory (refused)")
        try:
            owned = json.loads(marker.read_text())
            data = json.loads(self.path.read_text())
        except (OSError, ValueError):
            raise StackError("stack state is unreadable (refused)") from None
        if not (isinstance(data, dict) and data.get("version") == 2
                and secrets.compare_digest(str(owned.get("owner")), str(data.get("owner")))
                and owned.get("dir") == data.get("dir") == self.canonical()):
            raise StackError("ownership marker does not match the stack state (refused)")
        return data

    def save(self, data: dict) -> None:
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
        try:
            self.path.chmod(0o600)
        except OSError:
            pass


# ---- database ------------------------------------------------------------------------------

def cluster(stack: Stack, port: int):
    from sentinel import devdb
    bin_dir = devdb.find_pg_bin()
    if bin_dir is None:
        raise StackError("PostgreSQL initdb not found; set SENTINEL_PG_BIN")
    return devdb.Cluster(bin_dir, stack.dir / "pg" / "data", port)


def pg_status(c) -> str:
    try:
        code = subprocess.run([str(c.bin_dir / "pg_ctl"), "-D", str(c.data_dir), "status"],
                              stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, timeout=30).returncode
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return {0: "running", 3: "stopped"}.get(code, "unknown")


def database_state(stack: Stack, data: dict) -> str:
    """absent | stopped | owned | foreign | unknown for the recorded cluster."""
    port = data["database"].get("port")
    if port is None:
        return "absent"
    c = cluster(stack, port)
    if not (c.data_dir / "PG_VERSION").exists():
        return "absent" if port_state(port, None) == "free" else "foreign"
    status = pg_status(c)
    if status == "stopped":
        return "stopped" if port_state(port, None) == "free" else "foreign"
    if status != "running":
        return "unknown"
    try:  # postmaster.pid: pid, data directory, start time, port
        lines = (c.data_dir / "postmaster.pid").read_text().splitlines()
        pid, data_dir, pg_port = int(lines[0]), lines[1], int(lines[3])
        proc = identity(pid)
    except (OSError, IndexError, ValueError, StackError):
        return "unknown"
    expected_exe = os.path.normcase(str(c.bin_dir / ("postgres.exe" if os.name == "nt"
                                                       else "postgres")))
    same_dir = os.path.normcase(os.path.realpath(data_dir)) == \
        os.path.normcase(os.path.realpath(c.data_dir))
    if not (proc and proc["exe"] == expected_exe and same_dir and pg_port == port):
        return "foreign"
    return "owned" if port_state(port, pid) == "owned" else "foreign"


def owner_url(stack: Stack, data: dict, database: str | None = None) -> str:
    c = cluster(stack, data["database"]["port"])
    return c.url(database) if database else c.url()  # default: the maintenance database


def start_database(stack: Stack, data: dict, port: int) -> None:
    data["database"].setdefault("port", port)
    state = database_state(stack, data)
    if state == "owned":
        return
    if state in ("foreign", "unknown"):
        raise StackError(f"database port {data['database']['port']} or cluster is not ours "
                         f"({state}); refused")
    c = cluster(stack, data["database"]["port"])
    if state == "absent":
        c.init()
    stack.save(data)
    c.start()
    if database_state(stack, data) != "owned":
        raise StackError("database started but could not be verified as ours")


def stop_database(stack: Stack, data: dict) -> None:
    state = database_state(stack, data)
    if state in ("absent", "stopped"):
        return
    if state != "owned":
        raise StackError(f"database is {state}; not stopped (refused)")
    c = cluster(stack, data["database"]["port"])
    try:
        c.stop()
    except (subprocess.SubprocessError, OSError):
        pass
    if not wait_until(lambda: database_state(stack, data) == "stopped", STOP_SECONDS):
        raise StackError("database stop could not be verified; state kept, retry down")


# ---- investigator configuration -------------------------------------------------------------

def requested_config(investigator: str, adapter: str | None) -> dict:
    """The effective investigator configuration of an `up` request. The adapter applies only
    to three-role (deterministic unless chosen explicitly). A live configuration keeps the
    model the API would otherwise read (SENTINEL_CLAUDE_MODEL, default sonnet) so a restart
    pins the same config."""
    if investigator not in INVESTIGATORS:
        raise StackError(f"unknown investigator {investigator}")
    if investigator != "three-role":
        if adapter is not None:
            raise StackError("--agent-adapter applies only to --investigator three-role")
    else:
        adapter = adapter or "deterministic"
        if adapter not in AGENT_ADAPTERS:
            raise StackError(f"unknown agent adapter {adapter}")
    live = investigator == "claude-cli" or adapter == "claude-cli"
    model = (os.environ.get("SENTINEL_CLAUDE_MODEL") or "sonnet") if live else None
    return {"investigator": investigator, "adapter": adapter, "claude_model": model}


def recorded_config(record: dict) -> dict:
    """The configuration a restart must reproduce, from the API record only. A record from
    before G3D-P3 is accepted for deterministic; one that leaves a three-role adapter or a
    live model unstated is refused rather than guessed."""
    investigator, adapter = record.get("investigator"), record.get("adapter")
    model = record.get("claude_model")
    if investigator not in INVESTIGATORS:
        raise StackError("the API record has no usable investigator; restart refused "
                         "(down, then up)")
    if investigator == "three-role" and adapter not in AGENT_ADAPTERS:
        raise StackError("the three-role API record does not state its agent adapter; restart "
                         "refused (down, then up --agent-adapter ...)")
    if investigator != "three-role" and adapter is not None:
        raise StackError("the API record is inconsistent (adapter without three-role); "
                         "restart refused (down, then up)")
    live = investigator == "claude-cli" or adapter == "claude-cli"
    if live != bool(model):
        raise StackError("the API record does not state the live model it was started with; "
                         "restart refused (down, then up)")
    return {"investigator": investigator, "adapter": adapter, "claude_model": model}


def describe(config: dict) -> str:
    text = config["investigator"]
    if config["adapter"]:
        text += f" (adapter {config['adapter']})"
    if config["claude_model"]:
        text += f" (model {config['claude_model']})"
    return text


def child_environment(url: str, scorer: str, config: dict) -> dict:
    env = {k: v for k, v in os.environ.items()
           if k not in CONFIG_ENV and k != "SENTINEL_TEST_DATABASE_URL"}
    env.update({"SENTINEL_DATABASE_URL": url, "SENTINEL_SCORER": SCORERS[scorer],
                "SENTINEL_INVESTIGATOR": config["investigator"], "SENTINEL_MODE": "local",
                # Serve this checkout's code, never another installed copy.
                "PYTHONPATH": os.pathsep.join([str(ROOT / "src"), str(ROOT)])})
    if config["adapter"]:
        env["SENTINEL_AGENT_ADAPTER"] = config["adapter"]
    if config["claude_model"]:
        env["SENTINEL_CLAUDE_MODEL"] = config["claude_model"]
    return env


# ---- API -----------------------------------------------------------------------------------

def tree_alive(pid: int) -> bool:
    """A live descendant of pid (Windows keeps an orphan's parent pid). Unknown -> alive."""
    try:
        return bool(descendants(pid))
    except StackError:
        return True


def launch_unresolved(record: dict) -> bool:
    """A launch whose identity was never established is resolved only when its pid is gone,
    no descendant survives and its port is free; anything else (or not knowing) is
    unresolved. Such a launch is never killed."""
    if not isinstance(record.get("pid"), int):
        return True  # the launch may have happened before its pid was recorded
    try:
        alive = identity(record["pid"]) is not None
    except StackError:
        return True
    return alive or tree_alive(record["pid"]) or port_state(record["port"], None) != "free"


def api_state(data: dict) -> str:
    """down | owned | unresolved-launch | gone-but-port-busy | reused | unknown."""
    record = data.get("api")
    if not record:
        return "down"
    if record.get("pending"):
        return "unresolved-launch" if launch_unresolved(record) else "down"
    kind = classify(record)
    port_now = port_state(record["port"], record.get("pid") if kind == "owned" else None)
    if kind == "owned":
        return "owned" if port_now in ("owned", "free") else "unknown"
    if kind == "gone" and port_now == "free" and tree_alive(record["pid"]):
        return "gone-but-child-alive"  # the launcher exited, its interpreter did not
    if kind in ("gone", "reused") and port_now == "free":
        return "down"
    return kind if kind != "gone" else "gone-but-port-busy"


def stop_api(stack: Stack, data: dict) -> str:
    """Stop only a verified owned API; return what happened. Raises on refusal/failure."""
    record = data.get("api")
    state = api_state(data)
    if state == "down":
        if record:
            data["api"] = None
            stack.save(data)
            return "api already exited (record cleared; no process touched)"
        return "api not running"
    if state != "owned":
        raise StackError(f"recorded API is {state}; no process was touched (refused)")
    accepted = terminate_tree(record["pid"])
    stopped = wait_until(lambda: classify(record) == "gone"
                         and classify(record.get("listener")) != "owned"
                         and not tree_alive(record["pid"])
                         and port_state(record["port"], None) == "free", STOP_SECONDS)
    if not stopped:
        raise StackError(f"API stop not confirmed (request {'accepted' if accepted else 'failed'})"
                         "; identity kept, retry down")
    data["api"] = None
    stack.save(data)
    return "api stopped"


def start_api(stack: Stack, data: dict, port: int, scorer: str, config: dict,
              database: str) -> str:
    current = api_state(data)
    if current == "owned":
        return f"API already running (owned) on port {data['api']['port']}"
    if current != "down":
        raise StackError(f"recorded API is {current}; refused to start another")
    if port_state(port, None) != "free":
        raise StackError(f"port {port} is in use by another process; refused")
    from psycopg.conninfo import make_conninfo
    env = child_environment(make_conninfo(owner_url(stack, data, database), user=RUNTIME_ROLE),
                            scorer, config)
    flags = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" \
        else {"start_new_session": True}
    # Recovery authority exists before the launch and before any inspection that can fail
    # (R28A): an unresolved launch blocks `down` from stopping the database.
    data["api"] = {"pending": True, "pid": None, "port": port, "scorer": scorer,
                   **config, "database": database}
    stack.save(data)
    try:
        with open(stack.dir / "api.log", "ab") as log:
            process = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", API_FACTORY, "--factory", "--host",
                 "127.0.0.1", "--port", str(port), "--log-level", "warning",
                 "--no-access-log"],
                cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log, **flags)
    except OSError as error:  # nothing was launched
        data["api"] = None
        stack.save(data)
        raise StackError(f"API could not be launched ({type(error).__name__})") from None
    data["api"]["pid"] = process.pid
    stack.save(data)
    try:
        record = identity(process.pid)
    except StackError:
        record = None
    if record is None:
        raise StackError(f"API launch (pid {process.pid}) could not be verified; unresolved "
                         "launch recorded and nothing killed. Once it has exited and port "
                         f"{port} is free, run down")
    data["api"] = {**data["api"], **record}
    del data["api"]["pending"]
    stack.save(data)

    def serving() -> bool:  # a healthy response from our own process tree (R28B)
        return process.poll() is None and healthy(port) is not None \
            and port_state(port, process.pid) == "owned"
    wait_until(lambda: process.poll() is not None or serving(), READY_SECONDS)
    if serving():
        child = next(iter(listeners(port) - {process.pid}), process.pid)
        try:
            data["api"]["listener"] = identity(child)
        except StackError:
            data["api"]["listener"] = None
        stack.save(data)
        return (f"API up on port {port} (scorer {scorer}, investigator {describe(config)}, "
                f"database {database})")
    try:
        outcome = stop_api(stack, data)
    except StackError as error:
        raise StackError(f"API failed to start and cleanup was not confirmed ({error}); "
                         "recovery state kept, run down") from None
    raise StackError(f"API failed to start ({outcome}); see api.log")


# ---- commands ------------------------------------------------------------------------------

def ensure_session(stack: Stack, url: str) -> None:
    """Reuse the stored dev token if it still authenticates against this database (a
    restored database keeps its sessions); otherwise issue one. Never printed."""
    from sentinel.investigators import DeterministicInvestigator
    from sentinel.service import Sentinel, ServiceError
    path = stack.dir / "session.json"
    if path.exists():
        stored = json.loads(path.read_text())
        try:
            Sentinel(url, DeterministicInvestigator()).authenticate(stored["token"])
            return
        except (ServiceError, KeyError):
            pass  # expired or unknown in this database
    token, ctx = Sentinel(url, DeterministicInvestigator()).create_session(
        frozenset(CAPABILITIES), ttl=timedelta(hours=8))
    path.write_text(json.dumps({"token": token, "tenant_id": str(ctx.scope.tenant_id),
                                "session_id": str(ctx.scope.session_id),
                                "expires_at": (datetime.now(timezone.utc)
                                               + timedelta(hours=8)).isoformat()}))
    try:
        path.chmod(0o600)
    except OSError:
        pass


def up(stack: Stack, args) -> str:
    import psycopg

    from sentinel import db
    from sentinel.db import roles
    config = requested_config(args.investigator, args.agent_adapter)  # before any state
    data = stack.load(create=True)
    current = api_state(data)
    if current not in ("down", "owned"):
        raise StackError(f"recorded API is {current}; refused")
    if current == "owned":
        running_matches(data, args, config)
    if current == "down" and port_state(args.port, None) != "free":
        raise StackError(f"port {args.port} is in use by another process; refused")
    start_database(stack, data, args.db_port)
    database = args.database
    with psycopg.connect(owner_url(stack, data), autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s",
                              (database,)).fetchone()
        if not exists:
            if database != DEFAULT_DATABASE:  # never create an empty rollback target
                raise StackError(f"database {database} does not exist; refused")
            conn.execute(f'CREATE DATABASE "{DEFAULT_DATABASE}"')
    url = owner_url(stack, data, database)
    applied = db.migrate(url)
    try:
        roles.grant_runtime(url, RUNTIME_ROLE)
    except RuntimeError as error:  # includes UnsafeRoleError; messages carry no secrets
        raise StackError(f"runtime role not granted: {error}") from None
    ensure_session(stack, url)
    lines = [f"migrations applied: {', '.join(applied) or 'none pending'}"]
    lines.append(start_api(stack, data, args.port, args.scorer, config, database))
    lines.append(f"token in {stack.dir / 'session.json'} (not printed)")
    return "\n".join(lines)


def running_matches(data: dict, args, config: dict) -> None:
    """`up` against the running owned API changes nothing: an equal request is idempotent,
    any difference is refused with the process and its record left alone."""
    record = data["api"]
    try:
        running = describe(recorded_config(record))
    except StackError:
        running = "unstated"
    wanted = {"port": args.port, "database port": args.db_port, "scorer": args.scorer,
              "database": args.database, "investigator": describe(config)}
    have = {"port": record.get("port"), "database port": data["database"].get("port"),
            "scorer": record.get("scorer"), "database": record.get("database"),
            "investigator": running}
    changed = [f"{k} {have[k]} -> {wanted[k]}" for k in wanted if wanted[k] != have[k]]
    if changed:
        raise StackError("the API is already running with a different configuration ("
                         + "; ".join(changed) + "); nothing was changed (down, then up)")


def down(stack: Stack, args) -> str:
    data = stack.load()
    problems, lines = [], []
    try:
        lines.append(stop_api(stack, data))
    except StackError as error:
        problems.append(str(error))
    if not problems:  # never stop the database under an API we could not account for
        try:
            stop_database(stack, data)
            lines.append("database stopped (data kept)")
        except StackError as error:
            problems.append(str(error))
    if problems:
        raise StackError("; ".join(problems))
    return "\n".join(lines)


def status(stack: Stack, args) -> str:
    data = stack.load()
    api, database = api_state(data), database_state(stack, data)
    record = data.get("api") or {}
    try:
        investigator = describe(recorded_config(record))
    except StackError:
        investigator = f"{record.get('investigator')} (configuration unstated)"
    text = (f"database: {database}; api: {api}"
            + (f" (port {record['port']}, scorer {record['scorer']}, investigator "
               f"{investigator}, database {record['database']})" if api == "owned" else ""))
    if api != "owned" or database != "owned":
        raise StackError(text)
    return text


def smoke(stack: Stack, args) -> str:
    data = stack.load()
    record = data.get("api") or {}
    if api_state(data) != "owned" or record.get("scorer") != "rule":
        raise StackError("smoke needs an owned API in rule mode (up --scorer rule)")
    config = recorded_config(record) if args.restart_api else None  # refuse before any work
    token = json.loads((stack.dir / "session.json").read_text())["token"]
    base = f"http://127.0.0.1:{record['port']}"
    env = {**os.environ, "SENTINEL_TOKEN": token}
    script = [sys.executable, str(ROOT / "scripts" / "smoke_thin_path.py"), "--base-url", base]
    first = subprocess.run([*script, "investigate"], env=env, capture_output=True, text=True,
                           check=True).stdout
    case_id = first.rsplit("CASE_ID=", 1)[1].strip()
    lines = [first.strip()]
    if args.restart_api:
        lines.append(stop_api(stack, data))
        lines.append(start_api(stack, data, record["port"], record["scorer"], config,
                               record["database"]))
    lines.append(subprocess.run([*script, "execute", case_id], env=env, capture_output=True,
                                text=True, check=True).stdout.strip())
    return "\n".join(lines)


def backup(stack: Stack, args) -> str:
    data = stack.load()
    if database_state(stack, data) != "owned":
        raise StackError("backup needs the owned database running (up)")
    database = (data.get("api") or {}).get("database") or args.database
    out = args.out or stack.dir.parent / "backups" / \
        f"{database}-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.dump"
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    c = cluster(stack, data["database"]["port"])
    done = subprocess.run([str(c.bin_dir / "pg_dump"), "--format=custom", "--no-owner",
                           f"--file={out}", owner_url(stack, data, database)],
                          capture_output=True, text=True)
    if done.returncode != 0:
        raise StackError(f"pg_dump failed ({done.returncode})")
    return f"backup of {database} written: {out}"


def restore(stack: Stack, args) -> str:
    """Into a NEW database with the API stopped. Starts (and verifies) only the owned
    cluster, restores, reports the schema version, and neither migrates nor starts an API."""
    import psycopg
    data = stack.load()
    if not args.database.isidentifier() or args.database == DEFAULT_DATABASE:
        raise StackError("restore target must be a new plain identifier, not the live "
                         "database")
    if api_state(data) != "down":
        raise StackError("stop the API first (down); restore never runs under a live API")
    start_database(stack, data, data["database"].get("port") or args.db_port)
    with psycopg.connect(owner_url(stack, data), autocommit=True) as conn:
        if conn.execute("SELECT 1 FROM pg_database WHERE datname = %s",
                        (args.database,)).fetchone():
            raise StackError(f"database {args.database} already exists; refused")
        conn.execute(f'CREATE DATABASE "{args.database}"')
    c = cluster(stack, data["database"]["port"])
    done = subprocess.run([str(c.bin_dir / "pg_restore"), "--no-owner", "--exit-on-error",
                           f"--dbname={owner_url(stack, data, args.database)}", str(args.file)],
                          capture_output=True, text=True)
    if done.returncode != 0:
        raise StackError(f"pg_restore failed ({done.returncode}); {args.database} is "
                         "incomplete, drop it before retrying")
    with psycopg.connect(owner_url(stack, data, args.database)) as conn:
        names = [r[0] for r in conn.execute("SELECT name FROM schema_migrations ORDER BY name")]
        tables = conn.execute("SELECT count(*) FROM information_schema.tables WHERE "
                              "table_schema = 'public' AND table_type = 'BASE TABLE'"
                              ).fetchone()[0]
    return (f"restored {args.file} into {args.database}: {tables} tables, migrations "
            f"{', '.join(names)}; not migrated, no API started (database left running)")


COMMANDS = {"up": up, "down": down, "status": status, "smoke": smoke, "backup": backup,
            "restore": restore}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db-port", type=int, default=55433)
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE)
    sub = parser.add_subparsers(dest="command", required=True)
    up_cmd = sub.add_parser("up")
    up_cmd.add_argument("--investigator", choices=INVESTIGATORS, default="deterministic")
    up_cmd.add_argument("--agent-adapter", choices=AGENT_ADAPTERS, default=None,
                        help="three-role only; deterministic unless given (never inherited)")
    up_cmd.add_argument("--scorer", choices=sorted(SCORERS), default="rule")
    up_cmd.add_argument("--database", default=DEFAULT_DATABASE)
    sub.add_parser("down")
    sub.add_parser("status")
    sub.add_parser("smoke").add_argument("--restart-api", action="store_true")
    backup_cmd = sub.add_parser("backup")
    backup_cmd.add_argument("--out", type=Path)
    backup_cmd.add_argument("--database", default=DEFAULT_DATABASE)
    restore_cmd = sub.add_parser("restore")
    restore_cmd.add_argument("file", type=Path)
    restore_cmd.add_argument("--database", required=True)
    args = parser.parse_args(argv)
    try:
        print(COMMANDS[args.command](Stack(args.state_dir), args))
        return 0
    except StackError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
