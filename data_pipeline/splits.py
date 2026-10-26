"""Chronological split policy with delayed-label eligibility.

Rows are assigned by decision time (ingested_at), never shuffled:
    train:      D <  train_end
    validation: train_end + embargo <= D < validation_end
    test:       validation_end + embargo <= D
Rows inside an embargo gap are dropped, so a model is never evaluated on rows decided just
after its training cutoff with overlapping history windows.

Delayed labels: a model trained at `train_end` may use only labels disclosed by then.
Training rows whose label is not yet known (pending dispute window or never disputed) are
`ineligible` for training, not silently treated as legitimate.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from data_pipeline.features import ts

SPLIT_VERSION = "s1"


@dataclass(frozen=True)
class SplitPolicy:
    train_end: datetime
    validation_end: datetime
    embargo: timedelta = timedelta(days=1)

    def __post_init__(self):
        if not self.train_end < self.validation_end:
            raise ValueError("train_end must precede validation_end")
        if self.embargo < timedelta(0):
            raise ValueError("embargo cannot be negative")

    @classmethod
    def by_fraction(cls, start: datetime, end: datetime, train: float = 0.6,
                    validation: float = 0.2, embargo: timedelta = timedelta(days=1)):
        span = end - start
        return cls(start + span * train, start + span * (train + validation), embargo)

    def to_dict(self) -> dict:
        return {"version": SPLIT_VERSION, "train_end": self.train_end.isoformat(),
                "validation_end": self.validation_end.isoformat(),
                "embargo_seconds": int(self.embargo.total_seconds())}


def label_as_of(label: dict, cutoff: datetime) -> bool | None:
    """True/False if the label was disclosed by `cutoff`, else None (unknown then)."""
    at = label["label_available_at"]
    return label["is_fraud"] if at is not None and ts(at) <= cutoff else None


def split(transactions: list[dict], labels: list[dict], policy: SplitPolicy) -> dict:
    label_of = {label["external_id"]: label for label in labels}
    parts: dict[str, list[str]] = {"train": [], "train_ineligible": [], "validation": [],
                                   "test": [], "embargoed": []}
    for txn in sorted(transactions, key=lambda t: (t["ingested_at"], t["external_id"])):
        decided = ts(txn["ingested_at"])
        ext = txn["external_id"]
        if decided < policy.train_end:
            known = label_as_of(label_of[ext], policy.train_end)
            parts["train" if known is not None else "train_ineligible"].append(ext)
        elif policy.train_end + policy.embargo <= decided < policy.validation_end:
            parts["validation"].append(ext)
        elif decided >= policy.validation_end + policy.embargo:
            parts["test"].append(ext)
        else:
            parts["embargoed"].append(ext)
    return parts
