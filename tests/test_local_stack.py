"""C08 review R24: the operator stack touches only resources it can prove it owns, refuses
reused/foreign/unknown identities without a kill, reports a stop only after the process is
gone and the port is closed, and keeps its recovery record when cleanup fails. All tests use
the real entrypoint `main(argv)` with a private --state-dir; destructive requests are
intercepted in the negative cases."""
import json
import os
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import local_stack  # noqa: E402
from sentinel import devdb  # noqa: E402

needs_pg = pytest.mark.skipif(devdb.find_pg_bin() is None, reason="needs PostgreSQL binaries")


def cli(state_dir, *argv, port=None, db_port=None):
    args = ["--state-dir", str(state_dir)]
    if port:
        args += ["--port", str(port)]
    if db_port:
        args += ["--db-port", str(db_port)]
    return local_stack.main([*args, *argv])


@pytest.fixture
def kills(monkeypatch):
    """Intercept every termination request; nothing is killed."""
    requested = []
    monkeypatch.setattr(local_stack, "terminate_tree", lambda pid: requested.append(pid) or True)
    return requested


@pytest.fixture
def owned_dir(tmp_path):
    stack = local_stack.Stack(tmp_path / "stack")
    stack.load(create=True)
    return stack


def record_api(stack, record):
    data = stack.load()
    data["api"] = record
    stack.save(data)


def free_port():
    return devdb.free_port()


@pytest.fixture
def listener():
    """A foreign process-less socket on a port (this test process listens)."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen()
    yield sock.getsockname()[1]
    sock.close()


@pytest.fixture
def foreign_api():
    """A foreign healthy server answering /healthz like the API would."""
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status":"ok","investigator":"foreign"}')

        def log_message(self, *args):
            pass
    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server.server_address[1]
    server.shutdown()


@pytest.fixture
def dummy():
    """A real process of ours (same interpreter) listening on a port, standing in for the API
    so stop can be exercised on a genuinely owned identity."""
    code = ("import socket,sys,time;s=socket.socket();s.bind(('127.0.0.1',0));s.listen();"
            "print(s.getsockname()[1],flush=True);time.sleep(600)")
    flags = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" \
        else {"start_new_session": True}
    process = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True,
                               **flags)
    port = int(process.stdout.readline())
    yield process, port
    if process.poll() is None:  # our own child: cleanup by handle, never by name
        process.kill()
        process.wait(10)


def test_a_directory_without_our_marker_is_never_adopted(tmp_path, kills):
    foreign = tmp_path / "stack"
    foreign.mkdir()
    (foreign / "state.json").write_text(json.dumps({"api": {"pid": os.getpid()}}))
    assert cli(foreign, "down") == 1 and cli(foreign, "status") == 1
    assert kills == [] and json.loads((foreign / "state.json").read_text())["api"]
    assert cli(tmp_path / "absent", "down") == 1  # nothing created by down


def test_reused_pid_is_never_killed(owned_dir, kills, listener):
    me = local_stack.identity(os.getpid())  # alive, but not the recorded process
    record_api(owned_dir, {**me, "start": me["start"] - 1, "port": listener, "scorer": "rule",
                           "investigator": "deterministic", "database": "sentinel"})
    assert cli(owned_dir.dir, "down") == 1  # its port is still served: refused, kept
    assert kills == [] and owned_dir.load()["api"]["pid"] == os.getpid()


def test_reused_pid_with_a_closed_port_is_cleared_without_a_kill(owned_dir, kills):
    me = local_stack.identity(os.getpid())
    record_api(owned_dir, {**me, "start": me["start"] - 1, "port": free_port(),
                           "scorer": "rule", "investigator": "deterministic",
                           "database": "sentinel"})
    assert cli(owned_dir.dir, "down") == 0  # the recorded process had exited (PID reused)
    assert kills == [] and owned_dir.load()["api"] is None


def test_missing_identity_is_refused_without_a_kill(owned_dir, kills):
    record_api(owned_dir, {"pid": os.getpid(), "port": free_port()})  # no start/exe
    assert cli(owned_dir.dir, "down") == 1
    assert kills == [] and owned_dir.load()["api"] == {"pid": os.getpid(),
                                                       "port": owned_dir.load()["api"]["port"]}


def test_foreign_healthy_api_on_the_port_is_refused(owned_dir, foreign_api, kills, monkeypatch):
    started = []
    monkeypatch.setattr(local_stack.subprocess, "Popen", lambda *a, **k: started.append(a))
    assert cli(owned_dir.dir, "up", port=foreign_api, db_port=free_port()) == 1
    assert started == [] and kills == [] and owned_dir.load()["api"] is None
    assert owned_dir.load()["database"] == {}  # refused before any database work


def test_foreign_process_on_the_database_port_is_refused(owned_dir, listener, monkeypatch):
    calls = []
    real = local_stack.cluster

    def watched(stack, port):
        c = real(stack, port)
        c.init = lambda: calls.append("init")
        c.start = lambda: calls.append("start")
        return c
    monkeypatch.setattr(local_stack, "cluster", watched)
    assert cli(owned_dir.dir, "up", port=free_port(), db_port=listener) == 1
    assert calls == []  # neither initdb nor pg_ctl start on a port someone else holds


def test_failed_stop_keeps_the_identity_and_a_retry_completes(owned_dir, dummy, monkeypatch):
    process, port = dummy
    me = local_stack.identity(process.pid)
    record_api(owned_dir, {**me, "port": port, "scorer": "rule", "investigator": "deterministic",
                           "database": "sentinel"})
    assert local_stack.api_state(owned_dir.load()) == "owned"
    monkeypatch.setattr(local_stack, "STOP_SECONDS", 2)
    monkeypatch.setattr(local_stack, "terminate_tree", lambda pid: False)  # stop fails
    assert cli(owned_dir.dir, "down") == 1
    assert process.poll() is None and owned_dir.load()["api"]["pid"] == process.pid
    monkeypatch.undo()  # the real, verified stop of our own process
    assert cli(owned_dir.dir, "down") == 0
    assert process.wait(15) is not None and owned_dir.load()["api"] is None
    assert local_stack.port_state(port, None) == "free"


@needs_pg
def test_startup_failure_cleans_up_the_owned_api_and_keeps_the_database(tmp_path, monkeypatch):
    state, api_port, db_port = tmp_path / "stack", free_port(), free_port()
    monkeypatch.setattr(local_stack, "API_FACTORY", "sentinel.no_such_module:create_app")
    try:
        assert cli(state, "up", port=api_port, db_port=db_port) == 1
        data = local_stack.Stack(state).load()
        assert data["api"] is None  # the failed API was verified gone, then cleared
        assert local_stack.port_state(api_port, None) == "free"
        assert local_stack.database_state(local_stack.Stack(state), data) == "owned"
    finally:
        assert cli(state, "down") == 0
    data = local_stack.Stack(state).load()
    assert local_stack.database_state(local_stack.Stack(state), data) == "stopped"
