import itertools
import os
import uuid
from datetime import datetime, timedelta, timezone

import psycopg
from psycopg import sql
import pytest
from psycopg.conninfo import make_conninfo

from sentinel import db, devdb

NOW = datetime(2026, 10, 23, 17, 0, tzinfo=timezone.utc)
_names = itertools.count()


class FakeClock:
    def __init__(self, now=NOW):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, **delta):
        self.now += timedelta(**delta)


@pytest.fixture(scope="session")
def pg_cluster(tmp_path_factory):
    """SENTINEL_TEST_DATABASE_URL (an admin URL) or a disposable cluster from initdb."""
    url = os.environ.get("SENTINEL_TEST_DATABASE_URL")
    if url:
        yield url, None
        return
    bin_dir = devdb.find_pg_bin()
    if bin_dir is None:
        pytest.skip("Postgres not available: set SENTINEL_PG_BIN or SENTINEL_TEST_DATABASE_URL")
    cluster = devdb.Cluster(bin_dir, tmp_path_factory.mktemp("pg") / "data", devdb.free_port())
    cluster.init()
    cluster.start()
    try:  # everything after start, including template setup, is covered by the stop below
        db.migrate(cluster.create_database("sentinel_template"))
        yield cluster.url(), cluster
    finally:
        cluster.stop()


@pytest.fixture
def database_url(pg_cluster):
    admin_url, cluster = pg_cluster
    name = f"sentinel_test_{os.getpid()}_{next(_names)}"
    # Rebuild the DSN properly so query/TLS parameters on an external admin URL survive.
    url = make_conninfo(admin_url, dbname=name)
    with psycopg.connect(admin_url, autocommit=True) as conn:
        template = "" if cluster is None else " TEMPLATE sentinel_template"
        conn.execute(f'CREATE DATABASE "{name}"{template}')
    try:
        if cluster is None:
            db.migrate(url)
        yield url
    finally:
        with psycopg.connect(admin_url, autocommit=True) as conn:
            conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


@pytest.fixture
def clock():
    return FakeClock()


R18_OLD_PASSWORD = "SYNTHETIC-OLD-PASSWORD-r18"


@pytest.fixture
def make_role(database_url):
    created = []

    def make(attributes="LOGIN NOINHERIT", password=R18_OLD_PASSWORD):
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
