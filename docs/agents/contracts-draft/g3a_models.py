"""G3A draft contracts for the three-role investigation workflow (proposal, not frozen).

These models are a design artifact under docs/: nothing in src/ imports them. G3B copies the
accepted shapes into src/sentinel/contracts/agents.py (see docs/agents/G3B-implementation-plan.md).
They reuse the frozen v1 primitives so identity, digests and timestamps keep one meaning.

Run from the repository root to regenerate or check the schemas and examples:

    uv run --locked python docs/agents/contracts-draft/g3a_models.py --check
    uv run --locked python docs/agents/contracts-draft/g3a_models.py --write

Trust model: every model named *Output is untrusted role output. It names enumerated tools,
fact keys and evidence references only; it never carries tenant/session/actor/case ids,
credentials, SQL, paths or URLs. The coordinator assigns identity, executes tools, verifies
claims against stored values and builds any action intent itself.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated, Literal, Union

from pydantic import (
    BaseModel, ConfigDict, Field, StrictBool, StrictInt, ValidationError, model_validator,
)

from sentinel.contracts.v1 import ArtifactRef, Digest, Id, Revision, Timestamp

HERE = Path(__file__).resolve().parent
SCHEMA_VERSION = "g3a-draft-1"

# ---- shared vocabulary ------------------------------------------------------------------

Role = Literal["evidence_analyst", "investigator", "reviewer"]
# Server-derived fact keys a claim may cite. Each maps to exactly one stored value source
# (EvidenceItem fact, ScoringOutcome field/inputs, or a recorded tool result field).
FactKey = Literal[
    "amount_minor", "transaction_count_1h", "large_amount_rule_hit",
    "history_count_24h", "history_count_7d", "history_median_amount_minor_30d",
    "history_max_amount_minor_30d", "account_age_days", "prior_known_fraud",
]
ToolName = Literal["case_evidence", "scoring_outcome", "account_history", "account_profile"]
HistoryWindow = Literal["24h", "7d", "30d"]
ReasonCode = Literal["velocity_pattern", "unusual_amount", "insufficient_evidence"]
Operation = Literal["simulated_hold", "escalate"]
NoteText = Annotated[str, Field(min_length=1, max_length=400)]
FailureCode = Literal["provider_unavailable", "timeout", "invalid_output", "budget_exhausted"]


class Draft(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    schema_version: Literal["g3a-draft-1"] = SCHEMA_VERSION


# ---- tools (read-only; the server injects scope, case and account) ----------------------

class CaseEvidenceArgs(Draft):
    tool: Literal["case_evidence"]


class ScoringOutcomeArgs(Draft):
    tool: Literal["scoring_outcome"]


class AccountHistoryArgs(Draft):
    tool: Literal["account_history"]
    window: HistoryWindow


class AccountProfileArgs(Draft):
    tool: Literal["account_profile"]


ToolRequest = Annotated[
    Union[CaseEvidenceArgs, ScoringOutcomeArgs, AccountHistoryArgs, AccountProfileArgs],
    Field(discriminator="tool"),
]


class ToolResult(Draft):
    """Server-produced, digest-addressed. `values` hold only FactKey -> integer/bool values
    computed from records available at the case decision time (alert.created_at)."""
    id: Id
    tool: ToolName
    window: HistoryWindow | None = None
    status: Literal["ok", "unavailable", "denied"]
    denial: Literal["unknown_tool", "budget_exhausted", "not_in_profile", "schema_rejected"] | None = None
    values: dict[FactKey, StrictInt | StrictBool] = Field(default_factory=dict)
    evidence_ids: Annotated[tuple[Id, ...], Field(max_length=32)] = ()
    as_of: Timestamp
    content_sha256: Digest

    @model_validator(mode="after")
    def status_fields(self):
        if (self.status == "denied") != (self.denial is not None):
            raise ValueError("a denied result (only) carries a denial code")
        if self.status != "ok" and self.values:
            raise ValueError("only an ok result carries values")
        if (self.tool == "account_history") != (self.window is not None):
            raise ValueError("window is required for account_history only")
        return self


# ---- claims (checked by the server against stored values) -------------------------------

class Citation(Draft):
    kind: Literal["evidence", "tool_result"]
    id: Id


class FactClaim(Draft):
    """`fact` relation `value`, cited to where the server can read that exact value."""
    kind: Literal["fact"]
    fact: FactKey
    relation: Literal["eq", "gte", "lte"]
    value: StrictInt | StrictBool
    cite: Citation


class MissingEvidenceClaim(Draft):
    """The role says this fact was not available; the server checks that it really was not."""
    kind: Literal["missing"]
    fact: FactKey


Claim = Annotated[Union[FactClaim, MissingEvidenceClaim], Field(discriminator="kind")]
Claims = Annotated[tuple[Claim, ...], Field(max_length=12)]


# ---- role outputs (untrusted) -----------------------------------------------------------

class AnalystOutput(Draft):
    role: Literal["evidence_analyst"]
    claims: Claims
    missing: Annotated[tuple[FactKey, ...], Field(max_length=8)] = ()
    tool_requests: Annotated[tuple[ToolRequest, ...], Field(max_length=4)] = ()
    note: NoteText | None = None  # display-only; never forwarded to another role


class InvestigatorOutput(Draft):
    role: Literal["investigator"]
    operation: Operation
    reason_code: ReasonCode
    claims: Annotated[tuple[Claim, ...], Field(min_length=1, max_length=12)]
    tool_requests: Annotated[tuple[ToolRequest, ...], Field(max_length=2)] = ()
    note: NoteText | None = None


class ReviewerOutput(Draft):
    role: Literal["reviewer"]
    verdict: Literal["accept", "challenge", "abstain"]
    challenged_claims: Annotated[tuple[StrictInt, ...], Field(max_length=12)] = ()
    reasons: Annotated[tuple[Literal[
        "unsupported_claim", "contradiction", "missing_evidence", "reason_mismatch",
        "operation_not_supported"], ...], Field(max_length=5)] = ()
    note: NoteText | None = None


RoleOutput = Annotated[Union[AnalystOutput, InvestigatorOutput, ReviewerOutput],
                       Field(discriminator="role")]


# ---- server-side records ----------------------------------------------------------------

class ClaimCheck(Draft):
    index: StrictInt
    status: Literal["supported", "unsupported", "uncheckable"]
    reason: Literal["value_mismatch", "citation_not_in_scope", "fact_not_in_cited_record",
                    "fact_was_available", "verified"]


class WorkflowLimits(Draft):
    """Pinned hard limits. Times are provisional, unmeasured defaults (review decision 2)."""
    max_role_invocations: Annotated[StrictInt, Field(ge=1, le=8)] = 5
    max_transitions: Annotated[StrictInt, Field(ge=1, le=24)] = 12
    max_followup_tool_calls: Annotated[StrictInt, Field(ge=0, le=6)] = 3
    max_investigator_revisions: Annotated[StrictInt, Field(ge=0, le=1)] = 1
    # Repeats only a call whose worker already returned (provider_unavailable/invalid_output);
    # never a timed-out call, whose worker is still unresolved (R31).
    max_repeats: Annotated[StrictInt, Field(ge=0, le=1)] = 1
    role_timeout_seconds: Annotated[StrictInt, Field(ge=1, le=60)] = 45
    role_grace_seconds: Annotated[StrictInt, Field(ge=0, le=5)] = 2
    workflow_deadline_seconds: Annotated[StrictInt, Field(ge=1, le=170)] = 150
    # Kept free at every role/tool start, so the terminal transaction fits the deadline.
    terminal_reserve_seconds: Annotated[StrictInt, Field(ge=1, le=10)] = 5
    # Bounds every connection, lock and statement wait the coordinator or a tool makes.
    db_wait_seconds: Annotated[StrictInt, Field(ge=1, le=10)] = 5
    tool_statement_timeout_ms: Annotated[StrictInt, Field(ge=100, le=5000)] = 2000
    max_live_workflows_per_process: Annotated[StrictInt, Field(ge=1, le=4)] = 1
    # Provider-call worker threads alive in this process, including late (timed-out) ones.
    max_outstanding_calls_per_process: Annotated[StrictInt, Field(ge=1, le=4)] = 2

    @model_validator(mode="after")
    def coherent(self):
        if self.workflow_deadline_seconds < (self.role_timeout_seconds + self.role_grace_seconds
                                             + self.terminal_reserve_seconds):
            raise ValueError("the deadline must fit one full role call plus the terminal reserve")
        if self.max_outstanding_calls_per_process < self.max_live_workflows_per_process:
            raise ValueError("every admitted workflow needs at least one call slot")
        return self


REQUIRED_ROLES = frozenset({"evidence_analyst", "investigator", "reviewer"})


class WorkflowConfig(Draft):
    """Content-addressed composite; its ArtifactRef is pinned as Case.pins.agent_config."""
    kind: Literal["three-role"]
    roles: dict[Role, ArtifactRef]
    tool_profile: ArtifactRef
    claim_schema: Literal["g3a-draft-1"]
    limits: WorkflowLimits

    @model_validator(mode="after")
    def exact_roles(self):
        if set(self.roles) != REQUIRED_ROLES:
            raise ValueError("exactly the evidence_analyst, investigator and reviewer roles")
        return self


class Usage(Draft):
    """What the adapter actually measured; unknown is explicit, never zero (decision 4).
    not_applicable (server tools, transitions) and unknown carry no counts and measured=False;
    adapter_reported carries both validated counts and measured=True."""
    measured: StrictBool
    input_tokens: Annotated[StrictInt, Field(ge=0)] | None = None
    output_tokens: Annotated[StrictInt, Field(ge=0)] | None = None
    source: Literal["not_applicable", "adapter_reported", "unknown"]

    @model_validator(mode="after")
    def coherent(self):
        counts = (self.input_tokens is not None, self.output_tokens is not None)
        if self.source == "adapter_reported":
            if not self.measured or counts != (True, True):
                raise ValueError("reported usage is measured and carries both counts")
        elif self.measured or any(counts):
            raise ValueError("unmeasured usage carries no counts")
        return self


class StepRecord(Draft):
    """One append-only coordinator event (proposed table agent_steps)."""
    workflow_id: Id
    seq: Annotated[StrictInt, Field(ge=1, le=64)]
    kind: Literal["transition", "role_started", "role_completed", "role_failed",
                  "tool_executed", "tool_denied", "claims_checked", "workflow_terminated"]
    state: Literal["claimed", "gathering", "analyst", "analyst_tools", "investigator",
                   "investigator_tools", "reviewer", "verifying", "done"]
    role: Role | None = None
    agent_run_id: Id | None = None
    attempt: Annotated[StrictInt, Field(ge=1, le=2)] | None = None
    tool: ToolName | None = None
    tool_result_id: Id | None = None
    output_sha256: Digest | None = None
    checks: Annotated[tuple[ClaimCheck, ...], Field(max_length=12)] = ()
    failure_code: FailureCode | None = None
    # A timed-out call's worker thread had not returned when the coordinator stopped waiting.
    worker_unresolved: StrictBool = False
    elapsed_ms: Annotated[StrictInt, Field(ge=0)]
    usage: Usage
    at: Timestamp

    @model_validator(mode="after")
    def coherent(self):
        if self.worker_unresolved and (self.kind, self.failure_code) != ("role_failed",
                                                                         "timeout"):
            raise ValueError("only a timed-out role call can leave its worker unresolved")
        if (self.kind == "role_failed") != (self.failure_code is not None):
            raise ValueError("a role_failed step (only) carries a failure code")
        return self


InconclusiveCode = Literal[
    "provider_unavailable", "timeout", "invalid_output", "budget_exhausted",
    "stale_evidence_snapshot", "call_capacity_exhausted", "coordinator_error", "interrupted",
]


class Disposition(Draft):
    """Coordinator outcome. recommend/abstain produce exactly one server-built intent whose
    basis is a completed investigator run of the same workflow (a coordinator check);
    inconclusive produces none and reopens the case (review decision 3)."""
    kind: Literal["recommend", "abstain", "inconclusive"]
    operation: Operation | None = None
    reason_code: ReasonCode | None = None
    basis_run_id: Id | None = None
    inconclusive_code: InconclusiveCode | None = None
    supported_claims: Annotated[StrictInt, Field(ge=0)]
    unsupported_claims: Annotated[StrictInt, Field(ge=0)]

    @model_validator(mode="after")
    def consistent(self):
        if self.kind == "inconclusive":
            if (self.operation or self.reason_code or self.basis_run_id
                    or self.inconclusive_code is None):
                raise ValueError("inconclusive: no operation or basis, a typed code")
        elif self.basis_run_id is None or self.inconclusive_code is not None:
            raise ValueError("recommend/abstain: a basis run and no inconclusive code")
        if self.kind == "recommend" and (self.operation is None or self.reason_code is None
                                         or self.unsupported_claims):
            raise ValueError("recommend: operation and reason, every adopted claim supported")
        if self.kind == "abstain" and (self.operation, self.reason_code) != (
                "escalate", "insufficient_evidence"):
            raise ValueError("abstain is always escalate/insufficient_evidence")
        return self


class WorkflowRecord(Draft):
    """Proposed table agent_workflows: one row per coordinator attempt on a case.

    running: no finish, disposition or terminal actor. completed: finished, recommend or
    abstain, by the coordinator, after at least analyst, investigator and reviewer.
    inconclusive: finished, an inconclusive disposition, by the coordinator or by recovery;
    recovery (no live coordinator) always records `interrupted`. Zero role invocations is a
    valid inconclusive record (exhaustion before the first role)."""
    id: Id
    case_id: Id
    case_revision: Revision
    config: ArtifactRef
    tool_profile: ArtifactRef
    input_snapshot_sha256: Digest
    status: Literal["running", "completed", "inconclusive"]
    started_at: Timestamp
    deadline_at: Timestamp
    finished_at: Timestamp | None = None
    terminal_by: Literal["coordinator", "recovery"] | None = None
    role_invocations: Annotated[StrictInt, Field(ge=0, le=8)]
    tool_calls: Annotated[StrictInt, Field(ge=0, le=12)]
    disposition: Disposition | None = None

    @model_validator(mode="after")
    def lifecycle(self):
        if self.deadline_at <= self.started_at:
            raise ValueError("deadline must follow start")
        if self.finished_at is not None and self.finished_at < self.started_at:
            raise ValueError("finish precedes start")
        terminal = (self.finished_at, self.disposition, self.terminal_by)
        if self.status == "running":
            if any(value is not None for value in terminal):
                raise ValueError("a running workflow has no finish, disposition or actor")
            return self
        if any(value is None for value in terminal):
            raise ValueError("a terminal workflow needs finish time, disposition and actor")
        kind = self.disposition.kind
        if self.status == "completed":
            if kind == "inconclusive" or self.terminal_by != "coordinator":
                raise ValueError("completed: a recommend/abstain disposition by the coordinator")
            if self.role_invocations < 3:
                raise ValueError("completed needs the analyst, investigator and reviewer")
        elif kind != "inconclusive":
            raise ValueError("inconclusive status needs an inconclusive disposition")
        elif (self.terminal_by == "recovery") != (self.disposition.inconclusive_code
                                                  == "interrupted"):
            raise ValueError("recovery (only) records an interrupted workflow")
        return self


class TraceRole(Draft):
    role: Role
    agent_run_id: Id
    attempt: StrictInt
    status: Literal["running", "completed", "failed", "inconclusive", "cancelled"]
    claims: Claims = ()
    checks: Annotated[tuple[ClaimCheck, ...], Field(max_length=12)] = ()
    verdict: Literal["accept", "challenge", "abstain"] | None = None
    note: NoteText | None = Field(default=None, description="Untrusted; render as inert text.")


class TraceSummary(Draft):
    """Proposed additive v1.2 read model (G3C); not required by the G3B slice."""
    workflow: WorkflowRecord
    roles: Annotated[tuple[TraceRole, ...], Field(max_length=8)]
    tool_results: Annotated[tuple[ToolResult, ...], Field(max_length=12)]


EXPORTS = {
    "ToolRequest": ToolRequest, "ToolResult": ToolResult, "Claim": Claim,
    "AnalystOutput": AnalystOutput, "InvestigatorOutput": InvestigatorOutput,
    "ReviewerOutput": ReviewerOutput, "RoleOutput": RoleOutput, "ClaimCheck": ClaimCheck,
    "WorkflowConfig": WorkflowConfig, "StepRecord": StepRecord, "Disposition": Disposition,
    "WorkflowRecord": WorkflowRecord, "TraceSummary": TraceSummary, "Usage": Usage,
    "WorkflowLimits": WorkflowLimits,
}


def schemas() -> dict[str, dict]:
    from pydantic import TypeAdapter
    return {name: TypeAdapter(model).json_schema() for name, model in EXPORTS.items()}


def check_examples() -> list[str]:
    """Every examples/valid/<Model>.*.json validates; every examples/invalid/<Model>.*.json
    is rejected. Returns problems (empty means consistent)."""
    from pydantic import TypeAdapter
    problems = []
    for expected in ("valid", "invalid"):
        files = sorted((HERE / "examples" / expected).glob("*.json"))
        if not files:
            problems.append(f"no {expected} examples")
        for path in files:
            model = EXPORTS.get(path.name.split(".", 1)[0])
            if model is None:
                problems.append(f"{path.name}: unknown model prefix")
                continue
            try:
                TypeAdapter(model).validate_json(path.read_bytes())
                ok = True
            except ValidationError:
                ok = False
            if ok != (expected == "valid"):
                problems.append(f"{expected}/{path.name}: "
                                f"{'rejected' if expected == 'valid' else 'accepted'}")
    return problems


def main(argv: list[str]) -> int:
    target = HERE / "schemas"
    generated = {f"{name}.schema.json": json.dumps(schema, indent=2, sort_keys=True) + "\n"
                 for name, schema in schemas().items()}
    if argv == ["--write"]:
        target.mkdir(exist_ok=True)
        for name, text in generated.items():
            (target / name).write_text(text, encoding="utf-8", newline="\n")
    elif argv != ["--check"]:
        print("usage: g3a_models.py --check | --write")
        return 2
    stale = [name for name, text in generated.items()
             if not (target / name).is_file()
             or (target / name).read_text(encoding="utf-8") != text]
    extra = sorted(p.name for p in target.glob("*.json") if p.name not in generated)
    problems = [f"stale schema {n}" for n in stale] + [f"extra schema {n}" for n in extra]
    problems += check_examples()
    for problem in problems:
        print(problem)
    if not problems:
        valid = len(list((HERE / "examples" / "valid").glob("*.json")))
        invalid = len(list((HERE / "examples" / "invalid").glob("*.json")))
        print(f"{len(generated)} draft schemas current; {valid} valid and {invalid} invalid "
              "examples behave as labelled")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
