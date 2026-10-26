"""Frozen offline model results (C07), built only from packaged server-owned C04 files.

The only accepted results id is "p1". There is no path parameter into the filesystem: the
id selects a registry entry, and the files are the packaged byte copies of the frozen C04
report (verified equal to evals/ml/p1 by tests).
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from sentinel.scorers import REGISTRY, ScorerError, ml_root

RESULTS = {"p1": "hgb_balanced@p1"}
LIMITATIONS = [
    "Synthetic data from one seeded generator world (C03 g1, seed 7); not real transactions.",
    "Test labels are synthetic truth, including never-disclosed fraud a real institution "
    "would not observe; validation used only labels known by day 115.",
    "Model scores are uncalibrated ranking scores, not fraud probabilities.",
    "Daily top-k is an offline batch policy; online alerts use the frozen threshold.",
    "Small positive counts (109 test fraud rows); see the account-bootstrap intervals.",
    "No claim of real-bank effectiveness, savings or production efficacy.",
]


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load(results_id: str) -> dict | None:
    if results_id not in RESULTS:
        return None
    accepted = REGISTRY[RESULTS[results_id]]
    root = ml_root()
    from ml import protocol as proto

    protocol = _json(root / "protocol.json")
    selection = _json(root / "runs" / accepted.protocol_version / "selection.json")
    report = _json(root / "results" / results_id / "test_report.json")
    if (proto.digest(protocol) != accepted.protocol_sha256
            or proto.digest(selection) != accepted.selection_sha256
            or report["selection_sha256"] != accepted.selection_sha256
            or report["artifact_sha256"] != accepted.artifact_sha256):
        raise ScorerError("packaged results do not match the accepted identity")
    with (root / "results" / results_id / "pr_curve_selected.csv").open(encoding="utf-8") as f:
        curve = [{"recall": float(r["recall"]), "precision": float(r["precision"])}
                 for r in csv.DictReader(f)]
    validation = {c["name"]: c["validation"] for c in selection["candidates"]}
    candidates = [{
        "name": c["name"], "kind": c["kind"],
        "validation_average_precision": validation[c["name"]]["average_precision"],
        "test_average_precision": c["test"]["average_precision"],
        "test_pr_auc_trapezoid": c["test"]["pr_auc_trapezoid"],
        "test_daily_top_k": c["test"]["daily_top_k"], "test_brier": c["test"].get("brier"),
    } for c in report["candidates"]]
    unc = report["uncertainty"]
    windows = {k: v for k, v in protocol["windows"].items() if not k.startswith("_")}
    views = {name: json.dumps(view, sort_keys=True)
             for name, view in protocol["label_views"].items()}
    return {
        "results_id": results_id, "label": "offline synthetic benchmark", "synthetic": True,
        "protocol_version": protocol["protocol_version"],
        "protocol_sha256": accepted.protocol_sha256,
        "selection_sha256": accepted.selection_sha256,
        "artifact_sha256": accepted.artifact_sha256, "selected": report["selected"],
        "windows": windows, "label_views": views,
        "review_k_per_day": protocol["review_policy"]["k_per_day"],
        "review_ranking": protocol["review_policy"]["ranking"],
        "frozen_threshold": report["frozen_threshold"],
        "splits": {**selection["splits"], "test": report["split"]},
        "candidates": candidates,
        "selected_policy": {"daily_top_k": report["selected_policy"]["daily_top_k"],
                            "frozen_threshold": report["selected_policy"]["frozen_threshold"]},
        "uncertainty": {"method": protocol["uncertainty"]["method"],
                        "replicates": unc["replicates"], "accounts": unc["accounts"],
                        "skipped_one_class": unc["skipped_one_class"],
                        "average_precision": unc["average_precision"],
                        "recall_at_capacity": unc["recall_at_capacity"],
                        "precision_at_capacity": unc["precision_at_capacity"]},
        "calibration": report["calibration"], "slices": report["slices_daily_top_k"],
        "pr_curve": curve, "limitations": LIMITATIONS,
    }
