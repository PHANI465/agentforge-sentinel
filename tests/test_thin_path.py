"""Integrated path against real Postgres: ingest -> score -> case -> investigate -> approve ->
simulated action -> audit, including restarts, isolation, races and denials."""
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import psycopg
import pytest
from fastapi.testclient import TestClient

from sentinel import db
from sentinel.api import create_app
from sentinel.contracts.v1 import ExecuteActionInput, InvestigationFinding
from sentinel.investigators import DeterministicInvestigator, InvestigatorError
from sentinel.service import Sentinel, ServiceError

ANALYST = frozenset({"ingest_transaction", "read_case", "approve_action",
                     "execute_simulated_action"})
ACCOUNT = "00000000-0000-4000-8000-0000000000a1"


def txn(clock, external_id, minor_units=1500, minutes_ago=0):
    occurred = clock() - timedelta(minutes=minutes_ago)
    return {"external_id": external_id, "account_id": ACCOUNT, "direction": "debit",
            "amount": {"currency": "USD", "minor_units": minor_units, "currency_exponent": 2},
            "occurred_at": occurred.isoformat()}


class Harness:
    """A 'process': its own service, app and client. Recreate it to simulate a restart."""

    def __init__(self, database_url, clock, investigator=None):
        self.service = Sentinel(database_url, investigator or DeterministicInvestigator(), clock)
        self.client = TestClient(create_app(self.service))

    def call(self, method, path, token, json=None):
        return self.client.request(method, path, json=json,
                                   headers={"Authorization": f"Bearer {token}"})


@pytest.fixture
def harness(database_url, clock):
    return Harness(database_url, clock)


@pytest.fixture
def token(harness):
    return harness.service.create_session(ANALYST)[0]


def alerting_case(h, token, clock):
    """Three prior small transactions, then a large one: velocity + amount -> alert."""
    for i in range(3):
        response = h.call("POST", "/v1/transactions", token, txn(clock, f"prior-{i}",
                                                                  minutes_ago=30 - i))
        assert response.status_code == 201 and response.json()["alert"] is None
    response = h.call("POST", "/v1/transactions", token, txn(clock, "big", minor_units=250_000))
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["alert"]["scoring_kind"] == "rule"
    assert body["alert"]["score_semantics"] == "heuristic"
    return body["case"]


def approve_pending(h, token, case_id):
    view = h.call("GET", f"/v1/cases/{case_id}", token).json()
    intent = view["action_intents"][-1]["intent"]
    response = h.call("POST", "/v1/approvals", token,
                      {"action_intent_id": intent["id"], "decision": "approved"})
    assert response.status_code == 201, response.text
    return response.json()


def audit_types(h, token, case_id):
    return [(e["event_type"], e["outcome"], e["case_revision"])
            for e in h.call("GET", f"/v1/cases/{case_id}/audit", token).json()]


def test_full_path_with_restart_between_every_step(database_url, clock):
    h = Harness(database_url, clock)
    token = h.service.create_session(ANALYST)[0]
    case = alerting_case(h, token, clock)
    assert (case["state"], case["revision"]) == ("open", 1)

    clock.advance(seconds=5)
    h = Harness(database_url, clock)  # restart
    response = h.call("POST", f"/v1/cases/{case['id']}/investigations", token,
                      {"expected_revision": 1})
    assert response.status_code == 200, response.text
    view = response.json()
    assert (view["case"]["state"], view["case"]["revision"]) == ("awaiting_approval", 3)
    assert view["agent_runs"][0]["run"]["status"] == "completed"
    assert view["agent_runs"][0]["finding"]["operation"] == "simulated_hold"
    params = view["action_intents"][0]["intent"]["parameters"]
    # The server, not the investigator, fills the target and amount from stored records.
    assert params["transaction_id"] == view["transaction"]["id"]
    assert params["amount"]["minor_units"] == 250_000

    clock.advance(seconds=5)
    h = Harness(database_url, clock)  # restart
    approval = approve_pending(h, token, case["id"])

    clock.advance(seconds=5)
    h = Harness(database_url, clock)  # restart
    key = str(uuid.uuid4())
    first = h.call("POST", "/v1/actions", token, {"approval_id": approval["id"],
                                                  "idempotency_key": key})
    assert first.status_code == 200, first.text
    assert first.json()["replayed"] is False
    assert first.json()["action"]["mode"] == "simulated"

    h = Harness(database_url, clock)  # restart, then client retry with the same key
    retry = h.call("POST", "/v1/actions", token, {"approval_id": approval["id"],
                                                  "idempotency_key": key})
    assert retry.status_code == 200
    assert retry.json() == {**first.json(), "replayed": True}

    final = h.call("GET", f"/v1/cases/{case['id']}", token).json()
    assert (final["case"]["state"], final["case"]["revision"]) == ("closed", 4)
    assert final["action_intents"][0]["approval"]["consumed_at"] is not None
    assert audit_types(h, token, case["id"]) == [
        ("transaction_received", "success", 1), ("alert_raised", "success", 1),
        ("investigation_started", "success", 2), ("investigation_completed", "success", 3),
        ("approval_recorded", "success", 3), ("action_succeeded", "success", 4),
    ]


def test_below_threshold_transaction_creates_no_case(harness, token, clock):
    response = harness.call("POST", "/v1/transactions", token, txn(clock, "small"))
    assert response.status_code == 201
    assert response.json()["alert"] is None and response.json()["case"] is None


def test_ingestion_is_idempotent_per_external_id(harness, token, clock):
    payload = txn(clock, "dup", minor_units=250_000)
    first = harness.call("POST", "/v1/transactions", token, payload)
    again = harness.call("POST", "/v1/transactions", token, payload)
    assert again.json()["replayed"] is True
    assert again.json()["transaction"]["id"] == first.json()["transaction"]["id"]
    changed = harness.call("POST", "/v1/transactions", token, {**payload, "direction": "credit"})
    assert (changed.status_code, changed.json()) == (409, {"error": "idempotency_conflict"})


def test_future_transaction_is_rejected(harness, token, clock):
    response = harness.call("POST", "/v1/transactions", token, txn(clock, "f", minutes_ago=-5))
    assert (response.status_code, response.json()) == (422, {"error": "future_event_time"})


def test_authentication_and_safe_errors(harness, token, clock):
    assert harness.call("GET", f"/v1/cases/{uuid.uuid4()}", "wrong").status_code == 401
    assert harness.client.get(f"/v1/cases/{uuid.uuid4()}").status_code == 401
    canary = "DUMMY_SECRET_NOT_REAL_7731"
    response = harness.call("POST", "/v1/transactions", token,
                            {**txn(clock, "x"), "api_key": canary, "tenant_id": canary})
    assert response.status_code == 422
    assert canary not in response.text and "api_key" not in response.text
    assert response.json()["details"][0] == {"code": "extra_forbidden"}


def test_other_session_cannot_see_or_act(database_url, clock):
    h = Harness(database_url, clock)
    owner = h.service.create_session(ANALYST)[0]
    case = alerting_case(h, owner, clock)
    h.call("POST", f"/v1/cases/{case['id']}/investigations", owner, {"expected_revision": 1})
    view = h.call("GET", f"/v1/cases/{case['id']}", owner).json()
    intent_id = view["action_intents"][0]["intent"]["id"]

    # Same tenant, different session: still invisible.
    tenant = uuid.UUID(case["scope"]["tenant_id"])
    other = h.service.create_session(ANALYST, tenant_id=tenant)[0]
    for method, path, body in (
        ("GET", f"/v1/cases/{case['id']}", None),
        ("GET", f"/v1/cases/{case['id']}/audit", None),
        ("POST", f"/v1/cases/{case['id']}/investigations", {"expected_revision": 3}),
        ("POST", "/v1/approvals", {"action_intent_id": intent_id, "decision": "approved"}),
    ):
        response = h.call(method, path, other, body)
        assert (response.status_code, response.json()) == (404, {"error": "not_found"})

    approval = approve_pending(h, owner, case["id"])
    response = h.call("POST", "/v1/actions", other, {"approval_id": approval["id"],
                                                     "idempotency_key": str(uuid.uuid4())})
    assert response.status_code == 404


def test_stale_revision_and_wrong_state_are_rejected(harness, token, clock):
    case = alerting_case(harness, token, clock)
    path = f"/v1/cases/{case['id']}/investigations"
    assert harness.call("POST", path, token, {"expected_revision": 2}).json() == {
        "error": "stale_case_revision"}
    assert harness.call("POST", path, token, {"expected_revision": 1}).status_code == 200
    assert harness.call("POST", path, token, {"expected_revision": 3}).json() == {
        "error": "case_not_investigable"}


def run_concurrently(fn, arg_lists, timeout=30):
    """Start all callers together; every caller must finish in time with a result. Unexpected
    exceptions are re-raised and stuck callers fail the test (R7)."""
    barrier = threading.Barrier(len(arg_lists))

    def call(args):
        barrier.wait(timeout)
        return fn(*args)

    pool = ThreadPoolExecutor(len(arg_lists))
    try:
        futures = [pool.submit(call, args) for args in arg_lists]
        return [future.result(timeout=timeout) for future in futures]
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def test_run_concurrently_reraises_unexpected_errors():
    def fn(n):
        if n == 2:
            raise RuntimeError("unexpected")
        return n
    with pytest.raises(RuntimeError):
        run_concurrently(fn, [(0,), (1,), (2,), (3,)], timeout=5)


def test_run_concurrently_fails_on_stuck_caller():
    release = threading.Event()
    try:
        with pytest.raises(TimeoutError):
            run_concurrently(lambda n: n if n else release.wait(30), [(0,), (1,)], timeout=0.5)
    finally:
        release.set()


def test_concurrent_execution_consumes_approval_once(database_url, clock):
    h = Harness(database_url, clock)
    token = h.service.create_session(ANALYST)[0]
    case = alerting_case(h, token, clock)
    h.call("POST", f"/v1/cases/{case['id']}/investigations", token, {"expected_revision": 1})
    approval = approve_pending(h, token, case["id"])
    ctx = h.service.authenticate(token)

    def attempt(key):
        try:
            out = h.service.execute_action(ctx, ExecuteActionInput(
                approval_id=approval["id"], idempotency_key=key))
            return ("ok", out["action"]["id"])
        except ServiceError as error:  # only expected, typed denials are tolerated
            return (error.code, None)

    shared = uuid.uuid4()
    keys = [shared, shared, uuid.uuid4(), uuid.uuid4()]
    results = run_concurrently(attempt, [(key,) for key in keys])
    assert len(results) == len(keys)
    with db.connect(database_url) as conn:
        row = conn.execute("SELECT id, idempotency_key FROM simulated_actions").fetchall()
    assert len(row) == 1
    action_id, winning_key = str(row[0]["id"]), row[0]["idempotency_key"]
    for key, outcome in zip(keys, results):
        # The winning key (performed or replayed) returns the one action; others are denied.
        expected = ("ok", action_id) if key == winning_key else ("approval_not_available", None)
        assert outcome == expected, (key == shared, outcome)
    assert audit_types(h, token, case["id"]).count(("action_succeeded", "success", 4)) == 1


def test_idempotency_key_reuse_for_another_approval_conflicts(database_url, clock):
    h = Harness(database_url, clock)
    token = h.service.create_session(ANALYST)[0]
    key = str(uuid.uuid4())
    approvals = []
    for prefix in ("a", "b"):
        for i in range(3):
            h.call("POST", "/v1/transactions", token, txn(clock, f"{prefix}{i}", minutes_ago=9 - i))
        case = h.call("POST", "/v1/transactions", token,
                      txn(clock, f"{prefix}-big", minor_units=250_000)).json()["case"]
        h.call("POST", f"/v1/cases/{case['id']}/investigations", token, {"expected_revision": 1})
        approvals.append(approve_pending(h, token, case["id"]))
    first = h.call("POST", "/v1/actions", token, {"approval_id": approvals[0]["id"],
                                                  "idempotency_key": key})
    assert first.status_code == 200
    reused = h.call("POST", "/v1/actions", token, {"approval_id": approvals[1]["id"],
                                                   "idempotency_key": key})
    assert (reused.status_code, reused.json()) == (409, {"error": "idempotency_conflict"})


def test_expired_approval_is_denied_and_audited(harness, token, clock):
    case = alerting_case(harness, token, clock)
    harness.call("POST", f"/v1/cases/{case['id']}/investigations", token,
                 {"expected_revision": 1})
    approval = approve_pending(harness, token, case["id"])
    clock.advance(minutes=6)
    response = harness.call("POST", "/v1/actions", token, {"approval_id": approval["id"],
                                                           "idempotency_key": str(uuid.uuid4())})
    assert (response.status_code, response.json()) == (409, {"error": "approval_outside_validity"})
    assert audit_types(harness, token, case["id"])[-2:] == [
        ("action_denied", "denied", 3), ("approval_expired", "success", 4)]
    view = harness.call("GET", f"/v1/cases/{case['id']}", token).json()
    assert view["action_intents"][0]["action"] is None
    assert view["action_intents"][0]["approval"]["consumed_at"] is None


def test_rejected_approval_closes_case_and_cannot_execute(harness, token, clock):
    case = alerting_case(harness, token, clock)
    harness.call("POST", f"/v1/cases/{case['id']}/investigations", token,
                 {"expected_revision": 1})
    intent = harness.call("GET", f"/v1/cases/{case['id']}", token).json()[
        "action_intents"][0]["intent"]
    rejected = harness.call("POST", "/v1/approvals", token,
                            {"action_intent_id": intent["id"], "decision": "rejected"}).json()
    again = harness.call("POST", "/v1/approvals", token,
                         {"action_intent_id": intent["id"], "decision": "approved"})
    assert again.status_code == 409
    response = harness.call("POST", "/v1/actions", token, {"approval_id": rejected["id"],
                                                           "idempotency_key": str(uuid.uuid4())})
    assert response.status_code == 409
    assert response.json()["error"] in {"approval_not_available", "case_not_executable"}
    assert harness.call("GET", f"/v1/cases/{case['id']}", token).json()["case"]["state"] == "closed"


def test_missing_capability_is_denied_inside_scope(harness, token, clock, database_url):
    case = alerting_case(harness, token, clock)
    harness.call("POST", f"/v1/cases/{case['id']}/investigations", token,
                 {"expected_revision": 1})
    approval = approve_pending(harness, token, case["id"])
    ctx = harness.service.authenticate(token)
    # Same scope and actor, but a session without execute capability.
    limited = "limited-token-for-test"
    from sentinel.service import token_digest
    with db.connect(database_url) as conn:
        conn.execute("INSERT INTO api_sessions VALUES (%s, %s, %s, %s, 'human', %s, %s, %s)",
                     (token_digest(limited), ctx.scope.tenant_id, ctx.scope.session_id,
                      ctx.actor_id, ["read_case", "approve_action"], clock(),
                      clock() + timedelta(hours=1)))
    response = harness.call("POST", "/v1/actions", limited, {"approval_id": approval["id"],
                                                             "idempotency_key": str(uuid.uuid4())})
    assert (response.status_code, response.json()) == (403, {"error": "action_permission_denied"})
    assert audit_types(harness, token, case["id"])[-1][:2] == ("action_denied", "denied")


class FlakyInvestigator(DeterministicInvestigator):
    def __init__(self, failures):
        super().__init__()
        self.failures = list(failures)

    def investigate(self, view):
        if self.failures:
            raise InvestigatorError(self.failures.pop(0))
        return super().investigate(view)


def test_investigator_failure_reopens_case_for_retry(database_url, clock):
    h = Harness(database_url, clock, FlakyInvestigator(["provider_unavailable"]))
    token = h.service.create_session(ANALYST)[0]
    case = alerting_case(h, token, clock)
    path = f"/v1/cases/{case['id']}/investigations"
    failed = h.call("POST", path, token, {"expected_revision": 1}).json()
    assert (failed["case"]["state"], failed["case"]["revision"]) == ("open", 3)
    assert failed["agent_runs"][0]["run"]["failure_code"] == "provider_unavailable"
    assert failed["action_intents"] == []
    ok = h.call("POST", path, token, {"expected_revision": 3}).json()
    assert ok["case"]["state"] == "awaiting_approval"
    assert ("investigation_completed", "failure", 3) in audit_types(h, token, case["id"])


def test_crashed_investigation_is_recovered_after_restart(database_url, clock):
    h = Harness(database_url, clock)
    token = h.service.create_session(ANALYST)[0]
    case = alerting_case(h, token, clock)
    ctx = h.service.authenticate(token)
    h.service.begin_investigation(ctx, uuid.UUID(case["id"]), 1)  # then the process dies

    h = Harness(database_url, clock)  # restart
    path = f"/v1/cases/{case['id']}/investigations"
    busy = h.call("POST", path, token, {"expected_revision": 2})
    assert busy.json() == {"error": "investigation_in_progress"}
    clock.advance(seconds=DeterministicInvestigator.timeout_seconds + 31)
    recovered = h.call("POST", path, token, {"expected_revision": 2})
    assert recovered.json() == {"error": "investigation_recovered"}
    view = h.call("GET", f"/v1/cases/{case['id']}", token).json()
    assert view["agent_runs"][0]["run"]["failure_code"] == "timeout"
    assert view["case"]["state"] == "open"
    retried = h.call("POST", path, token, {"expected_revision": view["case"]["revision"]})
    assert retried.json()["case"]["state"] == "awaiting_approval"


def test_finish_after_recovery_is_superseded(database_url, clock):
    h = Harness(database_url, clock)
    token = h.service.create_session(ANALYST)[0]
    case = alerting_case(h, token, clock)
    ctx = h.service.authenticate(token)
    run, view = h.service.begin_investigation(ctx, uuid.UUID(case["id"]), 1)
    clock.advance(minutes=5)
    h.call("POST", f"/v1/cases/{case['id']}/investigations", token, {"expected_revision": 2})
    from sentinel.service import ServiceError
    with pytest.raises(ServiceError) as raised:
        h.service.finish_investigation(ctx, run, InvestigationFinding(
            operation="escalate", reason_code="velocity_pattern", rationale="late"), None)
    assert raised.value.code == "investigation_superseded"


def test_audit_log_is_append_only(harness, token, clock, database_url):
    alerting_case(harness, token, clock)
    with db.connect(database_url) as conn:
        for statement in ("UPDATE audit_events SET body = '{}'", "DELETE FROM audit_events",
                          "TRUNCATE audit_events"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with conn.transaction():
                    conn.execute(statement)


def test_migrations_apply_once(database_url):
    assert db.migrate(database_url) == []
