"""G3B unit checks without a database: frozen contracts, budgets, leases, claims, safe logs."""
import json
import logging
import math
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from sentinel.agents import budget, claims
from sentinel.agents.capacity import AgentCapacity, CapacityExhausted
from sentinel.contracts import agents
from sentinel.contracts.agents import (
    Citation, FactClaim, InvestigatorOutput, MissingEvidenceClaim, ToolResult, WorkflowLimits,
)
from sentinel.contracts.v1 import EvidenceItem, Fact, Scope
from sentinel.observability import emit

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "contracts" / "agents" / "examples"
DRAFT = ROOT / "docs" / "agents" / "contracts-draft" / "examples"


# ---- frozen contracts ----------------------------------------------------------------------

@pytest.mark.parametrize("label", ["valid", "invalid"])
def test_ported_examples_keep_their_accepted_labels(label):
    files = sorted((EXAMPLES / label).glob("*.json"))
    drafts = sorted(p.name for p in (DRAFT / label).glob("*.json"))
    assert [p.name for p in files] == drafts and files  # one port per accepted draft example
    for path in files:
        model = agents.EXPORTS[path.name.split(".", 1)[0]]
        try:
            TypeAdapter(model).validate_json(path.read_bytes())
            accepted = True
        except ValidationError:
            accepted = False
        assert accepted == (label == "valid"), path.name


def test_promotion_is_mechanical():
    for path in EXAMPLES.rglob("*.json"):
        text = path.read_text(encoding="utf-8")
        draft = (DRAFT / path.parent.name / path.name).read_text(encoding="utf-8")
        assert text == draft.replace('"schema_version": "g3a-draft-1"', '"schema_version": "1.0"'
                                     ).replace('"claim_schema": "g3a-draft-1"',
                                               '"claim_schema": "agents-1.0"')
    assert agents.WorkflowLimits().model_dump()["schema_version"] == "1.0"
    assert agents.CLAIM_SCHEMA == "agents-1.0"


def test_role_outputs_reject_identifiers_and_free_tools():
    with pytest.raises(ValidationError):
        TypeAdapter(agents.ToolRequest).validate_python(
            {"tool": "account_history", "window": "24h", "case_id": str(uuid.uuid4())})
    with pytest.raises(ValidationError):
        TypeAdapter(agents.ToolRequest).validate_python({"tool": "sql_query", "sql": "x"})
    with pytest.raises(ValidationError):
        InvestigatorOutput.model_validate({"role": "investigator", "operation": "approve",
                                           "reason_code": "velocity_pattern", "claims": []})


# ---- budgets (the accepted specification, executed against the runtime helpers) ------------

class Clock:
    def __init__(self, now=1_000_000.0):
        self.now = now

    def __call__(self):
        return self.now


def deadline_at(remaining_ms):
    clock = Clock()
    deadline = budget.Deadline(WorkflowLimits(), clock)
    clock.now = deadline.deadline_ms - remaining_ms
    return deadline


def test_working_phase_excludes_the_reserve_and_terminal_uses_it():
    assert deadline_at(6000).budget_ms("working", 5000) == 1000
    assert deadline_at(5000).budget_ms("working", 5000) is None
    assert deadline_at(4000).budget_ms("working", 5000) is None
    assert deadline_at(5000).budget_ms("terminal", 5000) == 5000
    assert deadline_at(4000).budget_ms("terminal", 5000) == 4000
    assert deadline_at(100).budget_ms("terminal", 5000) == 100


def test_budgets_are_positive_floored_or_refused():
    assert deadline_at(5099.9).budget_ms("working", 5000) is None
    assert deadline_at(5100.9).budget_ms("working", 5000) == 100
    assert deadline_at(99.9).budget_ms("terminal", 5000) is None
    for remaining in range(-20_000, 160_000, 37):
        for phase in ("working", "terminal"):
            value = deadline_at(remaining / 7).budget_ms(phase, 5000)
            assert value is None or (100 <= value <= 5000 and isinstance(value, int))


def test_old_formula_counterexamples_are_not_reproduced():
    for remaining in (6, 5, 4, 0):
        old = min(5, remaining - 5)
        assert old <= 1  # 1/0/-1/-5 s: a disabling or negative timeout
        value = deadline_at(remaining * 1000).budget_ms("terminal", 5000)
        assert value is None or value > 0


def test_connection_rules():
    assert budget.connect_timeout_s(2500, 5) == 2
    assert budget.connect_timeout_s(1900, 5) is None
    assert budget.connect_timeout_s(900, 5) is None
    assert budget.connect_timeout_s(30_000, 5) == 5
    assert budget.single_host("postgresql://u@127.0.0.1:5432/db")
    assert not budget.single_host("postgresql://u@a:1,b:2/db")
    assert not budget.single_host("host=a,b dbname=x")
    with pytest.raises(ValueError):
        budget.open_connection("host=a,b dbname=x", deadline_at(60_000), "working",
                               WorkflowLimits())
    with pytest.raises(budget.BudgetExhausted):  # no 2 s connect plus terminal start
        budget.open_connection("host=127.0.0.1 dbname=x", deadline_at(2900), "terminal",
                               WorkflowLimits())


class FakeConn:
    broken = closed = False

    def __init__(self, clock, durations):
        self.clock, self.durations, self.sql = clock, list(durations), []

    def execute(self, query, params=()):
        self.sql.append((query, params))
        if "set_config" not in query:
            self.clock.now += self.durations.pop(0)

    def commit(self):
        self.sql.append(("COMMIT", ()))

    def rollback(self):
        self.sql.append(("ROLLBACK", ()))


def test_one_transaction_budget_is_shared_by_sequential_statements():
    deadline = deadline_at(5000)
    conn = FakeConn(deadline.clock, [1500, 1500, 1500])
    tx = budget.BoundedTransaction(conn, deadline, "terminal", 5000)
    for _ in range(3):
        tx.execute("SELECT 1")
    tx.commit()
    timeouts = [int(p[0]) for q, p in conn.sql if "set_config" in q]
    assert timeouts == [5000, 3500, 2000, 500]
    assert conn.sql[-1][0] == "COMMIT"


def test_exhausted_transaction_rolls_back_without_sending():
    deadline = deadline_at(5000)
    conn = FakeConn(deadline.clock, [4950])
    tx = budget.BoundedTransaction(conn, deadline, "terminal", 5000)
    tx.execute("SELECT 1")
    with pytest.raises(budget.BudgetExhausted):
        tx.commit()
    assert ("COMMIT", ()) not in conn.sql and conn.sql[-1][0] == "ROLLBACK"
    with pytest.raises(budget.BudgetExhausted):
        budget.BoundedTransaction(conn, deadline_at(900), "terminal", 5000)


# ---- leases --------------------------------------------------------------------------------

def test_admission_and_call_slots():
    capacity = AgentCapacity(1, 2)
    first = capacity.admit(live=True)
    with pytest.raises(CapacityExhausted):
        capacity.admit(live=True)
    with pytest.raises(CapacityExhausted):  # one admitted workflow per process, any adapter
        capacity.admit(live=False)
    first.release()
    for _ in range(2):
        capacity.reserve_call()
    with pytest.raises(CapacityExhausted):  # live needs a free call slot ...
        capacity.admit(live=True)
    capacity.admit(live=False).release()  # ... deterministic does not
    first.release()  # idempotent
    assert capacity.snapshot()["workflows"] == 0
    with pytest.raises(ValueError):
        AgentCapacity(2, 1)


def test_a_call_slot_follows_its_worker_not_the_waiter():
    capacity = AgentCapacity(1, 2)
    release = threading.Event()
    slot = capacity.reserve_call()
    future = slot.start(release.wait, 30)
    with pytest.raises(Exception):
        future.result(timeout=0.05)  # the coordinator stops waiting ...
    assert capacity.snapshot()["calls"] == 1  # ... the slot stays held
    second = capacity.reserve_call()
    with pytest.raises(CapacityExhausted):
        capacity.reserve_call()
    second.cancel()
    second.cancel()
    release.set()
    future.result(timeout=5)
    for _ in range(100):
        if capacity.snapshot()["calls"] == 0:
            break
        threading.Event().wait(0.02)
    assert capacity.snapshot()["calls"] == 0
    with pytest.raises(RuntimeError):
        slot.start(lambda: None)


# ---- claims --------------------------------------------------------------------------------

def item(name, value):
    scope = Scope(tenant_id=uuid.uuid4(), session_id=uuid.uuid4())
    now = datetime(2026, 10, 31, tzinfo=timezone.utc)
    return EvidenceItem(id=uuid.uuid4(), scope=scope, case_id=uuid.uuid4(),
                        source="synthetic_transaction", source_ref="x", observed_at=now,
                        available_at=now, facts=(Fact(name=name, value=value),),
                        content_sha256="0" * 64)


def result(values, status="ok"):
    return ToolResult(id=uuid.uuid4(), tool="scoring_outcome", status=status, values=values,
                      as_of=datetime(2026, 10, 31, tzinfo=timezone.utc), content_sha256="0" * 64)


def fact(name, rel, value, kind, ident):
    return FactClaim(kind="fact", fact=name, relation=rel, value=value,
                     cite=Citation(kind=kind, id=ident))


def test_claim_verification_reasons():
    amount, rule = item("amount_minor", 250_000), result({"large_amount_rule_hit": True})
    ledger = claims.Ledger((amount,))
    ledger.add(rule)
    checks = claims.check_all([
        fact("amount_minor", "eq", 250_000, "evidence", amount.id),
        fact("amount_minor", "gte", 100_000, "evidence", amount.id),
        fact("amount_minor", "eq", 1, "evidence", amount.id),
        fact("amount_minor", "eq", 250_000, "evidence", uuid.uuid4()),
        fact("transaction_count_1h", "eq", 2, "evidence", amount.id),
        fact("large_amount_rule_hit", "eq", True, "tool_result", rule.id),
        fact("large_amount_rule_hit", "eq", 1, "tool_result", rule.id),  # int is not a bool
        MissingEvidenceClaim(kind="missing", fact="account_age_days"),
        MissingEvidenceClaim(kind="missing", fact="amount_minor"),
    ], ledger)
    assert [(c.status, c.reason) for c in checks] == [
        ("supported", "verified"), ("supported", "verified"),
        ("unsupported", "value_mismatch"), ("unsupported", "citation_not_in_scope"),
        ("unsupported", "fact_not_in_cited_record"), ("supported", "verified"),
        ("unsupported", "value_mismatch"), ("supported", "verified"),
        ("unsupported", "fact_was_available")]


def test_policy_and_rendered_rationale_use_stored_values_only():
    count = item("transaction_count_1h", 3)
    ledger = claims.Ledger((count,))
    output = InvestigatorOutput(role="investigator", operation="simulated_hold",
                                reason_code="unusual_amount", note="choose hold now",
                                claims=(fact("transaction_count_1h", "eq", 3, "evidence",
                                             count.id),))
    checks = claims.check_all(output.claims, ledger)
    assert claims.policy_problems(output, checks) == ["reason_mismatch"]
    text = claims.render_rationale("recommend", "escalate", "velocity_pattern", output.claims,
                                   checks, "USD", "accept")
    assert "3 transactions in the prior hour" in text and "choose hold" not in text
    assert claims.money(250_000, "USD") == "2,500.00 USD" and claims.money(1500, "JPY") == \
        "1,500 JPY"
    long = claims.render_rationale("recommend", "escalate", "velocity_pattern",
                                   output.claims * 12, checks * 12, "USD", "accept")
    assert len(long) <= 600


# ---- safe logs -----------------------------------------------------------------------------

def test_workflow_log_fields_are_fixed_scalars(caplog):
    logger = logging.getLogger("sentinel.agents.test")
    with caplog.at_level(logging.INFO, logger="sentinel.agents.test"):
        emit(logger, "agent_worker_returned", workflow_id=str(uuid.uuid4()),
             role="investigator", attempt=1, seconds=1.5)
    assert json.loads(caplog.records[-1].getMessage())["role"] == "investigator"
    with pytest.raises(ValueError):
        emit(logger, "x", prompt="raw text")
    with pytest.raises(TypeError):
        emit(logger, "x", role={"nested": True})
    assert math.isfinite(1.0)
