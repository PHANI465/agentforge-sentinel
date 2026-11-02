"""G3C R40: the investigator and live-role caller deadlines are measured on the monotonic clock.

Both callers waited with Future.result(timeout), a timed condition wait. On the observed uv
CPython 3.11.14 (HAVE_SEM_CLOCKWAIT = 0), that wait expires on CLOCK_REALTIME, which the
native WSL2 host steps by about 2.5 s (docs/agents/G3C-native-clock-diagnosis.md).

Only Future's own condition is skewed here, as a stepping realtime clock would skew it:
"forward" ends a positive timed wait almost at once, and "backward" lengthens it by one
second. System time, workers, database budgets and every other wait stay real. The real
service (over HTTP, single investigator) and coordinator (three-role, live adapter) run on
disposable PostgreSQL with synthetic workers; no provider is called. Workers always return or
are released in finally.
"""
import sys
import threading
import time
from concurrent import futures
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "support"))

import agent_cases as ac  # noqa: E402
from sentinel.investigators import DeterministicInvestigator, InvestigatorError  # noqa: E402
from test_thin_path import ANALYST, Harness, alerting_case  # noqa: E402

BUDGET_S = 1 + 2  # worker timeout_seconds 1 + the 2 s grace (investigator and role alike)


def skew_future_waits(monkeypatch, direction):
    """Futures created from now on wait on a skewed condition (only positive timeouts)."""
    original = futures._base.Future

    class Condition(threading.Condition):
        def wait(self, timeout=None):
            if timeout is None or timeout <= 0:
                return super().wait(timeout)
            return super().wait(0.001 if direction == "forward" else timeout + 1.0)

    class Future(original):
        def __init__(self):
            super().__init__()
            self._condition = Condition()
    monkeypatch.setattr(futures._base, "Future", Future)


# ---- single investigator, through the real HTTP route --------------------------------------

class Controlled(DeterministicInvestigator):
    """A deterministic investigator that answers after 150 ms, raises, or holds until
    released (a worker still running when the deadline passes)."""
    timeout_seconds = 1

    def __init__(self, mode="answer"):
        super().__init__()
        self.mode = mode
        self.release, self.finished = threading.Event(), threading.Event()

    def investigate(self, view):
        try:
            if self.mode == "hold":
                self.release.wait(30)
            else:
                time.sleep(0.15)
            if self.mode == "fail":
                raise InvestigatorError("provider_unavailable")
            return super().investigate(view)
        finally:
            self.finished.set()


def investigate_over_http(database_url, clock, monkeypatch, mode, direction):
    worker = Controlled(mode)
    h = Harness(database_url, clock, worker)
    token = h.service.create_session(ANALYST)[0]
    case = alerting_case(h, token, clock)
    if direction != "normal":
        skew_future_waits(monkeypatch, direction)
    started = time.monotonic()
    try:
        reply = h.call("POST", f"/v1/cases/{case['id']}/investigations", token,
                       {"expected_revision": 1})
        elapsed = time.monotonic() - started
    finally:
        worker.release.set()
    assert worker.finished.wait(5)
    assert reply.status_code == 200
    return h, token, case, reply.json(), elapsed


@pytest.mark.parametrize("direction", ["normal", "forward"])
def test_single_investigator_in_time_result_is_kept(database_url, clock, monkeypatch,
                                                    direction):
    """Forward: a 150 ms answer inside its 3 s deadline is not turned into a timeout."""
    _h, _t, _c, body, _e = investigate_over_http(database_url, clock, monkeypatch, "answer",
                                                 direction)
    assert body["case"]["state"] == "awaiting_approval", \
        body["agent_runs"][-1]["run"].get("failure_code")


@pytest.mark.parametrize("direction", ["normal", "backward"])
def test_single_investigator_deadline_is_monotonic(database_url, clock, monkeypatch,
                                                   direction):
    """Backward: a held worker still times out at budget + grace, not a second later."""
    h, token, case, body, elapsed = investigate_over_http(database_url, clock, monkeypatch,
                                                          "hold", direction)
    assert BUDGET_S - 0.1 <= elapsed < BUDGET_S + 0.5, f"deadline stretched to {elapsed:.3f}s"
    assert (body["case"]["state"], body["agent_runs"][-1]["run"]["failure_code"]) == (
        "open", "timeout")
    # The worker's late result (it returned in finally) was discarded: nothing changed.
    again = h.call("GET", f"/v1/cases/{case['id']}", token).json()
    assert (again["case"]["revision"], again["agent_runs"][-1]["run"]["status"]) == (
        body["case"]["revision"], "failed")


def test_single_investigator_error_keeps_its_code_under_forward_skew(database_url, clock,
                                                                     monkeypatch):
    _h, _t, _c, body, _e = investigate_over_http(database_url, clock, monkeypatch, "fail",
                                                 "forward")
    assert (body["case"]["state"], body["agent_runs"][-1]["run"]["failure_code"]) == (
        "open", "provider_unavailable")


# ---- three-role live adapter, through the real coordinator ----------------------------------

@pytest.fixture
def mono():
    return ac.Monotonic()


def live_analyst(mode, release):
    def work(_input):
        if mode == "hold":
            release.wait(30)
        else:
            time.sleep(0.15)

    def fail(_input):  # an in-budget provider failure, 150 ms in
        time.sleep(0.15)
        raise InvestigatorError("provider_unavailable")
    if mode == "fail":  # attempt 1 and its one allowed repeat
        return ac.FaultyRole("evidence_analyst", live=True, timeout_seconds=1,
                             behaviours=[("do", fail), ("do", fail)])
    return ac.FaultyRole("evidence_analyst", live=True, timeout_seconds=1,
                         behaviours=[("do", work)])


def investigate_live(database_url, clock, mono, monkeypatch, mode, direction):
    release = threading.Event()
    analyst = live_analyst(mode, release)
    url = ac.runtime_url(database_url)
    svc = ac.service(url, ac.workflow(evidence_analyst=analyst), clock, mono)
    ctx = svc.authenticate(ac.session(url, clock))
    case = ac.seed(svc, ctx, "D01", clock)["case"]
    if direction != "normal":
        skew_future_waits(monkeypatch, direction)
    started = time.monotonic()
    snapshots = {}
    try:
        detail = svc.investigate(ctx, case["id"], case["revision"])
        snapshots["after_wait"] = svc.capacity.snapshot()
        elapsed = time.monotonic() - started
    finally:
        release.set()
    assert analyst.returned.wait(5)
    return svc, ctx, case, detail, elapsed, snapshots


@pytest.mark.parametrize("direction", ["normal", "forward"])
def test_live_role_in_time_result_is_kept(database_url, clock, mono, monkeypatch, direction):
    """Forward: a 150 ms live role answer is used, not recorded as a timeout."""
    *_rest, detail, _elapsed, _snap = investigate_live(database_url, clock, mono, monkeypatch,
                                                       "answer", direction)
    assert detail["case"]["state"] == "awaiting_approval", \
        detail["agent_runs"][0]["run"].get("failure_code")


@pytest.mark.parametrize("direction", ["normal", "backward"])
def test_live_role_deadline_is_monotonic_and_keeps_the_worker_slot(database_url, clock, mono,
                                                                   monkeypatch, direction):
    """Backward: the held role times out at timeout + grace; its call slot stays held by the
    unreturned worker after the coordinator stops waiting, and is released only when it
    really returns. The late result is discarded."""
    svc, ctx, case, detail, elapsed, snapshots = investigate_live(
        database_url, clock, mono, monkeypatch, "hold", direction)
    assert BUDGET_S - 0.1 <= elapsed < BUDGET_S + 0.5, f"deadline stretched to {elapsed:.3f}s"
    assert (detail["case"]["state"], detail["agent_runs"][0]["run"]["failure_code"]) == (
        "open", "timeout")
    assert snapshots["after_wait"]["calls"] == 1  # still held by the running worker
    end = time.monotonic() + 5
    while svc.capacity.snapshot()["calls"] and time.monotonic() < end:
        threading.Event().wait(0.02)
    assert svc.capacity.snapshot()["calls"] == 0  # released at the worker's real return
    after = svc.get_case(ctx, case["id"])
    assert (after["case"]["revision"], len(after["agent_runs"])) == (
        detail["case"]["revision"], len(detail["agent_runs"]))


def test_live_role_error_keeps_its_code_under_forward_skew(database_url, clock, mono,
                                                           monkeypatch):
    *_rest, detail, _elapsed, _snap = investigate_live(database_url, clock, mono, monkeypatch,
                                                       "fail", "forward")
    failures = [r["run"]["failure_code"] for r in detail["agent_runs"]]
    assert detail["case"]["state"] == "open"
    assert failures and set(failures) == {"provider_unavailable"}
