"""C08 review R28: API startup fails closed.

R28A - a launch is recorded before any inspection that can fail. If its identity cannot be
established (inspection raises, or the launcher is already gone while its child still
listens), startup exits nonzero with an unresolved launch record, and `down` refuses to stop
the database (or kill anything) until that launch's exit and port closure are proved.

R28B - success requires an actual healthy response from a verified owned process; an owned
listening port alone is not readiness. A timeout exits nonzero and either confirms owned
cleanup or keeps the recovery record.

`start_api` receives real test-owned processes through an intercepted Popen; `down` is the
real entrypoint with kill and database-stop requests intercepted unless stated."""
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import local_stack  # noqa: E402

# Stand-ins bind their pre-chosen port only when "launched" (a line on stdin), like a real
# launch, so start_api's pre-launch port-free check passes and the path under test runs.
GO = "import sys;port=int(sys.argv[1]);sys.stdin.readline()\n"
LISTEN = GO + ("import socket,time;s=socket.socket();s.bind(('127.0.0.1',port));s.listen();"
               "print('bound',flush=True);time.sleep(600)")
HEALTHY = GO + textwrap.dedent("""
    import json
    from http.server import BaseHTTPRequestHandler, HTTPServer
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200); self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "investigator": "stub"}).encode())
        def log_message(self, *a): pass
    server = HTTPServer(("127.0.0.1", port), H)
    print("bound", flush=True)
    server.serve_forever()
""")
# On launch, starts a detached listener and exits, so its pid is gone while the child
# listens (a launcher that died without its interpreter child). It runs on the base
# interpreter, so no venv launcher job object ties the child's lifetime to its parent.
ORPHANING = GO + textwrap.dedent("""
    import subprocess
    listen = "import socket,sys,time;s=socket.socket();s.bind(('127.0.0.1',int(sys.argv[1])));" \
             "s.listen();print('bound',flush=True);time.sleep(600)"
    child = subprocess.Popen([sys.executable, "-c", listen, str(port)], stdout=subprocess.PIPE,
                             text=True, creationflags=0x00000200 | 0x00000008)
    child.stdout.readline()
    print(child.pid, flush=True)
""")
FLAGS = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" \
    else {"start_new_session": True}


@pytest.fixture
def stack(tmp_path):
    s = local_stack.Stack(tmp_path / "stack")
    data = s.load(create=True)
    data["database"] = {"port": 54999}
    s.save(data)
    return s


@pytest.fixture
def intercepted(monkeypatch):
    calls = {"kill": [], "db_stop": []}
    monkeypatch.setattr(local_stack, "terminate_tree",
                        lambda pid: calls["kill"].append(pid) or True)
    monkeypatch.setattr(local_stack, "stop_database",
                        lambda stack, data: calls["db_stop"].append(True))
    return calls


@pytest.fixture
def spawned():
    owned = []

    def spawn(code, executable=sys.executable):
        port = local_stack_free_port()
        process = subprocess.Popen([executable, "-c", code, str(port)], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, text=True, **FLAGS)
        owned.append(process)
        return process, port
    yield spawn
    for process in owned:  # our own children, by handle; the tree for launcher children
        if process.poll() is None:
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"]
                           if os.name == "nt" else ["kill", str(process.pid)],
                           capture_output=True)


def local_stack_free_port():
    from sentinel import devdb
    return devdb.free_port()


def launch_as(monkeypatch, process, after=None):
    """The API launch starts this stand-in: it binds its port, then Popen returns it."""
    real_popen = subprocess.Popen

    def launched(command, *args, **kwargs):
        if "uvicorn" not in command:  # taskkill, PostgreSQL tools...: the real Popen
            return real_popen(command, *args, **kwargs)
        process.stdin.write("go\n")
        process.stdin.flush()
        line = process.stdout.readline().strip()
        if after:
            after(line)
        return process
    monkeypatch.setattr(local_stack.subprocess, "Popen", launched)


def start(stack, port):
    return local_stack.start_api(stack, stack.load(), port, "rule", "deterministic", "sentinel")


def down(stack):
    return local_stack.main(["--state-dir", str(stack.dir), "down"])


def test_r28a_identity_inspection_failure_keeps_an_unresolved_launch(
        stack, spawned, intercepted, monkeypatch):
    process, port = spawned(LISTEN)
    launch_as(monkeypatch, process)
    real_identity = local_stack.identity

    def failing(pid):
        if pid == process.pid:
            raise local_stack.StackError(f"process {pid} cannot be inspected")
        return real_identity(pid)
    monkeypatch.setattr(local_stack, "identity", failing)
    with pytest.raises(local_stack.StackError):
        start(stack, port)
    record = stack.load()["api"]
    assert record is not None and record["pid"] == process.pid and record["port"] == port
    monkeypatch.setattr(local_stack, "identity", real_identity)  # inspection works again,
    assert down(stack) == 1  # but this launch was never verified: refuse, keep, no stop
    assert intercepted == {"kill": [], "db_stop": []}
    assert process.poll() is None and stack.load()["api"]["pid"] == process.pid


def test_r28a_gone_launcher_with_a_live_listening_child_is_unresolved(
        stack, spawned, intercepted, monkeypatch):
    base = getattr(sys, "_base_executable", sys.executable)
    launcher, port = spawned(ORPHANING, executable=base)
    child = {}

    def orphaned(line):
        child["pid"] = int(line)
        launcher.wait(15)  # the launcher is gone before its identity is taken
    launch_as(monkeypatch, launcher, after=orphaned)
    try:
        with pytest.raises(local_stack.StackError):
            start(stack, port)
        child_pid = child["pid"]
        assert local_stack.identity(child_pid) is not None
        assert local_stack.listeners(port) == {child_pid}
        assert stack.load()["api"]["pid"] == launcher.pid
        assert down(stack) == 1
        assert intercepted == {"kill": [], "db_stop": []}
        assert local_stack.identity(child_pid) is not None  # untouched
    finally:
        if "pid" in child:  # our own orphan, by the pid its parent reported
            subprocess.run(["taskkill", "/PID", str(child["pid"]), "/F"] if os.name == "nt"
                           else ["kill", str(child["pid"])], capture_output=True)


def test_r28b_owned_port_without_health_is_not_ready(stack, spawned, monkeypatch):
    process, port = spawned(LISTEN)  # listens (owned port) but never answers /healthz
    launch_as(monkeypatch, process)
    monkeypatch.setattr(local_stack, "READY_SECONDS", 2)
    with pytest.raises(local_stack.StackError, match="failed to start"):
        start(stack, port)
    assert process.wait(20) is not None  # verified owned cleanup of our own process
    assert stack.load()["api"] is None and local_stack.port_state(port, None) == "free"


def test_r28b_timeout_with_failed_cleanup_keeps_recovery(stack, spawned, intercepted,
                                                          monkeypatch):
    process, port = spawned(LISTEN)
    launch_as(monkeypatch, process)
    monkeypatch.setattr(local_stack, "READY_SECONDS", 2)
    monkeypatch.setattr(local_stack, "STOP_SECONDS", 2)
    monkeypatch.setattr(local_stack, "terminate_tree",
                        lambda pid: intercepted["kill"].append(pid) or False)
    with pytest.raises(local_stack.StackError, match="recovery state kept"):
        start(stack, port)
    record = stack.load()["api"]
    assert record["pid"] == process.pid and record["start"] is not None
    assert down(stack) == 1 and intercepted["db_stop"] == []  # still running: no DB stop
    assert process.poll() is None


def test_positive_startup_requires_and_records_a_healthy_owned_api(stack, spawned,
                                                                    monkeypatch):
    process, port = spawned(HEALTHY)
    launch_as(monkeypatch, process)
    assert "API up" in start(stack, port)
    record = stack.load()["api"]
    assert record["pid"] == process.pid and record["start"] is not None
    assert "pending" not in record and record["listener"]["pid"] in \
        local_stack.listeners(port)
    monkeypatch.setattr(local_stack, "stop_database", lambda stack, data: None)
    assert down(stack) == 0  # real verified stop of our own healthy stand-in
    assert process.wait(20) is not None and local_stack.port_state(port, None) == "free"
