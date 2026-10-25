"""Metric and policy definitions (C04).

- average_precision: sklearn's step-wise AP = sum_n (R_n - R_{n-1}) P_n. Not the trapezoidal
  PR-AUC, which interpolates linearly and is reported separately.
- daily_top_k: per UTC decision day, rank by score descending with ties by external_id
  ascending, flag the first k. This is a batch review queue.
- frozen_threshold: the score at rank k x (validation decision days) over validation,
  applied unchanged elsewhere; rows with score >= threshold are flagged (ties at the
  threshold are all flagged, so the flagged count can exceed the nominal capacity).
"""
from __future__ import annotations

import numpy as np
from sklearn.metrics import auc, average_precision_score, precision_recall_curve


def average_precision(y, scores) -> float:
    return float(average_precision_score(y, scores))


def pr_auc_trapezoid(y, scores) -> float:
    precision, recall, _ = precision_recall_curve(y, scores)
    return float(auc(recall, precision))


def rank_order(scores, ids) -> np.ndarray:
    """Indices sorted by score descending, then external_id ascending."""
    return np.lexsort((np.asarray(ids, dtype=str), -np.asarray(scores, dtype=float)))


def daily_top_k(scores, ids, days, k: int) -> np.ndarray:
    scores, ids, days = np.asarray(scores, float), np.asarray(ids, str), np.asarray(days)
    flagged = np.zeros(len(scores), dtype=bool)
    for day in np.unique(days):
        members = np.flatnonzero(days == day)
        order = members[rank_order(scores[members], ids[members])]
        flagged[order[:k]] = True
    return flagged


def frozen_threshold(scores, ids, n_days: int, k: int) -> float:
    order = rank_order(scores, ids)
    position = min(k * n_days, len(order)) - 1
    return float(np.asarray(scores, float)[order[position]])


def at_policy(y, flagged) -> dict:
    y, flagged = np.asarray(y, int), np.asarray(flagged, bool)
    tp = int(np.sum(flagged & (y == 1)))
    fp = int(np.sum(flagged & (y == 0)))
    fn = int(np.sum(~flagged & (y == 1)))
    tn = int(np.sum(~flagged & (y == 0)))
    return {"flagged": tp + fp, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": round(tp / (tp + fp), 6) if tp + fp else None,
            "recall": round(tp / (tp + fn), 6) if tp + fn else None,
            "false_positive_rate": round(fp / (fp + tn), 6) if fp + tn else None}


def brier(y, scores) -> float:
    return float(np.mean((np.asarray(scores, float) - np.asarray(y, float)) ** 2))


def reliability(y, scores, bins: int = 10) -> list[dict]:
    y, scores = np.asarray(y, float), np.asarray(scores, float)
    edges = np.linspace(0.0, 1.0, bins + 1)
    index = np.clip(np.digitize(scores, edges[1:-1], right=False), 0, bins - 1)
    out = []
    for b in range(bins):
        members = index == b
        n = int(members.sum())
        out.append({"lo": round(float(edges[b]), 2), "hi": round(float(edges[b + 1]), 2),
                    "n": n,
                    "mean_score": round(float(scores[members].mean()), 6) if n else None,
                    "fraud_rate": round(float(y[members].mean()), 6) if n else None})
    return out


def bootstrap(y, scores, flagged, accounts, replicates: int, seed: int,
              interval=(0.025, 0.975)) -> dict:
    """Account-level resampling: rows of one account stay together, so correlated episode
    rows are not treated as independent. Replicates without both classes are skipped
    (counted), never silently imputed."""
    y, scores = np.asarray(y, int), np.asarray(scores, float)
    flagged, accounts = np.asarray(flagged, bool), np.asarray(accounts, str)
    unique, inverse = np.unique(accounts, return_inverse=True)
    groups = [np.flatnonzero(inverse == g) for g in range(len(unique))]
    rng = np.random.default_rng(seed)
    ap, recall, precision, skipped = [], [], [], 0
    for _ in range(replicates):
        picked = rng.integers(0, len(groups), size=len(groups))
        rows = np.concatenate([groups[g] for g in picked])
        yr = y[rows]
        if yr.min() == yr.max():
            skipped += 1
            continue
        ap.append(average_precision(yr, scores[rows]))
        stats = at_policy(yr, flagged[rows])
        recall.append(stats["recall"])
        if stats["precision"] is not None:
            precision.append(stats["precision"])

    def ci(values):
        if not values:
            return None
        lo, hi = np.quantile(values, interval)
        return [round(float(lo), 6), round(float(hi), 6)]
    return {"replicates": replicates, "skipped_one_class": skipped, "accounts": len(groups),
            "average_precision": ci(ap), "recall_at_capacity": ci(recall),
            "precision_at_capacity": ci(precision)}


def slices(split, flagged, feature_names) -> list[dict]:
    """Offline error slices. Scenario is hidden synthetic truth: slice dimension only."""
    count_24h = split.X[:, feature_names.index("count_24h")].astype(float)
    activity = np.where(count_24h == 0, "0", np.where(count_24h <= 2, "1-2", "3+"))
    week = (split.decision_day - split.decision_day.min()) // 7
    dims = {"currency": split.X[:, len(feature_names)].astype(str),
            "scenario": split.scenario.astype(str), "activity_count_24h": activity,
            "test_week": week.astype(str)}
    out = []
    for dim, values in dims.items():
        for value in sorted(set(values.tolist())):
            members = values == value
            stats = at_policy(split.y[members], flagged[members])
            out.append({"dimension": dim, "value": value, "rows": int(members.sum()),
                        "fraud": int(split.y[members].sum()), **stats})
    return out
