"""C08 review R26: the documented rollback actually runs. Real processes, two code versions:
`prev` is this tree; `next` is the same tree plus an upgrade migration. Sequence:

    prev up -> smoke -> backup; prev down; next up (applies 0005); restore refused under the
    live API; next down; next restore into a NEW database (API stopped, not migrated);
    prev up --database <restored> (none pending) -> same session, case, action and audit;
    prev down.
"""
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

import psycopg
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import local_stack  # noqa: E402
from sentinel import devdb  # noqa: E402

pytestmark = pytest.mark.skipif(devdb.find_pg_bin() is None, reason="needs PostgreSQL binaries")
UPGRADE = "0005_drill_upgrade.sql"


def copy_tree(target: Path) -> Path:
    listed = subprocess.run(["git", "ls-files", "-z", "--cached", "--others",
                             "--exclude-standard"], cwd=ROOT, capture_output=True,
                            check=True).stdout.decode()
    for name in filter(None, listed.split("\0")):
        if (ROOT / name).is_file() and not name.startswith(("web/", "docs/")):
            (target / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target / name)
    return target


def tables(url):
    with psycopg.connect(url) as conn:
        names = [r[0] for r in conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
            " AND table_type = 'BASE TABLE' ORDER BY 1")]
        return {t: conn.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0] for t in names}


def history(url, case_id):
    with psycopg.connect(url) as conn:
        return {
            "case": conn.execute("SELECT state, revision FROM cases WHERE id = %s",
                                 (case_id,)).fetchone(),
            "actions": conn.execute(
                "SELECT sa.id::text, sa.body->>'state' FROM simulated_actions sa JOIN approvals"
                " ap ON ap.id = sa.approval_id JOIN action_intents i ON i.id = ap.intent_id"
                " WHERE i.case_id = %s ORDER BY 1", (case_id,)).fetchall(),
            "audit": conn.execute("SELECT id::text, body->>'event_type' FROM audit_events"
                                  " WHERE case_id = %s ORDER BY id", (case_id,)).fetchall(),
            "sessions": conn.execute("SELECT token_sha256, expires_at FROM api_sessions"
                                     " ORDER BY 1").fetchall()}


def get(port, path, token):
    request = urllib.request.Request(f"http://127.0.0.1:{port}{path}",
                                     headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def test_down_restore_previous_code_rollback(tmp_path):
    prev, nxt = copy_tree(tmp_path / "prev"), copy_tree(tmp_path / "next")
    (nxt / "src/sentinel/db/migrations" / UPGRADE).write_text(
        "CREATE TABLE drill_upgrade (id integer PRIMARY KEY);\n", encoding="utf-8")
    roles = nxt / "src/sentinel/db/roles.py"  # a real upgrade decides its runtime grants
    text = roles.read_text(encoding="utf-8")
    anchor = '    "fraud_disclosures": ("SELECT",),\n'
    assert text.count(anchor) == 1
    roles.write_text(text.replace(anchor, anchor + '    "drill_upgrade": ("SELECT",),\n'),
                     encoding="utf-8")
    state, api_port, db_port = tmp_path / "state", devdb.free_port(), devdb.free_port()
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH",
                                                              "SENTINEL_TEST_DATABASE_URL")}
    env["SENTINEL_LIVE_CLAUDE"] = "0"

    def run(tree, *args, ok=True):
        done = subprocess.run([sys.executable, str(tree / "scripts" / "local_stack.py"),
                               "--state-dir", str(state), "--port", str(api_port),
                               "--db-port", str(db_port), *args], cwd=tree, env=env,
                              capture_output=True, text=True, timeout=300)
        assert (done.returncode == 0) == ok, (args, done.stdout[-1500:], done.stderr[-1500:])
        return done.stdout + done.stderr

    stack = local_stack.Stack(state)
    try:
        first = run(prev, "up")
        assert "migrations applied: 0001_thin_path.sql" in first and "API up" in first
        smoked = run(prev, "smoke")
        case_id = smoked.rsplit("CASE_ID=", 1)[1].split()[0]
        assert "case state=closed revision=4" in smoked
        url = local_stack.cluster(stack, db_port).url
        before_tables, before = tables(url("sentinel")), history(url("sentinel"), case_id)
        dump = tmp_path / "pre-upgrade.dump"
        assert "backup of sentinel written" in run(prev, "backup", "--out", str(dump))

        run(prev, "down")
        upgraded = run(nxt, "up")
        assert UPGRADE in upgraded  # the new code migrated the live database forward
        assert "stop the API first" in run(nxt, "restore", str(dump), "--database",
                                           "sentinel_rollback", ok=False)
        run(nxt, "down")
        assert local_stack.port_state(api_port, None) == "free"
        assert local_stack.database_state(stack, stack.load()) == "stopped"

        restored = run(nxt, "restore", str(dump), "--database", "sentinel_rollback")
        assert "0004_scoring_profiles.sql" in restored and UPGRADE not in restored
        assert "no API started" in restored
        assert local_stack.port_state(api_port, None) == "free"  # restore started no API
        rollback = url("sentinel_rollback")
        assert "drill_upgrade" not in tables(rollback)  # not migrated by restore
        assert "drill_upgrade" in tables(url("sentinel"))  # the live database untouched

        rolled = run(prev, "up", "--database", "sentinel_rollback")
        assert "migrations applied: none pending" in rolled and "API up" in rolled
        assert tables(rollback) == before_tables
        assert history(rollback, case_id) == before
        token = json.loads((state / "session.json").read_text())["token"]
        view = get(api_port, f"/v1/cases/{case_id}", token)  # the original session works
        assert (view["case"]["state"], view["case"]["revision"]) == ("closed", 4)
        audit = get(api_port, f"/v1/cases/{case_id}/audit", token)
        assert sorted(e["id"] for e in audit) == [row[0] for row in before["audit"]]  # by id
        assert len(audit) == 6
        assert get(api_port, "/v1/scoring", token)["mode"] == "rule"
        log = (state / "api.log").read_text(encoding="utf-8", errors="replace")
        assert token not in log and "postgresql://" not in log
        for line in (first, smoked, upgraded, restored, rolled):
            assert token not in line and "postgresql://" not in line
    finally:
        stopped = subprocess.run([sys.executable, str(prev / "scripts" / "local_stack.py"),
                                  "--state-dir", str(state), "down"], cwd=prev, env=env,
                                 capture_output=True, text=True, timeout=120)
    assert stopped.returncode == 0, stopped.stderr[-1000:]
    assert local_stack.port_state(api_port, None) == "free"
    assert local_stack.port_state(db_port, None) == "free"
