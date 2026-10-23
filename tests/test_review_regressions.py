"""Regressions for review Sentinel_Review_ed08de0 findings R2-R6 and R8 (R1: test_investigators,
R7: test_thin_path). Each test reproduced its finding on ed08de0 before the fix."""
import asyncio
import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import psycopg
import pytest

from sentinel import db
from sentinel.api import MAX_BODY_BYTES, create_app
from sentinel.contracts.v1 import ExecuteActionInput, TransactionInput
from sentinel.service import ServiceError, token_digest
from test_thin_path import (
    ANALYST, Harness, alerting_case, approve_pending, audit_types, txn,
)


def ready_for_execution(database_url, clock):
    h = Harness(database_url, clock)
    token = h.service.create_session(ANALYST)[0]
    case = alerting_case(h, token, clock)
    h.call("POST", f"/v1/cases/{case['id']}/investigations", token, {"expected_revision": 1})
    return h, token, case, approve_pending(h, token, case["id"])


def wait_for_lock_waiter(database_url, timeout=10.0):
    deadline = time.monotonic() + timeout
    with psycopg.connect(database_url, autocommit=True) as conn:
        while time.monotonic() < deadline:
            if conn.execute("SELECT count(*) FROM pg_stat_activity WHERE wait_event_type = 'Lock'"
                            " AND datname = current_database()").fetchone()[0]:
                return
            time.sleep(0.02)
    raise AssertionError("executor never blocked on the lock")


def table_count(database_url, table):
    with db.connect(database_url) as conn:
        return conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]


# ---- R2: validity time must be taken after lock waits ---------------------------------------

def test_r2_approval_expiring_during_lock_wait_is_denied(database_url, clock):
    h, token, case, approval = ready_for_execution(database_url, clock)
    clock.advance(seconds=299)  # still valid when the request arrives
    ctx = h.service.authenticate(token)
    blocker = psycopg.connect(database_url)
    blocker.execute("SELECT 1 FROM approvals WHERE id = %s FOR UPDATE", (approval["id"],))
    pool = ThreadPoolExecutor(1)
    future = pool.submit(h.service.execute_action, ctx, ExecuteActionInput(
        approval_id=approval["id"], idempotency_key=uuid.uuid4()))
    try:
        wait_for_lock_waiter(database_url)
        clock.advance(seconds=2)  # expires while the request waits
    finally:
        blocker.rollback()
        blocker.close()
    with pytest.raises(ServiceError) as raised:
        future.result(timeout=30)
    pool.shutdown()
    assert raised.value.code == "approval_outside_validity"
    assert table_count(database_url, "simulated_actions") == 0
    view = h.call("GET", f"/v1/cases/{case['id']}", token).json()
    assert view["action_intents"][0]["approval"]["consumed_at"] is None
    assert ("action_denied", "denied", 3) in audit_types(h, token, case["id"])


# ---- R3: features only from history available at the decision time --------------------------

class HookClock:
    """Runs `hook` once, inside the first clock read made by `thread`."""

    def __init__(self, clock):
        self.clock, self.hook, self.thread = clock, None, None

    def __call__(self):
        value = self.clock()
        if self.hook is not None and threading.current_thread() is self.thread:
            hook, self.hook = self.hook, None
            hook()
        return value


def test_r3_concurrent_older_event_ingested_later_is_not_counted(database_url, clock):
    hooked = HookClock(clock)
    h = Harness(database_url, hooked)
    token = h.service.create_session(ANALYST)[0]
    ctx = h.service.authenticate(token)
    late = TransactionInput.model_validate(txn(clock, "late-older-event", minutes_ago=10))
    big = TransactionInput.model_validate(txn(clock, "decision", minor_units=250_000))
    worker = {}

    def ingest_late_meanwhile():
        clock.advance(seconds=1)  # B is ingested after A's decision time
        thread = threading.Thread(target=lambda: worker.update(
            result=h.service.ingest(ctx, late)))
        thread.start()
        thread.join(timeout=1.5)  # B either commits now (bug) or waits for A (fixed)
        worker["thread"] = thread

    hooked.hook, hooked.thread = ingest_late_meanwhile, threading.current_thread()
    decision = h.service.ingest(ctx, big)
    worker["thread"].join(timeout=30)
    assert decision["alert"]["features_as_of"] < worker["result"]["transaction"]["ingested_at"]
    assert decision["rule_score"] == 0.6  # 0.8 if the unavailable transaction was counted
    facts = {e["facts"][0]["name"]: e["facts"][0]["value"] for e in h.call(
        "GET", f"/v1/cases/{decision['case']['id']}", token).json()["evidence"]}
    assert facts["transaction_count_1h"] == 0


def test_r3_same_timestamp_transactions_are_excluded(harness_parts):
    h, token, clock = harness_parts
    h.call("POST", "/v1/transactions", token, txn(clock, "same-ts"))
    decision = h.call("POST", "/v1/transactions", token,
                      txn(clock, "decision", minor_units=250_000)).json()
    assert decision["rule_score"] == 0.6


# ---- R4: replay must re-check current authorization -----------------------------------------

def executed(database_url, clock):
    h, token, case, approval = ready_for_execution(database_url, clock)
    body = {"approval_id": approval["id"], "idempotency_key": str(uuid.uuid4())}
    assert h.call("POST", "/v1/actions", token, body).status_code == 200
    return h, token, case, body


def test_r4_replay_after_capability_revocation_is_denied(database_url, clock):
    h, token, case, body = executed(database_url, clock)
    with db.connect(database_url) as conn:
        conn.execute("UPDATE api_sessions SET capabilities = %s WHERE token_sha256 = %s",
                     (["read_case", "approve_action"], token_digest(token)))
    response = h.call("POST", "/v1/actions", token, body)
    assert (response.status_code, response.json()) == (403, {"error": "action_permission_denied"})
    assert audit_types(h, token, case["id"])[-1][:2] == ("action_denied", "denied")


def test_r4_replay_by_another_actor_in_same_scope_is_denied(database_url, clock):
    h, token, case, body = executed(database_url, clock)
    ctx = h.service.authenticate(token)
    other = "same-scope-other-actor"
    with db.connect(database_url) as conn:
        conn.execute("INSERT INTO api_sessions VALUES (%s, %s, %s, %s, 'human', %s, %s, %s)",
                     (token_digest(other), ctx.scope.tenant_id, ctx.scope.session_id,
                      uuid.uuid4(), sorted(ANALYST), clock(), clock() + timedelta(hours=1)))
    response = h.call("POST", "/v1/actions", other, body)
    assert (response.status_code, response.json()) == (403, {"error": "approver_mismatch"})


def test_r4_legitimate_replay_after_expiry_still_returns_original(database_url, clock):
    h, token, case, body = executed(database_url, clock)
    clock.advance(minutes=30)  # past approval validity; the retry is still the same request
    response = h.call("POST", "/v1/actions", token, body)
    assert response.status_code == 200 and response.json()["replayed"] is True


# ---- R5: every scoring outcome is persisted and replayed ------------------------------------

@pytest.fixture
def harness_parts(database_url, clock):
    h = Harness(database_url, clock)
    return h, h.service.create_session(ANALYST)[0], clock


@pytest.mark.parametrize("priors, minor_units, expected", [
    (0, 1500, 0.0), (2, 1500, 0.4), (1, 250_000, 0.8),
])
def test_r5_replay_returns_original_rule_score(harness_parts, priors, minor_units, expected):
    h, token, clock = harness_parts
    for i in range(priors):
        h.call("POST", "/v1/transactions", token, txn(clock, f"p{i}", minutes_ago=20 - i))
    payload = txn(clock, "scored", minor_units=minor_units)
    first = h.call("POST", "/v1/transactions", token, payload).json()
    # Later history must not change the recorded outcome of the earlier decision.
    h.call("POST", "/v1/transactions", token, txn(clock, "after", minutes_ago=1))
    retry = h.call("POST", "/v1/transactions", token, payload).json()
    assert first["rule_score"] == expected
    assert retry == {**first, "replayed": True}
    assert retry["scoring"]["scorer"] == first["scoring"]["scorer"]


# ---- R6: body limit enforced while streaming ------------------------------------------------

def asgi_post(app, path, token, chunks, headers=()):
    """Drive the ASGI app directly; returns (status, body, chunks_consumed)."""
    consumed = {"n": 0}
    out = {"status": None, "body": b""}
    chunk_iter = iter(chunks)

    async def receive():
        try:
            chunk = next(chunk_iter)
        except StopIteration:
            return {"type": "http.request", "body": b"", "more_body": False}
        consumed["n"] += 1
        return {"type": "http.request", "body": chunk, "more_body": True}

    async def send(message):
        if message["type"] == "http.response.start":
            out["status"] = message["status"]
        elif message["type"] == "http.response.body":
            out["body"] += message.get("body", b"")

    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "POST",
             "scheme": "http", "path": path, "raw_path": path.encode(), "query_string": b"",
             "root_path": "", "server": ("test", 80), "client": ("test", 1),
             "headers": [(b"authorization", f"Bearer {token}".encode()),
                         (b"content-type", b"application/json"), *headers]}
    asyncio.run(app(scope, receive, send))
    return out["status"], out["body"], consumed["n"]


def test_r6_streaming_body_stops_at_limit(harness_parts):
    h, token, _ = harness_parts
    app = create_app(h.service)
    chunk = b" " * 1024
    status, body, consumed = asgi_post(app, "/v1/transactions", token,
                                       (chunk for _ in range(4096)))  # 4 MiB offered
    assert status == 413 and json.loads(body) == {"error": "body_too_large"}
    assert consumed <= MAX_BODY_BYTES // len(chunk) + 1


def test_r6_declared_oversize_length_is_rejected_before_reading(harness_parts):
    h, token, _ = harness_parts
    app = create_app(h.service)
    status, _, consumed = asgi_post(app, "/v1/transactions", token, [b"{}"] * 100,
                                    headers=[(b"content-length", b"10000000")])
    assert (status, consumed) == (413, 0)


# ---- R8: an expired approval must not strand its case ---------------------------------------

def test_r8_expired_approval_reopens_case_for_a_fresh_intent(database_url, clock):
    h, token, case, old = ready_for_execution(database_url, clock)
    clock.advance(minutes=6)
    denied = h.call("POST", "/v1/actions", token, {"approval_id": old["id"],
                                                   "idempotency_key": str(uuid.uuid4())})
    assert denied.json() == {"error": "approval_outside_validity"}
    view = h.call("GET", f"/v1/cases/{case['id']}", token).json()
    assert (view["case"]["state"], view["case"]["revision"]) == ("open", 4)
    assert audit_types(h, token, case["id"])[-1] == ("approval_expired", "success", 4)

    redo = h.call("POST", f"/v1/cases/{case['id']}/investigations", token,
                  {"expected_revision": 4}).json()
    assert (redo["case"]["state"], redo["case"]["revision"]) == ("awaiting_approval", 6)
    fresh = approve_pending(h, token, case["id"])
    assert fresh["intent"]["case_revision"] == 6 and fresh["id"] != old["id"]
    # The old approval stays unusable even though its case is executable again.
    stale = h.call("POST", "/v1/actions", token, {"approval_id": old["id"],
                                                  "idempotency_key": str(uuid.uuid4())})
    assert stale.status_code == 409
    ok = h.call("POST", "/v1/actions", token, {"approval_id": fresh["id"],
                                               "idempotency_key": str(uuid.uuid4())})
    assert ok.status_code == 200
    assert table_count(database_url, "simulated_actions") == 1


def test_r8_investigate_request_also_expires_a_lapsed_approval(database_url, clock):
    h, token, case, _ = ready_for_execution(database_url, clock)
    path = f"/v1/cases/{case['id']}/investigations"
    assert h.call("POST", path, token, {"expected_revision": 3}).json() == {
        "error": "case_not_investigable"}  # still valid: nothing to do
    clock.advance(minutes=6)
    assert h.call("POST", path, token, {"expected_revision": 3}).json() == {
        "error": "approval_expired"}
    assert h.call("POST", path, token, {"expected_revision": 4}).status_code == 200
