"""Bounded child lifecycle: limits, verified stop, cleanup, unconfirmed stop and recovery."""
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from conftest import ROOT, SESSION, fake_argv, leftovers
from docworker.limits import Limits
from docworker.supervisor import RUN_MARKER, Supervisor, process_identity

pytestmark = pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")


def _alive(pid: int) -> bool:
    return process_identity(pid) is not None


def _codes(result):
    return [e["code"] for e in result.get("errors", [])]


def test_deadline_kills_and_cleans(store, ingest, make_supervisor):
    sup = make_supervisor(Limits(deadline_seconds=2), child_argv=fake_argv("slow"))
    t0 = time.monotonic()
    result = sup.extract(ingest("csv_statement_usd.csv"), SESSION)
    assert time.monotonic() - t0 < 2 + 8
    assert result["status"] == "error" and "deadline_exceeded" in _codes(result)
    assert result["supervisor"]["stop"] == {"requested": True, "confirmed": True,
                                            "method": result["supervisor"]["stop"]["method"],
                                            "run_dir_removed": True}
    assert leftovers(store) == {"runs": [], "recovery": []}


def test_output_cap(store, ingest, make_supervisor):
    sup = make_supervisor(Limits(max_stdout_bytes=1024 * 1024), child_argv=fake_argv("spam"))
    result = sup.extract(ingest("csv_statement_usd.csv"), SESSION)
    assert "output_limit_exceeded" in _codes(result)
    assert result["supervisor"]["stop"]["confirmed"] is True
    assert leftovers(store) == {"runs": [], "recovery": []}


def test_memory_cap(store, ingest, make_supervisor):
    limits = Limits(memory_bytes=256 * 1024 * 1024,
                    posix_address_space_bytes=1024 * 1024 * 1024)
    sup = make_supervisor(limits, child_argv=fake_argv("alloc"))
    result = sup.extract(ingest("csv_statement_usd.csv"), SESSION)
    assert result["status"] == "error"
    assert result["supervisor"]["exit_code"] == 7  # MemoryError inside the child
    if sys.platform == "win32":
        assert result["supervisor"]["peak_memory_bytes"] <= limits.memory_bytes
    assert leftovers(store) == {"runs": [], "recovery": []}


def _probe_run(make_supervisor, ingest, argv):
    """Test children report a probe in a deliberately incomplete document. Since R59 the
    supervisor rejects that document; the probe is read through the raw-output test seam."""
    seen = []
    result = make_supervisor(child_argv=argv, hooks={"child_output": seen.append}).extract(
        ingest("csv_statement_usd.csv"), SESSION)
    assert result["status"] == "error" and "probe" not in result
    assert "invalid_child_output:exit_0" in _codes(result)
    return result, json.loads(seen[0])


def test_grandchild_cannot_outlive_supervision(store, ingest, make_supervisor):
    result, doc = _probe_run(make_supervisor, ingest, fake_argv("spawn"))
    info = doc["probe"]
    assert result["supervisor"]["stop"]["confirmed"] is True
    if sys.platform == "win32":
        assert info["spawned"] is False  # job object: one active process
    else:
        assert info["spawned"] is True
        deadline = time.monotonic() + 5
        while _alive(info["pid"]) and time.monotonic() < deadline:
            time.sleep(0.05)
        assert not _alive(info["pid"])  # the whole session/process group was stopped
    assert leftovers(store) == {"runs": [], "recovery": []}


def test_os_level_file_write_bound_is_platform_specific(store, ingest, make_supervisor,
                                                       tmp_path):
    """POSIX: RLIMIT_FSIZE 0 stops any non-empty file write at the OS level. Windows: the job
    object does NOT restrict files; only the in-child guard does (see the guard probe). This
    test records the actual behaviour instead of skipping either platform."""
    target = tmp_path / "escape.bin"
    _result, doc = _probe_run(make_supervisor, ingest, fake_argv("file_write", str(target)))
    if os.name == "nt":
        assert doc["probe"] == {"wrote": True}
        assert target.stat().st_size == 4096
    else:
        assert doc["probe"] == {"wrote": False, "error": "OSError"}
        assert not target.exists() or target.stat().st_size == 0


@pytest.mark.parametrize("mode,code", [("crash", "invalid_child_output:exit_3"),
                                       ("garbage", "invalid_child_output:exit_0"),
                                       ("wrong_id", "invalid_child_output:exit_0")])
def test_invalid_child_results_rejected(store, ingest, make_supervisor, mode, code):
    result = make_supervisor(child_argv=fake_argv(mode)).extract(
        ingest("csv_statement_usd.csv"), SESSION)
    assert result["status"] == "error" and code in _codes(result)
    assert leftovers(store) == {"runs": [], "recovery": []}


def test_guard_in_contained_child(store, ingest, make_supervisor, tmp_path):
    canary = tmp_path / "canary.txt"
    canary.write_text("SECRET-CANARY-7731")
    result, doc = _probe_run(make_supervisor, ingest,
                             fake_argv("guard_probe", str(tmp_path / "r.json")))
    probe = doc["probe"]
    for name in ("socket_connect", "read_outside", "write_cwd", "subprocess", "os_system",
                 "remove", "urlopen"):
        assert probe[name] == "denied", name
    assert probe["stdlib_read"] == "allowed"
    assert "SECRET-CANARY-7731" not in json.dumps(result)
    assert canary.exists()
    assert doc["guard"]["denied_events"]


def test_interrupt_during_run_stops_and_cleans(store, ingest, make_supervisor):
    seen = {}

    def boom(proc):
        seen["pid"] = proc.pid
        raise KeyboardInterrupt

    sup = make_supervisor(child_argv=fake_argv("slow"), hooks={"after_spawn": boom})
    with pytest.raises(KeyboardInterrupt):
        sup.extract(ingest("csv_statement_usd.csv"), SESSION)
    assert not _alive(seen["pid"])
    assert leftovers(store) == {"runs": [], "recovery": []}


def test_unconfirmed_stop_is_reported_then_recovered(store, ingest, make_supervisor):
    sup = make_supervisor(Limits(deadline_seconds=1), child_argv=fake_argv("slow"),
                          hooks={"confirm_stop": lambda confirmed: False})
    result = sup.extract(ingest("csv_statement_usd.csv"), SESSION)
    assert result["status"] == "error" and "stop_unconfirmed" in _codes(result)
    left = leftovers(store)
    assert len(left["runs"]) == 1 and len(left["recovery"]) == 1
    record = json.loads((store.root / "recovery" / left["recovery"][0]).read_text())
    assert record["state"] == "stop_unconfirmed"
    report = Supervisor(store).recover()
    assert [r["result"] for r in report["records"]] == ["recovered"]
    assert leftovers(store) == {"runs": [], "recovery": []}


def _plant_record(store, pid, identity, nonce="n" * 32, marker_nonce=None):
    run_id = "r_" + os.urandom(8).hex()
    run_dir = store.root / "runs" / run_id
    run_dir.mkdir()
    (run_dir / RUN_MARKER).write_text(json.dumps({"run_id": run_id,
                                                  "nonce": marker_nonce or nonce}))
    (store.root / "recovery" / f"{run_id}.json").write_text(json.dumps(
        {"run_id": run_id, "nonce": nonce, "state": "running", "pid": pid,
         "identity": identity}))
    return run_id


def _sleeper():
    if os.name != "nt":
        return Orphan.spawn([sys.executable, "-c", "import time; time.sleep(120)"])[0]
    return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])


# A short-lived intermediate starts argv as a new session leader, reports its pid and exits,
# so the leader is reparented to init exactly as after a supervisor crash. Init reaps it when
# it dies, so its group really empties; an unreaped zombie child of the test process would
# (correctly) keep its group in existence (review DOC01-7ec46ae).
_SPAWN = ("import subprocess, sys\n"
          "p = subprocess.Popen(sys.argv[1:], start_new_session=True)\n"
          "print('leader', p.pid, file=sys.stderr, flush=True)\n")


class Orphan:
    """Handle for an orphaned process: identity-checked, never signalled once reused."""

    def __init__(self, pid):
        self.pid = pid
        deadline = time.monotonic() + 10
        while process_identity(pid) is None and time.monotonic() < deadline:
            time.sleep(0.02)
        self.identity = process_identity(pid)
        assert self.identity is not None

    @classmethod
    def spawn(cls, argv):
        """Start argv orphaned; return (Orphan, the pipe the leader may write lines to)."""
        # The intermediate reports on stderr; the leader's own lines arrive on stdout, so the
        # two can never interleave.
        mid = subprocess.Popen([sys.executable, "-c", _SPAWN, *argv], stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True)
        line = mid.stderr.readline().split()
        assert line[0] == "leader", line
        mid.wait(timeout=10)
        return cls(int(line[1])), mid.stdout

    def poll(self):
        return None if process_identity(self.pid) == self.identity else 0

    def wait(self, timeout=10):
        deadline = time.monotonic() + timeout
        while self.poll() is None:
            if time.monotonic() > deadline:
                raise subprocess.TimeoutExpired(str(self.pid), timeout)
            time.sleep(0.02)
        return 0

    def kill(self):
        if self.poll() is None:
            os.kill(self.pid, signal.SIGKILL)


def test_recover_kills_only_a_verified_owned_process(store):
    proc = _sleeper()
    try:
        deadline = time.monotonic() + 5
        while process_identity(proc.pid) is None and time.monotonic() < deadline:
            time.sleep(0.05)
        _plant_record(store, proc.pid, process_identity(proc.pid))
        report = Supervisor(store).recover()
        assert [r["result"] for r in report["records"]] == ["recovered"]
        assert proc.wait(timeout=10) is not None
        assert proc.poll() is not None
    finally:
        if proc.poll() is None:
            proc.kill()


def test_recover_never_touches_a_reused_pid(store):
    """Forged identity for this test process. The expected result depends on whether the
    runner leads its own process group (review DOC01-69b51fe), so the layout is asserted
    explicitly; test_review_r58_followup.py covers both layouts with dedicated processes."""
    me = os.getpid()
    _plant_record(store, me, "win-created:1" if os.name == "nt" else "linux-start:1")
    report = Supervisor(store).recover()
    leads_group = os.name != "nt" and os.getpgrp() == me
    assert [r["result"] for r in report["records"]] == (
        ["group_members_alive_kept"] if leads_group else ["recovered"])
    assert "terminated_pid" not in report["records"][0]
    assert _alive(me)


def test_recover_keeps_unprovable_and_foreign_records(store):
    _plant_record(store, 999999, None)  # pid without identity: cannot prove ownership
    _plant_record(store, None, None, nonce="a" * 32, marker_nonce="b" * 32)  # foreign run dir
    (store.root / "recovery" / "r_garbage.json").write_text("{")
    report = Supervisor(store).recover()
    results = sorted(r["result"] for r in report["records"])
    assert results == ["identity_unknown_kept", "run_dir_not_owned_kept",
                       "unreadable_record_kept"]
    assert len(leftovers(store)["runs"]) == 2


def test_crashed_supervisor_is_recoverable(store, ingest, tmp_path):
    """Kill the supervising process hard mid-run; recovery finds and stops what remains."""
    handle = ingest("csv_statement_usd.csv")
    script = tmp_path / "sup.py"
    script.write_text(
        "import sys, json\n"
        f"sys.path[:0] = [{str(ROOT / 'src')!r}, {str(Path(__file__).parent)!r}]\n"
        "from conftest import fake_argv, SESSION\n"
        "from docworker.handles import HandleStore\n"
        "from docworker.limits import Limits\n"
        "from docworker.supervisor import Supervisor\n"
        f"s = HandleStore({str(store.root)!r})\n"
        "Supervisor(s, Limits(deadline_seconds=300), child_argv=fake_argv('slow'))"
        f".extract({handle!r}, SESSION)\n")
    err_path = tmp_path / "sup.stderr"
    with open(err_path, "wb") as err:
        parent = subprocess.Popen([sys.executable, str(script)], stderr=err)
    try:
        record, states = None, []
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline and parent.poll() is None:
            records = list((store.root / "recovery").glob("r_*.json"))
            if records:
                data = json.loads(records[0].read_text())
                states.append(data.get("state"))
                if data.get("state") == "running":
                    record = data
                    break
            time.sleep(0.1)
        # Diagnostics for an intermittent Windows failure under load: say whether the
        # supervising process exited early, how long it took, and what it printed.
        assert record is not None, (
            "supervisor never recorded a running child: exit="
            f"{parent.poll()} states={sorted(set(map(str, states)))} "
            f"stderr={err_path.read_bytes()[-2000:]!r}")
        parent.kill()
        parent.wait(timeout=10)
    finally:
        if parent.poll() is None:
            parent.kill()
    report = Supervisor(store).recover()
    assert [r["result"] for r in report["records"]] == ["recovered"]
    assert not _alive(record["pid"])
    assert leftovers(store) == {"runs": [], "recovery": []}
