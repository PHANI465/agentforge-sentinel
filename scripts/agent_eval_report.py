"""Scoped read-only export and partially blinded review packets (G3D-P4a).

    uv run --locked python scripts/agent_eval_report.py export --root DIR --pair P00-det
    uv run --locked python scripts/agent_eval_report.py packets --root DIR [--seed N]

`export` reads one pair's stored history as the RUNTIME role (never the operator), in one
REPEATABLE READ, READ ONLY transaction, selecting only the tenant/session/case/workflow
relationships its run artifact names and re-validating every returned row's scope. A
foreign, missing or tampered mapping is refused, never broadened. It writes a private
machine bundle (`sentinel.agent-eval.bundle/1`) with a before/after proof that nothing was
mutated. `packets` builds human review packets from the bundles: seeded random order, opaque
packet IDs, no comparator/config/role names, pins, case IDs or expected answers, and a
separate unblinding key. Blinding is partial: output shape can reveal the system. Text is
data (JSON, and CSV with formula-like cells escaped); nothing is rendered as HTML.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

from agent_eval_support import artifact  # noqa: E402

MUTABLE = ("cases", "agent_workflows", "agent_runs", "agent_steps", "action_intents",
           "approvals", "simulated_actions", "audit_events")
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
SHEET_COLUMNS = artifact.SHEET_COLUMNS
# Recommendation and claim fields an exported adoption must share with storage (R49).
DISPOSITION_FIELDS = ("source", "kind", "operation", "reason_code", "basis_run_id",
                      "workflow_id", "supported_claims", "unsupported_claims")
VERIFIED = "matches stored disposition"
STORED_ONLY = "stored only (run artifact telemetry unavailable; artifact recommendation unknown)"


class ExportError(RuntimeError):
    """A refused export: scope, mapping or artifact problem. Never broadened or skipped."""


def _scope_clause() -> tuple[str, tuple]:
    """The scope predicate every export query appends (tests break it on purpose)."""
    return " AND tenant_id = %s AND session_id = %s", ()


def _rows(conn, sql_text: str, key, scope: dict) -> list[dict]:
    clause, _ = _scope_clause()
    params = (key, scope["tenant_id"], scope["session_id"]) if clause else (key,)
    rows = conn.execute(sql_text + clause, params).fetchall()
    for row in rows:  # every returned row must be this attempt's scope, whatever the query
        if (str(row["tenant_id"]), str(row["session_id"])) != (scope["tenant_id"],
                                                               scope["session_id"]):
            raise ExportError("a returned row is outside the attempt's tenant/session "
                              "(refused; nothing exported)")
    return rows


def snapshot(runtime_url: str) -> dict:
    """Row count and content digest of each mutable table, read-only, as the runtime role."""
    import psycopg
    from psycopg import sql
    with psycopg.connect(runtime_url) as conn, conn.transaction():
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        return {table: list(conn.execute(sql.SQL(
            "SELECT count(*), md5(coalesce(string_agg(t::text, '|' ORDER BY t::text), ''))"
            " FROM {} t").format(sql.Identifier(table))).fetchone()) for table in MUTABLE}


def stored_disposition(workflows: list[dict], runs: list[dict]) -> dict | None:
    """The adopted disposition as storage records it, by the runner's own rule: a workflow
    names its basis run (never the last role or attempt 1); without a workflow, the single
    investigator's one run with a finding. None when nothing was adopted."""
    adopted = None
    for workflow in sorted(workflows, key=lambda w: (w["started_at"], str(w["id"]))):
        disposition = workflow["body"].get("disposition") or {}
        if disposition.get("kind") in ("recommend", "abstain"):
            adopted = {"source": "workflow_disposition", "kind": disposition["kind"],
                       "operation": disposition.get("operation"),
                       "reason_code": disposition.get("reason_code"),
                       "basis_run_id": disposition.get("basis_run_id"),
                       "workflow_id": str(workflow["id"]),
                       "supported_claims": disposition.get("supported_claims"),
                       "unsupported_claims": disposition.get("unsupported_claims")}
    if adopted is None and not workflows:
        found = [r for r in runs if r["finding"]]
        if len(found) == 1:
            adopted = {"source": "single_investigator_finding", "kind": None,
                       "operation": found[0]["finding"].get("operation"),
                       "reason_code": found[0]["finding"].get("reason_code"),
                       "basis_run_id": str(found[0]["id"])}
    return adopted


def adopted_disposition(row: dict, workflows: list[dict], runs: list[dict]) -> dict | None:
    """The exported adoption, built from storage and checked against the run artifact (R49).

    Every recommendation and claim field the artifact records must equal the stored
    adopted disposition; a disagreement is refused, never repaired. The recorded outcome is
    never changed: a disposition whose telemetry was unavailable is exported from storage
    and labelled so, and stored state found after a pending/error outcome is labelled as
    found later, not as the outcome."""
    attempt_id, outcome = row["attempt_id"], row.get("outcome")
    stored, claimed = stored_disposition(workflows, runs), row.get("disposition")
    if stored is not None:
        basis = [r for r in runs if str(r["id"]) == stored["basis_run_id"]]
        if len(basis) != 1 or not basis[0]["finding"] or (
                stored["source"] == "workflow_disposition"
                and str(basis[0]["workflow_id"]) != stored["workflow_id"]):
            raise ExportError(f"{attempt_id}: the stored adopted basis run is not a run with "
                              "a finding in the adopted workflow and scope (refused)")
    if claimed is not None:
        if stored is None:
            raise ExportError(f"{attempt_id}: the run artifact names a disposition but none "
                              "is stored as adopted in this scope (refused)")
        differs = [k for k in DISPOSITION_FIELDS if k in stored and claimed.get(k) != stored[k]]
        if differs:
            raise ExportError(f"{attempt_id}: the run artifact's {', '.join(differs)} "
                              "disagree with the stored adopted disposition (refused; "
                              "nothing exported)")
        verification = VERIFIED
    elif stored is None:
        if outcome == "disposition":
            raise ExportError(f"{attempt_id}: a disposition outcome with no stored adopted "
                              "disposition (refused)")
        return None
    elif outcome == "disposition" and (row.get("telemetry") or {}).get("status") == \
            "unavailable":
        verification = STORED_ONLY
    elif outcome in ("pending", "error"):
        verification = f"stored state found after a {outcome} outcome (not the recorded " \
                       "outcome)"
    else:
        raise ExportError(f"{attempt_id}: the stored adopted disposition contradicts the "
                          f"recorded {outcome} outcome (refused)")
    return {"agent_run_id": stored["basis_run_id"], "verification": verification,
            "finding": basis[0]["finding"],
            **{k: stored[k] for k in DISPOSITION_FIELDS if k in stored}}


def export_attempt(conn, row: dict) -> dict:
    scope = row["ids"]
    cases = _rows(conn, "SELECT id, tenant_id, session_id, alert_id, state, revision, body"
                        " FROM cases WHERE id = %s", scope["case_id"], scope)
    if len(cases) != 1:
        raise ExportError(f"{row['attempt_id']}: case not found in the attempt's scope "
                          "(foreign or tampered mapping; refused)")
    case = cases[0]
    alerts = _rows(conn, "SELECT id, tenant_id, session_id, transaction_id, body FROM alerts"
                         " WHERE id = %s", case["alert_id"], scope)
    txns = _rows(conn, "SELECT id, tenant_id, session_id, body FROM transactions WHERE id = %s",
                 alerts[0]["transaction_id"], scope) if alerts else []
    scoring = _rows(conn, "SELECT transaction_id, tenant_id, session_id, body FROM"
                          " scoring_outcomes WHERE transaction_id = %s",
                    alerts[0]["transaction_id"], scope) if alerts else []
    evidence = _rows(conn, "SELECT id, tenant_id, session_id, body FROM evidence_items"
                           " WHERE case_id = %s", scope["case_id"], scope)
    workflows = _rows(conn, "SELECT id, tenant_id, session_id, status, terminal_by, body,"
                            " started_at FROM agent_workflows WHERE case_id = %s",
                      scope["case_id"], scope)
    runs = _rows(conn, "SELECT id, tenant_id, session_id, workflow_id, attempt, status, body,"
                       " finding, seq FROM agent_runs WHERE case_id = %s", scope["case_id"],
                 scope)
    steps = _rows(conn, "SELECT tenant_id, session_id, workflow_id, step_seq, body, payload"
                        " FROM agent_steps WHERE case_id = %s", scope["case_id"], scope)
    workflow_ids = sorted(str(w["id"]) for w in workflows)
    if "workflow_ids" in row and sorted(row["workflow_ids"]) != workflow_ids:
        raise ExportError(f"{row['attempt_id']}: stored workflows do not match the run "
                          "artifact (tampered mapping; refused)")
    runs.sort(key=lambda r: r["seq"])
    steps.sort(key=lambda s: (str(s["workflow_id"]), s["step_seq"]))
    adopted = adopted_disposition(row, workflows, runs)
    txn = txns[0]["body"] if txns else {}
    return {
        "attempt_id": row["attempt_id"], "case": row["case"], "outcome": row["outcome"],
        "ids": scope, "case_state": case["state"], "case_revision": case["revision"],
        "pins": case["body"].get("pins"),
        "transaction": {k: txn.get(k) for k in ("direction", "occurred_at")} | {
            "amount": txn.get("amount")},
        "scoring": {k: (scoring[0]["body"] if scoring else {}).get(k)
                    for k in ("scoring_kind", "score", "threshold", "alerted")},
        "evidence": [{"name": fact.get("name"), "value": fact.get("value"),
                      "source": e["body"].get("source")}
                     for e in evidence for fact in e["body"].get("facts") or []],
        "workflows": [{"id": str(w["id"]), "status": w["status"],
                       "terminal_by": w["terminal_by"],
                       "disposition": w["body"].get("disposition")} for w in workflows],
        "runs": [{"id": str(r["id"]), "role": r["body"].get("role"), "status": r["status"],
                  "failure_code": r["body"].get("failure_code"), "attempt": r["attempt"],
                  "config": (r["body"].get("config") or {}).get("name"),
                  "has_finding": r["finding"] is not None} for r in runs],
        "role_outputs": [{"agent_run_id": s["body"].get("agent_run_id"),
                          "role": s["body"].get("role"), "output": s["payload"]}
                         for s in steps if s["body"].get("kind") == "role_completed"],
        "tool_results": [s["payload"] for s in steps
                         if s["body"].get("kind") in ("tool_executed", "tool_denied")],
        "claim_checks": [list(s["body"].get("checks") or []) for s in steps
                         if s["body"].get("kind") == "claims_checked"],
        "adopted": adopted}


def export_run(runtime_url: str, doc: dict) -> dict:
    """A private machine bundle for every recorded attempt of a run artifact."""
    import psycopg
    from psycopg.rows import dict_row
    artifact.validate_run(doc)
    check_identity(runtime_url)
    before = snapshot(runtime_url)
    exports = []
    with psycopg.connect(runtime_url, row_factory=dict_row) as conn, conn.transaction():
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        for name, result in doc["comparators"].items():
            for row in result["attempts"]:
                if "ids" not in row:
                    raise ExportError(f"{row['attempt_id']}: no recorded IDs (refused)")
                exports.append({"comparator": name, **export_attempt(conn, row)})
    after = snapshot(runtime_url)
    return {"version": artifact.BUNDLE_VERSION, "run_artifact_sha256": artifact.digest(doc),
            "run": doc, "exports": exports,
            "mutation_proof": {"identity": "runtime role",
                               "identity_check": "not a table owner, administrator or "
                                                 "switched role (checked before reading)",
                               "before": before, "after": after,
                               "unchanged": before == after}}


def check_identity(runtime_url: str) -> None:
    """Refuse an export login that owns (or is a member of the owner of) a mutable table,
    holds administration attributes or runs as another role: export is runtime-only."""
    import psycopg
    with psycopg.connect(runtime_url) as conn, conn.transaction():
        conn.execute("SET TRANSACTION READ ONLY")
        admin, switched = conn.execute(
            "SELECT rolsuper OR rolcreaterole OR rolcreatedb OR rolreplication OR rolbypassrls,"
            " session_user <> current_user FROM pg_roles WHERE rolname = session_user"
        ).fetchone()
        owns = conn.execute(
            "SELECT count(*) FROM pg_class c WHERE c.relkind IN ('r', 'p')"
            " AND c.relname = ANY(%s) AND pg_table_is_visible(c.oid)"
            " AND pg_has_role(session_user, c.relowner, 'MEMBER')", (list(MUTABLE),)
        ).fetchone()[0]
    if admin or switched or owns:
        raise ExportError("the export login is not the least-privilege runtime role (an "
                          "owner, administrator or switched role; refused, nothing read)")


# ---- partially blinded review packets --------------------------------------------------------

def statements(export: dict) -> list[str]:
    """Free text shown to the human: the adopted rationale, then role notes (no role names)."""
    texts = []
    finding = (export.get("adopted") or {}).get("finding") or {}
    if finding.get("rationale"):
        texts.append(finding["rationale"])
    for output in export["role_outputs"]:
        note = (output.get("output") or {}).get("note")
        if note:
            texts.append(note)
    return texts


def evidence_shown(export: dict) -> dict:
    shown = {"transaction": export["transaction"],
             "facts": {e["name"]: e["value"] for e in export["evidence"]}}
    values = {}
    for result in export["tool_results"]:
        if result.get("status") == "ok":
            values.update(result.get("values") or {})
    if values:
        shown["tool_values"] = values
    return shown


def check_bundle(bundle: dict) -> None:
    """A bundle's adopted records must agree with the run artifact it carries (R49).

    The export already checked them against storage; this re-check refuses a bundle file
    edited afterwards in one place but not the other. It is consistency checking of an
    unsigned file, not tamper-proofing."""
    run = bundle.get("run")
    if not isinstance(run, dict) or artifact.digest(run) != bundle.get("run_artifact_sha256"):
        raise ExportError("the bundle's run artifact digest does not match (refused)")
    artifact.validate_run(run)
    rows = {row["attempt_id"]: (name, row) for name, result in run["comparators"].items()
            for row in result["attempts"]}
    for export in bundle["exports"]:
        adopted = export.get("adopted")
        if not adopted or export.get("outcome") != "disposition":
            continue
        name, row = rows.get(export["attempt_id"], (None, None))
        if row is None or name != export["comparator"] or row["outcome"] != "disposition":
            raise ExportError(f"{export['attempt_id']}: the bundle export does not match its "
                              "run artifact (refused)")
        claimed = row.get("disposition")
        if claimed is None:
            if adopted.get("verification") != STORED_ONLY:
                raise ExportError(f"{export['attempt_id']}: the bundle's adopted record "
                                  "disagrees with its run artifact (refused)")
            continue
        differs = [k for k in DISPOSITION_FIELDS if k in adopted and k != "basis_run_id"
                   and adopted[k] != claimed.get(k)]
        if adopted.get("verification") != VERIFIED or differs or \
                adopted.get("agent_run_id") != claimed.get("basis_run_id"):
            raise ExportError(f"{export['attempt_id']}: the bundle's adopted record "
                              "disagrees with its run artifact (refused; no packet built)")


def review_packets(bundles: list[dict], seed: int) -> tuple[dict, dict]:
    """(blinded packets, separate unblinding key). Only dispositions are scored. The key
    binds each packet's generated sheet rows (item, kind, text digest) so a returned sheet
    can be checked against the material that was actually shown (R47)."""
    for bundle in bundles:  # every bundle is checked before any packet is built
        check_bundle(bundle)
    items = [(bundle, export) for bundle in bundles for export in bundle["exports"]
             if export["outcome"] == "disposition" and export.get("adopted")]
    rng = random.Random(seed)
    rng.shuffle(items)
    packets, key, used = [], {}, set()
    for bundle, export in items:
        packet_id = f"PK-{rng.getrandbits(40):010x}"
        while packet_id in used:
            packet_id = f"PK-{rng.getrandbits(40):010x}"
        used.add(packet_id)
        packet = {"packet_id": packet_id, "evidence": evidence_shown(export),
                  "recommendation": {k: export["adopted"][k]
                                     for k in ("operation", "reason_code")},
                  "statements": [{"item": f"S{i}", "text": text}
                                 for i, text in enumerate(statements(export), 1)]}
        packets.append(packet)
        key[packet_id] = {"attempt_id": export["attempt_id"], "comparator": export["comparator"],
                          "case": export["case"], "run_artifact_sha256":
                          bundle["run_artifact_sha256"], "items": sheet_binding(packet)}
    return ({"version": artifact.PACKETS_VERSION, "seed_recorded_in_key": True,
             "blinding": "partial: comparator, config, role names, pins, case IDs and expected "
                         "answers are removed; output shape may still reveal the system",
             "instructions": "For each statement: supported / unsupported / not_checkable "
                             "against the evidence shown. Then: is the recommendation "
                             "acceptable (yes/no + reason code), and would you correct it? "
                             "Leave a field blank only if you did not answer it: blank is "
                             "recorded as unanswered, never as no.",
             "packets": packets},
            {"version": artifact.PACKETS_VERSION, "seed": seed, "packets": key})


def cell(value):
    """CSV-safe: a formula-like text cell is prefixed with ' ; numbers stay typed."""
    if isinstance(value, str) and value.startswith(FORMULA_PREFIXES):
        return "'" + value
    return value


def packet_rows(packet: dict) -> list[list]:
    """The sheet rows generated for one packet, as written (formula-like text escaped)."""
    rows = [[cell(packet["packet_id"]), cell(f"E:{name}"), "evidence", cell(value),
             "", "", "", "", ""] for name, value in packet["evidence"]["facts"].items()]
    rows += [[cell(packet["packet_id"]), statement["item"], "statement",
              cell(statement["text"]), "", "", "", "", ""] for statement in packet["statements"]]
    rec = packet["recommendation"]
    rows.append([cell(packet["packet_id"]), "R", "recommendation",
                 cell(f"{rec['operation']} / {rec['reason_code']}"), "", "", "", "", ""])
    return rows


def sheet_binding(packet: dict) -> dict:
    """item -> {kind, text_sha256} of the rows exactly as a CSV reader reads them back."""
    out = io.StringIO()
    csv.writer(out, lineterminator="\n").writerows(packet_rows(packet))
    return {row[1]: {"kind": row[2], "text_sha256": artifact.text_digest(row[3])}
            for row in csv.reader(io.StringIO(out.getvalue()))}


def sheet_csv(packets: dict) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(SHEET_COLUMNS)
    for packet in packets["packets"]:
        writer.writerows(packet_rows(packet))
    return out.getvalue()


# ---- CLI over a pilot root ---------------------------------------------------------------------

def export_pair(root: Path, pair_id: str) -> Path:
    import agent_eval_pilot as pilot
    manifest = pilot.load(root)
    pair = next((p for p in manifest["pairs"] if p["pair_id"] == pair_id), None)
    if pair is None or not pair.get("run_file") or pair_id not in manifest["databases"]:
        raise ExportError(f"pair {pair_id} has no recorded run to export")
    doc = json.loads((Path(root) / pair["run_file"]).read_text(encoding="utf-8"))
    stack, data = pilot.start(root, manifest)
    try:
        _owner, runtime = pilot.urls(stack, data, manifest["databases"][pair_id])
        bundle = export_run(runtime, doc)
    finally:
        pilot.stop(stack, data)
    out = Path(root) / "exports" / f"{pair_id}.bundle.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out


def build_packets(root: Path, seed: int) -> dict:
    import agent_eval_pilot as pilot
    pilot.load(root)
    bundles = [json.loads(p.read_text(encoding="utf-8"))
               for p in sorted((Path(root) / "exports").glob("*.bundle.json"))]
    packets, key = review_packets(bundles, seed)
    review, keys = Path(root) / "review", Path(root) / "keys"
    review.mkdir(exist_ok=True)
    keys.mkdir(exist_ok=True)
    (review / "packets.json").write_text(json.dumps(packets, indent=2, ensure_ascii=False)
                                         + "\n", encoding="utf-8")
    (review / "sheet.csv").write_text(sheet_csv(packets), encoding="utf-8", newline="")
    (keys / "unblinding-key.json").write_text(json.dumps(key, indent=2) + "\n",
                                              encoding="utf-8")
    return {"packets": len(packets["packets"]), "review": str(review), "key": str(keys)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    export = sub.add_parser("export")
    export.add_argument("--root", type=Path, required=True)
    export.add_argument("--pair", required=True)
    packets = sub.add_parser("packets")
    packets.add_argument("--root", type=Path, required=True)
    packets.add_argument("--seed", type=int, default=20261106)
    args = parser.parse_args(argv)
    import agent_eval_pilot as pilot
    try:
        if args.command == "export":
            result = {"bundle": str(export_pair(args.root, args.pair))}
        else:
            result = build_packets(args.root, args.seed)
    except (ExportError, pilot.PilotError, artifact.ArtifactError) as error:
        print(f"refused: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
