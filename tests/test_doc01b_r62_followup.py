"""DOC01 Part B re-review aca58f2, R62: unknown process state must not clear a bridge record,
and bridge evidence must survive a failed write or replace and an API restart.

Real test-owned processes carry genuine identities; lookup, write and replace failures are
injected. Failing-first against aca58f2 (see the branch handoff)."""
import json
import os
import pathlib
import subprocess
import sys
import time

import pytest

from sentinel import documents as docs
from test_documents_api import Stack, _handle, _pid_alive



def _live(pid) -> bool:
    """Running (a zombie on POSIX is exited, not running), unlike `kill(pid, 0)`."""
    return bool(pid) and docs.process_state(pid)[0] == docs.LIVE


def _records(store):
    folder = store / docs.BRIDGE_RECORD_DIR
    return sorted(p.name for p in folder.iterdir()) if folder.is_dir() else []


def _stop(pid):
    """Test-owned cleanup by exact pid (never by name)."""
    if pid and _pid_alive(pid):
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
        else:
            os.kill(pid, 9)


def _sleeper():
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    deadline = time.monotonic() + 10
    while docs.process_identity(proc.pid) is None and time.monotonic() < deadline:
        time.sleep(0.05)
    identity = docs.process_identity(proc.pid)
    assert identity is not None
    return proc, identity


def _plant(store, pid, identity, name=None):
    folder = store / docs.BRIDGE_RECORD_DIR
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (name or f"bridge-{pid}.json")
    path.write_text(json.dumps({"pid": pid, "identity": identity, "op": "analyze"}))
    return path


def _unknown_lookup(monkeypatch, signals):
    """Every identity lookup is unreadable (inaccessible / permission / I/O)."""
    monkeypatch.setattr(docs, "process_identity", lambda pid: None)
    monkeypatch.setattr(docs, "process_state", lambda pid: (docs.UNKNOWN, None),
                        raising=False)
    monkeypatch.setattr(docs, "_terminate_pid", lambda pid: signals.append(pid))


@pytest.fixture
def stack(database_url, clock, tmp_path):
    s = Stack(database_url, clock, tmp_path / "store")
    s.fake()
    return s


# ---- 1. unknown is not gone --------------------------------------------------------------

def test_unknown_lookup_keeps_the_record_blocks_and_never_signals(stack, database_url, clock,
                                                                  monkeypatch):
    proc, identity = _sleeper()
    try:
        token = stack.session()
        handle = _handle(stack, token)
        record = _plant(stack.store, proc.pid, identity)
        signals = []
        _unknown_lookup(monkeypatch, signals)
        response = stack.analyze(token, handle)
        assert response.json() == {"error": "document_worker_recovery_pending"}
        restarted = Stack(database_url, clock, stack.store)  # fresh API instance
        assert restarted.analyze(token, handle).json() == {
            "error": "document_worker_recovery_pending"}
        assert signals == [] and proc.poll() is None  # never signalled, still alive
        assert record.exists()
        monkeypatch.undo()
        # The lookup works again: the genuine identity verifies; recovery stops it.
        verified = Stack(database_url, clock, stack.store)
        assert verified.analyze(token, handle).status_code == 200
        assert proc.wait(timeout=20) is not None
        assert _records(stack.store) == []
    finally:
        if proc.poll() is None:
            proc.kill()


# Platform-specific lookups are *defined* only where they apply, not collected and
# skipped: the CI test gate permits exactly one skip (the opt-in live Claude test).
if os.name != "nt":
    def test_no_proc_filesystem_is_unknown_not_gone(stack, database_url, clock, monkeypatch):
        """macOS-style: no /proc at all. The record stays and nothing is signalled."""
        proc, identity = _sleeper()
        try:
            token = stack.session()
            handle = _handle(stack, token)
            _plant(stack.store, proc.pid, identity)
            signals = []
            monkeypatch.setattr(docs, "PROC_ROOT", "/nonexistent-proc", raising=False)
            monkeypatch.setattr(docs, "_terminate_pid", lambda pid: signals.append(pid))
            assert stack.analyze(token, handle).json() == {
                "error": "document_worker_recovery_pending"}
            assert signals == [] and proc.poll() is None
        finally:
            proc.kill()
            proc.wait(timeout=10)

    @pytest.mark.parametrize("fault,expected", [
        (PermissionError(13, "denied"), "unknown"), (OSError(5, "I/O error"), "unknown"),
        ("garbage-without-paren", "unknown"), ("1 (x) S 1", "unknown"),
        (FileNotFoundError(2, "gone"), "gone"), (ProcessLookupError(3, "gone"), "gone")])
    def test_linux_lookup_classification(monkeypatch, fault, expected):
        def read(pid):
            if isinstance(fault, BaseException):
                raise fault
            return fault
        monkeypatch.setattr(docs, "_read_proc_stat", read)
        state, _identity = docs.process_state(12345)
        assert state == {"unknown": docs.UNKNOWN, "gone": docs.GONE}[expected]
else:
    @pytest.mark.parametrize("error,expected", [(5, "unknown"), (87, "gone"),
                                                (31, "unknown")])
    def test_windows_lookup_classification(monkeypatch, error, expected):
        monkeypatch.setattr(docs, "_open_process", lambda pid, access: (None, error))
        state, _identity = docs.process_state(12345)
        assert state == {"unknown": docs.UNKNOWN, "gone": docs.GONE}[expected]


def test_live_lookups_report_identity_and_a_different_process_is_reused():
    proc, identity = _sleeper()
    try:
        assert docs.process_state(proc.pid) == (docs.LIVE, identity)
    finally:
        proc.kill()
        proc.wait(timeout=10)
    assert docs.process_state(proc.pid)[0] in (docs.GONE, docs.LIVE)  # LIVE only if reused


# ---- 2. durable evidence survives write/replace failures and a restart ----------------------

def _hung(database_url, clock, tmp_path):
    stack = Stack(database_url, clock, tmp_path / "store", analyze_timeout_seconds=2.0)
    stack.fake(modes={"analyze": "hang"})
    return stack


def _refuse_kill(monkeypatch):
    def refuse(self):
        raise PermissionError(13, "Access is denied: C:\\secret\\bridge")
    monkeypatch.setattr(subprocess.Popen, "kill", refuse)
    monkeypatch.setattr(docs, "_terminate_pid", lambda pid: None)


def _pid_writes_fail(monkeypatch, how, times=None):
    """Fail writes (or replaces) of api-bridge records that carry a pid; `times` failures
    (None = every one). Records without a pid (launch intent) are unaffected."""
    state = {"left": times}
    real_write, real_replace = pathlib.Path.write_text, os.replace

    def due(data):
        if '"pid": null' in data or '"pid"' not in data:
            return False
        if state["left"] is None:
            return True
        if state["left"] > 0:
            state["left"] -= 1
            return True
        return False

    if how == "write":
        def write_text(self, data, *a, **k):
            if docs.BRIDGE_RECORD_DIR in self.parts and due(data):
                raise OSError(28, "No space left on device: E:\\secret")
            return real_write(self, data, *a, **k)
        monkeypatch.setattr(pathlib.Path, "write_text", write_text)
    else:
        def replace(src, dst, *a, **k):
            if docs.BRIDGE_RECORD_DIR in pathlib.Path(dst).parts:
                try:
                    data = pathlib.Path(src).read_text()
                except OSError:
                    data = ""
                if due(data):
                    raise PermissionError(13, "sharing violation: E:\\secret")
            return real_replace(src, dst, *a, **k)
        monkeypatch.setattr(docs.os, "replace", replace)


def _hung_pids(stack):
    return [(c["pid"], c.get("ppid")) for c in stack.calls() if c["op"] == "analyze"]


def _no_leak(stack, token, *responses):
    for response in responses:
        body = response.json()
        assert set(body) == {"error"} and "secret" not in response.text, body
    stored = "".join(p.read_text(errors="ignore")
                     for p in (stack.store / docs.BRIDGE_RECORD_DIR).glob("*")
                     if p.is_file()) if (stack.store / docs.BRIDGE_RECORD_DIR).is_dir() else ""
    assert token not in stored and "secret" not in stored and str(stack.store) not in stored


@pytest.mark.parametrize("how", ["write", "replace"])
def test_failed_evidence_write_is_never_forgotten_after_restart(database_url, clock, tmp_path,
                                                                monkeypatch, how):
    stack = _hung(database_url, clock, tmp_path)
    token = stack.session()
    handle = _handle(stack, token)
    _refuse_kill(monkeypatch)
    _pid_writes_fail(monkeypatch, how, times=None)  # persistent failure
    first = stack.analyze(token, handle)
    monkeypatch.undo()
    hung = _hung_pids(stack)
    try:
        assert first.status_code in (503, 504), first.text
        assert first.json()["error"] in ("document_worker_unavailable",
                                         "document_worker_timeout",
                                         "document_worker_recovery_pending")
        _no_leak(stack, token, first)
        restarted = Stack(database_url, clock, stack.store)
        restarted.fake(modes={})
        second = restarted.analyze(token, handle)
        alive = [p for pid, ppid in hung for p in (pid, ppid) if p and _live(p)
                 and p != os.getpid()]
        # Never a success while the unconfirmed bridge from the first request lives.
        assert not (second.status_code == 200 and alive), (second.status_code, alive)
        if how == "replace":
            # The validated temporary held the pid: recovery verified and stopped it.
            assert second.status_code == 200 and not alive
            assert _records(stack.store) == []
        else:
            # No pid could be stored anywhere: the request failed closed, and either no
            # bridge outlived it or the launch intent keeps analysis refused.
            assert second.status_code == 200 and not alive or \
                second.json() == {"error": "document_worker_recovery_pending"}
        _no_leak(stack, token, *([second] if second.status_code != 200 else []))
    finally:
        for pid, ppid in hung:
            _stop(pid)
            if ppid != os.getpid():
                _stop(ppid)


def test_transient_write_failure_is_retried_and_the_evidence_recovers(database_url, clock,
                                                                       tmp_path, monkeypatch):
    stack = _hung(database_url, clock, tmp_path)
    token = stack.session()
    handle = _handle(stack, token)
    _refuse_kill(monkeypatch)
    _pid_writes_fail(monkeypatch, "write", times=1)
    first = stack.analyze(token, handle)
    monkeypatch.undo()
    hung = _hung_pids(stack)
    try:
        assert first.json() == {"error": "document_worker_timeout"}
        assert any(name.startswith("bridge-") for name in _records(stack.store))
        assert any(_live(p) for pid, ppid in hung for p in (pid, ppid)
                   if p != os.getpid())
        restarted = Stack(database_url, clock, stack.store)  # API restart
        restarted.fake(modes={})
        result = restarted.analyze(token, handle)
        assert result.status_code == 200
        assert not any(_live(p) for pid, ppid in hung for p in (pid, ppid)
                       if p != os.getpid())
        assert _records(stack.store) == []
    finally:
        for pid, ppid in hung:
            _stop(pid)
            if ppid != os.getpid():
                _stop(ppid)


def test_confirmed_absence_control_recovers(stack, database_url, clock):
    proc, identity = _sleeper()
    proc.kill()
    proc.wait(timeout=10)
    _plant(stack.store, proc.pid, identity)
    token = stack.session()
    handle = _handle(stack, token)
    assert stack.analyze(token, handle).status_code == 200
    assert _records(stack.store) == []
