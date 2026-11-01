"""HTTP v1.2 response bodies (G3C-A): the read-only investigation trace.

Additive to v1.1; see docs/api/investigation-trace-v1.2.md. Nested agent records reuse the
frozen agents-1.0 models unchanged. Every field is projected from stored records; unknown
values are null, never zero, and nothing here grants a permission or performs an action.
"""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import AwareDatetime, Field

from sentinel.contracts.agents import (
    ClaimCheck, Disposition, FailureCode, InconclusiveCode, Role, RoleOutput, ToolName,
    ToolResult, Usage, WorkflowLimits,
)
from sentinel.contracts.http_v1 import CaseState, HttpBody
from sentinel.contracts.v1 import ArtifactRef, Digest, Id, InvestigationFinding

MAX_LISTED_WORKFLOWS = 25
WorkflowStatus = Literal["running", "completed", "inconclusive"]
Count = Annotated[int, Field(ge=0)]


class WorkflowSummary(HttpBody):
    id: Id
    case_revision: int
    status: WorkflowStatus
    terminal_by: Literal["coordinator", "recovery"] | None
    started_at: AwareDatetime
    deadline_at: AwareDatetime
    finished_at: AwareDatetime | None
    disposition_kind: Literal["recommend", "abstain", "inconclusive"] | None
    inconclusive_code: InconclusiveCode | None


class WorkflowView(HttpBody):
    id: Id
    case_revision: int
    status: WorkflowStatus
    terminal_by: Literal["coordinator", "recovery"] | None
    started_at: AwareDatetime
    deadline_at: AwareDatetime
    finished_at: AwareDatetime | None
    config: ArtifactRef
    tool_profile: ArtifactRef
    input_snapshot_sha256: Digest
    disposition: Disposition | None
    recorded_role_invocations: Count | None = Field(description=(
        "The terminal record's counter; null while running (not yet recorded, not zero)."))
    recorded_tool_calls: Count | None = Field(description=(
        "Executed tool calls in the terminal record; null while running."))
    deadline_status: Literal["before_deadline", "past_deadline", "recovery_due"] | None = Field(
        description="Running workflows only, relative to read_at. recovery_due is not "
                    "recovery: the workflow stays running until an investigation request "
                    "recovers it.")


class RoleAttempt(HttpBody):
    """One recorded role attempt (a role_started step and its agent_runs row). Not a
    provider call: a failed attempt may never have been submitted."""
    agent_run_id: Id
    role: Role
    attempt: Annotated[int, Field(ge=1, le=2)]
    status: Literal["queued", "running", "completed", "failed", "inconclusive", "cancelled"] = (
        Field(description="The stored AgentRun status; G3B writes running, completed and "
                          "failed."))
    failure_code: FailureCode | None
    failure_source: Literal["role_step", "workflow_terminal"] | None
    worker_unresolved: bool | None = Field(description="From the role_failed step; null "
                                           "when no such step was recorded.")
    started_at: AwareDatetime
    finished_at: AwareDatetime | None
    config: ArtifactRef
    output: RoleOutput | None = Field(description=(
        "Coordinator-validated untrusted role output; notes are inert display text."))
    output_sha256: Digest | None
    claim_checks: Annotated[list[ClaimCheck], Field(max_length=12)] | None = Field(
        description="Server checks recorded for this attempt's claims; null if none was "
                    "recorded (analyst checks are not persisted).")
    elapsed_ms: Count | None = Field(description=(
        "Coordinator time from the role_started step to its end step, including "
        "persistence; not provider latency. Null without a recorded end step."))
    usage: Usage | None = Field(description=(
        "Adapter-reported usage from role_completed; null means none was recorded "
        "(unknown, not zero)."))
    basis: bool
    finding: InvestigationFinding | None = Field(description=(
        "Server-rendered finding of the basis run; render rationale as inert text."))


class TraceStep(HttpBody):
    """A persisted StepRecord without workflow_id and usage."""
    seq: Annotated[int, Field(ge=1, le=64)]
    kind: Literal["transition", "role_started", "role_completed", "role_failed",
                  "tool_executed", "tool_denied", "claims_checked", "workflow_terminated"]
    state: Literal["claimed", "gathering", "analyst", "analyst_tools", "investigator",
                   "investigator_tools", "reviewer", "verifying", "done"]
    role: Role | None
    agent_run_id: Id | None
    attempt: int | None
    tool: ToolName | None
    tool_result_id: Id | None
    output_sha256: Digest | None
    checks: Annotated[list[ClaimCheck], Field(max_length=12)]
    failure_code: FailureCode | None
    worker_unresolved: bool
    elapsed_ms: Count
    at: AwareDatetime


class UsageSummary(HttpBody):
    """Adapter-reported token counts for this workflow; not provider billing."""
    reported_attempts: Count
    not_applicable_attempts: Count
    unknown_attempts: Count = Field(description="Usage unknown or not recorded.")
    input_tokens: Count | None = Field(description="Sum over reported attempts; null if none.")
    output_tokens: Count | None


class WorkflowTrace(HttpBody):
    workflow: WorkflowView
    limits: WorkflowLimits | None = Field(description=(
        "Pinned limits, only when this server's three-role config has the stored config "
        "digest; else null (unknown). *_per_process limits are this API process's "
        "admission limits, not provider-wide."))
    attempts: Annotated[list[RoleAttempt], Field(max_length=64)]
    steps: Annotated[list[TraceStep], Field(max_length=64)]
    tool_results: Annotated[list[ToolResult], Field(max_length=64)]
    usage_summary: UsageSummary


class InvestigationTrace(HttpBody):
    case_id: Id
    case_state: CaseState
    case_revision: int
    read_at: AwareDatetime
    legacy_investigator_runs: Count = Field(description=(
        "Runs of the single investigator (no workflow); listed in CaseDetail.agent_runs."))
    workflow_count: Count
    workflows: Annotated[list[WorkflowSummary], Field(max_length=MAX_LISTED_WORKFLOWS)] = Field(
        description="Newest first (highest case_revision), at most 25.")
    selected: WorkflowTrace | None = Field(description=(
        "The newest workflow, or the one named by workflow_id; null when the case has no "
        "workflow."))
