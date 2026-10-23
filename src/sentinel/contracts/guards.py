"""Pure precondition checks. Storage must enforce atomicity and reference ownership."""
from datetime import datetime, timezone

from sentinel.contracts.v1 import (
    Approval, ArtifactRef, Case, EvidenceItem, Scope, TrustedContext,
    evidence_content_digest, evidence_snapshot_digest,
)


class ContractViolation(ValueError):
    """Safe machine-readable reason; never include raw request/model content."""


def require_scope(context: TrustedContext, scope: Scope) -> None:
    if context.scope != scope:
        raise ContractViolation("scope_mismatch")


def _require_case_at_decision(
    context: TrustedContext, case: Case, decision_at: datetime,
) -> datetime:
    if "read_case" not in context.capabilities:
        raise ContractViolation("evidence_permission_denied")
    require_scope(context, case.scope)
    if decision_at.tzinfo is None or decision_at.utcoffset() is None:
        raise ContractViolation("naive_decision_time")
    decision = decision_at.astimezone(timezone.utc)
    if case.created_at > decision or case.updated_at > decision:
        raise ContractViolation("case_not_yet_available")
    return decision


def require_evidence_at_decision(
    context: TrustedContext, case: Case, evidence: EvidenceItem, decision_at: datetime,
) -> None:
    decision = _require_case_at_decision(context, case, decision_at)
    require_scope(context, evidence.scope)
    if evidence.case_id != case.id or evidence.id not in case.evidence_ids:
        raise ContractViolation("evidence_reference_mismatch")
    if evidence.content_sha256 != evidence_content_digest(evidence):
        raise ContractViolation("evidence_content_mismatch")
    if evidence.available_at > decision:
        raise ContractViolation("evidence_not_yet_available")


def require_evidence_snapshot(
    context: TrustedContext, case: Case, items: tuple[EvidenceItem, ...], decision_at: datetime,
) -> None:
    """Check the complete referenced set before an investigation or approval is prepared."""
    _require_case_at_decision(context, case, decision_at)
    if len({item.id for item in items}) != len(items):
        raise ContractViolation("duplicate_evidence")
    if {item.id for item in items} != set(case.evidence_ids):
        raise ContractViolation("incomplete_evidence_snapshot")
    for item in items:
        require_evidence_at_decision(context, case, item, decision_at)
    if evidence_snapshot_digest(items) != case.pins.evidence_snapshot_sha256:
        raise ContractViolation("evidence_snapshot_mismatch")


def require_executable_approval(
    context: TrustedContext,
    approval: Approval,
    *,
    now: datetime,
    current_case: Case,
    current_intent_sha256: str,
    active_policy: ArtifactRef,
) -> None:
    """Checks trusted snapshots only; does not consume approval or perform an action."""
    require_scope(context, current_case.scope)
    require_scope(context, approval.intent.scope)
    if context.actor_kind != "human" or "execute_simulated_action" not in context.capabilities:
        raise ContractViolation("action_permission_denied")
    if context.actor_id != approval.actor_id:
        raise ContractViolation("approver_mismatch")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ContractViolation("naive_execution_time")
    if approval.decision != "approved" or approval.consumed_at is not None:
        raise ContractViolation("approval_not_available")
    if not approval.decided_at <= now.astimezone(timezone.utc) < approval.expires_at:
        raise ContractViolation("approval_outside_validity")
    if not current_case.created_at <= current_case.updated_at <= approval.decided_at:
        raise ContractViolation("approval_precedes_case_snapshot")
    if approval.intent.policy != active_policy:
        raise ContractViolation("inactive_policy")
    intent = approval.intent
    if current_case.state != "awaiting_approval" or intent.case_id != current_case.id:
        raise ContractViolation("case_not_executable")
    if intent.case_revision != current_case.revision:
        raise ContractViolation("stale_case_revision")
    if intent.evidence_snapshot_sha256 != current_case.pins.evidence_snapshot_sha256:
        raise ContractViolation("stale_evidence_snapshot")
    if intent.policy != current_case.pins.policy:
        raise ContractViolation("stale_policy")
    if approval.intent_sha256 != current_intent_sha256:
        raise ContractViolation("stale_action_intent")
