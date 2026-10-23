import uuid
from datetime import datetime, timezone

from sentinel import scoring
from sentinel.contracts.v1 import Money, Scope, Transaction


def transaction(minor_units, currency="USD", exponent=2):
    return Transaction(
        id=uuid.uuid4(), scope=Scope(tenant_id=uuid.uuid4(), session_id=uuid.uuid4()),
        external_id="t", account_id=uuid.uuid4(), direction="debit",
        amount=Money(currency=currency, minor_units=minor_units, currency_exponent=exponent),
        occurred_at=datetime(2026, 10, 23, tzinfo=timezone.utc),
        ingested_at=datetime(2026, 10, 23, tzinfo=timezone.utc), dataset=scoring.DATASET)


def test_rule_score_components_and_cap():
    assert scoring.rule_score(transaction(1500), 0) == 0.0
    assert scoring.rule_score(transaction(1500), 2) == 0.4
    assert scoring.rule_score(transaction(100_000), 0) == 0.6
    assert scoring.rule_score(transaction(100_000), 10) == 1.0
    assert scoring.rule_score(transaction(150_000, "JPY", 0), 0) == 0.6
    assert scoring.rule_score(transaction(150_000, "INR"), 0) == 0.0


def test_artifacts_are_content_addressed():
    changed = scoring.artifact("velocity-amount-rules", "r1",
                               {**scoring.RULE_CONFIG, "large_amount_points": 0.7})
    assert changed.sha256 != scoring.SCORER.sha256
