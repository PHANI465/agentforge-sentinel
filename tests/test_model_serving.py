"""C07: actual trained-model inference in the service and API, with offline parity, scoped
decision-time inputs, refusal without a profile, and replay across scorer changes."""
import json
from dataclasses import replace
from datetime import datetime

import numpy as np
import psycopg
import pytest

from data_pipeline import features as f1
from data_pipeline import fixtures
from data_pipeline.generator import generate
from ml import dataset
from sentinel import db, scorers
from sentinel.contracts.v1 import TransactionInput
from sentinel.investigators import DeterministicInvestigator
from sentinel.service import Sentinel, ServiceError
from test_db_roles import runtime  # noqa: F401  (fixture)
from test_thin_path import ANALYST, Harness

MODEL = scorers.ModelScorer(scorers.REGISTRY["hgb_balanced@p1"])
# Independent of C04's training data: a different seed and size.
PARITY = replace(fixtures.TINY, seed=23, accounts=16, days=20)


class Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


def ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def txn_input(txn: dict) -> TransactionInput:
    return TransactionInput.model_validate({k: v for k, v in txn.items() if k != "ingested_at"})


@pytest.fixture(scope="module")
def parity_data():
    return generate(PARITY)


def test_online_features_and_scores_equal_offline_f1_and_c04(database_url, parity_data):
    data = parity_data
    clock = Clock(ts(data.transactions[0]["ingested_at"]))
    service = Sentinel(database_url, DeterministicInvestigator(), clock, scorer=MODEL)
    token, ctx = service.create_session(ANALYST)
    service.provision_accounts(ctx.scope.tenant_id, ctx.scope.session_id, data.accounts)
    # Every disclosure is recorded up front, including those far in the future: only the
    # ones known by each decision may count.
    service.record_disclosures(ctx.scope.tenant_id, ctx.scope.session_id, [
        {"external_id": label["external_id"], "account_id": txn["account_id"],
         "is_fraud": label["is_fraud"], "disclosed_at": label["label_available_at"]}
        for txn, label in zip(data.transactions, data.labels)
        if label["label_available_at"] is not None])
    online = {}
    for txn in sorted(data.transactions, key=f1.availability_key):  # arrival order
        clock.now = ts(txn["ingested_at"])
        result = service.ingest(ctx, txn_input(txn))
        online[txn["external_id"]] = result["scoring"]
    offline = f1.batch_features(data.transactions, data.accounts, data.labels)
    X = dataset.build_matrix(MODEL.protocol, offline, data.transactions)
    expected = MODEL.pipeline.predict_proba(X)[:, 1]
    mismatched = []
    for row, score in zip(offline, expected):
        scored = online[row["external_id"]]
        want = {k: v for k, v in row.items() if k != "external_id"}
        if scored["inputs"]["values"] != want or scored["score"] != round(float(score), 12):
            mismatched.append(row["external_id"])
    assert mismatched == [], mismatched[:5]
    assert len(online) == len(data.transactions)
    used = [s["inputs"]["disclosures_used"] for s in online.values()]
    assert max(used) > 0  # disclosures did contribute somewhere (non-vacuous)
    sample = next(iter(online.values()))
    assert sample["scoring_kind"] == "model" and sample["score_semantics"] == "uncalibrated_score"
    assert sample["model"]["artifact_sha256"] == MODEL.accepted.artifact_sha256
    assert sample["threshold"] == MODEL.threshold


def provisioned(database_url, clock, scorer=MODEL):
    service = Sentinel(database_url, DeterministicInvestigator(), clock, scorer=scorer)
    token, ctx = service.create_session(ANALYST)
    return service, token, ctx


def one_txn(clock, external_id="m1", account="00000000-0000-4000-8000-0000000000b1",
            minor_units=250_000):
    return TransactionInput.model_validate({
        "external_id": external_id, "account_id": account, "direction": "debit",
        "amount": {"currency": "USD", "minor_units": minor_units, "currency_exponent": 2},
        "occurred_at": clock().isoformat()})


def counts(database_url):
    with db.connect(database_url) as conn:
        return {t: conn.execute(f"SELECT count(*) AS n FROM {t}").fetchone()["n"]
                for t in ("transactions", "scoring_outcomes", "alerts", "cases")}


def test_missing_profile_is_refused_and_nothing_is_stored(database_url, clock):
    service, _, ctx = provisioned(database_url, clock)
    with pytest.raises(ServiceError) as raised:
        service.ingest(ctx, one_txn(clock))
    assert (raised.value.code, raised.value.status) == ("account_profile_missing", 422)
    assert counts(database_url) == {"transactions": 0, "scoring_outcomes": 0, "alerts": 0,
                                    "cases": 0}


def test_another_scopes_profile_is_not_used(database_url, clock):
    service, _, ctx = provisioned(database_url, clock)
    _, other = service.create_session(ANALYST, tenant_id=ctx.scope.tenant_id)
    account = "00000000-0000-4000-8000-0000000000b2"
    service.provision_accounts(other.scope.tenant_id, other.scope.session_id, [
        {"account_id": account, "home_currency": "USD", "opened_at": "2025-01-01T00:00:00Z"}])
    with pytest.raises(ServiceError, match="account_profile_missing"):
        service.ingest(ctx, one_txn(clock, account=account))
    assert service.ingest(other, one_txn(clock, account=account))["scoring"]["inputs"]


def test_recorded_outcomes_replay_across_scorer_changes(database_url, clock):
    service, _, ctx = provisioned(database_url, clock)
    account = "00000000-0000-4000-8000-0000000000b3"
    service.provision_accounts(ctx.scope.tenant_id, ctx.scope.session_id, [
        {"account_id": account, "home_currency": "USD", "opened_at": "2025-01-01T00:00:00Z"}])
    model_first = service.ingest(ctx, one_txn(clock, "m-a", account))
    rule = Sentinel(database_url, DeterministicInvestigator(), clock)  # operator switched back
    replay = rule.ingest(ctx, one_txn(clock, "m-a", account))
    assert replay["replayed"] is True
    assert replay["scoring"] == model_first["scoring"]  # never rescored
    fresh = rule.ingest(ctx, one_txn(clock, "r-b", account))["scoring"]
    assert fresh["scoring_kind"] == "rule" and "model" not in fresh and "inputs" not in fresh
    again = Sentinel(database_url, DeterministicInvestigator(), clock, scorer=MODEL)
    assert again.ingest(ctx, one_txn(clock, "r-b", account))["scoring"] == fresh


def test_http_model_mode_end_to_end(database_url, clock):
    h = Harness(database_url, clock)
    h.service.scorer = MODEL
    token = h.service.create_session(ANALYST)[0]
    ctx = h.service.authenticate(token)
    account = "00000000-0000-4000-8000-0000000000b4"
    info = h.call("GET", "/v1/scoring", token).json()
    assert info["mode"] == "model" and info["score_semantics"] == "uncalibrated_score"
    missing = h.call("POST", "/v1/transactions", token,
                     json.loads(one_txn(clock, "h1", account).model_dump_json()))
    assert (missing.status_code, missing.json()) == (422, {"error": "account_profile_missing"})
    h.service.provision_accounts(ctx.scope.tenant_id, ctx.scope.session_id, [
        {"account_id": account, "home_currency": "USD", "opened_at": "2025-01-01T00:00:00Z"}])
    response = h.call("POST", "/v1/transactions", token,
                      json.loads(one_txn(clock, "h1", account).model_dump_json()))
    assert response.status_code == 201
    body = response.json()
    assert body["scoring"]["model"]["results_id"] == "p1"
    assert set(body["scoring"]["inputs"]["values"]) == set(f1.FEATURE_NAMES)
    if body["alert"]:
        assert body["alert"]["scoring_kind"] == "model"
        assert body["case"]["pins"]["scorer"]["sha256"] == MODEL.accepted.artifact_sha256


def test_rule_mode_remains_the_default_and_unchanged(database_url, clock):
    service = Sentinel(database_url, DeterministicInvestigator(), clock)
    assert isinstance(service.scorer, scorers.RuleScorer)
    token, ctx = service.create_session(ANALYST)
    scored = service.ingest(ctx, one_txn(clock, "d1"))["scoring"]  # no profile needed
    assert scored["scoring_kind"] == "rule" and scored["score"] == 0.6
    assert np.isclose(scored["threshold"], 0.5)


def test_runtime_role_scores_with_the_model_but_cannot_provision(database_url, runtime,  # noqa: F811
                                                                 clock):
    _, runtime_url = runtime
    operator = Sentinel(database_url, DeterministicInvestigator(), clock)
    token, ctx = operator.create_session(ANALYST)
    account = "00000000-0000-4000-8000-0000000000b5"
    operator.provision_accounts(ctx.scope.tenant_id, ctx.scope.session_id, [
        {"account_id": account, "home_currency": "USD", "opened_at": "2025-01-01T00:00:00Z"}])
    service = Sentinel(runtime_url, DeterministicInvestigator(), clock, scorer=MODEL)
    scored = service.ingest(service.authenticate(token), one_txn(clock, "rt1", account))
    assert scored["scoring"]["scoring_kind"] == "model"
    for statement in (
            "UPDATE account_profiles SET home_currency = 'GBP'",
            "DELETE FROM account_profiles",
            "INSERT INTO fraud_disclosures SELECT * FROM fraud_disclosures LIMIT 0",
            "UPDATE fraud_disclosures SET is_fraud = true"):
        with psycopg.connect(runtime_url) as conn:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(statement)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        service.provision_accounts(ctx.scope.tenant_id, ctx.scope.session_id, [
            {"account_id": account, "home_currency": "GBP",
             "opened_at": "2025-01-01T00:00:00Z"}])
