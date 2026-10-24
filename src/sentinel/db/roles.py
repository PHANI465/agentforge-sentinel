"""Least-privilege runtime role (C05).

The migration/operator identity owns the schema (tables, triggers, functions) and issues
sessions. The runtime role used by the API gets only the table privileges the service needs:
- no ownership, so it cannot ALTER/DROP tables or drop/disable the audit triggers;
- audit_events: SELECT and INSERT only (UPDATE/DELETE/TRUNCATE are not granted, and the
  append-only triggers still apply to everyone below a superuser/owner);
- api_sessions and schema_migrations: SELECT only (no session issuing, no migrations);
- no DELETE or TRUNCATE anywhere; no CREATE in the public schema.

Every table must appear in RUNTIME_PRIVILEGES; a new migration has to decide its grants
explicitly (tested).

An existing role is used only if it already has the exact runtime shape (review R18): LOGIN,
NOINHERIT and none of SUPERUSER/CREATEDB/CREATEROLE/REPLICATION/BYPASSRLS; no role
memberships (no SET ROLE reach); owns nothing; no CREATE on any database or schema; no
privileges outside the managed tables/sequence, no grant options and no function or
default-privilege grants; and it is not the connecting operator. Otherwise UnsafeRoleError
is raised before any password or privilege change: an operator is never silently demoted
and an unsafe identity is never reported as restricted.

This limits what a compromised runtime credential can do; it does not make storage
tamper-proof against the owner or a superuser.
"""
from __future__ import annotations

import re

import psycopg
from psycopg import sql

RUNTIME_PRIVILEGES: dict[str, tuple[str, ...]] = {
    "api_sessions": ("SELECT",),
    "transactions": ("SELECT", "INSERT"),
    "scoring_outcomes": ("SELECT", "INSERT"),
    "alerts": ("SELECT", "INSERT"),
    "cases": ("SELECT", "INSERT", "UPDATE"),
    "evidence_items": ("SELECT", "INSERT"),
    "agent_runs": ("SELECT", "INSERT", "UPDATE"),
    "action_intents": ("SELECT", "INSERT"),
    "approvals": ("SELECT", "INSERT", "UPDATE"),
    "simulated_actions": ("SELECT", "INSERT"),
    "audit_events": ("SELECT", "INSERT"),
    "schema_migrations": ("SELECT",),
}
SEQUENCES = ("audit_events_seq_seq",)
_ROLE_NAME = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
_SAFE_ATTRIBUTES = {"rolsuper": False, "rolcreatedb": False, "rolcreaterole": False,
                    "rolreplication": False, "rolbypassrls": False, "rolinherit": False,
                    "rolcanlogin": True}
_ATTRIBUTE_NAMES = {"rolsuper": "SUPERUSER", "rolcreatedb": "CREATEDB",
                    "rolcreaterole": "CREATEROLE", "rolreplication": "REPLICATION",
                    "rolbypassrls": "BYPASSRLS", "rolinherit": "INHERIT", "rolcanlogin": "LOGIN"}


class UnsafeRoleError(RuntimeError):
    """An existing role is not a verified least-privilege runtime identity. Nothing was
    changed. The message lists reasons only (never credentials)."""


def unsafe_reasons(conn: psycopg.Connection, role: str) -> list[str]:
    """Why an existing role is not a safe runtime identity (empty list: safe to refresh)."""
    row = conn.execute(
        "SELECT oid, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls,"
        " rolinherit, rolcanlogin, rolname = current_user OR rolname = session_user"
        " AS is_operator FROM pg_roles WHERE rolname = %s", (role,)).fetchone()
    oid, *flags, is_operator = row
    reasons = []
    if is_operator:
        reasons.append("it is the connecting operator identity")
    for (name, safe), value in zip(_SAFE_ATTRIBUTES.items(), flags):
        if value != safe:
            reasons.append(f"{'has' if value else 'lacks'} {_ATTRIBUTE_NAMES[name]}")
    members = [r[0] for r in conn.execute(
        "SELECT r.rolname FROM pg_auth_members m JOIN pg_roles r ON r.oid = m.roleid"
        " WHERE m.member = %s ORDER BY 1", (oid,))]
    if members:
        reasons.append(f"is a member of {members} (SET ROLE reach)")
    owned = conn.execute(
        "SELECT (SELECT count(*) FROM pg_shdepend WHERE refclassid = 'pg_authid'::regclass"
        " AND refobjid = %s AND deptype = 'o')"
        " + (SELECT count(*) FROM pg_database WHERE datdba = %s)", (oid, oid)).fetchone()[0]
    if owned:
        reasons.append(f"owns {owned} object(s)")
    if conn.execute("SELECT count(*) FROM pg_database WHERE has_database_privilege(%s, oid,"
                    " 'CREATE')", (oid,)).fetchone()[0]:
        reasons.append("can CREATE in a database")
    schemas = [r[0] for r in conn.execute(
        "SELECT n.nspname FROM pg_namespace n, aclexplode(n.nspacl) a WHERE a.grantee = %s"
        " AND (a.privilege_type <> 'USAGE' OR a.is_grantable OR n.nspname <> 'public')"
        " ORDER BY 1", (oid,))]
    if schemas:
        reasons.append(f"has direct CREATE/other schema privileges or grant options on "
                       f"{sorted(set(schemas))}")
    managed = set(RUNTIME_PRIVILEGES) | set(SEQUENCES)
    for relname, privilege, grantable in conn.execute(
            "SELECT c.relname, a.privilege_type, a.is_grantable FROM pg_class c,"
            " aclexplode(c.relacl) a WHERE a.grantee = %s ORDER BY 1, 2", (oid,)):
        if grantable:
            reasons.append(f"has a grant option on {relname}")
        elif relname not in managed:
            reasons.append(f"has {privilege} on unmanaged relation {relname}")
    if conn.execute("SELECT count(*) FROM pg_database d, aclexplode(d.datacl) a"
                    " WHERE a.grantee = %s AND a.is_grantable", (oid,)).fetchone()[0]:
        reasons.append("has a grant option on a database")
    if conn.execute("SELECT count(*) FROM pg_proc p, aclexplode(p.proacl) a"
                    " WHERE a.grantee = %s", (oid,)).fetchone()[0]:
        reasons.append("has function privileges")
    if conn.execute("SELECT count(*) FROM pg_default_acl WHERE defaclrole = %s",
                    (oid,)).fetchone()[0]:
        reasons.append("defines default privileges")
    return sorted(set(reasons))


def grant_runtime(admin_url: str, role: str, password: str | None = None) -> None:
    """Create (if needed) and (re)grant the runtime role. Run as the schema owner."""
    if not _ROLE_NAME.fullmatch(role):
        raise ValueError("role must be a lowercase identifier")
    ident = sql.Identifier(role)
    with psycopg.connect(admin_url, autocommit=True) as conn:
        tables = {r[0] for r in conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
            " AND table_type = 'BASE TABLE'")}
        missing = tables - set(RUNTIME_PRIVILEGES)
        if missing:
            raise RuntimeError(f"no runtime grant decided for tables {sorted(missing)}")
        exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,)).fetchone()
        if exists:
            reasons = unsafe_reasons(conn, role)
            if reasons:  # verified before any password or privilege change
                raise UnsafeRoleError(f"refusing existing role {role}: " + "; ".join(reasons))
        else:
            conn.execute(sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE"
                                 " NOREPLICATION NOBYPASSRLS NOINHERIT").format(ident))
        if password is not None:
            conn.execute(sql.SQL("ALTER ROLE {} PASSWORD {}").format(ident,
                                                                      sql.Literal(password)))
        database = conn.execute("SELECT current_database()").fetchone()[0]
        with conn.transaction():
            conn.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
            conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(database), ident))
            conn.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(ident))
            conn.execute(sql.SQL("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {}").format(
                ident))
            for table, privileges in RUNTIME_PRIVILEGES.items():
                if table in tables:
                    conn.execute(sql.SQL("GRANT {} ON {} TO {}").format(
                        sql.SQL(", ").join(sql.SQL(p) for p in privileges),
                        sql.Identifier(table), ident))
            for sequence in SEQUENCES:
                conn.execute(sql.SQL("GRANT USAGE ON SEQUENCE {} TO {}").format(
                    sql.Identifier(sequence), ident))
