"""Regressions for Codex review 0119ca7: R18 (existing runtime identities are verified, never
silently trusted or demoted), R19 (connect_timeout detected from parsed options) and R20
(bounded HTTP-method metric labels), plus SENTINEL_LOG_LEVEL=off.

Role tests run only in the disposable per-test databases of the test cluster, with newly
created role names that are dropped afterwards. No real operator role is touched."""
import io
import logging
import uuid

import psycopg
import pytest
from psycopg import sql

import sentinel.db as sdb
from sentinel import observability
from sentinel.db import roles
from test_thin_path import ANALYST, Harness, alerting_case, approve_pending

OLD_PASSWORD = "SYNTHETIC-OLD-PASSWORD-r18"
# Resolved with a fallback so these tests exercise grant_runtime on code that predates the
# error class (there they fail with DID NOT RAISE, i.e. the unsafe role was accepted).
UnsafeRoleError = getattr(roles, "UnsafeRoleError", Exception)


# ---- R18 ---------------------------------------------------------------------------------

@pytest.fixture
def make_role(database_url):
    created = []

    def make(attributes="LOGIN NOINHERIT", password=OLD_PASSWORD):
        name = f"r18_{uuid.uuid4().hex[:10]}"
        with psycopg.connect(database_url, autocommit=True) as conn:
            conn.execute(sql.SQL("CREATE ROLE {} " + attributes + " PASSWORD {}").format(
                sql.Identifier(name), sql.Literal(password)))
        created.append(name)
        return name

    yield make
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("ALTER TABLE audit_events ENABLE TRIGGER ALL")
        for name in created:
            conn.execute(sql.SQL("REASSIGN OWNED BY {} TO CURRENT_USER").format(
                sql.Identifier(name)))
            conn.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(name)))
            conn.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(name)))


def snapshot(database_url, role):
    """Everything a rejection must leave unchanged: attributes, password hash, memberships,
    ACL entries naming the role, and whether PUBLIC may CREATE in public."""
    with psycopg.connect(database_url) as conn:
        attrs = conn.execute(
            "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls,"
            " rolinherit, rolcanlogin, rolpassword FROM pg_authid WHERE rolname = %s",
            (role,)).fetchone()
        members = conn.execute(
            "SELECT roleid::regrole::text FROM pg_auth_members m JOIN pg_roles r"
            " ON r.oid = m.member WHERE r.rolname = %s ORDER BY 1", (role,)).fetchall()
        acl = conn.execute(
            "SELECT c.relname, a.privilege_type, a.is_grantable FROM pg_class c,"
            " aclexplode(c.relacl) a JOIN pg_roles r ON r.oid = a.grantee"
            " WHERE r.rolname = %s ORDER BY 1, 2", (role,)).fetchall()
        schema = conn.execute(
            "SELECT a.privilege_type FROM pg_namespace n, aclexplode(n.nspacl) a"
            " WHERE n.nspname = 'public' AND a.grantee = 0 ORDER BY 1").fetchall()
    return attrs, members, acl, schema


@pytest.mark.parametrize("attributes", [
    "SUPERUSER LOGIN", "LOGIN NOINHERIT CREATEROLE", "LOGIN NOINHERIT CREATEDB",
    "LOGIN NOINHERIT BYPASSRLS", "LOGIN NOINHERIT REPLICATION", "LOGIN INHERIT",
    "NOLOGIN NOINHERIT",
])
def test_r18_unsafe_existing_attributes_are_rejected_unchanged(database_url, make_role,
                                                               attributes):
    role = make_role(attributes)
    before = snapshot(database_url, role)
    with pytest.raises(UnsafeRoleError) as raised:
        roles.grant_runtime(database_url, role, password="SYNTHETIC-NEW-PASSWORD")
    assert snapshot(database_url, role) == before  # no password, grant or schema change
    assert OLD_PASSWORD not in str(raised.value) and "SYNTHETIC-NEW" not in str(raised.value)


def test_r18_existing_superuser_cannot_be_used_to_disable_audit(database_url, make_role):
    role = make_role("SUPERUSER LOGIN")
    with pytest.raises(UnsafeRoleError):
        roles.grant_runtime(database_url, role)
    with psycopg.connect(database_url) as conn:
        assert conn.execute("SELECT rolsuper FROM pg_roles WHERE rolname = %s",
                            (role,)).fetchone()[0] is True  # not silently demoted either


def test_r18_direct_schema_create_grant_is_rejected(database_url, make_role):
    role = make_role()
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute(sql.SQL("GRANT CREATE ON SCHEMA public TO {}").format(sql.Identifier(role)))
    before = snapshot(database_url, role)
    with pytest.raises(UnsafeRoleError, match="CREATE"):
        roles.grant_runtime(database_url, role)
    assert snapshot(database_url, role) == before


def test_r18_database_create_privilege_is_rejected(database_url, make_role):
    role = make_role()
    with psycopg.connect(database_url, autocommit=True) as conn:
        db_name = conn.execute("SELECT current_database()").fetchone()[0]
        conn.execute(sql.SQL("GRANT CREATE ON DATABASE {} TO {}").format(
            sql.Identifier(db_name), sql.Identifier(role)))
    with pytest.raises(UnsafeRoleError, match="CREATE"):
        roles.grant_runtime(database_url, role)


def test_r18_membership_reaching_another_role_is_rejected(database_url, make_role):
    privileged = make_role("NOLOGIN NOINHERIT CREATEDB")
    role = make_role()
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute(sql.SQL("GRANT {} TO {}").format(sql.Identifier(privileged),
                                                      sql.Identifier(role)))
    before = snapshot(database_url, role)
    with pytest.raises(UnsafeRoleError, match="member"):
        roles.grant_runtime(database_url, role)
    assert snapshot(database_url, role) == before


def test_r18_role_owning_objects_is_rejected(database_url, make_role):
    role = make_role()
    with psycopg.connect(database_url, autocommit=True) as conn:
        # A sequence, not a table: an unmanaged table would trip the grant-map check instead.
        conn.execute("CREATE SEQUENCE r18_owned_seq")
        conn.execute(sql.SQL("ALTER SEQUENCE r18_owned_seq OWNER TO {}").format(
            sql.Identifier(role)))
    with pytest.raises(UnsafeRoleError, match="owns"):
        roles.grant_runtime(database_url, role)


def test_r18_grant_option_on_managed_table_is_rejected(database_url, make_role):
    role = make_role()
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute(sql.SQL("GRANT SELECT ON cases TO {} WITH GRANT OPTION").format(
            sql.Identifier(role)))
    with pytest.raises(UnsafeRoleError, match="grant option"):
        roles.grant_runtime(database_url, role)


def test_r18_verified_runtime_refresh_is_idempotent_and_drops_stale_grants(
        database_url, make_role, clock):
    role = make_role()  # safe shape: LOGIN NOINHERIT, nothing else
    roles.grant_runtime(database_url, role)
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute(sql.SQL("GRANT DELETE ON cases TO {}").format(sql.Identifier(role)))
    roles.grant_runtime(database_url, role, password="SYNTHETIC-ROTATED")  # refresh + rotate
    with psycopg.connect(database_url) as conn:
        assert conn.execute("SELECT has_table_privilege(%s, 'cases', 'DELETE')",
                            (role,)).fetchone()[0] is False
    runtime_url = psycopg.conninfo.make_conninfo(database_url, user=role)
    operator = Harness(database_url, clock)
    token = operator.service.create_session(ANALYST)[0]
    h = Harness(runtime_url, clock)
    case = alerting_case(h, token, clock)
    h.call("POST", f"/v1/cases/{case['id']}/investigations", token, {"expected_revision": 1})
    approval = approve_pending(h, token, case["id"])
    assert h.call("POST", "/v1/actions", token, {"approval_id": approval["id"],
                                                 "idempotency_key": str(uuid.uuid4())}
                  ).status_code == 200


def test_r18_operator_identity_itself_is_rejected(database_url):
    with psycopg.connect(database_url) as conn:
        me = conn.execute("SELECT current_user").fetchone()[0]
    with pytest.raises(UnsafeRoleError):
        roles.grant_runtime(database_url, me)


# ---- R19 ---------------------------------------------------------------------------------

@pytest.fixture
def connect_kwargs(monkeypatch):
    seen = []

    def fake_connect(url, **kwargs):
        seen.append(kwargs)
        raise psycopg.OperationalError("intercepted")

    monkeypatch.setattr(sdb.psycopg, "connect", fake_connect)
    return seen


@pytest.mark.parametrize("url, expected", [
    ("host=127.0.0.1 dbname=sentinel user=app", 10),
    ("postgresql://app@127.0.0.1/sentinel", 10),
    ("host=127.0.0.1 dbname=sentinel application_name=connect_timeout_probe", 10),
    ("postgresql://app@127.0.0.1/sentinel?application_name=connect_timeout_probe", 10),
    ("host=127.0.0.1 dbname=connect_timeout user=app password=connect_timeout=1", 10),
    ("postgresql://app:connect_timeout%3D1@127.0.0.1/connect_timeout", 10),
    ("host=127.0.0.1 dbname=sentinel connect_timeout=3", None),
    ("postgresql://app@127.0.0.1/sentinel?connect_timeout=3", None),
    ("postgresql://app@127.0.0.1/sentinel?sslmode=disable&connect_timeout=0", None),
])
def test_r19_timeout_default_uses_parsed_options(connect_kwargs, url, expected):
    with pytest.raises(psycopg.OperationalError):
        sdb.connect(url)
    (kwargs,) = connect_kwargs
    assert kwargs.get("connect_timeout") == expected


# ---- R20 ---------------------------------------------------------------------------------

def test_r20_unsupported_methods_share_one_metric_label(database_url, clock):
    h = Harness(database_url, clock)
    for i in range(64):
        assert h.client.request(f"XMETHOD{i}", "/healthz").status_code == 405
    h.client.get("/healthz")
    snap = h.client.app.state.metrics.snapshot()
    assert snap["requests"]["OTHER /healthz 405"] == 64
    assert sum(snap["latency_ms"]["OTHER /healthz"].values()) == 64
    assert snap["requests"]["GET /healthz 200"] == 1
    assert len(snap["requests"]) == 2 and len(snap["latency_ms"]) == 2


def test_r20_logged_method_is_bounded(database_url, clock, caplog):
    import json
    caplog.set_level(logging.INFO)
    h = Harness(database_url, clock)
    h.client.request("XMETHOD-INJECTED-r20", "/healthz")
    events = [json.loads(r.getMessage()) for r in caplog.records if r.name == "sentinel.http"]
    assert events[-1]["method"] == "OTHER"


# ---- SENTINEL_LOG_LEVEL=off ----------------------------------------------------------------

@pytest.fixture
def isolated_logging():
    logger, root = logging.getLogger("sentinel"), logging.getLogger()
    saved = (list(logger.handlers), logger.level, logger.propagate, list(root.handlers),
             root.level)
    stream = io.StringIO()
    root_handler = logging.StreamHandler(stream)
    root.addHandler(root_handler)
    root.setLevel(logging.DEBUG)
    yield stream
    logger.handlers[:] = saved[0]
    logger.setLevel(saved[1])
    logger.propagate = saved[2]
    root.handlers[:] = saved[3]
    root.setLevel(saved[4])


def emit_probe():
    observability.emit(logging.getLogger("sentinel.http"), "http_request", request_id="probe",
                       status=200)


@pytest.mark.parametrize("sequence", [["off"], ["INFO", "off"]])
def test_log_level_off_silences_sentinel_output(isolated_logging, monkeypatch, capsys,
                                                sequence):
    for level in sequence:
        monkeypatch.setenv("SENTINEL_LOG_LEVEL", level)
        observability.configure_logging()
    emit_probe()
    assert isolated_logging.getvalue() == ""  # nothing reaches a root handler
    assert "probe" not in capsys.readouterr().err  # nor the sentinel stderr handler
    monkeypatch.setenv("SENTINEL_LOG_LEVEL", "INFO")
    observability.configure_logging()
    emit_probe()
    assert "probe" in isolated_logging.getvalue()  # turning it back on works
