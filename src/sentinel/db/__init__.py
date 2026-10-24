"""Postgres migrations and connections. Services own scoping; this module owns schema."""
from __future__ import annotations

from pathlib import Path

import psycopg
from psycopg.rows import dict_row

MIGRATIONS = Path(__file__).with_name("migrations")


CONNECT_TIMEOUT_SECONDS = 10


def connect(url: str) -> psycopg.Connection:
    """Bounded connection attempts: an unreachable database fails in seconds, not minutes,
    unless the URL sets its own connect_timeout."""
    extra = {} if "connect_timeout" in url else {"connect_timeout": CONNECT_TIMEOUT_SECONDS}
    return psycopg.connect(url, row_factory=dict_row, **extra)


def migrate(url: str) -> list[str]:
    """Apply pending numbered SQL files once each, in order. Returns names applied now."""
    applied_now = []
    with connect(url) as conn:
        with conn.transaction():
            # Serialize concurrent migrators on one well-known advisory lock.
            conn.execute("SELECT pg_advisory_xact_lock(4224001)")
            conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations ("
                         "name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())")
            done = {row["name"] for row in conn.execute("SELECT name FROM schema_migrations")}
            for path in sorted(MIGRATIONS.glob("[0-9][0-9][0-9][0-9]_*.sql")):
                if path.name in done:
                    continue
                conn.execute(path.read_text(encoding="utf-8"))
                conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,))
                applied_now.append(path.name)
    return applied_now
