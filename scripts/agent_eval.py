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
accounting and a run record as JSON. Exit 0: complete. Exit 2: refused before any work.
Exit 3: a setup failure stopped the run; earlier attempts are kept and the record says what
stopped and what never started (runbook §4). Development results only: never a final held-out
evaluation.

The JSON is a versioned run artifact (`record.artifact_version`, G3D-P4a; format in
docs/evals/agents/p4a-tooling.md). Per attempt it adds scoped IDs, pins, the adopted
disposition, recorded role intervals, a capacity snapshot, observed late returns and the
reservation accounting; workflow_elapsed_ms stays null (not measured). These are read only
after the outcome, so a telemetry failure never changes a recorded outcome.
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
sys.path.insert(0, str(ROOT / "scripts"))

from agent_eval_support import artifact, measure  # noqa: E402

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
    try:  # every catalog read and the close, not only the connect (R41)
        with _connect(runtime_url, "runtime") as rt:
            here = rt.execute(IDENTITY).fetchone()
            attributes = rt.execute(
                "SELECT rolsuper, rolcreaterole, rolcreatedb, rolreplication, rolbypassrls"
                " FROM pg_roles WHERE rolname = session_user").fetchone()
    except psycopg.Error:
        raise Refused("runtime_check_failed", "a runtime catalog check failed") from None
    try:
        with _connect(operator_url, "operator") as op:
            there = op.execute(IDENTITY).fetchone()
            if any(here[k] != there[k] for k in SAME):
                raise Refused("database_mismatch", "the operator and runtime configurations "
                              "reach different databases")
            if here["login"] == there["login"] or here["current"] != here["login"] \
                    or any(attributes.values()):
                raise Refused("runtime_unsafe", "the runtime login is the operator, switched "
                              "role, or holds superuser/administration attributes")
            op.row_factory = tuple_row  # roles.py reads positional rows
            reasons = (roles.unsafe_reasons(op, here["login"])
                       + roles.verify_effective(op, here["login"])
                       + roles.environment_reasons(op))
            op.rollback()
    except psycopg.Error:
        raise Refused("operator_check_failed",
                      "an operator catalog check of the runtime role failed") from None
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


class SetupFailed(Exception):
    """Setup before the request (provision, authenticate, ingest) failed: not an attempt."""

    def __init__(self, phase: str, code: str):
        super().__init__(phase)
        self.phase, self.code = phase, code


def stored_measurements(runtime_url: str, case_id, scope) -> dict:
    """The case's stored workflow history, read as the runtime role in one read-only
    transaction and scoped to the attempt's own tenant/session/case."""
    from sentinel import db
    args = (case_id, scope.tenant_id, scope.session_id)
    where = " WHERE case_id = %s AND tenant_id = %s AND session_id = %s"
    with db.connect(runtime_url) as conn, conn.transaction():
        conn.execute("SET TRANSACTION READ ONLY")
        pins = conn.execute("SELECT body->'pins' AS pins FROM cases WHERE id = %s"
                            " AND tenant_id = %s AND session_id = %s", args).fetchone()
        workflows = conn.execute("SELECT id, status, terminal_by, body FROM agent_workflows"
                                 + where + " ORDER BY started_at, id", args).fetchall()
        runs = conn.execute("SELECT id, workflow_id, attempt, status, body, finding"
                            " FROM agent_runs" + where + " ORDER BY seq", args).fetchall()
        steps = [r["body"] for r in conn.execute(
            "SELECT body FROM agent_steps" + where + " ORDER BY seq", args)]
    adopted = None
    for workflow in workflows:  # a workflow names its basis run; never the last or attempt 1
        disposition = workflow["body"].get("disposition") or {}
        if disposition.get("kind") in ("recommend", "abstain"):
            adopted = {"source": "workflow_disposition", "kind": disposition["kind"],
                       "operation": disposition.get("operation"),
                       "reason_code": disposition.get("reason_code"),
                       "basis_run_id": disposition.get("basis_run_id"),
                       "workflow_id": str(workflow["id"]),
                       "supported_claims": disposition.get("supported_claims"),
                       "unsupported_claims": disposition.get("unsupported_claims")}
    if adopted is None and not workflows:  # the single investigator: its run with a finding
        found = [r for r in runs if r["finding"]]
        if len(found) == 1:
            finding = found[0]["finding"]
            adopted = {"source": "single_investigator_finding", "kind": None,
                       "operation": finding.get("operation"),
                       "reason_code": finding.get("reason_code"),
                       "basis_run_id": str(found[0]["id"])}
    return {"pins": pins["pins"] if pins else None,
            "workflow_ids": [str(w["id"]) for w in workflows],
            "workflows": [{"id": str(w["id"]), "status": w["status"],
                           "terminal_by": w["terminal_by"],
                           "role_invocations": w["body"].get("role_invocations"),
                           "tool_calls": w["body"].get("tool_calls"),
                           "disposition_kind": (w["body"].get("disposition") or {}).get("kind"),
                           "inconclusive_code": (w["body"].get("disposition") or {}).get(
                               "inconclusive_code")} for w in workflows],
            "disposition": adopted,
            "recorded_role_attempts": len(runs),
            "repeats": sum(1 for r in runs if r["attempt"] == 2),
            "role_intervals": measure.role_intervals(steps)}


def safe_code(error: Exception) -> str:
    """A typed service code, else the exception class name; never its message."""
    from sentinel.service import ServiceError
    return error.code if isinstance(error, ServiceError) else type(error).__name__


def attempt(provisioner, runtime_url: str, investigator, case_id: str) -> dict:
    """One protocol-v1 attempt (one investigate request): the operator issues the session;
    the rest is runtime. Raises SetupFailed if the request could not be started."""
    import agent_cases as ac
    from sentinel.service import Sentinel, ServiceError, utc_now

    phase = "provision"
    try:  # Exception only: KeyboardInterrupt and SystemExit still stop the process
        token = provisioner.create_session(ac.ANALYST)[0]
        phase = "authenticate"
        svc = Sentinel(runtime_url, investigator, utc_now)
        ctx = svc.authenticate(token)
        phase = "ingest"
        case = ac.seed(svc, ctx, case_id, utc_now)["case"]
    except Exception as error:
        raise SetupFailed(phase, safe_code(error)) from None
    row = {"case": case_id, "ids": {"tenant_id": str(ctx.scope.tenant_id),
                                    "session_id": str(ctx.scope.session_id),
                                    "case_id": str(case["id"])},
           "started_at": datetime.now(timezone.utc).isoformat()}
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
        row["outcome"], row["code"] = "error", safe_code(error)
    returned = time.monotonic()
    row["request_latency_s"] = round(returned - started, 3)
    row["ended_at"] = datetime.now(timezone.utc).isoformat()
    # Exact protocol-v1 workflow elapsed is not observable here (accepted P4 plan, R44).
    row["workflow_elapsed_ms"], row["workflow_elapsed_status"] = None, "not_measured"
    try:  # the attempt's own service instance, this process only
        row["capacity"] = measure.capacity_observation(svc, returned)
    except Exception as error:
        row["capacity"] = {"status": "unavailable", "error": safe_code(error)}
    if row["outcome"] == "error":
        row["usage_sources"] = ["not_read"]
        row["telemetry"] = {"status": "not_read"}
        return row
    try:  # telemetry after the outcome: a failure leaves the known outcome as it is
        row["usage_sources"] = usage_sources(runtime_url, case["id"]) or ["no_role_steps"]
    except Exception as error:
        row["usage_sources"], row["usage_error"] = ["unavailable"], safe_code(error)
    try:
        row.update(stored_measurements(runtime_url, case["id"], ctx.scope))
        row["telemetry"] = {"status": "read"}
    except Exception as error:
        row["telemetry"] = {"status": "unavailable", "error": safe_code(error)}
    return row


def reservation(name: str, row: dict) -> dict:
    """Accounting kept apart (accepted P4 plan §2): reserved allowance, stored role
    attempts, observed adapter submissions and provider/CLI reach. Unknown stays unknown."""
    live = name in artifact.LIVE
    intervals = row.get("role_intervals") or []
    return {"reserved_invocations": artifact.RESERVATIONS[name],
            "unit": "application adapter/CLI-invocation reservation (not provider requests "
                    "or billing)",
            "recorded_role_attempts": row.get("recorded_role_attempts", artifact.UNKNOWN),
            "pre_submission_refusals": sum(i["pre_submission"] for i in intervals),
            "observed_adapter_submissions": "not_observed" if live else "not_applicable",
            "provider_reach": artifact.UNKNOWN if live else "not_applicable"}


def comparator_config(name: str, investigator) -> dict:
    workflow = getattr(investigator, "adapters", None)
    if workflow:
        aliases = sorted({getattr(a, "model", None) for a in workflow.values()} - {None})
    else:
        aliases = [investigator.model] if getattr(investigator, "model", None) else []
    live = name in artifact.LIVE
    return {"pin": investigator.config.model_dump(mode="json"), "live": live,
            "reservation_per_attempt": artifact.RESERVATIONS[name],
            "model_alias": aliases[0] if len(aliases) == 1 else (aliases or None),
            "model_version": artifact.UNKNOWN if live else "not_applicable"}


def summarize(rows: list[dict], not_attempted: list[str]) -> dict:
    tally = Counter({"attempts": len(rows)})
    for row in rows:
        tally[{"disposition": "dispositions"}.get(row["outcome"], row["outcome"])] += 1
    inconclusive = Counter(row["failure_codes"][-1] if row["failure_codes"] else "none"
                           for row in rows if row["outcome"] == "inconclusive")
    # Tokens only if every attempt's usage is known to be adapter-reported (protocol-v1);
    # missing, unavailable, not-read or unknown provenance leaves the comparator unknown.
    reported = bool(rows) and all(row.get("usage_sources") == ["adapter_reported"]
                                  for row in rows)
    return {"counts": dict(tally), "inconclusive_by_code": dict(inconclusive),
            "tokens": "adapter_reported" if reported else "unknown",
            "request_latency_s": [row["request_latency_s"] for row in rows],
            "attempts": rows, "cases_not_attempted": not_attempted}


def run(operator_url: str, runtime_url: str, names: list[str], case_ids: list[str],
        progress: dict | None = None) -> dict:
    """Comparator name -> summary, for every comparator that started. If setup fails, the
    run stops there; `progress` (if given) gets `stopped` and `comparators_not_started`."""
    from sentinel.investigators import DeterministicInvestigator
    from sentinel.service import Sentinel, utc_now

    progress = {} if progress is None else progress
    progress.update(stopped=None, comparators_not_started=[], comparator_config={})
    # Provisioning only: this object issues sessions; it never ingests, reads or investigates.
    provisioner = Sentinel(operator_url, DeterministicInvestigator(), utc_now)
    report = {}
    with measure.LateReturnObserver() as observer:
        _run(provisioner, runtime_url, names, case_ids, progress, report)
    for name, result in report.items():  # late returns observed up to the cutoff above
        for row in result["attempts"]:
            if name in artifact.WORKFLOW_COMPARATORS and "workflow_ids" in row:
                events = observer.for_workflows(row["workflow_ids"])
                row["late_returns"] = {
                    "observed_count": len(events), "events": events,
                    "window": "sentinel.agents log events in this process until this "
                              "run() call returned", "after_cutoff": artifact.UNKNOWN}
            else:
                row["late_returns"] = {"status": "not_observable" if name in
                                       artifact.WORKFLOW_COMPARATORS else
                                       "not_observable (the single investigator emits no "
                                       "late-return event)"}
    return report


def _run(provisioner, runtime_url, names, case_ids, progress, report) -> None:
    for index, name in enumerate(names):
        try:
            investigator = comparator(name)
        except Exception as error:
            progress.update(comparators_not_started=names[index:], stopped={
                "comparator": name, "case": None, "phase": "comparator",
                "code": safe_code(error)})
            return
        try:  # provenance only: a failure to describe the comparator never stops the run
            progress["comparator_config"][name] = comparator_config(name, investigator)
        except Exception as error:
            progress["comparator_config"][name] = {"status": "unavailable",
                                                   "error": safe_code(error)}
        rows = []
        for case_id in case_ids:
            try:
                row = attempt(provisioner, runtime_url, investigator, case_id)
            except SetupFailed as failure:  # stop; earlier attempts are kept as they are
                progress.update(comparators_not_started=names[index + 1:], stopped={
                    "comparator": name, "case": case_id, "phase": failure.phase,
                    "code": failure.code})
                break
            number = len(rows) + 1
            rows.append({"index": number, "attempt_id": f"{name}:{number}:{case_id}",
                         **row, "reservation": reservation(name, row)})
        stopped = progress["stopped"] is not None
        report[name] = summarize(rows, case_ids[len(rows):] if stopped else [])
        if stopped:
            return


def git_head() -> str:
    try:
        head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                              capture_output=True, text=True, timeout=10).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain"],
                               capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return (head + ("+dirty" if dirty else "")) if head else "unknown"


def load_annotations(path: Path | None) -> list[dict]:
    """Manual annotations need a recorded source and time; nothing here contacts an
    account to fill them."""
    if path is None:
        return []
    try:
        items = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise Refused("annotations_unreadable", "the annotations file is not readable JSON") \
            from None
    if not isinstance(items, list) or not all(
            isinstance(i, dict) and {"field", "value", "source", "recorded_at"} <= set(i)
            and i["field"] in ("quota", "model_version") for i in items):
        raise Refused("annotations_invalid", "each annotation needs field (quota or "
                      "model_version), value, source and recorded_at")
    return [{k: str(i[k]) for k in ("field", "value", "source", "recorded_at")}
            for i in items]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--database-url", help="provisioning-only operator URL (prefer "
                        f"{OPERATOR_ENV}); never used for investigations")
    parser.add_argument("--comparators", default="C0,C2-det")
    parser.add_argument("--cases", default="dev")
    parser.add_argument("--allow-live", action="store_true")
    parser.add_argument("--annotations", type=Path, help="manual annotations JSON (quota, "
                        "model version), each with field, value, source and recorded_at")
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
        if len(set(names)) != len(names):
            raise Refused("duplicate_comparator", "name each comparator once")
        check_cases(case_ids)
        annotations = load_annotations(args.annotations)
        operator_url, runtime_url = configuration(args.database_url)
        verify_authorities(operator_url, runtime_url)
    except Refused as refusal:
        print(f"refused: {refusal.code}: {refusal.detail}")
        return 2
    started = datetime.now(timezone.utc)
    progress = {}
    results = run(operator_url, runtime_url, names, case_ids, progress)
    print(json.dumps({
        "record": {
            "artifact_version": artifact.RUN_VERSION,
            "kind": "development (not a held-out evaluation)",
            "status": "incomplete" if progress["stopped"] else "complete",
            "stopped": progress["stopped"],
            "comparators_not_started": progress["comparators_not_started"],
            "git": git_head(),
            "platform": platform.platform(), "python": platform.python_version(),
            "started_at": started.isoformat(),
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "planned_comparators": names, "planned_cases": case_ids,
            "comparator_config": progress["comparator_config"],
            "measurements": {
                "request_latency": "seconds, monotonic, around svc.investigate (includes "
                                   "admission, setup, cleanup)",
                "workflow_elapsed": "not measured; the 150 s gate is not demonstrated",
                "role_intervals": "recorded step intervals, not provider latency",
                "usage_tokens_model_version_quota": "unknown unless adapter_reported or "
                                                    "manually annotated with a source"},
            "quota": "annotated" if any(a["field"] == "quota" for a in annotations)
            else artifact.UNKNOWN,
            "manual_annotations": annotations,
            "authorities": {"session_provisioning": "operator",
                            "authenticate_ingest_investigate_read": "runtime",
                            "runtime_verified": True},
            "cases": {c: {"runtime_sha256": runtime_digest(c),
                          "faults_not_applied": [f["kind"] for f in
                                                 ac.CASES[c]["runtime"]["faults"]]}
                      for c in case_ids}},
        "comparators": results}, indent=2))
    return 3 if progress["stopped"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
