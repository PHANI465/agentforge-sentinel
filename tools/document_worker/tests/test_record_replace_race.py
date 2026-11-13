"""Part A follow-up before API exposure: the Windows recovery-record replacement race.

On Windows os.replace onto a file another process holds open fails with PermissionError
(a sharing violation). The supervisor used to treat that as a containment failure, stop the
child and leave an orphan `r_*.tmp` (review DOC01-8f7bd87); a concurrent reader such as the
crash test's polling loop could trigger it. A failed or uncertain record write must never
become a successful extraction, must not leave an orphan temporary record, and recovery must
use any temporary record that carries the only copy of a child's pid.
"""
import errno
import json
import os
import subprocess
import sys
import threading
import time

import pytest

from conftest import SESSION, leftovers
from docworker.handles import HandleStore
from docworker.supervisor import Supervisor, process_identity

import docworker.supervisor as sv


def _tmp_files(store):
    return sorted(p.name for p in (store.root / "recovery").glob("*.tmp"))


def _flaky_replace(monkeypatch, failures):
    """os.replace onto a recovery record raises a sharing violation `failures` times
    (None = always); other replaces are untouched."""
    real = os.replace
    state = {"left": failures, "calls": 0}

    def replace(src, dst, *args, **kwargs):
        name = os.path.basename(os.fspath(dst))
        if os.path.basename(os.path.dirname(os.fspath(dst))) == "recovery" \
                and name.endswith(".json"):
            state["calls"] += 1
            if state["left"] is None or state["left"] > 0:
                if state["left"] is not None:
                    state["left"] -= 1
                raise PermissionError(errno.EACCES, "sharing violation (simulated)")
        return real(src, dst, *args, **kwargs)

    monkeypatch.setattr(sv.os, "replace", replace)
    return state


def test_transient_sharing_violation_is_retried_and_extraction_succeeds(
        store, ingest, make_supervisor, monkeypatch):
    handle = ingest("csv_statement_usd.csv")
    state = _flaky_replace(monkeypatch, failures=3)
    result = make_supervisor().extract(handle, SESSION)
    monkeypatch.undo()
    assert result["status"] == "complete", result.get("errors")
    assert state["calls"] >= 4  # the conflicts really happened and were retried
    assert leftovers(store) == {"runs": [], "recovery": []}


def test_persistent_record_write_failure_is_an_error_without_orphans(
        store, ingest, make_supervisor, monkeypatch):
    handle = ingest("csv_statement_usd.csv")
    _flaky_replace(monkeypatch, failures=None)
    result = make_supervisor().extract(handle, SESSION)
    monkeypatch.undo()
    assert result["status"] == "error"
    assert "records" not in result or not result["records"]
    codes = [e["code"] for e in result["errors"]]
    assert any(c.startswith("recovery_record_write_failed") for c in codes), codes
    assert result["supervisor"]["stop"]["confirmed"] is True
    assert _tmp_files(store) == []  # no orphan temporary record
    assert leftovers(store)["runs"] == []


@pytest.mark.skipif(os.name != "nt", reason="Windows sharing semantics: POSIX rename "
                    "replaces a file that another process holds open")
def test_real_windows_reader_holding_the_record_open(store, ingest, make_supervisor,
                                                     monkeypatch):
    """A real open handle on the 'starting' record (as the crash test's poll creates) while
    the supervisor replaces it with the 'running' record."""
    handle = ingest("csv_statement_usd.csv")
    held = {}
    real_attach = sv.Containment.attach

    def attach(self, proc):
        real_attach(self, proc)
        (path,) = (store.root / "recovery").glob("r_*.json")
        fh = open(path, "rb")  # no FILE_SHARE_DELETE: os.replace onto it must fail
        held["fh"] = fh
        threading.Timer(0.3, fh.close).start()

    monkeypatch.setattr(sv.Containment, "attach", attach)
    result = make_supervisor().extract(handle, SESSION)
    monkeypatch.undo()
    assert "fh" in held
    assert result["status"] == "complete", result.get("errors")
    assert leftovers(store) == {"runs": [], "recovery": []}


# ---- recovery of temporary records ------------------------------------------------------------

def _sleeper():
    kw = {"start_new_session": True} if os.name != "nt" else {}
    return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"], **kw)


def _plant_run(store, run_id, nonce="n" * 32):
    run_dir = store.root / "runs" / run_id
    run_dir.mkdir()
    (run_dir / sv.RUN_MARKER).write_text(json.dumps({"run_id": run_id, "nonce": nonce}))


def test_recover_uses_a_temporary_record_that_holds_the_only_pid(store):
    """'starting' record without a pid, plus the failed 'running' write still in a .tmp:
    recovery must act on the tmp's verified pid rather than discard the run as pid-less."""
    proc = _sleeper()
    try:
        deadline = time.monotonic() + 5
        while process_identity(proc.pid) is None and time.monotonic() < deadline:
            time.sleep(0.05)
        run_id = "r_" + "a" * 16
        _plant_run(store, run_id)
        rec = store.root / "recovery"
        (rec / f"{run_id}.json").write_text(json.dumps(
            {"run_id": run_id, "nonce": "n" * 32, "state": "starting", "pid": None,
             "identity": None}))
        (rec / f"{run_id}.0123abcd.tmp").write_text(json.dumps(
            {"run_id": run_id, "nonce": "n" * 32, "state": "running", "pid": proc.pid,
             "identity": process_identity(proc.pid),
             "pgid": None if os.name == "nt" else proc.pid}))
        report = Supervisor(HandleStore(store.root)).recover()["records"]
        assert [r["result"] for r in report] == ["recovered"], report
        assert report[0]["terminated_pid"] == proc.pid
        assert proc.wait(timeout=10) is not None
        assert leftovers(store) == {"runs": [], "recovery": []}
    finally:
        if proc.poll() is None:
            proc.kill()


def test_recover_keeps_a_run_whose_newer_record_is_unreadable(store):
    run_id = "r_" + "b" * 16
    _plant_run(store, run_id)
    rec = store.root / "recovery"
    (rec / f"{run_id}.json").write_text(json.dumps(
        {"run_id": run_id, "nonce": "n" * 32, "state": "starting", "pid": None,
         "identity": None}))
    (rec / f"{run_id}.0123abcd.tmp").write_text('{"run_id": "r_bbbb')  # torn write
    report = Supervisor(HandleStore(store.root)).recover()["records"]
    assert [r["result"] for r in report] == ["temporary_record_unreadable_kept"]
    assert leftovers(store) == {"runs": [run_id],
                                "recovery": [f"{run_id}.0123abcd.tmp", f"{run_id}.json"]}


def test_recover_removes_a_temporary_record_left_after_a_confirmed_cleanup(store):
    """A tmp with no record and no run dir (the record was unlinked after a confirmed stop)
    proves nothing is outstanding; a pid-less or torn tmp of that kind is removed."""
    rec = store.root / "recovery"
    (rec / ("r_" + "c" * 16 + ".0123abcd.tmp")).write_text('{"torn')
    (rec / ("r_" + "d" * 16 + ".tmp")).write_text(json.dumps(  # pre-fix name shape
        {"run_id": "r_" + "d" * 16, "state": "starting", "pid": None}))
    report = Supervisor(HandleStore(store.root)).recover()["records"]
    assert sorted(r["result"] for r in report) == ["orphan_temporary_removed"] * 2
    assert leftovers(store) == {"runs": [], "recovery": []}
