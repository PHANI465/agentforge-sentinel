"""Draft v1 persisted contracts and deliberately narrower untrusted request DTOs.

Models validate values; trusted server code must assign identity and verify every
reference. No model is an authorization mechanism or a durable execution engine.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime, BaseModel, BeforeValidator, ConfigDict, Field, StrictInt, ValidationError,
    field_validator, model_validator,
)

Id = UUID
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Name = Annotated[str, Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")]
Version = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")]
Revision = Annotated[StrictInt, Field(ge=1, le=2_147_483_647)]
UnitScore = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False, strict=True)]
Currency = Literal["USD", "INR", "GBP", "JPY"]
CURRENCY_EXPONENT = {"USD": 2, "INR": 2, "GBP": 2, "JPY": 0}
MAX_MINOR_UNITS = 9_000_000_000_000


def strict_timestamp(value):
    if isinstance(value, datetime):
        return value
    pattern = r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:[Zz]|[+-]\d{2}:\d{2})$"
    if not isinstance(value, str) or re.fullmatch(pattern, value) is None:
        raise ValueError("use a timezone-aware datetime or RFC3339 string")
    return value


Timestamp = Annotated[AwareDatetime, BeforeValidator(strict_timestamp)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    schema_version: Literal["1.0"] = "1.0"

    @field_validator("*")
    @classmethod
    def normalize_datetime(cls, value):
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc)
        return value


class Scope(Contract):
    tenant_id: Id
    session_id: Id


class TrustedContext(Contract):
    """Construct only at the authenticated server boundary, never from a request/model."""
    scope: Scope
    actor_id: Id
    actor_kind: Literal["human", "system"]
    capabilities: frozenset[Literal[
        "ingest_transaction", "read_case", "approve_action", "execute_simulated_action",
    ]]


class Money(Contract):
    """Positive magnitude; direction is separate. Integers remain safe in JavaScript."""
    currency: Currency
    minor_units: Annotated[StrictInt, Field(gt=0, le=MAX_MINOR_UNITS)]
    currency_exponent: Annotated[StrictInt, Field(ge=0, le=2)]

    @model_validator(mode="after")
    def currency_precision(self):
        if self.currency_exponent != CURRENCY_EXPONENT[self.currency]:
            raise ValueError("currency exponent does not match the v1 currency table")
        return self


class ArtifactRef(Contract):
    name: Name
    version: Version
    sha256: Digest

    @field_validator("version")
    @classmethod
    def immutable_version(cls, value):
        if value.lower() in {"latest", "head", "main", "master"}:
            raise ValueError("use an immutable artifact version")
        return value


class TransactionInput(Contract):
    """Untrusted input: no scope, source provenance, labels, actor or credentials."""
    external_id: Name
    account_id: Id
    amount: Money
    direction: Literal["debit", "credit"]
    occurred_at: Timestamp


class Transaction(TransactionInput):
    id: Id
    scope: Scope
    ingested_at: Timestamp
    dataset: ArtifactRef
    synthetic: Literal[True] = True

    @model_validator(mode="after")
    def chronological(self):
        if self.ingested_at < self.occurred_at:
            raise ValueError("ingestion precedes event time; v1 permits no future clock skew")
        return self


class Alert(Contract):
    id: Id
    scope: Scope
    transaction_id: Id
    created_at: Timestamp
    features_as_of: Timestamp
    scorer: ArtifactRef
    features: ArtifactRef
    threshold_policy: ArtifactRef
    scoring_kind: Literal["rule", "model"]
    score_semantics: Literal["heuristic", "estimated_probability"]
    score: UnitScore
    threshold: UnitScore

    @model_validator(mode="after")
    def scoring_snapshot(self):
        if self.features_as_of > self.created_at:
            raise ValueError("features are unavailable at the decision time")
        if self.scoring_kind == "rule" and self.score_semantics != "heuristic":
            raise ValueError("rule scores are not probabilities")
        return self


class Fact(Contract):
    name: Literal["amount_minor", "transaction_count_1h", "account_age_days"]
    value: Annotated[StrictInt, Field(ge=0, le=MAX_MINOR_UNITS)]


class EvidenceItem(Contract):
    id: Id
    scope: Scope
    case_id: Id
    source: Literal["synthetic_transaction", "historical_aggregate"]
    source_ref: Name
    observed_at: Timestamp
    available_at: Timestamp
    facts: Annotated[tuple[Fact, ...], Field(min_length=1, max_length=32)]
    content_sha256: Digest

    @model_validator(mode="after")
    def evidence_snapshot(self):
        if self.available_at < self.observed_at:
            raise ValueError("evidence cannot be available before it is observed")
        names = [fact.name for fact in self.facts]
        if len(set(names)) != len(names):
            raise ValueError("duplicate fact names are ambiguous")
        return self


def canonical_digest(namespace: str, value: dict | list) -> str:
    document = {"canonicalization": namespace, "value": value}
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                         allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def evidence_content_digest(item: EvidenceItem) -> str:
    payload = item.model_dump(mode="json", exclude={"content_sha256"})
    payload["facts"] = sorted(payload["facts"], key=lambda fact: fact["name"])
    return canonical_digest("sentinel.evidence.v1", payload)


def evidence_snapshot_digest(items: tuple[EvidenceItem, ...]) -> str:
    if len({item.id for item in items}) != len(items):
        raise ValueError("duplicate evidence identifiers")
    payload = [{"id": str(item.id), "sha256": item.content_sha256}
               for item in sorted(items, key=lambda item: str(item.id))]
    return canonical_digest("sentinel.evidence-snapshot.v1", payload)


class CasePins(Contract):
    dataset: ArtifactRef
    scorer: ArtifactRef
    threshold_policy: ArtifactRef
    policy: ArtifactRef
    agent_config: ArtifactRef
    tool_config: ArtifactRef
    evidence_snapshot_sha256: Digest


class Case(Contract):
    id: Id
    scope: Scope
    alert_id: Id
    revision: Revision
    state: Literal["open", "investigating", "awaiting_approval", "closed", "inconclusive"]
    pins: CasePins
    evidence_ids: Annotated[tuple[Id, ...], Field(max_length=100)] = ()
    created_at: Timestamp
    updated_at: Timestamp

    @model_validator(mode="after")
    def case_snapshot(self):
        if self.updated_at < self.created_at:
            raise ValueError("case update precedes creation")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("duplicate evidence identifiers")
        return self


class RunBudget(Contract):
    max_steps: Annotated[StrictInt, Field(ge=1, le=16)] = 4
    max_tool_calls: Annotated[StrictInt, Field(ge=0, le=16)] = 4
    max_output_tokens: Annotated[StrictInt, Field(ge=1, le=4096)] = 1024
    timeout_seconds: Annotated[StrictInt, Field(ge=1, le=60)] = 30
    max_delegations: Annotated[StrictInt, Field(ge=0, le=2)] = 0


class AgentRun(Contract):
    id: Id
    scope: Scope
    case_id: Id
    case_revision: Revision
    role: Literal["evidence_analyst", "investigator", "reviewer"]
    principal_id: Id
    config: ArtifactRef
    tool_profile: ArtifactRef
    input_snapshot_sha256: Digest
    budget: RunBudget
    status: Literal["queued", "running", "completed", "failed", "inconclusive", "cancelled"]
    failure_code: Literal["provider_unavailable", "timeout", "invalid_output", "budget_exhausted"] | None = None

    @model_validator(mode="after")
    def failure_state(self):
        if self.status == "failed" and self.failure_code is None:
            raise ValueError("failed run needs a typed failure code")
        if self.status in {"queued", "running", "completed"} and self.failure_code is not None:
            raise ValueError("failure code is incompatible with run status")
        return self


class HoldParameters(Contract):
    operation: Literal["simulated_hold"]
    transaction_id: Id
    amount: Money


class EscalateParameters(Contract):
    operation: Literal["escalate"]
    transaction_id: Id
    reason_code: Literal["velocity_pattern", "unusual_amount", "insufficient_evidence"]


ActionParameters = Annotated[
    HoldParameters | EscalateParameters, Field(discriminator="operation")
]


class ActionIntent(Contract):
    id: Id
    scope: Scope
    case_id: Id
    case_revision: Revision
    evidence_snapshot_sha256: Digest
    policy: ArtifactRef
    parameters: ActionParameters


def intent_digest(intent: ActionIntent) -> str:
    """Versioned canonical JSON, UTF-8, sorted keys, no floats in this document."""
    document = {
        "canonicalization": "sentinel.action-intent.v1",
        "intent": intent.model_dump(mode="json"),
    }
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                         allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class InvestigationFinding(Contract):
    """Untrusted agent output. It selects among enumerated options only; the server builds
    the action intent from stored records. Rationale is display text, never instructions."""
    operation: Literal["simulated_hold", "escalate"]
    reason_code: Literal["velocity_pattern", "unusual_amount", "insufficient_evidence"]
    rationale: Annotated[str, Field(min_length=1, max_length=600)]


class InvestigationRequestInput(Contract):
    """Untrusted request to investigate a case at the revision the analyst last read."""
    expected_revision: Revision


class ApprovalDecisionInput(Contract):
    """Untrusted human choice; server resolves intent and authenticated approver."""
    action_intent_id: Id
    decision: Literal["approved", "rejected"]


class ExecuteActionInput(Contract):
    """Untrusted execution request; the key makes client retries return the original result."""
    approval_id: Id
    idempotency_key: Id


class Approval(Contract):
    id: Id
    intent: ActionIntent
    intent_sha256: Digest
    actor_id: Id
    actor_kind: Literal["human"] = "human"
    decision: Literal["approved", "rejected"]
    decided_at: Timestamp
    expires_at: Timestamp
    consumed_at: Timestamp | None = None

    @model_validator(mode="after")
    def exact_binding(self):
        if self.intent_sha256 != intent_digest(self.intent):
            raise ValueError("approval does not match the exact action intent")
        if self.expires_at <= self.decided_at:
            raise ValueError("approval expiry must follow decision time")
        if self.consumed_at is not None:
            if self.decision != "approved":
                raise ValueError("a rejected approval cannot be consumed")
            if not self.decided_at <= self.consumed_at < self.expires_at:
                raise ValueError("approval was consumed outside its validity interval")
        return self


class SimulatedAction(Contract):
    id: Id
    intent: ActionIntent
    approval_id: Id
    intent_sha256: Digest
    idempotency_key: Id
    mode: Literal["simulated"] = "simulated"
    state: Literal["pending", "succeeded", "failed", "cancelled"]
    created_at: Timestamp
    completed_at: Timestamp | None = None

    @model_validator(mode="after")
    def action_state(self):
        if self.intent_sha256 != intent_digest(self.intent):
            raise ValueError("action binding differs from intent")
        terminal = self.state != "pending"
        if terminal != (self.completed_at is not None):
            raise ValueError("completion timestamp must match terminal status")
        if self.completed_at is not None and self.completed_at < self.created_at:
            raise ValueError("action completion precedes creation")
        return self


class AuditEvent(Contract):
    id: Id
    scope: Scope
    case_id: Id
    case_revision: Revision
    correlation_id: Id
    actor_id: Id
    actor_kind: Literal["human", "agent", "system"]
    event_type: Literal[
        "transaction_received", "alert_raised", "investigation_started",
        "investigation_completed", "approval_recorded", "action_succeeded", "action_denied",
    ]
    outcome: Literal["success", "denied", "failure"]
    occurred_at: Timestamp
    recorded_at: Timestamp

    @model_validator(mode="after")
    def audit_order(self):
        if self.recorded_at < self.occurred_at:
            raise ValueError("audit recording precedes occurrence")
        if self.event_type == "action_denied" and self.outcome != "denied":
            raise ValueError("a denial event requires a denied outcome")
        if self.event_type == "action_succeeded" and self.outcome != "success":
            raise ValueError("a success event requires a successful outcome")
        return self


def safe_validation_errors(error: ValidationError) -> list[dict[str, str]]:
    """Codes only: even unknown field names and validation context may contain secrets."""
    return [{"code": item["type"]} for item in
            error.errors(include_input=False, include_context=False, include_url=False)[:20]]


PERSISTED_MODELS = (Transaction, Alert, EvidenceItem, Case, AgentRun, Approval,
                    SimulatedAction, AuditEvent)
EXPORT_MODELS = PERSISTED_MODELS + (
    TransactionInput, ApprovalDecisionInput, ActionIntent, InvestigationFinding,
    InvestigationRequestInput, ExecuteActionInput,
)
