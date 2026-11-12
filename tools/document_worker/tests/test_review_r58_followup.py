"""Regressions for review DOC01-69b51fe: R58 unreadable /proc members and reused-PID layouts."""
import errno
import os
import pathlib
import signal
import subprocess
import sys
import time

import pytest

from conftest import leftovers
from docworker.handles import HandleStore
from docworker.supervisor import Supervisor, process_identity
from test_review_r58_r59 import _start_group, _wait
from test_supervisor import _plant_record

posix_only = pytest.mark.skipif(
    os.name == "nt", reason="POSIX /proc process groups; on Windows the parser runs in a job "
    "with one active process and kill-on-close")


def _record_signals(monkeypatch):
    """Fail-safe recorder: any signal recovery tries to send is captured, never delivered."""
    import docworker.supervisor as sv
    sent = []
    monkeypatch.setattr(sv, "kill_pid", lambda pid: sent.append(("pid", pid)))
    monkeypatch.setattr(sv, "kill_group", lambda pgid: sent.append(("group", pgid)),
                        raising=False)
    return sent


def _fault_stat(monkeypatch, pid, fault):
    """Make reading only /proc/<pid>/stat fail (exception) or return malformed text."""
    target = f"/proc/{pid}/stat"
    real = pathlib.Path.read_text

    def read_text(self, *args, **kwargs):
        if str(self) == target:
            if isinstance(fault, BaseException):
                raise fault
            return fault
        return real(self, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "read_text", read_text)


FAULTS = {
    "permission": PermissionError(errno.EACCES, "Permission denied"),
    "io_error": OSError(errno.EIO, "Input/output error"),
    "malformed_no_paren": "12345 garbage-without-comm-terminator",
    "malformed_short": "12345 (sleep) S 1",
    "malformed_pgrp": "12345 (sleep) S 1 not-a-number 1 0 -1 0",
}


@posix_only
@pytest.mark.parametrize("fault", list(FAULTS), ids=list(FAULTS))
def test_r58_unreadable_live_member_fails_closed(store, monkeypatch, fault):
    """Leader exited, member alive but its /proc stat unreadable: never 'recovered'."""
    leader, member = _start_group(0.5)
    member_identity = process_identity(member)
    try:
        run_id = _plant_record(store, leader.pid, process_identity(leader.pid))
        leader.wait(timeout=10)
        assert os.getpgid(member) == leader.pid
        with monkeypatch.context() as m:
            sent = _record_signals(m)
            _fault_stat(m, member, FAULTS[fault])
            for _ in range(3):  # repeated fresh-supervisor retries stay safe
                report = Supervisor(HandleStore(store.root)).recover()["records"]
                assert [r["result"] for r in report] == ["group_state_unknown_kept"]
                assert "terminated_pid" not in report[0]
                assert leftovers(store) == {"runs": [run_id], "recovery": [f"{run_id}.json"]}
            assert sent == []
        assert process_identity(member) == member_identity  # never signalled
        # Fault removed, member alive and readable: still kept, as a live member.
        assert [r["result"] for r in Supervisor(HandleStore(store.root)).recover()["records"]] \
            == ["group_members_alive_kept"]
        os.kill(member, signal.SIGKILL)  # the test stops its own verified member
        assert _wait(lambda: not os.path.exists(f"/proc/{member}"))
        retry = Supervisor(HandleStore(store.root)).recover()["records"]
        assert [r["result"] for r in retry] == ["recovered"]
        assert leftovers(store) == {"runs": [], "recovery": []}
    finally:
        if process_identity(member) == member_identity:
            os.kill(member, signal.SIGKILL)


@posix_only
def test_r58_fault_on_member_while_leader_alive_keeps_record(store, monkeypatch):
    """A verified leader is stopped with its group, but an unreadable member stops 'recovered'."""
    leader, member = _start_group(120)
    member_identity = process_identity(member)
    try:
        run_id = _plant_record(store, leader.pid, process_identity(leader.pid))
        with monkeypatch.context() as m:
            _fault_stat(m, member, PermissionError(errno.EACCES, "Permission denied"))
            # The member is killed by the group signal, but until its /proc entry is gone
            # the unreadable entry cannot prove anything.
            report = Supervisor(HandleStore(store.root)).recover()["records"]
            if os.path.exists(f"/proc/{member}"):
                assert report[0]["result"] in ("group_state_unknown_kept", "recovered")
            assert report[0]["result"] != "recovered" or not os.path.exists(f"/proc/{member}")
        leader.wait(timeout=10)
        assert _wait(lambda: not os.path.exists(f"/proc/{member}"))
        if leftovers(store)["recovery"]:
            assert leftovers(store) == {"runs": [run_id], "recovery": [f"{run_id}.json"]}
            retry = Supervisor(HandleStore(store.root)).recover()["records"]
            assert [r["result"] for r in retry] == ["recovered"]
        assert leftovers(store) == {"runs": [], "recovery": []}
    finally:
        if leader.poll() is None:
            leader.kill()
        if process_identity(member) == member_identity:
            os.kill(member, signal.SIGKILL)


@posix_only
def test_r58_disappeared_proc_entry_is_skipped(store, monkeypatch):
    """A pid that vanishes between listing and reading (ENOENT/ESRCH) is genuinely gone."""
    import docworker.supervisor as sv
    run_id = _plant_record(store, 999999, "linux-start:1")  # leader gone
    ghost = 999998
    real_pids = sv._proc_pids
    monkeypatch.setattr(sv, "_proc_pids", lambda: list(real_pids()) + [ghost])
    for exc in (FileNotFoundError(errno.ENOENT, "gone"), ProcessLookupError(errno.ESRCH, "gone")):
        with monkeypatch.context() as m:
            _fault_stat(m, ghost, exc)
            assert sv.group_members(999999) == []
    report = Supervisor(HandleStore(store.root)).recover()["records"]
    assert [r["result"] for r in report] == ["recovered"]
    assert leftovers(store)["runs"] == [] and run_id


@posix_only
def test_r58_unlistable_proc_fails_closed(store, monkeypatch):
    import docworker.supervisor as sv

    def boom():
        raise PermissionError(errno.EACCES, "Permission denied")

    run_id = _plant_record(store, 999999, "linux-start:1")
    monkeypatch.setattr(sv, "_proc_pids", boom)
    report = Supervisor(HandleStore(store.root)).recover()["records"]
    assert [r["result"] for r in report] == ["group_state_unknown_kept"]
    assert leftovers(store) == {"runs": [run_id], "recovery": [f"{run_id}.json"]}


# ---- reused PID under both process-group layouts ---------------------------------------------

def _live(new_session: bool):
    kw = {"start_new_session": True} if (new_session and os.name != "nt") else {}
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"], **kw)
    assert _wait(lambda: process_identity(proc.pid) is not None)
    return proc


def _forged():
    return "win-created:1" if os.name == "nt" else "linux-start:1"


@pytest.mark.parametrize("layout", ["group_leader", "not_group_leader"])
def test_reused_pid_is_never_signalled_in_either_group_layout(store, monkeypatch, layout):
    """The recorded pid is alive but its identity does not match (a reused pid).

    group_leader: the stranger leads a live process group whose id equals the recorded pid,
    so the group cannot be proved empty and the record is kept (never recovered, never
    signalled). not_group_leader: no group has that id, so the record is safely recovered.
    Windows has no process groups here and always recovers. No signal is sent either way.
    """
    stranger = _live(new_session=(layout == "group_leader"))
    identity = process_identity(stranger.pid)
    try:
        if os.name != "nt":
            assert (os.getpgid(stranger.pid) == stranger.pid) == (layout == "group_leader")
        run_id = _plant_record(store, stranger.pid, _forged())
        sent = _record_signals(monkeypatch)
        report = Supervisor(store).recover()["records"]
        monkeypatch.undo()
        expected = ("group_members_alive_kept"
                    if layout == "group_leader" and os.name != "nt" else "recovered")
        assert [r["result"] for r in report] == [expected]
        assert "terminated_pid" not in report[0]
        assert sent == []
        assert process_identity(stranger.pid) == identity
        kept = expected != "recovered"
        assert leftovers(store) == ({"runs": [run_id], "recovery": [f"{run_id}.json"]} if kept
                                    else {"runs": [], "recovery": []})
    finally:
        stranger.kill()
        stranger.wait(timeout=10)


def test_reused_pid_of_the_test_runner_itself(store, monkeypatch):
    """pytest's own pid with a forged identity: the outcome depends on whether pytest leads
    its process group, and that layout is asserted explicitly instead of assumed."""
    me = os.getpid()
    sent = _record_signals(monkeypatch)
    _plant_record(store, me, _forged())
    report = Supervisor(store).recover()["records"]
    monkeypatch.undo()
    leads_group = os.name != "nt" and os.getpgrp() == me
    assert [r["result"] for r in report] == (["group_members_alive_kept"] if leads_group
                                             else ["recovered"])
    assert "terminated_pid" not in report[0]
    assert sent == []
    time.sleep(0)  # still here: nothing signalled this process
