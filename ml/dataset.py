"""Protocol splits, as-of label eligibility and the model input matrix.

Inputs contain only the protocol's decision-time features (f1) plus currency. Identifiers,
timestamps, scenario, fraud truth and label-availability metadata never enter X; they are
kept alongside for ranking ties, per-day capacity and offline-only slices.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from data_pipeline.features import ts
from data_pipeline.splits import label_as_of

from ml import protocol as proto


class SplitError(RuntimeError):
    pass


@dataclass
class Split:
    name: str
    X: np.ndarray            # object array: numeric features..., currency
    y: np.ndarray            # 0/1 under this split's label view
    external_id: np.ndarray
    account_id: np.ndarray
    decision_day: np.ndarray  # integer UTC day index from epoch (decision time)
    scenario: np.ndarray      # offline-only slice dimension; never an input
    unknown: int              # rows in the window excluded because their label is unknown
    observable: int | None = None  # test only: labels observable by the horizon end


def input_columns(protocol: dict) -> list[str]:
    return list(protocol["features"]) + list(protocol["categorical_features"])


def build_matrix(protocol: dict, feature_rows: list[dict], transactions: list[dict]
                 ) -> np.ndarray:
    """X for the given rows: f1 features (as float) then currency. Nothing else."""
    by_id = {t["external_id"]: t for t in transactions}
    names = list(protocol["features"])
    X = np.empty((len(feature_rows), len(names) + 1), dtype=object)
    for i, row in enumerate(feature_rows):
        X[i, :len(names)] = [float(row[n]) for n in names]
        X[i, len(names)] = by_id[row["external_id"]]["amount"]["currency"]
    return X


def splits(protocol: dict, snapshot, names=("train", "validation", "test")
           ) -> dict[str, Split]:
    """Assign rows by decision time to the named splits with the protocol label views. Only
    the requested splits are built, so selection never reads test labels at all."""
    label_of = {label["external_id"]: label for label in snapshot.labels}
    txn_of = {t["external_id"]: t for t in snapshot.transactions}
    epoch = proto.day(protocol, 0)
    horizon = proto.day(protocol, protocol["generator"]["days"])
    out = {}
    for name in names:
        start, end = proto.window(protocol, name)
        view = protocol["label_views"][name]
        cutoff = (proto.day(protocol, view["labels_known_by_day"])
                  if "labels_known_by_day" in view else None)
        chosen, y, unknown, observable = [], [], 0, 0
        for row in snapshot.features:
            txn = txn_of[row["external_id"]]
            decided = ts(txn["ingested_at"])
            if not start <= decided < end:
                continue
            label = label_of[row["external_id"]]
            if cutoff is not None:
                known = label_as_of(label, cutoff)
                if known is None:
                    unknown += 1
                    continue
                y.append(int(known))
            else:  # synthetic-truth offline view (test)
                y.append(int(label["is_fraud"]))
                if label_as_of(label, horizon) is not None:
                    observable += 1
            chosen.append(row)
        if not chosen:
            raise SplitError(f"{name} split is empty")
        y_arr = np.asarray(y, dtype=int)
        if y_arr.min() == y_arr.max():
            raise SplitError(f"{name} split has a single class under its label view")
        ids = [r["external_id"] for r in chosen]
        out[name] = Split(
            name=name, X=build_matrix(protocol, chosen, snapshot.transactions), y=y_arr,
            external_id=np.asarray(ids, dtype=object),
            account_id=np.asarray([txn_of[i]["account_id"] for i in ids], dtype=object),
            decision_day=np.asarray([(ts(txn_of[i]["ingested_at"]) - epoch).days for i in ids]),
            scenario=np.asarray([label_of[i]["scenario"] for i in ids], dtype=object),
            unknown=unknown, observable=observable if cutoff is None else None)
    return out


def describe(split: Split) -> dict:
    return {"rows": int(len(split.y)), "fraud": int(split.y.sum()),
            "legitimate": int(len(split.y) - split.y.sum()),
            "unknown_excluded": int(split.unknown),
            "decision_days": int(len(set(split.decision_day.tolist()))),
            **({"labels_observable_by_horizon": int(split.observable)}
               if split.observable is not None else {})}
