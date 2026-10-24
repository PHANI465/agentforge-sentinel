"""Deterministic browser-test scenarios (C02), seeded through the real service methods.

Seeding runs in the fixture process, never through an HTTP route. Identifiers come from a
per-label UUID sequence, so a fresh stack always yields the same IDs. Timestamps are relative
to the wall clock at seeding time (the API process uses the real clock). The expired-approval
scenario is seeded by a service whose clock is 10 minutes in the past, so its approval is
already outside its 5-minute validity when the browser sees it. The API process has no test
clock and no seeding route.
"""
from __future__ import annotations

import contextlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Callable
from unittest import mock

from fixture_app import PROVIDER_FAILURE_MINOR, FixtureInvestigator
from sentinel import db
from sentinel.contracts.v1 import ApprovalDecisionInput, ExecuteActionInput, TransactionInput
from sentinel.service import Sentinel, token_digest

ANALYST = frozenset({"ingest_transaction", "read_case", "approve_action",
                     "execute_simulated_action"})
NAMESPACE = uuid.UUID("5e1e0000-c02f-4000-8000-000000000000")
LARGE_MINOR = 250_000  # alerts on amount alone (rule score 0.6 >= 0.5)
SESSION_TTL = timedelta(hours=8)


class Clock:
    def __init__(self, now: datetime):
        self.now = now

    def __call__(self) -> datetime:
        return self.now


ServiceAt = Callable[[datetime], Sentinel]


def service_factory(database_url: str) -> ServiceAt:
    return lambda at: Sentinel(database_url, FixtureInvestigator(), Clock(at))


@contextlib.contextmanager
def stable_ids(label: str):
    """uuid4() inside the block returns uuid5(NAMESPACE, f'{label}:{n}') for n = 1, 2, ..."""
    counter = iter(range(1, 1_000_000))
    with mock.patch("uuid.uuid4", lambda: uuid.uuid5(NAMESPACE, f"{label}:{next(counter)}")):
        yield


def create_sessions(at: ServiceAt, database_url: str, now: datetime) -> tuple[dict, dict]:
    """analyst and other_session (same tenant, different session), plus two tokens in the
    analyst's own scope: read_only (read_case only) and second_actor (another human).
    Returns (tokens, public session descriptions)."""
    service = at(now)
    with stable_ids("sessions"):
        analyst_token, analyst = service.create_session(ANALYST, ttl=SESSION_TTL)
        other_token, other = service.create_session(ANALYST, tenant_id=analyst.scope.tenant_id,
                                                    ttl=SESSION_TTL)
        second_actor_id = uuid.uuid4()
    tokens = {"analyst": analyst_token, "other_session": other_token}
    extra = {"read_only": (analyst.actor_id, ["read_case"]),
             "second_actor": (second_actor_id, sorted(ANALYST))}
    with db.connect(database_url) as conn:
        for name, (actor, capabilities) in extra.items():
            token = secrets.token_urlsafe(32)
            conn.execute("INSERT INTO api_sessions VALUES (%s, %s, %s, %s, 'human', %s, %s, %s)",
                         (token_digest(token), analyst.scope.tenant_id, analyst.scope.session_id,
                          actor, capabilities, now, now + SESSION_TTL))
            tokens[name] = token
    sessions = {}
    for name, token in tokens.items():
        ctx = service.authenticate(token)
        sessions[name] = {"tenant_id": str(ctx.scope.tenant_id),
                          "session_id": str(ctx.scope.session_id),
                          "actor_id": str(ctx.actor_id), "capabilities": sorted(ctx.capabilities)}
    return tokens, sessions


def _txn(at: datetime, label: str, minor_units: int) -> TransactionInput:
    return TransactionInput.model_validate({
        "external_id": f"c02-{label}", "account_id": str(uuid.uuid5(NAMESPACE, f"acct:{label}")),
        "direction": "debit",
        "amount": {"currency": "USD", "minor_units": minor_units, "currency_exponent": 2},
        "occurred_at": at.isoformat()})


def _open(service, ctx, label, minor_units=LARGE_MINOR) -> dict:
    result = service.ingest(ctx, _txn(service.clock(), label, minor_units))
    return {"case_id": result["case"]["id"], "transaction_id": result["transaction"]["id"]}


def _investigated(service, ctx, label) -> dict:
    ids = _open(service, ctx, label)
    detail = service.investigate(ctx, uuid.UUID(ids["case_id"]), 1)
    return {**ids, "intent_id": detail["action_intents"][-1]["intent"]["id"]}


def _approved(service, ctx, label) -> dict:
    ids = _investigated(service, ctx, label)
    approval = service.record_approval(ctx, ApprovalDecisionInput(
        action_intent_id=ids["intent_id"], decision="approved"))
    return {**ids, "approval_id": approval["id"], "approval_expires_at": approval["expires_at"]}


# Builders: (service_at, contexts, label, now) -> public scenario record (no tokens).

def open_case(at, ctx, label, now):
    return {**_open(at(now), ctx["analyst"], label), "session": "analyst", "state": "open",
            "revision": 1,
            "next": "investigate with expected_revision 1 -> awaiting_approval (revision 3)"}


def awaiting_approval(at, ctx, label, now):
    return {**_investigated(at(now), ctx["analyst"], label), "session": "analyst",
            "state": "awaiting_approval", "revision": 3,
            "next": "approve -> 201 (case stays revision 3); or reject -> 201 and the case "
                    "closes (revision 4)"}


def approved(at, ctx, label, now):
    """Valid for 5 minutes from seeding: seed on demand right before the test that uses it."""
    return {**_approved(at(now), ctx["analyst"], label), "session": "analyst",
            "state": "awaiting_approval", "revision": 3,
            "next": "execute with a new idempotency_key -> succeeded and case closed "
                    "(revision 4); the same key again -> replayed true, one action row"}


def executed(at, ctx, label, now):
    service = at(now)
    ids = _approved(service, ctx["analyst"], label)
    key = uuid.uuid5(NAMESPACE, f"{label}:idempotency")
    action = service.execute_action(ctx["analyst"], ExecuteActionInput(
        approval_id=ids["approval_id"], idempotency_key=key))
    return {**ids, "action_id": action["action"]["id"], "idempotency_key": str(key),
            "session": "analyst", "state": "closed", "revision": 4,
            "next": "execute again with idempotency_key -> 200 replayed true, same action_id; "
                    "a different key -> 409 approval_not_available"}


def rejected(at, ctx, label, now):
    service = at(now)
    ids = _investigated(service, ctx["analyst"], label)
    approval = service.record_approval(ctx["analyst"], ApprovalDecisionInput(
        action_intent_id=ids["intent_id"], decision="rejected"))
    return {**ids, "approval_id": approval["id"], "session": "analyst", "state": "closed",
            "revision": 4, "next": "execute -> 409 approval_not_available; approving the "
                                   "same intent again -> 409 stale_case_revision (the case "
                                   "is closed, so the approval-exists check is not reached)"}


def approval_expired(at, ctx, label, now):
    ids = _approved(at(now - timedelta(minutes=10)), ctx["analyst"], label)
    return {**ids, "session": "analyst", "state": "awaiting_approval", "revision": 3,
            "next": "execute -> 409 approval_outside_validity and the case reopens (open, "
                    "revision 4, approval_expired audit); investigate with expected_revision 4 "
                    "-> awaiting_approval revision 6 with a new intent; approve + execute -> "
                    "succeeded; the old approval is rejected (409)"}


def stale_revision(at, ctx, label, now):
    return {**_open(at(now), ctx["analyst"], label), "session": "analyst", "state": "open",
            "revision": 1,
            "next": "load it in the UI, investigate it out of band (a second request with the "
                    "analyst token), then submit investigate with revision 1 -> 409 "
                    "stale_case_revision; a re-read shows revision 3"}


def provider_failure(at, ctx, label, now):
    return {**_open(at(now), ctx["analyst"], label, minor_units=PROVIDER_FAILURE_MINOR),
            "session": "analyst", "state": "open", "revision": 1,
            "next": "investigate with expected_revision 1 -> 200 with the run failed "
                    "(failure_code provider_unavailable), case open revision 3, no intent; "
                    "every retry fails the same way (deterministic; no model call)"}


def failed_run_reopened(at, ctx, label, now):
    service = at(now)
    ids = _open(service, ctx["analyst"], label)
    run, _view = service.begin_investigation(ctx["analyst"], uuid.UUID(ids["case_id"]), 1)
    service.finish_investigation(ctx["analyst"], run, None, "provider_unavailable")
    return {**ids, "failed_run_id": str(run.id), "session": "analyst", "state": "open",
            "revision": 3, "next": "investigate with expected_revision 3 -> awaiting_approval "
                                   "revision 5; the failed run stays in agent_runs"}


def foreign_session_case(at, ctx, label, now):
    return {**_open(at(now), ctx["other_session"], label), "session": "other_session",
            "state": "open", "revision": 1,
            "next": "analyst token -> 404 not_found on read, audit and investigate; absent "
                    "from the analyst's list and overview"}


def limited_capabilities(at, ctx, label, now):
    return {**_approved(at(now), ctx["analyst"], label), "session": "analyst",
            "state": "awaiting_approval", "revision": 3,
            "next": "read_only token: GET 200, approve -> 403 permission_denied, execute -> "
                    "403 action_permission_denied; second_actor token: execute -> 403 "
                    "approver_mismatch. Each denied execution adds an action_denied audit "
                    "event; a denied approval is not audited"}


SCENARIOS = {fn.__name__: fn for fn in (
    open_case, awaiting_approval, approved, executed, rejected, approval_expired,
    stale_revision, provider_failure, failed_run_reopened, foreign_session_case,
    limited_capabilities,
)}


def _contexts(at: ServiceAt, tokens: dict, now: datetime) -> dict:
    service = at(now)
    return {name: service.authenticate(token) for name, token in tokens.items()}


def seed_all(database_url: str) -> tuple[dict, dict, dict]:
    """Sessions plus one instance of every scenario. Returns (tokens, sessions, scenarios)."""
    at = service_factory(database_url)
    now = datetime.now(timezone.utc)
    tokens, sessions = create_sessions(at, database_url, now)
    contexts = _contexts(at, tokens, now)
    scenarios = {}
    for name, build in SCENARIOS.items():
        with stable_ids(name):
            scenarios[name] = build(at, contexts, name, now)
    return tokens, sessions, scenarios


def seed_one(database_url: str, tokens: dict, name: str, ordinal: int) -> dict:
    """A fresh instance of one scenario (stable IDs per name and ordinal)."""
    at = service_factory(database_url)
    now = datetime.now(timezone.utc)
    label = f"{name}-{ordinal}"
    with stable_ids(label):
        return SCENARIOS[name](at, _contexts(at, tokens, now), label, now)
