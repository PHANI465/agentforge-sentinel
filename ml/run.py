"""C04 stages: snapshot -> select (train + validation only) -> test (once, frozen).

`select` never reads test labels. `test` refuses to run unless the protocol digest, data
provenance and selection record match, and writes its report once; `--reproduce` recomputes
everything and compares it with the stored report without rewriting it.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ml import artifact, dataset, evaluate, models, report
from ml import protocol as proto
from ml import snapshot as snap


class StageError(RuntimeError):
    pass


@dataclass
class Paths:
    protocol: Path
    data: Path          # generated dataset (git-ignored)
    run: Path           # selection record + provenance (tracked)
    artifacts: Path     # trusted root for saved models (tracked, small)
    evals: Path         # frozen test report (tracked)

    @classmethod
    def default(cls, version: str = "p1") -> "Paths":
        root = proto.ROOT
        return cls(protocol=root / "ml" / "protocol.json",
                   data=root / "data" / "generated" / f"c04-{version}",
                   run=root / "ml" / "runs" / version,
                   artifacts=root / "ml" / "artifacts",
                   evals=root / "evals" / "ml" / version)


def _write(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _deterministic(provenance: dict) -> dict:
    return {k: v for k, v in provenance.items() if k != "runtime"}


def _fit_and_score(protocol, parts, names):
    """Fit every candidate on train; return {name: (model, val_scores, fit_s, score_s)}."""
    out = {}
    for candidate in protocol["candidates"]:
        if names is not None and candidate["name"] not in names:
            continue
        model = models.build(protocol, candidate)
        started = time.perf_counter()
        model.fit(parts["train"].X, parts["train"].y)
        fitted = time.perf_counter() - started
        started = time.perf_counter()
        val = models.scores(model, parts["validation"].X)
        out[candidate["name"]] = (model, val, fitted, time.perf_counter() - started)
    return out


def _policy_metrics(split, scores, k: int, threshold: float | None) -> dict:
    top_k = evaluate.daily_top_k(scores, split.external_id, split.decision_day, k)
    result = {"average_precision": round(evaluate.average_precision(split.y, scores), 6),
              "pr_auc_trapezoid": round(evaluate.pr_auc_trapezoid(split.y, scores), 6),
              "daily_top_k": evaluate.at_policy(split.y, top_k)}
    if threshold is not None:
        result["frozen_threshold"] = evaluate.at_policy(split.y, scores >= threshold)
    return result


def select(paths: Paths) -> dict:
    protocol, digest = proto.load(paths.protocol)
    started = time.perf_counter()
    snapshot, provenance = snap.build(protocol, paths.data)
    parts = dataset.splits(protocol, snapshot, names=("train", "validation"))
    fitted = _fit_and_score(protocol, parts, None)
    k = protocol["review_policy"]["k_per_day"]
    val = parts["validation"]
    candidates, timings = [], {}
    for candidate in protocol["candidates"]:
        name = candidate["name"]
        model, scores, fit_s, score_s = fitted[name]
        metrics = _policy_metrics(val, scores, k, None)
        if candidate["kind"] != "rule":
            metrics["brier"] = round(evaluate.brier(val.y, scores), 6)
        candidates.append({"name": name, "kind": candidate["kind"], "validation": metrics})
        timings[name] = {"fit_seconds": round(fit_s, 3), "score_seconds": round(score_s, 3)}
    best = max(range(len(candidates)),
               key=lambda i: (candidates[i]["validation"]["average_precision"], -i))
    chosen = protocol["candidates"][best]
    model, scores = fitted[chosen["name"]][0], fitted[chosen["name"]][1]
    n_days = len(set(val.decision_day.tolist()))
    threshold = evaluate.frozen_threshold(scores, val.external_id, n_days, k)
    manifest = artifact.save(paths.artifacts / protocol["protocol_version"], model, {
        "candidate": chosen, "protocol_version": protocol["protocol_version"],
        "protocol_sha256": digest, "feature_version": protocol["feature_version"],
        "features": list(protocol["features"]),
        "categorical_features": protocol["categorical_features"],
        "random_seed": protocol["random_seed"], "data": _deterministic(provenance),
        "training_label_view": protocol["label_views"]["train"],
        "train_split": dataset.describe(parts["train"]),
        "frozen_threshold": threshold, "review_policy": protocol["review_policy"],
        "score_semantics": "uncalibrated model score" if chosen["kind"] != "rule"
                           else "rule heuristic (not a probability)"})
    selection = {
        "protocol_version": protocol["protocol_version"], "protocol_sha256": digest,
        "data": _deterministic(provenance),
        "splits": {name: dataset.describe(s) for name, s in parts.items()},
        "candidates": candidates, "selected": chosen["name"],
        "selection_rule": protocol["selection"],
        "frozen_threshold": threshold, "validation_decision_days": n_days,
        "artifact_sha256": manifest["artifact_sha256"],
        "artifact_manifest": f"{protocol['protocol_version']}/{artifact.MANIFEST_FILE}",
    }
    _write(paths.run / "selection.json", selection)
    _write(paths.run / "select_stats.json", {
        "snapshot_runtime": provenance["runtime"], "candidates": timings,
        "stage_seconds": round(time.perf_counter() - started, 2),
        "peak_rss_mib": snap.peak_rss_mib(), "environment": artifact.environment()})
    return selection


def test(paths: Paths, reproduce: bool = False) -> dict:
    protocol, digest = proto.load(paths.protocol)
    selection_path = paths.run / "selection.json"
    if not selection_path.exists():
        raise StageError("no frozen selection record; run select first")
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    if selection["protocol_sha256"] != digest:
        raise StageError("protocol changed after selection; test access refused")
    report_path = paths.evals / "test_report.json"
    if report_path.exists() and not reproduce:
        raise StageError("the frozen test report already exists; use --reproduce to verify it")
    started = time.perf_counter()
    snapshot, provenance = snap.build(protocol, paths.data)
    if _deterministic(provenance) != selection["data"]:
        raise StageError("data snapshot differs from the one used for selection")
    parts = dataset.splits(protocol, snapshot)
    fitted = _fit_and_score(protocol, parts, None)
    for record in selection["candidates"]:  # the refit must reproduce validation exactly
        got = round(evaluate.average_precision(parts["validation"].y,
                                               fitted[record["name"]][1]), 6)
        if got != record["validation"]["average_precision"]:
            raise StageError(f"refit of {record['name']} does not reproduce validation AP")
    saved, manifest = artifact.load_trusted(
        paths.artifacts / selection["artifact_manifest"], paths.artifacts, protocol)
    test_split, k = parts["test"], protocol["review_policy"]["k_per_day"]
    selected_scores = models.scores(saved, test_split.X)
    refit_scores = models.scores(fitted[selection["selected"]][0], test_split.X)
    if not np.allclose(selected_scores, refit_scores, rtol=0, atol=1e-12):
        raise StageError("saved artifact predictions differ from the deterministic refit")
    threshold = selection["frozen_threshold"]
    results = []
    for candidate in protocol["candidates"]:
        name = candidate["name"]
        scores = selected_scores if name == selection["selected"] else \
            models.scores(fitted[name][0], test_split.X)
        metrics = _policy_metrics(test_split, scores, k,
                                  threshold if name == selection["selected"] else None)
        if candidate["kind"] != "rule":
            metrics["brier"] = round(evaluate.brier(test_split.y, scores), 6)
        results.append({"name": name, "kind": candidate["kind"], "test": metrics})
    top_k = evaluate.daily_top_k(selected_scores, test_split.external_id,
                                 test_split.decision_day, k)
    uncertainty = protocol["uncertainty"]
    document = {
        "protocol_version": protocol["protocol_version"], "protocol_sha256": digest,
        "selection_sha256": artifact.sha256(selection_path),
        "label_view": protocol["label_views"]["test"],
        "split": dataset.describe(test_split), "selected": selection["selected"],
        "frozen_threshold": threshold, "candidates": results,
        "selected_policy": {
            "daily_top_k": evaluate.at_policy(test_split.y, top_k),
            "frozen_threshold": evaluate.at_policy(test_split.y, selected_scores >= threshold),
            "confusion_matrix_frozen_threshold": evaluate.at_policy(
                test_split.y, selected_scores >= threshold)},
        "calibration": {"brier": round(evaluate.brier(test_split.y, selected_scores), 6),
                        "reliability": evaluate.reliability(test_split.y, selected_scores),
                        "note": protocol["calibration"]},
        "uncertainty": evaluate.bootstrap(test_split.y, selected_scores, top_k,
                                          test_split.account_id, uncertainty["replicates"],
                                          uncertainty["seed"], tuple(uncertainty["interval"])),
        "slices_daily_top_k": evaluate.slices(test_split, top_k, list(protocol["features"])),
        "artifact_sha256": manifest["artifact_sha256"],
    }
    if reproduce:
        stored = json.loads(report_path.read_text(encoding="utf-8"))
        same = stored == json.loads(json.dumps(document))
        return {"reproduced": same}
    _write(report_path, document)
    report.write(paths.evals, protocol, selection, document, test_split, selected_scores)
    _write(paths.evals / "test_stats.json", {
        "stage_seconds": round(time.perf_counter() - started, 2),
        "peak_rss_mib": snap.peak_rss_mib(), "environment": artifact.environment()})
    return document
