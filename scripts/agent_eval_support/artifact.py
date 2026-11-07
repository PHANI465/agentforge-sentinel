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


STATUSES = ("complete", "incomplete")
REFUSED_CODE = "agent_capacity_exhausted"
PENDING_CODES = frozenset({"investigation_in_progress", "investigation_outcome_unknown"})
TELEMETRY = ("read", "unavailable", "not_read")
AWAITING = "awaiting_approval"
# The review sheet's columns; each generated row is bound to its packet in the key (R47).
SHEET_COLUMNS = ("packet_id", "item", "kind", "text", "supported", "acceptable",
                 "reason_code", "would_correct", "correction")


def text_digest(text) -> str:
    """SHA-256 of a sheet cell's text as written; binds a returned sheet to its packets."""
    return hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def _check_row(name: str, row: dict) -> None:
    """Outcome, code, case state, disposition and telemetry must tell one story (R46).

    Consistency only: an unsigned file can still be edited coherently. Nothing is
    inferred: a pending row may carry the stored state found afterwards but stays pending,
    and a disposition whose telemetry could not be read has an unknown recommendation."""
    outcome, label = row.get("outcome"), f"{name} attempt {row.get('attempt_id')}"
    _require(outcome in OUTCOMES, f"{name}: unknown outcome")
    telemetry = (row.get("telemetry") or {}).get("status")
    _require(telemetry is None or telemetry in TELEMETRY,
             f"{label}: unknown telemetry status {telemetry!r}")
    _require(telemetry != "not_read" or outcome == "error",
             f"{label}: telemetry is 'not_read' only for an error outcome")
    disposition, state, code = row.get("disposition"), row.get("case_state"), row.get("code")
    _require(disposition is None or isinstance(disposition, dict),
             f"{label}: disposition must be an object or null")
    if outcome == "disposition":
        _require(code is None, f"{label}: a disposition outcome carries no refusal/error code")
        _require(state is None or state == AWAITING,
                 f"{label}: a disposition outcome needs case state {AWAITING}")
        if telemetry == "unavailable":
            _require(disposition is None, f"{label}: a disposition outcome cannot carry a "
                                          "disposition read while telemetry was unavailable")
        else:
            _require(disposition is not None, f"{label}: a disposition outcome without its "
                                              "recorded disposition (telemetry was read)")
    elif outcome == "inconclusive":
        _require(code is None, f"{label}: an inconclusive outcome carries no code")
        _require(state != AWAITING,
                 f"{label}: an inconclusive outcome cannot be {AWAITING}")
        _require(disposition is None,
                 f"{label}: an inconclusive outcome has no adopted disposition")
        _require(isinstance(row.get("failure_codes", []), list),
                 f"{label}: inconclusive failure_codes must be a list")
    elif outcome == "refused":
        _require(code == REFUSED_CODE, f"{label}: a refused outcome needs code {REFUSED_CODE}")
        _require(disposition is None and state is None,
                 f"{label}: a refused (admission) outcome has no case state or disposition")
        attempts = row.get("recorded_role_attempts")
        _require(not isinstance(attempts, int) or attempts == 0,
                 f"{label}: a refused (admission) outcome recorded role attempts")
    elif outcome == "pending":
        _require(code in PENDING_CODES, f"{label}: a pending outcome needs a pending code")
    else:  # error: outside the typed paths; its telemetry is never read
        _require(isinstance(code, str) and bool(code) and code != REFUSED_CODE
                 and code not in PENDING_CODES,
                 f"{label}: an error outcome needs a non-typed error code")
        _require(disposition is None,
                 f"{label}: an error outcome has no recorded disposition")
    if disposition is not None:
        workflow = name in WORKFLOW_COMPARATORS
        kinds = ("recommend", "abstain") if workflow else (None,)
        _require(disposition.get("kind") in kinds,
                 f"{label}: disposition kind {disposition.get('kind')!r} does not fit the "
                 "comparator")
        source = disposition.get("source")
        expected = "workflow_disposition" if workflow else "single_investigator_finding"
        _require(source is None or source == expected,
                 f"{label}: disposition source {source!r} does not fit the comparator kind")


def _check_stop(record: dict, comparators: dict) -> None:
    """Accounting on both sides of the attempted / not-attempted boundary (R46)."""
    status, stopped = record.get("status"), record.get("stopped")
    _require(status in STATUSES, f"unknown record status {status!r}")
    not_started = list(record.get("comparators_not_started") or [])
    names = list(comparators)
    short = [n for n, r in comparators.items() if r.get("cases_not_attempted")]
    if status == "complete":
        _require(stopped is None and not not_started,
                 "a complete record cannot have stopped")
        _require(not short, "a complete record has cases not attempted: " + ", ".join(short))
        return
    _require(isinstance(stopped, dict) and isinstance(stopped.get("comparator"), str)
             and isinstance(stopped.get("phase"), str) and "case" in stopped,
             "an incomplete record must say where it stopped")
    if stopped["phase"] == "comparator":  # the comparator itself was never built
        _require(stopped["case"] is None and not_started[:1] == [stopped["comparator"]],
                 "the stopped comparator is not the first one not started")
        _require(not short, "cases not attempted on a comparator that was not stopped: "
                 + ", ".join(short))
        return
    _require(bool(names) and names[-1] == stopped["comparator"],
             "the stopped comparator is not the last one that ran")
    rest = comparators[stopped["comparator"]].get("cases_not_attempted") or []
    _require(rest[:1] == [stopped["case"]],
             "the stopped case is not the first case not attempted")
    _require(short == [stopped["comparator"]],
             "cases not attempted on a comparator that was not stopped: "
             + ", ".join(n for n in short if n != stopped["comparator"]))


def validate_run(doc: dict) -> dict:
    """Check a version-1 run artifact for shape and accounting integrity; return it.

    Integrity: every comparator's attempts plus `cases_not_attempted` are exactly the
    planned cases, in order; attempt indices are contiguous from 1; counts agree with the
    rows; each row's outcome, code, case state and disposition agree; a complete record has nothing not attempted, and an incomplete one
    says exactly where it stopped. A censored, relabelled or recounted attempt therefore
    fails here instead of vanishing. This checks consistency of an editable, unsigned file;
    it is not tamper-proofing."""
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
    not_started = list(record.get("comparators_not_started") or [])
    started = set(comparators) | set(not_started)
    _require(started == set(record.get("planned_comparators") or []),
             "planned comparators are not all accounted for")
    _require(list(comparators) + not_started == list(record.get("planned_comparators")),
             "comparators did not run in the planned order")
    for name, result in comparators.items():
        rows = result.get("attempts")
        _require(isinstance(rows, list), f"{name}: attempts missing")
        cases = [row.get("case") for row in rows] + list(result.get("cases_not_attempted", []))
        _require(cases == planned, f"{name}: attempts and cases_not_attempted do not equal "
                                   "the planned cases (an attempt is missing or extra)")
        _require([row.get("index") for row in rows] == list(range(1, len(rows) + 1)),
                 f"{name}: attempt indices are not contiguous")
        for row in rows:
            _check_row(name, row)
            _require(row.get("attempt_id") == f"{name}:{row['index']}:{row['case']}",
                     f"{name}: attempt id does not match its comparator/index/case")
            _require(row.get("workflow_elapsed_ms") is None,
                     f"{name}: workflow_elapsed_ms must stay null (not measured)")
        counts = result.get("counts", {})
        _require(counts.get("attempts") == len(rows), f"{name}: attempt count mismatch")
        tally = {o: sum(r["outcome"] == o for r in rows) for o in OUTCOMES}
        tally["dispositions"] = tally.pop("disposition")
        _require({k: v for k, v in tally.items() if v} ==
                 {k: v for k, v in counts.items() if k != "attempts" and v},
                 f"{name}: outcome counts do not match the attempt rows")
        # Latency lists and inconclusive codes are recomputed from the rows by the scorer;
        # the runner's copies of them are never read, so they are not cross-checked here.
    _check_stop(record, comparators)
    return doc
