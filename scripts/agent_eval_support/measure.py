"""Measurements read after an attempt's outcome (G3D-P4a). None of them waits on, cancels
or joins a worker, patches coordinator timing, or adds production instrumentation.

- Recorded role intervals: differences of the cumulative `elapsed_ms` markers of a role's
  `role_started` and its `role_completed`/`role_failed` (same agent_run_id). They include
  persistence and validation; they are not provider latency.
- Capacity: the attempt's own service instance's `capacity.snapshot()`, read once right
  after the request returned (this process, this instance only).
- Late returns: `agent_worker_returned` events the coordinator already logs, observed in
  this process up to a stated cutoff. A late return after the cutoff is unknown, not zero.
"""
from __future__ import annotations

import json
import logging
import threading
import time

LATE_EVENT = "agent_worker_returned"
AGENT_LOGGER = "sentinel.agents"


def role_intervals(steps: list[dict]) -> list[dict]:
    """One entry per role_started step, in step order, paired with its end marker."""
    ends = {}
    for step in steps:
        if step.get("kind") in ("role_completed", "role_failed") and step.get("agent_run_id"):
            ends[step["agent_run_id"]] = step
    intervals = []
    for step in steps:
        if step.get("kind") != "role_started":
            continue
        end = ends.get(step.get("agent_run_id"))
        entry = {"agent_run_id": step.get("agent_run_id"), "role": step.get("role"),
                 "attempt": step.get("attempt"), "start_marker_ms": step.get("elapsed_ms"),
                 "end_kind": end["kind"] if end else None,
                 "failure_code": end.get("failure_code") if end else None,
                 "worker_unresolved": bool(end and end.get("worker_unresolved")),
                 # A budget refusal after the start record is the R35 pre-submission path:
                 # nothing was submitted to the adapter.
                 "pre_submission": bool(end and end.get("failure_code") == "budget_exhausted"),
                 "label": "recorded step interval (includes persistence/validation; "
                          "not provider latency)"}
        if end is None:
            entry["interval_ms"], entry["status"] = None, "unknown (no end marker)"
        else:
            entry["interval_ms"] = end["elapsed_ms"] - step["elapsed_ms"]
            entry["status"] = "recorded"
        intervals.append(entry)
    return intervals


def capacity_observation(service, request_returned: float) -> dict:
    snapshot = service.capacity.snapshot()
    return {**snapshot, "scope": "this attempt's service instance in this process",
            "observed_after_return_s": round(time.monotonic() - request_returned, 3),
            "note": "not provider-wide; other services/processes are not observed"}


class LateReturnObserver(logging.Handler):
    """Collects the coordinator's existing late-return log events while active. Restores
    the logger's level and handlers on close; never changes what is logged elsewhere."""

    def __init__(self):
        super().__init__(level=logging.INFO)
        self.events: list[dict] = []
        self._lock_events = threading.Lock()
        self.cutoff: float | None = None

    def emit(self, record: logging.LogRecord) -> None:
        try:
            event = json.loads(record.getMessage())
        except (TypeError, ValueError):
            return
        if isinstance(event, dict) and event.get("event") == LATE_EVENT:
            with self._lock_events:
                self.events.append({"workflow_id": event.get("workflow_id"),
                                    "role": event.get("role"), "attempt": event.get("attempt"),
                                    "seconds": event.get("seconds")})

    def __enter__(self):
        self.logger = logging.getLogger(AGENT_LOGGER)
        self._level = self.logger.level
        if self.logger.getEffectiveLevel() > logging.INFO:
            self.logger.setLevel(logging.INFO)
        self.logger.addHandler(self)
        return self

    def __exit__(self, *exc):
        self.cutoff = time.monotonic()
        self.logger.removeHandler(self)
        self.logger.setLevel(self._level)
        return False

    def for_workflows(self, workflow_ids: list[str]) -> list[dict]:
        with self._lock_events:
            return [e for e in self.events if e["workflow_id"] in set(workflow_ids)]
