"""AN01-r2 known-answer checker. Draft specification aid; not an application test.

Pure standard library, no network, no database, no files and no time-zone database: the
only output is printed lines. It encodes the synthetic fixture in AN01-acceptance-cases.md,
recomputes every expected answer from the proposed report semantics, and compares the
results with the hard-coded values that the documents state. Run from the repository root:

    uv run --locked python docs/analytics/check_an01.py

Exit status 0 means every known answer matched. That says the documents agree with their own
rules. It says nothing about the application: no report route, query or UI exists yet.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import sys
from datetime import datetime, timedelta, timezone

UTC = timezone.utc

# Verified against src/sentinel at dd6518d: contracts/v1.py and scoring.py.
MAX_MINOR_UNITS = 9_000_000_000_000
CURRENCY_EXPONENT = {"USD": 2, "INR": 2, "GBP": 2, "JPY": 0}
LARGE_AMOUNT_MINOR = {"USD": 100_000, "GBP": 100_000, "INR": 8_000_000, "JPY": 150_000}
LARGE_AMOUNT_POINTS, ALERT_AT_OR_ABOVE = 0.6, 0.5
JS_MAX_SAFE_INTEGER = 2**53 - 1
PG_BIGINT_MAX = 2**63 - 1
# Draft values proposed by AN01-r2 (not accepted).
MATCHING_ROW_CAP = 200_000
MAX_REPORT_CURSOR_LENGTH = 400
AGE_BUCKETS = (("lt_1h", 0, 3600), ("1h_8h", 3600, 28800), ("8h_24h", 28800, 86400),
               ("ge_24h", 86400, None))
NON_TERMINAL = ("open", "investigating", "awaiting_approval")
CASE_STATES = ("open", "investigating", "awaiting_approval", "closed", "inconclusive")


def t(text: str) -> datetime:
    """'10-01 08:15:00' means 2026-10-01T08:15:00Z; '09-30 18:30' style is also accepted."""
    date, _, clock = text.partition(" ")
    if clock.count(":") == 1:
        clock += ":00"
    return datetime.fromisoformat(f"2026-{date}T{clock}+00:00")


def uid(suffix: str) -> str:
    return f"00000000-0000-4000-8000-00000000{suffix}"


# ---- fixture (AN01-acceptance-cases.md section 1) -------------------------------------------
# kind: "api" (a POST /v1/transactions request), "operator" (a labelled direct insert by the
# schema owner, simulating a row stored before migration 0002). status is the API response.
# alerted is the stored outcome: True/False, or None when no scoring_outcomes row exists.
FIXTURE = [
    # key  scope ext     id-suffix cur  dir      minor     occurred                ingested               kind        status          alerted
    ("R01", "S1", "an-01", "a001", "USD", "debit", 12_500, "10-01 00:00:00", "10-01 00:00:05", "api", "201", False),
    ("R02", "S1", "an-02", "a002", "USD", "credit", 5_000, "10-01 08:15:00", "10-01 08:15:01", "api", "201", False),
    ("R03", "S1", "an-03", "a003", "USD", "debit", 250_000, "10-01 23:59:59.999", "10-02 00:00:01", "api", "201", True),
    ("R04", "S1", "an-04", "a004", "USD", "debit", 999, "10-02 00:00:00", "10-02 00:00:02", "api", "201", False),
    ("R05", "S1", "an-05", "a005", "INR", "debit", 8_000_000, "10-01 05:30:00", "10-01 05:30:02", "api", "201", True),
    ("R06", "S1", "an-06", "a006", "INR", "credit", 250_050, "10-01 18:31:00", "10-01 18:31:01", "api", "201", False),
    ("R07", "S1", "an-07", "a007", "JPY", "debit", 200_000, "10-01 12:00:00", "10-01 12:00:01", "api", "201", True),
    ("R08", "S1", "an-08", "a008", "GBP", "debit", 7_525, "10-01 09:00:00", "10-02 07:00:00", "api", "201", False),
    ("R09", "S1", "an-01", None, "USD", "debit", 12_500, "10-01 00:00:00", None, "api", "201 replayed", None),
    ("R10", "S1", "an-01", None, "USD", "debit", 13_000, "10-01 00:00:00", None, "api", "409", None),
    ("R11", "S2", "an-11", "a011", "USD", "debit", 777_777, "10-01 10:00:00", "10-01 10:00:01", "api", "201", True),
    ("R12", "T2", "an-12", "a012", "USD", "debit", 500_000, "10-01 11:00:00", "10-01 11:00:01", "api", "201", True),
    ("R13", "S1", "an-13", None, "USD", "debit", 0, "10-01 13:00:00", None, "api", "422", None),
    ("R14", "S1", "an-14", "e014", "USD", "debit", 3_000, "10-01 10:00:00", "10-01 10:00:03", "operator", None, None),
    ("R15", "S1", "an-15", "a015", "GBP", "credit", 10_000, "10-01 14:00:00", "10-01 14:00:02", "api", "201", False),
    ("R16", "S1", "an-16", "a016", "USD", "credit", 2_000, "10-01 10:00:00", "10-01 10:00:04", "api", "201", False),
]
COLUMNS = ("key", "scope", "ext", "id", "cur", "dir", "minor", "occurred", "ingested", "kind",
           "status", "alerted")
ROWS = []
for entry in FIXTURE:
    row = dict(zip(COLUMNS, entry))
    row["occurred"] = t(row["occurred"])
    row["stored"] = row["ingested"] is not None
    row["ingested"] = t(row["ingested"]) if row["stored"] else None
    row["id"] = uid(row["id"]) if row["id"] else None
    row["commit"] = row["ingested"]  # main fixture: committed when stamped (scenarios differ)
    ROWS.append(row)
BY_KEY = {row["key"]: row for row in ROWS}

# Cases of S1 (created by ingestion at ingested_at) and their later workflow, by FakeClock.
CASES = {
    "R03": {"created": t("10-02 00:00:01"), "state": "awaiting_approval", "actions": [],
            "history": [(t("10-02 00:00:01"), "open"), (t("10-02 00:20:00"), "awaiting_approval")]},
    "R05": {"created": t("10-01 05:30:02"), "state": "closed", "actions": [t("10-01 05:46:00")],
            "history": [(t("10-01 05:30:02"), "open"), (t("10-01 05:40:00"), "awaiting_approval"),
                        (t("10-01 05:46:00"), "closed")]},
    "R07": {"created": t("10-01 12:00:01"), "state": "open", "actions": [],
            "history": [(t("10-01 12:00:01"), "open")]},
}
# Operator-recorded disclosures (fraud_disclosures). Labels are deferred from S1: no function
# here reads them; they exist so a future database test can prove S1 never exposes them.
DISCLOSURES = {"R05": (True, t("10-02 07:30"), t("10-02 07:31")),
               "R07": (False, t("10-01 20:00"), t("10-01 20:05"))}

WINDOW = (t("10-01 00:00:00"), t("10-02 00:00:00"))
AS_OF = t("10-02 06:00:00")
READ_AT = t("10-02 08:00:00")
KOLKATA = timedelta(hours=5, minutes=30)  # fixed: no DST in the verified 2000-2037 range


# ---- reference semantics --------------------------------------------------------------------

def rule_alerted(row) -> bool:
    """r1 with prior_count_1h = 0 (every S1 row uses its own account)."""
    score = LARGE_AMOUNT_POINTS if row["minor"] >= LARGE_AMOUNT_MINOR[row["cur"]] else 0.0
    return score >= ALERT_AT_OR_ABOVE


def visible(rows, snapshot, scope="S1"):
    """What one REPEATABLE READ transaction sees: rows committed before its snapshot."""
    return [r for r in rows if r["stored"] and r["scope"] == scope and r["commit"] <= snapshot]


def matching(rows, window, as_of, snapshot):
    lo, hi = window
    return [r for r in visible(rows, snapshot)
            if lo <= r["occurred"] < hi and r["ingested"] <= as_of]


def currency_totals(rows):
    out = {}
    for r in rows:
        c = out.setdefault(r["cur"], {"debit_count": 0, "debit": 0, "credit_count": 0,
                                      "credit": 0})
        c[f"{r['dir']}_count"] += 1
        c[r["dir"]] += r["minor"]
    return {cur: {"debit_count": c["debit_count"], "credit_count": c["credit_count"],
                  "debit_minor": str(c["debit"]), "credit_minor": str(c["credit"]),
                  "gross_minor": str(c["debit"] + c["credit"]),
                  "net_outflow_minor": str(c["debit"] - c["credit"])}
            for cur, c in sorted(out.items())}


def display(minor: int, cur: str) -> str:
    exp = CURRENCY_EXPONENT[cur]
    sign, minor = ("-" if minor < 0 else ""), abs(minor)
    whole, frac = divmod(minor, 10**exp)
    return f"{sign}{whole:,}" + (f".{frac:0{exp}d}" if exp else "") + f" {cur}"


def buckets(window, local_starts):
    """Local-day buckets: [start of local date D, start of D+1), clipped to the window."""
    lo, hi = window
    out = []
    for (day, start), (_, nxt) in zip(local_starts, local_starts[1:]):
        a, b = max(start, lo), min(nxt, hi)
        if a < b:
            out.append({"day": day, "start": a, "end": b,
                        "day_seconds": int((nxt - start).total_seconds()),
                        "covered_seconds": int((b - a).total_seconds())})
    return out


def daily(rows, bucket_list):
    out = {}
    for b in bucket_list:
        for r in rows:
            if b["start"] <= r["occurred"] < b["end"]:
                d = out.setdefault((b["day"], r["cur"]), {"transactions": 0, "alerted": 0,
                                                          "score_unknown": 0, "debit": 0,
                                                          "credit": 0})
                d["transactions"] += 1
                d["alerted"] += r["alerted"] is True
                d["score_unknown"] += r["alerted"] is None
                d[r["dir"]] += r["minor"]
    return {k: (v["transactions"], v["alerted"], v["score_unknown"], str(v["debit"]),
                str(v["credit"])) for k, v in sorted(out.items())}


def workload(window, as_of, read_at):
    lo, hi = window
    created = [k for k, c in CASES.items() if lo <= c["created"] < hi and c["created"] <= as_of]
    by_state = {s: sum(CASES[k]["state"] == s for k in created) for s in CASE_STATES}
    actions = sum(lo <= a < hi and a <= as_of for c in CASES.values() for a in c["actions"])
    ages = {}
    for k, c in CASES.items():
        if c["state"] in NON_TERMINAL:
            age = int((read_at - c["created"]).total_seconds())
            name = next(n for n, a, b in AGE_BUCKETS if age >= a and (b is None or age < b))
            ages[k] = (c["state"], age, name)
    open_counts = {n: sum(v[2] == n for v in ages.values()) for n, _, _ in AGE_BUCKETS}
    return {"created_in_window": sorted(created), "created_by_current_state": by_state,
            "actions_completed_in_window": actions, "open_now": ages,
            "open_now_buckets": open_counts}


def state_at(key, when):
    return [s for at, s in CASES[key]["history"] if at <= when][-1]


def nearest_rank(sorted_values, p):
    """ceil(p*n)-th smallest (1-based): PostgreSQL percentile_disc(p) for 0 < p <= 1."""
    return sorted_values[math.ceil(p * len(sorted_values)) - 1]


def lag_us(r) -> int:
    delta = r["ingested"] - r["occurred"]
    return (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds


def iso(when: datetime) -> str:
    return when.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def filter_digest(report_id, window, tz, as_of, currencies=(), direction=None) -> str:
    canonical = json.dumps({"report_id": report_id, "from": iso(window[0]),
                            "to": iso(window[1]), "tz": tz, "as_of": iso(as_of),
                            "currency": sorted(currencies), "direction": direction},
                           sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(("sentinel.report-filters.an01-s1\n" + canonical).encode()).hexdigest()


def encode_cursor(digest, last, counts) -> str:
    raw = json.dumps(["rows.transactions", digest, iso(last["occurred"]), last["id"], *counts],
                     separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_cursor(cursor: str, digest: str):
    """Mirror of the proposed rules: malformed or mismatched -> 422 invalid_cursor."""
    if len(cursor) > MAX_REPORT_CURSOR_LENGTH or not cursor.isascii():
        return "invalid_cursor"
    try:
        value = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
    except (ValueError, TypeError):
        return "invalid_cursor"
    if not (isinstance(value, list) and len(value) == 6 and value[0] == "rows.transactions"
            and all(isinstance(v, str) for v in value[1:4])
            and all(type(v) is int and v >= 0 for v in value[4:])):
        return "invalid_cursor"
    if value[1] != digest:
        return "invalid_cursor"
    return value


def drilldown(rows_by_snapshot, window, as_of, limit, digest):
    """Pages read at successive snapshots; each page is its own transaction."""
    pages, cursor, first = [], None, None
    for snapshot in rows_by_snapshot:
        found = sorted(matching(snapshot["rows"], window, as_of, snapshot["at"]),
                       key=lambda r: (r["occurred"], r["id"]))
        counts = (len(found), sum(r["alerted"] is not None for r in found))
        first = first or counts
        if cursor is not None:
            pos = decode_cursor(cursor, digest)
            assert pos != "invalid_cursor"
            key = (datetime.fromisoformat(pos[2].replace("Z", "+00:00")), pos[3])
            found = [r for r in found if (r["occurred"], r["id"]) > key]
            first = (pos[4], pos[5])
        page, more = found[:limit], len(found) > limit
        cursor = encode_cursor(digest, page[-1], first) if more else None
        pages.append({"rows": [r["key"] for r in page], "counts": counts,
                      "row_set_changed": counts != first, "next_cursor": cursor})
        if cursor is None:
            break
    return pages


FORMULA_LEAD = ("=", "+", "-", "@", "\t", "\r")


def csv_cell(value, column_type: str) -> str:
    """S2 export rule: typed integer/boolean/null cells verbatim; text gets a quote prefix if
    it could start a formula; then RFC 4180 quoting."""
    if value is None:
        text = ""
    elif column_type in ("integer", "integer-string", "boolean"):
        text = str(value).lower() if column_type == "boolean" else str(value)
    else:
        text = str(value)
        if text.startswith(FORMULA_LEAD):
            text = "'" + text
    if any(ch in text for ch in ',"\r\n'):
        text = '"' + text.replace('"', '""') + '"'
    return text


# ---- expected answers (as written in AN01-acceptance-cases.md section 2) --------------------
EXPECTED = {
    "requests": {"api_requests_all_scopes": 15, "operator_rows": 1, "s1_api_requests": 13,
                 "s1_201_new": 10, "s1_201_replayed": 1, "s1_409": 1, "s1_422": 1,
                 "stored_all_scopes": 13, "stored_s1": 11, "s1_scoring_outcomes": 10,
                 "s1_alerts": 3, "s1_cases": 3},
    "utc_rows": ["R01", "R02", "R03", "R05", "R06", "R07", "R14", "R15", "R16"],
    "utc_totals": {
        "GBP": {"debit_count": 0, "credit_count": 1, "debit_minor": "0", "credit_minor": "10000",
                "gross_minor": "10000", "net_outflow_minor": "-10000"},
        "INR": {"debit_count": 1, "credit_count": 1, "debit_minor": "8000000",
                "credit_minor": "250050", "gross_minor": "8250050",
                "net_outflow_minor": "7749950"},
        "JPY": {"debit_count": 1, "credit_count": 0, "debit_minor": "200000",
                "credit_minor": "0", "gross_minor": "200000", "net_outflow_minor": "200000"},
        "USD": {"debit_count": 3, "credit_count": 2, "debit_minor": "265500",
                "credit_minor": "7000", "gross_minor": "272500",
                "net_outflow_minor": "258500"}},
    "utc_net_display": {"GBP": "-100.00 GBP", "INR": "77,499.50 INR", "JPY": "200,000 JPY",
                        "USD": "2,585.00 USD"},
    "kolkata_rows": ["R01", "R02", "R05", "R07", "R14", "R15", "R16"],
    "kolkata_totals": {
        "GBP": {"debit_count": 0, "credit_count": 1, "debit_minor": "0", "credit_minor": "10000",
                "gross_minor": "10000", "net_outflow_minor": "-10000"},
        "INR": {"debit_count": 1, "credit_count": 0, "debit_minor": "8000000",
                "credit_minor": "0", "gross_minor": "8000000", "net_outflow_minor": "8000000"},
        "JPY": {"debit_count": 1, "credit_count": 0, "debit_minor": "200000",
                "credit_minor": "0", "gross_minor": "200000", "net_outflow_minor": "200000"},
        "USD": {"debit_count": 2, "credit_count": 2, "debit_minor": "15500",
                "credit_minor": "7000", "gross_minor": "22500", "net_outflow_minor": "8500"}},
    "utc_daily": {("2026-10-01", "GBP"): (1, 0, 0, "0", "10000"),
                  ("2026-10-01", "INR"): (2, 1, 0, "8000000", "250050"),
                  ("2026-10-01", "JPY"): (1, 1, 0, "200000", "0"),
                  ("2026-10-01", "USD"): (5, 1, 1, "265500", "7000")},
    "kolkata_instant_buckets": [("2026-10-01", "2026-10-01T00:00:00Z", "2026-10-01T18:30:00Z",
                                 86400, 66600),
                                ("2026-10-02", "2026-10-01T18:30:00Z", "2026-10-02T00:00:00Z",
                                 86400, 19800)],
    "kolkata_instant_daily": {("2026-10-01", "GBP"): (1, 0, 0, "0", "10000"),
                              ("2026-10-01", "INR"): (1, 1, 0, "8000000", "0"),
                              ("2026-10-01", "JPY"): (1, 1, 0, "200000", "0"),
                              ("2026-10-01", "USD"): (4, 0, 1, "15500", "7000"),
                              ("2026-10-02", "INR"): (1, 0, 0, "0", "250050"),
                              ("2026-10-02", "USD"): (1, 1, 0, "250000", "0")},
    "workload": {"created_in_window": ["R05", "R07"],
                 "created_by_current_state": {"open": 1, "investigating": 0,
                                              "awaiting_approval": 0, "closed": 1,
                                              "inconclusive": 0},
                 "actions_completed_in_window": 1,
                 "open_now": {"R03": ("awaiting_approval", 28799, "1h_8h"),
                              "R07": ("open", 71999, "8h_24h")},
                 "open_now_buckets": {"lt_1h": 0, "1h_8h": 1, "8h_24h": 1, "ge_24h": 0}},
    "workload_past_as_of": {"created_in_window": ["R05"],
                            "closed_now": 1, "state_at_as_of": "awaiting_approval",
                            "actions_completed_in_window": 0},
    "quality": {"without_outcome": (1, 9), "alerted_without_alert_row": (0, 3),
                "alerts_without_case": (0, 3), "ingested_after_window_end": (1, 9),
                "lag_us_sorted": [1_000_000, 1_000_000, 1_000_000, 1_001_000, 2_000_000,
                                  2_000_000, 3_000_000, 4_000_000, 5_000_000],
                "lag_p50_us": 2_000_000, "lag_p95_us": 5_000_000, "lag_max_us": 5_000_000},
    "pages_limit4": [["R01", "R05", "R02", "R16"], ["R14", "R07", "R15", "R06"], ["R03"]],
    "page_counts": (9, 8),
    # A reference vector produced by this script's canonicalization, not an independent answer.
    "filter_digest": "8c8263345233e1427e5ecada81cfc42c7dc8943163c9058dd9fc83e0e24a04b6",
    "late_commit_pages": [["R01", "R05", "R02", "R08"], ["R16", "R14", "R07", "R15"],
                          ["R06", "R03"]],
    "late_commit_changed": [False, True, True],
    "late_commit_counts": [(10, 9), (11, 10), (11, 10)],
    "late_commit_usd_debit_before_after": ("265500", "269500"),
    "slow_clock_pages": [["R01", "R05", "R02", "R08"], ["R16", "R14", "L2", "R07"],
                         ["R15", "R06", "R03"]],
    "slow_clock_changed": [False, True, True],
    "r08_at_as_of_0700": True, "r08_at_as_of_065959": False,
    "money": {"rows_until_unsafe": 1001, "sum_1000": 9_000_000_000_000_000,
              "sum_1001": 9_009_000_000_000_000, "cap_sum": 1_800_000_000_000_000_000},
    "csv": [("=HYPERLINK(\"x\")", "text", "\"'=HYPERLINK(\"\"x\"\")\""),
            ("-10000", "integer-string", "-10000"), ("-10000", "text", "'-10000"),
            ("+1", "text", "'+1"), ("@SUM(A1)", "text", "'@SUM(A1)"),
            ("\tx", "text", "'\tx"), ("\rx", "text", "\"'\rx\""), ("an-01", "text", "an-01"),
            ("a,b", "text", "\"a,b\""), (None, "integer-string", ""),
            (True, "boolean", "true")],
    "dst_day_seconds": {("America/New_York", "2026-03-08"): 82800,
                        ("America/New_York", "2026-11-01"): 90000,
                        ("Europe/London", "2026-03-29"): 82800,
                        ("Europe/London", "2026-10-25"): 90000,
                        ("Australia/Lord_Howe", "2026-10-04"): 84600,
                        ("Australia/Lord_Howe", "2026-04-05"): 88200,
                        ("Antarctica/Troll", "2026-03-29"): 79200,
                        ("Antarctica/Troll", "2026-10-25"): 93600},
}

# First instant of a local date and of the next one, as UTC offsets in tzdata 2026e (checked
# once with zoneinfo outside this script; this checker does arithmetic on them only).
DST_FACTS = {("America/New_York", "2026-03-08"): ("2026-03-08T00:00-05:00", "2026-03-09T00:00-04:00"),
             ("America/New_York", "2026-11-01"): ("2026-11-01T00:00-04:00", "2026-11-02T00:00-05:00"),
             ("Europe/London", "2026-03-29"): ("2026-03-29T00:00+00:00", "2026-03-30T00:00+01:00"),
             ("Europe/London", "2026-10-25"): ("2026-10-25T00:00+01:00", "2026-10-26T00:00+00:00"),
             ("Australia/Lord_Howe", "2026-10-04"): ("2026-10-04T00:00+10:30", "2026-10-05T00:00+11:00"),
             ("Australia/Lord_Howe", "2026-04-05"): ("2026-04-05T00:00+11:00", "2026-04-06T00:00+10:30"),
             ("Antarctica/Troll", "2026-03-29"): ("2026-03-29T00:00+00:00", "2026-03-30T00:00+02:00"),
             ("Antarctica/Troll", "2026-10-25"): ("2026-10-25T00:00+02:00", "2026-10-26T00:00+00:00")}


def main() -> int:
    failures = []

    def check(name, actual, expected):
        ok = actual == expected
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f": {actual!r} != {expected!r}"))
        if not ok:
            failures.append(name)

    # Fixture realism: what today's code would store for each request.
    api = [r for r in ROWS if r["kind"] == "api"]
    for r in api:
        valid = 0 < r["minor"] <= MAX_MINOR_UNITS
        assert valid == (r["status"] != "422"), r["key"]
        if r["stored"]:
            assert r["occurred"] <= r["ingested"], r["key"]  # else future_event_time
            assert r["alerted"] == rule_alerted(r), r["key"]  # r1 outcome, prior_count_1h = 0
    check("fixture alerted values equal r1 rule outcomes", True, True)
    s1 = [r for r in ROWS if r["scope"] == "S1"]
    counts = {"api_requests_all_scopes": len(api),
              "operator_rows": sum(r["kind"] == "operator" for r in ROWS),
              "s1_api_requests": sum(r["kind"] == "api" for r in s1),
              "s1_201_new": sum(r["status"] == "201" for r in s1),
              "s1_201_replayed": sum(r["status"] == "201 replayed" for r in s1),
              "s1_409": sum(r["status"] == "409" for r in s1),
              "s1_422": sum(r["status"] == "422" for r in s1),
              "stored_all_scopes": sum(r["stored"] for r in ROWS),
              "stored_s1": sum(r["stored"] for r in s1),
              "s1_scoring_outcomes": sum(r["stored"] and r["alerted"] is not None for r in s1),
              "s1_alerts": sum(r["alerted"] is True for r in s1),
              "s1_cases": sum(r["alerted"] is True for r in s1)}
    check("request vs stored-row counts", counts, EXPECTED["requests"])

    utc = matching(ROWS, WINDOW, AS_OF, READ_AT)
    check("UTC window rows", sorted(r["key"] for r in utc), EXPECTED["utc_rows"])
    totals = currency_totals(utc)
    check("UTC currency totals", totals, EXPECTED["utc_totals"])
    check("UTC net display", {c: display(int(v["net_outflow_minor"]), c)
                              for c, v in totals.items()}, EXPECTED["utc_net_display"])
    check("UTC count across currencies", len(utc), 9)

    kol_window = (t("09-30 18:30"), t("10-01 18:30"))  # date_from 10-01, date_to 10-02 local
    kol = matching(ROWS, kol_window, AS_OF, READ_AT)
    check("Kolkata local-date rows", sorted(r["key"] for r in kol), EXPECTED["kolkata_rows"])
    check("Kolkata currency totals", currency_totals(kol), EXPECTED["kolkata_totals"])

    utc_buckets = buckets(WINDOW, [("2026-10-01", t("10-01 00:00")),
                                   ("2026-10-02", t("10-02 00:00"))])
    check("UTC daily", daily(utc, utc_buckets), EXPECTED["utc_daily"])
    starts = [(f"2026-{d}", t(f"{d} 00:00") - KOLKATA) for d in ("10-01", "10-02", "10-03")]
    kol_buckets = buckets(WINDOW, starts)
    check("Kolkata buckets for the UTC instant window",
          [(b["day"], iso(b["start"]).replace(".000000", ""), iso(b["end"]).replace(".000000", ""),
            b["day_seconds"], b["covered_seconds"]) for b in kol_buckets],
          EXPECTED["kolkata_instant_buckets"])
    check("Kolkata daily for the UTC instant window", daily(utc, kol_buckets),
          EXPECTED["kolkata_instant_daily"])

    check("workload (time bases)", workload(WINDOW, AS_OF, READ_AT), EXPECTED["workload"])
    past = t("10-01 05:43")
    w2 = workload(WINDOW, past, READ_AT)
    check("workload with past as_of reports current state",
          {"created_in_window": w2["created_in_window"],
           "closed_now": w2["created_by_current_state"]["closed"],
           "state_at_as_of": state_at("R05", past),
           "actions_completed_in_window": w2["actions_completed_in_window"]},
          EXPECTED["workload_past_as_of"])

    lags = sorted(lag_us(r) for r in utc)
    alerted_rows = [r for r in utc if r["alerted"] is True]
    check("data quality", {
        "without_outcome": (sum(r["alerted"] is None for r in utc), len(utc)),
        "alerted_without_alert_row": (0, len(alerted_rows)),  # alert inserted atomically
        "alerts_without_case": (sum(r["key"] not in CASES for r in alerted_rows),
                                len(alerted_rows)),
        "ingested_after_window_end": (sum(r["ingested"] >= WINDOW[1] for r in utc), len(utc)),
        "lag_us_sorted": lags, "lag_p50_us": nearest_rank(lags, 0.5),
        "lag_p95_us": nearest_rank(lags, 0.95), "lag_max_us": lags[-1]}, EXPECTED["quality"])

    digest = filter_digest("rows.transactions", WINDOW, "UTC", AS_OF)
    check("filter digest reference vector", digest, EXPECTED["filter_digest"])
    pages = drilldown([{"at": READ_AT, "rows": ROWS}] * 3, WINDOW, AS_OF, 4, digest)
    check("drilldown pages, limit 4, tie broken by id", [p["rows"] for p in pages],
          EXPECTED["pages_limit4"])
    check("drilldown counts unchanged", {p["counts"] for p in pages}, {EXPECTED["page_counts"]})
    check("drilldown row_set_changed all false", [p["row_set_changed"] for p in pages],
          [False, False, False])
    sample = encode_cursor(digest, BY_KEY["R16"], (9, 8))
    check("page-1 cursor length (reference vector)", len(sample), 215)
    check("cursor fits the draft length limit", len(sample) <= MAX_REPORT_CURSOR_LENGTH, True)
    check("cursor for other filters refused",
          decode_cursor(sample, filter_digest("rows.transactions", WINDOW, "UTC",
                                              t("10-02 07:00"))), "invalid_cursor")
    check("malformed cursors refused",
          [decode_cursor(c, digest) for c in ("!!", "W10", sample[:-3], "x" * 401,
                                               base64.urlsafe_b64encode(
                                                   b'["rows.transactions","d","t","i",-1,0]')
                                               .decode())],
          ["invalid_cursor"] * 5)

    # Late commit: as_of = read_at default (08:00:00). L1 stamps 07:59:59.900 and commits at
    # 08:00:00.200, after page 1's snapshot; it sorts before the page-1 cursor.
    as_of_now = READ_AT
    l1 = dict(BY_KEY["R01"], key="L1", ext="an-l1", id=uid("b017"), minor=4000,
              occurred=t("10-01 07:00"), ingested=t("10-02 07:59:59.900"),
              commit=t("10-02 08:00:00.200"), alerted=False)
    with_l1 = ROWS + [l1]
    snapshots = [{"at": READ_AT, "rows": with_l1}, {"at": t("10-02 08:00:10"), "rows": with_l1},
                 {"at": t("10-02 08:00:20"), "rows": with_l1}]
    digest_now = filter_digest("rows.transactions", WINDOW, "UTC", as_of_now)
    late = drilldown(snapshots, WINDOW, as_of_now, 4, digest_now)
    check("late commit: page rows", [p["rows"] for p in late], EXPECTED["late_commit_pages"])
    check("late commit: row_set_changed", [p["row_set_changed"] for p in late],
          EXPECTED["late_commit_changed"])
    check("late commit: per-page counts", [p["counts"] for p in late],
          EXPECTED["late_commit_counts"])
    before = currency_totals(matching(with_l1, WINDOW, as_of_now, READ_AT))["USD"]["debit_minor"]
    after = currency_totals(matching(with_l1, WINDOW, as_of_now,
                                     t("10-02 08:00:10")))["USD"]["debit_minor"]
    check("late commit: same as_of, different totals", (before, after),
          EXPECTED["late_commit_usd_debit_before_after"])

    # Slow clock: a second process runs 3 s behind; L2 stamps 07:59:59 at real 08:00:02 and
    # commits at 08:00:02.050. It sorts after the cursor, so it shifts page 2.
    l2 = dict(BY_KEY["R02"], key="L2", ext="an-l2", id=uid("b018"), dir="debit", minor=1500,
              occurred=t("10-01 11:00"), ingested=t("10-02 07:59:59"),
              commit=t("10-02 08:00:02.050"), alerted=False)
    with_l2 = ROWS + [l2]
    slow = drilldown([{"at": READ_AT, "rows": with_l2},
                      {"at": t("10-02 08:00:10"), "rows": with_l2},
                      {"at": t("10-02 08:00:20"), "rows": with_l2}],
                     WINDOW, as_of_now, 4, digest_now)
    check("slow clock: page rows", [p["rows"] for p in slow], EXPECTED["slow_clock_pages"])
    check("slow clock: row_set_changed", [p["row_set_changed"] for p in slow],
          EXPECTED["slow_clock_changed"])

    # Tie at the availability boundary: ingested_at == as_of is included.
    check("R08 included at as_of 07:00:00 exactly",
          "R08" in {r["key"] for r in matching(ROWS, WINDOW, t("10-02 07:00"), READ_AT)},
          EXPECTED["r08_at_as_of_0700"])
    check("R08 excluded at as_of 06:59:59.999999",
          "R08" in {r["key"] for r in matching(ROWS, WINDOW, t("10-02 06:59:59.999999"),
                                                READ_AT)}, EXPECTED["r08_at_as_of_065959"])

    unsafe = math.ceil((JS_MAX_SAFE_INTEGER + 1) / MAX_MINOR_UNITS)
    check("money bounds", {"rows_until_unsafe": unsafe, "sum_1000": 1000 * MAX_MINOR_UNITS,
                           "sum_1001": 1001 * MAX_MINOR_UNITS,
                           "cap_sum": MATCHING_ROW_CAP * MAX_MINOR_UNITS}, EXPECTED["money"])
    check("single amount is JS-safe; 1000 rows safe; 1001 unsafe; cap fits bigint",
          (MAX_MINOR_UNITS <= JS_MAX_SAFE_INTEGER, 1000 * MAX_MINOR_UNITS <= JS_MAX_SAFE_INTEGER,
           1001 * MAX_MINOR_UNITS > JS_MAX_SAFE_INTEGER,
           MATCHING_ROW_CAP * MAX_MINOR_UNITS <= PG_BIGINT_MAX), (True, True, True, True))

    check("CSV cells", [csv_cell(v, k) for v, k, _ in EXPECTED["csv"]],
          [e for _, _, e in EXPECTED["csv"]])

    check("local day lengths in seconds",
          {k: int((datetime.fromisoformat(b) - datetime.fromisoformat(a)).total_seconds())
           for k, (a, b) in DST_FACTS.items()}, EXPECTED["dst_day_seconds"])

    print(f"{'FAILED' if failures else 'OK'}: {len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
