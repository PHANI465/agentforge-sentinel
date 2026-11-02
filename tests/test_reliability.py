"""C05: safe diagnostics, request IDs, metrics, failure honesty, consistency and contention.

Labels: [regression] failed on accepted C01 2e6c232 before C05; [guard] already held and
must keep holding."""
import json
import logging
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import psycopg
import pytest
from fastapi.testclient import TestClient

from sentinel import db, service as service_module
from sentinel.api import create_app
from sentinel.contracts.v1 import ExecuteActionInput, InvestigationFinding, TransactionInput
from sentinel.investigators import DeterministicInvestigator
from sentinel.service import Sentinel, ServiceError
from test_thin_path import ANALYST, Harness, alerting_case, approve_pending, txn

CANARY = "SYNTHETIC-CANARY-c05-7731"
REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{7,63}$")


CLIENT_LOGGERS = ("httpx", "httpcore")  # the test client's own logs, not the server's


def all_log_text(caplog) -> str:
    out = []
    for record in caplog.records:
        if record.name.startswith(CLIENT_LOGGERS):
            continue
        out.append(record.getMessage())
        if record.exc_info:
            out.append(logging.Formatter().formatException(record.exc_info))
        out.extend(str(v) for v in record.__dict__.values())
    return "\n".join(out)


def http_events(caplog):
    return [json.loads(r.getMessage()) for r in caplog.records if r.name == "sentinel.http"]


# ---- request IDs, request logs, metrics ---------------------------------------------------

def test_request_id_and_one_safe_log_line_per_request(database_url, clock, caplog):  # [regression]
    caplog.set_level(logging.DEBUG)
    h = Harness(database_url, clock)
    token = h.service.create_session(ANALYST)[0]
    case = alerting_case(h, token, clock)
    caplog.clear()
    response = h.client.get(f"/v1/cases/{case['id']}?limit=1&debug={CANARY}",
                            headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    rid = response.headers["X-Request-ID"]
    assert REQUEST_ID.match(rid)
    (event,) = http_events(caplog)
    assert event == {"event": "http_request", "request_id": rid, "method": "GET",
                     "route": "/v1/cases/{case_id}", "status": 200,
                     "duration_ms": event["duration_ms"], "outcome": "ok"}
    text = all_log_text(caplog)
    assert token not in text and CANARY not in text and case["id"] not in text


@pytest.mark.parametrize("supplied, echoed", [
    ("client-trace-0001", True), ("short", False), ("has space inside", False),
    ("x" * 65, False), ("line\nbreak-injected", False), (CANARY + "<script>", False),
])
def test_client_request_id_is_echoed_only_when_safe(database_url, clock, supplied, echoed):  # [regression]
    h = Harness(database_url, clock)
    response = h.client.get("/healthz", headers={"X-Request-ID": supplied})
    rid = response.headers["X-Request-ID"]
    assert REQUEST_ID.match(rid)
    assert (rid == supplied) is echoed


def test_metrics_count_routes_statuses_and_latency(database_url, clock):  # [regression]
    h = Harness(database_url, clock)
    token = h.service.create_session(ANALYST)[0]
    h.call("GET", "/v1/overview", token)
    h.call("GET", "/v1/overview", token)
    h.call("GET", f"/v1/cases/{uuid.uuid4()}", token)
    h.client.get("/v1/nope")
    snapshot = h.client.app.state.metrics.snapshot()
    assert snapshot["requests"]["GET /v1/overview 200"] == 2
    assert snapshot["requests"]["GET /v1/cases/{case_id} 404"] == 1
    assert snapshot["requests"]["GET unmatched 404"] == 1
    assert sum(snapshot["latency_ms"]["GET /v1/overview"].values()) == 2
    assert all(CANARY not in key for key in snapshot["requests"])


# ---- unexpected failures: unchanged body, code-only logs ----------------------------------

def unexpected(database_url, clock, monkeypatch, method_name, error):
    h = Harness(database_url, clock)
    token = h.service.create_session(ANALYST)[0]

    def broken(*args, **kwargs):
        raise error

    monkeypatch.setattr(h.service, method_name, broken)
    return h, token


def test_unexpected_exception_is_contained_and_logged_by_type_only(
        database_url, clock, monkeypatch, caplog):  # [regression]
    caplog.set_level(logging.DEBUG)
    dsn = f"postgresql://user:{CANARY}@db.invalid:5432/sentinel"
    h, token = unexpected(database_url, clock, monkeypatch, "list_cases",
                          RuntimeError(f"storage failed for {dsn} token {CANARY}"))
    # raise_server_exceptions=True: the exception must not escape to the server layer,
    # where uvicorn would log its full traceback and message.
    client = TestClient(create_app(h.service), raise_server_exceptions=True)
    response = client.get(f"/v1/cases?debug={CANARY}",
                          headers={"Authorization": f"Bearer {token}", "X-Leak": CANARY})
    assert response.status_code == 500
    assert response.text == "Internal Server Error"  # frozen C01 behavior: not JSON
    assert response.headers["content-type"].startswith("text/plain")
    rid = response.headers["X-Request-ID"]
    (event,) = [e for e in http_events(caplog) if e["status"] == 500]
    assert event["outcome"] == "unexpected_error" and event["error_type"] == "RuntimeError"
    assert event["request_id"] == rid
    text = all_log_text(caplog)
    assert CANARY not in text and token not in text and "db.invalid" not in text


def test_response_validation_failure_is_contained(database_url, clock, monkeypatch,
                                                  caplog):  # [regression]
    caplog.set_level(logging.DEBUG)
    h, token = unexpected(database_url, clock, monkeypatch, "overview", RuntimeError("x"))
    monkeypatch.setattr(h.service, "overview",
                        lambda ctx: {"cases_by_state": {}, "secret": CANARY})
    client = TestClient(create_app(h.service), raise_server_exceptions=True)
    response = client.get("/v1/overview", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 500 and CANARY not in response.text
    (event,) = [e for e in http_events(caplog) if e["status"] == 500]
    assert event["error_type"] == "ResponseValidationError"
    assert CANARY not in all_log_text(caplog)


def test_database_outage_is_safe(database_url, clock, monkeypatch, caplog):  # [regression]
    caplog.set_level(logging.DEBUG)
    h = Harness(database_url, clock)
    token = h.service.create_session(ANALYST)[0]
    h.service.database_url = f"postgresql://sentinel:{CANARY}@127.0.0.1:1/none?connect_timeout=2"
    client = TestClient(create_app(h.service), raise_server_exceptions=True)
    response = client.get("/v1/overview", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 500
    (event,) = [e for e in http_events(caplog) if e["status"] == 500]
    assert event["error_type"] in {"OperationalError", "ConnectionTimeout"}
    assert CANARY not in all_log_text(caplog) and CANARY not in response.text


# ---- investigator faults, timeout and late results ----------------------------------------

class Exploding(DeterministicInvestigator):
    def investigate(self, view):
        raise RuntimeError(f"provider exploded with {CANARY}")


class Slow(DeterministicInvestigator):
    timeout_seconds = 1

    def __init__(self, seconds):
        super().__init__()
        self.seconds = seconds
        self.finished = threading.Event()

    def investigate(self, view):
        time.sleep(self.seconds)
        self.finished.set()
        return InvestigationFinding(operation="simulated_hold", reason_code="velocity_pattern",
                                    rationale="late")


def test_unexpected_investigator_exception_fails_the_run_honestly(
        database_url, clock, caplog):  # [regression]
    caplog.set_level(logging.DEBUG)
    h = Harness(database_url, clock, Exploding())
    token = h.service.create_session(ANALYST)[0]
    case = alerting_case(h, token, clock)
    response = h.call("POST", f"/v1/cases/{case['id']}/investigations", token,
                      {"expected_revision": 1})
    assert response.status_code == 200
    view = response.json()
    assert (view["case"]["state"], view["case"]["revision"]) == ("open", 3)
    assert view["agent_runs"][-1]["run"]["failure_code"] == "provider_unavailable"
    assert CANARY not in all_log_text(caplog)
    assert any(json.loads(r.getMessage()).get("error_type") == "RuntimeError"
               for r in caplog.records if r.name == "sentinel.service")


def test_investigator_timeout_is_enforced_and_late_result_discarded(database_url,
                                                                    clock):  # [regression]
    slow = Slow(seconds=6)
    h = Harness(database_url, clock, slow)
    token = h.service.create_session(ANALYST)[0]
    case = alerting_case(h, token, clock)
    started = time.monotonic()
    view = h.call("POST", f"/v1/cases/{case['id']}/investigations", token,
                  {"expected_revision": 1}).json()
    elapsed = time.monotonic() - started
    assert elapsed < 5.5  # budget 1 s + grace, not the investigator's 6 s
    assert view["agent_runs"][-1]["run"]["failure_code"] == "timeout"
    assert (view["case"]["state"], view["case"]["revision"]) == ("open", 3)
    assert slow.finished.wait(10)
    time.sleep(0.5)
    after = h.call("GET", f"/v1/cases/{case['id']}", token).json()
    assert after["case"]["revision"] == 3 and after["action_intents"] == []


# ---- rollback on injected database faults --------------------------------------------------

def test_ingest_fault_leaves_no_partial_rows(database_url, clock, monkeypatch):  # [guard]
    h = Harness(database_url, clock)
    token = h.service.create_session(ANALYST)[0]

    def fail(*args, **kwargs):
        raise psycopg.errors.QueryCanceled("injected")

    monkeypatch.setattr(Sentinel, "_evidence", staticmethod(fail))
    client = TestClient(create_app(h.service), raise_server_exceptions=False)
    response = client.post("/v1/transactions", json=txn(clock, "faulty", minor_units=250_000),
                           headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 500
    with db.connect(database_url) as conn:
        for table in ("transactions", "scoring_outcomes", "alerts", "cases", "audit_events"):
            assert conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"] == 0


def test_execute_fault_after_consumption_rolls_back(database_url, clock, monkeypatch):  # [guard]
    h = Harness(database_url, clock)
    token = h.service.create_session(ANALYST)[0]
    case = alerting_case(h, token, clock)
    h.call("POST", f"/v1/cases/{case['id']}/investigations", token, {"expected_revision": 1})
    approval = approve_pending(h, token, case["id"])
    real_audit = Sentinel._audit

    def audit(self, conn, ctx, case_, corr, actor, kind, event_type, *rest):
        if event_type == "action_succeeded":
            raise psycopg.errors.QueryCanceled("injected")
        return real_audit(self, conn, ctx, case_, corr, actor, kind, event_type, *rest)

    monkeypatch.setattr(Sentinel, "_audit", audit)
    ctx = h.service.authenticate(token)
    with pytest.raises(psycopg.errors.QueryCanceled):
        h.service.execute_action(ctx, ExecuteActionInput(approval_id=approval["id"],
                                                         idempotency_key=uuid.uuid4()))
    view = h.call("GET", f"/v1/cases/{case['id']}", token).json()
    assert view["case"]["state"] == "awaiting_approval"
    assert view["action_intents"][0]["approval"]["consumed_at"] is None
    assert view["action_intents"][0]["action"] is None


# ---- same-account contention ---------------------------------------------------------------

@pytest.mark.parametrize("coarse_clock", [False, True], ids=["native-clock", "tied-clock"])
def test_same_account_concurrent_ingestion_counts_exactly_prior_available(
        database_url, coarse_clock):  # [guard]
    # The first clock read per ingest happens under the account lock, before audit reads.
    # Its order identifies earlier committed decisions when timestamps repeat or go back.
    fixed = datetime.now(timezone.utc)
    current = threading.local()
    decisions = []

    def decision_clock():
        stamp = fixed if coarse_clock else datetime.now(timezone.utc)
        name = getattr(current, "external_id", None)
        if name is not None and not getattr(current, "recorded", False):
            decisions.append(name)
            current.recorded = True
        return stamp

    service = Sentinel(database_url, DeterministicInvestigator(), decision_clock)
    token, ctx = service.create_session(ANALYST)
    account = str(uuid.uuid4())
    base = datetime.now(timezone.utc) - timedelta(minutes=30)
    inputs = [TransactionInput.model_validate({
        "external_id": f"race-{i}", "account_id": account, "direction": "debit",
        "amount": {"currency": "USD", "minor_units": 1000 + i, "currency_exponent": 2},
        "occurred_at": (base + timedelta(minutes=i)).isoformat()}) for i in range(8)]
    barrier = threading.Barrier(len(inputs))

    def ingest(item):
        current.external_id = item.external_id
        current.recorded = False
        barrier.wait(10)
        return service.ingest(ctx, item)

    with ThreadPoolExecutor(len(inputs)) as pool:
        results = [f.result(timeout=60) for f in [pool.submit(ingest, i) for i in inputs]]
    rows = {r["transaction"]["external_id"]: r for r in results}
    assert len(decisions) == len(inputs) and set(decisions) == set(rows)
    decision_order = {name: index for index, name in enumerate(decisions)}
    if coarse_clock:
        assert len({row["transaction"]["ingested_at"] for row in results}) == 1
    for name, result in rows.items():
        own = result["transaction"]
        expected = sum(1 for other_name, other in rows.items()
                       if decision_order[other_name] < decision_order[name]
                       and other["transaction"]["occurred_at"] < own["occurred_at"]
                       and other["transaction"]["ingested_at"] <= own["ingested_at"])
        assert result["scoring"]["prior_count_1h"] == expected, name


def test_tied_ingestion_times_keep_committed_history_and_exclude_same_event_time(database_url):
    # An intentional arrival order distinguishes a committed equal-timestamp row from a
    # row that arrives later. Event time still uses the exclusive upper bound [t-1h, t).
    fixed = datetime.now(timezone.utc)
    service = Sentinel(database_url, DeterministicInvestigator(), lambda: fixed)
    _token, ctx = service.create_session(ANALYST)
    account = str(uuid.uuid4())
    inputs = [TransactionInput.model_validate({
        "external_id": f"tied-{index}", "account_id": account, "direction": "debit",
        "amount": {"currency": "USD", "minor_units": 1000, "currency_exponent": 2},
        "occurred_at": (fixed - timedelta(minutes=minutes)).isoformat()})
        for index, minutes in enumerate([10, 20, 10, 0])]
    results = [service.ingest(ctx, item) for item in inputs]
    assert len({row["transaction"]["ingested_at"] for row in results}) == 1
    assert [row["scoring"]["prior_count_1h"] for row in results] == [0, 0, 1, 3]
    # Later arrivals cannot change the first saved decision on an idempotent replay.
    replay = service.ingest(ctx, inputs[0])
    assert replay["replayed"] is True
    assert replay["scoring"] == results[0]["scoring"]


# ---- overview read consistency (C01 review follow-up) -------------------------------------

def test_overview_reads_one_consistent_snapshot(database_url, clock, monkeypatch):  # [regression]
    h = Harness(database_url, clock)
    token = h.service.create_session(ANALYST)[0]
    alerting_case(h, token, clock)
    ctx = h.service.authenticate(token)
    writer = Sentinel(database_url, DeterministicInvestigator(), clock)
    real_connect = service_module.db.connect
    state = {"armed": True}

    class Interleaving:
        """After the overview's first statement, another transaction commits a new alerting
        case before any further statement runs."""

        def __init__(self, conn):
            self.conn = conn

        def __enter__(self):
            self.conn.__enter__()
            return self

        def __exit__(self, *exc):
            return self.conn.__exit__(*exc)

        def __getattr__(self, name):
            return getattr(self.conn, name)

        def execute(self, *args, **kwargs):
            cursor = self.conn.execute(*args, **kwargs)
            if state["armed"]:
                state["armed"] = False
                rows = cursor.fetchall()
                writer.ingest(ctx, TransactionInput.model_validate(
                    txn(clock, "interleaved", minor_units=250_000)))
                return _Rows(rows)
            return cursor

    class _Rows:
        def __init__(self, rows):
            self.rows = rows

        def fetchone(self):
            return self.rows[0] if self.rows else None

        def fetchall(self):
            return self.rows

        def __iter__(self):
            return iter(self.rows)

    monkeypatch.setattr(service_module.db, "connect", lambda url: Interleaving(real_connect(url)))
    body = h.service.overview(ctx)
    monkeypatch.setattr(service_module.db, "connect", real_connect)
    assert sum(body["cases_by_state"].values()) == body["alerts"]
    final = h.service.overview(ctx)
    assert final["alerts"] == 2 and sum(final["cases_by_state"].values()) == 2


# ---- approval expiry is observable ----------------------------------------------------------

def test_approval_expiry_is_logged_safely_and_counted(database_url, clock, caplog):  # [regression]
    caplog.set_level(logging.DEBUG)
    h = Harness(database_url, clock)
    token = h.service.create_session(ANALYST)[0]
    case = alerting_case(h, token, clock)
    h.call("POST", f"/v1/cases/{case['id']}/investigations", token, {"expected_revision": 1})
    approval = approve_pending(h, token, case["id"])
    clock.advance(minutes=6)
    h.call("POST", "/v1/actions", token, {"approval_id": approval["id"],
                                          "idempotency_key": str(uuid.uuid4())})
    events = [json.loads(r.getMessage()) for r in caplog.records if r.name == "sentinel.service"]
    expired = [e for e in events if e["event"] == "approval_expired"]
    assert expired == [{"event": "approval_expired", "case_id": case["id"], "revision": 4}]
    assert h.client.app.state.metrics.snapshot()["events"]["approval_expired"] == 1
    assert token not in all_log_text(caplog)


def test_service_error_paths_still_typed(database_url, clock):  # [guard]
    h = Harness(database_url, clock)
    token = h.service.create_session(ANALYST)[0]
    with pytest.raises(ServiceError):
        h.service.get_case(h.service.authenticate(token), uuid.uuid4())
