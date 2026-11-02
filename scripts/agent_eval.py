"""Manual comparator runner for protocol-v1 development cases (G3B, G3D-P1). Never run by
the gates. Runbook: docs/evals/agents/evaluator-runbook.md.

    uv run --locked python scripts/agent_eval.py --comparators C0,C2-det --cases dev

Two authorities, both read from the environment (never printed):
- SENTINEL_EVAL_OPERATOR_URL: the schema owner of a disposable, migrated database. It is used
  only to verify the runtime identity (read-only catalog queries) and to issue one session
  per attempt, which the runtime role cannot do.
- SENTINEL_EVAL_RUNTIME_URL: a least-privilege runtime role of the same database, created by
  `python -m sentinel.cli grant-runtime`. Authentication, case ingestion, evidence reads,
  the investigation and the post-attempt usage read all run as this role, through the
  service as the API runs them.
`--database-url` is kept as a provisioning-only operator URL (it lands in shell history;
prefer the environment). There is no fallback: without a valid, separate runtime role of the
same database the runner refuses before constructing any comparator or running any case.

Each case is ingested into a fresh session from its `runtime` history and alerted row only;
evaluator data is never read here. Runtime `faults` are test-harness instructions that this
runner does not apply; they are listed per case as not applied. Live comparators (C1, C2)
call the owner's local Claude subscription and are refused unless `--allow-live` is given
explicitly; this script never falls back to a paid key. It prints protocol-v1 attempt
accounting and a run record as JSON. Development results only: never a final held-out
evaluation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "support"))

OPERATOR_ENV, RUNTIME_ENV = "SENTINEL_EVAL_OPERATOR_URL", "SENTINEL_EVAL_RUNTIME_URL"
COMPARATORS = ("C0", "C1", "C2-det", "C2")
LIVE = {"C1", "C2"}
PENDING = {"investigation_in_progress", "investigation_outcome_unknown"}


class Refused(Exception):
    """A typed refusal. Its code and detail never carry a connection string, password,
    token or raw driver message."""

    def __init__(self, code: str, detail: str):
        super().__init__(code)
        self.code, self.detail = code, detail


def comparator(name: str):
    from sentinel import investigators
    from sentinel.agents import coordinator
    if name == "C0":
        return investigators.DeterministicInvestigator()
    if name == "C1":
        return investigators.ClaudeCliInvestigator()
    if name == "C2-det":
        return coordinator.deterministic_workflow()
    if name == "C2":
        return coordinator.claude_cli_workflow()
    raise Refused("unknown_comparator", "comparators are " + ", ".join(COMPARATORS))


# ---- configuration -------------------------------------------------------------------------

def configuration(database_url: str | None) -> tuple[str, str]:
    """(operator URL, runtime URL). --database-url is an operator URL only."""
    operator = os.environ.get(OPERATOR_ENV) or ""
    if database_url:
        if operator and operator != database_url:
            raise Refused("operator_config_conflict",
                          f"--database-url and {OPERATOR_ENV} differ")
        operator = database_url
    runtime = os.environ.get(RUNTIME_ENV) or ""
    if not operator:
        raise Refused("operator_config_missing", f"set {OPERATOR_ENV} (provisioning only)")
    if not runtime:
        raise Refused("runtime_config_missing",
                      f"set {RUNTIME_ENV} to a least-privilege runtime role of the same "
                      "database; the operator is never used for investigations")
    if runtime == operator:
        raise Refused("runtime_unsafe", "the runtime and operator configurations are "
                      "identical")
    return operator, runtime


# Same database: name and OID within the same running server (start time and port).
IDENTITY = ("SELECT current_database() AS db, d.oid AS db_oid, session_user AS login,"
            " current_user AS current, pg_postmaster_start_time() AS started,"
            " current_setting('port') AS port FROM pg_database d"
            " WHERE d.datname = current_database()")
SAME = ("db", "db_oid", "started", "port")


def _connect(url: str, side: str):
    import psycopg

    from sentinel import db
    try:
        return db.connect(url)
    except (psycopg.Error, ValueError):  # the driver message can echo host and user
        raise Refused(f"{side}_connection_failed",
                      f"could not connect with the {side} configuration") from None


def verify_authorities(operator_url: str, runtime_url: str) -> None:
    """Refuse unless both URLs reach the same database and the runtime login is a distinct
    least-privilege role, using the accepted roles.py checks read-only (no grant changes)."""
    import psycopg
    from psycopg.rows import tuple_row

    from sentinel.db import roles
    with _connect(runtime_url, "runtime") as rt:
        here = rt.execute(IDENTITY).fetchone()
        attributes = rt.execute(
            "SELECT rolsuper, rolcreaterole, rolcreatedb, rolreplication, rolbypassrls"
            " FROM pg_roles WHERE rolname = session_user").fetchone()
    with _connect(operator_url, "operator") as op:
        there = op.execute(IDENTITY).fetchone()
        if any(here[k] != there[k] for k in SAME):
            raise Refused("database_mismatch",
                          "the operator and runtime configurations reach different databases")
        if here["login"] == there["login"] or here["current"] != here["login"] \
                or any(attributes.values()):
            raise Refused("runtime_unsafe", "the runtime login is the operator, switched "
                          "role, or holds superuser/administration attributes")
        op.row_factory = tuple_row  # roles.py reads positional rows
        try:
            reasons = (roles.unsafe_reasons(op, here["login"])
                       + roles.verify_effective(op, here["login"])
                       + roles.environment_reasons(op))
        except psycopg.Error:
            raise Refused("runtime_check_failed",
                          "the operator could not inspect the runtime role") from None
        op.rollback()
    if reasons:
        raise Refused("runtime_unsafe", "not a least-privilege runtime role: "
                      + "; ".join(sorted(set(reasons))))


def check_cases(case_ids: list[str]) -> None:
    """Only the setup this runner performs: rule scoring and no provisioned profile."""
    import agent_cases as ac
    unknown = [c for c in case_ids if c not in ac.CASES]
    if unknown:
        raise Refused("unknown_case", f"unknown development cases {unknown}")
    for case_id in case_ids:
        runtime = ac.CASES[case_id]["runtime"]
        if runtime["scorer"] != "rule" or runtime["account_profile"] is not None:
            raise Refused("unsupported_case", f"{case_id} needs scorer or profile setup "
                          "this runner does not perform")


# ---- run -----------------------------------------------------------------------------------

def runtime_digest(case_id: str) -> str:
    import agent_cases as ac
    body = json.dumps(ac.CASES[case_id]["runtime"], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode()).hexdigest()


def usage_sources(runtime_url: str, case_id) -> list[str]:
    """Usage sources of the case's role steps, read as the runtime role (none for C0)."""
    from sentinel import db
    with db.connect(runtime_url) as conn:
        return sorted(r["source"] for r in conn.execute(
            "SELECT DISTINCT body->'usage'->>'source' AS source FROM agent_steps"
            " WHERE case_id = %s AND body->>'kind' IN ('role_completed', 'role_failed')",
            (case_id,)))


def attempt(provisioner, runtime_url: str, investigator, case_id: str) -> dict:
    """One protocol-v1 attempt: the operator issues the session; the rest is runtime."""
    import agent_cases as ac
    from sentinel.service import Sentinel, ServiceError, utc_now

    token = provisioner.create_session(ac.ANALYST)[0]
    svc = Sentinel(runtime_url, investigator, utc_now)
    ctx = svc.authenticate(token)
    case = ac.seed(svc, ctx, case_id, utc_now)["case"]
    row = {"case": case_id}
    started = time.monotonic()
    try:
        detail = svc.investigate(ctx, case["id"], case["revision"])
        state = detail["case"]["state"]
        row["outcome"] = "disposition" if state == "awaiting_approval" else "inconclusive"
        row["case_state"] = state
        row["failure_codes"] = [r["run"]["failure_code"] for r in detail["agent_runs"]
                                if r["run"].get("failure_code")]
    except ServiceError as error:
        row["outcome"] = ("refused" if error.code == "agent_capacity_exhausted" else
                          "pending" if error.code in PENDING else "error")
        row["code"] = error.code
    except Exception as error:  # outside the typed paths: counted, never dropped or re-run
        row["outcome"], row["code"] = "error", type(error).__name__
    row["request_latency_s"] = round(time.monotonic() - started, 3)
    if row["outcome"] != "error":
        row["usage_sources"] = usage_sources(runtime_url, case["id"]) or ["no_role_steps"]
    return row


def run(operator_url: str, runtime_url: str, names: list[str], case_ids: list[str]) -> dict:
    from sentinel.investigators import DeterministicInvestigator
    from sentinel.service import Sentinel, utc_now

    # Provisioning only: this object issues sessions; it never ingests, reads or investigates.
    provisioner = Sentinel(operator_url, DeterministicInvestigator(), utc_now)
    report = {}
    for name in names:
        rows = [attempt(provisioner, runtime_url, comparator(name), c) for c in case_ids]
        tally = Counter({"attempts": len(rows)})
        for row in rows:
            tally[{"disposition": "dispositions"}.get(row["outcome"], row["outcome"])] += 1
        inconclusive = Counter(row["failure_codes"][-1] if row["failure_codes"] else "none"
                               for row in rows if row["outcome"] == "inconclusive")
        sources = {s for row in rows for s in row.get("usage_sources", ())}
        report[name] = {
            "counts": dict(tally), "inconclusive_by_code": dict(inconclusive),
            # Tokens only if every call in the comparator measured them (protocol-v1).
            "tokens": "adapter_reported" if sources == {"adapter_reported"} else "unknown",
            "request_latency_s": [row["request_latency_s"] for row in rows],
            "attempts": rows}
    return report


def git_head() -> str:
    try:
        head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                              capture_output=True, text=True, timeout=10).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain"],
                               capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return (head + ("+dirty" if dirty else "")) if head else "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--database-url", help="provisioning-only operator URL (prefer "
                        f"{OPERATOR_ENV}); never used for investigations")
    parser.add_argument("--comparators", default="C0,C2-det")
    parser.add_argument("--cases", default="dev")
    parser.add_argument("--allow-live", action="store_true")
    args = parser.parse_args()
    names = [n.strip() for n in args.comparators.split(",") if n.strip()]
    if LIVE & set(names) and not args.allow_live:
        print("refused: C1/C2 use the local Claude subscription; pass --allow-live explicitly")
        return 2
    import agent_cases as ac
    case_ids = sorted(ac.CASES) if args.cases == "dev" else args.cases.split(",")
    try:
        if not names or set(names) - set(COMPARATORS):
            raise Refused("unknown_comparator", "comparators are " + ", ".join(COMPARATORS))
        check_cases(case_ids)
        operator_url, runtime_url = configuration(args.database_url)
        verify_authorities(operator_url, runtime_url)
    except Refused as refusal:
        print(f"refused: {refusal.code}: {refusal.detail}")
        return 2
    started = datetime.now(timezone.utc)
    results = run(operator_url, runtime_url, names, case_ids)
    print(json.dumps({
        "record": {
            "kind": "development (not a held-out evaluation)", "git": git_head(),
            "platform": platform.platform(), "python": platform.python_version(),
            "started_at": started.isoformat(),
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "authorities": {"session_provisioning": "operator",
                            "authenticate_ingest_investigate_read": "runtime",
                            "runtime_verified": True},
            "cases": {c: {"runtime_sha256": runtime_digest(c),
                          "faults_not_applied": [f["kind"] for f in
                                                 ac.CASES[c]["runtime"]["faults"]]}
                      for c in case_ids}},
        "comparators": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
