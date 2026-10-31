"""Deterministic coordinator for the three-role workflow (G3A-design sections 3, 3.1, 3.2, 6.1).

Server code owns role identity, transitions, tool execution, claim verification, budgets,
leases, the disposition and the action intent. Roles return untrusted output only. Every
persisted step runs in its own bounded transaction guarded by "this workflow is running and
its case is investigating at the claimed revision"; one terminal transaction ends every
workflow, with or without a running role. Human approval and execution are unchanged.
"""
from __future__ import annotations

import logging
import uuid
from concurrent import futures
from dataclasses import dataclass, field
from datetime import timedelta

from pydantic import TypeAdapter, ValidationError
from psycopg.types.json import Jsonb

from sentinel.agents import adapters as role_adapters
from sentinel.agents.budget import (
    QUARANTINE, BoundedTransaction, BudgetExhausted, CommitUncertain, ConnectionLost, Deadline,
    discard, open_connection, usable,
)
from sentinel.agents.capacity import CapacityExhausted, late_worker_event
from sentinel.agents.claims import Ledger, check_all, policy_problems, render_rationale
from sentinel.agents.tools import TOOL_PROFILE_DOCUMENT, CaseFacts, denied, run_tool
from sentinel.contracts.agents import (
    STEP_NAMESPACE, AccountHistoryArgs, CaseEvidenceArgs, Disposition, ScoringOutcomeArgs,
    StepRecord, ToolRequest, Usage, WorkflowConfig, WorkflowLimits, WorkflowRecord,
)
from sentinel.contracts.guards import ContractViolation, require_evidence_snapshot
from sentinel.contracts.v1 import (
    AgentRun, Alert, Case, EvidenceItem, InvestigationFinding, RunBudget, ScoringOutcome,
    Transaction, canonical_digest,
)
from sentinel.investigators import InvestigatorError
from sentinel.scoring import artifact

LOG = logging.getLogger("sentinel.agents")
ROLES = ("evidence_analyst", "investigator", "reviewer")
BASELINE_TOOLS = (CaseEvidenceArgs(tool="case_evidence"),
                  ScoringOutcomeArgs(tool="scoring_outcome"),
                  AccountHistoryArgs(tool="account_history", window="24h"))
ANALYST_FOLLOWUPS, INVESTIGATOR_FOLLOWUPS = 2, 1
NOT_APPLICABLE = Usage(measured=False, source="not_applicable")
RUN_CODES = {"timeout", "provider_unavailable", "invalid_output", "budget_exhausted"}
_TOOL_REQUEST = TypeAdapter(ToolRequest)


class Workflow:
    """The operator-selected three-role mode. It exposes the investigator attributes the
    service pins and reports (config, principal_id, timeout_seconds), plus tool_profile."""

    def __init__(self, role_adapters_by_role: dict, limits: WorkflowLimits | None = None):
        if set(role_adapters_by_role) != set(ROLES):
            raise ValueError("exactly the three roles")
        self.adapters = role_adapters_by_role
        self.limits = limits or WorkflowLimits()
        self.tool_profile = artifact("agent-read-tools", "t1", TOOL_PROFILE_DOCUMENT)
        self.document = WorkflowConfig(
            kind="three-role", roles={r: a.config for r, a in self.adapters.items()},
            tool_profile=self.tool_profile, claim_schema="agents-1.0", limits=self.limits)
        self.config = artifact("three-role-workflow", "w1", self.document.model_dump(mode="json"))
        self.principal_id = role_adapters.principal(self.config)
        self.timeout_seconds = self.limits.workflow_deadline_seconds
        self.live = any(a.live for a in self.adapters.values())

    def investigate(self, view):  # the single-investigator interface is not used
        raise RuntimeError("the three-role workflow runs through the coordinator")


def deterministic_workflow() -> Workflow:
    return Workflow({r: role_adapters.DeterministicRole(r) for r in ROLES})


def claude_cli_workflow(model: str = "sonnet") -> Workflow:
    return Workflow({r: role_adapters.ClaudeCliRoleAdapter(r, model=model) for r in ROLES})


class Superseded(Exception):
    """The workflow is no longer running or its case moved on: write nothing."""


class End(Exception):
    """Finish the workflow inconclusive with this code."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _service_error(code: str):
    from sentinel.service import ServiceError
    return ServiceError(code, 409)


@dataclass
class Run:
    svc: object
    ctx: object
    workflow: Workflow
    deadline: Deadline
    conn: object
    hooks: dict = field(default_factory=dict)
    record: WorkflowRecord | None = None
    facts: CaseFacts | None = None
    ledger: Ledger | None = None
    seq: int = 0
    role_invocations: int = 0
    tool_calls: int = 0
    followups_left: int = 0
    repeats_left: int = 0
    revisions_left: int = 0
    completed_investigator_run: object = None
    claims_supported: int = 0
    claims_unsupported: int = 0
    state: str = "claimed"
    transitions: int = 0
    opened: list = field(default_factory=list)

    @property
    def limits(self) -> WorkflowLimits:
        return self.workflow.limits

    @property
    def db_wait_ms(self) -> int:
        return self.limits.db_wait_seconds * 1000

    def hook(self, name: str) -> None:
        if name in self.hooks:
            self.hooks[name](self)

    def connection(self, phase: str):
        """The workflow connection, replaced within the phase's rules when the previous one
        broke, was closed after a failed rollback or is quarantined behind an unanswered
        operation (budget.bounded_call). A quarantined connection is never reused."""
        if not usable(self.conn):
            self.conn = open_connection(self.svc.database_url, self.deadline, phase,
                                        self.limits)
            self.opened.append(self.conn)
        return self.conn

    # ---- claim ----------------------------------------------------------------------------

    def claim(self, case_id, expected_revision: int) -> None:
        svc, ctx = self.svc, self.ctx
        try:
            tx = BoundedTransaction(self.conn, self.deadline, "working", self.db_wait_ms)
        except BudgetExhausted:
            raise _service_error("conflict") from None
        try:
            case = svc._case(tx, ctx, case_id, lock=True)
            now = svc.clock()
            if case.revision != expected_revision:
                raise _service_error("stale_case_revision")
            if case.state == "investigating":
                recovered = svc._recover_lost_run(tx, ctx, case, now)
                tx.commit()
                raise _service_error("investigation_recovered" if recovered
                                     else "investigation_in_progress")
            if case.state == "awaiting_approval" and \
                    svc._expire_lapsed_approval(tx, ctx, case, now) is not None:
                tx.commit()
                raise _service_error("approval_expired")
            if case.state != "open":
                raise _service_error("case_not_investigable")
            if (case.pins.agent_config != self.workflow.config
                    or case.pins.tool_config != self.workflow.tool_profile):
                raise _service_error("stale_agent_config")
            evidence = tuple(EvidenceItem.model_validate(body)
                             for body in svc._rows(tx, ctx, "evidence_items", case.id))
            try:
                require_evidence_snapshot(ctx, case, evidence, now)
            except ContractViolation as violation:
                raise _service_error(str(violation)) from None
            alert = Alert.model_validate(tx.execute(
                "SELECT body FROM alerts WHERE id = %s", (case.alert_id,)).fetchone()["body"])
            txn = Transaction.model_validate(tx.execute(
                "SELECT body FROM transactions WHERE id = %s",
                (alert.transaction_id,)).fetchone()["body"])
            scored = tx.execute("SELECT body FROM scoring_outcomes WHERE transaction_id = %s",
                                (txn.id,)).fetchone()
            claimed = svc._transition(tx, case, "investigating", now)
            self.record = WorkflowRecord(
                id=uuid.uuid4(), case_id=case.id, case_revision=claimed.revision,
                config=self.workflow.config, tool_profile=self.workflow.tool_profile,
                input_snapshot_sha256=case.pins.evidence_snapshot_sha256, status="running",
                started_at=now,
                deadline_at=now + timedelta(seconds=self.limits.workflow_deadline_seconds),
                role_invocations=0, tool_calls=0)
            tx.execute("INSERT INTO agent_workflows (id, tenant_id, session_id, case_id,"
                       " case_revision, status, started_at, deadline_at, body)"
                       " VALUES (%s, %s, %s, %s, %s, 'running', %s, %s, %s)",
                       (self.record.id, *_scope(ctx), case.id, claimed.revision, now,
                        self.record.deadline_at, Jsonb(self.record.model_dump(mode="json"))))
            svc._audit(tx, ctx, claimed, uuid.uuid4(), ctx.actor_id, "human",
                       "investigation_started", "success", now)
            tx.commit()
        except BudgetExhausted:
            raise _service_error("conflict") from None
        except ConnectionLost:
            raise _service_error("conflict") from None
        except CommitUncertain:
            raise _service_error("investigation_outcome_unknown") from None
        except BaseException:
            tx.rollback()
            raise
        self.facts = CaseFacts(ctx=ctx, case=claimed, alert=alert, txn=txn,
                               scoring=ScoringOutcome.model_validate(scored["body"])
                               if scored else None, evidence=evidence)
        self.ledger = Ledger(evidence)
        self.followups_left = self.limits.max_followup_tool_calls
        self.repeats_left = self.limits.max_repeats
        self.revisions_left = self.limits.max_investigator_revisions

    # ---- guarded steps --------------------------------------------------------------------

    def _guard(self, tx) -> None:
        # Lock order: case, then workflow (as the claim, recovery and terminal transaction).
        row = tx.execute(
            "SELECT w.status, c.state, c.revision FROM agent_workflows w"
            " JOIN cases c ON c.id = w.case_id WHERE w.id = %s AND w.tenant_id = %s"
            " AND w.session_id = %s FOR UPDATE OF c, w", (self.record.id, *_scope(self.ctx))
        ).fetchone()
        if row is None or row["status"] != "running" or row["state"] != "investigating" \
                or row["revision"] != self.record.case_revision:
            raise Superseded()

    def write(self, action) -> None:
        """One guarded, bounded working transaction. A known failure raises; an uncertain
        COMMIT ends the workflow (the step may or may not exist, so its seq is skipped)."""
        tx = BoundedTransaction(self.connection("working"), self.deadline, "working",
                                self.db_wait_ms)
        try:
            self._guard(tx)
            action(tx)
            tx.commit()
        except CommitUncertain:
            raise End("coordinator_error") from None
        except BaseException:
            tx.rollback()
            raise

    def step(self, tx, kind: str, state: str, payload=None, **fields) -> None:
        self.seq += 1
        record = StepRecord(workflow_id=self.record.id, seq=self.seq, kind=kind, state=state,
                            elapsed_ms=self.deadline.elapsed_ms(),
                            usage=fields.pop("usage", NOT_APPLICABLE), at=self.svc.clock(),
                            **fields)
        body = record.model_dump(mode="json")
        tx.execute("INSERT INTO agent_steps (id, tenant_id, session_id, workflow_id, case_id,"
                   " step_seq, body, payload) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                   (uuid.uuid5(uuid.NAMESPACE_URL, canonical_digest(STEP_NAMESPACE, body)),
                    *_scope(self.ctx), self.record.id, self.record.case_id, self.seq,
                    Jsonb(body), Jsonb(payload) if payload is not None else None))

    def advance(self, state: str) -> None:
        """One coordinator state change (G3A-design section 3), recorded as a `transition`
        step and counted against the pinned max_transitions before it happens. A repeat
        (invoke) stays in its state and never comes here. The final change to `done` is the
        terminal transaction's own workflow_terminated step and is never refused, so an
        exhausted limit still ends the workflow honestly."""
        if self.transitions >= self.limits.max_transitions:
            raise End("budget_exhausted")
        self.write(lambda tx: self.step(tx, "transition", state))
        self.transitions += 1
        self.state = state

    # ---- tools ----------------------------------------------------------------------------

    def tools(self, requests, state: str, allowance: int) -> None:
        executed = {(r.tool, getattr(r, "window", None)) for r in self.ledger.results.values()}
        for request in requests:
            key = (request.tool, getattr(request, "window", None))
            self.hook(f"before_tool:{request.tool}")
            if key in executed:
                continue
            if allowance <= 0 or (state != "gathering" and self.followups_left <= 0):
                result = denied(self.facts, request.tool, "budget_exhausted",
                                getattr(request, "window", None))
                self.write(lambda tx, r=result: self.step(
                    tx, "tool_denied", state, r.model_dump(mode="json"), tool=r.tool,
                    tool_result_id=r.id))
                continue
            cap = self.limits.tool_statement_timeout_ms
            holder = {}

            def execute(tx, request=request):
                holder["result"] = run_tool(tx, self.facts, request, cap)
                result = holder["result"]
                self.step(tx, "tool_executed", state, result.model_dump(mode="json"),
                          tool=result.tool, tool_result_id=result.id)
            self.write(execute)
            self.ledger.add(holder["result"])
            executed.add(key)
            self.tool_calls += 1
            allowance -= 1
            if state != "gathering":
                self.followups_left -= 1

    # ---- role calls -----------------------------------------------------------------------

    def role_input(self, role: str, **extra) -> dict:
        """Server-rendered input: typed values with their citations and enums only. Never
        external_id, notes, evaluator data or faults."""
        facts, unavailable = [], []
        for item in self.facts.evidence:
            for fact in item.facts:
                facts.append({"fact": fact.name, "value": fact.value,
                              "cite": {"kind": "evidence", "id": str(item.id)}})
        seen = {f["fact"] for f in facts}
        for result in self.ledger.results.values():
            if result.status != "ok":
                continue
            for name, value in result.values.items():
                if name not in seen:
                    seen.add(name)
                    facts.append({"fact": name, "value": value,
                                  "cite": {"kind": "tool_result", "id": str(result.id)}})
        for name in ("large_amount_rule_hit", "history_count_24h", "history_count_7d",
                     "history_median_amount_minor_30d", "history_max_amount_minor_30d",
                     "account_age_days", "prior_known_fraud"):
            if name not in seen:
                unavailable.append(name)
        run_keys = {(r.tool, getattr(r, "window", None)) for r in self.ledger.results.values()}
        offered = [{"tool": "account_history", "window": w} for w in ("24h", "7d", "30d")
                   if ("account_history", w) not in run_keys]
        if ("account_profile", None) not in run_keys:
            offered.append({"tool": "account_profile"})
        return {"role": role, "currency": self.facts.txn.amount.currency, "facts": facts,
                "unavailable": unavailable, "tools_not_yet_run": offered, **extra}

    def invoke(self, role: str, role_input: dict):
        """One role invocation with at most one repeat after a *resolved* failure."""
        attempt = 1
        while True:
            outcome = self._call_once(role, role_input, attempt)
            if outcome[0] == "ok":
                return outcome[1], outcome[2]
            code, worker_returned = outcome[1], outcome[2]
            if worker_returned and code in ("provider_unavailable", "invalid_output") \
                    and self.repeats_left > 0 and attempt == 1:
                self.repeats_left -= 1
                attempt = 2
                continue
            raise End(code)

    def _call_once(self, role: str, role_input: dict, attempt: int):
        adapter = self.workflow.adapters[role]
        call_ms = (adapter.timeout_seconds + self.limits.role_grace_seconds) * 1000
        if self.role_invocations >= self.limits.max_role_invocations \
                or self.deadline.budget_ms("working", call_ms, call_ms) is None:
            raise End("budget_exhausted")
        slot = None
        if adapter.live:
            try:
                slot = self.svc.capacity.reserve_call()
            except CapacityExhausted:
                raise End("call_capacity_exhausted") from None
        run = AgentRun(
            id=uuid.uuid4(), scope=self.ctx.scope, case_id=self.record.case_id,
            case_revision=self.record.case_revision, role=role,
            principal_id=adapter.principal_id, config=adapter.config,
            tool_profile=self.workflow.tool_profile,
            input_snapshot_sha256=self.record.input_snapshot_sha256,
            budget=RunBudget(max_steps=1, max_tool_calls=ANALYST_FOLLOWUPS if role ==
                             "evidence_analyst" else INVESTIGATOR_FOLLOWUPS if role ==
                             "investigator" else 0, timeout_seconds=adapter.timeout_seconds,
                             max_delegations=0), status="running")
        try:
            self.hook(f"before_role:{role}")
            self.write(lambda tx: (tx.execute(
                "INSERT INTO agent_runs (id, tenant_id, session_id, case_id, status,"
                " started_at, body, workflow_id, attempt)"
                " VALUES (%s, %s, %s, %s, 'running', %s, %s, %s, %s)",
                (run.id, *_scope(self.ctx), run.case_id, self.svc.clock(),
                 Jsonb(run.model_dump(mode="json")), self.record.id, attempt)),
                self.step(tx, "role_started", _STATE[role], role=role, agent_run_id=run.id,
                          attempt=attempt)))
        except BaseException:
            if slot is not None:
                slot.cancel()
            raise
        self.role_invocations += 1
        # The start record (and anything before it) took time: the full call must still fit
        # in the working phase now, immediately before submission (R35). Otherwise nothing is
        # submitted, the reserved call slot is released, and the recorded attempt fails as
        # budget_exhausted with no usage.
        if self.deadline.budget_ms("working", call_ms, call_ms) is None:
            if slot is not None:
                slot.cancel()
            self._fail_run(run, role, attempt, "budget_exhausted", returned=True)
            raise End("budget_exhausted")
        result, failure, returned = None, None, True
        if slot is None:
            try:
                result = adapter.call(role_input)
            except InvestigatorError as error:
                failure = error.code if error.code in RUN_CODES else "provider_unavailable"
            except Exception:  # type only; messages may carry provider output
                failure = "provider_unavailable"
        else:
            abandoned = {"flag": False}
            started_ms = self.deadline.clock()

            def on_return(done, role=role, attempt=attempt):
                if abandoned["flag"]:
                    late = (self.deadline.clock() - started_ms - call_ms) / 1000
                    late_worker_event(str(self.record.id), role, attempt, max(0.0, late))
            future = slot.start(adapter.call, role_input, on_return=on_return)
            try:  # never past the working phase, which the recheck above showed fits call_ms
                wait_ms = min(call_ms, self.deadline.available_ms("working"))
                result = future.result(timeout=max(wait_ms, 0) / 1000)
            except futures.TimeoutError:
                abandoned["flag"] = True
                failure, returned = "timeout", False
            except InvestigatorError as error:
                failure = error.code if error.code in RUN_CODES else "provider_unavailable"
            except Exception:
                failure = "provider_unavailable"
        output = None
        if failure is None:
            try:
                output = TypeAdapter(role_adapters.OUTPUT_MODELS[role]).validate_python(
                    result.output)
            except ValidationError:
                failure = "invalid_output"
        if failure is not None:
            self._fail_run(run, role, attempt, failure, returned)
            return ("failed", failure, returned)
        done = AgentRun.model_validate({**run.model_dump(), "status": "completed"})
        payload = output.model_dump(mode="json")
        self.write(lambda tx: (tx.execute(
            "UPDATE agent_runs SET status = 'completed', finished_at = %s, body = %s"
            " WHERE id = %s AND status = 'running'",
            (self.svc.clock(), Jsonb(done.model_dump(mode="json")), run.id)),
            self.step(tx, "role_completed", _STATE[role], payload, role=role,
                      agent_run_id=run.id, attempt=attempt,
                      output_sha256=canonical_digest(STEP_NAMESPACE, payload),
                      usage=result.usage)))
        return ("ok", output, run.id)

    def _fail_run(self, run: AgentRun, role: str, attempt: int, failure: str,
                  returned: bool) -> None:
        failed = AgentRun.model_validate({**run.model_dump(), "status": "failed",
                                          "failure_code": failure})
        self.write(lambda tx: (tx.execute(
            "UPDATE agent_runs SET status = 'failed', finished_at = %s, body = %s"
            " WHERE id = %s AND status = 'running'",
            (self.svc.clock(), Jsonb(failed.model_dump(mode="json")), run.id)),
            self.step(tx, "role_failed", _STATE[role], role=role, agent_run_id=run.id,
                      attempt=attempt, failure_code=failure, worker_unresolved=not returned)))

    # ---- the state machine ----------------------------------------------------------------

    def execute(self) -> dict:
        """Run to a disposition, then the terminal transaction. Returns CaseDetail or raises
        the honest ServiceError (G3A-design section 3.2)."""
        try:
            disposition = self._decide()
        except End as end:
            disposition = self._inconclusive(end.code)
        except Superseded:
            raise _service_error("investigation_superseded") from None
        except BudgetExhausted:
            disposition = self._inconclusive("budget_exhausted")
        except ConnectionLost:  # terminate() replaces the connection under the terminal rules
            disposition = self._inconclusive("coordinator_error")
        except Exception as error:  # an unexpected server-side error: type only
            LOG.warning('{"event": "workflow_error", "error_type": "%s"}',
                        type(error).__name__)
            disposition = self._inconclusive("coordinator_error")
        return self.terminate(disposition)

    def _inconclusive(self, code: str) -> Disposition:
        return Disposition(kind="inconclusive", inconclusive_code=code,
                           supported_claims=self.claims_supported,
                           unsupported_claims=self.claims_unsupported)

    def _decide(self) -> Disposition:
        self.advance("gathering")
        self.tools(BASELINE_TOOLS, "gathering", len(BASELINE_TOOLS))
        self.advance("analyst")
        analyst, _ = self.invoke("evidence_analyst", self.role_input(
            "evidence_analyst", tool_requests_allowed=ANALYST_FOLLOWUPS))
        analyst_checks = check_all(analyst.claims, self.ledger)
        if analyst.tool_requests:
            self.advance("analyst_tools")
        self.tools(analyst.tool_requests, "analyst_tools", ANALYST_FOLLOWUPS)
        analyst_view = {"claims": [c.model_dump(mode="json") for c in analyst.claims],
                        "checks": [k.model_dump(mode="json") for k in analyst_checks],
                        "missing": list(analyst.missing)}
        challenge = None
        investigator_tools_used = False
        while True:
            self.advance("investigator")
            investigator, run_id = self.invoke("investigator", self.role_input(
                "investigator", analyst=analyst_view, challenge=challenge,
                tool_requests_allowed=0 if investigator_tools_used else INVESTIGATOR_FOLLOWUPS))
            if investigator.tool_requests and not investigator_tools_used \
                    and self.revisions_left > 0:
                investigator_tools_used = True
                self.revisions_left -= 1
                self.advance("investigator_tools")
                self.tools(investigator.tool_requests, "investigator_tools",
                           INVESTIGATOR_FOLLOWUPS)
                continue
            self.completed_investigator_run = run_id
            checks = check_all(investigator.claims, self.ledger)
            problems = policy_problems(investigator, checks)
            self.claims_supported = sum(k.status == "supported" for k in checks)
            self.claims_unsupported = len(checks) - self.claims_supported
            self.advance("verifying")
            self.write(lambda tx: self.step(tx, "claims_checked", "verifying", checks=checks))
            self.advance("reviewer")
            reviewer, _ = self.invoke("reviewer", self.role_input(
                "reviewer", investigator={
                    "operation": investigator.operation, "reason_code": investigator.reason_code,
                    "claims": [c.model_dump(mode="json") for c in investigator.claims],
                    "checks": [k.model_dump(mode="json") for k in checks],
                    "problems": problems},
                revision_available=self.revisions_left > 0))
            if reviewer.verdict == "accept" and not problems:
                self.adopted = (investigator, checks, "accept")
                return Disposition(kind="recommend", operation=investigator.operation,
                                   reason_code=investigator.reason_code, basis_run_id=run_id,
                                   supported_claims=self.claims_supported,
                                   unsupported_claims=0)
            if reviewer.verdict != "abstain" and self.revisions_left > 0:
                self.revisions_left -= 1
                challenge = {"challenged_claims": list(reviewer.challenged_claims),
                             "reasons": sorted(set(reviewer.reasons) | set(problems))}
                continue
            self.adopted = (investigator, checks, reviewer.verdict)
            return Disposition(kind="abstain", operation="escalate",
                               reason_code="insufficient_evidence", basis_run_id=run_id,
                               supported_claims=self.claims_supported,
                               unsupported_claims=self.claims_unsupported)

    # ---- terminal -------------------------------------------------------------------------

    def terminate(self, disposition: Disposition) -> dict:
        self.hook("before_terminal")
        try:
            tx = BoundedTransaction(self.connection("terminal"), self.deadline, "terminal",
                                    self.db_wait_ms)
        except (BudgetExhausted, ConnectionLost):
            raise _service_error("investigation_in_progress") from None
        try:
            adopted = getattr(self, "adopted", None)
            terminate_workflow(self.svc, tx, self.ctx, self.record.id, disposition,
                               "coordinator", self.workflow, adopted, self.facts)
            detail = self.svc._case_detail(tx, self.ctx, self.record.case_id)
            self.hook("before_terminal_commit")
            tx.commit()
        except Superseded:
            tx.rollback()
            raise _service_error("investigation_superseded") from None
        except (BudgetExhausted, ConnectionLost):
            raise _service_error("investigation_in_progress") from None
        except CommitUncertain:
            raise _service_error("investigation_outcome_unknown") from None
        except BaseException:
            tx.rollback()
            raise
        return detail


_STATE = {"evidence_analyst": "analyst", "investigator": "investigator", "reviewer": "reviewer"}


def _scope(ctx):
    return ctx.scope.tenant_id, ctx.scope.session_id


def terminate_workflow(svc, tx, ctx, workflow_id, disposition: Disposition, terminal_by: str,
                       workflow: Workflow | None, adopted, facts) -> Disposition:
    """The one terminal transaction (G3A-design section 6.1); `tx` is bounded."""
    from sentinel.service import SYSTEM_ACTOR
    found = tx.execute("SELECT case_id FROM agent_workflows WHERE id = %s AND tenant_id = %s"
                       " AND session_id = %s", (workflow_id, *_scope(ctx))).fetchone()
    if found is None:
        raise Superseded()
    case = svc._case(tx, ctx, found["case_id"], lock=True)  # lock order: case, then workflow
    row = tx.execute("SELECT body FROM agent_workflows WHERE id = %s FOR UPDATE",
                     (workflow_id,)).fetchone()
    record = WorkflowRecord.model_validate(row["body"])
    if record.status != "running" or case.state != "investigating" \
            or case.revision != record.case_revision:
        raise Superseded()
    now = svc.clock()
    if disposition.kind != "inconclusive":
        problem = None
        evidence = tuple(EvidenceItem.model_validate(body)
                         for body in svc._rows(tx, ctx, "evidence_items", case.id))
        try:
            require_evidence_snapshot(ctx, case, evidence, now)
        except ContractViolation:
            problem = "stale_evidence_snapshot"
        basis = tx.execute(
            "SELECT id FROM agent_runs WHERE workflow_id = %s AND body->>'role' = 'investigator'"
            " AND status = 'completed' ORDER BY seq DESC LIMIT 1", (workflow_id,)).fetchone()
        if problem is None and (basis is None or basis["id"] != disposition.basis_run_id):
            problem = "coordinator_error"
        if problem is not None:
            disposition = Disposition(kind="inconclusive", inconclusive_code=problem,
                                      supported_claims=disposition.supported_claims,
                                      unsupported_claims=disposition.unsupported_claims)
    running = tx.execute("SELECT body FROM agent_runs WHERE workflow_id = %s"
                         " AND status = 'running'", (workflow_id,)).fetchone()
    if running is not None:
        code = disposition.inconclusive_code
        code = code if code in RUN_CODES else "timeout" if terminal_by == "recovery" \
            else "budget_exhausted"
        failed = AgentRun.model_validate({**running["body"], "status": "failed",
                                          "failure_code": code})
        tx.execute("UPDATE agent_runs SET status = 'failed', finished_at = %s, body = %s"
                   " WHERE id = %s AND status = 'running'",
                   (now, Jsonb(failed.model_dump(mode="json")), failed.id))
    counts = tx.execute(
        "SELECT (SELECT count(*) FROM agent_runs WHERE workflow_id = %s) AS roles,"
        " (SELECT count(*) FROM agent_steps WHERE workflow_id = %s"
        "  AND body->>'kind' = 'tool_executed') AS tools,"
        " (SELECT coalesce(max(step_seq), 0) FROM agent_steps WHERE workflow_id = %s) AS seq",
        (workflow_id, workflow_id, workflow_id)).fetchone()
    status = "inconclusive" if disposition.kind == "inconclusive" else "completed"
    final = WorkflowRecord.model_validate({
        **record.model_dump(), "status": status, "finished_at": now, "terminal_by": terminal_by,
        "role_invocations": counts["roles"], "tool_calls": counts["tools"],
        "disposition": disposition})
    updated = tx.execute(
        "UPDATE agent_workflows SET status = %s, finished_at = %s, terminal_by = %s, body = %s"
        " WHERE id = %s AND status = 'running'",
        (status, now, terminal_by, Jsonb(final.model_dump(mode="json")), workflow_id))
    if updated.rowcount != 1:
        raise Superseded()
    if disposition.kind == "inconclusive":
        nxt = svc._transition(tx, case, "open", now)
    else:
        nxt = svc._transition(tx, case, "awaiting_approval", now)
        investigator, checks, verdict = adopted
        finding = InvestigationFinding(
            operation=disposition.operation, reason_code=disposition.reason_code,
            rationale=render_rationale(disposition.kind, disposition.operation,
                                       disposition.reason_code, investigator.claims, checks,
                                       facts.txn.amount.currency, verdict))
        tx.execute("UPDATE agent_runs SET finding = %s WHERE id = %s",
                   (Jsonb(finding.model_dump(mode="json")), disposition.basis_run_id))
        svc._build_intent(tx, ctx, nxt, disposition.basis_run_id, finding)
    step = StepRecord(workflow_id=workflow_id, seq=min(64, counts["seq"] + 1),
                      kind="workflow_terminated", state="done", elapsed_ms=0,
                      usage=NOT_APPLICABLE, at=now)
    body = step.model_dump(mode="json")
    tx.execute("INSERT INTO agent_steps (id, tenant_id, session_id, workflow_id, case_id,"
               " step_seq, body, payload) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
               (uuid.uuid4(), *_scope(ctx), workflow_id, case.id, step.seq, Jsonb(body),
                Jsonb(final.model_dump(mode="json"))))
    if terminal_by == "coordinator":
        actor, kind = workflow.principal_id, "agent"
    else:
        actor, kind = SYSTEM_ACTOR, "system"
    svc._audit(tx, ctx, nxt, uuid.uuid4(), actor, kind, "investigation_completed",
               "failure" if disposition.kind == "inconclusive" else "success", now)
    return disposition


def running_workflow(conn, ctx, case_id):
    return conn.execute("SELECT id, deadline_at FROM agent_workflows WHERE case_id = %s"
                        " AND tenant_id = %s AND session_id = %s AND status = 'running'",
                        (case_id, *_scope(ctx))).fetchone()


def recover_workflow(svc, tx, ctx, case: Case, now) -> bool | None:
    """Lazy recovery of a running workflow past deadline_at + RECOVERY_GRACE, inside an owned
    BoundedTransaction that holds the case lock and is committed by its own bounded COMMIT
    (the claim's, or recover_workflow_bounded's). Returns None when the case has no running
    workflow, False when it is not yet recoverable."""
    from sentinel.service import RECOVERY_GRACE
    row = running_workflow(tx, ctx, case.id)
    if row is None:
        return None
    if not isinstance(tx, BoundedTransaction):  # begin_investigation defers these instead
        raise TypeError("a workflow is recovered only inside a bounded transaction")
    if row["deadline_at"] + RECOVERY_GRACE >= now:
        return False
    terminate_workflow(svc, tx, ctx, row["id"],
                       Disposition(kind="inconclusive", inconclusive_code="interrupted",
                                   supported_claims=0, unsupported_claims=0),
                       "recovery", None, None, None)
    return True


def recover_workflow_bounded(svc, ctx, case_id) -> bool:
    """Recovery requested outside the coordinator (Sentinel.begin_investigation, after its
    own transaction released the case): a fresh connection and one owned terminal
    transaction under a fresh db_wait budget, re-checked under the case lock. True when it
    committed; False when the workflow is not recoverable yet, or the attempt was refused or
    known rolled back; an unanswered COMMIT is investigation_outcome_unknown."""
    from sentinel.service import ServiceError
    limits = WorkflowLimits()
    fresh = Deadline(limits, svc.monotonic, total_ms=limits.db_wait_seconds * 1000,
                     reserve_ms=0)
    try:
        conn = open_connection(svc.database_url, fresh, "terminal", limits)
    except (BudgetExhausted, ConnectionLost):
        return False
    try:
        tx = BoundedTransaction(conn, fresh, "terminal", limits.db_wait_seconds * 1000)
        try:
            case = svc._case(tx, ctx, case_id, lock=True)
            recovered = case.state == "investigating" and \
                recover_workflow(svc, tx, ctx, case, svc.clock())
            if not recovered:
                tx.rollback()
                return False
            tx.commit()
            return True
        except Superseded:
            tx.rollback()
            return False
        except (BudgetExhausted, ConnectionLost):
            return False
        except CommitUncertain:
            raise ServiceError("investigation_outcome_unknown", 409) from None
        except BaseException:
            tx.rollback()
            raise
    except BudgetExhausted:
        return False
    finally:
        discard(conn)


def run_workflow(svc, ctx, case_id, expected_revision: int, hooks: dict | None = None) -> dict:
    """Entry point from Sentinel.investigate under SENTINEL_INVESTIGATOR=three-role."""
    from sentinel.service import ServiceError, _require
    _require(ctx, "read_case", human=True)
    workflow: Workflow = svc.investigator
    # Abandoned database operations hold their connections and threads until they return;
    # while they reach the per-process workflow limit, nothing new is admitted (R34).
    if QUARANTINE.count() >= workflow.limits.max_live_workflows_per_process:
        raise ServiceError("agent_capacity_exhausted", 409)
    try:
        admission = svc.capacity.admit(workflow.live)
    except CapacityExhausted:
        raise ServiceError("agent_capacity_exhausted", 409) from None
    try:
        deadline = Deadline(workflow.limits, svc.monotonic)
        try:
            conn = open_connection(svc.database_url, deadline, "working", workflow.limits)
        except (BudgetExhausted, ConnectionLost):
            raise ServiceError("conflict", 409) from None
        run = Run(svc, ctx, workflow, deadline, conn, hooks or {}, opened=[conn])
        try:
            run.claim(case_id, expected_revision)
            return run.execute()
        finally:
            for connection in run.opened:
                discard(connection)
    finally:
        admission.release()
