"""AN01-M1 review regressions R53-R57 (docs/reviews/AN01-M1-93583a.md on task/coordination).

Written before the corrections and run first against candidate 93583a, where each case
marked "defect" failed its intended assertion (evidence kept outside the repository).
Cases marked "control" pass on both. Tests use only the public entry points that existed
at 93583a (stage_command, recover_command, load_records, the rules, run_statements,
run_report, bounded_call), so a failure there is an assertion, not an import error.

No full-size grid, no network beyond loopback, no provider. Process tests use harmless
sleeper or crashing Python children owned by the test; only a verified owned sleeper is
ever stopped, and every other stop request is intercepted. Real-PostgreSQL cases use the
disposable test cluster from tests/conftest.py.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import secrets
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
import pytest
from psycopg.conninfo import make_conninfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import benchmark_reports as br  # noqa: E402
import report_benchmark_support as rb  # noqa: E402

from sentinel.db import roles  # noqa: E402

UTC = timezone.utc
TINY = br.PROFILES["tiny"]
RECORD_SCHEMA = getattr(br, "RECORD_SCHEMA", 2)


def ns(run_dir) -> argparse.Namespace:
    return argparse.Namespace(run_dir=str(run_dir))


def stage_args(run_dir, stage, **kw):
    values = {"run_dir": str(run_dir), "stage": stage, "selection": None,
              "authorized_full_size": False, "fault": None, "wsl_host_path": None}
    values.update(kw)
    return argparse.Namespace(**values)


def _until(predicate, seconds=10.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


def refused_preflight(*args, **kwargs):
    return {"ok": False, "problems": ["test refusal (no worker is launched)"]}


class Gate:
    """A preflight stand-in that blocks its FIRST call (the controller's real interval
    between taking the run lock and launching a worker) and refuses every call."""

    def __init__(self):
        self.entered, self.release, self.calls = threading.Event(), threading.Event(), 0

    def __call__(self, *args, **kwargs):
        self.calls += 1
        if self.calls == 1:
            self.entered.set()
            self.release.wait(30)
        return refused_preflight()


def in_thread(fn, *args, **kwargs):
    box = {}

    def target():
        try:
            box["value"] = fn(*args, **kwargs)
        except BaseException as error:  # noqa: BLE001 - reported to the test
            box["error"] = error
    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    return thread, box


@pytest.fixture
def signals(monkeypatch):
    """Every recovery stop request is intercepted and recorded (never sent)."""
    calls = []

    def record(worker, until):
        calls.append(dict(worker or {}))
        return "unconfirmed:intercepted-by-test"
    monkeypatch.setattr(br, "terminate_owned", record)
    return calls


# ---- R53: controller identity and exclusive recovery ---------------------------------------

def test_r53_recover_refuses_in_the_pre_worker_gap(tmp_path, monkeypatch, signals):
    """defect: during the real interval after the stage takes the run lock and before any
    worker is recorded, recovery must not remove the live controller's lock."""
    run = br.Run.create(tmp_path / "run", TINY)
    gate = Gate()
    monkeypatch.setattr(br, "preflight", gate)
    thread, box = in_thread(br.stage_command, stage_args(run.dir, "S1"))
    try:
        assert gate.entered.wait(30)
        assert run.lock_path.exists() and run.load()["worker"] is None
        code = br.recover_command(ns(run.dir))
        assert code != 0, "recovery must refuse while the controller is alive"
        assert run.lock_path.exists(), "the live controller's lock was removed"
        assert signals == []
        with pytest.raises(br.RunError):
            br.stage_command(stage_args(run.dir, "S2"))   # a second stage is refused too
    finally:
        gate.release.set()
        thread.join(30)
    assert box.get("value") == br.EXIT["refused"], box
    assert not run.lock_path.exists()


def sleeper_launch(run, state, stage, argv, log):
    """As launch_worker (pending record, then identity) but the worker is a harmless
    sleeper owned by this test, so the stage's own deadline stop is a real verified stop."""
    state["worker"] = {"pending": True, "stage": stage}
    run.save(state)
    flags = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" \
        else {"start_new_session": True}
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                            stdin=subprocess.DEVNULL, stdout=log, stderr=log, **flags)
    ident = br.local_stack.identity(proc.pid)
    state["worker"] = {**ident, "pending": False, "stage": stage}
    run.save(state)
    return proc


def test_r53_recover_refuses_while_the_controller_supervises_a_live_worker(
        tmp_path, monkeypatch, signals):
    """defect: with a worker recorded, recovery must not try to stop it while its
    controller is alive. The controller itself then stops its verified owned worker."""
    run = br.Run.create(tmp_path / "run", TINY)
    monkeypatch.setattr(br, "launch_worker", sleeper_launch)
    budget = br.smaller_budget([3, 4, 6, 10, 12], "test (smaller than accepted)")
    thread, box = in_thread(br.stage_command, stage_args(run.dir, "S1"), budget=budget)
    try:
        assert _until(lambda: (run.load().get("worker") or {}).get("pending") is False, 20), box
        worker = run.load()["worker"]
        code = br.recover_command(ns(run.dir))
        assert code != 0
        assert signals == [], "recovery asked to stop a worker its live controller owns"
        assert run.lock_path.exists()
        assert br.local_stack.classify(worker) == "owned"
    finally:
        thread.join(40)
    assert box.get("value") == br.EXIT["incomplete"], box
    rec = run.load()["stages"]["S1"]
    assert rec["cleanup"]["worker"] == "stopped" and not run.lock_path.exists()
    assert br.local_stack.classify(worker) == "gone"


CRASH_IN_GAP = """
import argparse, os, sys
sys.path.insert(0, sys.argv[2])
import benchmark_reports as br
br.preflight = lambda *a, **k: os._exit(9)       # the controller dies inside the gap
br.stage_command(argparse.Namespace(run_dir=sys.argv[1], stage="S1", selection=None,
                 authorized_full_size=False, fault=None, wsl_host_path=None))
"""


def crash_controller(run) -> int:
    proc = subprocess.run([sys.executable, "-c", CRASH_IN_GAP, str(run.dir),
                           str(ROOT / "scripts")], cwd=str(ROOT), capture_output=True,
                          timeout=120)
    assert proc.returncode == 9, proc.stderr.decode(errors="replace")[-2000:]
    assert run.lock_path.exists()
    return proc


def test_r53_a_truly_dead_controller_can_be_recovered(tmp_path, monkeypatch, signals):
    """control: a controller that died in the gap leaves its lock; recovery proves it is
    gone, removes only that lock, and a new stage is then admitted."""
    run = br.Run.create(tmp_path / "run", TINY)
    crash_controller(run)
    assert br.recover_command(ns(run.dir)) == 0
    assert not run.lock_path.exists() and run.load()["blocked"] is None and signals == []
    monkeypatch.setattr(br, "preflight", refused_preflight)
    assert br.stage_command(stage_args(run.dir, "S1")) == br.EXIT["refused"]


def test_r53_reused_identities_grant_no_authority(tmp_path, monkeypatch):
    """control: a lock and a worker record naming this live test process with another
    start time describe processes that are gone; nothing is signalled."""
    run = br.Run.create(tmp_path / "run", TINY)
    me = br.local_stack.identity(os.getpid())
    stale = {**me, "start": me["start"] + 1}
    run.acquire_lock({**stale, "token": secrets.token_hex(16), "stage": "S1"})
    state = run.load()
    state["worker"] = {**stale, "pending": False, "stage": "S1"}
    run.save(state)
    sent = []
    monkeypatch.setattr(br.subprocess, "run", lambda *a, **k: sent.append(a))
    if hasattr(os, "killpg"):
        monkeypatch.setattr(os, "killpg", lambda *a: sent.append(a))
    assert br.recover_command(ns(run.dir)) == 0
    assert sent == [] and br.local_stack.identity(os.getpid()) == me
    assert not run.lock_path.exists() and run.load()["worker"] is None


def test_r53_a_stage_never_removes_a_lock_it_does_not_own(tmp_path, monkeypatch):
    """defect: a lock replaced by another invocation must survive this stage's release."""
    run = br.Run.create(tmp_path / "run", TINY)
    gate = Gate()
    monkeypatch.setattr(br, "preflight", gate)
    thread, box = in_thread(br.stage_command, stage_args(run.dir, "S1"))
    other = {"pid": os.getpid(), "token": "another-invocation", "stage": "S9"}
    try:
        assert gate.entered.wait(30)
        tmp = run.lock_path.with_suffix(".other")
        tmp.write_text(json.dumps(other))
        os.replace(tmp, run.lock_path)
    finally:
        gate.release.set()
        thread.join(30)
    assert "error" not in box or isinstance(box["error"], br.RunError), box
    assert run.lock_path.exists(), "the stage released a lock it did not own"
    assert json.loads(run.lock_path.read_text())["token"] == "another-invocation"


def test_r53_a_racing_recovery_or_stage_cannot_take_the_slot(tmp_path, monkeypatch):
    """defect: while one recovery works, a second recovery and a stage are refused."""
    run = br.Run.create(tmp_path / "run", TINY)
    proc = crash_controller(run)
    state = run.load()
    state["worker"] = {"pid": 2 ** 22 + 12345, "start": 1, "exe": "gone", "pending": False,
                       "stage": "S1"}
    run.save(state)
    entered, release, calls = threading.Event(), threading.Event(), []

    def slow_stop(worker, until):
        calls.append(worker)
        if len(calls) == 1:
            entered.set()
            release.wait(30)
        return "gone"
    monkeypatch.setattr(br, "terminate_owned", slow_stop)
    monkeypatch.setattr(br, "preflight", refused_preflight)
    thread, box = in_thread(br.recover_command, ns(run.dir))
    try:
        assert entered.wait(30)
        assert br.recover_command(ns(run.dir)) != 0
        assert len(calls) == 1, "a second recovery ran concurrently"
        assert run.lock_path.exists()
        with pytest.raises(br.RunError):
            br.stage_command(stage_args(run.dir, "S1"))
    finally:
        release.set()
        thread.join(30)
    assert box.get("value") == 0, box
    assert not run.lock_path.exists() and proc.returncode == 9


# ---- R54: typed, bound evidence --------------------------------------------------------------

def _plan(op):
    return {"execution_ms": 0.1, "planning_ms": 0.1, "scans": [["transactions", "Index Scan"]],
            "temp_blocks": 0}


def _timed(kind, n, ms=10.0, **extra):
    return [{"kind": kind, "elapsed_ms": ms, **extra} for _ in range(n)]


def cell_record(cell: br.Cell, platform: str) -> dict:
    """A complete, typed cell record shaped as the worker writes it."""
    base = {"platform": platform, "cell": asdict(cell), "cell_s": 1.0, "status": "complete"}
    if cell.phase in ("A", "B", "E"):
        statements = [sid for sid, _ in rb.OPERATIONS[cell.op.removesuffix("_cols")]]
        return {**base, "warmup": _timed("ok", cell.warmup), "timed": _timed("ok", 5),
                "explain": [{"statement": s, "outcome": {"kind": "ok"}, "plan": _plan(s)}
                            for s in statements] if cell.explain else [],
                "median_ms": 10.0}
    if cell.phase == "BG":
        return {**base, "warmup": [], "timed": _timed("too_large", 5, 5.0), "explain": [],
                "median_ms": 5.0}
    if cell.phase == "D":
        return {**base, "timed": _timed("ok", cell.timed), "max_ms": 10.0}
    if cell.expect == "C5":
        return {**base, "label": "fault injection: delayed final close (not cancellation "
                "latency)", "timed": [
                    {"holders": ["no_reply", "no_reply"]},
                    {"counts_held": [0, 2], "quarantined": 2},
                    {"connect_calls": 0, "third": "admission_refused"},
                    {"close_calls": [1, 1], "drained": True},
                    {"connect_calls": 1, "fresh": "ok"}]}
    work_end = cell.budget_ms - 250
    # Each control run carries its defining diagnostics, as Worker.control records them.
    extra = {"C1": {"kind": "refused_before_submission", "submitted": 0, "sql_submitted": 0,
                    "observer": [], "refused_at": "Ka", "rollback": "not_needed",
                    "retired": False, "close": "closed", "work_end_ms": work_end},
             "C2": {"kind": "server_cancelled", "sqlstate": "57014",
                    "error_class": "QueryCanceled", "submitted": 2, "sql_submitted": 1,
                    "observer": [["an01-m1:C2:S", "active", "Timeout"]]},
             "C3": {"kind": "lock_timeout", "sqlstate": "55P03",
                    "error_class": "LockNotAvailable", "submitted": 2, "sql_submitted": 1,
                    "observer": [["an01-m1:totals:G", "active", "Lock"]]},
             "C4": {"kind": "no_reply", "submitted": 2, "sql_submitted": 1, "retired": True,
                    "close": "retired", "rollback": "not_needed", "relay_saw_statement": True,
                    "drained": True, "drain_s": 0.2, "events": ["retired", "final_close"],
                    "work_end_ms": work_end}}[cell.expect]
    if cell.expect in ("C2", "C3"):
        extra.update(deadline_to_error_ms=5.0, rollback="answered", rollback_ms=2.0,
                     error_at_ms=float(work_end - 20), work_end_ms=work_end,
                     armed_deadline_ms=float(work_end - 25), retired=False, close="closed")
    kind = extra.pop("kind")
    return {**base, "timed": _timed(kind, cell.timed, proved=True, **extra)}


def stage_record(stage: str, platform: str, profile=TINY, cells=None, identities=None,
                 os_name=None) -> dict:
    if cells is None:
        cells = {c.id: cell_record(c, platform) for c in br.grid(profile, n_star=80)
                 if c.stage == stage}
    return {"schema": RECORD_SCHEMA, "kind": "an01-m1-stage-record", "stage": stage,
            "platform": platform, "profile": profile.name,
            "identities": identities or br.identities(), "record": {"status": "complete"},
            "datasets": {}, "selection": {}, "cells": cells,
            "environment": {"os": os_name or {"windows": "Windows", "linux": "Linux"}
                            .get(platform, platform), "python": "3.11"}}


def write_records(folder: Path, records: list[dict]) -> list[str]:
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, data in enumerate(records):
        path = folder / f"{i}-{data['stage']}-{data['platform']}.json"
        path.write_text(json.dumps(data))
        paths.append(str(path))
    return paths


def b_cells(platform, mutate=None):
    cells = {}
    for stage in ("S5a", "S5b"):
        cells.update(stage_record(stage, platform)["cells"])
    if mutate:
        mutate(cells)
    return cells


def test_r54_empty_guard_outcomes_never_qualify_a_cap():
    """defect: complete B-guard cells with no timed outcome cannot demonstrate N*."""
    def empty(cells):
        for cid in cells:
            if cid.startswith("BG:"):
                cells[cid]["timed"] = []
    answer = br.rule_n_star({"windows": b_cells("windows", empty),
                             "linux": b_cells("linux", empty)}, TINY.sizes)
    assert answer["value"]["demonstrated"] is False and answer["value"]["n_star"] is None


def test_r54_good_cap_evidence_still_qualifies():
    """control"""
    answer = br.rule_n_star({"windows": b_cells("windows"), "linux": b_cells("linux")},
                            TINY.sizes)
    assert answer["value"] == {"n_star": 80, "demonstrated": True}


@pytest.mark.parametrize("bad", [None, float("nan"), float("inf"), "10"])
def test_r54_unknown_or_non_finite_times_are_not_demonstrated(bad):
    def poison(cells):
        cells["B:D1:20:totals:base"]["timed"][2]["elapsed_ms"] = bad
    answer = br.rule_n_star({"windows": b_cells("windows", poison),
                             "linux": b_cells("linux")}, TINY.sizes)
    assert answer["value"]["demonstrated"] is False


def test_r54_short_guard_or_phase_b_counts_are_not_demonstrated():
    def short(cells):
        cells["BG:totals"]["timed"] = cells["BG:totals"]["timed"][:4]
    answer = br.rule_n_star({"windows": b_cells("windows", short),
                             "linux": b_cells("linux")}, TINY.sizes)
    assert answer["value"]["demonstrated"] is False


def test_r54_the_platform_pair_must_be_windows_and_linux():
    """defect: two records that are not the windows/linux pair cannot select anything."""
    for pair in (("windows", "darwin"), ("linux", "native")):
        answer = br.rule_n_star({p: b_cells(p) for p in pair}, TINY.sizes)
        assert answer["value"]["demonstrated"] is False, pair


def test_r54_mixed_sql_identities_are_refused(tmp_path):
    """defect"""
    other = {**br.identities(), "registry_sha256": "b" * 64}
    paths = write_records(tmp_path, [stage_record("S5a", "windows"),
                                     stage_record("S5a", "linux", identities=other)])
    with pytest.raises(br.RunError):
        br.load_records(paths)


def test_r54_mixed_profiles_are_refused(tmp_path):
    """defect"""
    full = stage_record("S5a", "linux")
    full["profile"] = "full"
    paths = write_records(tmp_path, [stage_record("S5a", "windows"), full])
    with pytest.raises(br.RunError):
        br.load_records(paths)


def test_r54_records_from_other_source_code_are_refused(tmp_path):
    """defect: a record whose source digests are not this code's cannot be combined."""
    ident = br.identities()
    old = {**ident, "sources": {**ident["sources"], "scripts/benchmark_reports.py": "0" * 64}}
    paths = write_records(tmp_path, [stage_record("S5a", "windows", identities=old),
                                     stage_record("S5a", "linux", identities=old)])
    with pytest.raises(br.RunError):
        br.load_records(paths)


def test_r54_a_record_whose_platform_contradicts_its_environment_is_refused(tmp_path):
    """defect"""
    paths = write_records(tmp_path, [stage_record("S5a", "windows"),
                                     stage_record("S5a", "linux", os_name="Windows")])
    with pytest.raises(br.RunError):
        br.load_records(paths)


def test_r54_a_later_record_cannot_replace_an_earlier_failure(tmp_path):
    """defect: conflicting outcomes for one platform/cell are refused, never merged."""
    first = stage_record("S5a", "windows")
    first["cells"]["B:D1:20:totals:base"]["status"] = "failed"
    paths = write_records(tmp_path, [first, stage_record("S5a", "windows")])
    with pytest.raises(br.RunError):
        br.load_records(paths)


def test_r54_the_same_record_given_twice_is_refused_explicitly(tmp_path):
    paths = write_records(tmp_path, [stage_record("S5a", "windows")])
    with pytest.raises(br.RunError):
        br.load_records(paths + paths)


def c_cells(platform, mutate=None):
    cells = stage_record("S6", platform)["cells"]
    if mutate:
        mutate(cells)
    return cells


def test_r54_rollback_over_half_the_reserve_opens_review():
    """defect: rule 3's pre-registered R trigger (any C2/C3 ROLLBACK > 50% of R)."""
    def slow(cells):
        cells["C3:700"]["timed"][1]["rollback_ms"] = 200.0
    answer = br.rule_controls({"windows": c_cells("windows", slow),
                               "linux": c_cells("linux")})
    assert any("rollback" in t.lower() for t in answer["triggers"]), answer


def test_r54_controls_with_complete_evidence_demonstrate_without_triggers():
    """control"""
    answer = br.rule_controls({"windows": c_cells("windows"), "linux": c_cells("linux")})
    assert answer["demonstrated"] is True and answer["triggers"] == [], answer


@pytest.mark.parametrize("field", ["rollback_ms", "deadline_to_error_ms"])
def test_r54_unknown_required_control_metrics_are_not_demonstrated(field):
    """defect: an answered C2/C3 run without its measured interval is not evidence."""
    def drop(cells):
        cells["C2:400"]["timed"][0][field] = None
    answer = br.rule_controls({"windows": c_cells("windows", drop),
                               "linux": c_cells("linux")})
    assert answer["demonstrated"] is False, answer


def test_r54_control_cells_need_their_registered_run_counts():
    """defect"""
    def short(cells):
        cells["C2:400"]["timed"] = cells["C2:400"]["timed"][:4]
    answer = br.rule_controls({"windows": c_cells("windows", short),
                               "linux": c_cells("linux")})
    assert answer["demonstrated"] is False, answer


def selection_from(tmp_path, rule, records, profile="tiny") -> Path:
    paths = write_records(tmp_path / f"records-{rule}", records)
    out = tmp_path / f"selection-{rule}.json"
    args = ["select", "--rule", rule, "--profile", profile, "--out", str(out)]
    for path in paths:
        args += ["--record", path]
    assert br.main(args) == 0
    return out


def test_r54_a_bound_demonstrated_selection_is_consumed(tmp_path, monkeypatch):
    """control"""
    selection = selection_from(tmp_path, "common-index",
                               [stage_record("S2", p) for p in ("windows", "linux")])
    run = br.Run.create(tmp_path / "run", TINY)
    monkeypatch.setattr(br, "preflight", refused_preflight)
    code = br.stage_command(stage_args(run.dir, "S4", selection=str(selection)))
    assert code == br.EXIT["refused"]       # reached admission; refused only by preflight


def test_r54_an_undemonstrated_selection_is_never_consumed(tmp_path, monkeypatch):
    """defect"""
    windows = stage_record("S2", "windows")
    del windows["cells"]["A:A:totals"]
    selection = selection_from(tmp_path, "common-index",
                               [windows, stage_record("S2", "linux")])
    assert json.loads(selection.read_text())["value"]["demonstrated"] is False
    run = br.Run.create(tmp_path / "run", TINY)
    monkeypatch.setattr(br, "preflight", refused_preflight)
    with pytest.raises(br.RunError):
        br.stage_command(stage_args(run.dir, "S4", selection=str(selection)))


@pytest.mark.parametrize("change", ["identities", "profile", "value"])
def test_r54_a_selection_bound_elsewhere_or_edited_is_refused(tmp_path, monkeypatch, change):
    """defect: a selection must carry, and match, this run's profile and identities."""
    selection = selection_from(tmp_path, "common-index",
                               [stage_record("S2", p) for p in ("windows", "linux")])
    data = json.loads(selection.read_text())
    binding = data.setdefault("binding", {})
    if change == "identities":
        binding["identities_sha256"] = "0" * 64
    elif change == "profile":
        binding["profile"] = "full"
    else:
        data["value"]["variant"] = "C"           # an edited value: its digest is stale
    digest = getattr(br, "selection_digest", None)
    if digest is not None and change != "value":
        data["selection_sha256"] = digest(data)  # consistent, so the binding itself is checked
    selection.write_text(json.dumps(data))
    run = br.Run.create(tmp_path / "run", TINY)
    monkeypatch.setattr(br, "preflight", refused_preflight)
    with pytest.raises(br.RunError):
        br.stage_command(stage_args(run.dir, "S4", selection=str(selection)))


# ---- R55-R57: the report runtime with controlled connections ---------------------------------

TOTALS_ROW = {"currency": "USD", "debit_count": 1, "credit_count": 0, "debit_minor": "100",
              "credit_minor": "0"}


class RInfo:
    def __init__(self, conn):
        self.conn = conn

    @property
    def transaction_status(self):
        return (psycopg.pq.TransactionStatus.INTRANS if self.conn.began
                else psycopg.pq.TransactionStatus.IDLE)


class RConn:
    """A controlled report connection: a fake report clock (ms) advanced by arming and by
    statements; per-tag rows; optional error/late arrival, blocked statements or rollback,
    and close failures. Every gate is bounded and released in each test's finally."""

    def __init__(self, clock=None, arm_ms=0.0, sql_ms=0.0, error_on=None, error=None,
                 block_on=None, gate=None, rollback_gate=None, rollback_error=False,
                 close_failures=0, rows=None):
        self.clock, self.arm_ms, self.sql_ms = clock, arm_ms, sql_ms
        self.error_on, self.error = error_on, error
        self.block_on, self.gate = block_on, gate
        self.rollback_gate, self.rollback_error = rollback_gate, rollback_error
        self.close_failures = close_failures
        self.rows = rows or {}
        self.began = False
        self.sql, self.params = [], []
        self.close_calls, self.closed = 0, False
        self.info = RInfo(self)

    def fileno(self):
        raise OSError("controlled connection has no socket")

    def _advance(self, ms):
        if self.clock is not None:
            self.clock[0] += ms

    def execute(self, text, params=None):
        self.began = True
        if "set_config" in text:
            self._advance(self.arm_ms)
            return FakeCursor([])
        self.sql.append(text)
        self.params.append(dict(params or {}))
        if self.block_on and self.block_on in text:
            self.gate.wait(30)
            raise psycopg.OperationalError("socket shut under the statement")
        self._advance(self.sql_ms)
        if self.error_on and self.error_on in text:
            raise self.error
        for tag, rows in self.rows.items():
            if tag in text:
                return FakeCursor(rows)
        if ":G */" in text:
            return FakeCursor([{"n": 1}])
        if ":P */" in text:
            return FakeCursor([{"matching": 1, "with_outcome": 1}])
        return FakeCursor([TOTALS_ROW])

    def rollback(self):
        if self.rollback_gate is not None:
            self.rollback_gate.wait(30)
            raise psycopg.OperationalError("socket shut under ROLLBACK")
        if self.rollback_error:
            raise psycopg.OperationalError("synthetic ROLLBACK failure")
        self.began = False

    def close(self):
        self.close_calls += 1
        if self.close_failures:
            self.close_failures -= 1
            raise OSError("synthetic close refusal")
        self.closed = True


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


def rt_for(conn, *, clock=None, resources=None, quarantine=None, **kw):
    kw.setdefault("read_clock", lambda: datetime(2026, 10, 3, tzinfo=UTC))
    if clock is not None:
        kw["clock"] = lambda: clock[0]
    return rb.Runtime(connect=lambda: conn, resources=resources or rb.Resources(),
                      quarantine=quarantine or rb.ReportQuarantine(), **kw)


SEQ = [("G", "/* an01-m1:totals:G */ SELECT 1", {}),
       ("Q", "/* an01-m1:totals:Q */ SELECT 2", {})]


@pytest.fixture
def workflow_quarantine_unchanged():
    from sentinel.agents import budget
    before = budget.QUARANTINE.count()
    yield
    assert budget.QUARANTINE.count() == before


# ---- R55

@pytest.mark.parametrize("arm_ms,sends", [(10, True), (90, False), (160, False)])
def test_r55_budget_is_rechecked_after_arming(arm_ms, sends, workflow_quarantine_unchanged):
    """defect (90, 160) / control (10): B=400, R=250, work_end=150 ms; arming takes arm_ms.
    The statement is sent only if floor(work_end - now) - margin is still >= MIN_DB_MS."""
    clock = [0.0]
    conn = RConn(clock, arm_ms=arm_ms)
    rt = rt_for(conn, clock=clock, total_ms=400, reserve_ms=250)
    out = rb.run_statements(rt, SEQ[:1])
    assert bool(conn.sql) is sends, out.public()
    if not sends:
        assert out.kind != "ok" and out.sql_submitted == 0 and out.http.startswith("503")
    assert _until(lambda: rt.resources.counts() == (0, 0))


def test_r55_the_server_deadline_is_measured_from_submission():
    """defect: with arming taking 10 ms, the armed timeout (120 ms) starts at the SQL
    submission (10 ms), so the recorded server deadline is 130 ms, not 120."""
    clock = [0.0]
    conn = RConn(clock, arm_ms=10)
    out = rb.run_statements(rt_for(conn, clock=clock, total_ms=400, reserve_ms=250), SEQ[:1])
    assert out.kind == "ok" and out.armed_deadline_ms == 130.0, out.public()


@pytest.mark.parametrize("wait_ms", [0, -5, 0.0])
def test_r55_bounded_call_refuses_a_non_positive_wait_before_starting_work(wait_ms):
    """defect: an expired wait must not start the operation thread."""
    admission = rb.Resources().admit()
    rc = rb.ReportConnection(RConn(), admission, rb.ReportQuarantine())
    called = []
    with pytest.raises(Exception):
        rb.bounded_call(rc, lambda: called.append(1), wait_ms)
    time.sleep(0.05)
    assert called == []


def test_r55_answered_branch_on_time(workflow_quarantine_unchanged):
    """control: the server's cancel arrives at 120 ms, before work_end 150 ms."""
    clock = [0.0]
    conn = RConn(clock, sql_ms=120, error_on="totals:G",
                 error=psycopg.errors.QueryCanceled("synthetic"))
    rt = rt_for(conn, clock=clock, total_ms=400, reserve_ms=250)
    out = rb.run_statements(rt, SEQ)
    assert out.kind == "server_cancelled" and out.rollback == "answered"
    assert out.error_at_ms == 120.0 <= out.work_end_ms
    assert conn.close_calls == 1 and rt.resources.counts() == (0, 0)


def test_r55_a_late_arrival_is_never_classified_as_answered(workflow_quarantine_unchanged):
    """defect: the cancel ARRIVES at 155 ms, after work_end 150 ms; the waiter notices it,
    but the outcome must not be server_cancelled (a reply on time)."""
    clock = [0.0]
    conn = RConn(clock, sql_ms=155, error_on="totals:G",
                 error=psycopg.errors.QueryCanceled("synthetic"))
    rt = rt_for(conn, clock=clock, total_ms=400, reserve_ms=250)
    out = rb.run_statements(rt, SEQ)
    assert out.kind not in ("server_cancelled", "lock_timeout", "ok"), out.public()
    assert out.http.startswith("503")
    assert _until(lambda: rt.resources.counts() == (0, 0) and rt.quarantine.count() == 0)
    assert conn.close_calls == 1


def test_r55_no_reply_branch(workflow_quarantine_unchanged):
    """control"""
    gate = threading.Event()
    conn = RConn(block_on="totals:G", gate=gate)
    rt = rt_for(conn, total_ms=400, reserve_ms=250)
    try:
        out = rb.run_statements(rt, SEQ)
        assert out.kind == "no_reply" and out.retired
        assert rt.resources.counts() == (0, 1) and rt.quarantine.count() == 1
    finally:
        gate.set()
    assert _until(lambda: rt.resources.counts() == (0, 0) and rt.quarantine.count() == 0)
    assert conn.close_calls == 1


# ---- R56

def test_r56_a_failed_close_keeps_its_reservation_and_owner(workflow_quarantine_unchanged):
    """defect: a close that raises is not a close."""
    conn = RConn(close_failures=1)
    rt = rt_for(conn)
    out = rb.run_statements(rt, SEQ)
    assert not conn.closed
    assert rt.resources.counts() == (0, 1), "reservation released without an actual close"
    assert rt.quarantine.count() == 1, "no accountable owner holds the unclosed connection"
    assert getattr(out, "close", None) != "closed", "a failed close reported as closed"


def test_r56_a_hook_failure_cannot_orphan_the_connection(workflow_quarantine_unchanged):
    """defect: an observer/setup hook failure after acquisition still closes it."""
    conn = RConn()

    def hook(raw):
        raise psycopg.OperationalError("synthetic observer failure")
    rt = rt_for(conn, on_connect=hook)
    with pytest.raises(psycopg.Error):
        rb.run_statements(rt, SEQ)
    assert conn.close_calls == 1 and conn.closed
    assert rt.resources.counts() == (0, 0) and rt.quarantine.count() == 0
    assert conn.sql == []


def test_r56_an_interrupt_in_the_hook_closes_and_propagates(workflow_quarantine_unchanged):
    conn = RConn()

    def hook(raw):
        raise KeyboardInterrupt
    rt = rt_for(conn, on_connect=hook)
    with pytest.raises(KeyboardInterrupt):
        rb.run_statements(rt, SEQ)
    assert conn.closed and rt.resources.counts() == (0, 0)


def test_r56_an_interrupt_while_waiting_transfers_the_busy_connection(
        monkeypatch, workflow_quarantine_unchanged):
    """defect: Ctrl-C while the SQL thread still uses the connection: the request must not
    ROLLBACK or close it under that thread; ownership moves to the final close."""
    import sentinel.clock as sclock
    real, calls = sclock.wait_until, []

    def interrupted(*args, **kwargs):
        calls.append(1)
        if len(calls) == 2:                 # the wait for G (after Ka answered)
            raise KeyboardInterrupt
        return real(*args, **kwargs)
    monkeypatch.setattr(sclock, "wait_until", interrupted)
    gate = threading.Event()
    conn = RConn(block_on="totals:G", gate=gate)
    rt = rt_for(conn, total_ms=3000, reserve_ms=250)
    try:
        with pytest.raises(KeyboardInterrupt):
            rb.run_statements(rt, SEQ)
        assert conn.close_calls == 0, "closed under the running SQL thread"
        assert rt.resources.counts() == (0, 1) and rt.quarantine.count() == 1
    finally:
        gate.set()
    assert _until(lambda: rt.resources.counts() == (0, 0) and rt.quarantine.count() == 0)
    assert conn.close_calls == 1


def test_r56_a_failed_final_close_after_late_return_keeps_ownership(
        workflow_quarantine_unchanged):
    """defect: the lease's final close fails too: still reserved and held."""
    gate = threading.Event()
    conn = RConn(block_on="totals:G", gate=gate, close_failures=1)
    rt = rt_for(conn, total_ms=400, reserve_ms=250)
    try:
        out = rb.run_statements(rt, SEQ)
        assert out.kind == "no_reply"
    finally:
        gate.set()
    assert _until(lambda: out.connection.users == set())
    time.sleep(0.05)
    assert conn.close_calls == 1 and not conn.closed
    assert rt.resources.counts() == (0, 1) and rt.quarantine.count() == 1


def test_r56_retry_closes_once_and_releases_once(workflow_quarantine_unchanged):
    """new behaviour (not failing-first evidence: the retry entry point did not exist)."""
    conn = RConn(close_failures=1)
    rt = rt_for(conn)
    out = rb.run_statements(rt, SEQ)
    rc = out.connection
    assert rc.close_state == "close_failed" and out.close == "close_failed"
    assert rc.retry_close() is True
    assert conn.closed and conn.close_calls == 2
    assert rt.resources.counts() == (0, 0) and rt.quarantine.count() == 0
    assert rc.retry_close() is False and rc.admission.releases == 1
    assert rt.resources.counts() == (0, 0)


def test_r56_healthy_path_closes_once(workflow_quarantine_unchanged):
    """control"""
    conn = RConn()
    rt = rt_for(conn)
    out = rb.run_statements(rt, SEQ)
    assert out.kind == "ok" and conn.close_calls == 1 and conn.closed
    assert rt.resources.counts() == (0, 0) and out.connection.admission.releases == 1


# ---- R57

ZONES = rb.ZoneTable()
REQ_AT = datetime(2026, 10, 3, tzinfo=UTC)
SNAP_AT = datetime(2026, 10, 4, tzinfo=UTC)
WIN = ("2026-10-01T00:00:00Z", "2026-10-02T00:00:00Z")
SCOPE = (uuid.UUID(int=1), uuid.UUID(int=2))


def totals_request(**kw):
    return rb.normalize(ZONES, "transactions.currency_totals", read_at=REQ_AT,
                        from_=WIN[0], to=WIN[1], **kw)


def test_r57_answered_reads_survive_an_unanswered_rollback(workflow_quarantine_unchanged):
    """defect: every read answered; ROLLBACK unanswered by B: 200 WITH the report."""
    gate = threading.Event()
    conn = RConn(rollback_gate=gate)
    rt = rt_for(conn, total_ms=400, reserve_ms=250, read_clock=lambda: SNAP_AT)
    try:
        out, body = rb.run_report(rt, totals_request(), SCOPE, ZONES)
        assert out.kind == "rollback_unanswered" and out.retired and out.http.startswith("200")
        assert body is not None, "a fully answered report was dropped"
        assert body["rows"][0]["debit_minor"] == "100"
        assert body["consistency"] == {"matching_transactions": 1, "with_outcome": 1}
    finally:
        gate.set()
    assert _until(lambda: rt.resources.counts() == (0, 0) and rt.quarantine.count() == 0)


def test_r57_a_rollback_error_after_answered_reads_keeps_the_report():
    """control"""
    conn = RConn(rollback_error=True)
    out, body = rb.run_report(rt_for(conn), totals_request(), SCOPE, ZONES)
    assert out.rollback == "error_closed" and body is not None and conn.closed


@pytest.mark.parametrize("failure", ["no_reply", "too_large", "error"])
def test_r57_an_incomplete_read_never_produces_a_body(failure, workflow_quarantine_unchanged):
    gate = threading.Event()
    conn = {"no_reply": lambda: RConn(block_on="totals:Q", gate=gate),
            "too_large": lambda: RConn(rows={":G */": [{"n": rb.MATCHING_ROW_CAP + 1}]}),
            "error": lambda: RConn(error_on="totals:P",
                                   error=psycopg.errors.UndefinedTable("synthetic"))}[failure]()
    rt = rt_for(conn, total_ms=400, reserve_ms=250)
    try:
        out, body = rb.run_report(rt, totals_request(), SCOPE, ZONES)
        assert body is None and out.kind == failure
    finally:
        gate.set()
    assert _until(lambda: rt.resources.counts() == (0, 0))


def test_r57_dto_read_at_is_the_snapshot_boundary_and_as_of_stays_explicit():
    """defect: acquisition waited; the snapshot was read at 10-04, the cutoff is 10-03."""
    conn = RConn()
    out, body = rb.run_report(rt_for(conn, read_clock=lambda: SNAP_AT),
                              totals_request(as_of="2026-10-03T00:00:00Z"), SCOPE, ZONES)
    assert out.read_at == SNAP_AT
    assert body["provenance"]["read_at"] == rb.iso(SNAP_AT)
    assert body["provenance"]["as_of"] == "2026-10-03T00:00:00.000000Z"
    assert all(p["as_of"] == datetime(2026, 10, 3, tzinfo=UTC) for p in conn.params)


def test_r57_a_default_cutoff_binds_to_the_snapshot_read_at():
    """defect: as_of omitted means as_of = read_at, the actual snapshot boundary."""
    conn = RConn()
    out, body = rb.run_report(rt_for(conn, read_clock=lambda: SNAP_AT), totals_request(),
                              SCOPE, ZONES)
    assert body["provenance"]["as_of"] == body["provenance"]["read_at"] == rb.iso(SNAP_AT)
    assert conn.params and all(p["as_of"] == SNAP_AT and p["read_at"] == SNAP_AT
                               for p in conn.params)


def test_r57_workload_open_ages_use_the_snapshot_read_at():
    """defect: the workload age buckets are computed against the actual read_at."""
    conn = RConn(rows={"workload:Q1": [], "workload:Q2": [{"n": 0}], "workload:Q3": []})
    request = rb.normalize(ZONES, "cases.workload", read_at=REQ_AT, from_=WIN[0], to=WIN[1],
                           as_of="2026-10-02T00:00:00Z")
    out, body = rb.run_report(rt_for(conn, read_clock=lambda: SNAP_AT), request, SCOPE, ZONES)
    assert body is not None
    q3 = [p for text, p in zip(conn.sql, conn.params) if "workload:Q3" in text]
    assert q3 and q3[0]["read_at"] == SNAP_AT


def drill_rows(n):
    base = datetime(2026, 10, 1, 1, tzinfo=UTC)
    return [{"id": uuid.UUID(int=100 + i), "external_id": f"x{i}", "occurred_at":
             base + timedelta(minutes=i), "ingested_at": base + timedelta(minutes=i),
             "currency": "USD", "minor_units": "1", "direction": "debit", "alerted": False,
             "score": 0.1, "scoring_kind": "k", "score_semantics": "s", "case_id": None,
             "case_state": None} for i in range(n)]


def test_r57_page_one_cursor_binds_the_resolved_cutoff():
    """defect: a page-1 cursor issued under a default as_of is bound to the resolved
    (snapshot) as_of, which page 2 must repeat explicitly."""
    conn = RConn(rows={":G */": [{"n": 3}], ":P */": [{"matching": 3, "with_outcome": 3}],
                       "drill_first:Q": drill_rows(2)})
    request = rb.normalize(ZONES, "rows.transactions", read_at=REQ_AT, from_=WIN[0],
                           to=WIN[1], limit=1)
    out, body = rb.run_report(rt_for(conn, read_clock=lambda: SNAP_AT), request, SCOPE,
                              ZONES)
    assert body["provenance"]["as_of"] == rb.iso(SNAP_AT) and body["next_cursor"]
    later = SNAP_AT + timedelta(hours=1)
    page2 = rb.normalize(ZONES, "rows.transactions", read_at=later, from_=WIN[0], to=WIN[1],
                         limit=1, as_of=body["provenance"]["as_of"],
                         cursor=body["next_cursor"])
    assert page2.cursor[2:] == (3, 3)
    with pytest.raises(rb.InvalidCursor):
        rb.normalize(ZONES, "rows.transactions", read_at=later, from_=WIN[0], to=WIN[1],
                     limit=1, cursor=body["next_cursor"])


# ---- R57 on real PostgreSQL: delayed acquisition and an unanswered readonly ROLLBACK -------

T1 = uuid.UUID("10000000-0000-4000-8000-000000000001")
S1 = uuid.UUID("20000000-0000-4000-8000-000000000001")


@pytest.fixture
def runtime_url(database_url):
    role = f"an01m1_rv_{os.getpid()}_{secrets.token_hex(3)}"
    password = secrets.token_urlsafe(18)   # synthetic; never printed
    roles.grant_runtime(database_url, role, password)
    yield make_conninfo(database_url, user=role, password=password)
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute(f'DROP OWNED BY "{role}"')
        conn.execute(f'DROP ROLE "{role}"')


class HeldRollback:
    """A real report connection whose ROLLBACK is held by a test gate (the server never
    sees it before B); every other attribute is the real connection's."""

    def __init__(self, conn, gate):
        self._conn, self._gate = conn, gate

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def rollback(self):
        self._gate.wait(20)
        return self._conn.rollback()


def test_r57_real_report_with_delayed_acquisition_and_unanswered_rollback(
        database_url, runtime_url, workflow_quarantine_unchanged):
    from test_report_benchmark import build_r2
    rb.copy_rows(database_url, build_r2())
    gate = threading.Event()
    connect = rb.runtime_connect(runtime_url)

    def slow_connect():
        time.sleep(0.2)                         # acquisition waits outside B
        return HeldRollback(connect(), gate)
    request_at = datetime.now(UTC)
    request = rb.normalize(ZONES, "transactions.currency_totals", read_at=request_at,
                           from_=WIN[0], to=WIN[1], as_of="2026-10-02T06:00:00Z")
    rt = rb.Runtime(connect=slow_connect, resources=rb.Resources(),
                    quarantine=rb.ReportQuarantine(), total_ms=1250)
    try:
        out, body = rb.run_report(rt, request, (T1, S1), ZONES)
        assert out.kind == "rollback_unanswered" and out.retired, out.public()
        assert body is not None
        assert out.read_at >= request_at + timedelta(milliseconds=150)
        assert body["provenance"]["read_at"] == rb.iso(out.read_at)
        assert body["provenance"]["as_of"] == "2026-10-02T06:00:00.000000Z"
        assert [(r["currency"], r["debit_minor"], r["credit_minor"]) for r in body["rows"]] == [
            ("GBP", "0", "10000"), ("INR", "8000000", "250050"), ("JPY", "200000", "0"),
            ("USD", "265500", "7000")]
        assert rt.resources.counts() == (0, 1) and rt.quarantine.count() == 1
    finally:
        gate.set()
    assert _until(lambda: rt.resources.counts() == (0, 0) and rt.quarantine.count() == 0)
    assert out.connection.close_calls == 1
    assert not math.isnan(out.elapsed_ms)


# ---- R54 residual (review 5e0a578): summaries and control diagnostics -----------------------
# Every case goes through the public loader (load_records) and then a rule, as `select`
# and `report` do. Mutations are validation counterexamples applied to synthetic records
# shaped like the worker's, never to captured smoke records.

def loaded(tmp_path, records: list[dict]) -> dict:
    return br.load_records(write_records(tmp_path / secrets.token_hex(4), records), "tiny")


def s6_pair(mutate=None):
    out = []
    for p in br.PAIR:
        rec = stage_record("S6", p)
        if mutate:
            mutate(rec["cells"])
        out.append(rec)
    return out


def test_r54b_unmodified_records_still_qualify(tmp_path):
    """control"""
    s2 = loaded(tmp_path, [stage_record("S2", p) for p in br.PAIR])
    assert br.rule_common_index(s2)["value"] == {"variant": "A", "demonstrated": True}
    controls = br.rule_controls(loaded(tmp_path, s6_pair()))
    assert controls["demonstrated"] is True and controls["triggers"] == [], controls


def test_r54b_contradictory_medians_cannot_select_an_index(tmp_path):
    """defect: B's stored medians claim 100x faster than its own timed outcomes."""
    records = [stage_record("S2", p) for p in br.PAIR]
    for rec in records:
        for op in rb.OPERATIONS:
            rec["cells"][f"A:B:{op}"]["median_ms"] = rec["cells"][f"A:A:{op}"]["median_ms"] / 100
    value = br.rule_common_index(loaded(tmp_path, records))["value"]
    assert not (value["variant"] == "B" and value["demonstrated"]), value


def test_r54b_a_median_derived_from_timed_outcomes_is_used(tmp_path):
    """control: a stored median equal to the timed median (at 0.001 ms) is accepted."""
    records = [stage_record("S2", p) for p in br.PAIR]
    for rec in records:
        cell = rec["cells"]["A:A:totals"]
        for i, t in enumerate(cell["timed"]):
            t["elapsed_ms"] = [9.0, 11.0, 10.0, 12.0, 8.0][i]
        cell["median_ms"] = 10.0
    assert br.rule_common_index(loaded(tmp_path, records))["value"]["demonstrated"] is True


@pytest.mark.parametrize("case", ["c5-empty", "c5-no-refusal", "c5-not-drained",
                                  "c1-submitted", "c1-observer-saw", "c2-no-observer",
                                  "c2-late", "c2-wrong-sqlstate", "c3-no-lock-wait",
                                  "c4-relay-blind", "c4-not-drained"])
def test_r54b_control_diagnostics_must_prove_the_control(tmp_path, case):
    """defect: proved=True / status complete / a nonempty list are not evidence by
    themselves; each control's own diagnostics must show what it claims."""
    def mutate(cells):
        name, _, what = case.partition("-")
        if name == "c5":
            timed = cells["C5"]["timed"]
            if what == "empty":
                cells["C5"]["timed"] = [{}]
            elif what == "no-refusal":
                timed[2] = {"connect_calls": 1, "third": "ok"}
            else:
                timed[3] = {"close_calls": [1, 0], "drained": False}
            return
        cid = {"c1": "C1:300", "c2": "C2:400", "c3": "C3:400", "c4": "C4:1250"}[name]
        for t in cells[cid]["timed"]:
            if case == "c1-submitted":
                t.update(kind="ok", submitted=99, sql_submitted=99)
            elif case == "c1-observer-saw":
                t["observer"] = [["an01-m1:totals:G", "active", None]]
            elif case == "c2-no-observer":
                t["observer"] = []
            elif case == "c2-late":
                t["error_at_ms"] = t["work_end_ms"] + 3.0
            elif case == "c2-wrong-sqlstate":
                t["sqlstate"] = "57P01"
            elif case == "c3-no-lock-wait":
                t["observer"] = [["an01-m1:totals:G", "active", None]]
            elif case == "c4-relay-blind":
                t["relay_saw_statement"] = False
            else:
                t["drained"] = False
    answer = br.rule_controls(loaded(tmp_path, s6_pair(mutate)))
    assert answer["demonstrated"] is False, answer


def test_r54b_a_stored_maximum_cannot_hide_over_budget_measurements(tmp_path):
    """defect: D's timed outcomes are 6000 ms; its stored max_ms claims 1."""
    def mutate(cells):
        for t in cells["D"]["timed"]:
            t["elapsed_ms"] = 6000.0
        cells["D"]["max_ms"] = 1.0
    answer = br.rule_controls(loaded(tmp_path, s6_pair(mutate)))
    assert answer["demonstrated"] is False or any("maximum" in t for t in answer["triggers"])


def test_r54b_raw_rule_inputs_fail_safe_without_the_loader():
    """defect: the rules apply the same evidence checks to raw dicts."""
    cells = {p: stage_record("S6", p)["cells"] for p in br.PAIR}
    for p in br.PAIR:
        cells[p]["C5"]["timed"] = [{}]
        for t in cells[p]["D"]["timed"]:
            t["elapsed_ms"] = 6000.0
        cells[p]["D"]["max_ms"] = 1.0
    answer = br.rule_controls(cells)
    assert answer["demonstrated"] is False, answer
    s2 = {p: stage_record("S2", p)["cells"] for p in br.PAIR}
    for p in br.PAIR:
        for op in rb.OPERATIONS:
            s2[p][f"A:B:{op}"]["median_ms"] = 0.1
    assert br.rule_common_index(s2)["value"]["variant"] != "B"


def test_r54b_n_star_tolerates_absent_summaries_but_not_contradictory_ones():
    """Added after the fix (not failing-first evidence): rule_n_star consumes only timed
    outcomes, so on raw input an absent median/EXPLAIN is tolerated (Codex's good-cap
    control), but a present median contradicting the timed outcomes disqualifies."""
    def bare(cells):
        for rec in cells.values():
            rec.pop("median_ms", None)
            rec.pop("explain", None)
    good = {p: b_cells(p, bare) for p in br.PAIR}
    assert br.rule_n_star(good, TINY.sizes)["value"] == {"n_star": 80, "demonstrated": True}
    bad = {p: b_cells(p) for p in br.PAIR}
    bad["linux"]["B:D2:20:totals:base"]["median_ms"] = 0.5
    assert br.rule_n_star(bad, TINY.sizes)["value"]["demonstrated"] is False


@pytest.mark.parametrize("bad", ["order", "outcome", "count"])
def test_r54b_explain_evidence_names_the_operation_statements(tmp_path, bad):
    """defect: EXPLAIN evidence must cover the operation's statements, in order, answered."""
    records = [stage_record("S2", p) for p in br.PAIR]
    for rec in records:
        explain = rec["cells"]["A:A:totals"]["explain"]
        if bad == "order":
            explain.reverse()
        elif bad == "outcome":
            explain[0]["outcome"] = {"kind": "server_cancelled"}
        else:
            explain.append(dict(explain[0]))
    value = br.rule_common_index(loaded(tmp_path, records))["value"]
    assert value["demonstrated"] is False, value


def test_r54b_an_invalid_mandatory_cell_is_not_mandatory_evidence(tmp_path):
    """defect: the final report cannot claim mandatory evidence over an unproved control."""
    records = [stage_record(s, p) for s in ("S2", "S5a", "S5b", "S6") for p in br.PAIR]
    for rec in records:
        if rec["stage"] == "S6":
            rec["cells"]["C5"]["timed"] = [{}]
    report = br.final_report(loaded(tmp_path, records), TINY)
    assert report["rule6_status"] == "not demonstrated", report["rule6_missing_mandatory"]


# ---- R56 residual: an interrupt after the ROLLBACK reply ----------------------------------

def _interrupt_at(monkeypatch, n, error):
    """Let the real wait helper finish, then raise `error` at the n-th wait."""
    import sentinel.clock as sclock
    real, calls = sclock.wait_until, []

    def wait(*args, **kwargs):
        calls.append(1)
        value = real(*args, **kwargs)
        if len(calls) == n:
            raise error()
        return value
    monkeypatch.setattr(sclock, "wait_until", wait)
    return calls


@pytest.mark.parametrize("error", [KeyboardInterrupt, SystemExit])
def test_r56b_interrupt_after_rollback_reply_still_closes(monkeypatch, error,
                                                         workflow_quarantine_unchanged):
    """defect: Ka, G, then ROLLBACK replies; the interrupt hits as ROLLBACK's waiter
    returns. Nothing uses the connection any more, so it must be closed once and released
    once, and the interrupt must still propagate."""
    calls = _interrupt_at(monkeypatch, 3, error)
    conn = RConn()
    rt = rt_for(conn)
    with pytest.raises(error):
        rb.run_statements(rt, SEQ[:1])
    assert len(calls) == 3
    assert conn.close_calls == 1 and conn.closed, "acquired connection left unowned"
    assert rt.resources.counts() == (0, 0) and rt.quarantine.count() == 0


@pytest.mark.parametrize("error", [KeyboardInterrupt, SystemExit])
def test_r56b_interrupt_raised_by_rollback_itself_still_closes(error,
                                                               workflow_quarantine_unchanged):
    """defect: ROLLBACK's own call raises the interrupt (it answered by raising)."""
    conn = RConn()

    def rollback():
        conn.began = False
        raise error()
    conn.rollback = rollback
    rt = rt_for(conn)
    with pytest.raises(error):
        rb.run_statements(rt, SEQ[:1])
    assert conn.close_calls == 1 and conn.closed
    assert rt.resources.counts() == (0, 0) and rt.quarantine.count() == 0


def test_r56b_interrupt_after_rollback_with_failed_close_keeps_an_owner(
        monkeypatch, workflow_quarantine_unchanged):
    """defect: the same interrupt, and the close then fails: reservation and owner kept."""
    _interrupt_at(monkeypatch, 3, KeyboardInterrupt)
    conn = RConn(close_failures=1)
    rt = rt_for(conn)
    with pytest.raises(KeyboardInterrupt):
        rb.run_statements(rt, SEQ[:1])
    assert conn.close_calls == 1 and not conn.closed
    assert rt.resources.counts() == (0, 1) and rt.quarantine.count() == 1


def test_r56b_interrupt_while_rollback_still_runs_transfers_to_the_lease(
        monkeypatch, workflow_quarantine_unchanged):
    """control: ROLLBACK has NOT replied when the interrupt lands: never closed under its
    running thread; the lease closes it after the late return."""
    import sentinel.clock as sclock
    real, calls = sclock.wait_until, []

    def wait(*args, **kwargs):
        calls.append(1)
        if len(calls) == 3:
            raise KeyboardInterrupt
        return real(*args, **kwargs)
    monkeypatch.setattr(sclock, "wait_until", wait)
    gate = threading.Event()
    conn = RConn(rollback_gate=gate)
    rt = rt_for(conn, total_ms=3000)
    try:
        with pytest.raises(KeyboardInterrupt):
            rb.run_statements(rt, SEQ[:1])
        assert conn.close_calls == 0 and rt.resources.counts() == (0, 1)
        assert rt.quarantine.count() == 1
    finally:
        gate.set()
    assert _until(lambda: rt.resources.counts() == (0, 0) and rt.quarantine.count() == 0)
    assert conn.close_calls == 1
