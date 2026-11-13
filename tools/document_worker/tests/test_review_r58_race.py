"""Regressions for review DOC01-7ec46ae: R58 fork-after-/proc-listing race.

A /proc snapshot alone cannot prove a process group empty: a live member can fork a new
member after the listing and then exit. Recovery must confirm emptiness at the kernel
boundary after its scan, keep the record on a live, inaccessible or unknown group, and
never signal a group whose ownership is unproved.
"""
import errno
import os
import signal
import subprocess
import sys

import pytest

from conftest import leftovers
from docworker.handles import HandleStore
from docworker.supervisor import Supervisor, process_identity
from test_review_r58_followup import _record_signals
from test_review_r58_r59 import _wait
from test_supervisor import _plant_record

posix_only = pytest.mark.skipif(
    os.name == "nt", reason="POSIX process groups; on Windows the parser runs in a job with one "
    "active process and kill-on-close")

# The member blocks on a gate FIFO; once released it forks a descendant (same process group,
# no new session), reports the descendant's pid on a second FIFO and exits.
MEMBER = ("import os, subprocess, sys\n"
          "with open(sys.argv[1]) as gate: gate.read(1)\n"
          "d = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
          "with open(sys.argv[2], 'w') as out: out.write(str(d.pid))\n"
          "os._exit(0)\n")
# The session leader starts the member, prints its pid and exits at once.
LEADER = ("import subprocess, sys\n"
          "m = subprocess.Popen([sys.executable, '-c', sys.argv[1], sys.argv[2], sys.argv[3]])\n"
          "print(m.pid, flush=True)\n")


def _gone(pid):
    """True once pid has no live (non-zombie) process; zombies are not members."""
    return process_identity(pid) is None


def _start_gated_group(tmp_path):
    gate, out = tmp_path / "gate.fifo", tmp_path / "out.fifo"
    os.mkfifo(gate)
    os.mkfifo(out)
    leader = subprocess.Popen([sys.executable, "-c", LEADER, MEMBER, str(gate), str(out)],
                              start_new_session=True, stdout=subprocess.PIPE, text=True)
    member = int(leader.stdout.readline())
    leader.wait(timeout=10)  # the recorded leader has exited (and is reaped)
    assert process_identity(member) is not None and os.getpgid(member) == leader.pid
    return leader, member, gate, out


def _release(gate, out):
    """Let the member fork; return the descendant pid it reports. Blocking FIFO opens are
    the synchronisation, so no sleep decides the order."""
    with open(gate, "w") as g:
        g.write("x")
    with open(out) as o:
        return int(o.read())


@posix_only
def test_r58_member_forks_after_proc_listing_then_exits(store, monkeypatch, tmp_path):
    import docworker.supervisor as sv
    leader, member, gate, out = _start_gated_group(tmp_path)
    pgid = leader.pid
    member_identity = process_identity(member)
    state = {}
    try:
        run_id = _plant_record(store, leader.pid, "linux-start:1")  # leader gone
        real_pids = sv._proc_pids

        def listing_then_fork():
            pids = real_pids()  # the real /proc snapshot, taken first
            if "descendant" not in state:
                assert member in pids
                state["descendant"] = desc = _release(gate, out)
                assert desc not in pids  # created after the snapshot
                assert os.getpgid(desc) == pgid  # still in the recorded group
                state["identity"] = process_identity(desc)
                assert _wait(lambda: _gone(member))  # the listed member exited
            return pids

        with monkeypatch.context() as m:
            sent = _record_signals(m)
            m.setattr(sv, "_proc_pids", listing_then_fork)
            report = Supervisor(HandleStore(store.root)).recover()["records"]
            assert sent == []
        desc = state["descendant"]
        assert report[0]["result"] != "recovered", report
        assert report[0]["result"] in ("group_members_alive_kept", "group_state_unknown_kept")
        assert "terminated_pid" not in report[0]
        assert leftovers(store) == {"runs": [run_id], "recovery": [f"{run_id}.json"]}
        assert process_identity(desc) == state["identity"]  # never signalled

        # Repeated fresh retries stay kept while the descendant lives.
        with monkeypatch.context() as m:
            sent = _record_signals(m)
            for _ in range(2):
                again = Supervisor(HandleStore(store.root)).recover()["records"]
                assert [r["result"] for r in again] == ["group_members_alive_kept"]
            assert sent == []

        # The test stops its own verified descendant by exact pid; a fresh retry cleans up.
        assert process_identity(desc) == state["identity"] and os.getpgid(desc) == pgid
        os.kill(desc, signal.SIGKILL)
        assert _wait(lambda: not os.path.exists(f"/proc/{desc}"))
        retry = Supervisor(HandleStore(store.root)).recover()["records"]
        assert [r["result"] for r in retry] == ["recovered"]
        assert leftovers(store) == {"runs": [], "recovery": []}
    finally:
        desc = state.get("descendant")
        if desc and state.get("identity") and process_identity(desc) == state["identity"]:
            os.kill(desc, signal.SIGKILL)
        if process_identity(member) == member_identity:
            os.kill(member, signal.SIGKILL)  # still gated after a failure: our own member


@posix_only
def test_r58_kernel_check_catches_a_live_group_the_scan_missed(store, monkeypatch):
    """Even with the /proc scan forced empty, a live group with the recorded id is kept and
    not signalled (covers a reused or inaccessible group id too)."""
    import docworker.supervisor as sv
    stranger = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"],
                                start_new_session=True)
    try:
        assert _wait(lambda: process_identity(stranger.pid) is not None)
        run_id = _plant_record(store, stranger.pid, "linux-start:1")  # forged: not ours
        with monkeypatch.context() as m:
            sent = _record_signals(m)
            m.setattr(sv, "group_members", lambda pgid: [])
            report = Supervisor(HandleStore(store.root)).recover()["records"]
            assert sent == []
        assert [r["result"] for r in report] == ["group_members_alive_kept"]
        assert leftovers(store) == {"runs": [run_id], "recovery": [f"{run_id}.json"]}
        assert stranger.poll() is None
    finally:
        stranger.kill()
        stranger.wait(timeout=10)


@posix_only
@pytest.mark.parametrize("answer,expected", [
    (False, "recovered"), (True, "group_members_alive_kept"),
    (None, "group_state_unknown_kept")])
def test_r58_kernel_group_answer_decides(store, monkeypatch, answer, expected):
    import docworker.supervisor as sv
    run_id = _plant_record(store, 999999, "linux-start:1")
    monkeypatch.setattr(sv, "group_members", lambda pgid: [])
    monkeypatch.setattr(sv, "_group_exists", lambda pgid: answer)
    report = Supervisor(HandleStore(store.root)).recover()["records"]
    assert [r["result"] for r in report] == [expected]
    kept = expected != "recovered"
    assert leftovers(store) == ({"runs": [run_id], "recovery": [f"{run_id}.json"]} if kept
                                else {"runs": [], "recovery": []})


@posix_only
@pytest.mark.parametrize("exc,expected", [
    (ProcessLookupError(errno.ESRCH, "no such group"), False),
    (PermissionError(errno.EPERM, "not permitted"), True),
    (OSError(errno.EINVAL, "invalid"), None)])
def test_r58_group_exists_maps_kernel_errors(monkeypatch, exc, expected):
    import docworker.supervisor as sv
    calls = []

    def killpg(pgid, sig):
        calls.append((pgid, sig))
        raise exc

    monkeypatch.setattr(sv.os, "killpg", killpg)
    assert sv._group_exists(4242) is expected
    assert calls == [(4242, 0)]  # signal 0 only: an existence query, never a signal


@posix_only
def test_r58_group_exists_real_kernel_answers():
    import docworker.supervisor as sv
    assert sv._group_exists(os.getpgrp()) is True  # our own group exists
    proc = subprocess.Popen([sys.executable, "-c", "pass"], start_new_session=True)
    proc.wait(timeout=10)  # exited and reaped: its group id now has no process
    assert sv._group_exists(proc.pid) is False


@posix_only
def test_r58_unreaped_zombie_leader_keeps_its_group_until_reaped(store):
    """A verified leader that is the recovering process's own child becomes a zombie when
    stopped; the kernel still counts it in the group, so the record is kept (conservative)
    until the parent reaps it. A fresh retry then completes cleanup."""
    from docworker.limits import Limits
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"],
                            start_new_session=True)
    try:
        assert _wait(lambda: process_identity(proc.pid) is not None)
        run_id = _plant_record(store, proc.pid, process_identity(proc.pid))
        report = Supervisor(HandleStore(store.root),
                            Limits(stop_confirm_seconds=1.0)).recover()["records"]
        assert [r["result"] for r in report] == ["group_members_alive_kept"]
        assert report[0]["terminated_pid"] == proc.pid  # the verified leader was stopped
        assert leftovers(store) == {"runs": [run_id], "recovery": [f"{run_id}.json"]}
        assert proc.wait(timeout=10) == -signal.SIGKILL  # the test reaps its own child
        retry = Supervisor(HandleStore(store.root)).recover()["records"]
        assert [r["result"] for r in retry] == ["recovered"]
        assert leftovers(store) == {"runs": [], "recovery": []}
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=10)
