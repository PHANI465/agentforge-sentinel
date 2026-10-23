from datetime import datetime, timedelta, timezone
import json
from uuid import UUID

import pytest
from pydantic import ValidationError

from sentinel.contracts.guards import (
    ContractViolation, require_evidence_at_decision, require_evidence_snapshot,
    require_executable_approval,
)
from sentinel.contracts.v1 import (
    ActionIntent, AgentRun, Alert, Approval, ApprovalDecisionInput, ArtifactRef,
    AuditEvent, Case, CasePins, EvidenceItem, Fact, HoldParameters, Money,
    RunBudget, Scope, SimulatedAction, Transaction, TransactionInput, TrustedContext,
    evidence_content_digest, evidence_snapshot_digest, intent_digest, safe_validation_errors,
)

NOW = datetime(2026, 10, 23, 17, 0, tzinfo=timezone.utc)
SHA = "a" * 64
OTHER_SHA = "b" * 64


def uid(n):
    return UUID(int=n)


def artifact(name="policy", digest=SHA):
    return ArtifactRef(name=name, version="v1.0.0", sha256=digest)


def scope(session=2, tenant=1):
    return Scope(tenant_id=uid(tenant), session_id=uid(session))


def money(amount=12345, currency="USD", exponent=2):
    return Money(currency=currency, minor_units=amount, currency_exponent=exponent)


def case(**changes):
    values = dict(
        id=uid(3), scope=scope(), alert_id=uid(4), revision=1,
        state="awaiting_approval", evidence_ids=(uid(5),),
        pins=CasePins(dataset=artifact("data"), scorer=artifact("rule"),
                      threshold_policy=artifact("threshold"), policy=artifact(),
                      agent_config=artifact("agent"), tool_config=artifact("tools"),
                      evidence_snapshot_sha256=evidence_snapshot_digest((evidence(),))),
        created_at=NOW - timedelta(minutes=2), updated_at=NOW,
    )
    values.update(changes)
    return Case(**values)


def intent(**changes):
    values = dict(
        id=uid(6), scope=scope(), case_id=uid(3), case_revision=1,
        evidence_snapshot_sha256=evidence_snapshot_digest((evidence(),)), policy=artifact(),
        parameters=HoldParameters(operation="simulated_hold",
                                  transaction_id=uid(7), amount=money()),
    )
    values.update(changes)
    return ActionIntent(**values)


def approval(**changes):
    action_intent = changes.pop("intent", intent())
    values = dict(
        id=uid(8), intent=action_intent, intent_sha256=intent_digest(action_intent),
        actor_id=uid(9), decision="approved", decided_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )
    values.update(changes)
    return Approval(**values)


def context(**changes):
    values = dict(scope=scope(), actor_id=uid(9), actor_kind="human",
                  capabilities=frozenset({"read_case", "execute_simulated_action"}))
    values.update(changes)
    return TrustedContext(**values)


def evidence(**changes):
    values = dict(
        id=uid(5), scope=scope(), case_id=uid(3), source="synthetic_transaction",
        source_ref="transaction:7", observed_at=NOW - timedelta(minutes=2),
        available_at=NOW, facts=(Fact(name="amount_minor", value=12345),),
        content_sha256=SHA,
    )
    values.update(changes)
    values["content_sha256"] = evidence_content_digest(EvidenceItem(**values))
    return EvidenceItem(**values)


def check_approval(item=None, ctx=None, current_case=None, now=NOW):
    item = item or approval()
    require_executable_approval(
        ctx or context(), item, now=now, current_case=current_case or case(),
        current_intent_sha256=intent_digest(intent()), active_policy=artifact(),
    )


def test_money_json_round_trip_preserves_integer_and_precision():
    value = money(9_000_000_000_000)
    payload = json.loads(value.model_dump_json())
    assert type(payload["minor_units"]) is int
    assert payload["minor_units"] < 2**53
    assert Money.model_validate_json(json.dumps(payload)) == value
    assert money(100, "JPY", 0).currency_exponent == 0


@pytest.mark.parametrize("value", [1.5, "12345", True, -1, 0, 9_000_000_000_001,
                                   float("nan"), float("inf")])
def test_money_rejects_noncanonical_or_out_of_range_values(value):
    with pytest.raises(ValidationError):
        money(value)


def test_unsupported_currency_and_exponent_rejected():
    with pytest.raises(ValidationError):
        money(100, "JPY", 2)
    with pytest.raises(ValidationError):
        money(100, "XYZ", 2)


def transaction_input(**changes):
    values = dict(external_id="replay-1", account_id=uid(10), amount=money(),
                  direction="debit", occurred_at=NOW)
    values.update(changes)
    return TransactionInput(**values)


@pytest.mark.parametrize("field,value", [
    ("tenant_id", str(uid(99))), ("scope", scope().model_dump(mode="json")),
    ("actor_id", str(uid(99))), ("is_fraud", True), ("label_available_at", NOW),
    ("api_key", "DUMMY_SECRET_NOT_REAL"), ("permissions", ["admin"]),
])
def test_untrusted_transaction_input_cannot_set_identity_truth_or_credentials(field, value):
    with pytest.raises(ValidationError):
        transaction_input(**{field: value})


def test_input_and_persisted_transaction_are_distinct():
    input_value = transaction_input()
    persisted = Transaction(**input_value.model_dump(), id=uid(7), scope=scope(),
                            ingested_at=NOW, dataset=artifact("data"))
    assert persisted.synthetic is True
    assert "scope" not in TransactionInput.model_fields
    with pytest.raises(ValidationError):
        Transaction(**input_value.model_dump(), id=uid(7), scope=scope(),
                    ingested_at=NOW - timedelta(seconds=1), dataset=artifact("data"))


def test_timestamps_reject_naive_and_normalize_timezone():
    with pytest.raises(ValidationError):
        transaction_input(occurred_at=NOW.replace(tzinfo=None))
    offset = timezone(timedelta(hours=5, minutes=30))
    assert transaction_input(occurred_at=NOW.astimezone(offset)).occurred_at == NOW
    assert transaction_input(occurred_at=NOW.astimezone(offset)).occurred_at.tzinfo == timezone.utc


@pytest.mark.parametrize("score", [float("nan"), float("inf"), -0.1, 1.1, True])
def test_alert_rejects_invalid_numeric_scores(score):
    with pytest.raises(ValidationError):
        alert(score=score)


def alert(**changes):
    values = dict(
        id=uid(4), scope=scope(), transaction_id=uid(7), created_at=NOW,
        features_as_of=NOW, scorer=artifact("rule"), features=artifact("features"),
        threshold_policy=artifact("threshold"), scoring_kind="rule",
        score_semantics="heuristic", score=0.8, threshold=0.7,
    )
    values.update(changes)
    return Alert(**values)


def test_rule_score_never_claimed_as_probability_or_future_feature():
    assert alert().score_semantics == "heuristic"
    with pytest.raises(ValidationError):
        alert(score_semantics="estimated_probability")
    with pytest.raises(ValidationError):
        alert(features_as_of=NOW + timedelta(seconds=1))


def test_evidence_requires_case_scope_reference_and_decision_time():
    require_evidence_at_decision(context(), case(), evidence(), NOW)
    for item in (evidence(scope=scope(22)), evidence(scope=scope(2, 99)),
                 evidence(case_id=uid(99)), evidence(id=uid(99)),
                 evidence(available_at=NOW + timedelta(seconds=1))):
        with pytest.raises(ContractViolation):
            require_evidence_at_decision(context(), case(), item, NOW)
    with pytest.raises(ContractViolation):
        require_evidence_at_decision(context(capabilities=frozenset()), case(), evidence(), NOW)


def test_duplicate_evidence_and_fact_names_rejected():
    with pytest.raises(ValidationError):
        case(evidence_ids=(uid(5), uid(5)))
    with pytest.raises(ValidationError):
        evidence(facts=(Fact(name="amount_minor", value=1), Fact(name="amount_minor", value=2)))


def test_canonical_action_binding_survives_json_key_reordering():
    item = intent()
    reordered = dict(reversed(list(item.model_dump(mode="json").items())))
    assert intent_digest(ActionIntent.model_validate_json(json.dumps(reordered))) == intent_digest(item)


def test_each_material_action_change_invalidates_binding():
    original = intent_digest(intent())
    variants = [
        intent(scope=scope(22)), intent(case_revision=2),
        intent(evidence_snapshot_sha256=OTHER_SHA),
        intent(policy=artifact(digest=OTHER_SHA)),
        intent(parameters=HoldParameters(operation="simulated_hold",
                                        transaction_id=uid(7), amount=money(12346))),
        intent(parameters=HoldParameters(operation="simulated_hold",
                                        transaction_id=uid(99), amount=money())),
    ]
    assert all(intent_digest(item) != original for item in variants)


def test_approval_rejects_mismatched_digest_and_nonhuman_actor():
    with pytest.raises(ValidationError):
        approval(intent_sha256=OTHER_SHA)
    with pytest.raises(ValidationError):
        approval(actor_kind="agent")


@pytest.mark.parametrize("changes", [
    {"decision": "rejected"},
    {"consumed_at": NOW + timedelta(seconds=1)},
])
def test_unavailable_approval_cannot_execute(changes):
    with pytest.raises(ContractViolation):
        check_approval(approval(**changes), now=NOW + timedelta(seconds=2))


@pytest.mark.parametrize("moment", [NOW - timedelta(seconds=1), NOW + timedelta(minutes=5)])
def test_approval_time_window_has_exclusive_expiry(moment):
    with pytest.raises(ContractViolation):
        check_approval(now=moment)


def test_stale_case_evidence_policy_and_intent_fail_closed():
    pins = case().pins
    changed_pins = pins.model_dump()
    changed_pins["evidence_snapshot_sha256"] = OTHER_SHA
    changed_policy = pins.model_dump()
    changed_policy["policy"] = artifact(digest=OTHER_SHA)
    variants = [
        case(revision=2), case(state="closed"),
        case(pins=CasePins(**changed_pins)),
        case(pins=CasePins(**changed_policy)),
        case(id=uid(99)), case(scope=scope(22)),
    ]
    for current in variants:
        with pytest.raises(ContractViolation):
            check_approval(current_case=current)
    with pytest.raises(ContractViolation):
        require_executable_approval(context(), approval(), now=NOW, current_case=case(),
                                    current_intent_sha256=OTHER_SHA, active_policy=artifact())


def test_scope_actor_and_permissions_are_not_inferred_from_valid_ids():
    check_approval()
    for ctx in (context(scope=scope(22)), context(scope=scope(2, 99)),
                context(actor_id=uid(99)), context(actor_kind="system"),
                context(capabilities=frozenset())):
        with pytest.raises(ContractViolation):
            check_approval(ctx=ctx)


def test_client_approval_choice_cannot_supply_authority():
    body = dict(action_intent_id=uid(6), decision="approved")
    assert ApprovalDecisionInput(**body).decision == "approved"
    for field in ("actor_id", "actor_kind", "scope", "intent_sha256"):
        with pytest.raises(ValidationError):
            ApprovalDecisionInput(**body, **{field: "forged"})


def test_canary_values_are_omitted_from_safe_validation_errors():
    canary = "DUMMY_NOT_A_REAL_KEY_938471"
    try:
        transaction_input(api_key=canary)
    except ValidationError as error:
        safe = json.dumps(safe_validation_errors(error))
        assert canary not in safe
        assert "input" not in safe
        assert "extra_forbidden" in safe
    else:
        pytest.fail("credential field was accepted")


def test_actions_are_explicitly_simulated_and_have_consistent_terminal_state():
    item = intent()
    values = dict(id=uid(11), intent=item, approval_id=uid(8),
                  intent_sha256=intent_digest(item), idempotency_key=uid(12),
                  state="pending", created_at=NOW)
    assert SimulatedAction(**values).mode == "simulated"
    with pytest.raises(ValidationError):
        SimulatedAction(**values, mode="live")
    with pytest.raises(ValidationError):
        SimulatedAction(**(values | {"state": "succeeded"}))


def test_run_budget_and_failure_state_are_bounded():
    with pytest.raises(ValidationError):
        RunBudget(max_steps=1000)
    with pytest.raises(ValidationError):
        RunBudget(timeout_seconds=True)
    values = dict(id=uid(13), scope=scope(), case_id=uid(3), case_revision=1,
                  role="investigator", principal_id=uid(14), config=artifact("agent"),
                  tool_profile=artifact("tools"), input_snapshot_sha256=SHA,
                  budget=RunBudget(), status="failed")
    with pytest.raises(ValidationError):
        AgentRun(**values)
    assert AgentRun(**values, failure_code="timeout").status == "failed"


def test_artifact_pins_and_audit_outcomes_cannot_be_ambiguous():
    with pytest.raises(ValidationError):
        ArtifactRef(name="policy", version="latest", sha256=SHA)
    values = dict(id=uid(15), scope=scope(), case_id=uid(3), case_revision=1,
                  correlation_id=uid(16), actor_id=uid(9), actor_kind="human",
                  event_type="action_denied", outcome="denied", occurred_at=NOW,
                  recorded_at=NOW)
    assert AuditEvent(**values).outcome == "denied"
    with pytest.raises(ValidationError):
        AuditEvent(**(values | {"outcome": "success"}))


def test_snapshot_checks_content_completeness_and_case_hash():
    require_evidence_snapshot(context(), case(), (evidence(),), NOW)
    with pytest.raises(ContractViolation):
        require_evidence_snapshot(context(), case(), (), NOW)
    tampered = evidence().model_dump()
    tampered["facts"] = (Fact(name="amount_minor", value=999),)
    with pytest.raises(ContractViolation, match="evidence_content_mismatch"):
        require_evidence_at_decision(context(), case(), EvidenceItem(**tampered), NOW)
    changed = evidence(facts=(Fact(name="amount_minor", value=999),))
    with pytest.raises(ContractViolation, match="evidence_snapshot_mismatch"):
        require_evidence_snapshot(context(), case(), (changed,), NOW)


def test_active_policy_is_independent_from_the_case_pin():
    with pytest.raises(ContractViolation, match="inactive_policy"):
        require_executable_approval(context(), approval(), now=NOW, current_case=case(),
                                    current_intent_sha256=intent_digest(intent()),
                                    active_policy=artifact(digest=OTHER_SHA))


def test_future_case_cannot_be_used_for_an_earlier_decision_or_execution():
    future = case(created_at=NOW + timedelta(days=1), updated_at=NOW + timedelta(days=1))
    with pytest.raises(ContractViolation):
        require_evidence_at_decision(context(), future, evidence(), NOW)
    with pytest.raises(ContractViolation, match="approval_precedes_case_snapshot"):
        check_approval(current_case=future)


@pytest.mark.parametrize("value", [1792774800, 1792774800.0, True, "1792774800"])
def test_timestamps_reject_unix_number_coercion(value):
    with pytest.raises(ValidationError):
        transaction_input(occurred_at=value)


def test_empty_snapshot_still_requires_permission_and_nonfuture_case():
    pins = case().pins.model_dump()
    pins["evidence_snapshot_sha256"] = evidence_snapshot_digest(())
    empty_case = case(evidence_ids=(), pins=CasePins(**pins))
    require_evidence_snapshot(context(), empty_case, (), NOW)
    with pytest.raises(ContractViolation, match="evidence_permission_denied"):
        require_evidence_snapshot(context(capabilities=frozenset()), empty_case, (), NOW)
    with pytest.raises(ContractViolation, match="naive_decision_time"):
        require_evidence_snapshot(context(), empty_case, (), NOW.replace(tzinfo=None))


def test_evidence_snapshot_hash_is_order_independent_and_rejects_duplicates():
    first = evidence()
    second = evidence(id=uid(55), source_ref="transaction:55")
    assert evidence_snapshot_digest((first, second)) == evidence_snapshot_digest((second, first))
    with pytest.raises(ValueError):
        evidence_snapshot_digest((first, first))
