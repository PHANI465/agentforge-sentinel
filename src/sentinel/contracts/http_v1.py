"""HTTP v1 response bodies. Domain records reuse the v1 contracts; these wrappers fix the
envelope shapes the analyst UI consumes. See docs/api/README.md and contracts/http/.

Responses never carry bearer tokens, credentials, provider account details or raw inputs.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from sentinel.contracts.v1 import (
    ActionIntent, AgentRun, Alert, Approval, Case, Digest, EvidenceItem, Id,
    InvestigationFinding, Money, ScoringOutcome, SimulatedAction, Transaction,
)

CaseState = Literal["open", "investigating", "awaiting_approval", "closed", "inconclusive"]
CASE_STATES: tuple[str, ...] = CaseState.__args__
Capability = Literal["ingest_transaction", "read_case", "approve_action",
                     "execute_simulated_action"]
MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 25


class HttpBody(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("*")
    @classmethod
    def utc(cls, value):
        # Database drivers return the session time zone; the contract is always UTC.
        return value.astimezone(timezone.utc) if isinstance(value, datetime) else value


class ErrorDetail(HttpBody):
    code: str


class ErrorResponse(HttpBody):
    """Body of every handled (documented) error response. `error` is a stable machine code;
    no input is echoed. Unexpected server failures, proxies and network faults can instead
    produce a non-JSON 5xx, an empty or invalid body, or no response: clients must fall back
    to a generic message and, for an execution request, keep the same idempotency key."""
    error: str
    details: list[ErrorDetail] | None = Field(
        default=None, description="Validation error codes only (no field names or values).")


class IngestResponse(HttpBody):
    transaction: Transaction
    rule_score: float | None = Field(description=(
        "Recorded rule heuristic, not a probability. Null only for legacy transactions "
        "ingested before scoring outcomes were recorded (outcome unknown)."))
    scoring: ScoringOutcome | None = Field(description="Null means unknown (legacy), not zero.")
    alert: Alert | None
    case: Case | None
    replayed: bool


class AgentRunView(HttpBody):
    run: AgentRun
    finding: InvestigationFinding | None = Field(
        description="Untrusted model/agent output; render rationale as inert text.")


class IntentView(HttpBody):
    intent: ActionIntent = Field(description="Built by the server from stored records.")
    intent_sha256: Digest
    approval: Approval | None
    action: SimulatedAction | None


class CaseDetail(HttpBody):
    case: Case
    alert: Alert
    transaction: Transaction
    scoring: ScoringOutcome | None
    evidence: list[EvidenceItem]
    agent_runs: list[AgentRunView]
    action_intents: list[IntentView] = Field(description="Oldest revision first; the last "
                                             "entry is current only if its case_revision "
                                             "equals case.revision.")


class CaseSummary(HttpBody):
    id: Id
    state: CaseState
    revision: int
    created_at: AwareDatetime
    updated_at: AwareDatetime
    alert_id: Id
    transaction_id: Id
    external_id: str
    amount: Money
    direction: Literal["debit", "credit"]
    score: float
    threshold: float
    scoring_kind: Literal["rule", "model"]
    score_semantics: Literal["heuristic", "estimated_probability"]


class CasePage(HttpBody):
    items: list[CaseSummary]
    next_cursor: str | None = Field(description="Opaque; pass back unchanged. Null at the end.")
    limit: int


class SessionView(HttpBody):
    """The authenticated session's own scope and permissions. Never the token."""
    tenant_id: Id
    session_id: Id
    actor_id: Id
    actor_kind: Literal["human", "system"]
    capabilities: list[Capability]
    expires_at: AwareDatetime


class InvestigatorInfo(HttpBody):
    name: str
    version: str


class Overview(HttpBody):
    cases_by_state: dict[CaseState, Annotated[int, Field(ge=0)]]
    transactions: int
    alerts: int
    simulated_actions: int
    investigator: InvestigatorInfo


class ExecuteResponse(HttpBody):
    action: SimulatedAction
    replayed: bool = Field(description="True when this idempotency key already succeeded; "
                           "the original action is returned and nothing is re-executed.")


class Health(HttpBody):
    status: Literal["ok"]
    investigator: str
