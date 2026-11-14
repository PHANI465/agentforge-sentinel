"""DOC01 Part B re-review a3d1a6c, R62: a recorded bridge whose owner API is verifiably alive,
or that is this process's own in-flight call, is left untouched but still counts as
recovery pending. A second API runs in a separate interpreter process sharing the store.
Failing-first against a3d1a6c (see the branch handoff)."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from sentinel import documents as docs
from test_doc01b_r62_followup import _live, _records, _sleeper
from test_documents_api import FAKE, Stack, _handle

ROOT = Path(__file__).resolve().parents[1]
SECOND_API = ROOT / "tests" / "support" / "doc01_second_api.py"


@pytest.fixture
def stack(database_url, clock, tmp_path):
    s = Stack(database_url, clock, tmp_path / "store")
    s.fake()
    return s


def _record(store, nonce, owner, bridge, state="stop_unconfirmed"):
    """A bridge record as an API process writes it (owner = that API process)."""
    folder = store / docs.BRIDGE_RECORD_DIR
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"bridge-{nonce}.json"
    path.write_text(json.dumps({
        "nonce": nonce, "op": "analyze", "state": state,
        "owner_pid": owner[0], "owner_identity": owner[1],
        "pid": bridge[0], "identity": bridge[1], "recorded_at": 0}))
    return path


def _second_api(stack, database_url, token, handle, tmp_path):
    """A separate API process sharing the store; returns its JSON report."""
    spec = tmp_path / "second_api.json"
    spec.write_text(json.dumps({"database_url": database_url, "store": str(stack.store),
                                "fake_bridge": str(FAKE), "token": token,
                                "handle": handle,
                                "now": stack.service.clock().isoformat()}))
    proc = subprocess.run([sys.executable, str(SECOND_API), str(spec)], capture_output=True,
                          timeout=180)
    spec.unlink()
    assert proc.returncode == 0, proc.stderr[-2000:]
    report = json.loads(proc.stdout.decode().strip().splitlines()[-1])
    assert report["pid"] != __import__("os").getpid()  # really another process
    return report


def test_live_owner_bridge_is_kept_pending_in_a_separate_api_process(
        stack, database_url, tmp_path):
    owner, owner_id = _sleeper()   # stands in for the other, still-running API process
    bridge, bridge_id = _sleeper()  # that API's bridge whose stop was not confirmed
    try:
        token = stack.session()
        handle = _handle(stack, token)
        record = _record(stack.store, "a" * 16, (owner.pid, owner_id),
                         (bridge.pid, bridge_id))
        report = _second_api(stack, database_url, token, handle, tmp_path)
        assert report["recover"] == {"kept": 1, "pending": True}, report
        assert (report["status"], report["body"]) == (
            503, {"error": "document_worker_recovery_pending"}), report
        # Never signalled: both are the same processes, untouched; the record stays.
        assert docs.process_state(owner.pid) == (docs.LIVE, owner_id)
        assert docs.process_state(bridge.pid) == (docs.LIVE, bridge_id)
        assert record.exists()
        assert token not in json.dumps(report)
        # The owner really goes away: the bridge is now an orphan, verified and stopped.
        owner.kill()
        owner.wait(timeout=10)
        report = _second_api(stack, database_url, token, handle, tmp_path)
        assert report["recover"] == {"kept": 0, "pending": False}, report
        assert report["status"] == 200
        assert bridge.wait(timeout=20) is not None and not _live(bridge.pid)
        assert _records(stack.store) == []
    finally:
        for proc in (owner, bridge):
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=10)


def test_own_in_flight_call_counts_as_pending_until_verified_cleanup(stack, monkeypatch):
    """Control in this process: an in-flight call is left alone but keeps recovery
    pending; once it is no longer in flight and its bridge is verified gone, it clears."""
    bridge, bridge_id = _sleeper()
    try:
        _handle(stack, stack.session())  # registers the worker
        documents = stack.documents
        me = (docs.os.getpid(), docs.process_identity(docs.os.getpid()))
        _record(stack.store, "b" * 16, me, (bridge.pid, bridge_id), state="running")
        signals = []
        monkeypatch.setattr(docs, "_terminate_pid", lambda pid: signals.append(pid))
        documents._inflight.add("b" * 16)
        assert documents._recover_bridges() == 1
        assert documents.recover()["pending"] is True
        assert signals == [] and _live(bridge.pid)
        documents._inflight.discard("b" * 16)
        bridge.kill()  # the call's own bridge exits (test-owned stop)
        bridge.wait(timeout=10)
        monkeypatch.undo()
        assert documents.recover() == {"kept": 0, "pending": False}
        assert _records(stack.store) == []
    finally:
        if bridge.poll() is None:
            bridge.kill()
            bridge.wait(timeout=10)


def test_unknown_owner_state_counts_as_pending_without_a_signal(stack, monkeypatch):
    owner, owner_id = _sleeper()
    bridge, bridge_id = _sleeper()
    try:
        _handle(stack, stack.session())
        _record(stack.store, "c" * 16, (owner.pid, owner_id), (bridge.pid, bridge_id))
        real = docs.process_state
        signals = []
        monkeypatch.setattr(docs, "process_state",
                            lambda pid: (docs.UNKNOWN, None) if pid == owner.pid else real(pid))
        monkeypatch.setattr(docs, "_terminate_pid", lambda pid: signals.append(pid))
        assert stack.documents.recover() == {"kept": 1, "pending": True}
        assert signals == [] and _live(bridge.pid)
        assert owner.poll() is None  # alive (its lookup is patched to unknown above)
        assert len(_records(stack.store)) == 1
    finally:
        for proc in (owner, bridge):
            proc.kill()
            proc.wait(timeout=10)
