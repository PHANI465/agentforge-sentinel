"""Versioned evaluator artifacts (G3D-P4a): constants, rates, quantiles and validation.

A run artifact is the JSON `scripts/agent_eval.py` prints. Version 1 adds identity,
provenance and measurement fields to the G3D-P1 report without removing any field; an
artifact without `record.artifact_version` is a pre-P4a report and is never read as if it
carried the new measurements. Validation refuses (raises ArtifactError) rather than drops.
"""
from __future__ import annotations

import hashlib
import json
import math

RUN_VERSION = "sentinel.agent-eval.run/1"
BUNDLE_VERSION = "sentinel.agent-eval.bundle/1"
PACKETS_VERSION = "sentinel.agent-eval.review-packets/1"
SUMMARY_VERSION = "sentinel.agent-eval.summary/1"
PILOT_VERSION = "sentinel.agent-eval.pilot/1"

# Worst-case application adapter/CLI-invocation reservations per attempt (accepted P4
# plan §2): one for the single live investigator, the pinned max_role_invocations (5) for
# the live workflow, none for deterministic comparators. Not provider requests or billing.
RESERVATIONS = {"C0": 0, "C2-det": 0, "C1": 1, "C2": 5}
LIVE = frozenset({"C1", "C2"})
WORKFLOW_COMPARATORS = frozenset({"C2", "C2-det"})
OUTCOMES = ("disposition", "inconclusive", "refused", "pending", "error")
UNKNOWN = "unknown"


class ArtifactError(ValueError):
    """An artifact is missing, of another version, inconsistent or censored."""


def rate(numerator: int, denominator: int) -> dict:
    """A rate with its counts; a zero denominator is `n/a (0/0)`, never 0 % or 100 %."""
    text = f"n/a ({numerator}/{denominator})" if denominator == 0 else \
        f"{numerator}/{denominator} ({numerator / denominator:.3f})"
    return {"numerator": numerator, "denominator": denominator,
            "value": None if denominator == 0 else numerator / denominator, "text": text}


def nearest_rank(values: list[float], p: float) -> float | None:
    """Nearest-rank quantile: the ceil(p*n)-th smallest value (1-based), p in (0, 1].
    None for an empty sample. p=1 is the maximum."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(1, math.ceil(p * len(ordered))) - 1]


def latency_summary(values: list[float]) -> dict:
    return {"n": len(values), "convention": "nearest-rank: ceil(p*n)-th smallest",
            "unit": "seconds (monotonic, around svc.investigate)",
            "p50": nearest_rank(values, 0.5), "p95": nearest_rank(values, 0.95),
            "max": nearest_rank(values, 1.0)}


def digest(doc: dict) -> str:
    """SHA-256 of a document's canonical JSON (sorted keys, compact): ties bundles, keys
    and summaries to the exact run artifact they came from."""
    return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()
                          ).hexdigest()


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise ArtifactError(reason)


def validate_run(doc: dict) -> dict:
    """Check a version-1 run artifact for shape and accounting integrity; return it.

    Integrity: every comparator's attempts plus `cases_not_attempted` are exactly the
    planned cases, in order; attempt indices are contiguous from 1; counts agree with the
    rows. A censored (removed) attempt therefore fails here instead of vanishing."""
    _require(isinstance(doc, dict) and isinstance(doc.get("record"), dict),
             "not a run artifact")
    record = doc["record"]
    _require(record.get("artifact_version") == RUN_VERSION,
             f"unsupported artifact version {record.get('artifact_version')!r} "
             f"(expected {RUN_VERSION}; pre-P4a reports carry no P4a measurements)")
    planned = record.get("planned_cases")
    _require(isinstance(planned, list) and planned, "record.planned_cases missing")
    comparators = doc.get("comparators")
    _require(isinstance(comparators, dict), "comparators missing")
    started = set(comparators) | set(record.get("comparators_not_started") or [])
    _require(started == set(record.get("planned_comparators") or []),
             "planned comparators are not all accounted for")
    for name, result in comparators.items():
        rows = result.get("attempts")
        _require(isinstance(rows, list), f"{name}: attempts missing")
        cases = [row.get("case") for row in rows] + list(result.get("cases_not_attempted", []))
        _require(cases == planned, f"{name}: attempts and cases_not_attempted do not equal "
                                   "the planned cases (an attempt is missing or extra)")
        _require([row.get("index") for row in rows] == list(range(1, len(rows) + 1)),
                 f"{name}: attempt indices are not contiguous")
        for row in rows:
            _require(row.get("outcome") in OUTCOMES, f"{name}: unknown outcome")
            _require(row.get("attempt_id") == f"{name}:{row['index']}:{row['case']}",
                     f"{name}: attempt id does not match its comparator/index/case")
            _require(row.get("workflow_elapsed_ms") is None,
                     f"{name}: workflow_elapsed_ms must stay null (not measured)")
        counts = result.get("counts", {})
        _require(counts.get("attempts") == len(rows), f"{name}: attempt count mismatch")
        tally = {o: sum(r["outcome"] == o for r in rows) for o in OUTCOMES}
        tally["dispositions"] = tally.pop("disposition")
        _require({k: v for k, v in tally.items() if v} ==
                 {k: v for k, v in counts.items() if k != "attempts"},
                 f"{name}: outcome counts do not match the attempt rows")
    if record.get("status") == "complete":
        _require(record.get("stopped") is None and not record.get("comparators_not_started"),
                 "a complete record cannot have stopped")
    return doc
