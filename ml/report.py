"""Small reviewable outputs from the frozen test report: CSV tables, a PR-curve SVG drawn
from its own CSV source data, and a markdown summary. No values are typed in by hand."""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
from sklearn.metrics import precision_recall_curve


def _csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _svg(path: Path, points: list[tuple[float, float]], title: str) -> None:
    w, h, pad = 420, 320, 40
    xy = " ".join(f"{pad + r * (w - 2 * pad):.1f},{h - pad - p * (h - 2 * pad):.1f}"
                  for r, p in points)
    path.write_bytes((  # bytes, not text mode: identical LF output on every platform
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}" font-family="sans-serif" font-size="11">\n'
        f'<rect width="{w}" height="{h}" fill="white"/>\n'
        f'<text x="{pad}" y="20">{title}</text>\n'
        f'<line x1="{pad}" y1="{h - pad}" x2="{w - pad}" y2="{h - pad}" stroke="black"/>\n'
        f'<line x1="{pad}" y1="{pad}" x2="{pad}" y2="{h - pad}" stroke="black"/>\n'
        f'<text x="{w / 2 - 20}" y="{h - 10}">recall</text>\n'
        f'<text x="5" y="{h / 2}">precision</text>\n'
        f'<polyline points="{xy}" fill="none" stroke="#1f6feb" stroke-width="1.5"/>\n'
        f'</svg>\n').encode("utf-8"))


def write(out: Path, protocol, selection, document, split, scores) -> None:
    out.mkdir(parents=True, exist_ok=True)
    _csv(out / "slices.csv", document["slices_daily_top_k"])
    _csv(out / "reliability.csv", document["calibration"]["reliability"])
    _csv(out / "candidates.csv", [
        {"name": c["name"], "kind": c["kind"],
         "validation_ap": v["validation"]["average_precision"],
         "test_ap": c["test"]["average_precision"],
         "test_pr_auc_trapezoid": c["test"]["pr_auc_trapezoid"],
         "test_topk_precision": c["test"]["daily_top_k"]["precision"],
         "test_topk_recall": c["test"]["daily_top_k"]["recall"],
         "test_topk_fp": c["test"]["daily_top_k"]["fp"]}
        for c, v in zip(document["candidates"], selection["candidates"])])
    precision, recall, _ = precision_recall_curve(split.y, scores)
    keep = np.unique(np.linspace(0, len(recall) - 1, 200).astype(int))
    curve = [{"recall": round(float(recall[i]), 6), "precision": round(float(precision[i]), 6)}
             for i in keep]
    _csv(out / "pr_curve_selected.csv", curve)
    _svg(out / "pr_curve_selected.svg", [(c["recall"], c["precision"]) for c in curve],
         f"Test PR curve, {document['selected']} (synthetic data; source: pr_curve_selected.csv)")
    pol, unc = document["selected_policy"], document["uncertainty"]
    lines = [
        f"# C04 frozen test report ({protocol['protocol_version']})", "",
        "Generated from test_report.json. Synthetic data; offline benchmark only.", "",
        f"- Protocol sha256: `{document['protocol_sha256']}`",
        f"- Selected on validation AP: **{document['selected']}**; artifact sha256 "
        f"`{document['artifact_sha256']}`",
        f"- Test rows {document['split']['rows']}, fraud {document['split']['fraud']} "
        f"(synthetic truth; {document['split']['labels_observable_by_horizon']} labels "
        "observable by the horizon end)", "",
        "| Candidate | Val AP | Test AP | Test PR-AUC (trapezoid) | Top-k precision | "
        "Top-k recall | Top-k FP |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for c, v in zip(document["candidates"], selection["candidates"]):
        t = c["test"]
        lines.append(f"| {c['name']} | {v['validation']['average_precision']} | "
                     f"{t['average_precision']} | {t['pr_auc_trapezoid']} | "
                     f"{t['daily_top_k']['precision']} | {t['daily_top_k']['recall']} | "
                     f"{t['daily_top_k']['fp']} |")
    lines += ["", f"Daily top-{protocol['review_policy']['k_per_day']} (selected): "
              f"{pol['daily_top_k']}", "",
              f"Frozen threshold {document['frozen_threshold']} (from validation): "
              f"{pol['frozen_threshold']}", "",
              f"Account bootstrap ({unc['replicates']} reps, {unc['accounts']} accounts, "
              f"{unc['skipped_one_class']} skipped): AP {unc['average_precision']}, "
              f"recall@capacity {unc['recall_at_capacity']}, precision@capacity "
              f"{unc['precision_at_capacity']}", "",
              f"Brier {document['calibration']['brier']} (scores are not calibrated "
              "probabilities).", ""]
    (out / "report.md").write_bytes("\n".join(lines).encode("utf-8"))
