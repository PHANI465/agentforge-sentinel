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


def text_field(value: object, key: str) -> str | None:
    if not isinstance(value, dict):
        return None
    item = value.get(key)
    return item if isinstance(item, str) else None


def presence(conn, external_id: str) -> dict:
    counts = {}
    counts["transactions"] = conn.execute(
        "SELECT count(*) AS n FROM transactions WHERE external_id = %s",
        (external_id,),
    ).fetchone()["n"]
    counts["scoring_outcomes"] = conn.execute(
        "SELECT count(*) AS n FROM scoring_outcomes s"
        " JOIN transactions t ON t.id = s.transaction_id WHERE t.external_id = %s",
        (external_id,),
    ).fetchone()["n"]
    counts["alerts"] = conn.execute(
        "SELECT count(*) AS n FROM alerts a"
        " JOIN transactions t ON t.id = a.transaction_id WHERE t.external_id = %s",
        (external_id,),
    ).fetchone()["n"]
    counts["cases"] = conn.execute(
        "SELECT count(*) AS n FROM cases c"
        " JOIN alerts a ON a.id = c.alert_id"
        " JOIN transactions t ON t.id = a.transaction_id WHERE t.external_id = %s",
        (external_id,),
    ).fetchone()["n"]
    return {"external_id": external_id, **counts}


def stored_scoring(conn, case_id: uuid.UUID | None, external_id: str | None) -> dict:
    if external_id:
        rows = conn.execute(
            "SELECT t.external_id, t.body AS transaction, s.body AS scoring, c.id::text AS case_id"
            " FROM transactions t"
            " LEFT JOIN scoring_outcomes s ON s.transaction_id = t.id"
            " LEFT JOIN alerts a ON a.transaction_id = t.id"
            " LEFT JOIN cases c ON c.alert_id = a.id"
            " WHERE t.external_id = %s",
            (external_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT t.external_id, t.body AS transaction, s.body AS scoring, c.id::text AS case_id"
            " FROM cases c"
            " JOIN alerts a ON a.id = c.alert_id"
            " JOIN transactions t ON t.id = a.transaction_id"
            " LEFT JOIN scoring_outcomes s ON s.transaction_id = t.id"
            " WHERE c.id = %s",
            (case_id,),
        ).fetchall()
    if len(rows) != 1 or not isinstance(rows[0]["scoring"], dict):
        fail("not_found")
    row = rows[0]
    scoring = row["scoring"]
    inputs = scoring.get("inputs") if isinstance(scoring.get("inputs"), dict) else None
    model = scoring.get("model") if isinstance(scoring.get("model"), dict) else None
    values = inputs.get("values") if inputs and isinstance(inputs.get("values"), dict) else None
    return {
        "external_id": row["external_id"],
        "case_id": row["case_id"],
        "scoring_kind": scoring.get("scoring_kind"),
        "score_semantics": scoring.get("score_semantics"),
        "score": scoring.get("score"),
        "threshold": scoring.get("threshold"),
        "alerted": scoring.get("alerted"),
        "scorer_name": text_field(scoring.get("scorer"), "name"),
        "scorer_version": text_field(scoring.get("scorer"), "version"),
        "scorer_sha256": text_field(scoring.get("scorer"), "sha256"),
        "features_sha256": text_field(scoring.get("features"), "sha256"),
        "threshold_policy_sha256": text_field(scoring.get("threshold_policy"), "sha256"),
        "model_candidate": text_field(model, "candidate"),
        "model_artifact_sha256": text_field(model, "artifact_sha256"),
        "model_results_id": text_field(model, "results_id"),
        "input_currency": inputs.get("currency") if inputs else None,
        "profile_home_currency": inputs.get("profile_home_currency") if inputs else None,
        "profile_opened_at": inputs.get("profile_opened_at") if inputs else None,
        "history_rows": inputs.get("history_rows") if inputs else None,
        "disclosures_used": inputs.get("disclosures_used") if inputs else None,
        "feature_values": values,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--case-id")
    selector.add_argument("--external-id")
    reading = parser.add_mutually_exclusive_group()
    reading.add_argument("--presence", action="store_true")
    reading.add_argument("--scoring", action="store_true")
    args = parser.parse_args()
    if args.presence and not args.external_id:
        fail("refused")
    url = load_url(args.manifest)
    if args.presence or args.scoring:
        try:
            with connect(url) as conn:
                conn.read_only = True  # before the first query; rejects accidental writes
                if args.presence:
                    found = presence(conn, args.external_id)
                else:
                    case_id = uuid.UUID(args.case_id) if args.case_id else None
                    found = stored_scoring(conn, case_id, args.external_id)
        except SystemExit:
            raise
        except Exception:
            fail("query_failed")
        print(json.dumps(found, sort_keys=True))
        return
    try:
        with connect(url) as conn:
            conn.read_only = True  # same protection for case-detail inspection
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
