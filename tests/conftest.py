import itertools
import os
from datetime import datetime, timedelta, timezone

import psycopg
import pytest

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
    template = cluster.create_database("sentinel_template")
    db.migrate(template)
    try:
        yield cluster.url(), cluster
    finally:
        cluster.stop()


@pytest.fixture
def database_url(pg_cluster):
    admin_url, cluster = pg_cluster
    name = f"sentinel_test_{os.getpid()}_{next(_names)}"
    with psycopg.connect(admin_url, autocommit=True) as conn:
        if cluster is None:
            conn.execute(f'CREATE DATABASE "{name}"')
        else:
            conn.execute(f'CREATE DATABASE "{name}" TEMPLATE sentinel_template')
    url = admin_url.rsplit("/", 1)[0] + "/" + name
    if cluster is None:
        db.migrate(url)
    yield url
    with psycopg.connect(admin_url, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


@pytest.fixture
def clock():
    return FakeClock()
