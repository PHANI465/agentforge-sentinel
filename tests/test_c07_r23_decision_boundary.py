"""C07 review R23: operator writes (account profiles, fraud disclosures) and model decisions
share one scoped account decision boundary. A write that commits after a decision captured
its time T never enters that decision; it does enter later eligible decisions; stored
replays never change. Real connections and commits; bounded gates instead of sleeps."""
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import psycopg
import pytest
from pydantic import ValidationError

from sentinel import db, scorers
from sentinel.contracts.v1 import ScoringOutcome, TransactionInput
from sentinel.investigators import DeterministicInvestigator
from sentinel.service import Sentinel, ServiceError
from test_thin_path import ANALYST

MODEL = scorers.ModelScorer(scorers.REGISTRY["hgb_balanced@p1"])
T = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)
SECOND = timedelta(seconds=1)
ACCOUNT = "00000000-0000-4000-8000-00000000c001"
WAIT = 30  # an upper bound for each step; success never depends on it


class Clock:
    """A test clock; when armed, the next read blocks until released (a gate placed exactly
    where the code under test reads its decision or write time)."""

    def __init__(self, now):
        self.now = now
        self.armed = False
        self.entered = threading.Event()
        self.release = threading.Event()

    def __call__(self):
        if self.armed:
            self.armed = False
            self.entered.set()
            if not self.release.wait(WAIT):
                raise AssertionError("clock gate was never released")
        return self.now


def wait_until(predicate, what):
    deadline = time.monotonic() + WAIT
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError(f"timed out waiting for {what}")
        time.sleep(0.01)  # polling an observed database state, bounded above


def advisory_waiters(database_url) -> int:
    with psycopg.connect(database_url, autocommit=True) as conn:
        return conn.execute(
            "SELECT count(*) FROM pg_locks l JOIN pg_database d ON d.oid = l.database"
            " WHERE l.locktype = 'advisory' AND NOT l.granted"
            " AND d.datname = current_database()").fetchone()[0]


def pause_scoring(service):
    """Pause model ingestion after it captured T (and holds its lock), before any model
    feature query."""
    entered, release = threading.Event(), threading.Event()
    original = service._model_score

    def paused(*args):
        entered.set()
        if not release.wait(WAIT):
            raise AssertionError("scoring pause was never released")
        return original(*args)

    service._model_score = paused
    return entered, release


def txn(external_id, at, account=ACCOUNT):
    return TransactionInput.model_validate({
        "external_id": external_id, "account_id": account, "direction": "debit",
        "amount": {"currency": "USD", "minor_units": 250_000, "currency_exponent": 2},
        "occurred_at": at.isoformat()})


def profile(currency, account=ACCOUNT):
    return {"account_id": account, "home_currency": currency,
            "opened_at": "2026-01-01T00:00:00Z"}


def disclosure(external_id, disclosed_at, account=ACCOUNT):
    return {"external_id": external_id, "account_id": account, "is_fraud": True,
            "disclosed_at": disclosed_at.isoformat()}


def operator(database_url, now):
    return Sentinel(database_url, DeterministicInvestigator(), Clock(now))


def setup(database_url, variant):
    """A scope with, unless the variant creates it, a USD profile and one genuinely eligible
    disclosure recorded an hour before T."""
    op = operator(database_url, T - timedelta(hours=1))
    _, ctx = op.create_session(ANALYST)
    scope = (ctx.scope.tenant_id, ctx.scope.session_id)
    if variant != "new_profile":
        op.provision_accounts(*scope, [profile("USD")])
        op.record_disclosures(*scope, [disclosure("old-fraud", T - timedelta(hours=2))])
    return ctx, scope


def write(service, scope, variant):
    if variant == "disclosure":  # backdated: disclosed the previous day, recorded now
        return service.record_disclosures(*scope, [disclosure("late", T - timedelta(days=1))])
    return service.provision_accounts(*scope, [profile("GBP")])


def check_before(result, variant):
    """The decision at T saw only data available by T."""
    if variant == "new_profile":
        assert isinstance(result, ServiceError) and result.code == "account_profile_missing"
        return
    inputs = result["scoring"]["inputs"]
    assert inputs["profile_home_currency"] == "USD"
    assert inputs["disclosures_used"] == 1  # the eligible one, not the late one
    assert inputs["values"]["prior_known_fraud"] == 1


def check_after(result, variant):
    """A later decision sees the committed write."""
    inputs = result["scoring"]["inputs"]
    if variant == "disclosure":
        assert inputs["disclosures_used"] == 2 and inputs["profile_home_currency"] == "USD"
    elif variant == "profile_update":
        assert inputs["profile_home_currency"] == "GBP" and inputs["disclosures_used"] == 1
    else:
        assert inputs["profile_home_currency"] == "GBP" and inputs["disclosures_used"] == 0


def outcome_of(fn):
    try:
        return fn()
    except ServiceError as error:
        return error


VARIANTS = ["disclosure", "profile_update", "new_profile"]


@pytest.mark.parametrize("variant", VARIANTS)
def test_write_committed_after_decision_time_does_not_enter_it(database_url, variant):
    ctx, scope = setup(database_url, variant)
    decider = Sentinel(database_url, DeterministicInvestigator(), Clock(T), scorer=MODEL)
    entered, release = pause_scoring(decider)
    writer = operator(database_url, T + SECOND)
    with ThreadPoolExecutor(2) as pool:
        decision = pool.submit(outcome_of, lambda: decider.ingest(ctx, txn("d1", T)))
        assert entered.wait(WAIT), "ingestion never reached scoring"
        written = pool.submit(write, writer, scope, variant)
        wait_until(lambda: written.done() or advisory_waiters(database_url) >= 1,
                   "the operator write to commit or wait")
        writer_waited = not written.done()
        # The pre-lock clock value must not be what is recorded: the write time is read only
        # once the decision has released the account.
        writer.clock.now = T + 3 * SECOND
        release.set()
        first = decision.result(WAIT)
        written.result(WAIT)
    check_before(first, variant)
    assert writer_waited, "the operator write did not wait for the in-flight decision"
    with db.connect(database_url) as conn:
        table, column = (("fraud_disclosures", "recorded_at") if variant == "disclosure"
                         else ("account_profiles", "provisioned_at"))
        stamped = conn.execute(f"SELECT max({column}) AS t FROM {table}").fetchone()["t"]
    assert stamped == T + 3 * SECOND

    later = Sentinel(database_url, DeterministicInvestigator(), Clock(T + 5 * SECOND),
                     scorer=MODEL)
    check_after(later.ingest(ctx, txn("d2", T + 4 * SECOND)), variant)
    if variant != "new_profile":  # the stored decision is replayed unchanged
        replay = later.ingest(ctx, txn("d1", T))
        assert replay["replayed"] is True and replay["scoring"] == first["scoring"]
    else:  # nothing was stored for the refused decision; it is now scored afresh
        assert later.ingest(ctx, txn("d1", T))["replayed"] is False


@pytest.mark.parametrize("variant", VARIANTS)
def test_decision_waits_for_an_inflight_write_and_then_includes_it(database_url, variant):
    ctx, scope = setup(database_url, variant)
    writer = operator(database_url, T)
    writer.clock.armed = True  # blocks at the write-time read
    decider = Sentinel(database_url, DeterministicInvestigator(), Clock(T + SECOND),
                       scorer=MODEL)
    with ThreadPoolExecutor(2) as pool:
        written = pool.submit(write, writer, scope, variant)
        assert writer.clock.entered.wait(WAIT), "the writer never read its write time"
        decision = pool.submit(outcome_of, lambda: decider.ingest(ctx, txn("d1", T)))
        wait_until(lambda: decision.done() or advisory_waiters(database_url) >= 1,
                   "the decision to finish or wait")
        decision_waited = not decision.done()
        writer.clock.release.set()
        written.result(WAIT)
        result = decision.result(WAIT)
    assert not isinstance(result, ServiceError), result
    check_after(result, variant)
    assert decision_waited, "the decision did not wait for the in-flight write"


def test_disclosure_recorded_after_decision_time_is_unavailable(database_url):
    """Even a committed disclosure counts only once recorded by the decision time (e.g. an
    operator clock ahead of the API's); its disclosed_at alone is not availability."""
    ctx, scope = setup(database_url, "disclosure")
    operator(database_url, T + 10 * SECOND).record_disclosures(
        *scope, [disclosure("ahead", T - timedelta(days=1))])
    at_t = Sentinel(database_url, DeterministicInvestigator(), Clock(T), scorer=MODEL)
    assert at_t.ingest(ctx, txn("d1", T))["scoring"]["inputs"]["disclosures_used"] == 1
    later = Sentinel(database_url, DeterministicInvestigator(), Clock(T + 11 * SECOND),
                     scorer=MODEL)
    assert later.ingest(ctx, txn("d2", T + 11 * SECOND))["scoring"]["inputs"][
        "disclosures_used"] == 2


def test_future_disclosed_at_stays_excluded(database_url):
    ctx, scope = setup(database_url, "disclosure")
    operator(database_url, T - SECOND).record_disclosures(
        *scope, [disclosure("future", T + timedelta(days=1))])
    decider = Sentinel(database_url, DeterministicInvestigator(), Clock(T), scorer=MODEL)
    assert decider.ingest(ctx, txn("d1", T))["scoring"]["inputs"]["disclosures_used"] == 1


def test_another_sessions_write_does_not_wait_for_this_decision(database_url):
    ctx, _ = setup(database_url, "profile_update")
    op = operator(database_url, T - SECOND)
    _, other = op.create_session(ANALYST, tenant_id=ctx.scope.tenant_id)
    other_scope = (other.scope.tenant_id, other.scope.session_id)
    decider = Sentinel(database_url, DeterministicInvestigator(), Clock(T), scorer=MODEL)
    entered, release = pause_scoring(decider)
    with ThreadPoolExecutor(2) as pool:
        decision = pool.submit(decider.ingest, ctx, txn("d1", T))
        assert entered.wait(WAIT)
        try:  # same account id, other session: an independent boundary
            assert operator(database_url, T + SECOND).provision_accounts(
                *other_scope, [profile("GBP")]) == 1
            assert advisory_waiters(database_url) == 0
        finally:
            release.set()
        assert decision.result(WAIT)["scoring"]["inputs"]["profile_home_currency"] == "USD"


def test_batches_lock_accounts_in_one_global_order(database_url):
    ctx, scope = setup(database_url, "profile_update")
    accounts = [str(uuid.UUID(int=0xC0DE0000 + i, version=4)) for i in range(6)]
    with db.connect(database_url) as conn, conn.transaction():
        forward = Sentinel._lock_accounts(conn, *scope, accounts)
    with db.connect(database_url) as conn, conn.transaction():
        backward = Sentinel._lock_accounts(conn, *scope, list(reversed(accounts)) + accounts)
    assert forward == backward == sorted(forward) and len(forward) == len(accounts)


def test_overlapping_batches_serialize_without_deadlock(database_url):
    ctx, scope = setup(database_url, "profile_update")
    other = "00000000-0000-4000-8000-00000000c002"
    first = operator(database_url, T)
    first.clock.armed = True
    second = operator(database_url, T + SECOND)
    with ThreadPoolExecutor(2) as pool:
        a = pool.submit(first.provision_accounts, *scope,
                        [profile("INR", ACCOUNT), profile("INR", other)])
        assert first.clock.entered.wait(WAIT)
        b = pool.submit(second.provision_accounts, *scope,
                        [profile("JPY", other), profile("JPY", ACCOUNT)])
        wait_until(lambda: b.done() or advisory_waiters(database_url) >= 1,
                   "the second batch to finish or wait")
        second_waited = not b.done()
        first.clock.release.set()
        assert a.result(WAIT) == 2 and b.result(WAIT) == 2
    assert second_waited
    with db.connect(database_url) as conn:
        rows = conn.execute("SELECT home_currency, provisioned_at FROM account_profiles"
                            " WHERE account_id = ANY(%s)", ([ACCOUNT, other],)).fetchall()
    assert {(r["home_currency"], r["provisioned_at"]) for r in rows} == {("JPY", T + SECOND)}


@pytest.mark.parametrize("partial", ["model", "inputs"])
def test_rule_outcome_with_partial_model_payload_is_rejected(partial):
    base = {
        "transaction_id": str(uuid.uuid4()),
        "scope": {"tenant_id": str(uuid.uuid4()), "session_id": str(uuid.uuid4())},
        "scored_at": T.isoformat(), "features_as_of": T.isoformat(),
        "scorer": MODEL.scorer.model_dump(mode="json"),
        "features": MODEL.features.model_dump(mode="json"),
        "threshold_policy": MODEL.threshold_policy.model_dump(mode="json"),
        "scoring_kind": "rule", "score_semantics": "heuristic", "score": 0.6,
        "threshold": 0.5, "alerted": True, "prior_count_1h": 0}
    ScoringOutcome.model_validate(base)  # a plain rule outcome is valid
    extra = {"model": MODEL.model.model_dump(mode="json"),
             "inputs": {"feature_version": "f1",
                        "values": dict.fromkeys(MODEL.protocol["features"], 0),
                        "currency": "USD", "history_rows": 0, "disclosures_used": 0,
                        "profile_home_currency": "USD",
                        "profile_opened_at": "2026-01-01T00:00:00Z"}}
    with pytest.raises(ValidationError, match="model outcomes"):
        ScoringOutcome.model_validate({**base, partial: extra[partial]})


def test_oversized_batch_is_refused_before_any_lock_or_write(database_url):
    from sentinel.service import MAX_LOCKED_ACCOUNTS
    _, scope = setup(database_url, "new_profile")
    rows = [profile("USD", str(uuid.UUID(int=0xBA7C0000 + i, version=4)))
            for i in range(MAX_LOCKED_ACCOUNTS + 1)]
    with pytest.raises(ServiceError, match="batch_too_large"):
        operator(database_url, T).provision_accounts(*scope, rows)
    with db.connect(database_url) as conn:
        assert conn.execute("SELECT count(*) AS n FROM account_profiles").fetchone()["n"] == 0
