"""Safe diagnostics (C05): request IDs, code-only structured events and in-process metrics.

Policy: events carry identifiers, route templates, status codes, durations, outcome codes
and exception *type names* only. Never bearer tokens, header values, query strings, request
or response bodies, exception messages, model context or connection strings; an exception
message can contain any of those (psycopg errors include host and user, for example).
"""
from __future__ import annotations

import json
import logging
import os
import re
import secrets
import sys
import threading
from collections import Counter, defaultdict

REQUEST_ID_HEADER = "X-Request-ID"
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{7,63}$")
LATENCY_BUCKETS_MS = (5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000)
_ALLOWED_FIELDS = {"request_id", "method", "route", "status", "duration_ms", "outcome",
                   "error_type", "case_id", "revision", "run_id", "failure_code", "seconds"}


def request_id(supplied: str | None) -> str:
    """Echo a client ID only if it matches a conservative pattern; otherwise mint a random
    one (secrets, not uuid4: domain-ID generation stays independent of request handling)."""
    if supplied and _SAFE_REQUEST_ID.fullmatch(supplied):
        return supplied
    return secrets.token_hex(16)


def emit(logger: logging.Logger, event: str, level: int = logging.INFO, **fields) -> None:
    """One JSON line. Unknown field names or non-scalar values are a programming error."""
    for key, value in fields.items():
        if key not in _ALLOWED_FIELDS:
            raise ValueError(f"field {key!r} is not on the safe-log allowlist")
        if value is not None and not isinstance(value, (str, int, float, bool)):
            raise TypeError(f"field {key!r} must be a scalar")
    logger.log(level, json.dumps({"event": event, **fields}, sort_keys=False))


def configure_logging() -> None:
    """Attach a stderr handler to the `sentinel` logger once (SENTINEL_LOG_LEVEL, default
    INFO; `off` disables). Uvicorn configures only its own loggers."""
    level = os.environ.get("SENTINEL_LOG_LEVEL", "INFO").upper()
    root = logging.getLogger("sentinel")
    if level == "OFF":
        root.addHandler(logging.NullHandler())
        return
    if not any(getattr(h, "_sentinel", False) for h in root.handlers):
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(message)s"))
        handler._sentinel = True
        root.addHandler(handler)
    root.setLevel(getattr(logging, level, logging.INFO))


class Metrics:
    """Thread-safe counters: requests by method/route/status, latency buckets by route and
    named events. Process-local; exported by snapshot() (no HTTP endpoint in v1)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._requests: Counter[str] = Counter()
        self._latency: dict[str, Counter[str]] = defaultdict(Counter)
        self._events: Counter[str] = Counter()

    def observe(self, method: str, route: str, status: int, duration_ms: float) -> None:
        bucket = next((f"le_{b}" for b in LATENCY_BUCKETS_MS if duration_ms <= b), "gt_5000")
        with self._lock:
            self._requests[f"{method} {route} {status}"] += 1
            self._latency[f"{method} {route}"][bucket] += 1

    def count(self, event: str) -> None:
        with self._lock:
            self._events[event] += 1

    def snapshot(self) -> dict:
        with self._lock:
            return {"requests": dict(self._requests),
                    "latency_ms": {k: dict(v) for k, v in self._latency.items()},
                    "events": dict(self._events)}
