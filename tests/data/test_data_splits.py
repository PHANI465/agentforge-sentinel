"""C03: chronological split with embargo and delayed-label training eligibility."""
from datetime import timedelta

import pytest

from data_pipeline import fixtures
from data_pipeline.features import ts
from data_pipeline.generator import EPOCH, generate
from data_pipeline.splits import SplitPolicy, label_as_of, split


@pytest.fixture(scope="module")
def data():
    return generate(fixtures.REFERENCE)


@pytest.fixture(scope="module")
def policy():
    return SplitPolicy.by_fraction(EPOCH, EPOCH + timedelta(days=fixtures.REFERENCE.days))


def test_partitions_are_disjoint_complete_and_chronological(data, policy):
    parts = split(data.transactions, data.labels, policy)
    decided = {t["external_id"]: ts(t["ingested_at"]) for t in data.transactions}
    ids = [x for p in parts.values() for x in p]
    assert len(ids) == len(set(ids)) == len(data.transactions)
    train = parts["train"] + parts["train_ineligible"]
    assert max(decided[x] for x in train) < policy.train_end
    assert min(decided[x] for x in parts["validation"]) >= policy.train_end + policy.embargo
    assert max(decided[x] for x in parts["validation"]) < policy.validation_end
    assert min(decided[x] for x in parts["test"]) >= policy.validation_end + policy.embargo
    assert parts["embargoed"]  # the gap is real, not empty by accident


def test_training_uses_only_labels_known_at_train_end(data, policy):
    parts = split(data.transactions, data.labels, policy)
    label_of = {label["external_id"]: label for label in data.labels}
    assert all(label_as_of(label_of[x], policy.train_end) is not None for x in parts["train"])
    assert all(label_as_of(label_of[x], policy.train_end) is None
               for x in parts["train_ineligible"])
    # Legitimate rows mature after 30 days, so with an 18-day train window most are pending.
    assert len(parts["train_ineligible"]) > len(parts["train"])


def test_test_set_keeps_natural_prevalence(data, policy):
    parts = split(data.transactions, data.labels, policy)
    label_of = {label["external_id"]: label for label in data.labels}
    fraud = sum(label_of[x]["is_fraud"] for x in parts["test"])
    assert 0 < fraud < len(parts["test"]) * 0.05


def test_label_as_of_and_policy_validation():
    label = {"external_id": "x", "is_fraud": True, "scenario": "card_testing",
             "label_available_at": "2026-09-10T00:00:00.000000Z"}
    assert label_as_of(label, ts("2026-09-09T23:59:59Z")) is None
    assert label_as_of(label, ts("2026-09-10T00:00:00Z")) is True
    assert label_as_of({**label, "label_available_at": None}, ts("2027-01-01T00:00:00Z")) is None
    with pytest.raises(ValueError):
        SplitPolicy(EPOCH, EPOCH)
    with pytest.raises(ValueError):
        SplitPolicy(EPOCH, EPOCH + timedelta(days=1), embargo=timedelta(seconds=-1))
