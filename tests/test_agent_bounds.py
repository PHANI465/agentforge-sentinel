"""G3B review fixes R34-R36: finite client waits, the pre-submission budget recheck and the
pinned transition limit.

Unit cases use test-owned connection stand-ins that withhold their reply. Real cases run
against PostgreSQL through the production runtime role, with faults injected only through
hooks, the coordinator's clock, an owner connection, or a test-owned TCP relay that stops
forwarding server replies. Every test-owned thread and socket is released and joined.
"""
import socket
import sys
import threading
import time
from pathlib import Path

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict, make_conninfo

sys.path.insert(0, str(Path(__file__).resolve().parent / "support"))

import agent_cases as ac  # noqa: E402
from sentinel.agents import budget, coordinator  # noqa: E402
from sentinel.contracts.agents import WorkflowLimits  # noqa: E402
from sentinel.investigators import DeterministicInvestigator  # noqa: E402
from sentinel.service import ServiceError  # noqa: E402


@pytest.fixture
def url(database_url):
    return ac.runtime_url(database_url)


@pytest.fixture
def mono():
    return ac.Monotonic()


def code_of(call):
    with pytest.raises(ServiceError) as raised:
        call()
    return raised.value.code


def until(condition, seconds=10.0):
    """Wait for a condition on test-owned state, checking every 20 ms, for a bounded time."""
    end = time.monotonic() + seconds
    while not condition():
        if time.monotonic() > end:
            return False
        threading.Event().wait(0.02)
    return True


def current_intent(detail):
    return [i for i in detail["action_intents"]
            if i["intent"]["case_revision"] == detail["case"]["revision"]]


# ---- R34: no reply within the budget (stand-ins) -------------------------------------------

class Silent:
    """A connection whose next commit/execute withholds its reply until released."""
    broken = closed = False

    def __init__(self, stall: str, cancel_reply: str = "ack"):
        self.stall, self.cancel_reply = stall, cancel_reply
        self.release, self.cancelled, self.closed_by = (threading.Event(), threading.Event(),
                                                        threading.Event())
        self.sql = []

    def _wait(self):
        self.release.wait(30)
        raise psycopg.OperationalError("test-owned unanswered operation")

    def execute(self, query, params=()):
        self.sql.append(query)
        if self.stall == "statement" and "set_config" not in query:
            self._wait()

    def commit(self):
        self.sql.append("COMMIT")
        if self.stall == "commit":
            self._wait()

    def rollback(self):
        self.sql.append("ROLLBACK")

    def cancel_safe(self, timeout):
        self.cancelled.set()
        if self.cancel_reply == "failure":
            raise OSError("test-owned failed cancellation")
        if self.cancel_reply == "unfinished":  # the cancel request itself gets no answer
            self.release.wait(timeout)

    def close(self):
        self.closed = True
        self.closed_by.set()


def silent_transaction(conn, budget_ms=1000):
    deadline = budget.Deadline(WorkflowLimits(), total_ms=budget_ms + 4000, reserve_ms=0)
    return budget.BoundedTransaction(conn, deadline, "terminal", budget_ms)


@pytest.mark.parametrize("cancel_reply", ["failure", "ack", "unfinished"])
def test_commit_without_a_reply_ends_at_its_budget(cancel_reply):
    conn = Silent("commit", cancel_reply)
    tx = silent_transaction(conn)
    started = time.monotonic()
    try:
        with pytest.raises(budget.CommitUncertain):  # never a known rollback or success
            tx.commit()
        elapsed = time.monotonic() - started
        assert conn.cancelled.is_set()  # the cancel request went out inside the budget ...
        if cancel_reply == "unfinished":  # ... and the wait ended at the budget, or ...
            assert 0.95 <= elapsed < 1.2
        else:  # ... shortly after a completed cancel request (sent at half this budget)
            assert 0.5 <= elapsed < 0.5 + budget.COMMIT_CANCEL_REPLY_MS / 1000 + 0.15
        assert not conn.release.is_set() and budget.QUARANTINE.holds(conn)
        assert not conn.closed_by.is_set()  # nobody closes it under the blocked call
    finally:
        conn.release.set()
    assert conn.closed_by.wait(5)  # the operation thread owns, then closes, the connection
    assert until(lambda: not budget.QUARANTINE.holds(conn))


def test_statement_without_a_reply_is_budget_exhausted_and_quarantined():
    conn = Silent("statement")
    tx = silent_transaction(conn)
    started = time.monotonic()
    try:
        with pytest.raises(budget.BudgetExhausted):  # COMMIT was never sent
            tx.execute("SELECT 1")
        assert time.monotonic() - started < 1.2
        assert budget.QUARANTINE.holds(conn) and not budget.usable(conn)
        tx.rollback()  # nothing more is sent on a quarantined connection
        assert "COMMIT" not in conn.sql and "ROLLBACK" not in conn.sql
    finally:
        conn.release.set()
    assert conn.closed_by.wait(5)
    assert until(lambda: not budget.QUARANTINE.holds(conn))


def test_rollback_without_time_closes_instead_of_waiting():
    clock = {"now": 0.0}
    deadline = budget.Deadline(WorkflowLimits(), lambda: clock["now"], total_ms=5000,
                               reserve_ms=0)
    conn = Silent("none")
    tx = budget.BoundedTransaction(conn, deadline, "terminal", 5000)
    clock["now"] = 5000.0  # the phase is over: no wait at all is allowed
    tx.rollback()
    assert "ROLLBACK" not in conn.sql and conn.closed_by.is_set()


# ---- R34: real PostgreSQL behind a relay that withholds replies -----------------------------

class StallingRelay:
    """A test-owned TCP relay to the test server. withhold() stops forwarding server
    replies on the connections open now; withhold_from_commit() does so from the next
    COMMIT a client sends. Requests still reach the server, connections made later are
    relayed normally, and closing either side closes the pair."""

    def __init__(self, target_url: str):
        params = conninfo_to_dict(target_url)
        host, port = params.get("host") or "127.0.0.1", int(params.get("port") or 5432)
        self.target = (host, port)
        self.listener = socket.create_server(("127.0.0.1", 0))
        self.port = self.listener.getsockname()[1]
        self.pairs, self.threads, self.lock = [], [], threading.Lock()
        self.stopped = False
        self._spawn(self._accept)

    def _spawn(self, target, *args):
        thread = threading.Thread(target=target, args=args, daemon=True)
        with self.lock:
            self.threads.append(thread)
        thread.start()

    def _upstream(self):
        host, port = self.target
        if host.startswith("/"):
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(f"{host}/.s.PGSQL.{port}")
            return sock
        return socket.create_connection((host, port))

    def _accept(self):
        while not self.stopped:
            try:
                client, _ = self.listener.accept()
            except OSError:
                return
            server = self._upstream()
            pair = {"client": client, "server": server, "withheld": False,
                    "from_commit": False}
            with self.lock:
                self.pairs.append(pair)
            self._spawn(self._pump, pair, client, server, False)
            self._spawn(self._pump, pair, server, client, True)

    def _pump(self, pair, source, sink, replies):
        try:
            while True:
                data = source.recv(65536)
                if not data:
                    break
                if not replies and pair["from_commit"] and b"COMMIT" in data:
                    pair["withheld"] = True
                if replies and pair["withheld"]:
                    continue
                sink.sendall(data)
        except OSError:
            pass
        finally:
            _end(pair["client"], pair["server"])

    def withhold(self):
        with self.lock:
            for pair in self.pairs:
                pair["withheld"] = True

    def withhold_from_commit(self):
        with self.lock:
            for pair in self.pairs:
                pair["from_commit"] = True

    def url(self, runtime_url: str) -> str:
        return make_conninfo(runtime_url, host="127.0.0.1", port=str(self.port),
                             sslmode="disable", gssencmode="disable")

    def close(self):
        self.stopped = True
        _end(self.listener)
        with self.lock:
            pairs, threads = list(self.pairs), list(self.threads)
        for pair in pairs:
            _end(pair["client"], pair["server"])
        for thread in threads:
            thread.join(5)
        assert not any(t.is_alive() for t in threads)


def _end(*socks):
    """Shut down, then close: on Linux, close() alone does not wake a thread blocked in
    recv() or accept() on the same socket."""
    for sock in socks:
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            sock.close()
        except OSError:
            pass


@pytest.fixture
def relay(database_url):
    relay = StallingRelay(database_url)
    try:
        yield relay
    finally:
        relay.close()


def relayed(url, relay, clock, mono, **roles):
    svc = ac.service(relay.url(url), ac.workflow(**roles), clock, mono)
    return svc, svc.authenticate(ac.session(url, clock))


def to_remaining(mono, ms):
    def hook(run):
        mono.advance(run.deadline.deadline_ms - ms - mono())
    return hook


def test_withheld_terminal_commit_reply_is_unknown_within_the_budget(url, relay, clock,
                                                                       mono):
    svc, ctx = relayed(url, relay, clock, mono)
    case = ac.seed(svc, ctx, "D01", clock)["case"]["id"]
    timing = {}

    def withhold(_run):
        relay.withhold_from_commit()
        timing["sent"] = time.monotonic()
    hooks = {"before_terminal": to_remaining(mono, 2000), "before_terminal_commit": withhold}
    assert code_of(lambda: coordinator.run_workflow(svc, ctx, case, 1, hooks)) == \
        "investigation_outcome_unknown"
    assert time.monotonic() - timing["sent"] < 2.5  # the 2 s terminal budget, no reply
    assert svc.capacity.snapshot()["workflows"] == 0
    # The shut-down socket ends the abandoned operation; its thread closes the connection.
    assert until(lambda: budget.QUARANTINE.count() == 0)
    # Only the reply was lost: the server committed, which a client re-read now shows.
    direct = ac.service(url, ac.workflow(), clock, mono)
    detail = direct.get_case(ctx, case)
    assert detail["case"]["state"] == "awaiting_approval" and current_intent(detail)


def test_withheld_statement_reply_replaces_the_quarantined_connection(url, relay, clock,
                                                                        mono):
    investigator = ac.FaultyRole("investigator")
    svc, ctx = relayed(url, relay, clock, mono, investigator=investigator)
    case = ac.seed(svc, ctx, "D01", clock)["case"]["id"]
    seen = {}

    def withhold(run):
        seen["conn"] = run.conn
        relay.withhold()
    started = time.monotonic()
    detail = coordinator.run_workflow(svc, ctx, case, 1,
                                      {"before_role:investigator": withhold})
    assert time.monotonic() - started < 15  # one 5 s statement wait, then the terminal
    assert detail["case"]["state"] == "open" and not current_intent(detail)
    assert investigator.calls == 0  # its start record never committed, so no submission
    (record,) = ac.workflows(url, case)
    assert (record["disposition"]["inconclusive_code"], record["terminal_by"]) == (
        "budget_exhausted", "coordinator")
    assert [r["run"]["role"] for r in detail["agent_runs"]] == ["evidence_analyst"]
    assert until(lambda: budget.QUARANTINE.count() == 0)
    assert seen["conn"].closed  # closed by its operation thread, never reused


def test_quarantined_operations_refuse_new_workflows(url, clock, mono):
    svc = ac.service(url, ac.workflow(), clock, mono)
    ctx = svc.authenticate(ac.session(url, clock))
    case = ac.seed(svc, ctx, "D01", clock)["case"]["id"]
    held = Silent("none")
    budget.QUARANTINE.hold(held)
    try:
        assert code_of(lambda: svc.investigate(ctx, case, 1)) == "agent_capacity_exhausted"
        assert svc.get_case(ctx, case)["case"]["state"] == "open"
        assert ac.workflows(url, case) == []
    finally:
        budget.QUARANTINE.release(held)
    assert svc.investigate(ctx, case, 1)["case"]["state"] == "awaiting_approval"


@pytest.fixture
def slower_commit(database_url):
    """A deferred trigger sleeping longer than the recovery's 5 s budget."""
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("CREATE FUNCTION g3b_slower_commit() RETURNS trigger LANGUAGE plpgsql"
                     " AS $$ BEGIN PERFORM pg_sleep(8); RETURN NULL; END; $$")
        conn.execute("CREATE CONSTRAINT TRIGGER g3b_slower_commit AFTER UPDATE ON"
                     " agent_workflows DEFERRABLE INITIALLY DEFERRED FOR EACH ROW"
                     " EXECUTE FUNCTION g3b_slower_commit()")

    def drop():
        with psycopg.connect(database_url, autocommit=True) as conn:
            conn.execute("DROP TRIGGER IF EXISTS g3b_slower_commit ON agent_workflows")
            conn.execute("DROP FUNCTION IF EXISTS g3b_slower_commit()")
    try:
        yield drop
    finally:
        drop()


def test_recovery_outside_the_coordinator_commits_with_its_own_bound(url, clock, mono,
                                                                       slower_commit):
    def die(_run):
        raise ac.SimulatedProcessDeath()
    svc = ac.service(url, ac.workflow(), clock, mono)
    ctx = svc.authenticate(ac.session(url, clock))
    case = ac.seed(svc, ctx, "D14", clock)["case"]["id"]
    with pytest.raises(ac.SimulatedProcessDeath):
        coordinator.run_workflow(svc, ctx, case, 1, {"before_role:investigator": die})
    clock.advance(seconds=181)
    single = ac.service(url, DeterministicInvestigator(), clock, mono)  # begin_investigation
    started = time.monotonic()
    assert code_of(lambda: single.investigate(ctx, case, 2)) == "investigation_in_progress"
    assert time.monotonic() - started < 7  # the 5 s recovery budget; COMMIT was cancelled
    assert ac.workflows(url, case)[0]["status"] == "running"  # a known rollback
    slower_commit()
    assert code_of(lambda: single.investigate(ctx, case, 2)) == "investigation_recovered"
    (record,) = ac.workflows(url, case)
    assert (record["terminal_by"], record["disposition"]["inconclusive_code"]) == (
        "recovery", "interrupted")
    assert single.get_case(ctx, case)["case"]["state"] == "open"


# ---- R35: the full call must still fit when it is actually submitted ------------------------

CALL_MS = (45 + WorkflowLimits().role_grace_seconds) * 1000


@pytest.mark.parametrize("spent_ms, submitted", [(3000, False), (500, True)])
def test_role_start_persistence_is_rechecked_before_submission(database_url, url, clock, mono,
                                                                spent_ms, submitted):
    """Before the start record, CALL_MS + 1 s of working time is left (the first check
    passes). Writing the record then waits on a case lock while `spent_ms` passes."""
    analyst = ac.FaultyRole("evidence_analyst", live=True, timeout_seconds=45)
    svc = ac.service(url, ac.workflow(evidence_analyst=analyst), clock, mono)
    ctx = svc.authenticate(ac.session(url, clock))
    case = ac.seed(svc, ctx, "D01", clock)["case"]["id"]
    gate = {}

    def block_start_record(run):
        mono.advance(run.deadline.available_ms("working") - (CALL_MS + 1000))
        blocker = psycopg.connect(database_url)
        blocker.execute("SELECT 1 FROM cases WHERE id = %s FOR UPDATE", (run.record.case_id,))
        pid = run.conn.info.backend_pid

        def release():
            try:
                with psycopg.connect(database_url, autocommit=True) as watcher:
                    gate["waited"] = until(lambda: watcher.execute(
                        "SELECT wait_event_type FROM pg_stat_activity WHERE pid = %s",
                        (pid,)).fetchone()[0] == "Lock")
                mono.advance(spent_ms)  # the persistence wait, on the coordinator's clock
            finally:
                blocker.commit()
                blocker.close()
        gate["thread"] = threading.Thread(target=release)
        gate["thread"].start()
    try:
        detail = coordinator.run_workflow(svc, ctx, case, 1,
                                          {"before_role:evidence_analyst": block_start_record})
    finally:
        gate["thread"].join(10)
    assert gate["waited"] and not gate["thread"].is_alive()
    assert until(lambda: svc.capacity.snapshot()["calls"] == 0)
    if submitted:  # the full call still fitted after the write: one ordinary call
        assert analyst.calls == 1
        assert detail["agent_runs"][0]["run"]["status"] == "completed"
        return
    assert analyst.calls == 0  # no provider call without its full call budget
    assert svc.capacity.snapshot() == {"workflows": 0, "calls": 0, "peak_calls": 1}
    assert detail["case"]["state"] == "open" and not current_intent(detail)
    (run,) = detail["agent_runs"]  # the recorded attempt, honestly failed
    assert (run["run"]["role"], run["run"]["status"], run["run"]["failure_code"]) == (
        "evidence_analyst", "failed", "budget_exhausted")
    failed = [s for s in ac.steps(url, case) if s["kind"] == "role_failed"]
    assert [(s["failure_code"], s["worker_unresolved"], s["usage"]["source"])
            for s in failed] == [("budget_exhausted", False, "not_applicable")]
    (record,) = ac.workflows(url, case)
    assert record["disposition"]["inconclusive_code"] == "budget_exhausted"


# ---- R36: the pinned transition limit ------------------------------------------------------

def limited(url, clock, mono, max_transitions=None, **roles):
    base = ac.workflow(**roles)
    limits = base.limits if max_transitions is None else base.limits.model_copy(
        update={"max_transitions": max_transitions})
    svc = ac.service(url, coordinator.Workflow(base.adapters, limits), clock, mono)
    return svc, svc.authenticate(ac.session(url, clock))


def transitions(url, case):
    return [s["state"] for s in ac.steps(url, case) if s["kind"] == "transition"]


DEFAULT_PATH = ["gathering", "analyst", "analyst_tools", "investigator", "verifying",
                "reviewer"]


def test_default_path_records_each_transition(url, clock, mono):
    svc, ctx = limited(url, clock, mono)
    case = ac.seed(svc, ctx, "D01", clock)["case"]["id"]
    assert svc.investigate(ctx, case, 1)["case"]["state"] == "awaiting_approval"
    assert transitions(url, case) == DEFAULT_PATH
    assert ac.steps(url, case)[-1]["state"] == "done"  # the terminal step, never counted


def test_a_small_transition_limit_ends_before_any_role(url, clock, mono):
    svc, ctx = limited(url, clock, mono, max_transitions=1)
    case = ac.seed(svc, ctx, "D01", clock)["case"]["id"]
    detail = svc.investigate(ctx, case, 1)
    assert detail["case"]["state"] == "open" and detail["agent_runs"] == []
    assert not current_intent(detail)
    assert transitions(url, case) == ["gathering"]
    (record,) = ac.workflows(url, case)
    assert (record["disposition"]["inconclusive_code"], record["tool_calls"],
            record["terminal_by"]) == ("budget_exhausted", 3, "coordinator")


@pytest.mark.parametrize("spare", [0, -1])
def test_an_exactly_fitting_limit_completes_and_one_less_stops(url, clock, mono, spare):
    svc, ctx = limited(url, clock, mono, max_transitions=len(DEFAULT_PATH) + spare)
    case = ac.seed(svc, ctx, "D01", clock)["case"]["id"]
    detail = svc.investigate(ctx, case, 1)
    roles = [r["run"]["role"] for r in detail["agent_runs"]]
    if spare == 0:
        assert detail["case"]["state"] == "awaiting_approval" and current_intent(detail)
        assert transitions(url, case) == DEFAULT_PATH
        return
    assert detail["case"]["state"] == "open" and not current_intent(detail)
    assert transitions(url, case) == DEFAULT_PATH[:-1]
    assert roles == ["evidence_analyst", "investigator"]  # the reviewer never started
    assert ac.workflows(url, case)[0]["disposition"]["inconclusive_code"] == "budget_exhausted"


def wrong_count(role_input, output):  # as in the D05 workflow test
    cite = next(f["cite"] for f in role_input["facts"] if f["fact"] == "transaction_count_1h")
    return {**output, "operation": "escalate", "reason_code": "velocity_pattern",
            "claims": [{"kind": "fact", "fact": "transaction_count_1h", "relation": "eq",
                        "value": 5, "cite": cite}]}


def test_a_revision_counts_its_transitions(url, clock, mono):
    investigator = ac.FaultyRole("investigator", behaviours=[("map", wrong_count)] * 2)
    revision_path = DEFAULT_PATH + ["investigator", "verifying", "reviewer"]
    svc, ctx = limited(url, clock, mono, investigator=investigator)
    case = ac.seed(svc, ctx, "D05", clock)["case"]["id"]
    assert svc.investigate(ctx, case, 1)["case"]["state"] == "awaiting_approval"
    assert transitions(url, case) == revision_path and len(revision_path) <= 12
    investigator = ac.FaultyRole("investigator", behaviours=[("map", wrong_count)] * 2)
    svc, ctx = limited(url, clock, mono, max_transitions=len(revision_path) - 1,
                       investigator=investigator)
    case = ac.seed(svc, ctx, "D05", clock, prefix="d05-limited")["case"]["id"]
    detail = svc.investigate(ctx, case, 1)
    assert detail["case"]["state"] == "open" and not current_intent(detail)
    assert [r["run"]["role"] for r in detail["agent_runs"]] == [
        "evidence_analyst", "investigator", "reviewer", "investigator"]


def test_a_repeat_stays_in_its_state(url, clock, mono):
    investigator = ac.FaultyRole("investigator", behaviours=[("fail", "provider_unavailable")])
    svc, ctx = limited(url, clock, mono, max_transitions=len(DEFAULT_PATH),
                       investigator=investigator)
    case = ac.seed(svc, ctx, "D07", clock)["case"]["id"]
    detail = svc.investigate(ctx, case, 1)
    assert detail["case"]["state"] == "awaiting_approval"
    assert investigator.calls == 2 and transitions(url, case) == DEFAULT_PATH
