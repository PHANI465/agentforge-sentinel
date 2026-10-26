"""C01: typed HTTP contract, scoped case list, session view, overview, safe errors and the
approval-creation clock hardening."""
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import psycopg
import pytest

from sentinel.contracts.v1 import ApprovalDecisionInput
from test_thin_path import ANALYST, Harness, alerting_case, txn


@pytest.fixture
def h(database_url, clock):
    return Harness(database_url, clock)


def open_cases(h, token, clock, n, prefix="c"):
    """n alerting cases created at the same instant (ties on created_at)."""
    ids = []
    for i in range(n):
        body = h.call("POST", "/v1/transactions", token,
                      txn(clock, f"{prefix}{i}", minor_units=250_000)).json()
        ids.append(body["case"]["id"])
    return ids


def all_pages(h, token, limit, **params):
    seen, cursor, pages = [], None, 0
    while True:
        query = {"limit": limit, **params, **({"cursor": cursor} if cursor else {})}
        response = h.client.get("/v1/cases", params=query,
                                headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200, response.text
        page = response.json()
        assert len(page["items"]) <= limit
        seen.extend(item["id"] for item in page["items"])
        pages += 1
        cursor = page["next_cursor"]
        if cursor is None:
            return seen, pages
        assert pages < 50


# ---- case list --------------------------------------------------------------------------

def test_case_list_is_session_scoped_and_stably_paginated_with_ties(h, clock):
    token = h.service.create_session(ANALYST)[0]
    mine = open_cases(h, token, clock, 5)
    tenant = uuid.UUID(h.service.authenticate(token).scope.tenant_id.hex)
    other = h.service.create_session(ANALYST, tenant_id=tenant)[0]
    theirs = open_cases(h, other, clock, 2, prefix="x")

    seen, pages = all_pages(h, token, limit=2)
    assert pages == 3
    assert len(seen) == len(set(seen)) == 5
    # created_at ties are broken by id, newest first.
    assert seen == sorted(mine, reverse=True)
    assert not set(seen) & set(theirs)
    assert all_pages(h, other, limit=10)[0] == sorted(theirs, reverse=True)


def test_case_list_pages_are_stable_while_new_cases_arrive(h, clock):
    token = h.service.create_session(ANALYST)[0]
    first = open_cases(h, token, clock, 3)
    page1 = h.call("GET", "/v1/cases?limit=2", token).json()
    clock.advance(seconds=1)
    open_cases(h, token, clock, 2, prefix="late")  # newer than the cursor position
    page2 = h.call("GET", f"/v1/cases?limit=2&cursor={page1['next_cursor']}", token).json()
    got = [i["id"] for i in page1["items"]] + [i["id"] for i in page2["items"]]
    assert got == sorted(first, reverse=True)


def test_case_list_state_filter_and_summary_fields(h, clock):
    token = h.service.create_session(ANALYST)[0]
    case = alerting_case(h, token, clock)
    open_cases(h, token, clock, 1, prefix="o")
    h.call("POST", f"/v1/cases/{case['id']}/investigations", token, {"expected_revision": 1})
    page = h.call("GET", "/v1/cases?state=awaiting_approval", token).json()
    assert [item["id"] for item in page["items"]] == [case["id"]]
    item = page["items"][0]
    assert item["state"] == "awaiting_approval" and item["revision"] == 3
    assert item["score_semantics"] == "heuristic" and item["scoring_kind"] == "rule"
    assert item["amount"] == {"currency": "USD", "minor_units": 250_000, "currency_exponent": 2,
                              "schema_version": "1.0"}
    assert item["external_id"] == "big"
    assert len(h.call("GET", "/v1/cases?state=open", token).json()["items"]) == 1


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "limit=x", "state=bogus",
                                   "cursor=not-a-cursor", "cursor=" + "A" * 300])
def test_case_list_rejects_bad_parameters_safely(h, query):
    token = h.service.create_session(ANALYST)[0]
    response = h.call("GET", f"/v1/cases?{query}", token)
    assert response.status_code == 422
    assert set(response.json()) <= {"error", "details"}
    assert response.json()["error"] in {"invalid_request", "invalid_cursor"}


def test_case_list_requires_read_capability(h):
    token = h.service.create_session(frozenset({"ingest_transaction"}))[0]
    assert h.call("GET", "/v1/cases", token).json() == {"error": "permission_denied"}


# ---- session view and overview ----------------------------------------------------------

def test_session_view_exposes_no_secrets(h, clock):
    token, ctx = h.service.create_session(ANALYST)
    response = h.call("GET", "/v1/session", token)
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "tenant_id": str(ctx.scope.tenant_id), "session_id": str(ctx.scope.session_id),
        "actor_id": str(ctx.actor_id), "actor_kind": "human",
        "capabilities": sorted(ANALYST), "expires_at": (clock() + timedelta(hours=8)).isoformat()
        .replace("+00:00", "Z")}
    assert token not in response.text
    assert h.client.get("/v1/session").json() == {"error": "unauthenticated"}


def test_overview_counts_only_own_session(h, clock):
    token = h.service.create_session(ANALYST)[0]
    case = alerting_case(h, token, clock)  # 3 non-alerting + 1 alerting transaction
    h.call("POST", f"/v1/cases/{case['id']}/investigations", token, {"expected_revision": 1})
    other = h.service.create_session(ANALYST)[0]
    open_cases(h, other, clock, 2, prefix="x")
    body = h.call("GET", "/v1/overview", token).json()
    assert body["cases_by_state"] == {"open": 0, "investigating": 0, "awaiting_approval": 1,
                                      "closed": 0, "inconclusive": 0}
    assert (body["transactions"], body["alerts"], body["simulated_actions"]) == (4, 1, 0)
    assert body["investigator"]["name"] == "deterministic-investigator"
    assert set(body["investigator"]) == {"name", "version"}


# ---- safe errors ------------------------------------------------------------------------

def test_unknown_route_and_method_use_safe_error_shape(h):
    token = h.service.create_session(ANALYST)[0]
    assert h.call("GET", "/v1/nope", token).json() == {"error": "not_found"}
    response = h.call("DELETE", "/v1/cases", token)
    assert (response.status_code, response.json()) == (405, {"error": "method_not_allowed"})
    bad_id = h.call("GET", "/v1/cases/not-a-uuid", token)
    assert (bad_id.status_code, bad_id.json()) == (422, {"error": "invalid_request"})


# ---- approval creation clock hardening (C01 review item) --------------------------------

def test_approval_issued_after_lock_wait_is_not_already_expired(database_url, clock):
    h = Harness(database_url, clock)
    token = h.service.create_session(ANALYST)[0]
    case = alerting_case(h, token, clock)
    h.call("POST", f"/v1/cases/{case['id']}/investigations", token, {"expected_revision": 1})
    intent_id = h.call("GET", f"/v1/cases/{case['id']}", token).json()[
        "action_intents"][0]["intent"]["id"]
    ctx = h.service.authenticate(token)
    blocker = psycopg.connect(database_url)
    blocker.execute("SELECT 1 FROM cases WHERE id = %s FOR UPDATE", (case["id"],))
    pool = ThreadPoolExecutor(1)
    future = pool.submit(h.service.record_approval, ctx, ApprovalDecisionInput(
        action_intent_id=intent_id, decision="approved"))
    try:
        deadline = time.monotonic() + 10
        with psycopg.connect(database_url, autocommit=True) as watch:
            while not watch.execute("SELECT count(*) FROM pg_stat_activity WHERE"
                                    " wait_event_type = 'Lock' AND datname = current_database()"
                                    ).fetchone()[0]:
                assert time.monotonic() < deadline, "approval never waited on the case lock"
                time.sleep(0.02)
        clock.advance(minutes=10)  # longer than the approval TTL
    finally:
        blocker.rollback()
        blocker.close()
    approval = future.result(timeout=30)
    pool.shutdown()
    decided = datetime.fromisoformat(approval["decided_at"].replace("Z", "+00:00"))
    expires = datetime.fromisoformat(approval["expires_at"].replace("Z", "+00:00"))
    assert decided == clock()
    assert expires > clock()


def test_migration_0003_backfills_existing_cases(h, clock, database_url):
    from sentinel import db
    token = h.service.create_session(ANALYST)[0]
    ids = open_cases(h, token, clock, 2)
    with db.connect(database_url) as conn:  # rewind to the pre-0003 schema, data retained
        conn.execute("DROP INDEX cases_session_listing; DROP INDEX cases_session_state;"
                     " ALTER TABLE cases DROP COLUMN created_at;"
                     " DELETE FROM schema_migrations WHERE name = '0003_case_listing.sql'")
    assert db.migrate(database_url) == ["0003_case_listing.sql"]
    with db.connect(database_url) as conn:
        rows = conn.execute("SELECT created_at, body ->> 'created_at' AS body_at FROM cases"
                            ).fetchall()
    assert len(rows) == 2
    assert all(r["created_at"] == datetime.fromisoformat(r["body_at"].replace("Z", "+00:00"))
               for r in rows)
    assert {i["id"] for i in h.call("GET", "/v1/cases", token).json()["items"]} == set(ids)
