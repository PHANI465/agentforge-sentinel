"""R43: the model browser fixtures reach their intended checks when the API's clock is a
little behind the seeder's.

These are CONTROLLED relative clocks, not host observations: the seeder and the API service
each get a fixed clock, and the host clock is never touched. The seeding goes through the
fixture builders exactly as seed_all / seed_one call them (owner, accepted operator methods,
the registered scorer). Every API-side request runs through the real service connected as a
least-privilege runtime role on disposable PostgreSQL, so the production future_event_time
guard, profile lookup, rollback and replay are the real ones. The documented tolerance is
EVENT_MARGIN (5 minutes) of API clock behind the seeder; one test pins that it is finite.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
import pytest
from psycopg import sql

from sentinel.contracts.v1 import TransactionInput
from sentinel.service import Sentinel, ServiceError
from test_db_roles import runtime  # noqa: F401  (fixture)

sys.path.insert(0, str(Path(__file__).resolve().parent / "support"))

import scenarios  # noqa: E402
from fixture_app import FixtureInvestigator  # noqa: E402

SEED_NOW = datetime(2026, 11, 2, 17, 0, tzinfo=timezone.utc)
ARTIFACT_SHA = "6c2982d1df12184f704bc45dbc5882d8f85dba16c50bd9829dda9e674602575b"
THRESHOLD = 4.0295386895426815e-06
RECORDED_SCORE, LIVE_SCORE = 0.61962960122, 0.802130558706
# How far the API clock is behind the seeder's: a control, the 3 s of the R43 probe (WSL2
# steps its realtime clock by about 2.5 s), and the edge of the documented tolerance.
BEHIND = [pytest.param(timedelta(0), id="same-clock"),
          pytest.param(timedelta(seconds=3), id="3s-behind"),
          pytest.param(timedelta(minutes=5), id="5min-behind")]
STORED = ("transactions", "scoring_outcomes", "alerts", "cases")
F1_LIVE = {"amount_minor": 250000, "is_credit": 0, "is_foreign_currency": 0,
           "account_age_days": 400, "count_1h": 0, "count_24h": 0, "small_count_1h": 0,
           "same_currency_sum_24h": 0, "credit_sum_24h": 0, "seconds_since_prev": -1,
           "amount_to_median_bps": -1, "prior_known_fraud": 0}
F1_RECORDED = {**F1_LIVE, "is_foreign_currency": 1, "prior_known_fraud": 1}


@pytest.fixture
def runtime_url(runtime):  # noqa: F811
    return runtime[1]


def ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def counts(owner_url) -> dict:
    with psycopg.connect(owner_url) as conn:
        return {t: conn.execute(sql.SQL("SELECT count(*) FROM {}").format(
            sql.Identifier(t))).fetchone()[0] for t in STORED}


def seeded(database_url):
    """An analyst session issued by the owner at SEED_NOW: (tokens, seeder factory)."""
    at = scenarios.model_service_factory(database_url)
    token, _ = at(SEED_NOW).create_session(scenarios.ANALYST, ttl=scenarios.SESSION_TTL)
    return {"analyst": token}, at


def build(database_url, tokens, at, name):
    """One model scenario as seed_all builds it, with the seeder's clock at SEED_NOW."""
    contexts = {"analyst": at(SEED_NOW).authenticate(tokens["analyst"])}
    with scenarios.stable_ids(name):
        return scenarios.MODEL_SCENARIOS[name](at, contexts, name, SEED_NOW)


def api(runtime_url, tokens, behind):
    """The service the API runs: runtime role, registered scorer, its own (lagging) clock."""
    service = Sentinel(runtime_url, FixtureInvestigator(), scenarios.Clock(SEED_NOW - behind),
                       scorer=scenarios.model_scorer())
    return service, service.authenticate(tokens["analyst"])


def post(service, ctx, body):
    return service.ingest(ctx, TransactionInput.model_validate(body))


def assert_fresh(result, record):
    expected = record["expected_scoring"]
    assert result["replayed"] is False
    scoring = result["scoring"]
    for key in ("scoring_kind", "score_semantics", "score", "threshold", "alerted", "model"):
        assert scoring[key] == expected[key], key
    assert scoring["score"] == LIVE_SCORE and scoring["threshold"] == THRESHOLD
    assert scoring["alerted"] is True and scoring["model"]["artifact_sha256"] == ARTIFACT_SHA
    assert scoring["inputs"]["values"] == expected["values"] == F1_LIVE
    assert (scoring["inputs"]["history_rows"], scoring["inputs"]["disclosures_used"],
            scoring["inputs"]["profile_home_currency"]) == (0, 0, "USD")
    assert result["case"]["pins"]["scorer"]["sha256"] == ARTIFACT_SHA
    occurred = ts(record["request_body"]["occurred_at"])
    assert ts(record["profile"]["opened_at"]) == occurred - timedelta(days=400)


@pytest.mark.parametrize("behind", BEHIND)
def test_missing_profile_reaches_its_documented_error_and_stores_nothing(database_url,
                                                                        runtime_url, behind):
    tokens, at = seeded(database_url)
    record = build(database_url, tokens, at, "model_missing_profile")
    service, ctx = api(runtime_url, tokens, behind)
    with pytest.raises(ServiceError) as refused:
        post(service, ctx, record["request_body"])
    assert (refused.value.code, refused.value.status) == ("account_profile_missing", 422)
    assert counts(database_url) == dict.fromkeys(STORED, 0)


@pytest.mark.parametrize("behind", BEHIND)
def test_live_alert_scores_exactly_as_the_artifact_expects(database_url, runtime_url, behind):
    tokens, at = seeded(database_url)
    record = build(database_url, tokens, at, "model_live_alert")
    service, ctx = api(runtime_url, tokens, behind)
    assert_fresh(post(service, ctx, record["request_body"]), record)
    assert counts(database_url) == dict.fromkeys(STORED, 1)


@pytest.mark.parametrize("behind", BEHIND)
def test_on_demand_live_alert_scores_exactly_as_the_artifact_expects(database_url,
                                                                    runtime_url, monkeypatch,
                                                                    behind):
    tokens, _at = seeded(database_url)

    class SeedClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return SEED_NOW.astimezone(tz)
    monkeypatch.setattr(scenarios, "datetime", SeedClock)  # seed_one reads datetime.now
    record = scenarios.seed_one(database_url, tokens, "model_live_alert", 1)
    assert record["request_body"]["external_id"] == "i01-model_live_alert-1"
    service, ctx = api(runtime_url, tokens, behind)
    assert_fresh(post(service, ctx, record["request_body"]), record)
    assert counts(database_url) == dict.fromkeys(STORED, 1)


@pytest.mark.parametrize("behind", BEHIND)
def test_recorded_alert_replays_its_stored_scoring(database_url, runtime_url, behind):
    tokens, at = seeded(database_url)
    record = build(database_url, tokens, at, "model_alert")
    stored = record["expected_scoring"]
    assert stored["score"] == RECORDED_SCORE and stored["threshold"] == THRESHOLD
    assert stored["model"]["artifact_sha256"] == ARTIFACT_SHA
    assert stored["inputs"]["values"] == F1_RECORDED
    assert (stored["inputs"]["currency"], stored["inputs"]["history_rows"],
            stored["inputs"]["disclosures_used"], stored["inputs"]["profile_home_currency"]
            ) == ("GBP", 0, 1, "USD")
    service, ctx = api(runtime_url, tokens, behind)
    replay = post(service, ctx, record["request_body"])
    assert replay["replayed"] is True
    assert replay["transaction"]["id"] == record["transaction_id"]
    assert replay["case"]["id"] == record["case_id"]
    assert {k: replay["scoring"][k] for k in stored} == stored
    assert counts(database_url) == dict.fromkeys(STORED, 1)


def test_the_tolerance_is_finite(database_url, runtime_url):
    """Beyond EVENT_MARGIN the production guard applies unchanged: the margin is a fixture
    precondition, not a relaxed time check."""
    tokens, at = seeded(database_url)
    record = build(database_url, tokens, at, "model_missing_profile")
    service, ctx = api(runtime_url, tokens, timedelta(minutes=5, seconds=1))
    with pytest.raises(ServiceError) as refused:
        post(service, ctx, record["request_body"])
    assert refused.value.code == "future_event_time"
    assert counts(database_url) == dict.fromkeys(STORED, 0)
