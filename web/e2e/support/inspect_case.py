"""Read one case from the disposable browser-stack database.

Prints codes, counts, and identifiers only. Tokens and the database URL stay in this
process and are never written to stdout or stderr.
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from sentinel.db import connect  # noqa: E402


def fail(code: str) -> None:
    print(json.dumps({"error": code}))
    raise SystemExit(1)


def load_url(manifest_path: Path) -> str:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        url = manifest["database_url"]
        port = int(manifest["database"]["port"])
    except (OSError, ValueError, KeyError, TypeError):
        fail("manifest_unreadable")
    directory = manifest_path.parent
    if not directory.name.startswith("sentinel-browser-"):
        fail("refused")
    parsed = urlparse(url)
    if parsed.scheme not in {"postgresql", "postgres"} or parsed.hostname != "127.0.0.1":
        fail("refused")
    if parsed.port != port:
        fail("refused")
    return url


def proposals(conn, case_id: uuid.UUID) -> list[dict]:
    rows = conn.execute(
        "SELECT case_revision, body FROM action_intents WHERE case_id = %s ORDER BY case_revision",
        (case_id,),
    ).fetchall()
    found = []
    for row in rows:
        params = (row["body"] or {}).get("parameters") or {}
        amount = params.get("amount") or {}
        found.append({
            "revision": row["case_revision"],
            "operation": params.get("operation"),
            "reason_code": params.get("reason_code"),
            "transaction_id": params.get("transaction_id"),
            "amount_minor": amount.get("minor_units"),
        })
    return found


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--case-id")
    selector.add_argument("--external-id")
    args = parser.parse_args()
    url = load_url(args.manifest)
    try:
        with connect(url) as conn:
            if args.external_id:
                rows = conn.execute(
                    "SELECT c.id FROM cases c"
                    " JOIN alerts a ON a.id = c.alert_id"
                    " JOIN transactions t ON t.id = a.transaction_id"
                    " WHERE t.external_id = %s",
                    (args.external_id,),
                ).fetchall()
                if len(rows) != 1:
                    fail("not_found")
                case_id = rows[0]["id"]
            else:
                case_id = uuid.UUID(args.case_id)
            case = conn.execute(
                "SELECT id::text AS id, state, revision FROM cases WHERE id = %s",
                (case_id,),
            ).fetchone()
            if case is None:
                fail("not_found")
            transaction = conn.execute(
                "SELECT t.id::text AS id, t.external_id FROM cases c"
                " JOIN alerts a ON a.id = c.alert_id"
                " JOIN transactions t ON t.id = a.transaction_id WHERE c.id = %s",
                (case_id,),
            ).fetchone()
            actions = conn.execute(
                "SELECT sa.id::text AS id FROM simulated_actions sa"
                " JOIN approvals ap ON ap.id = sa.approval_id"
                " JOIN action_intents i ON i.id = ap.intent_id"
                " WHERE i.case_id = %s ORDER BY sa.id",
                (case_id,),
            ).fetchall()
            approvals = conn.execute(
                "SELECT count(*) AS n,"
                " count(*) FILTER (WHERE ap.consumed_at IS NOT NULL) AS consumed"
                " FROM approvals ap JOIN action_intents i ON i.id = ap.intent_id"
                " WHERE i.case_id = %s",
                (case_id,),
            ).fetchone()
            runs = conn.execute(
                "SELECT status, body->>'failure_code' AS failure_code"
                " FROM agent_runs WHERE case_id = %s",
                (case_id,),
            ).fetchall()
            audits = conn.execute(
                "SELECT body->>'event_type' AS event_type, count(*) AS n"
                " FROM audit_events WHERE case_id = %s GROUP BY 1 ORDER BY 1",
                (case_id,),
            ).fetchall()
            intent_count = conn.execute(
                "SELECT count(*) AS n FROM action_intents WHERE case_id = %s",
                (case_id,),
            ).fetchone()["n"]
            proposal_rows = proposals(conn, case_id)
    except SystemExit:
        raise
    except Exception:
        fail("query_failed")
    audit_counts = {row["event_type"]: row["n"] for row in audits}
    print(json.dumps({
        "case_id": case["id"],
        "case_state": case["state"],
        "case_revision": case["revision"],
        "transaction_id": transaction["id"] if transaction else None,
        "external_id": transaction["external_id"] if transaction else None,
        "action_count": len(actions),
        "action_ids": [row["id"] for row in actions],
        "intent_count": intent_count,
        "approval_count": approvals["n"],
        "consumed_approval_count": approvals["consumed"],
        "failed_run_count": sum(1 for row in runs if row["status"] == "failed"),
        "run_count": len(runs),
        "failure_codes": [row["failure_code"] for row in runs if row["failure_code"]],
        "audit_total": sum(audit_counts.values()),
        "audit_counts": audit_counts,
        "proposals": proposal_rows,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
