"""Hosted guards against a disposable PostgreSQL database and the restricted role."""

from concurrent.futures import ThreadPoolExecutor
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
import pytest

HOSTING = Path(__file__).resolve().parents[1] / "hosting/vercel"
spec = spec_from_file_location("hosted_guard", HOSTING / "guard.py")
guard = module_from_spec(spec)
spec.loader.exec_module(guard)


@pytest.fixture
def hosted(database_url):
    # The SQL grants the fixed production role. A local, uniquely named role keeps the
    # test independent of other test databases or role names in this cluster.
    role = "demo_test_" + uuid4().hex[:12]
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE ROLE {} LOGIN").format(sql.Identifier(role)))
        try:
            for name in ("guest.sql", "request-limits.sql", "request-limits.sql"):
                conn.execute((HOSTING / name).read_text().replace("sentinel_hosted", role))
            yield make_conninfo(database_url, user=role), conn
        finally:
            conn.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(role)))
            conn.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


def test_shared_database_admission_and_permissions(hosted):
    url, owner = hosted
    with ThreadPoolExecutor(6) as callers:
        decisions = list(callers.map(lambda _: guard.reserve(url, "guest", "a" * 64, None), range(6)))
    assert decisions.count(True) == 3
    assert guard.reserve(url, "guest", "b" * 64, None)
    with psycopg.connect(url) as runtime, pytest.raises(psycopg.errors.InsufficientPrivilege):
        runtime.execute("SELECT * FROM sentinel_demo.request_limits")
    owner.execute(
        "UPDATE sentinel_demo.request_limits SET expires_at = now() - interval '1 second'"
        " WHERE subject = %s", ("a" * 64,)
    )
    assert guard.reserve(url, "guest", "a" * 64, None)
    assert owner.execute(
        "SELECT count(*) FROM sentinel_demo.request_limits WHERE expires_at <= now()"
    ).fetchone()[0] == 0


def test_session_limit_across_addresses_and_invalid_tokens_do_not_create_buckets(hosted):
    url, owner = hosted
    token = "a" * 43
    with psycopg.connect(url) as runtime:
        assert runtime.execute(
            "SELECT sentinel_demo.issue_session(%s,%s,%s,%s)",
            (guard.token_digest(token), uuid4(), uuid4(), uuid4())
        ).fetchone()[0]
    owner.execute("SET TIME ZONE 'UTC'")
    owner.execute(
        "INSERT INTO sentinel_demo.request_limits (bucket, subject, expires_at, hits)"
        " SELECT 'api', session_id::text, date_trunc('minute', now()) + interval '1 minute', 90"
        " FROM public.api_sessions"
    )
    assert not guard.reserve(url, "api", "e" * 64, guard.token_digest(token))
    assert guard.reserve(url, "api", "e" * 64, guard.token_digest("b" * 43))
    assert owner.execute(
        "SELECT count(*) FROM sentinel_demo.request_limits WHERE bucket = 'api'"
    ).fetchone()[0] == 3


def test_http_headers_trusted_address_and_fail_closed(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    calls = []

    def fake_reserve(_url, group, visitor, digest):
        calls.append((group, visitor, digest))
        if group == "iaf":
            raise psycopg.OperationalError("private connection details")
        return len(calls) < 2

    monkeypatch.setattr(guard, "reserve", fake_reserve)
    app = FastAPI()
    app.add_middleware(guard.HostedGuard, database_url="local-test-key")

    @app.get("/v1/session")
    def session():
        return {"test": True}

    with TestClient(app) as client:
        assert client.post("/demo/session/").status_code == 403
        assert client.get("/v1/session", headers={"x-forwarded-for": "203.0.113.1"}).status_code == 503
        base = {"x-vercel-forwarded-for": "2001:db8::1"}
        success = client.get("/v1/session", headers=base)
        assert success.status_code == 200
        assert success.headers["cache-control"] == "private, no-store"
        assert success.headers["x-frame-options"] == "DENY"
        refused = client.get("/v1/session", headers={"x-vercel-forwarded-for": "2001:db8::2"})
        assert refused.status_code == 429 and refused.headers["retry-after"] == "60"
        assert calls[0][1] == calls[1][1]
        failure = client.post("/iaf/ask", headers={**base, "sec-fetch-site": "same-origin"})
        assert failure.status_code == 503 and failure.json() == {"kind": "bad_request"}
