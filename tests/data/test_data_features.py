"""C03: features use only history available at decision time; future rows and future labels
cannot change them."""
import copy
import random
from dataclasses import replace

import pytest

from data_pipeline import fixtures
from data_pipeline.features import (
    FEATURE_NAMES, availability_key, batch_features, online_features,
)
from data_pipeline.generator import generate

MID = replace(fixtures.TINY, seed=5, accounts=80, days=10)


@pytest.fixture(scope="module")
def mid():
    return generate(MID)


def test_batch_equals_online_replay(mid):
    batch = batch_features(mid.transactions, mid.accounts, mid.labels)
    assert batch == online_features(mid.transactions, mid.accounts, mid.labels)
    assert set(batch[0]) == {"external_id", *FEATURE_NAMES}


def test_future_rows_cannot_change_features(mid):
    full = {f["external_id"]: f for f in batch_features(mid.transactions, mid.accounts,
                                                        mid.labels)}
    rng = random.Random(0)
    for txn in rng.sample(mid.transactions, 40):
        key = availability_key(txn)
        past = [t for t in mid.transactions if availability_key(t) <= key]
        only_past = {f["external_id"]: f for f in batch_features(past, mid.accounts, mid.labels)}
        assert only_past[txn["external_id"]] == full[txn["external_id"]]


def test_late_arriving_older_event_is_excluded_until_it_arrives(mid):
    account = mid.accounts[0]["account_id"]
    base = {"account_id": account, "direction": "debit",
            "amount": {"currency": mid.accounts[0]["home_currency"], "minor_units": 1000,
                       "currency_exponent": 0 if mid.accounts[0]["home_currency"] == "JPY" else 2}}
    decision = {**base, "external_id": "z-decision", "occurred_at": "2026-09-05T12:00:00.000000Z",
                "ingested_at": "2026-09-05T12:00:05.000000Z"}
    late = {**base, "external_id": "z-late", "occurred_at": "2026-09-05T11:30:00.000000Z",
            "ingested_at": "2026-09-05T18:00:00.000000Z"}
    after = {**base, "external_id": "z-after", "occurred_at": "2026-09-05T18:10:00.000000Z",
             "ingested_at": "2026-09-05T18:10:01.000000Z"}
    rows = [t for t in mid.transactions if t["account_id"] != account] + [decision, late, after]
    feats = {f["external_id"]: f for f in batch_features(rows, mid.accounts)}
    without = {f["external_id"]: f for f in batch_features(
        [r for r in rows if r is not late], mid.accounts)}
    assert feats["z-decision"] == without["z-decision"]  # not yet available at decision
    assert feats["z-after"]["count_24h"] == without["z-after"]["count_24h"] + 1  # later, it is


def test_same_timestamp_events_are_excluded_regardless_of_arrival(mid):
    account = mid.accounts[1]
    cur = account["home_currency"]
    exp = 0 if cur == "JPY" else 2
    a = {"external_id": "s-a", "account_id": account["account_id"], "direction": "debit",
         "amount": {"currency": cur, "minor_units": 500, "currency_exponent": exp},
         "occurred_at": "2026-09-06T09:00:00.000000Z",
         "ingested_at": "2026-09-06T09:00:01.000000Z"}
    b = {**a, "external_id": "s-b", "ingested_at": "2026-09-06T09:00:02.000000Z"}
    rows = [t for t in mid.transactions if t["account_id"] != account["account_id"]] + [a, b]
    feats = {f["external_id"]: f for f in batch_features(rows, mid.accounts)}
    assert feats["s-b"]["count_1h"] == 0 and feats["s-a"]["count_1h"] == 0


def test_future_labels_cannot_change_features(mid):
    base = {f["external_id"]: f for f in batch_features(mid.transactions, mid.accounts,
                                                        mid.labels)}
    decision = {t["external_id"]: t["ingested_at"] for t in mid.transactions}
    rng = random.Random(1)
    for target in rng.sample(mid.transactions, 25):
        cutoff = decision[target["external_id"]]
        changed = copy.deepcopy(mid.labels)
        for label in changed:  # rewrite every label not yet disclosed at this decision
            if label["label_available_at"] is None or label["label_available_at"] > cutoff:
                label["is_fraud"] = not label["is_fraud"]
                label["label_available_at"] = "2027-01-01T00:00:00.000000Z"
        again = {f["external_id"]: f for f in batch_features(mid.transactions, mid.accounts,
                                                             changed)}
        assert again[target["external_id"]] == base[target["external_id"]]


def test_disclosed_fraud_label_is_counted_after_disclosure_only(mid):
    account = mid.accounts[2]["account_id"]
    rows = sorted((t for t in mid.transactions if t["account_id"] == account),
                  key=availability_key)
    assert len(rows) >= 3
    first, later = rows[0], rows[-1]
    labels = [dict(label, is_fraud=False) for label in mid.labels]
    for label in labels:
        if label["external_id"] == first["external_id"]:
            label.update(is_fraud=True, label_available_at=later["ingested_at"])
    feats = {f["external_id"]: f for f in batch_features(mid.transactions, mid.accounts, labels)}
    assert feats[later["external_id"]]["prior_known_fraud"] == 1  # disclosed at decision time
    assert feats[rows[1]["external_id"]]["prior_known_fraud"] == 0  # decided before disclosure


def test_currency_specific_aggregates(mid):
    feats = batch_features(mid.transactions, mid.accounts)
    assert all(f["same_currency_sum_24h"] >= 0 and f["amount_to_median_bps"] >= -1
               for f in feats)
