"""Deterministic browser-test scenarios (C02), seeded through the real service methods.

Seeding runs in the fixture process, never through an HTTP route. Identifiers come from a
per-label UUID sequence, so a fresh stack always yields the same IDs. Timestamps are relative
to the wall clock at seeding time (the API process uses the real clock). The expired-approval
scenario is seeded by a service whose clock is 10 minutes in the past, so its approval is
already outside its 5-minute validity when the browser sees it. The API process has no test
clock and no seeding route.

Model fixtures (I01, opt-in) add three scenarios seeded by a service holding the accepted
registered scorer (`hgb_balanced@p1`). Their account profiles and disclosures go through the
accepted operator methods (`provision_accounts` / `record_disclosures`), and their expected
scores come from the actual artifact. Each model transaction occurs EVENT_MARGIN (5 minutes)
before the seeding clock reading, so the API accepts it as a past event while its own clock
is up to that much behind the seeder's (the production guard refuses occurred_at > now).
Profiles open exactly 400 days before each transaction's `occurred_at`, so every f1 input and
score is independent of the wall clock.
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


def _extra_token(database_url: str, scope, actor, capabilities, now: datetime) -> str:
    """A human session in an existing scope with chosen capabilities (fixture SQL only)."""
    token = secrets.token_urlsafe(32)
    with db.connect(database_url) as conn:
        conn.execute("INSERT INTO api_sessions VALUES (%s, %s, %s, %s, 'human', %s, %s, %s)",
                     (token_digest(token), scope.tenant_id, scope.session_id, actor,
                      capabilities, now, now + SESSION_TTL))
    return token


def describe(service: Sentinel, token: str) -> dict:
    ctx = service.authenticate(token)
    return {"tenant_id": str(ctx.scope.tenant_id), "session_id": str(ctx.scope.session_id),
            "actor_id": str(ctx.actor_id), "capabilities": sorted(ctx.capabilities)}


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
    for name, (actor, capabilities) in extra.items():
        tokens[name] = _extra_token(database_url, analyst.scope, actor, capabilities, now)
    return tokens, {name: describe(service, token) for name, token in tokens.items()}


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


# ---- model fixtures (I01) ------------------------------------------------------------------

MODEL_KEY = "hgb_balanced@p1"
MODEL_MINOR = 250_000
ACCOUNT_AGE = timedelta(days=400)
OPERATOR_LEAD = timedelta(hours=1)  # operator data is loaded an hour before the decision
# Model events occur this long before the seeding clock reading (R43). The API decides with
# its own clock, so a POST of request_body reaches its intended check while that clock is up
# to EVENT_MARGIN behind the seeder; further behind, it is future_event_time. Shorter than
# OPERATOR_LEAD, so operator data stays loaded before the event as well as the decision.
EVENT_MARGIN = timedelta(minutes=5)
_scorer = None


def model_scorer():
    """The accepted registered scorer, loaded once and outside every stable_ids block (a
    first-time ml import may call uuid4)."""
    global _scorer
    if _scorer is None:
        from sentinel import scorers
        _scorer = scorers.ModelScorer(scorers.REGISTRY[MODEL_KEY])
    return _scorer


def model_service_factory(database_url: str) -> ServiceAt:
    scorer = model_scorer()
    return lambda at: Sentinel(database_url, FixtureInvestigator(), Clock(at), scorer=scorer)


def _account(label: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, f"acct:{label}")


def _model_body(label: str, now: datetime, currency: str = "USD") -> dict:
    return {"external_id": f"i01-{label}", "account_id": str(_account(label)),
            "direction": "debit",
            "amount": {"currency": currency, "minor_units": MODEL_MINOR, "currency_exponent": 2},
            "occurred_at": (now - EVENT_MARGIN).isoformat().replace("+00:00", "Z")}


def _provision(at, ctx, label, now, home="USD") -> dict:
    """The account's profile, opened ACCOUNT_AGE before the transaction _model_body builds
    for the same `now`."""
    opened = now - EVENT_MARGIN - ACCOUNT_AGE
    profile = {"account_id": str(_account(label)), "home_currency": home,
               "opened_at": opened.isoformat().replace("+00:00", "Z")}
    at(now - OPERATOR_LEAD).provision_accounts(ctx.scope.tenant_id, ctx.scope.session_id,
                                               [profile])
    return profile


def _expected(scoring: dict) -> dict:
    keys = ("scoring_kind", "score_semantics", "score", "threshold", "alerted", "model",
            "inputs", "scorer", "features", "threshold_policy")
    return {k: scoring[k] for k in keys}


def expected_fresh_scoring(body: dict, profile: dict) -> dict:
    """What model mode must return for `body` as an account's first transaction: f1 by the
    accepted C03 code, scored by the actual artifact (rounded as the service rounds)."""
    import numpy as np

    from data_pipeline.features import compute
    scorer = model_scorer()
    values = compute(TransactionInput.model_validate(body).model_dump(mode="json"),
                     {"home_currency": profile["home_currency"],
                      "opened_at": profile["opened_at"]}, [], 0)
    values.pop("external_id")
    names = list(scorer.protocol["features"])
    X = np.empty((1, len(names) + 1), dtype=object)
    X[0, :len(names)] = [float(values[n]) for n in names]
    X[0, len(names)] = body["amount"]["currency"]
    score = round(float(scorer.pipeline.predict_proba(X)[0, 1]), 12)
    return {"scoring_kind": "model", "score_semantics": "uncalibrated_score", "score": score,
            "threshold": scorer.threshold, "alerted": score >= scorer.threshold,
            "model": scorer.model.model_dump(mode="json"), "values": values,
            "history_rows": 0, "disclosures_used": 0,
            "profile_home_currency": profile["home_currency"]}


def model_alert(at, ctx, label, now):
    """A recorded model-scored alert: USD-home account, one fraud disclosure known an hour
    earlier, a GBP debit (foreign currency)."""
    analyst = ctx["analyst"]
    _provision(at, analyst, label, now)
    at(now - OPERATOR_LEAD).record_disclosures(
        analyst.scope.tenant_id, analyst.scope.session_id,
        [{"external_id": f"i01-{label}-disclosed", "account_id": str(_account(label)),
          "is_fraud": True, "disclosed_at": (now - timedelta(days=2)).isoformat()}])
    body = _model_body(label, now, currency="GBP")
    result = at(now).ingest(analyst, TransactionInput.model_validate(body))
    if result["case"] is None:
        raise RuntimeError("model_alert fixture did not alert")  # fail closed, never fake
    return {"case_id": result["case"]["id"], "transaction_id": result["transaction"]["id"],
            "account_id": body["account_id"], "request_body": body,
            "expected_scoring": _expected(result["scoring"]), "session": "analyst",
            "state": "open", "revision": 1,
            "next": "GET the case: scoring_kind model, uncalibrated_score, pins.scorer "
                    "hgb_balanced; POST request_body again (any mode) -> 201 replayed true "
                    "with the identical stored scoring; investigate rev 1 -> awaiting_approval"}


def model_missing_profile(at, ctx, label, now):
    """No profile is provisioned for this account; nothing is stored at seeding."""
    return {"account_id": str(_account(label)), "request_body": _model_body(label, now),
            "session": "analyst",
            "expected": {"model_mode": {"status": 422, "error": "account_profile_missing",
                                        "stored_transaction": False}},
            "next": "model mode: POST request_body -> 422 account_profile_missing and no "
                    "transaction, outcome, alert or case is stored (inspect_case "
                    "--external-id finds none); in rule mode the rule would score it"}


def model_live_alert(at, ctx, label, now):
    """A provisioned account with no history, for a fresh ingestion through the live API."""
    profile = _provision(at, ctx["analyst"], label, now)
    body = _model_body(label, now)
    return {"account_id": body["account_id"], "request_body": body, "session": "analyst",
            "profile": profile, "expected_scoring": expected_fresh_scoring(body, profile),
            "next": "model mode: POST request_body (first ingestion for this account) -> 201 "
                    "with scoring matching expected_scoring (kind, semantics, score, threshold, "
                    "alerted, model, inputs.values/history_rows/disclosures_used/"
                    "profile_home_currency) and a new open case pinned to hgb_balanced; "
                    "seed a new ordinal for every further fresh ingestion"}


MODEL_SCENARIOS = {fn.__name__: fn for fn in (
    model_alert, model_missing_profile, model_live_alert)}
ALL_SCENARIOS = {**SCENARIOS, **MODEL_SCENARIOS}


def _contexts(at: ServiceAt, tokens: dict, now: datetime) -> dict:
    service = at(now)
    return {name: service.authenticate(token) for name, token in tokens.items()}


def seed_all(database_url: str, model_fixtures: bool = False) -> tuple[dict, dict, dict]:
    """Sessions plus one instance of every scenario (and, with model_fixtures, the model
    scenarios plus an `ingest_only` token). Returns (tokens, sessions, scenarios)."""
    at = service_factory(database_url)
    now = datetime.now(timezone.utc)
    tokens, sessions = create_sessions(at, database_url, now)
    if model_fixtures:
        model_at = model_service_factory(database_url)  # loads the model before stable_ids
        analyst = at(now).authenticate(tokens["analyst"])
        tokens["ingest_only"] = _extra_token(database_url, analyst.scope, analyst.actor_id,
                                             ["ingest_transaction"], now)
        sessions["ingest_only"] = describe(at(now), tokens["ingest_only"])
    contexts = _contexts(at, tokens, now)
    scenarios = {}
    for name, build in SCENARIOS.items():
        with stable_ids(name):
            scenarios[name] = build(at, contexts, name, now)
    if model_fixtures:
        for name, build in MODEL_SCENARIOS.items():
            with stable_ids(name):
                scenarios[name] = build(model_at, contexts, name, now)
    return tokens, sessions, scenarios


def seed_one(database_url: str, tokens: dict, name: str, ordinal: int) -> dict:
    """A fresh instance of one scenario (stable IDs per name and ordinal)."""
    model = name in MODEL_SCENARIOS
    at = model_service_factory(database_url) if model else service_factory(database_url)
    now = datetime.now(timezone.utc)
    label = f"{name}-{ordinal}"
    with stable_ids(label):
        return ALL_SCENARIOS[name](at, _contexts(at, tokens, now), label, now)
