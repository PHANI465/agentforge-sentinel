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

The database environment is checked too, for new and existing roles alike (review R18
follow-up): PUBLIC may not hold table or column privileges on a managed object beyond its
grant map, any privilege on an unmanaged non-system relation, CREATE on a non-system schema
other than `public` (whose PUBLIC CREATE this tool revokes), or CREATE on a database.
Managed objects are identified by exact schema-qualified identity (public.<name>), never by
a bare name another schema could reuse. After granting, effective privileges (direct and
via PUBLIC) are re-checked against the map inside the same transaction; any mismatch rolls
back the role creation, password change and grants.

Scope: the current database's relations, columns, schemas and the cluster's databases.
PUBLIC's default EXECUTE on functions and TEMP on databases are accepted; other databases'
objects are not scanned.

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
    # C07: provisioned by the operator; the API only reads them for decision-time features.
    "account_profiles": ("SELECT",),
    "fraud_disclosures": ("SELECT",),
}
SEQUENCES = ("audit_events_seq_seq",)
SCHEMA = "public"
_TABLE_KINDS = ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")
_COLUMN_KINDS = ("SELECT", "INSERT", "UPDATE", "REFERENCES")
# System namespaces whose PUBLIC grants are PostgreSQL defaults, not this tool's concern.
_SYSTEM_NAMESPACES = ("n.nspname NOT IN ('pg_catalog', 'information_schema')"
                      " AND left(n.nspname, 8) <> 'pg_toast' AND left(n.nspname, 7) <> 'pg_temp'")
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


def managed_objects(conn: psycopg.Connection) -> dict[int, tuple[str, frozenset[str]]]:
    """OID -> (qualified name, allowed privileges) for the managed tables and sequences."""
    objects = {}
    wanted = [(t, frozenset(p)) for t, p in RUNTIME_PRIVILEGES.items()]
    wanted += [(seq, frozenset({"USAGE"})) for seq in SEQUENCES]
    for name, allowed in wanted:
        oid = conn.execute("SELECT to_regclass(%s)::oid", (f"{SCHEMA}.{name}",)).fetchone()[0]
        if oid is not None:
            objects[oid] = (f"{SCHEMA}.{name}", allowed)
    return objects


def environment_reasons(conn: psycopg.Connection) -> list[str]:
    """Authority any runtime role would gain through PUBLIC (empty list: acceptable)."""
    managed = managed_objects(conn)
    reasons = []
    for oid, qualified, privilege in conn.execute(
            "SELECT c.oid, quote_ident(n.nspname) || '.' || quote_ident(c.relname), a.privilege_type FROM pg_class c"
            " JOIN pg_namespace n ON n.oid = c.relnamespace, aclexplode(c.relacl) a"
            f" WHERE a.grantee = 0 AND {_SYSTEM_NAMESPACES} ORDER BY 2, 3"):
        if oid in managed and privilege in managed[oid][1]:
            continue
        reasons.append(f"PUBLIC has {privilege} on {qualified}")
    for oid, qualified, column, privilege in conn.execute(
            "SELECT c.oid, quote_ident(n.nspname) || '.' || quote_ident(c.relname), t.attname, a.privilege_type FROM pg_class c"
            " JOIN pg_namespace n ON n.oid = c.relnamespace"
            " JOIN pg_attribute t ON t.attrelid = c.oid, aclexplode(t.attacl) a"
            f" WHERE a.grantee = 0 AND {_SYSTEM_NAMESPACES} ORDER BY 2, 3, 4"):
        if oid in managed and privilege in managed[oid][1]:
            continue
        reasons.append(f"PUBLIC has column {privilege} on {qualified}.{column}")
    for (schema,) in conn.execute(
            "SELECT n.nspname FROM pg_namespace n, aclexplode(n.nspacl) a WHERE a.grantee = 0"
            f" AND a.privilege_type = 'CREATE' AND n.nspname <> %s AND {_SYSTEM_NAMESPACES}"
            " ORDER BY 1", (SCHEMA,)):
        reasons.append(f"PUBLIC can CREATE in schema {schema}")
    for (database,) in conn.execute(
            "SELECT d.datname FROM pg_database d, aclexplode(d.datacl) a WHERE a.grantee = 0"
            " AND a.privilege_type = 'CREATE' ORDER BY 1"):
        reasons.append(f"PUBLIC can CREATE in database {database}")
    return reasons


def verify_effective(conn: psycopg.Connection, role: str) -> list[str]:
    """Effective privileges (direct and via PUBLIC) must equal the map exactly."""
    problems = []
    for table, allowed in RUNTIME_PRIVILEGES.items():
        qualified = f"{SCHEMA}.{table}"
        if conn.execute("SELECT to_regclass(%s)", (qualified,)).fetchone()[0] is None:
            continue
        for kind in _TABLE_KINDS:
            has = conn.execute("SELECT has_table_privilege(%s, %s, %s)",
                               (role, qualified, kind)).fetchone()[0]
            if has != (kind in allowed):
                problems.append(f"{'has' if has else 'lacks'} {kind} on {qualified}")
        for kind in _COLUMN_KINDS:
            if kind not in allowed and conn.execute(
                    "SELECT has_any_column_privilege(%s, %s, %s)",
                    (role, qualified, kind)).fetchone()[0]:
                problems.append(f"has column {kind} on {qualified}")
    for (schema,) in conn.execute(
            "SELECT n.nspname FROM pg_namespace n WHERE has_schema_privilege(%s, n.oid,"
            f" 'CREATE') AND {_SYSTEM_NAMESPACES} ORDER BY 1", (role,)):
        problems.append(f"can CREATE in schema {schema}")
    return problems


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
    managed = managed_objects(conn)  # exact identity: public.<name> by OID
    for rel_oid, qualified, privilege, grantable in conn.execute(
            "SELECT c.oid, quote_ident(n.nspname) || '.' || quote_ident(c.relname), a.privilege_type, a.is_grantable FROM pg_class c"
            " JOIN pg_namespace n ON n.oid = c.relnamespace, aclexplode(c.relacl) a"
            " WHERE a.grantee = %s ORDER BY 2, 3",
            (oid,)):
        if grantable:
            reasons.append(f"has a grant option on {qualified}")
        elif rel_oid not in managed:
            reasons.append(f"has {privilege} on unmanaged relation {qualified}")
    for rel_oid, qualified, column, grantable in conn.execute(
            "SELECT c.oid, quote_ident(n.nspname) || '.' || quote_ident(c.relname), t.attname, a.is_grantable FROM pg_attribute t"
            " JOIN pg_class c ON c.oid = t.attrelid JOIN pg_namespace n ON n.oid = c.relnamespace,"
            " aclexplode(t.attacl) a WHERE a.grantee = %s ORDER BY 2, 3", (oid,)):
        if grantable:
            reasons.append(f"has a grant option on {qualified}.{column}")
        elif rel_oid not in managed:
            reasons.append(f"has column privileges on unmanaged relation {qualified}")
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
        # Everything is verified before any change (no password, role, grant or PUBLIC edit).
        reasons = environment_reasons(conn) + (unsafe_reasons(conn, role) if exists else [])
        if reasons:
            raise UnsafeRoleError(f"refusing runtime role {role}: " + "; ".join(reasons))
        database = conn.execute("SELECT current_database()").fetchone()[0]
        with conn.transaction():  # role, password and grants commit together or not at all
            if not exists:
                conn.execute(sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE"
                                     " NOREPLICATION NOBYPASSRLS NOINHERIT").format(ident))
            if password is not None:
                conn.execute(sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                    ident, sql.Literal(password)))
            conn.execute(sql.SQL("REVOKE CREATE ON SCHEMA {} FROM PUBLIC").format(
                sql.Identifier(SCHEMA)))
            conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(database), ident))
            conn.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
                sql.Identifier(SCHEMA), ident))
            for kind in ("TABLES", "SEQUENCES"):
                conn.execute(sql.SQL("REVOKE ALL ON ALL " + kind + " IN SCHEMA {} FROM {}").format(
                    sql.Identifier(SCHEMA), ident))
            for table, privileges in RUNTIME_PRIVILEGES.items():
                if table in tables:
                    conn.execute(sql.SQL("GRANT {} ON {} TO {}").format(
                        sql.SQL(", ").join(sql.SQL(p) for p in privileges),
                        sql.Identifier(SCHEMA, table), ident))
            for sequence in SEQUENCES:
                conn.execute(sql.SQL("GRANT USAGE ON SEQUENCE {} TO {}").format(
                    sql.Identifier(SCHEMA, sequence), ident))
            problems = verify_effective(conn, role)
            if problems:  # raising inside the block rolls everything back
                raise UnsafeRoleError(f"post-grant verification failed for {role}: "
                                      + "; ".join(problems))
