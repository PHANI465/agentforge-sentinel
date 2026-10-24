"""Least-privilege runtime role (C05).

The migration/operator identity owns the schema (tables, triggers, functions) and issues
sessions. The runtime role used by the API gets only the table privileges the service needs:
- no ownership, so it cannot ALTER/DROP tables or drop/disable the audit triggers;
- audit_events: SELECT and INSERT only (UPDATE/DELETE/TRUNCATE are not granted, and the
  append-only triggers still apply to everyone below a superuser/owner);
- api_sessions and schema_migrations: SELECT only (no session issuing, no migrations);
- no DELETE or TRUNCATE anywhere; no CREATE in the public schema.

Every table must appear in RUNTIME_PRIVILEGES; a new migration has to decide its grants
explicitly (tested). This limits what a compromised runtime credential can do; it does not
make storage tamper-proof against the owner or a superuser.
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
        if not exists:
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
