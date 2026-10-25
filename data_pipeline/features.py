"""Historical-only features at decision time.

Decision time for a transaction is its availability key `(ingested_at, external_id)`: the
system decides when the row arrives, and rows arriving at the same instant are ordered by
external_id (a serialized stream, as in the API's per-account lock).

A prior row is usable iff (a) it belongs to the same account, (b) its availability key is
strictly before this row's, and (c) its event time is in [t - window, t) — events at exactly
t are excluded regardless of arrival order (matching the service's velocity rule).
A label is usable iff its label_available_at <= this row's ingested_at.

`batch_features` filters a complete dataset by those rules; `online_features` replays events
in arrival order and only ever sees the past. Tests require both to agree exactly.
"""
from __future__ import annotations

import bisect
import statistics
from collections import defaultdict
from datetime import datetime, timedelta

from data_pipeline.generator import CURRENCIES

FEATURE_VERSION = "f1"
FEATURE_NAMES = (
    "amount_minor", "is_credit", "is_foreign_currency", "account_age_days",
    "count_1h", "count_24h", "small_count_1h", "same_currency_sum_24h",
    "credit_sum_24h", "seconds_since_prev", "amount_to_median_bps", "prior_known_fraud",
)
MEDIAN_WINDOW = timedelta(days=30)
SMALL_USD = 5  # "small" means below 5 USD-equivalent in the row's own currency


def ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def availability_key(txn: dict) -> tuple[str, str]:
    return (txn["ingested_at"], txn["external_id"])


def _small_limit(currency: str) -> int:
    exponent, per_usd, _ = CURRENCIES[currency]
    return round(SMALL_USD * per_usd * 10 ** exponent)


def compute(txn: dict, account: dict, history: list[dict], known_fraud: int) -> dict:
    """Features from `history` (already restricted to usable rows, any order)."""
    t = ts(txn["occurred_at"])
    currency = txn["amount"]["currency"]
    amount = txn["amount"]["minor_units"]
    window = [h for h in history if t - MEDIAN_WINDOW <= ts(h["occurred_at"]) < t]
    hour = [h for h in window if ts(h["occurred_at"]) >= t - timedelta(hours=1)]
    day = [h for h in window if ts(h["occurred_at"]) >= t - timedelta(days=1)]
    same = [h["amount"]["minor_units"] for h in window if h["amount"]["currency"] == currency]
    previous = max((ts(h["occurred_at"]) for h in window), default=None)
    median = statistics.median(same) if same else None
    return {
        "external_id": txn["external_id"],
        "amount_minor": amount,
        "is_credit": int(txn["direction"] == "credit"),
        "is_foreign_currency": int(currency != account["home_currency"]),
        "account_age_days": (t - ts(account["opened_at"])).days,
        "count_1h": len(hour),
        "count_24h": len(day),
        "small_count_1h": sum(h["amount"]["minor_units"] < _small_limit(h["amount"]["currency"])
                              for h in hour),
        "same_currency_sum_24h": sum(h["amount"]["minor_units"] for h in day
                                     if h["amount"]["currency"] == currency),
        "credit_sum_24h": sum(h["amount"]["minor_units"] for h in day
                              if h["direction"] == "credit" and h["amount"]["currency"] == currency),
        "seconds_since_prev": int((t - previous).total_seconds()) if previous else -1,
        # Integer basis points avoid float formatting differences; -1 means no history.
        "amount_to_median_bps": int(amount * 10_000 // median) if median else -1,
        "prior_known_fraud": known_fraud,
    }


def batch_features(transactions: list[dict], accounts: list[dict],
                   labels: list[dict] | None = None) -> list[dict]:
    """Features for every transaction, in input order, using only usable history."""
    by_account: dict[str, list[dict]] = defaultdict(list)
    for txn in transactions:
        by_account[txn["account_id"]].append(txn)
    for rows in by_account.values():
        rows.sort(key=lambda r: r["occurred_at"])
    occurred = {a: [r["occurred_at"] for r in rows] for a, rows in by_account.items()}
    account_of = {a["account_id"]: a for a in accounts}
    fraud_labels: dict[str, list[tuple[str, str]]] = defaultdict(list)  # account -> (avail, id)
    if labels:
        txn_account = {t["external_id"]: t["account_id"] for t in transactions}
        for label in labels:  # labels for rows outside this set cannot inform it
            if (label["is_fraud"] and label["label_available_at"] is not None
                    and label["external_id"] in txn_account):
                fraud_labels[txn_account[label["external_id"]]].append(
                    (label["label_available_at"], label["external_id"]))
    out = []
    for txn in transactions:
        rows = by_account[txn["account_id"]]
        t = ts(txn["occurred_at"])
        lo = bisect.bisect_left(occurred[txn["account_id"]],
                                _iso_like(t - MEDIAN_WINDOW, txn["occurred_at"]))
        key = availability_key(txn)
        history = [r for r in rows[lo:] if r["occurred_at"] < txn["occurred_at"]
                   and availability_key(r) < key]
        known = sum(1 for at, ext in fraud_labels[txn["account_id"]]
                    if at <= txn["ingested_at"] and ext != txn["external_id"])
        out.append(compute(txn, account_of[txn["account_id"]], history, known))
    return out


def online_features(transactions: list[dict], accounts: list[dict],
                    labels: list[dict] | None = None) -> list[dict]:
    """Replay arrivals (and label disclosures) in time order; returns features in input order."""
    account_of = {a["account_id"]: a for a in accounts}
    txn_account = {t["external_id"]: t["account_id"] for t in transactions}
    # Label at time T is known to a decision at time T (label events sort first on ties).
    events = [(t["ingested_at"], 1, t["external_id"], t) for t in transactions]
    for label in labels or []:
        if (label["is_fraud"] and label["label_available_at"] is not None
                and label["external_id"] in txn_account):
            events.append((label["label_available_at"], 0, label["external_id"], None))
    events.sort(key=lambda e: e[:3])
    seen: dict[str, list[dict]] = defaultdict(list)
    known: dict[str, int] = defaultdict(int)
    result: dict[str, dict] = {}
    for _, kind, external_id, txn in events:
        if kind == 0:
            known[txn_account[external_id]] += 1
            continue
        result[external_id] = compute(txn, account_of[txn["account_id"]],
                                      seen[txn["account_id"]], known[txn["account_id"]])
        seen[txn["account_id"]].append(txn)
    return [result[t["external_id"]] for t in transactions]


def _iso_like(value: datetime, template: str) -> str:
    """Format a bound in the dataset's fixed-width timestamp style for string bisection."""
    text = value.isoformat(timespec="microseconds").replace("+00:00", "Z")
    assert len(text) == len(template), "timestamps must use the fixed-width generator format"
    return text
