"""C04 label eligibility, feature/label separation, preprocessing isolation, rule parity and
snapshot summary checks."""
import copy
import uuid
from dataclasses import dataclass
from datetime import timedelta

import numpy as np
import pytest

from data_pipeline.features import FEATURE_NAMES
from data_pipeline.generator import EPOCH
from ml import dataset, models, snapshot
from ml import protocol as proto
from sentinel.contracts.v1 import Money, Scope, Transaction
from sentinel.scoring import DATASET, rule_score

PROTOCOL, _ = proto.load()


def iso(day: float) -> str:
    return (EPOCH + timedelta(days=day)).isoformat(timespec="microseconds").replace(
        "+00:00", "Z")


@dataclass
class Snap:
    accounts: list
    transactions: list
    labels: list
    features: list


def row(ext, day, fraud, label_day, scenario="normal", currency="USD", amount=1000):
    txn = {"external_id": ext, "account_id": "acct", "direction": "debit",
           "amount": {"currency": currency, "minor_units": amount,
                      "currency_exponent": 0 if currency == "JPY" else 2},
           "occurred_at": iso(day), "ingested_at": iso(day)}
    label = {"external_id": ext, "is_fraud": fraud, "scenario": scenario,
             "label_available_at": None if label_day is None else iso(label_day)}
    feats = {"external_id": ext, **{n: 1 for n in FEATURE_NAMES}, "amount_minor": amount}
    return txn, label, feats


def snap(rows):
    return Snap([], [r[0] for r in rows], [r[1] for r in rows], [r[2] for r in rows])


def small_rows():
    return [  # train window [10,55), labels known by day 85
        row("t1", 20, True, 30), row("t2", 21, False, 51), row("t3", 22, True, None),
        row("t4", 54, True, 90), row("t5", 30, False, 60),
        # validation [56,85), labels by 115
        row("v1", 60, True, 70), row("v2", 61, False, 91), row("v3", 62, True, 200),
        # test [116,150): synthetic truth
        row("x1", 120, True, None), row("x2", 121, False, 151), row("x3", 122, True, 130),
        # burn-in and embargo gaps never appear
        row("b1", 5, True, 6), row("g1", 55.5, False, 85), row("g2", 100, True, 101)]


def test_train_and_validation_use_only_labels_known_by_their_cutoffs():
    parts = dataset.splits(PROTOCOL, snap(small_rows()))
    train, val, test = parts["train"], parts["validation"], parts["test"]
    assert sorted(train.external_id) == ["t1", "t2", "t5"]  # t3 never, t4 too late: unknown
    assert train.unknown == 2 and dict(zip(train.external_id, train.y)) == {
        "t1": 1, "t2": 0, "t5": 0}  # unknown labels are excluded, never turned into 0
    assert sorted(val.external_id) == ["v1", "v2"] and val.unknown == 1
    # Test is the synthetic-truth view: never-disclosed fraud counts as fraud.
    assert dict(zip(test.external_id, test.y)) == {"x1": 1, "x2": 0, "x3": 1}
    assert test.observable == 1  # only x3's label is disclosed by the day-150 horizon
    all_ids = {*train.external_id, *val.external_id, *test.external_id}
    assert not all_ids & {"b1", "g1", "g2"}


def test_single_class_split_is_refused():
    rows = [r for r in small_rows() if r[0]["external_id"] != "t1"]
    with pytest.raises(dataset.SplitError, match="train"):
        dataset.splits(PROTOCOL, snap(rows))


def test_inputs_hold_only_declared_features_and_ignore_hidden_truth():
    rows = small_rows()
    X = dataset.build_matrix(PROTOCOL, [r[2] for r in rows], [r[0] for r in rows])
    assert X.shape[1] == len(PROTOCOL["features"]) + 1
    assert dataset.input_columns(PROTOCOL)[-1] == "currency"
    changed = copy.deepcopy(rows)
    for txn, label, _ in changed:
        label["is_fraud"] = not label["is_fraud"]
        label["scenario"] = "card_testing"
        label["label_available_at"] = None
    X2 = dataset.build_matrix(PROTOCOL, [r[2] for r in changed], [r[0] for r in changed])
    assert (X == X2).all()
    assert not set(PROTOCOL["excluded_from_inputs"]) & set(dataset.input_columns(PROTOCOL))


def test_preprocessing_is_fitted_on_training_rows_only():
    rng = np.random.default_rng(0)
    n = len(PROTOCOL["features"])

    def matrix(rows, scale):
        X = np.empty((rows, n + 1), dtype=object)
        X[:, :n] = rng.integers(0, 1000, size=(rows, n)) * scale
        X[:, n] = rng.choice(["USD", "GBP", "INR", "JPY"], size=rows)
        return X
    train, y = matrix(200, 1), np.array([0, 1] * 100)
    pipeline = models.build(PROTOCOL, PROTOCOL["candidates"][1]).fit(train, y)
    scaler = pipeline.named_steps["prep"].named_transformers_["numeric"].named_steps["scale"]
    expected = models.signed_log1p(train[:, :n]).mean(axis=0)  # computed independently
    assert np.allclose(scaler.mean_, expected)
    pipeline.predict_proba(matrix(50, 10_000))  # wildly different validation data
    assert np.allclose(scaler.mean_, expected)  # transform only; nothing refitted


@pytest.mark.parametrize("currency, amount, prior", [
    ("USD", 250_000, 0), ("USD", 1500, 2), ("INR", 150_000, 0), ("JPY", 150_000, 4),
    ("GBP", 99_999, 1)])
def test_rule_candidate_matches_the_production_rule(currency, amount, prior):
    names = list(PROTOCOL["features"])
    X = np.empty((1, len(names) + 1), dtype=object)
    X[0, :len(names)] = 0.0
    X[0, names.index("amount_minor")] = float(amount)
    X[0, names.index("count_1h")] = float(prior)
    X[0, len(names)] = currency
    txn = Transaction(
        id=uuid.uuid4(), scope=Scope(tenant_id=uuid.uuid4(), session_id=uuid.uuid4()),
        external_id="r", account_id=uuid.uuid4(), direction="debit",
        amount=Money(currency=currency, minor_units=amount,
                     currency_exponent=0 if currency == "JPY" else 2),
        occurred_at=EPOCH, ingested_at=EPOCH, dataset=DATASET)
    assert models.RuleR1(names).score(X)[0] == rule_score(txn, prior)


def test_snapshot_check_recomputes_summaries_independently():
    rows = small_rows()
    accounts = [{"account_id": "acct"}]
    summary = snapshot.recomputed_summary(accounts, [r[0] for r in rows], [r[1] for r in rows])
    good = {"rows": {"accounts": 1, "transactions": 14, "labels": 14},
            "labels": {"fraud_rows": summary["fraud_rows"],
                       "fraud_never_disclosed": summary["fraud_never_disclosed"],
                       "by_scenario": summary["by_scenario"]},
            "currencies": summary["currencies"]}
    assert snapshot.check(good, summary) == []
    for path, value in ((("rows", "accounts"), 2), (("labels", "fraud_rows"), 0),
                        (("labels", "fraud_never_disclosed"), 99)):
        bad = copy.deepcopy(good)
        bad[path[0]][path[1]] = value
        assert snapshot.check(bad, summary), path  # verify() alone would not notice
