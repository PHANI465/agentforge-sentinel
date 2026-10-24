"""Regressions for Codex re-review b3b34ac (remaining R18): privileges reachable through
PUBLIC (including column ACLs), same-name relations in other schemas, and effective CREATE
on other schemas. Fresh per-test databases and new role names only; nothing is printed."""
import uuid

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

from sentinel.db import roles
from conftest import R18_OLD_PASSWORD as OLD_PASSWORD
from test_c05_review_regressions import UnsafeRoleError
from test_thin_path import ANALYST, Harness, alerting_case, approve_pending


def full_snapshot(database_url, role):
    """Role attributes/password hash plus every ACL that names the role or PUBLIC on tables,
    columns and schemas. Compared, never printed."""
    with psycopg.connect(database_url) as conn:
        role_row = conn.execute(
            "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls,"
            " rolinherit, rolcanlogin, rolpassword FROM pg_authid WHERE rolname = %s",
            (role,)).fetchone()
        oid = conn.execute("SELECT oid FROM pg_roles WHERE rolname = %s", (role,)).fetchone()
        grantees = [0, oid[0]] if oid else [0]
        tables = conn.execute(
            "SELECT c.oid::regclass::text, a.grantee, a.privilege_type FROM pg_class c,"
            " aclexplode(c.relacl) a WHERE a.grantee = ANY(%s) ORDER BY 1, 2, 3",
            (grantees,)).fetchall()
        columns = conn.execute(
            "SELECT t.attrelid::regclass::text, t.attname, a.grantee, a.privilege_type"
            " FROM pg_attribute t, aclexplode(t.attacl) a WHERE a.grantee = ANY(%s)"
            " ORDER BY 1, 2, 3, 4", (grantees,)).fetchall()
        schemas = conn.execute(
            "SELECT n.nspname, a.grantee, a.privilege_type FROM pg_namespace n,"
            " aclexplode(n.nspacl) a WHERE a.grantee = ANY(%s) ORDER BY 1, 2, 3",
            (grantees,)).fetchall()
    return role_row, tables, columns, schemas


def admin(database_url, *statements):
    with psycopg.connect(database_url, autocommit=True) as conn:
        for statement in statements:
            conn.execute(statement)


def role_exists(database_url, role) -> bool:
    with psycopg.connect(database_url) as conn:
        return conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s",
                            (role,)).fetchone() is not None


def assert_refused_unchanged(database_url, role):
    """Refused for an existing candidate AND for a brand-new role (the environment itself is
    unsafe); no password, attribute, grant or PUBLIC ACL changes; no role created."""
    new_role = f"r18n_{uuid.uuid4().hex[:8]}"
    before = full_snapshot(database_url, role)
    with pytest.raises(UnsafeRoleError) as raised:
        roles.grant_runtime(database_url, role, password="SYNTHETIC-NEW-PASSWORD-r18b")
    assert full_snapshot(database_url, role) == before
    message = str(raised.value)
    assert OLD_PASSWORD not in message and "SYNTHETIC-NEW" not in message
    public_before = full_snapshot(database_url, role)[1:]
    try:
        with pytest.raises(UnsafeRoleError):
            roles.grant_runtime(database_url, new_role)
        assert not role_exists(database_url, new_role)
        assert full_snapshot(database_url, role)[1:] == public_before
    finally:
        if role_exists(database_url, new_role):  # only on the unfixed code
            admin(database_url, sql.SQL("DROP OWNED BY {}").format(sql.Identifier(new_role)),
                  sql.SQL("DROP ROLE {}").format(sql.Identifier(new_role)))
    return message


def test_r18b_public_column_update_on_sessions_is_refused(database_url, make_role):
    role = make_role()
    admin(database_url, "GRANT UPDATE (capabilities) ON public.api_sessions TO PUBLIC")
    message = assert_refused_unchanged(database_url, role)
    assert "public.api_sessions" in message and "PUBLIC" in message


def test_r18b_same_name_relation_in_other_schema_is_not_managed(database_url, make_role):
    role = make_role()
    admin(database_url, "CREATE SCHEMA probe_other",
          "CREATE TABLE probe_other.api_sessions (x int)",
          "GRANT USAGE ON SCHEMA probe_other TO PUBLIC",
          sql.SQL("GRANT DELETE ON probe_other.api_sessions TO {}").format(
              sql.Identifier(role)))
    before = full_snapshot(database_url, role)
    with pytest.raises(UnsafeRoleError) as raised:  # a candidate grant on an unmanaged object
        roles.grant_runtime(database_url, role)
    assert full_snapshot(database_url, role) == before
    assert "probe_other.api_sessions" in str(raised.value)


def test_r18b_public_create_on_another_schema_is_refused(database_url, make_role):
    role = make_role()
    admin(database_url, "CREATE SCHEMA probe_other",
          "GRANT USAGE, CREATE ON SCHEMA probe_other TO PUBLIC")
    message = assert_refused_unchanged(database_url, role)
    assert "probe_other" in message and "CREATE" in message


def test_r18b_public_privilege_on_unmanaged_table_is_refused(database_url, make_role):
    role = make_role()
    admin(database_url, "CREATE SCHEMA probe_other",
          "CREATE TABLE probe_other.notes (x int)",
          "GRANT USAGE ON SCHEMA probe_other TO PUBLIC",
          "GRANT SELECT ON probe_other.notes TO PUBLIC")
    assert "probe_other.notes" in assert_refused_unchanged(database_url, role)


def test_r18b_public_read_within_the_grant_map_is_allowed(database_url, make_role):
    """Not over-strict: PUBLIC SELECT on a managed table adds nothing beyond the map."""
    role = make_role()
    admin(database_url, "GRANT SELECT ON public.cases TO PUBLIC")
    roles.grant_runtime(database_url, role)


def test_r18b_effective_privileges_exactly_match_the_map_after_refresh(database_url,
                                                                      make_role, clock):
    role = make_role()
    admin(database_url,
          sql.SQL("GRANT DELETE, TRUNCATE ON public.cases TO {}").format(sql.Identifier(role)),
          sql.SQL("GRANT UPDATE (capabilities) ON public.api_sessions TO {}").format(
              sql.Identifier(role)))
    roles.grant_runtime(database_url, role)  # stale direct grants are removed by refresh
    kinds = ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")
    with psycopg.connect(database_url) as conn:
        for table, allowed in roles.RUNTIME_PRIVILEGES.items():
            for kind in kinds:
                has = conn.execute("SELECT has_table_privilege(%s, %s, %s)",
                                   (role, f"public.{table}", kind)).fetchone()[0]
                assert has is (kind in allowed), (table, kind)
                if kind in ("INSERT", "UPDATE", "SELECT", "REFERENCES"):
                    column = conn.execute("SELECT has_any_column_privilege(%s, %s, %s)",
                                          (role, f"public.{table}", kind)).fetchone()[0]
                    assert column is (kind in allowed), (table, kind, "column")
    runtime_url = make_conninfo(database_url, user=role)
    token = Harness(database_url, clock).service.create_session(ANALYST)[0]
    h = Harness(runtime_url, clock)
    case = alerting_case(h, token, clock)
    h.call("POST", f"/v1/cases/{case['id']}/investigations", token, {"expected_revision": 1})
    approval = approve_pending(h, token, case["id"])
    assert h.call("POST", "/v1/actions", token, {"approval_id": approval["id"],
                                                 "idempotency_key": str(uuid.uuid4())}
                  ).status_code == 200
    with psycopg.connect(runtime_url) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("UPDATE api_sessions SET capabilities = '{}'")
