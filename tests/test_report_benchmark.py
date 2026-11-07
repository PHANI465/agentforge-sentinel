"""AN01-M1 prototype: report SQL known answers, request rules, statement identity, the
measurement budget/lease adapter, phase C controls, and the staged controller.

Real-database tests use the disposable test cluster (tests/conftest.py). Report SQL runs as
a least-privilege runtime role created with the accepted roles.grant_runtime; fixture rows
are inserted by the schema owner as labelled operator fixtures. Budgets used here are
explicitly smaller test budgets; no production or verification limit is changed.
"""
from __future__ import annotations

import itertools
import json
import os
import secrets
import sys
import threading
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import psycopg
import pytest
from psycopg.conninfo import make_conninfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import report_benchmark_support as rb  # noqa: E402

from sentinel.db import roles  # noqa: E402

UTC = timezone.utc
T1 = uuid.UUID("10000000-0000-4000-8000-000000000001")
S1 = uuid.UUID("20000000-0000-4000-8000-000000000001")
S2 = uuid.UUID("20000000-0000-4000-8000-000000000002")
S3 = uuid.UUID("20000000-0000-4000-8000-000000000003")
T2 = uuid.UUID("10000000-0000-4000-8000-000000000002")
S9 = uuid.UUID("20000000-0000-4000-8000-000000000009")
WINDOW = ("2026-10-01T00:00:00Z", "2026-10-02T00:00:00Z")
AS_OF = "2026-10-02T06:00:00Z"
READ_AT = datetime(2026, 10, 2, 8, 0, tzinfo=UTC)
_roles = itertools.count()


def t(text: str) -> datetime:
    day, _, clock = text.partition(" ")
    return datetime.fromisoformat(f"2026-{day}T{clock}+00:00")


def uid(suffix: str) -> uuid.UUID:
    return uuid.UUID(f"00000000-0000-4000-8000-00000000{suffix}")


# (key, scope, external_id, id suffix, currency, direction, minor, occurred, ingested, alerted)
# alerted: True/False, or None for the labelled operator row without an outcome (R14).
# R09, R10 and R13 are rejected/replayed API requests: they are never stored rows.
R2_ROWS = [
    ("R01", (T1, S1), "an-01", "a001", "USD", "debit", 12_500, "10-01 00:00:00", "10-01 00:00:05", False),
    ("R02", (T1, S1), "an-02", "a002", "USD", "credit", 5_000, "10-01 08:15:00", "10-01 08:15:01", False),
    ("R03", (T1, S1), "an-03", "a003", "USD", "debit", 250_000, "10-01 23:59:59.999", "10-02 00:00:01", True),
    ("R04", (T1, S1), "an-04", "a004", "USD", "debit", 999, "10-02 00:00:00", "10-02 00:00:02", False),
    ("R05", (T1, S1), "an-05", "a005", "INR", "debit", 8_000_000, "10-01 05:30:00", "10-01 05:30:02", True),
    ("R06", (T1, S1), "an-06", "a006", "INR", "credit", 250_050, "10-01 18:31:00", "10-01 18:31:01", False),
    ("R07", (T1, S1), "an-07", "a007", "JPY", "debit", 200_000, "10-01 12:00:00", "10-01 12:00:01", True),
    ("R08", (T1, S1), "an-08", "a008", "GBP", "debit", 7_525, "10-01 09:00:00", "10-02 07:00:00", False),
    ("R11", (T1, S2), "an-11", "a011", "USD", "debit", 777_777, "10-01 10:00:00", "10-01 10:00:01", True),
    ("R12", (T2, S9), "an-12", "a012", "USD", "debit", 500_000, "10-01 11:00:00", "10-01 11:00:01", True),
    ("R14", (T1, S1), "an-14", "e014", "USD", "debit", 3_000, "10-01 10:00:00", "10-01 10:00:03", None),
    ("R15", (T1, S1), "an-15", "a015", "GBP", "credit", 10_000, "10-01 14:00:00", "10-01 14:00:02", False),
    ("R16", (T1, S1), "an-16", "a016", "USD", "credit", 2_000, "10-01 10:00:00", "10-01 10:00:04", False),
]
CASES = {"R03": "awaiting_approval", "R05": "closed", "R07": "open", "R11": "closed",
         "R12": "closed"}
ACTIONS = {"R05": "10-01 05:46:00", "R11": "10-01 10:30:00", "R12": "10-01 11:30:00"}


def _ids(prefix: str):
    for n in itertools.count(1):
        yield uuid.UUID(f"{prefix}-0000-4000-8000-{n:012d}")


def build_r2() -> rb.FixtureBuilder:
    """The r2 known-answer fixture (AN01-acceptance-cases section 1) as owner-inserted,
    contract-valid operator rows with fixed identifiers."""
    builder, ids = rb.FixtureBuilder(), _ids("c0000000")
    for key, (tenant, session), ext, suffix, cur, direction, minor, occ, ing, alerted in R2_ROWS:
        builder.transaction(id=uid(suffix), tenant=tenant, session=session, external_id=ext,
                            account=uuid.uuid5(T1, key), currency=cur, minor=minor,
                            direction=direction, occurred=t(occ), ingested=t(ing))
        if alerted is None:
            continue
        builder.outcome(transaction=uid(suffix), tenant=tenant, session=session, at=t(ing),
                        alerted=alerted)
        if key in CASES:
            case_id, revision = builder.case(rng_or_ids=ids, transaction=uid(suffix),
                                             tenant=tenant, session=session, at=t(ing),
                                             state=CASES[key], minor=minor)
            if key in ACTIONS:
                builder.action(ids=ids, transaction=uid(suffix), tenant=tenant,
                               session=session, case_id=case_id, revision=revision,
                               at=t(ing), completed=t(ACTIONS[key]))
    return builder


@pytest.fixture
def runtime_url(database_url):
    """A least-privilege runtime role (accepted roles.grant_runtime) for report SQL."""
    role = f"an01m1_rt_{os.getpid()}_{next(_roles)}"
    password = secrets.token_urlsafe(18)  # synthetic; never printed
    roles.grant_runtime(database_url, role, password)
    yield make_conninfo(database_url, user=role, password=password)
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute(f'DROP OWNED BY "{role}"')
        conn.execute(f'DROP ROLE "{role}"')


@pytest.fixture
def zones():
    return rb.ZoneTable()


@pytest.fixture
def r2db(database_url, runtime_url):
    rb.copy_rows(database_url, build_r2())
    return database_url, runtime_url


def runtime(url, **kw):
    kw.setdefault("read_clock", lambda: READ_AT)
    return rb.Runtime(connect=rb.runtime_connect(url), resources=rb.Resources(),
                      quarantine=rb.ReportQuarantine(), **kw)


def report(url, zones, report_id, scope=(T1, S1), **filters):
    filters.setdefault("read_at", READ_AT)
    if "date_from" not in filters and "from_" not in filters:
        filters["from_"], filters["to"] = WINDOW
    filters.setdefault("as_of", AS_OF)
    request = rb.normalize(zones, report_id, **filters)
    outcome, body = rb.run_report(runtime(url), request, scope, zones)
    assert outcome.kind == "ok", outcome.public()
    assert outcome.rollback == "answered" and not outcome.retired
    return body


# ---- zone table and requests (no database) -------------------------------------------------

def test_zone_table_digest_edges_and_strict_lookups(zones):
    assert zones.digest == rb.ZONE_DIGEST
    assert zones.start("America/New_York", date(1999, 12, 31)) == datetime(1999, 12, 31, 5,
                                                                            tzinfo=UTC)
    assert zones.start("Asia/Kolkata", date(2038, 1, 2)) == datetime(2038, 1, 1, 18, 30,
                                                                     tzinfo=UTC)
    assert zones.start("Asia/Tokyo", date(2038, 1, 2)) == datetime(2038, 1, 1, 15, tzinfo=UTC)
    for zone, day in (("UTC", date(1999, 12, 30)), ("Asia/Tokyo", date(2038, 1, 3))):
        with pytest.raises(LookupError):
            zones.start(zone, day)
    with pytest.raises(LookupError):
        zones.start("Australia/Lord_Howe", date(2026, 1, 1))
    ny = zones.buckets("America/New_York", zones.start("America/New_York", date(2026, 11, 1)),
                       zones.start("America/New_York", date(2026, 11, 3)))
    assert [(b["day"], b["day_seconds"]) for b in ny] == [("2026-11-01", 90000),
                                                          ("2026-11-02", 86400)]
    spring = zones.buckets("Europe/London", t("03-29 00:00:00"), t("03-30 00:00:00"))
    assert [(b["day"], b["day_seconds"], b["covered_seconds"]) for b in spring] == [
        ("2026-03-29", 82800, 82800), ("2026-03-30", 86400, 3600)]


def test_date_mode_validates_after_conversion(zones):
    def req(tz, a, b):
        return rb.normalize(zones, "transactions.daily", read_at=READ_AT, tz=tz,
                            date_from=a, date_to=b)
    with pytest.raises(rb.InvalidRequest):
        req("America/New_York", "1999-12-31", "2000-01-01")
    assert req("America/New_York", "2000-01-01", "2000-01-02").start == datetime(
        2000, 1, 1, 5, tzinfo=UTC)
    with pytest.raises(rb.InvalidRequest):
        req("Asia/Tokyo", "2038-01-01", "2038-01-02")
    with pytest.raises(rb.InvalidRequest):
        req("Asia/Tokyo", "2038-01-02", "2038-01-03")


@pytest.mark.parametrize("filters", [
    {"from_": WINDOW[1], "to": WINDOW[0]},
    {"from_": "2026-07-01T00:00:00Z", "to": "2026-10-01T00:00:01Z"},   # over 92 days
    {"from_": "2026-10-01T00:00:00", "to": WINDOW[1]},                  # no offset
    {"from_": WINDOW[0], "to": WINDOW[1], "tz": "Australia/Lord_Howe"},
    {"from_": WINDOW[0], "to": WINDOW[1], "as_of": "2026-10-02T08:00:01Z"},
    {"from_": WINDOW[0], "to": WINDOW[1], "currencies": ["EUR"]},
    {"from_": WINDOW[0], "to": WINDOW[1], "date_from": "2026-10-01", "date_to": "2026-10-02"},
])
def test_invalid_requests_are_refused(zones, filters):
    with pytest.raises(rb.InvalidRequest):
        rb.normalize(zones, "transactions.currency_totals", read_at=READ_AT, **filters)


def test_workload_rejects_transaction_filters(zones):
    with pytest.raises(rb.InvalidRequest):
        rb.normalize(zones, "cases.workload", read_at=READ_AT, from_=WINDOW[0], to=WINDOW[1],
                     direction="debit")


def test_filter_digest_reference_vector_and_cursor_rules(zones):
    request = rb.normalize(zones, "rows.transactions", read_at=READ_AT, from_=WINDOW[0],
                           to=WINDOW[1], as_of=AS_OF, limit=4)
    assert request.filter_digest == \
        "8c8263345233e1427e5ecada81cfc42c7dc8943163c9058dd9fc83e0e24a04b6"
    cursor = rb.encode_cursor(request, t("10-01 10:00:00"), uid("a016"), (9, 8))
    assert len(cursor) == 215
    assert rb.decode_cursor(cursor, request)[2:] == (9, 8)
    other = rb.normalize(zones, "rows.transactions", read_at=READ_AT, from_=WINDOW[0],
                         to=WINDOW[1], as_of="2026-10-02T07:00:00Z", limit=4)
    import base64

    def enc(value):
        return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")
    good = ["rows.transactions", request.filter_digest, "2026-10-01T10:00:00.000000Z",
            str(uid("a016")), 9, 8]
    bad = ["!!", "W10", cursor[:-3], "x" * 257, enc(good[:5]),
           enc([*good[:4], True, 0]), enc([*good[:4], 9, 10]), enc([*good[:4], -1, 0]),
           enc([*good[:4], 200_001, 0]), enc([*good[:2], "2026-10-01T10:00:00Z", *good[3:]]),
           enc([*good[:3], str(uid("a016")).upper(), 9, 8]),
           enc([*good[:2], "2026-10-02T00:00:00.000000Z", *good[3:]]),
           enc(["cases.workload", *good[1:]])]
    for value in bad:
        with pytest.raises(rb.InvalidCursor):
            rb.decode_cursor(value, request)
    with pytest.raises(rb.InvalidCursor):
        rb.decode_cursor(cursor, other)


# ---- statement identity --------------------------------------------------------------------

# Pinned digests. Changing any statement text changes these, and a measurement checkpoint
# recorded under the old digests then refuses to continue (see the controller tests).
EXPECTED_REGISTRY_SHA256 = "2bf8b1667f24feffdc3ec031cf36107f2e9b45d5def2d7e62b0eff6f5ee51f46"


def test_registry_has_22_tagged_statements_3_controls_and_pinned_digests():
    reg = rb.REGISTRY
    assert len(reg["statements"]) == 22 and set(reg["controls"]) == {"K0", "Ka", "Kr"}
    assert {op: v["sql_statements"] for op, v in reg["operations"].items()} == {
        "totals": 3, "daily_utc": 3, "daily_ny": 3, "workload": 3, "quality": 4,
        "drill_first": 3, "drill_cursor": 3}
    for key, entry in reg["statements"].items():
        op, sid = key.split(":")
        assert entry["text"].startswith(f"/* an01-m1:{op}:{sid} */ SELECT ")
        assert entry["sha256"] == rb.sha(entry["text"])
        for forbidden in ("fraud_disclosures", "account_profiles", "is_fraud", "COMMIT",
                          "INSERT", "UPDATE", "DELETE"):
            assert forbidden not in entry["text"]
    for op, entry in reg["operations"].items():
        assert entry["order"][0] == "K0" and entry["order"][-1] == "Kr"
        assert entry["order"][1::2][:-1] == ["Ka"] * entry["sql_statements"]
    assert reg["sha256"] == EXPECTED_REGISTRY_SHA256


def test_every_transaction_relation_and_join_is_scoped():
    for key, entry in rb.REGISTRY["statements"].items():
        text = entry["text"]
        for alias, table in (("t", "transactions"), ("o", "scoring_outcomes"), ("a", "alerts"),
                             ("c", "cases"), ("s", "simulated_actions")):
            if f" {table} {alias}" in text:
                assert f"{alias}.tenant_id = %(tenant)s" in text, (key, alias)
                assert f"{alias}.session_id = %(session)s" in text, (key, alias)


def test_driver_control_forms_match_psycopg(database_url):
    """K0 is psycopg's generated BEGIN; Ka's server form is what the server records."""
    with psycopg.connect(database_url) as conn, \
            psycopg.connect(database_url, autocommit=True) as observer:
        conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
        conn.read_only = True
        conn.prepare_threshold = None
        assert conn._get_tx_start_command().decode() == rb.CONTROLS["K0"]["driver_form"]
        conn.execute(rb.CONTROLS["Ka"]["template"], ("1000", "1000"))
        seen = observer.execute("SELECT query FROM pg_stat_activity WHERE pid = %s",
                                (conn.info.backend_pid,)).fetchone()[0]
        assert seen == rb.CONTROLS["Ka"]["driver_form"]
        setting = conn.execute("SELECT current_setting('transaction_isolation'),"
                               " current_setting('transaction_read_only'),"
                               " current_setting('statement_timeout')").fetchone()
        assert setting == ("repeatable read", "on", "1s")
        conn.rollback()


def test_accepted_budget_source_is_unchanged_from_the_recorded_provenance():
    import hashlib
    text = (ROOT / rb.BUDGET_SOURCE).read_bytes()
    assert hashlib.sha256(text).hexdigest() == rb.BUDGET_SOURCE_SHA256


# ---- r2 known answers on real PostgreSQL ---------------------------------------------------

def test_r2_currency_totals_and_daily(r2db, zones):
    _, url = r2db
    totals = report(url, zones, "transactions.currency_totals")
    assert totals["consistency"] == {"matching_transactions": 9, "with_outcome": 8}
    assert [(r["currency"], r["currency_exponent"], r["debit_count"], r["debit_minor"],
             r["credit_count"], r["credit_minor"], r["gross_minor"], r["net_outflow_minor"])
            for r in totals["rows"]] == [
        ("GBP", 2, 0, "0", 1, "10000", "10000", "-10000"),
        ("INR", 2, 1, "8000000", 1, "250050", "8250050", "7749950"),
        ("JPY", 0, 1, "200000", 0, "0", "200000", "200000"),
        ("USD", 2, 3, "265500", 2, "7000", "272500", "258500")]
    daily = report(url, zones, "transactions.daily")
    assert [(b["day"], b["day_seconds"], b["covered_seconds"]) for b in daily["buckets"]] == [
        ("2026-10-01", 86400, 86400)]
    assert [(r["currency"], r["transactions"], r["alerted"], r["score_unknown"],
             r["debit_minor"], r["credit_minor"]) for r in daily["rows"]] == [
        ("GBP", 1, 0, 0, "0", "10000"), ("INR", 2, 1, 0, "8000000", "250050"),
        ("JPY", 1, 1, 0, "200000", "0"), ("USD", 5, 1, 1, "265500", "7000")]


def test_r2_kolkata_instant_and_date_windows(r2db, zones):
    _, url = r2db
    daily = report(url, zones, "transactions.daily", tz="Asia/Kolkata")
    assert [(b["day"], b["start"], b["end"], b["day_seconds"], b["covered_seconds"])
            for b in daily["buckets"]] == [
        ("2026-10-01", "2026-10-01T00:00:00.000000Z", "2026-10-01T18:30:00.000000Z", 86400,
         66600),
        ("2026-10-02", "2026-10-01T18:30:00.000000Z", "2026-10-02T00:00:00.000000Z", 86400,
         19800)]
    assert [(r["day"], r["currency"], r["transactions"], r["alerted"], r["score_unknown"],
             r["debit_minor"], r["credit_minor"]) for r in daily["rows"]] == [
        ("2026-10-01", "GBP", 1, 0, 0, "0", "10000"),
        ("2026-10-01", "INR", 1, 1, 0, "8000000", "0"),
        ("2026-10-01", "JPY", 1, 1, 0, "200000", "0"),
        ("2026-10-01", "USD", 4, 0, 1, "15500", "7000"),
        ("2026-10-02", "INR", 1, 0, 0, "0", "250050"),
        ("2026-10-02", "USD", 1, 1, 0, "250000", "0")]
    local = report(url, zones, "transactions.currency_totals", tz="Asia/Kolkata",
                   date_from="2026-10-01", date_to="2026-10-02")
    assert local["consistency"] == {"matching_transactions": 7, "with_outcome": 6}
    assert {r["currency"]: (r["debit_count"], r["debit_minor"], r["credit_count"],
                            r["credit_minor"], r["gross_minor"], r["net_outflow_minor"])
            for r in local["rows"]} == {
        "GBP": (0, "0", 1, "10000", "10000", "-10000"),
        "INR": (1, "8000000", 0, "0", "8000000", "8000000"),
        "JPY": (1, "200000", 0, "0", "200000", "200000"),
        "USD": (2, "15500", 2, "7000", "22500", "8500")}


def test_r2_ingestion_cutoff_includes_ties_and_excludes_later(r2db, zones):
    _, url = r2db
    for as_of, expected in (("2026-10-02T06:00:00Z", 9), ("2026-10-02T06:59:59.999999Z", 9),
                            ("2026-10-02T07:00:00Z", 10)):
        body = report(url, zones, "transactions.currency_totals", as_of=as_of)
        assert body["consistency"]["matching_transactions"] == expected


def test_r2_workload_time_bases_and_past_as_of(r2db, zones):
    _, url = r2db
    body = report(url, zones, "cases.workload")["workload"]
    assert body["created_in_window"]["by_current_state"] == {
        "open": 1, "investigating": 0, "awaiting_approval": 0, "closed": 1, "inconclusive": 0}
    assert body["actions_completed_in_window"]["count"] == 1
    assert body["open_now"]["by_state"] == {"open": 1, "investigating": 0,
                                            "awaiting_approval": 1}
    assert body["open_now"]["age_buckets"] == {"lt_1h": 0, "1h_8h": 1, "8h_24h": 1,
                                               "ge_24h": 0}
    past = report(url, zones, "cases.workload", as_of="2026-10-01T05:43:00Z")["workload"]
    assert past["created_in_window"]["by_current_state"]["closed"] == 1   # current state
    assert sum(past["created_in_window"]["by_current_state"].values()) == 1
    assert past["actions_completed_in_window"]["count"] == 0


def test_r2_data_quality(r2db, zones):
    _, url = r2db
    rows = {r["check"]: (r["value"], r["denominator"])
            for r in report(url, zones, "data_quality.checks")["rows"]}
    assert rows == {"transactions_without_outcome": (1, 9),
                    "alerted_outcome_without_alert": (0, 3), "alert_without_case": (0, 3),
                    "ingested_after_window_end": (1, 9),
                    "ingestion_lag_p50_us": (2_000_000, 9),
                    "ingestion_lag_p95_us": (5_000_000, 9),
                    "ingestion_lag_max_us": (5_000_000, 9)}


def drill_pages(url, zones, as_of=AS_OF, between=None):
    pages, cursor = [], None
    while True:
        body = report(url, zones, "rows.transactions", as_of=as_of, limit=4, cursor=cursor)
        pages.append(body)
        if between:
            between(len(pages))
        cursor = body["next_cursor"]
        if cursor is None:
            return pages


def names(body):
    by_id = {str(uid(suffix)): key for key, _, _, suffix, *_ in R2_ROWS}
    return [by_id.get(r["transaction_id"], r["external_id"]) for r in body["rows"]]


def test_r2_drilldown_keyset_order_ties_and_unknowns(r2db, zones):
    _, url = r2db
    pages = drill_pages(url, zones)
    assert [names(p) for p in pages] == [["R01", "R05", "R02", "R16"],
                                         ["R14", "R07", "R15", "R06"], ["R03"]]
    for page in pages:
        assert page["consistency"] == {"matching_transactions": 9, "with_outcome": 8}
        assert page["page"]["row_set_changed"] is False
    r14 = pages[1]["rows"][0]
    assert (r14["alerted"], r14["score"], r14["scoring_kind"]) == (None, None, None)
    r05 = pages[0]["rows"][1]
    assert (r05["alerted"], r05["case_state"], r05["minor_units"]) == (True, "closed",
                                                                         "8000000")
    assert len(pages[0]["next_cursor"]) == 215


def test_r2_late_commit_is_detected_not_repaired(r2db, zones):
    """Acceptance T1: L1 commits after page 1 and sorts before its cursor."""
    owner, url = r2db

    def commit_l1(page):
        if page == 1:
            builder = rb.FixtureBuilder()
            builder.transaction(id=uid("b017"), tenant=T1, session=S1, external_id="an-l1",
                                account=uid("b017"), currency="USD", minor=4000,
                                direction="debit", occurred=t("10-01 07:00:00"),
                                ingested=t("10-01 07:59:59.900"))
            builder.outcome(transaction=uid("b017"), tenant=T1, session=S1,
                            at=t("10-01 07:59:59.900"), alerted=False)
            rb.copy_rows(owner, builder)
    pages = drill_pages(url, zones, as_of="2026-10-02T08:00:00Z", between=commit_l1)
    assert [names(p) for p in pages] == [["R01", "R05", "R02", "R08"],
                                         ["R16", "R14", "R07", "R15"], ["R06", "R03"]]
    assert [(p["consistency"]["matching_transactions"], p["consistency"]["with_outcome"],
             p["page"]["row_set_changed"]) for p in pages] == [
        (10, 9, False), (11, 10, True), (11, 10, True)]


def test_foreign_scopes_never_counted_even_through_cross_scope_links(r2db, zones):
    owner, url = r2db
    # An adversarial operator row: an outcome for S1's R14 stamped with another scope.
    builder = rb.FixtureBuilder()
    builder.outcome(transaction=uid("e014"), tenant=T2, session=S9, at=t("10-01 10:00:03"),
                    alerted=True)
    rb.copy_rows(owner, builder)
    totals = report(url, zones, "transactions.currency_totals")
    assert totals["consistency"] == {"matching_transactions": 9, "with_outcome": 8}
    usd = next(r for r in report(url, zones, "transactions.daily")["rows"]
               if r["currency"] == "USD")
    assert (usd["transactions"], usd["score_unknown"], usd["debit_minor"]) == (5, 1, "265500")
    s2 = report(url, zones, "transactions.currency_totals", scope=(T1, S2))
    assert [(r["currency"], r["debit_minor"]) for r in s2["rows"]] == [("USD", "777777")]
    wl = report(url, zones, "cases.workload", scope=(T1, S2))["workload"]
    assert wl["actions_completed_in_window"]["count"] == 1
    other = report(url, zones, "cases.workload", scope=(T2, S1))["workload"]
    assert sum(other["created_in_window"]["by_current_state"].values()) == 0
    assert other["actions_completed_in_window"]["count"] == 0


DST_ROWS = [  # session S3: (suffix, occurred, local day expected in the zone named)
    ("d001", "10-31 03:59:59.999999"), ("d002", "11-01 04:00:00"),
    ("d003", "11-02 04:59:59.999999"), ("d004", "11-02 05:00:00"),
    ("d005", "03-09 03:59:59"), ("d006", "03-09 04:00:00"),
    ("d007", "03-28 23:59:59"), ("d008", "03-29 00:00:00"), ("d009", "03-29 22:59:59"),
    ("d010", "03-29 23:00:00"), ("d011", "10-24 23:00:00"), ("d012", "10-25 22:59:59"),
    ("d013", "10-25 23:59:59.999999"), ("d014", "10-26 00:00:00"),
]  # London 2026-10-25 (25 h) runs 10-24T23:00Z .. 10-26T00:00Z; 03-29 (23 h) to 03-29T23:00Z


def test_23_and_25_hour_local_days(database_url, runtime_url, zones):
    builder = rb.FixtureBuilder()
    for suffix, occurred in DST_ROWS:
        when = t(occurred)
        builder.transaction(id=uid(suffix), tenant=T1, session=S3, external_id=f"dst-{suffix}",
                            account=uid(suffix), currency="USD", minor=100, direction="debit",
                            occurred=when, ingested=when + timedelta(seconds=1))
        builder.outcome(transaction=uid(suffix), tenant=T1, session=S3,
                        at=when + timedelta(seconds=1), alerted=False)
    rb.copy_rows(database_url, builder)
    read_at = datetime(2026, 11, 7, tzinfo=UTC)

    def days(tz, a, b):
        body = report(runtime_url, zones, "transactions.daily", scope=(T1, S3), tz=tz,
                      date_from=a, date_to=b, as_of=None, read_at=read_at)
        counts = {r["day"]: r["transactions"] for r in body["rows"]}
        return [(x["day"], x["day_seconds"], counts.get(x["day"], 0)) for x in body["buckets"]]
    assert days("America/New_York", "2026-11-01", "2026-11-03") == [
        ("2026-11-01", 90000, 2), ("2026-11-02", 86400, 1)]
    assert days("America/New_York", "2026-03-08", "2026-03-10") == [
        ("2026-03-08", 82800, 1), ("2026-03-09", 86400, 1)]
    assert days("Europe/London", "2026-03-29", "2026-03-30") == [("2026-03-29", 82800, 2)]
    assert days("Europe/London", "2026-10-25", "2026-10-27") == [("2026-10-25", 90000, 3),
                                                                   ("2026-10-26", 86400, 1)]


def test_runtime_identity_is_read_only_and_restricted(r2db):
    owner, url = r2db
    connect = rb.runtime_connect(url)
    conn = connect()
    try:
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            conn.execute("INSERT INTO api_sessions SELECT * FROM api_sessions LIMIT 0")
        conn.rollback()
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("SELECT * FROM pg_catalog.pg_authid")
        conn.rollback()
        user = conn.execute("SELECT current_user, rolsuper FROM pg_roles"
                            " WHERE rolname = current_user").fetchone()
        assert user["rolsuper"] is False and user["current_user"].startswith("an01m1_rt_")
        conn.rollback()
    finally:
        conn.close()
    assert "commit" not in rb._run_admitted.__code__.co_names


# ---- the measurement budget/lease adapter: interleavings with controlled fakes --------------

class FakeCursor:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


class FakeInfo:
    def __init__(self, conn):
        self.conn = conn

    @property
    def transaction_status(self):
        return (psycopg.pq.TransactionStatus.INTRANS if self.conn.began
                else psycopg.pq.TransactionStatus.IDLE)


class FakeConn:
    """A connection whose statements answer, fail or block on an event (never forever: every
    gate is released in the test's finally)."""

    def __init__(self, block_on: str | None = None, gate: threading.Event | None = None,
                 fail_on: str | None = None):
        self.block_on, self.gate, self.fail_on = block_on, gate, fail_on
        self.began = False
        self.closed_count = 0
        self.statements: list[str] = []
        self.info = FakeInfo(self)

    def fileno(self):
        raise OSError("no socket")

    def execute(self, text, params=None):
        self.began = True
        self.statements.append(text)
        if self.block_on and self.block_on in text:
            self.gate.wait(30)
            raise psycopg.OperationalError("socket closed under the statement")
        if self.fail_on and self.fail_on in text:
            raise psycopg.errors.UndefinedTable("synthetic")
        return FakeCursor([{"n": 1}])

    def rollback(self):
        self.began = False

    def close(self):
        self.closed_count += 1


def fake_runtime(conns, resources=None, **kw):
    connects = {"calls": 0}

    def connect():
        connects["calls"] += 1
        return conns.pop(0)
    rt = rb.Runtime(connect=connect, resources=resources or rb.Resources(),
                    quarantine=rb.ReportQuarantine(), **kw)
    return rt, connects


SEQ = [("G", "/* an01-m1:totals:G */ SELECT 1", {}),
       ("Q", "/* an01-m1:totals:Q */ SELECT 2", {})]


@pytest.fixture
def workflow_quarantine_unchanged():
    from sentinel.agents import budget
    before = budget.QUARANTINE.count()
    yield budget.QUARANTINE
    assert budget.QUARANTINE.count() == before


def _until(predicate, seconds=10.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


def test_healthy_close_releases_once(workflow_quarantine_unchanged):
    conn = FakeConn()
    rt, _ = fake_runtime([conn])
    out = rb.run_statements(rt, SEQ)
    assert out.kind == "ok" and out.rollback == "answered" and out.sql_submitted == 2
    assert conn.closed_count == 1 and out.connection.close_calls == 1
    assert out.connection.admission.releases == 1
    assert rt.resources.counts() == (0, 0) and rt.quarantine.count() == 0
    assert len(conn.statements) == 4   # Ka G Ka Q (BEGIN/ROLLBACK are driver commands)


def test_answered_error_rolls_back_and_closes_once(workflow_quarantine_unchanged):
    conn = FakeConn(fail_on="totals:Q")
    rt, _ = fake_runtime([conn])
    out = rb.run_statements(rt, SEQ)
    assert (out.kind, out.error_class, out.rollback) == ("error", "UndefinedTable", "answered")
    assert conn.closed_count == 1 and rt.resources.counts() == (0, 0)


def test_no_reply_retires_keeps_reservation_until_late_return(workflow_quarantine_unchanged):
    gate = threading.Event()
    conn = FakeConn(block_on="totals:Q", gate=gate)
    rt, _ = fake_runtime([conn], total_ms=400, reserve_ms=250)
    try:
        out = rb.run_statements(rt, SEQ)
        assert out.kind == "no_reply" and out.retired and out.http.startswith("503")
        assert rt.resources.counts() == (0, 1)          # coordinator released, slot held
        assert rt.quarantine.count() == 1 and conn.closed_count == 0
        assert out.connection.close_normal() is False   # the request may not close it
    finally:
        gate.set()
    assert _until(lambda: rt.resources.counts() == (0, 0))
    assert conn.closed_count == 1 and rt.quarantine.count() == 0
    assert out.connection.events == ["retired", "final_close"]
    assert out.connection.admission.releases == 1


def test_delayed_final_close_holds_the_reservation(workflow_quarantine_unchanged):
    sql_gate, close_gate = threading.Event(), threading.Event()
    conn = FakeConn(block_on="totals:G", gate=sql_gate)
    rt, _ = fake_runtime([conn], total_ms=400, reserve_ms=250,
                         final_close_gate=lambda: close_gate.wait(30))
    try:
        out = rb.run_statements(rt, SEQ)
        assert out.kind == "no_reply"
        sql_gate.set()                                   # late return: the last user leaves
        assert _until(lambda: out.connection.users == set())
        assert rt.resources.counts() == (0, 1) and conn.closed_count == 0
    finally:
        sql_gate.set()
        close_gate.set()
    assert _until(lambda: rt.resources.counts() == (0, 0)) and conn.closed_count == 1


def test_reserved_capacity_prevents_the_r52_overflow(workflow_quarantine_unchanged):
    """One retired connection holds a slot (Q=2). Two concurrent admissions: exactly one is
    admitted, so retired connections can never exceed Q."""
    gates = [threading.Event() for _ in range(3)]
    resources = rb.Resources(max_active=2, max_reserved=2)
    first = FakeConn(block_on="totals:G", gate=gates[0])
    rt, _ = fake_runtime([first], resources, total_ms=400, reserve_ms=250)
    try:
        assert rb.run_statements(rt, SEQ).kind == "no_reply"
        conns = [FakeConn(block_on="totals:G", gate=gates[1]),
                 FakeConn(block_on="totals:G", gate=gates[2])]
        rt2, connects = fake_runtime(conns, resources, total_ms=400, reserve_ms=250)
        barrier, results = threading.Barrier(2), []

        def go():
            barrier.wait(5)
            results.append(rb.run_statements(rt2, SEQ).kind)
        threads = [threading.Thread(target=go) for _ in range(2)]
        for th in threads:
            th.start()
        for th in threads:
            th.join(10)
        assert sorted(results) == ["admission_refused", "no_reply"]
        assert connects["calls"] == 1 and resources.peak_reserved == 2
        assert resources.counts() == (0, 2)
    finally:
        for gate in gates:
            gate.set()
    assert _until(lambda: resources.counts() == (0, 0))


def test_admission_limit_m_refuses_before_connect():
    gate = threading.Event()
    resources = rb.Resources(max_active=1, max_reserved=5)
    rt, connects = fake_runtime([FakeConn(block_on="totals:Q", gate=gate), FakeConn()],
                                resources, total_ms=3000, reserve_ms=250)
    holder = threading.Thread(target=rb.run_statements, args=(rt, SEQ))
    holder.start()
    try:
        assert _until(lambda: resources.counts()[0] == 1)
        assert rb.run_statements(rt, SEQ).kind == "admission_refused"
        assert connects["calls"] == 1
    finally:
        gate.set()
        holder.join(10)


def test_admission_invariant_under_concurrent_churn():
    resources = rb.Resources(max_active=2, max_reserved=2)
    stop = time.monotonic() + 1.0

    def churn():
        while time.monotonic() < stop:
            admission = resources.admit()
            if admission:
                admission.end_coordinator()
                admission.release_reservation("test")
                admission.release_reservation("test")   # a second release is a no-op
    threads = [threading.Thread(target=churn) for _ in range(16)]
    for th in threads:
        th.start()
    for th in threads:
        th.join(10)
    assert resources.counts() == (0, 0)
    assert all(a <= 2 and r <= 2 for _, _, a, r in resources.events)


def test_connect_failure_releases_the_reservation_once():
    def connect():
        raise psycopg.OperationalError("synthetic connect failure")
    rt = rb.Runtime(connect=connect, resources=rb.Resources(),
                    quarantine=rb.ReportQuarantine())
    out = rb.run_statements(rt, SEQ)
    assert out.kind == "connect_failed" and out.submitted == 0
    assert rt.resources.counts() == (0, 0)


def test_workflow_quarantine_does_not_affect_report_admission(workflow_quarantine_unchanged):
    sentinel_conn = object()
    workflow_quarantine_unchanged.hold(sentinel_conn)
    try:
        rt, _ = fake_runtime([FakeConn()], rb.Resources(1, 1))
        assert rb.run_statements(rt, SEQ).kind == "ok"
    finally:
        workflow_quarantine_unchanged.release(sentinel_conn)


@pytest.mark.parametrize("total,refused", [(300, True), (349, True), (400, False)])
def test_budget_refusal_boundary(total, refused):
    conn = FakeConn()
    rt, _ = fake_runtime([conn], total_ms=total, reserve_ms=250)
    out = rb.run_statements(rt, SEQ)
    assert (out.kind == "refused_before_submission") is refused
    assert (out.submitted == 0) is refused and (conn.statements == []) is refused


# ---- phase C controls on real PostgreSQL ----------------------------------------------------

def control_runtime(url, total, observer=None, **kw):
    def on_connect(conn):
        if observer is not None:
            observer.watch(conn.info.backend_pid)
            time.sleep(0.05)   # the observer is polling before B starts
    return runtime(url, total_ms=total, on_connect=on_connect, **kw)


def totals_sequence(zones):
    request = rb.normalize(zones, "transactions.currency_totals", read_at=READ_AT,
                           from_=WINDOW[0], to=WINDOW[1], as_of=AS_OF)
    params = rb.parameters(request, (T1, S1), zones)
    return rb.operation_sequence("totals", params)


@pytest.mark.parametrize("total", [300, 349])
def test_c1_refusal_before_submission(r2db, zones, total):
    owner, url = r2db
    observer = rb.Observer(owner)
    out = rb.run_statements(control_runtime(url, total, observer), totals_sequence(zones))
    seen = observer.stop()
    assert out.kind == "refused_before_submission" and out.submitted == 0
    assert seen == [] and out.rollback == "not_needed" and not out.retired


@pytest.mark.parametrize("total", [400, 700, 1250])
def test_c2_submitted_and_cancelled_by_the_server(r2db, zones, total):
    owner, url = r2db
    observer = rb.Observer(owner)
    rt = control_runtime(url, total, observer)
    out = rb.run_statements(rt, [("C2", rb.CONTROL_SQL["C2"], {})])
    seen = observer.stop()
    assert out.kind == "server_cancelled" and out.sqlstate == "57014", out.public()
    assert out.rollback == "answered" and not out.retired and rt.quarantine.count() == 0
    assert any(s["tag"] == "an01-m1:C2:S" and s["state"] == "active" for s in seen)
    assert out.error_at_ms <= total - rt.reserve_ms        # answered inside the work phase
    assert rt.resources.counts() == (0, 0)


@pytest.mark.parametrize("total", [400, 700, 1250])
def test_c3_submitted_and_lock_timeout(r2db, zones, total):
    owner, url = r2db
    observer = rb.Observer(owner)
    with psycopg.connect(owner) as holder:
        holder.execute("LOCK TABLE transactions IN ACCESS EXCLUSIVE MODE")
        try:
            out = rb.run_statements(control_runtime(url, total, observer),
                                    totals_sequence(zones))
        finally:
            holder.rollback()
    seen = observer.stop()
    assert out.kind in ("lock_timeout", "server_cancelled"), out.public()
    assert out.sqlstate in ("55P03", "57014") and out.rollback == "answered"
    assert any(s["tag"] == "an01-m1:totals:G" and s["wait"] == "Lock" for s in seen)


def relay_url(url, relay):
    return make_conninfo(url, host="127.0.0.1", port=str(relay.port), sslmode="disable",
                         gssencmode="disable")


def owner_port(owner):
    return int(psycopg.conninfo.conninfo_to_dict(owner)["port"])


def test_c4_withheld_reply_retires_and_drains(r2db, zones):
    owner, url = r2db
    relay = rb.WithholdingRelay(owner_port(owner), b"an01-m1:totals:G")
    try:
        rt = runtime(relay_url(url, relay), total_ms=1250)
        out = rb.run_statements(rt, totals_sequence(zones))
        assert out.kind == "no_reply" and out.retired, out.public()
        assert relay.sightings, "the relay saw the tagged statement (submission proof)"
        assert _until(lambda: rt.resources.counts() == (0, 0) and rt.quarantine.count() == 0)
        assert out.connection.events == ["retired", "final_close"]
        assert out.connection.close_calls == 1
    finally:
        relay.close()


def test_c5_reserved_capacity_fault_control(r2db, zones):
    """Fault injection, not cancellation latency: two retired leases' final closes are held
    by a test gate, so both Q reservations stay taken; the third request is refused before
    connecting; releasing the gates drains to 0 and a fresh request succeeds."""
    owner, url = r2db
    relay = rb.WithholdingRelay(owner_port(owner), b"an01-m1:totals:G")
    gate = threading.Event()
    resources, quarantine = rb.Resources(2, 2), rb.ReportQuarantine()
    connects = {"relay": 0, "direct": 0}

    def counted(kind, target):
        def connect():
            connects[kind] += 1
            return rb.runtime_connect(target)()
        return connect
    holders = rb.Runtime(connect=counted("relay", relay_url(url, relay)), resources=resources,
                         quarantine=quarantine, total_ms=1250,
                         final_close_gate=lambda: gate.wait(20),
                         read_clock=lambda: READ_AT)
    fresh = rb.Runtime(connect=counted("direct", url), resources=resources,
                       quarantine=quarantine, total_ms=10_000, read_clock=lambda: READ_AT)
    try:
        held = [rb.run_statements(holders, totals_sequence(zones)) for _ in range(2)]
        assert [h.kind for h in held] == ["no_reply", "no_reply"]
        assert _until(lambda: all(h.connection.users == set() for h in held))
        assert resources.counts() == (0, 2) and quarantine.count() == 2
        refused = rb.run_statements(fresh, totals_sequence(zones))
        assert refused.kind == "admission_refused" and connects["direct"] == 0
        gate.set()
        assert _until(lambda: resources.counts() == (0, 0) and quarantine.count() == 0)
        assert [h.connection.close_calls for h in held] == [1, 1]
        after = rb.run_statements(fresh, totals_sequence(zones))
        assert after.kind == "ok" and connects["direct"] == 1
    finally:
        gate.set()
        relay.close()


# ---- the staged controller ------------------------------------------------------------------

import argparse  # noqa: E402
import dataclasses  # noqa: E402

import benchmark_reports as br  # noqa: E402


def stage_args(run_dir, stage, **kw):
    values = {"run_dir": str(run_dir), "stage": stage, "selection": None,
              "authorized_full_size": False, "fault": None, "wsl_host_path": None}
    values.update(kw)
    return argparse.Namespace(**values)


def test_accepted_supervisor_constants_and_smaller_test_budgets():
    accepted = br.ACCEPTED_BUDGET
    assert (accepted.no_new_work_s, accepted.work_deadline_s, accepted.cleanup_reserve_s,
            accepted.controller_deadline_s, accepted.outer_cap_s) == (2300, 2350, 300, 2650,
                                                                       2700)
    assert br.SETUP_DEADLINE_S == 900
    assert br.PROFILES["full"].budget is accepted
    with pytest.raises(ValueError):
        br.smaller_budget([2300, 2400, 300, 2700, 2750], "too large")
    with pytest.raises(ValueError):
        br.smaller_budget([50, 40, 10, 50, 60], "no_new_work after the deadline")
    with pytest.raises(ValueError):
        br.smaller_budget([10, 20, 10, 25, 40], "deadline + reserve != controller")


def test_grid_matches_the_pre_registered_plan():
    totals = br.grid_totals(br.grid(br.PROFILES["full"], n_star=100_000))
    assert totals == {
        "A": {"cells": 21, "operation_runs": 126, "explain_passes": 21},
        "B": {"cells": 152, "operation_runs": 912, "explain_passes": 152},
        "BG": {"cells": 6, "operation_runs": 30, "explain_passes": 0},
        "C": {"cells": 10, "operation_runs": 41, "explain_passes": 0},
        "D": {"cells": 1, "operation_runs": 20, "explain_passes": 0},
        "E": {"cells": 4, "operation_runs": 24, "explain_passes": 4}}
    c = [x for x in br.grid(br.PROFILES["full"]) if x.phase == "C"]
    assert sum(x.timed for x in c if x.expect in ("C1", "C2", "C3", "C4")) == 37


def test_full_profile_refuses_without_explicit_authorization(tmp_path):
    br.Run.create(tmp_path / "run", br.PROFILES["full"])
    with pytest.raises(br.RunError, match="authorization"):
        br.stage_command(stage_args(tmp_path / "run", "S1"))


def test_changed_digests_refuse_a_stage(tmp_path):
    run = br.Run.create(tmp_path / "run", br.PROFILES["tiny"])
    cp = run.checkpoint()
    cp["identities"]["statements"]["totals:Q"] = "0" * 64
    run.save_checkpoint(cp)
    with pytest.raises(br.RunError, match="digests changed"):
        br.stage_command(stage_args(run.dir, "S1"))
    assert not run.lock_path.exists()


def test_foreign_directory_and_marker_mismatch_are_refused(tmp_path):
    (tmp_path / "plain").mkdir()
    with pytest.raises(br.RunError):
        br.Run(tmp_path / "plain").load()
    run = br.Run.create(tmp_path / "run", br.PROFILES["tiny"])
    (run.dir / br.MARKER).write_text(json.dumps({"owner": "someone-else",
                                                 "dir": run.canonical()}))
    with pytest.raises(br.RunError, match="ownership"):
        run.load()


def test_preflight_refusal_launches_nothing(tmp_path, monkeypatch):
    run = br.Run.create(tmp_path / "run", br.PROFILES["tiny"])
    huge = dataclasses.replace(br.PROFILES["tiny"], min_free_bytes=10 ** 18)
    monkeypatch.setitem(br.PROFILES, "tiny", huge)
    assert br.stage_command(stage_args(run.dir, "S1")) == br.EXIT["refused"]
    state = run.load()
    assert state["stages"]["S1"]["status"] == "refused" and state["worker"] is None
    assert not run.lock_path.exists() and run.cluster_names() == []
    with pytest.raises(br.RunError, match="already ran"):
        br.stage_command(stage_args(run.dir, "S1"))   # no automatic resume or retry


def test_stages_after_selection_need_the_offline_selection(tmp_path):
    run = br.Run.create(tmp_path / "run", br.PROFILES["tiny"])
    with pytest.raises(br.RunError, match="selection"):
        br.stage_command(stage_args(run.dir, "S4"))


def test_identity_checks_never_touch_foreign_or_unresolved_processes():
    me = local_identity = br.local_stack.identity(os.getpid())
    stale = {**local_identity, "start": local_identity["start"] + 1}
    assert br.terminate_owned(stale, time.monotonic() + 5) == "unconfirmed:reused"
    assert br.local_stack.identity(os.getpid()) == me                   # untouched
    assert br.worker_resolved({"pending": True}) is False               # no pid recorded
    assert br.worker_resolved({"pending": True, "pid": os.getpid()}) is False  # alive


def test_public_records_refuse_paths_users_and_dsns(tmp_path):
    run = br.Run.create(tmp_path / "run", br.PROFILES["tiny"])
    for bad in ({"x": str(run.dir)}, {"x": "postgresql://u@h/db"}, {"x": str(Path.home())},
                {"x": "Traceback (most recent call last)"}):
        with pytest.raises(br.RunError):
            br.write_public(run, tmp_path / "out.json", bad)
    br.write_public(run, tmp_path / "ok.json", {"x": "an01-m1"})


def _phase_a(medians: dict, seq_scan: bool) -> dict:
    cells = {}
    for variant, by_op in medians.items():
        for op in rb.OPERATIONS:
            scans = [["transactions", "Seq Scan" if seq_scan and variant == "A"
                      else "Index Scan"]]
            cells[f"A:{variant}:{op}"] = {"status": "complete", "median_ms": by_op.get(op, 10),
                                          "explain": [{"plan": {"scans": scans}}]}
    return cells


def test_rule1_common_index_is_joint_and_never_picks_unmeasured():
    base = {op: 100 for op in rb.OPERATIONS}
    faster = {**base, "totals": 40}
    records = {"windows": _phase_a({"A": base, "B": faster, "C": faster}, False),
               "linux": _phase_a({"A": base, "B": base, "C": base}, False)}
    assert br.rule_common_index(records)["value"]["variant"] == "B"
    slower = {**base, "quality": 120}
    records["linux"] = _phase_a({"A": base, "B": slower, "C": slower}, False)
    records["windows"] = _phase_a({"A": base, "B": faster, "C": faster}, False)
    assert br.rule_common_index(records)["value"]["variant"] == "A"   # >10% regression
    del records["linux"]["A:B:totals"]
    assert br.rule_common_index({"windows": records["windows"]})["value"]["demonstrated"] \
        is False


def test_rule2_n_star_and_missing_evidence_are_not_demonstrated():
    profile = br.PROFILES["tiny"]

    def phase_b(slow_at=None, drop=None):
        cells = {}
        for size in profile.sizes:
            for dataset in ("D1", "D2"):
                for op in rb.OPERATIONS:
                    for filt in (br.FILTERS if op != "workload" else ("base",)):
                        ms = 3000 if slow_at and size >= slow_at else 10
                        cells[f"B:{dataset}:{size}:{op}:{filt}"] = {
                            "status": "complete",
                            "timed": [{"kind": "ok", "elapsed_ms": ms}] * 5}
        for op in rb.TRANSACTION_OPS:
            cells[f"BG:{op}"] = {"status": "complete",
                                 "timed": [{"kind": "too_large", "elapsed_ms": 5}] * 5}
        if drop:
            del cells[drop]
        return cells
    good = br.rule_n_star({"windows": phase_b(), "linux": phase_b()}, profile.sizes)
    assert good["value"] == {"n_star": 80, "demonstrated": True}
    slow = br.rule_n_star({"windows": phase_b(slow_at=60), "linux": phase_b()}, profile.sizes)
    assert slow["value"]["n_star"] == 40 and slow["proposal"] == "propose N* = 40"
    missing = br.rule_n_star({"windows": phase_b(drop="B:D2:20:totals:base"),
                              "linux": phase_b()}, profile.sizes)
    assert missing["value"] == {"n_star": None, "demonstrated": False}
    report = br.final_report({"windows": phase_b()}, profile)
    assert report["rule6_status"] == "not demonstrated"
    assert report["rule2_n_star"]["value"]["demonstrated"] is False


@pytest.fixture
def tiny_run(tmp_path, pg_cluster):
    """A tiny-profile run directory; any cluster it starts is stopped in teardown."""
    run = br.Run.create(tmp_path / "run", br.PROFILES["tiny"])
    yield run
    state = run.load()
    if state.get("worker") or state.get("blocked"):
        br.recover_command(argparse.Namespace(run_dir=str(run.dir)))
    for name in run.cluster_names():
        stack, data = run.cluster(name)
        br.stop_cluster(stack, data, time.monotonic() + 60)


SMALL = br.smaller_budget([12, 15, 30, 45, 50], "test (smaller than accepted)")


def test_stalled_setup_is_stopped_at_the_whole_stage_deadline(tiny_run):
    """The worker blocks inside setup (fault injection). The independent supervisor stops
    the verified owned worker at its work deadline and the cluster it started; cleanup is
    reported only after both are confirmed gone."""
    t0 = time.monotonic()
    code = br.stage_command(stage_args(tiny_run.dir, "S1", fault="stall-setup"), budget=SMALL)
    elapsed = time.monotonic() - t0
    state = tiny_run.load()
    rec = state["stages"]["S1"]
    assert code == br.EXIT["incomplete"] and rec["status"] == "deadline"
    assert rec["cleanup"]["worker"] == "stopped"
    assert rec["cleanup"]["cluster:D2"] in ("stopped", "already-stopped")
    assert rec["cells"] == {"prepare:D2": "started"}
    assert SMALL.work_deadline_s <= elapsed < SMALL.controller_deadline_s
    assert state["worker"] is None and state["blocked"] is None
    assert not tiny_run.lock_path.exists()
    stack, data = tiny_run.cluster("D2")
    assert br.local_stack.database_state(stack, data) == "stopped"
    public = json.loads((tiny_run.dir / "public" / f"S1-{state['platform']}.json").read_text())
    assert public["record"]["fault_injection"] == "stall-setup"


def test_unconfirmed_stop_blocks_further_stages_until_recover(tiny_run):
    """If the stop cannot be confirmed (here: an injected refusal to stop), the stage exits
    nonzero, keeps the run lock and recovery state, and refuses further stages; `recover`
    then stops only the verified owned worker and cluster."""
    code = br.stage_command(stage_args(tiny_run.dir, "S1", fault="stall-setup"), budget=SMALL,
                            terminate=lambda record, until: "unconfirmed:test-refused-stop")
    state = tiny_run.load()
    assert code == br.EXIT["unconfirmed"] and state["blocked"]
    assert state["stages"]["S1"]["status"] == "cleanup-unconfirmed"
    assert tiny_run.lock_path.exists()
    assert br.local_stack.classify(state["worker"]) == "owned"   # still running, kept
    with pytest.raises(br.RunError, match="recovery is pending"):
        br.stage_command(stage_args(tiny_run.dir, "S2"), budget=SMALL)
    assert br.recover_command(argparse.Namespace(run_dir=str(tiny_run.dir))) == 0
    state = tiny_run.load()
    assert state["blocked"] is None and state["worker"] is None
    assert not tiny_run.lock_path.exists()


def test_stalled_connector_after_a_real_prepare(tiny_run):
    """S1 prepares the tiny D2 for real; S2's first acquisition then never returns (fault
    injection). The stage ends at the whole-stage deadline with the cell interrupted and the
    remaining cells not run; nothing is retried."""
    assert br.stage_command(stage_args(tiny_run.dir, "S1"), budget=br.TINY_BUDGET) == 0
    datasets = tiny_run.datasets()
    assert datasets["D2"]["status"] == "complete"
    assert datasets["D2"]["rows"]["transactions"] == br.PROFILES["tiny"].d2_rows()
    code = br.stage_command(stage_args(tiny_run.dir, "S2", fault="stall-connect"),
                            budget=SMALL)
    rec = tiny_run.load()["stages"]["S2"]
    assert code == br.EXIT["incomplete"] and rec["status"] == "deadline"
    assert rec["cleanup"]["worker"] == "stopped"
    statuses = sorted(set(rec["cells"].values()))
    assert statuses == ["interrupted (outcome unknown)", "not_run"]
    assert list(rec["cells"].values()).count("interrupted (outcome unknown)") == 1


def test_full_grid_preflight_refuses_s4_under_the_design_bound(tmp_path):
    """Finding pinned, not fixed: with the tiny-measured row size, D1 + D2 exceed the
    design's 4 GB cluster bound from S4 on, so the full grid's own preflight refuses there.
    Nothing is deleted, resized or reconfigured to make it pass."""
    full = br.PROFILES["full"]
    assert br.preflight(tmp_path, full, "S1", None)["cluster_data_estimate"] <= 4 * br.GB
    s4 = br.preflight(tmp_path, full, "S4", None)
    assert s4["cluster_data_estimate"] > full.max_cluster_bytes
    assert "estimated clusters exceed the profile maximum" in s4["problems"]
    assert s4["ok"] is False


def test_guard_cursor_carries_an_issued_pair_and_strict_rule_is_kept(zones):
    """Regression for the first tiny smoke (BG:drill_cursor InvalidCursor): the harness now
    builds the guard cursor from a pair a served page 1 could have issued (<= cap)."""
    assert br.issued_pair(81, 80, 80) == (80, 80)
    assert br.issued_pair(81, 81, 80) == (80, 80)
    assert br.issued_pair(40, 39, 80) == (40, 39)
    request = rb.normalize(zones, "rows.transactions", read_at=READ_AT, from_=WINDOW[0],
                           to=WINDOW[1], limit=4)
    over = rb.encode_cursor(request, t("10-01 10:00:00"), uid("a016"), (81, 80))
    with pytest.raises(rb.InvalidCursor):
        rb.decode_cursor(over, request, cap=80)
    issued = rb.encode_cursor(request, t("10-01 10:00:00"), uid("a016"),
                              br.issued_pair(81, 80, 80))
    assert rb.decode_cursor(issued, request, cap=80)[2:] == (80, 80)


def test_phase_e_shadow_index_follows_the_common_variant():
    assert rb.SHADOW_WINDOW_INDEX not in rb.shadow_ddl("A")
    assert rb.shadow_ddl("B")[-1] == rb.SHADOW_WINDOW_INDEX
    assert rb.shadow_ddl("C")[-1] == rb.SHADOW_WINDOW_INDEX


def test_cleanup_deletes_only_owned_cluster_data_and_is_repeatable(tmp_path):
    """Regression (first S9 cleanup: a second cleanup crashed on already-deleted data).
    Only the marked cluster's own pg directory is removed; everything else is kept."""
    run = br.Run.create(tmp_path / "run", br.PROFILES["tiny"])
    stack, _ = run.cluster("D2", create=True)
    (stack.dir / "pg").mkdir()
    (stack.dir / "pg" / "placeholder").write_text("x")
    (run.dir / "public" / "keep.json").write_text("{}")
    args = argparse.Namespace(run_dir=str(run.dir), delete_owned_data=True)
    assert br.cleanup_command(args) == 0
    assert not (stack.dir / "pg").exists() and (stack.dir / br.local_stack.MARKER).exists()
    assert (run.dir / "public" / "keep.json").exists()
    assert br.cleanup_command(args) == 0           # repeatable, no traceback
    run.acquire_lock({"pid": os.getpid()})
    with pytest.raises(br.RunError, match="run lock"):
        br.cleanup_command(args)
