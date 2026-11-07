"""AN01-M1 measurement prototype: report SQL, request rules, budget adapter and fixtures.

Measurement-only code for scripts/benchmark_reports.py and its tests. It is not the S1
implementation: no route, capability, migration, grant or production module is added or
changed, and nothing here claims production equivalence (decisions r3.2 section 8.5).

Contents:
- the pinned five-zone table (docs/analytics/AN01-zone-table.json), strict lookups;
- request normalization, filter digest and the strict unsigned cursor (decisions section 4);
- the tagged statement registry: 7 operations, 22 SQL statements, 3 controls, digests;
- report shaping from raw rows (integer-string money, genuine unknowns);
- a measurement-only copy of the accepted budget/lease pattern with a SEPARATE report
  registry and pre-connect resource reservations (decisions section 5.2);
- an owner observer (pg_stat_activity), a withholding loopback relay (phase C4);
- the deterministic contract-valid operator fixture generator and COPY loader.

Provenance of the adapter: `src/sentinel/agents/budget.py` at accepted main a07ec12
(sha256 BUDGET_SOURCE_SHA256 below; a test fails if the accepted file changes). The copy
keeps its rules (integer millisecond budgets, MIN_DB_MS refusal, bounded reply waits on an
operation thread, retirement with socket shutdown through an independent duplicate, close
exactly once by the last user). It differs, deliberately and only here: the registry is a
parameter (never the workflow QUARANTINE), a retired lease keeps its resource reservation
until the actual final close, there is no COMMIT path, and ROLLBACK waits to the report
budget end B (not the phase end). Statement arming leaves REPLY_MARGIN_MS before work_end
(see that constant): without it the server timeout always fires about one round trip after
the client stops waiting, so a server cancellation could never be observed as answered.
The report clock is time.perf_counter (see monotonic_ms), not time.monotonic.
"""
from __future__ import annotations

import base64
import bisect
import hashlib
import json
import math
import random
import re
import socket
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc

# ---- provenance ----------------------------------------------------------------------------

ACCEPTED_BASE = "a07ec12710c86b15f111d13e3384c4cf0c6c8f6e"
BUDGET_SOURCE = "src/sentinel/agents/budget.py"
BUDGET_SOURCE_SHA256 = "4b5c7dd6aa9b2eca3376d5648e03f8dc0230e5bfffea36eee51a84bd58226e69"
REPORT_VERSION = "an01-m1-prototype"

# ---- 1. zones (decisions section 2) --------------------------------------------------------

ZONE_TABLE = ROOT / "docs" / "analytics" / "AN01-zone-table.json"
ZONE_DIGEST = "24e41cecb475453bb35e166abfc250610670593fd6ff0f324e0095eae274e165"
ZONE_DIGEST_DOMAIN = "sentinel.report-zones.an01-s1.v2\n"
DOMAIN_LOWER = datetime(2000, 1, 1, tzinfo=UTC)   # inclusive
DOMAIN_UPPER = datetime(2038, 1, 1, tzinfo=UTC)   # exclusive
ZONES = ("UTC", "Asia/Kolkata", "Asia/Tokyo", "Europe/London", "America/New_York")


class InvalidRequest(ValueError):
    """422 invalid_request (prototype classification)."""


class InvalidCursor(ValueError):
    """422 invalid_cursor (prototype classification)."""


class ZoneTable:
    """The committed midnight table. Lookups outside lookup_dates raise LookupError; there
    is no clamping or extrapolation. Host zoneinfo is never consulted."""

    def __init__(self, path: Path = ZONE_TABLE, expected: str = ZONE_DIGEST):
        doc = json.loads(path.read_text(encoding="utf-8"))
        canonical = json.dumps({"lookup_dates": doc["lookup_dates"], "ranges": doc["ranges"]},
                               sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256((ZONE_DIGEST_DOMAIN + canonical).encode()).hexdigest()
        if digest != doc.get("sha256") or digest != expected:
            raise ValueError("zone table digest mismatch")
        self.digest = digest
        self.first, self.last = (date.fromisoformat(d) for d in doc["lookup_dates"])
        self._ranges = {zone: ([date.fromisoformat(r[0]) for r in rows], [r[1] for r in rows])
                        for zone, rows in doc["ranges"].items()}
        if tuple(self._ranges) != ZONES:
            raise ValueError("zone table zones differ from the S1 allow-list")

    @property
    def label(self) -> str:
        return f"an01-zones IANA 2026e sha256:{self.digest[:8]}"

    def offset(self, zone: str, day: date) -> int:
        if zone not in self._ranges:
            raise LookupError(f"zone {zone} is not in the allow-list")
        if not self.first <= day <= self.last:
            raise LookupError(f"{day} is outside the table")
        starts, offsets = self._ranges[zone]
        index = bisect.bisect_right(starts, day) - 1
        if index < 0:
            raise LookupError(f"{day} precedes the first range")
        return offsets[index]

    def start(self, zone: str, day: date) -> datetime:
        """The first instant whose local date is `day`."""
        return datetime(day.year, day.month, day.day, tzinfo=UTC) - timedelta(
            seconds=self.offset(zone, day))

    def containing(self, zone: str, instant: datetime) -> date:
        guess = instant.astimezone(UTC).date()
        guess = (instant + timedelta(seconds=self.offset(zone, guess))).date()
        while self.start(zone, guess) > instant:
            guess -= timedelta(days=1)
        while self.start(zone, guess + timedelta(days=1)) <= instant:
            guess += timedelta(days=1)
        return guess

    def buckets(self, zone: str, start: datetime, end: datetime) -> list[dict]:
        """Every local date touched by [start, end), clipped to it."""
        day, out = self.containing(zone, start), []
        while self.start(zone, day) < end:
            begin, finish = self.start(zone, day), self.start(zone, day + timedelta(days=1))
            lo, hi = max(begin, start), min(finish, end)
            out.append({"day": day.isoformat(), "start": lo, "end": hi,
                        "day_seconds": int((finish - begin).total_seconds()),
                        "covered_seconds": int((hi - lo).total_seconds())})
            day += timedelta(days=1)
        return out


# ---- 2. requests, filter digest, cursor (contract draft section 2; decisions section 4) ---

REPORT_IDS = ("transactions.currency_totals", "transactions.daily", "cases.workload",
              "data_quality.checks", "rows.transactions")
CURRENCIES = ("GBP", "INR", "JPY", "USD")
CURRENCY_EXPONENT = {"USD": 2, "INR": 2, "GBP": 2, "JPY": 0}
MAX_WINDOW = timedelta(days=92)
MAX_DATES = 92
DEFAULT_LIMIT, MAX_LIMIT = 25, 100
MATCHING_ROW_CAP = 200_000          # provisional (decisions section 5.4)
MAX_CURSOR_LENGTH = 256             # derived
FILTER_DOMAIN = "sentinel.report-filters.an01-s1\n"
_INSTANT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$")
_CURSOR_TS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$")
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def iso(when: datetime) -> str:
    return when.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def parse_instant(value) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise InvalidRequest("instant without offset")
        return value.astimezone(UTC)
    if not isinstance(value, str) or not _INSTANT.fullmatch(value):
        raise InvalidRequest("instant must be RFC 3339 with an offset")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        raise InvalidRequest("invalid instant") from None


@dataclass(frozen=True)
class Request:
    report_id: str
    start: datetime
    end: datetime
    tz: str
    as_of: datetime
    read_at: datetime
    currencies: tuple[str, ...] = ()
    direction: str | None = None
    limit: int | None = None
    cursor: tuple | None = None   # (last_occurred_at, last_id, matching, with_outcome)

    @property
    def filter_digest(self) -> str:
        canonical = json.dumps({"report_id": self.report_id, "from": iso(self.start),
                                "to": iso(self.end), "tz": self.tz, "as_of": iso(self.as_of),
                                "currency": sorted(self.currencies),
                                "direction": self.direction},
                               sort_keys=True, separators=(",", ":"))
        return hashlib.sha256((FILTER_DOMAIN + canonical).encode()).hexdigest()


def normalize(zones: ZoneTable, report_id: str, *, read_at: datetime, from_=None, to=None,
              date_from=None, date_to=None, tz: str = "UTC", as_of=None, currencies=(),
              direction=None, limit=None, cursor=None, cap: int = MATCHING_ROW_CAP) -> Request:
    """Validate after conversion (decisions section 2.3). Any failure is InvalidRequest or
    InvalidCursor; nothing is clamped."""
    if report_id not in REPORT_IDS:
        raise InvalidRequest("unknown report")
    if tz not in ZONES:
        raise InvalidRequest("tz outside the allow-list")
    instant_mode, date_mode = (from_ is not None or to is not None,
                               date_from is not None or date_to is not None)
    if instant_mode == date_mode:
        raise InvalidRequest("use exactly one of from/to or date_from/date_to")
    if instant_mode:
        if from_ is None or to is None:
            raise InvalidRequest("from and to are both required")
        start, end = parse_instant(from_), parse_instant(to)
        if not start < end or end - start > MAX_WINDOW:
            raise InvalidRequest("window must be non-empty and at most 92 days")
    else:
        try:
            first, last = date.fromisoformat(str(date_from)), date.fromisoformat(str(date_to))
        except ValueError:
            raise InvalidRequest("dates must be YYYY-MM-DD") from None
        if not 1 <= (last - first).days <= MAX_DATES:
            raise InvalidRequest("1 to 92 local dates")
        try:
            start, end = zones.start(tz, first), zones.start(tz, last)
        except LookupError:
            raise InvalidRequest("date outside the zone table") from None
    if not (DOMAIN_LOWER <= start and end <= DOMAIN_UPPER):
        raise InvalidRequest("window outside the request domain")
    as_of = read_at if as_of is None else parse_instant(as_of)
    if as_of > read_at:
        raise InvalidRequest("as_of after read_at")
    currencies = tuple(sorted(set(currencies or ())))
    if any(c not in CURRENCIES for c in currencies):
        raise InvalidRequest("unknown currency")
    if direction not in (None, "debit", "credit"):
        raise InvalidRequest("unknown direction")
    if report_id == "cases.workload" and (currencies or direction):
        raise InvalidRequest("currency/direction do not apply to workload")
    if report_id == "rows.transactions":
        limit = DEFAULT_LIMIT if limit is None else limit
        if type(limit) is not int or not 1 <= limit <= MAX_LIMIT:
            raise InvalidRequest("limit 1-100")
    elif limit is not None or cursor is not None:
        raise InvalidRequest("limit/cursor apply only to rows.transactions")
    request = Request(report_id, start, end, tz, as_of, read_at, currencies, direction, limit)
    if cursor is not None:
        position = decode_cursor(cursor, request, cap)
        request = Request(report_id, start, end, tz, as_of, read_at, currencies, direction,
                          limit, position)
    return request


def encode_cursor(request: Request, last_occurred: datetime, last_id, counts) -> str:
    raw = json.dumps(["rows.transactions", request.filter_digest, iso(last_occurred),
                      str(last_id), *counts], separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_cursor(cursor, request: Request, cap: int = MATCHING_ROW_CAP) -> tuple:
    if not isinstance(cursor, str) or len(cursor) > MAX_CURSOR_LENGTH or not cursor.isascii():
        raise InvalidCursor("length or charset")
    if not re.fullmatch(r"[A-Za-z0-9_-]*", cursor):
        raise InvalidCursor("not url-safe base64")
    try:
        value = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
    except (ValueError, TypeError):
        raise InvalidCursor("not base64 JSON") from None
    if not (isinstance(value, list) and len(value) == 6):
        raise InvalidCursor("shape")
    report, digest, occurred, last_id, matching, with_outcome = value
    if report != "rows.transactions" or not isinstance(digest, str) \
            or not _HEX64.fullmatch(digest) or digest != request.filter_digest:
        raise InvalidCursor("report or filters differ")
    if not isinstance(occurred, str) or not _CURSOR_TS.fullmatch(occurred):
        raise InvalidCursor("timestamp form")
    if not isinstance(last_id, str) or not _UUID.fullmatch(last_id):
        raise InvalidCursor("id form")
    if type(matching) is not int or type(with_outcome) is not int \
            or not 0 <= with_outcome <= matching <= cap:
        raise InvalidCursor("counts")
    when = datetime.fromisoformat(occurred.replace("Z", "+00:00"))
    if not request.start <= when < request.end:
        raise InvalidCursor("position outside the window")
    return when, uuid.UUID(last_id), matching, with_outcome


# ---- 3. the tagged statement registry (decisions section 8.1) -----------------------------

REGISTRY_DOMAIN = "sentinel.an01-m1.statement-registry.v1\n"
OPERATION_DOMAIN = "sentinel.an01-m1.operation.v1\n"

# Controls: exact client templates, and the driver-generated form the server receives
# (psycopg 3.3: the implicit BEGIN of a REPEATABLE READ READ ONLY connection; %s -> $n).
CONTROLS = {
    "K0": {"template": "BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY",
           "driver_form": "BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY",
           "sent_by": "psycopg implicit transaction start (isolation_level, read_only)"},
    "Ka": {"template": "SELECT set_config('statement_timeout', %s, true),"
                       " set_config('lock_timeout', %s, true)",
           "driver_form": "SELECT set_config('statement_timeout', $1, true),"
                          " set_config('lock_timeout', $2, true)",
           "sent_by": "conn.execute before every SQL statement (accepted budget.py text)"},
    "Kr": {"template": "ROLLBACK", "driver_form": "ROLLBACK",
           "sent_by": "conn.rollback(); never COMMIT"},
}

_SCOPE_T = "t.tenant_id = %(tenant)s AND t.session_id = %(session)s"
_FILTER = (_SCOPE_T +
           " AND t.occurred_at >= %(from)s AND t.occurred_at < %(to)s"
           " AND t.ingested_at <= %(as_of)s"
           " AND (%(currencies)s::text[] IS NULL"
           " OR t.body -> 'amount' ->> 'currency' = ANY (%(currencies)s::text[]))"
           " AND (%(direction)s::text IS NULL OR t.body ->> 'direction' = %(direction)s::text)")
_JOIN_O = (" LEFT JOIN scoring_outcomes o ON o.transaction_id = t.id"
           " AND o.tenant_id = %(tenant)s AND o.session_id = %(session)s")
_JOIN_A = (" LEFT JOIN alerts a ON a.transaction_id = t.id"
           " AND a.tenant_id = %(tenant)s AND a.session_id = %(session)s")
_JOIN_C = (" LEFT JOIN cases c ON c.alert_id = a.id"
           " AND c.tenant_id = %(tenant)s AND c.session_id = %(session)s")
_MINOR = "(t.body -> 'amount' ->> 'minor_units')::numeric"
_DEBIT, _CREDIT = "t.body ->> 'direction' = 'debit'", "t.body ->> 'direction' = 'credit'"

_BODIES = {
    "G": "SELECT count(*) AS n FROM (SELECT 1 FROM transactions t WHERE " + _FILTER +
         " LIMIT %(guard_limit)s) g",
    "P": "SELECT count(*) AS matching, count(o.transaction_id) AS with_outcome"
         " FROM transactions t" + _JOIN_O + " WHERE " + _FILTER,
    "totals": "SELECT t.body -> 'amount' ->> 'currency' AS currency,"
              f" count(*) FILTER (WHERE {_DEBIT}) AS debit_count,"
              f" count(*) FILTER (WHERE {_CREDIT}) AS credit_count,"
              f" COALESCE(sum({_MINOR}) FILTER (WHERE {_DEBIT}), 0)::text AS debit_minor,"
              f" COALESCE(sum({_MINOR}) FILTER (WHERE {_CREDIT}), 0)::text AS credit_minor"
              " FROM transactions t WHERE " + _FILTER + " GROUP BY 1 ORDER BY 1",
    "daily": "SELECT width_bucket(t.occurred_at, %(bucket_starts)s::timestamptz[]) AS bucket,"
             " t.body -> 'amount' ->> 'currency' AS currency, count(*) AS transactions,"
             " count(*) FILTER (WHERE o.alerted) AS alerted,"
             " count(*) FILTER (WHERE o.transaction_id IS NULL) AS score_unknown,"
             f" COALESCE(sum({_MINOR}) FILTER (WHERE {_DEBIT}), 0)::text AS debit_minor,"
             f" COALESCE(sum({_MINOR}) FILTER (WHERE {_CREDIT}), 0)::text AS credit_minor"
             " FROM transactions t" + _JOIN_O + " WHERE " + _FILTER +
             " GROUP BY 1, 2 ORDER BY 1, 2",
    "wl_created": "SELECT c.state, count(*) AS n FROM cases c"
                  " WHERE c.tenant_id = %(tenant)s AND c.session_id = %(session)s"
                  " AND c.created_at >= %(from)s AND c.created_at < %(to)s"
                  " AND c.created_at <= %(as_of)s GROUP BY 1 ORDER BY 1",
    "wl_actions": "SELECT count(*) AS n FROM simulated_actions s"
                  " WHERE s.tenant_id = %(tenant)s AND s.session_id = %(session)s"
                  " AND s.body ->> 'state' = 'succeeded'"
                  " AND (s.body ->> 'completed_at')::timestamptz >= %(from)s"
                  " AND (s.body ->> 'completed_at')::timestamptz < %(to)s"
                  " AND (s.body ->> 'completed_at')::timestamptz <= %(as_of)s",
    "wl_open": "SELECT c.state,"
               " count(*) FILTER (WHERE %(read_at)s - c.created_at < interval '1 hour') AS lt_1h,"
               " count(*) FILTER (WHERE %(read_at)s - c.created_at >= interval '1 hour'"
               " AND %(read_at)s - c.created_at < interval '8 hours') AS h1_8h,"
               " count(*) FILTER (WHERE %(read_at)s - c.created_at >= interval '8 hours'"
               " AND %(read_at)s - c.created_at < interval '24 hours') AS h8_24h,"
               " count(*) FILTER (WHERE %(read_at)s - c.created_at >= interval '24 hours')"
               " AS ge_24h FROM cases c"
               " WHERE c.tenant_id = %(tenant)s AND c.session_id = %(session)s"
               " AND c.state IN ('open', 'investigating', 'awaiting_approval')"
               " GROUP BY 1 ORDER BY 1",
    "q_checks": "SELECT count(*) AS denominator,"
                " count(*) FILTER (WHERE o.transaction_id IS NULL) AS without_outcome,"
                " count(*) FILTER (WHERE o.alerted) AS alerted_outcomes,"
                " count(*) FILTER (WHERE o.alerted AND a.id IS NULL) AS alerted_without_alert,"
                " count(a.id) AS alerts,"
                " count(*) FILTER (WHERE a.id IS NOT NULL AND c.id IS NULL) AS alert_without_case,"
                " count(*) FILTER (WHERE t.ingested_at >= %(to)s) AS ingested_after_window_end"
                " FROM transactions t" + _JOIN_O + _JOIN_A + _JOIN_C + " WHERE " + _FILTER,
    "q_lags": "SELECT count(*) AS n,"
              " percentile_disc(0.5) WITHIN GROUP (ORDER BY lag) AS p50,"
              " percentile_disc(0.95) WITHIN GROUP (ORDER BY lag) AS p95, max(lag) AS lag_max"
              " FROM (SELECT ((extract(epoch FROM t.ingested_at) - extract(epoch FROM"
              " t.occurred_at)) * 1000000)::bigint AS lag FROM transactions t WHERE "
              + _FILTER + ") l",
    "drill": "SELECT t.id, t.external_id, t.occurred_at, t.ingested_at,"
             " t.body -> 'amount' ->> 'currency' AS currency,"
             " t.body -> 'amount' ->> 'minor_units' AS minor_units,"
             " t.body ->> 'direction' AS direction, o.alerted, o.score,"
             " o.body ->> 'scoring_kind' AS scoring_kind,"
             " o.body ->> 'score_semantics' AS score_semantics,"
             " c.id AS case_id, c.state AS case_state"
             " FROM transactions t" + _JOIN_O + _JOIN_A + _JOIN_C + " WHERE " + _FILTER +
             "{after} ORDER BY t.occurred_at, t.id LIMIT %(limit_plus_one)s",
}
_AFTER = " AND (t.occurred_at, t.id) > (%(after_occurred_at)s, %(after_id)s)"

# Operation -> ordered (statement id, body key). Each SQL statement is preceded by Ka.
OPERATIONS: dict[str, tuple[tuple[str, str], ...]] = {
    "totals": (("G", "G"), ("P", "P"), ("Q", "totals")),
    "daily_utc": (("G", "G"), ("P", "P"), ("Q", "daily")),
    "daily_ny": (("G", "G"), ("P", "P"), ("Q", "daily")),
    "workload": (("Q1", "wl_created"), ("Q2", "wl_actions"), ("Q3", "wl_open")),
    "quality": (("G", "G"), ("P", "P"), ("Q1", "q_checks"), ("Q2", "q_lags")),
    "drill_first": (("G", "G"), ("P", "P"), ("Q", "drill")),
    "drill_cursor": (("G", "G"), ("P", "P"), ("Q", "drill")),
}
TRANSACTION_OPS = ("totals", "daily_utc", "daily_ny", "quality", "drill_first", "drill_cursor")

# Phase C/E measurement-only texts (hashed separately; never part of a report).
CONTROL_SQL = {
    "C2": "/* an01-m1:C2:S */ SELECT pg_sleep(5)",
}


def tag(op: str, sid: str) -> str:
    return f"/* an01-m1:{op}:{sid} */"


def statement_text(op: str, sid: str, body: str, relation: str = "transactions") -> str:
    text = _BODIES[body]
    if body == "drill":
        text = text.replace("{after}", _AFTER if op == "drill_cursor" else "")
    if relation != "transactions":
        text = text.replace("FROM transactions t", f"FROM {relation} t")
    return f"{tag(op, sid)} {text}"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_registry(relation: str = "transactions", suffix: str = "") -> dict:
    """{statements: {op:sid -> {text, sha256}}, controls, operations: {op -> digest/order}}.
    Phase E's shadow variant uses another relation and a distinct tag suffix."""
    statements, operations = {}, {}
    controls = {k: {**v, "sha256": sha(v["template"]), "driver_sha256": sha(v["driver_form"])}
                for k, v in CONTROLS.items()}
    for op, sequence in OPERATIONS.items():
        name = op + suffix
        order = ["K0"]
        for sid, body in sequence:
            text = statement_text(name, sid, body, relation)
            statements[f"{name}:{sid}"] = {"text": text, "sha256": sha(text)}
            order += ["Ka", f"{name}:{sid}"]
        order.append("Kr")
        digests = [controls[k]["sha256"] if k in controls else statements[k]["sha256"]
                   for k in order]
        operations[name] = {"order": order, "sql_statements": len(sequence),
                            "sha256": sha(OPERATION_DOMAIN + "\n".join(digests))}
    registry = {"statements": statements, "controls": controls, "operations": operations,
                "control_sql": {k: {"text": v, "sha256": sha(v)} for k, v in CONTROL_SQL.items()}}
    registry["sha256"] = sha(REGISTRY_DOMAIN + json.dumps(
        {k: registry[k] for k in ("statements", "controls", "operations", "control_sql")},
        sort_keys=True, separators=(",", ":")))
    return registry


REGISTRY = build_registry()
SHADOW_SCHEMA = "an01_m1_shadow"
SHADOW_REGISTRY_OPS = ("totals", "daily_utc")


def shadow_registry() -> dict:
    """Phase E columns design: the same statements over a measurement-only shadow table
    whose money/direction are real columns (bodies rewritten accordingly)."""
    reg = build_registry(relation=f"{SHADOW_SCHEMA}.transactions", suffix="_cols")
    for key, entry in reg["statements"].items():
        text = (entry["text"].replace("t.body -> 'amount' ->> 'currency'", "t.currency")
                .replace("(t.body -> 'amount' ->> 'minor_units')::numeric", "t.minor_units")
                .replace("t.body ->> 'direction'", "t.direction"))
        entry["text"], entry["sha256"] = text, sha(text)
    keep = {k: v for k, v in reg["statements"].items()
            if k.split(":")[0].removesuffix("_cols") in SHADOW_REGISTRY_OPS}
    ops = {}
    for op in SHADOW_REGISTRY_OPS:
        name = op + "_cols"
        order = reg["operations"][name]["order"]
        digests = [reg["controls"][k]["sha256"] if k in reg["controls"] else keep[k]["sha256"]
                   for k in order]
        ops[name] = {"order": order, "sql_statements": len(OPERATIONS[op]),
                     "sha256": sha(OPERATION_DOMAIN + "\n".join(digests))}
    out = {"statements": keep, "operations": ops}
    out["sha256"] = sha(REGISTRY_DOMAIN + json.dumps(out, sort_keys=True, separators=(",", ":")))
    return out


def operation_for(request: Request) -> str:
    """The measured operation serving a report request. transactions.daily uses daily_utc for
    tz=UTC and daily_ny (identical SQL, its own tag) for the other zones."""
    if request.report_id == "rows.transactions":
        return "drill_cursor" if request.cursor else "drill_first"
    return {"transactions.currency_totals": "totals", "cases.workload": "workload",
            "data_quality.checks": "quality",
            "transactions.daily": "daily_utc" if request.tz == "UTC" else "daily_ny",
            }[request.report_id]


def parameters(request: Request, scope: tuple, zones: ZoneTable,
               cap: int = MATCHING_ROW_CAP) -> dict:
    tenant, session = scope
    params = {"tenant": tenant, "session": session, "from": request.start, "to": request.end,
              "as_of": request.as_of, "read_at": request.read_at,
              "currencies": list(request.currencies) or None, "direction": request.direction,
              "guard_limit": cap + 1}
    if request.report_id == "transactions.daily":
        params["buckets"] = zones.buckets(request.tz, request.start, request.end)
        params["bucket_starts"] = [b["start"] for b in params["buckets"]]
    if request.report_id == "rows.transactions":
        params["limit_plus_one"] = request.limit + 1
        if request.cursor:
            params["after_occurred_at"], params["after_id"] = request.cursor[:2]
    return params


# ---- 4. shaping results (contract draft sections 3-5) --------------------------------------

def shape(request: Request, results: dict, params: dict, zones: ZoneTable) -> dict:
    """The prototype DTO body from the raw statement results of one operation."""
    out = {"report_id": request.report_id, "report_version": REPORT_VERSION,
           "provenance": {"data": "synthetic", "scope": "current session",
                          "window": {"from": iso(request.start), "to": iso(request.end)},
                          "tz": request.tz, "tz_data": zones.label, "as_of": iso(request.as_of),
                          "read_at": iso(request.read_at), "snapshot": "per_request"}}
    if "P" in results:
        pair = results["P"][0]
        out["consistency"] = {"matching_transactions": pair["matching"],
                              "with_outcome": pair["with_outcome"]}
    rid = request.report_id
    if rid == "transactions.currency_totals":
        rows = []
        for r in results["Q"]:
            debit, credit = int(r["debit_minor"]), int(r["credit_minor"])
            rows.append({"currency": r["currency"],
                         "currency_exponent": CURRENCY_EXPONENT[r["currency"]],
                         "debit_count": r["debit_count"], "credit_count": r["credit_count"],
                         "debit_minor": str(debit), "credit_minor": str(credit),
                         "gross_minor": str(debit + credit),
                         "net_outflow_minor": str(debit - credit)})
        out["rows"] = rows
    elif rid == "transactions.daily":
        buckets = params["buckets"]
        out["buckets"] = [{**b, "start": iso(b["start"]), "end": iso(b["end"])}
                          for b in buckets]
        out["rows"] = [{"day": buckets[r["bucket"] - 1]["day"], "currency": r["currency"],
                        "transactions": r["transactions"], "alerted": r["alerted"],
                        "score_unknown": r["score_unknown"],
                        "debit_minor": str(int(r["debit_minor"])),
                        "credit_minor": str(int(r["credit_minor"]))} for r in results["Q"]]
    elif rid == "cases.workload":
        states = ("open", "investigating", "awaiting_approval", "closed", "inconclusive")
        created = {s: 0 for s in states} | {r["state"]: r["n"] for r in results["Q1"]}
        open_rows = {r["state"]: r for r in results["Q3"]}
        ages = {k: sum(r[c] for r in results["Q3"])
                for k, c in (("lt_1h", "lt_1h"), ("1h_8h", "h1_8h"), ("8h_24h", "h8_24h"),
                             ("ge_24h", "ge_24h"))}
        out["workload"] = {
            "created_in_window": {"by_current_state": created,
                                  "time_basis": "cases.created_at"},
            "actions_completed_in_window": {"count": results["Q2"][0]["n"],
                                            "time_basis": "simulated_actions.completed_at"},
            "open_now": {"by_state": {s: sum(open_rows[s][c] for c in
                                             ("lt_1h", "h1_8h", "h8_24h", "ge_24h"))
                                      if s in open_rows else 0 for s in states[:3]},
                         "age_buckets": ages, "time_basis": "read_at - cases.created_at",
                         "window_applied": False},
            "state_basis": "current_at_read"}
    elif rid == "data_quality.checks":
        c, lags = results["Q1"][0], results["Q2"][0]
        n = c["denominator"]
        out["rows"] = [
            {"check": "transactions_without_outcome", "value": c["without_outcome"],
             "denominator": n},
            {"check": "alerted_outcome_without_alert", "value": c["alerted_without_alert"],
             "denominator": c["alerted_outcomes"]},
            {"check": "alert_without_case", "value": c["alert_without_case"],
             "denominator": c["alerts"]},
            {"check": "ingested_after_window_end", "value": c["ingested_after_window_end"],
             "denominator": n},
            {"check": "ingestion_lag_p50_us", "value": lags["p50"], "denominator": lags["n"]},
            {"check": "ingestion_lag_p95_us", "value": lags["p95"], "denominator": lags["n"]},
            {"check": "ingestion_lag_max_us", "value": lags["lag_max"],
             "denominator": lags["n"]}]
    elif rid == "rows.transactions":
        rows = results["Q"]
        page, more = rows[:request.limit], len(rows) > request.limit
        out["rows"] = [{"transaction_id": str(r["id"]), "external_id": r["external_id"],
                        "occurred_at": iso(r["occurred_at"]), "ingested_at": iso(r["ingested_at"]),
                        "currency": r["currency"],
                        "currency_exponent": CURRENCY_EXPONENT[r["currency"]],
                        "minor_units": str(int(r["minor_units"])), "direction": r["direction"],
                        "alerted": r["alerted"], "score": r["score"],
                        "scoring_kind": r["scoring_kind"],
                        "score_semantics": r["score_semantics"],
                        "case_id": None if r["case_id"] is None else str(r["case_id"]),
                        "case_state": r["case_state"]} for r in page]
        pair = (out["consistency"]["matching_transactions"],
                out["consistency"]["with_outcome"])
        first = request.cursor[2:] if request.cursor else pair
        out["page"] = {"limit": request.limit, "row_set_changed": tuple(first) != pair}
        out["next_cursor"] = encode_cursor(request, page[-1]["occurred_at"], page[-1]["id"],
                                           first) if more else None
    return out


# ---- 5. measurement-only budget and lease adapter (decisions section 5.2) ------------------

MIN_DB_MS = 100                    # as accepted budget.MIN_DB_MS
REPLY_MARGIN_MS = 30               # prototype: server timeout fires this long before work_end
PROVISIONAL_B_MS, PROVISIONAL_R_MS = 5000, 250
MEASUREMENT_B_MS = 10_000
PROVISIONAL_M, PROVISIONAL_Q = 2, 2


def monotonic_ms() -> float:
    """The prototype's report clock: time.perf_counter, which is monotonic and fine-grained
    on both platforms. (time.monotonic, used by the accepted budget.py, advances in about
    15.6 ms steps on Windows, which the first tiny smoke recorded as quantized medians.)"""
    return time.perf_counter() * 1000


class ReportQuarantine:
    """Retired report connections, separate from the workflow budget.QUARANTINE."""

    def __init__(self):
        self._lock = threading.Lock()
        self._held: dict[int, object] = {}

    def hold(self, conn) -> None:
        with self._lock:
            self._held[id(conn)] = conn

    def release(self, conn) -> None:
        with self._lock:
            if self._held.get(id(conn)) is conn:
                del self._held[id(conn)]

    def holds(self, conn) -> bool:
        with self._lock:
            return self._held.get(id(conn)) is conn

    def count(self) -> int:
        with self._lock:
            return len(self._held)


class Resources:
    """Coordinator admission M and held-resource reservations Q, checked and taken together
    under one lock BEFORE any connection attempt. A reservation is released exactly once:
    after a definitive connect failure without a connection, or after the connection's actual
    close. Retirement does not release it; ownership moves to the final close."""

    def __init__(self, max_active: int = PROVISIONAL_M, max_reserved: int = PROVISIONAL_Q):
        self.max_active, self.max_reserved = max_active, max_reserved
        self._lock = threading.Lock()
        self.active = self.reserved = 0
        self.peak_reserved = 0
        self.events: list[tuple[float, str, int, int]] = []

    def _note(self, what: str) -> None:  # holding the lock
        self.events.append((time.monotonic(), what, self.active, self.reserved))

    def admit(self) -> "Admission | None":
        with self._lock:
            if self.active >= self.max_active or self.reserved >= self.max_reserved:
                self._note("refused")
                return None
            self.active += 1
            self.reserved += 1
            self.peak_reserved = max(self.peak_reserved, self.reserved)
            if self.reserved > self.max_reserved or self.active > self.max_active:
                raise AssertionError("reservation invariant broken")
            self._note("admitted")
            return Admission(self)

    def counts(self) -> tuple[int, int]:
        with self._lock:
            return self.active, self.reserved


class Admission:
    def __init__(self, resources: Resources):
        self.resources = resources
        self._lock = threading.Lock()
        self.coordinator_released = self.reservation_released = False
        self.releases = 0

    def end_coordinator(self) -> None:
        with self._lock:
            if self.coordinator_released:
                return
            self.coordinator_released = True
        with self.resources._lock:
            self.resources.active -= 1
            self.resources._note("coordinator_released")

    def release_reservation(self, why: str) -> None:
        with self._lock:
            self.releases += 1
            if self.reservation_released:
                return
            self.reservation_released = True
        with self.resources._lock:
            self.resources.reserved -= 1
            self.resources._note(f"reservation_released:{why}")


class _OwnSocket:
    """As accepted budget._OwnSocket: an independent socket reference taken before the
    operation, so shutdown reaches only this connection's own socket."""

    def __init__(self, conn):
        self.fd, self.sock = None, None
        try:
            fileno = conn.fileno()
        except Exception:
            return
        import os
        try:
            if os.name == "posix":
                self.fd = os.dup(fileno)
            else:
                borrowed = socket.socket(fileno=fileno)
                try:
                    self.sock = borrowed.dup()
                finally:
                    borrowed.detach()
        except OSError:
            self.fd, self.sock = None, None

    def shutdown(self) -> None:
        import os
        sock, self.sock = self.sock, None
        if sock is None and self.fd is not None:
            fd, self.fd = self.fd, None
            try:
                sock = socket.socket(fileno=fd)
            except Exception:
                os.close(fd)
                return
        if sock is None:
            return
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        finally:
            sock.close()

    def release(self) -> None:
        import os
        if self.sock is not None:
            self.sock.close()
        elif self.fd is not None:
            os.close(self.fd)
        self.fd, self.sock = None, None


class NoReply(Exception):
    """An operation was abandoned at its wait; the connection is retired to the report
    quarantine and its reservation stays held until the final close."""


class ReportConnection:
    """One report request's connection, its admission and its single close."""

    def __init__(self, conn, admission: Admission, quarantine: ReportQuarantine,
                 final_close_gate: Callable[[], None] | None = None):
        self.conn, self.admission, self.quarantine = conn, admission, quarantine
        self.final_close_gate = final_close_gate
        self.cond = threading.Condition()
        self.users: set[str] = set()
        self.retired = self.closed = False
        self.close_calls = 0
        self.events: list[str] = []
        self.reply_at: float | None = None

    def enter(self, user: str) -> None:
        with self.cond:
            self.users.add(user)

    def leave(self, user: str) -> None:
        with self.cond:
            self.users.discard(user)
            self.cond.notify_all()
            close = self._closing()
        if close:
            self._final_close()

    def retire(self) -> None:
        with self.cond:
            if not self.retired:
                self.retired = True
                self.quarantine.hold(self.conn)
                self.events.append("retired")
            close = self._closing()
        if close:
            self._final_close()

    def _closing(self) -> bool:  # holding the lock
        if self.retired and not self.users and not self.closed:
            self.closed = True
            return True
        return False

    def _final_close(self) -> None:
        """The last user of a retired connection closes it, once."""
        try:
            if self.final_close_gate is not None:
                self.final_close_gate()          # test-only injected delay (phase C5)
        finally:
            self._do_close("final_close")
            self.quarantine.release(self.conn)

    def close_normal(self) -> bool:
        """Request-owned close of a connection that was never retired. Returns False (and
        does nothing) for a retired one: its lease owns the close."""
        with self.cond:
            if self.retired or self.closed:
                return False
            self.closed = True
        self._do_close("normal_close")
        return True

    def _do_close(self, why: str) -> None:
        self.close_calls += 1
        self.events.append(why)
        try:
            self.conn.close()
        except Exception:
            pass
        self.admission.release_reservation(why)


def bounded_call(rc: ReportConnection, operation: Callable, wait_ms: float,
                 clock: Callable[[], float] = monotonic_ms):
    """Run `operation` on its own thread and wait at most `wait_ms`. Unanswered: retire,
    shut the own socket down, raise NoReply. The SQL thread leaving last closes the
    retired connection exactly once (as accepted budget.bounded_call, without COMMIT's
    cancel helper).

    The SQL thread records when its reply (result or server error) arrived in
    `rc.reply_at` on `clock`; the waiter may notice it later (polling every <= 5 ms, plus
    sleep overshoot), so latencies use the arrival time, not the moment it was noticed."""
    from sentinel.clock import wait_until
    own = _OwnSocket(rc.conn)
    box: dict = {}
    done = threading.Event()
    started = time.perf_counter()

    def work():
        try:
            box["value"] = operation()
        except BaseException as error:
            box["error"] = error
        finally:
            box["at"] = clock()
            done.set()
            rc.leave("sql")

    try:
        rc.enter("sql")
        threading.Thread(target=work, name="an01-m1-sql", daemon=True).start()
        wait_until(done.is_set, lambda: wait_ms / 1000 - (time.perf_counter() - started))
        if not done.is_set():
            rc.retire()
            own.shutdown()
            raise NoReply()
    finally:
        own.release()
    rc.reply_at = box.get("at")
    if "error" in box:
        raise box["error"]
    return box.get("value")


class ReportBudget:
    """One monotonic report budget B with ROLLBACK reserve R, started after acquisition."""

    def __init__(self, total_ms: int, reserve_ms: int, clock: Callable[[], float] = monotonic_ms):
        if not 0 < reserve_ms < total_ms:
            raise ValueError("need 0 < R < B")
        self.clock, self.total_ms, self.reserve_ms = clock, total_ms, reserve_ms
        self.t0 = clock()

    @property
    def work_end(self) -> float:
        return self.t0 + self.total_ms - self.reserve_ms

    @property
    def end(self) -> float:
        return self.t0 + self.total_ms

    def work_left(self) -> int:
        return math.floor(self.work_end - self.clock())

    def left(self) -> int:
        return math.floor(self.end - self.clock())


# Outcome -> prototype HTTP classification (decisions section 5.3). Labels only: there is no
# route, and these strings are never a contract.
PROTOTYPE_HTTP = {
    "ok": "200 (prototype classification)",
    "too_large": "413 report_too_large (prototype classification)",
    "admission_refused": "409 report_capacity_exhausted (prototype classification)",
    "connect_failed": "database error path (prototype classification)",
    "refused_before_submission": "503 report_timeout (prototype classification)",
    "server_cancelled": "503 report_timeout (prototype classification)",
    "lock_timeout": "503 report_timeout (prototype classification)",
    "no_reply": "503 report_timeout (prototype classification)",
    "rollback_unanswered": "200 (prototype classification)",
    "error": "500 (prototype classification)",
}


@dataclass
class Outcome:
    kind: str
    submitted: int = 0              # SQL/control statements whose bounded call started
    sql_submitted: int = 0          # report SQL statements among them
    results: dict = field(default_factory=dict)
    elapsed_ms: float | None = None  # BEGIN..ROLLBACK reply (or abandonment), on B's clock
    connect_ms: float | None = None  # outside B
    work_end_ms: float | None = None
    error_at_ms: float | None = None  # when a server error reply ARRIVED (relative to t0)
    error_noticed_ms: float | None = None  # when the waiting thread noticed it
    armed_deadline_ms: float | None = None  # client-clock time the last armed timeout fires
    rollback: str = "not_needed"
    error_class: str | None = None
    sqlstate: str | None = None
    retired: bool = False
    read_at: datetime | None = None
    connection: object = None        # the ReportConnection (in-process evidence only)

    @property
    def http(self) -> str:
        return PROTOTYPE_HTTP[self.kind]

    def public(self) -> dict:
        return {"kind": self.kind, "http": self.http, "submitted": self.submitted,
                "sql_submitted": self.sql_submitted, "elapsed_ms": _r(self.elapsed_ms),
                "connect_ms": _r(self.connect_ms), "rollback": self.rollback,
                "error_class": self.error_class, "sqlstate": self.sqlstate,
                "retired": self.retired,
                "deadline_to_error_ms": None if self.error_at_ms is None
                or self.armed_deadline_ms is None
                else _r(self.error_at_ms - self.armed_deadline_ms),
                "error_at_ms": _r(self.error_at_ms),
                "error_noticed_ms": _r(self.error_noticed_ms),
                "work_end_ms": _r(self.work_end_ms)}


def _r(value):
    return None if value is None else round(value, 3)


@dataclass
class Runtime:
    """What one operation needs besides its SQL: how to connect (outside B), the admission
    gate, the separate report registry, the clocks and test hooks."""
    connect: Callable[[], object]
    resources: Resources
    quarantine: ReportQuarantine
    total_ms: int = MEASUREMENT_B_MS
    reserve_ms: int = PROVISIONAL_R_MS
    clock: Callable[[], float] = monotonic_ms
    read_clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    final_close_gate: Callable[[], None] | None = None
    reply_margin_ms: int = REPLY_MARGIN_MS
    on_connect: Callable[[object], None] | None = None   # e.g. start an owner observer


def runtime_connect(url: str, connect_timeout_s: int = 2) -> Callable[[], object]:
    """The report connection policy (decisions 5.2.1): single host, connect_timeout 2 s per
    libpq attempt, REPEATABLE READ READ ONLY, no automatic prepares. Not bounded overall."""
    from sentinel.agents.budget import single_host  # read-only reuse of the accepted check
    if not single_host(url):
        raise ValueError("the report connection must name a single host")

    def connect():
        conn = psycopg.connect(url, row_factory=dict_row, autocommit=False,
                               connect_timeout=connect_timeout_s, prepare_threshold=None)
        conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
        conn.read_only = True
        return conn
    return connect


def run_statements(rt: Runtime, sequence: list[tuple[str, str, dict]],
                   guard: Callable[[str, list], bool] | None = None) -> Outcome:
    """One complete operation after admission: connect (outside B), then BEGIN .. ROLLBACK
    under one budget. `sequence` is [(key, text, params)]; `guard(key, rows)` returning
    True stops the operation as too_large after that statement."""
    admission = rt.resources.admit()
    if admission is None:
        return Outcome("admission_refused")
    try:
        return _run_admitted(rt, admission, sequence, guard)
    finally:
        admission.end_coordinator()


def _run_admitted(rt, admission, sequence, guard) -> Outcome:
    c0 = rt.clock()
    try:
        raw = rt.connect()
    except psycopg.Error as error:
        admission.release_reservation("connect_failed")
        return Outcome("connect_failed", connect_ms=rt.clock() - c0,
                       error_class=type(error).__name__, sqlstate=error.sqlstate)
    connect_ms = rt.clock() - c0
    rc = ReportConnection(raw, admission, rt.quarantine, rt.final_close_gate)
    if rt.on_connect is not None:
        rt.on_connect(raw)                      # outside B, before it starts
    budget = ReportBudget(rt.total_ms, rt.reserve_ms, rt.clock)
    out = Outcome("ok", connect_ms=connect_ms, work_end_ms=rt.total_ms - rt.reserve_ms)
    out.connection = rc
    began = False
    try:
        for key, text, params in sequence:
            armed = budget.work_left() - rt.reply_margin_ms
            if armed < MIN_DB_MS:
                out.kind = "refused_before_submission"
                break
            if not began:
                out.read_at = rt.read_clock()  # just before the first armed statement
            value = str(armed)
            out.armed_deadline_ms = rt.clock() - budget.t0 + armed
            out.submitted += 1
            bounded_call(rc, lambda: raw.execute(CONTROLS["Ka"]["template"], (value, value)),
                         max(budget.work_end - rt.clock(), 0), rt.clock)
            began = True
            out.submitted += 1
            out.sql_submitted += 1
            p = params
            rows = bounded_call(rc, lambda: raw.execute(text, p).fetchall(),
                                max(budget.work_end - rt.clock(), 0), rt.clock)
            out.results[key] = rows
            if guard is not None and guard(key, rows):
                out.kind = "too_large"
                break
    except NoReply:
        out.kind, out.retired = "no_reply", True
    except (psycopg.errors.LockNotAvailable, psycopg.errors.QueryCanceled) as error:
        out.kind = "lock_timeout" if isinstance(error, psycopg.errors.LockNotAvailable)             else "server_cancelled"
        out.error_noticed_ms = rt.clock() - budget.t0
        out.error_at_ms = None if rc.reply_at is None else rc.reply_at - budget.t0
        out.error_class, out.sqlstate = type(error).__name__, error.sqlstate
    except psycopg.Error as error:
        out.kind, out.error_class, out.sqlstate = "error", type(error).__name__, error.sqlstate
    finally:
        if not rc.retired:
            out.rollback = _rollback(rc, budget, rt, out)
        out.elapsed_ms = rt.clock() - budget.t0
        if not rc.retired:
            rc.close_normal()
        out.retired = rc.retired
    if out.kind == "ok" and out.rollback == "unanswered":
        out.kind = "rollback_unanswered"
    return out


def _rollback(rc: ReportConnection, budget: ReportBudget, rt: Runtime, out: Outcome) -> str:
    """ROLLBACK awaited until B (the reserve end), never past it. Nothing begun: nothing sent."""
    raw = rc.conn
    try:
        status = raw.info.transaction_status
    except Exception:
        return "connection_unusable"
    if status == psycopg.pq.TransactionStatus.IDLE:
        return "not_needed"
    left = budget.end - rt.clock()
    if left <= 0:
        return "no_time_closed"
    try:
        bounded_call(rc, raw.rollback, left)
        return "answered"
    except NoReply:
        return "unanswered"
    except psycopg.Error:
        return "error_closed"


def operation_sequence(op: str, params: dict, registry: dict = REGISTRY) -> list:
    return [(sid, registry["statements"][f"{op}:{sid}"]["text"], params)
            for sid, _ in OPERATIONS[op.removesuffix("_cols")]]


def guard_for(cap: int) -> Callable[[str, list], bool]:
    return lambda key, rows: key == "G" and rows[0]["n"] > cap


def run_report(rt: Runtime, request: Request, scope: tuple, zones: ZoneTable,
               cap: int = MATCHING_ROW_CAP) -> tuple[Outcome, dict | None]:
    op = operation_for(request)
    params = parameters(request, scope, zones, cap)
    params["read_at"] = request.read_at
    outcome = run_statements(rt, operation_sequence(op, params), guard_for(cap))
    body = shape(request, outcome.results, params, zones) if outcome.kind == "ok" else None
    return outcome, body


# ---- 6. observer and relay (phase C proofs) ------------------------------------------------

class Observer:
    """Owner connection polling pg_stat_activity for one backend: proves (or refutes) that a
    tagged statement was submitted, active or waiting on a lock."""

    def __init__(self, owner_url: str, interval_s: float = 0.005):
        self.url, self.interval = owner_url, interval_s
        self.seen: list[dict] = []
        self._stop = threading.Event()
        self._thread = None
        self.pid = None
        self.marker = "an01-m1:"

    def watch(self, pid: int, marker: str = "an01-m1:") -> None:
        self.pid, self.marker = pid, marker
        self._thread = threading.Thread(target=self._loop, name="an01-m1-observer",
                                        daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        with psycopg.connect(self.url, autocommit=True, row_factory=dict_row,
                             connect_timeout=5) as conn:
            while not self._stop.is_set():
                row = conn.execute("SELECT state, wait_event_type, query FROM pg_stat_activity"
                                   " WHERE pid = %s", (self.pid,)).fetchone()
                if row and self.marker in (row["query"] or ""):
                    self.seen.append({"at": time.monotonic(), "state": row["state"],
                                      "wait": row["wait_event_type"],
                                      "tag": _tag_of(row["query"])})
                self._stop.wait(self.interval)

    def stop(self) -> list[dict]:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(5)
        return self.seen


def _tag_of(query: str) -> str | None:
    match = re.search(r"/\* (an01-m1:[A-Za-z_0-9]+:[A-Z0-9]+) \*/", query or "")
    return match.group(1) if match else None


class WithholdingRelay:
    """An owned loopback TCP relay to the cluster. Once the client->server stream contains
    `trigger`, server->client bytes of that connection are read and withheld (never
    forwarded). Proof of submission is the relay's own sighting of the trigger bytes."""

    def __init__(self, upstream_port: int, trigger: bytes):
        self.upstream, self.trigger = ("127.0.0.1", upstream_port), trigger
        self.listener = socket.create_server(("127.0.0.1", 0))
        self.port = self.listener.getsockname()[1]
        self.sightings: list[float] = []
        self.withheld_bytes = 0
        self._sockets: list[socket.socket] = []
        self._threads: list[threading.Thread] = []
        self._lock = threading.Lock()
        self._closed = False
        self._spawn(self._accept)

    def _spawn(self, target, *args) -> None:
        thread = threading.Thread(target=target, args=args, name="an01-m1-relay", daemon=True)
        self._threads.append(thread)
        thread.start()

    def _accept(self) -> None:
        while True:
            try:
                client, _ = self.listener.accept()
            except OSError:
                return
            try:
                server = socket.create_connection(self.upstream, timeout=5)
                server.settimeout(None)
            except OSError:
                client.close()
                continue
            with self._lock:
                if self._closed:
                    client.close()
                    server.close()
                    return
                self._sockets += [client, server]
            state = {"withhold": False}
            self._spawn(self._pump_up, client, server, state)
            self._spawn(self._pump_down, server, client, state)

    def _pump_up(self, src, dst, state) -> None:
        tail = b""
        try:
            while True:
                data = src.recv(65536)
                if not data:
                    break
                window = tail + data
                if not state["withhold"] and self.trigger in window:
                    state["withhold"] = True
                    self.sightings.append(time.monotonic())
                tail = window[-len(self.trigger):]
                dst.sendall(data)
        except OSError:
            pass
        finally:
            _close(dst)
            _close(src)

    def _pump_down(self, src, dst, state) -> None:
        try:
            while True:
                data = src.recv(65536)
                if not data:
                    break
                if state["withhold"]:
                    self.withheld_bytes += len(data)
                    continue
                dst.sendall(data)
        except OSError:
            pass
        finally:
            _close(dst)

    def close(self) -> None:
        with self._lock:
            self._closed = True
            sockets = list(self._sockets)
        _close(self.listener)
        for s in sockets:
            _close(s)
        for thread in self._threads:
            thread.join(2)


def _close(sock) -> None:
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    try:
        sock.close()
    except OSError:
        pass


# ---- 7. deterministic contract-valid operator fixtures (decisions section 8.2) -------------

FIXTURE_START = datetime(2026, 7, 1, tzinfo=UTC)
FIXTURE_DAYS = 92
MAX_MINOR_UNITS = 9_000_000_000_000
CURRENCY_WEIGHTS = (("USD", 40), ("INR", 25), ("GBP", 20), ("JPY", 15))
CASE_STATES_NO_ACTION = (("open", 50), ("investigating", 5), ("awaiting_approval", 30),
                         ("inconclusive", 15))
_TABLE_COLUMNS = {
    "transactions": ("id", "tenant_id", "session_id", "external_id", "account_id",
                     "occurred_at", "ingested_at", "input_sha256", "body"),
    "scoring_outcomes": ("transaction_id", "tenant_id", "session_id", "score", "alerted", "body"),
    "alerts": ("id", "tenant_id", "session_id", "transaction_id", "body"),
    "cases": ("id", "tenant_id", "session_id", "alert_id", "revision", "state", "created_at",
              "body"),
    "agent_runs": ("id", "tenant_id", "session_id", "case_id", "status", "started_at",
                   "finished_at", "body"),
    "action_intents": ("id", "tenant_id", "session_id", "case_id", "case_revision",
                       "agent_run_id", "intent_sha256", "body"),
    "approvals": ("id", "tenant_id", "session_id", "intent_id", "decision", "consumed_at",
                  "body"),
    "simulated_actions": ("id", "tenant_id", "session_id", "approval_id", "idempotency_key",
                          "intent_sha256", "body"),
}
LOAD_ORDER = tuple(_TABLE_COLUMNS)


def _weighted(rng: random.Random, choices) -> str:
    total = sum(w for _, w in choices)
    pick = rng.randrange(total)
    for value, weight in choices:
        if pick < weight:
            return value
        pick -= weight
    raise AssertionError


def _uuid(rng: random.Random) -> uuid.UUID:
    return uuid.UUID(int=rng.getrandbits(128), version=4)


class FixtureBuilder:
    """Builds rows whose JSON bodies validate against the v1 contract models. The same
    builder serves the r2 known-answer fixture and the generated benchmark data."""

    def __init__(self):
        from sentinel import scoring
        from sentinel.contracts import v1
        self.v1, self.scoring = v1, scoring
        self.rows: dict[str, list[tuple]] = {t: [] for t in LOAD_ORDER}

    def _scope(self, tenant, session):
        return self.v1.Scope(tenant_id=tenant, session_id=session)

    def transaction(self, *, id, tenant, session, external_id, account, currency, minor,
                    direction, occurred, ingested) -> None:
        v1 = self.v1
        data = v1.TransactionInput(
            external_id=external_id, account_id=account,
            amount=v1.Money(currency=currency, minor_units=minor,
                            currency_exponent=v1.CURRENCY_EXPONENT[currency]),
            direction=direction, occurred_at=occurred)
        txn = v1.Transaction(**data.model_dump(), id=id, scope=self._scope(tenant, session),
                             ingested_at=ingested, dataset=self.scoring.DATASET)
        digest = v1.canonical_digest("sentinel.transaction-input.v1",
                                     data.model_dump(mode="json"))
        self.rows["transactions"].append(
            (id, tenant, session, external_id, account, txn.occurred_at, txn.ingested_at,
             digest, _json(txn)))

    def outcome(self, *, transaction, tenant, session, at, alerted: bool) -> None:
        s = self.scoring
        score = 0.6 if alerted else 0.0
        out = self.v1.ScoringOutcome(
            transaction_id=transaction, scope=self._scope(tenant, session), scored_at=at,
            features_as_of=at, scorer=s.SCORER, features=s.FEATURES,
            threshold_policy=s.THRESHOLD_POLICY, scoring_kind="rule",
            score_semantics="heuristic", score=score, threshold=s.THRESHOLD, alerted=alerted,
            prior_count_1h=0)
        self.rows["scoring_outcomes"].append((transaction, tenant, session, score, alerted,
                                              _json(out)))

    def case(self, *, rng_or_ids, transaction, tenant, session, at, state, minor) -> tuple:
        v1, s = self.v1, self.scoring
        alert_id, case_id = next(rng_or_ids), next(rng_or_ids)
        alert = v1.Alert(id=alert_id, scope=self._scope(tenant, session),
                         transaction_id=transaction, created_at=at, features_as_of=at,
                         scorer=s.SCORER, features=s.FEATURES,
                         threshold_policy=s.THRESHOLD_POLICY, scoring_kind="rule",
                         score_semantics="heuristic", score=0.6, threshold=s.THRESHOLD)
        self.rows["alerts"].append((alert_id, tenant, session, transaction, _json(alert)))
        revision = {"open": 1, "investigating": 2, "awaiting_approval": 3,
                    "inconclusive": 3, "closed": 4}[state]
        case = v1.Case(id=case_id, scope=self._scope(tenant, session), alert_id=alert_id,
                       revision=revision, state=state,
                       pins=v1.CasePins(dataset=s.DATASET, scorer=s.SCORER,
                                        threshold_policy=s.THRESHOLD_POLICY,
                                        policy=s.ACTION_POLICY, agent_config=s.TOOL_PROFILE,
                                        tool_config=s.TOOL_PROFILE,
                                        evidence_snapshot_sha256="0" * 64),
                       created_at=at, updated_at=at)
        self.rows["cases"].append((case_id, tenant, session, alert_id, revision, state, at,
                                   _json(case)))
        return case_id, revision

    def action(self, *, ids, transaction, tenant, session, case_id, revision, at,
               completed) -> None:
        v1, s = self.v1, self.scoring
        scope = self._scope(tenant, session)
        run_id, intent_id, approval_id, action_id, key, actor = (next(ids) for _ in range(6))
        run = v1.AgentRun(id=run_id, scope=scope, case_id=case_id, case_revision=1,
                          role="investigator", principal_id=actor, config=s.TOOL_PROFILE,
                          tool_profile=s.TOOL_PROFILE, input_snapshot_sha256="0" * 64,
                          budget=v1.RunBudget(), status="completed")
        self.rows["agent_runs"].append((run_id, tenant, session, case_id, "completed", at,
                                        at + timedelta(minutes=1), _json(run)))
        intent = v1.ActionIntent(id=intent_id, scope=scope, case_id=case_id, case_revision=2,
                                 evidence_snapshot_sha256="0" * 64, policy=s.ACTION_POLICY,
                                 parameters=v1.EscalateParameters(
                                     operation="escalate", transaction_id=transaction,
                                     reason_code="unusual_amount"))
        digest = v1.intent_digest(intent)
        self.rows["action_intents"].append((intent_id, tenant, session, case_id, 2, run_id,
                                            digest, _json(intent)))
        decided = completed - timedelta(minutes=1)
        approval = v1.Approval(id=approval_id, intent=intent, intent_sha256=digest,
                               actor_id=actor, decision="approved", decided_at=decided,
                               expires_at=decided + timedelta(minutes=5), consumed_at=completed)
        self.rows["approvals"].append((approval_id, tenant, session, intent_id, "approved",
                                       completed, _json(approval)))
        act = v1.SimulatedAction(id=action_id, intent=intent, approval_id=approval_id,
                                 intent_sha256=digest, idempotency_key=key, state="succeeded",
                                 created_at=completed, completed_at=completed)
        self.rows["simulated_actions"].append((action_id, tenant, session, approval_id, key,
                                               digest, _json(act)))

    def count(self) -> dict:
        return {t: len(r) for t, r in self.rows.items()}


def _json(model) -> str:
    return json.dumps(model.model_dump(mode="json"), separators=(",", ":"), sort_keys=True)


def generate(builder: FixtureBuilder, seed: int, tenant: uuid.UUID, session: uuid.UUID,
             rows: int, label: str) -> None:
    """Deterministic synthetic rows for one session (decisions section 8.2)."""
    rng = random.Random(f"an01-m1:{seed}:{label}")
    ids = iter(lambda: _uuid(rng), None)
    accounts = [_uuid(rng) for _ in range(max(1, rows // 50))]
    span_us = FIXTURE_DAYS * 86_400 * 1_000_000
    for i in range(rows):
        tid = _uuid(rng)
        currency = _weighted(rng, CURRENCY_WEIGHTS)
        minor = MAX_MINOR_UNITS if rng.random() < 0.001 else rng.randint(1, 5_000_000)
        direction = "debit" if rng.random() < 0.7 else "credit"
        occurred = FIXTURE_START + timedelta(microseconds=rng.randrange(span_us))
        lag = rng.randint(3_600_000_001, 7_200_000_000) if rng.random() < 0.005 \
            else rng.randint(1_000_000, 60_000_000)
        ingested = occurred + timedelta(microseconds=lag)
        builder.transaction(id=tid, tenant=tenant, session=session,
                            external_id=f"m1-{label}-{i:07d}", account=rng.choice(accounts),
                            currency=currency, minor=minor, direction=direction,
                            occurred=occurred, ingested=ingested)
        if rng.random() < 0.001:
            continue  # score unknown: labelled operator row without an outcome
        alerted = rng.random() < 0.02
        builder.outcome(transaction=tid, tenant=tenant, session=session, at=ingested,
                        alerted=alerted)
        if alerted:
            with_action = rng.random() < 0.25
            state = "closed" if with_action else _weighted(rng, CASE_STATES_NO_ACTION)
            case_id, revision = builder.case(rng_or_ids=ids, transaction=tid, tenant=tenant,
                                             session=session, at=ingested, state=state,
                                             minor=minor)
            if with_action:
                completed = ingested + timedelta(seconds=rng.randint(300, 14_400))
                builder.action(ids=ids, transaction=tid, tenant=tenant, session=session,
                               case_id=case_id, revision=revision, at=ingested,
                               completed=completed)


def copy_rows(owner_url: str, builder: FixtureBuilder) -> dict:
    """COPY every built row as the schema owner, one transaction. Returns row counts."""
    with psycopg.connect(owner_url, connect_timeout=10) as conn, conn.transaction():
        for table in LOAD_ORDER:
            rows = builder.rows[table]
            if not rows:
                continue
            columns = sql.SQL(", ").join(sql.Identifier(c) for c in _TABLE_COLUMNS[table])
            with conn.cursor().copy(sql.SQL("COPY {} ({}) FROM STDIN").format(
                    sql.Identifier(table), columns)) as copy:
                for row in rows:
                    copy.write_row(row)
    return builder.count()


def dataset_digest(builder: FixtureBuilder) -> str:
    h = hashlib.sha256()
    for table in LOAD_ORDER:
        for row in builder.rows[table]:
            h.update(repr(tuple(str(v) for v in row)).encode())
    return h.hexdigest()


# ---- 8. index variants and the phase E shadow table (owner provisioning) -----------------

INDEX_DDL = {
    "B": ("CREATE INDEX an01_m1_transactions_session_time"
          " ON transactions (tenant_id, session_id, occurred_at, id)",),
    "C": ("CREATE INDEX an01_m1_simulated_actions_session"
          " ON simulated_actions (tenant_id, session_id)",),
}
INDEX_NAMES = {"B": ("an01_m1_transactions_session_time",),
               "C": ("an01_m1_simulated_actions_session",)}
VARIANT_INDEXES = {"A": (), "B": ("B",), "C": ("B", "C")}
SHADOW_DDL = (
    f"CREATE SCHEMA {SHADOW_SCHEMA}",
    f"CREATE TABLE {SHADOW_SCHEMA}.transactions AS SELECT id, tenant_id, session_id,"
    " occurred_at, ingested_at, body -> 'amount' ->> 'currency' AS currency,"
    " body ->> 'direction' AS direction,"
    " (body -> 'amount' ->> 'minor_units')::numeric AS minor_units FROM public.transactions",
    f"ALTER TABLE {SHADOW_SCHEMA}.transactions ADD PRIMARY KEY (id)",
)
# Created only when the selected common variant has the transactions window index (B or C),
# so both designs are compared with the same window index (first tiny dry run: the shadow
# had it unconditionally while variant A's JSON table did not).
SHADOW_WINDOW_INDEX = (f"CREATE INDEX an01_m1_shadow_session_time ON {SHADOW_SCHEMA}.transactions"
                       " (tenant_id, session_id, occurred_at, id)")


def shadow_ddl(variant: str) -> tuple[str, ...]:
    return SHADOW_DDL + ((SHADOW_WINDOW_INDEX,) if "B" in VARIANT_INDEXES[variant] else ())


def apply_variant(owner_url: str, variant: str) -> dict:
    """Make the cluster's index set equal to `variant`; returns build seconds per index."""
    want = {name for key in VARIANT_INDEXES[variant] for name in INDEX_NAMES[key]}
    built = {}
    with psycopg.connect(owner_url, autocommit=True, connect_timeout=10) as conn:
        have = {r[0] for r in conn.execute(
            "SELECT indexname FROM pg_indexes WHERE schemaname = 'public'"
            " AND left(indexname, 8) = 'an01_m1_'")}
        for name in sorted(have - want):
            conn.execute(sql.SQL("DROP INDEX {}").format(sql.Identifier(name)))
        for key in VARIANT_INDEXES[variant]:
            for name, ddl in zip(INDEX_NAMES[key], INDEX_DDL[key]):
                if name not in have:
                    t0 = time.perf_counter()
                    conn.execute(ddl)
                    built[name] = round(time.perf_counter() - t0, 3)
        conn.execute("ANALYZE")
    return built


def setup_registry() -> dict:
    texts = {f"index:{k}": v[0] for k, v in INDEX_DDL.items()}
    texts.update({f"shadow:{i}": t for i, t in enumerate(SHADOW_DDL)})
    texts["shadow:window_index"] = SHADOW_WINDOW_INDEX
    return {k: {"text": v, "sha256": sha(v)} for k, v in texts.items()}
