"""C05: least-privilege runtime role. The runtime can run the application path but cannot
change schema, drop or bypass audit protections, rewrite audit rows, issue sessions or run
migrations. Migration/operator work stays with the separate owner (here the test superuser)."""
import uuid

import psycopg
import pytest
from psycopg.conninfo import make_conninfo

from sentinel import db
from sentinel.db import roles
from test_thin_path import ANALYST, Harness, alerting_case, approve_pending


@pytest.fixture
def runtime(database_url):
    role = f"sentinel_runtime_{uuid.uuid4().hex[:10]}"
    roles.grant_runtime(database_url, role)
    try:
        yield role, make_conninfo(database_url, user=role)
    finally:
        with psycopg.connect(database_url, autocommit=True) as conn:
            conn.execute(f'DROP OWNED BY "{role}"')
            conn.execute(f'DROP ROLE "{role}"')


def test_every_table_has_an_explicit_runtime_grant(database_url):
    with psycopg.connect(database_url) as conn:
        tables = {r[0] for r in conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
            " AND table_type = 'BASE TABLE'")}
    assert tables == set(roles.RUNTIME_PRIVILEGES)  # a new migration must decide its grants


def test_runtime_role_runs_the_application_path(database_url, runtime, clock):
    _, runtime_url = runtime
    operator = Harness(database_url, clock)  # sessions are issued by the operator, not runtime
    token = operator.service.create_session(ANALYST)[0]
    h = Harness(runtime_url, clock)
    case = alerting_case(h, token, clock)
    assert h.call("POST", f"/v1/cases/{case['id']}/investigations", token,
                  {"expected_revision": 1}).status_code == 200
    approval = approve_pending(h, token, case["id"])
    done = h.call("POST", "/v1/actions", token, {"approval_id": approval["id"],
                                                 "idempotency_key": str(uuid.uuid4())})
    assert done.status_code == 200
    assert h.call("GET", "/v1/overview", token).json()["simulated_actions"] == 1
    assert len(h.call("GET", f"/v1/cases/{case['id']}/audit", token).json()) == 6


@pytest.mark.parametrize("statement", [
    "ALTER TABLE cases ADD COLUMN injected text",
    "DROP TRIGGER audit_events_no_update ON audit_events",
    "ALTER TABLE audit_events DISABLE TRIGGER ALL",
    "DROP TABLE audit_events",
    "CREATE TABLE public.injected (x int)",
    "CREATE FUNCTION public.injected() RETURNS int LANGUAGE sql AS 'SELECT 1'",
    "TRUNCATE audit_events",
    "DELETE FROM cases",
    "INSERT INTO api_sessions SELECT * FROM api_sessions LIMIT 0",
    "UPDATE api_sessions SET capabilities = '{}'",
    "INSERT INTO schema_migrations (name) VALUES ('9999_injected.sql')",
])
def test_runtime_role_cannot_change_schema_or_protections(database_url, runtime, statement):
    _, runtime_url = runtime
    with psycopg.connect(runtime_url) as conn:
        with pytest.raises((psycopg.errors.InsufficientPrivilege,
                            psycopg.errors.WrongObjectType)):
            conn.execute(statement)


def test_runtime_role_cannot_grant_privileges(database_url, runtime):
    """A non-owner GRANT only warns ("no privileges were granted"); verify nothing changed."""
    role, runtime_url = runtime
    with psycopg.connect(runtime_url, autocommit=True) as conn:
        conn.execute("GRANT SELECT ON cases TO PUBLIC")
        conn.execute("GRANT INSERT ON api_sessions TO PUBLIC")
    with psycopg.connect(database_url) as conn:
        for table, privilege in (("cases", "SELECT"), ("api_sessions", "INSERT")):
            assert conn.execute("SELECT has_table_privilege('public', %s, %s)",
                                (table, privilege)).fetchone()[0] is False
        assert conn.execute("SELECT has_table_privilege(%s, 'api_sessions', 'INSERT')",
                            (role,)).fetchone()[0] is False


def test_runtime_role_cannot_rewrite_audit_even_with_rows(database_url, runtime, clock):
    _, runtime_url = runtime
    operator = Harness(database_url, clock)
    token = operator.service.create_session(ANALYST)[0]
    alerting_case(Harness(runtime_url, clock), token, clock)
    with psycopg.connect(runtime_url) as conn:
        for statement in ("UPDATE audit_events SET body = '{}'", "DELETE FROM audit_events"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with conn.transaction():
                    conn.execute(statement)


def test_runtime_role_cannot_migrate(database_url, runtime):
    _, runtime_url = runtime
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("DELETE FROM schema_migrations WHERE name = '0003_case_listing.sql'")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        db.migrate(runtime_url)


def test_grant_runtime_is_idempotent_and_rejects_unsafe_names(database_url, runtime):
    role, _ = runtime
    roles.grant_runtime(database_url, role)  # re-applying the same grants is safe
    with pytest.raises(ValueError):
        roles.grant_runtime(database_url, 'bad"; DROP TABLE cases; --')
