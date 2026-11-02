"""Read-only investigation trace projection (HTTP v1.2, G3C-A).

One REPEATABLE READ READ ONLY transaction, so every part comes from the same stored snapshot
and the database refuses any write. Nothing here runs a role or tool, recovers a workflow or
changes a case. Every query filters on the caller's tenant and session; a foreign case or
workflow is not_found. See docs/api/investigation-trace-v1.2.md.
"""
from __future__ import annotations

import uuid

from sentinel import db
from sentinel.contracts.agents import StepRecord, ToolResult, WorkflowRecord
from sentinel.contracts.http_v12 import MAX_LISTED_WORKFLOWS, InvestigationTrace
from sentinel.contracts.v1 import AgentRun, TrustedContext

SNAPSHOT = "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
# Each claim moves the case open -> investigating by compare-and-set, so case_revision is
# strictly increasing across a case's workflows; the rest only orders an impossible tie.
NEWEST_FIRST = "ORDER BY case_revision DESC, started_at DESC, id DESC"


def investigation_trace(svc, ctx: TrustedContext, case_id: uuid.UUID,
                        workflow_id: uuid.UUID | None = None) -> dict:
    from sentinel.service import ServiceError, _require
    _require(ctx, "read_case")
    scope = (ctx.scope.tenant_id, ctx.scope.session_id)
    with db.connect(svc.database_url) as conn, conn.transaction():
        conn.execute(SNAPSHOT)
        read_at = svc.clock()
        case = svc._case(conn, ctx, case_id)
        legacy = conn.execute(
            "SELECT count(*) AS n FROM agent_runs WHERE case_id = %s AND tenant_id = %s"
            " AND session_id = %s AND workflow_id IS NULL", (case.id, *scope)).fetchone()["n"]
        listed = conn.execute(
            "SELECT body, count(*) OVER () AS total FROM agent_workflows WHERE case_id = %s"
            f" AND tenant_id = %s AND session_id = %s {NEWEST_FIRST} LIMIT %s",
            (case.id, *scope, MAX_LISTED_WORKFLOWS)).fetchall()
        records = [WorkflowRecord.model_validate(row["body"]) for row in listed]
        if workflow_id is None:
            chosen = records[0] if records else None
        else:
            row = conn.execute(
                "SELECT body FROM agent_workflows WHERE id = %s AND case_id = %s"
                " AND tenant_id = %s AND session_id = %s", (workflow_id, case.id, *scope)
            ).fetchone()
            if row is None:
                raise ServiceError("not_found", 404)
            chosen = WorkflowRecord.model_validate(row["body"])
        selected = None
        if chosen is not None:
            runs = conn.execute(
                "SELECT started_at, finished_at, attempt, body, finding FROM agent_runs"
                " WHERE workflow_id = %s AND tenant_id = %s AND session_id = %s ORDER BY seq",
                (chosen.id, *scope)).fetchall()
            steps = conn.execute(
                "SELECT body, payload FROM agent_steps WHERE workflow_id = %s"
                " AND tenant_id = %s AND session_id = %s ORDER BY step_seq",
                (chosen.id, *scope)).fetchall()
            selected = _workflow_trace(svc, chosen, runs, steps, read_at)
    trace = InvestigationTrace.model_validate({
        "case_id": case.id, "case_state": case.state, "case_revision": case.revision,
        "read_at": read_at, "legacy_investigator_runs": legacy,
        "workflow_count": listed[0]["total"] if listed else 0,
        "workflows": [_summary(record) for record in records], "selected": selected})
    return trace.model_dump(mode="json")


def _summary(record: WorkflowRecord) -> dict:
    disposition = record.disposition
    return {"id": record.id, "case_revision": record.case_revision, "status": record.status,
            "terminal_by": record.terminal_by, "started_at": record.started_at,
            "deadline_at": record.deadline_at, "finished_at": record.finished_at,
            "disposition_kind": disposition.kind if disposition else None,
            "inconclusive_code": disposition.inconclusive_code if disposition else None}


def _deadline_status(record: WorkflowRecord, read_at) -> str | None:
    from sentinel.service import RECOVERY_GRACE
    if record.status != "running":
        return None
    if read_at <= record.deadline_at:
        return "before_deadline"
    # The same boundary as coordinator.recover_workflow: recoverable strictly after grace.
    return "recovery_due" if record.deadline_at + RECOVERY_GRACE < read_at else "past_deadline"


def _workflow_trace(svc, record: WorkflowRecord, runs, step_rows, read_at) -> dict:
    from sentinel.agents.coordinator import Workflow
    steps = [(StepRecord.model_validate(row["body"]), row["payload"]) for row in step_rows]
    running = record.status == "running"
    configured = svc.investigator
    limits = (configured.limits if isinstance(configured, Workflow)
              and configured.config == record.config else None)
    basis = record.disposition.basis_run_id if record.disposition else None
    attempts = [_attempt(row, steps, basis) for row in runs]
    usages = [a["usage"] for a in attempts]
    reported = [u for u in usages if u is not None and u.source == "adapter_reported"]
    return {
        "workflow": {
            **{k: getattr(record, k) for k in (
                "id", "case_revision", "status", "terminal_by", "started_at", "deadline_at",
                "finished_at", "config", "tool_profile", "input_snapshot_sha256",
                "disposition")},
            "recorded_role_invocations": None if running else record.role_invocations,
            "recorded_tool_calls": None if running else record.tool_calls,
            "deadline_status": _deadline_status(record, read_at)},
        "limits": limits,
        "attempts": attempts,
        "steps": [{**step.model_dump(exclude={"workflow_id", "usage", "schema_version"})}
                  for step, _ in steps],
        "tool_results": [ToolResult.model_validate(payload) for step, payload in steps
                         if step.kind in ("tool_executed", "tool_denied")],
        "usage_summary": {
            "reported_attempts": len(reported),
            "not_applicable_attempts": sum(u is not None and u.source == "not_applicable"
                                           for u in usages),
            "unknown_attempts": sum(u is None or u.source == "unknown" for u in usages),
            "input_tokens": sum(u.input_tokens for u in reported) if reported else None,
            "output_tokens": sum(u.output_tokens for u in reported) if reported else None},
    }


def _attempt(row, steps, basis) -> dict:
    run = AgentRun.model_validate(row["body"])
    index = {(step.kind, step.agent_run_id): i for i, (step, _) in enumerate(steps)
             if step.agent_run_id is not None}
    start = index.get(("role_started", run.id))
    end = index.get(("role_completed", run.id), index.get(("role_failed", run.id)))
    end_step, payload = steps[end] if end is not None else (None, None)
    completed = end_step is not None and end_step.kind == "role_completed"
    checks = None
    if completed and run.role == "investigator":
        # The coordinator verifies an investigator attempt right after it completes; one that
        # asked for tools instead goes back to gathering and has no recorded check.
        for step, _ in steps[end + 1:]:
            if step.kind == "role_started":
                break
            if step.kind == "claims_checked":
                checks = list(step.checks)
                break
    elapsed = None
    if start is not None and end_step is not None:
        delta = end_step.elapsed_ms - steps[start][0].elapsed_ms
        elapsed = delta if delta >= 0 else None
    failed = end_step is not None and end_step.kind == "role_failed"
    return {
        "agent_run_id": run.id, "role": run.role, "attempt": row["attempt"],
        "status": run.status, "failure_code": run.failure_code,
        "failure_source": None if run.status != "failed" else
        "role_step" if failed else "workflow_terminal",
        "worker_unresolved": end_step.worker_unresolved if failed else None,
        "started_at": row["started_at"], "finished_at": row["finished_at"],
        "config": run.config, "output": payload if completed else None,
        "output_sha256": end_step.output_sha256 if completed else None,
        "claim_checks": checks, "elapsed_ms": elapsed,
        "usage": end_step.usage if completed else None,
        "basis": run.id == basis, "finding": row["finding"],
    }
