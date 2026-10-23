"""C08: the documented backup/restore procedure (pg_dump -Fc / pg_restore) round-trips a
populated database, keeps the audit protection and leaves no pending migrations."""
import subprocess
import uuid

import psycopg
import pytest

from sentinel import db
from test_thin_path import ANALYST, Harness, alerting_case, approve_pending

TABLES = ("transactions", "scoring_outcomes", "alerts", "cases", "evidence_items",
          "agent_runs", "action_intents", "approvals", "simulated_actions", "audit_events",
          "api_sessions", "schema_migrations")


def counts(url):
    with psycopg.connect(url) as conn:
        return {t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in TABLES}


def test_backup_restore_round_trip(pg_cluster, database_url, clock, tmp_path):
    _, cluster = pg_cluster
    if cluster is None:
        pytest.skip("needs local Postgres client binaries (disposable cluster mode)")
    h = Harness(database_url, clock)
    token = h.service.create_session(ANALYST)[0]
    case = alerting_case(h, token, clock)
    h.call("POST", f"/v1/cases/{case['id']}/investigations", token, {"expected_revision": 1})
    approval = approve_pending(h, token, case["id"])
    h.call("POST", "/v1/actions", token, {"approval_id": approval["id"],
                                          "idempotency_key": str(uuid.uuid4())})

    dump = tmp_path / "sentinel.dump"
    subprocess.run([str(cluster.bin_dir / "pg_dump"), "--format=custom", "--no-owner",
                    f"--file={dump}", database_url], check=True, capture_output=True)
    restored = cluster.create_database(f"restored_{uuid.uuid4().hex[:8]}")
    subprocess.run([str(cluster.bin_dir / "pg_restore"), "--no-owner", "--exit-on-error",
                    f"--dbname={restored}", str(dump)], check=True, capture_output=True)

    assert counts(restored) == counts(database_url)
    assert db.migrate(restored) == []
    with psycopg.connect(restored) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("DELETE FROM audit_events")
    # The restored database serves the same case to the same session token.
    view = Harness(restored, clock).call("GET", f"/v1/cases/{case['id']}", token).json()
    assert (view["case"]["state"], view["case"]["revision"]) == ("closed", 4)
