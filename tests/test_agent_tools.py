"""The four read-only tools on real PostgreSQL through the runtime role: decision-time bounds,
scope, currency semantics, profile availability and stable digests."""
import sys
import uuid
from datetime import timedelta
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

sys.path.insert(0, str(Path(__file__).resolve().parent / "support"))

import agent_cases as ac  # noqa: E402
from sentinel.agents.budget import BoundedTransaction, Deadline  # noqa: E402
from sentinel.agents.tools import CaseFacts, run_tool  # noqa: E402
from sentinel.contracts.agents import (  # noqa: E402
    AccountHistoryArgs, AccountProfileArgs, CaseEvidenceArgs, ScoringOutcomeArgs, WorkflowLimits,
)
from sentinel.contracts.v1 import Alert, Case, EvidenceItem, Transaction, TransactionInput  # noqa: E402
from sentinel.investigators import DeterministicInvestigator  # noqa: E402
from sentinel.service import Sentinel  # noqa: E402


def txn(external_id, account, minor, occurred, currency="USD"):
    exponent = 0 if currency == "JPY" else 2
    return TransactionInput.model_validate({
        "external_id": external_id, "account_id": str(account), "direction": "debit",
        "amount": {"currency": currency, "minor_units": minor, "currency_exponent": exponent},
        "occurred_at": occurred.isoformat()})


def facts_for(svc, ctx, case_id):
    detail = svc.get_case(ctx, case_id)
    return CaseFacts(ctx=ctx, case=Case.model_validate(detail["case"]),
                     alert=Alert.model_validate(detail["alert"]),
                     txn=Transaction.model_validate(detail["transaction"]), scoring=None,
                     evidence=tuple(EvidenceItem.model_validate(e) for e in detail["evidence"]))


def run(url, facts, request):
    with psycopg.connect(url, row_factory=dict_row, autocommit=False) as conn:
        tx = BoundedTransaction(conn, Deadline(WorkflowLimits()), "working", 5000)
        result = run_tool(tx, facts, request, 2000)
        tx.commit()
    return result


def test_history_is_bounded_scoped_and_currency_aware(database_url, clock):
    url = ac.runtime_url(database_url)
    svc = Sentinel(url, DeterministicInvestigator(), clock)
    ctx = svc.authenticate(ac.session(url, clock))
    other_ctx = svc.authenticate(ac.session(url, clock))
    account, stranger = uuid.uuid4(), uuid.uuid4()
    now = clock()
    svc.ingest(ctx, txn("h1", account, 4000, now - timedelta(minutes=20)))
    svc.ingest(ctx, txn("h2", account, 9000, now - timedelta(hours=30)))
    svc.ingest(ctx, txn("h3", account, 5000, now - timedelta(days=10), currency="GBP"))
    svc.ingest(ctx, txn("old", account, 7000, now - timedelta(days=40)))
    svc.ingest(ctx, txn("stranger", stranger, 8000, now - timedelta(minutes=5)))
    svc.ingest(other_ctx, txn("foreign", account, 6000, now - timedelta(minutes=5)))
    case = svc.ingest(ctx, txn("alert", account, 250_000, now))["case"]["id"]
    clock.advance(seconds=30)  # a backdated row ingested after the decision time
    svc.ingest(ctx, txn("late", account, 3000, now - timedelta(minutes=10)))
    facts = facts_for(svc, ctx, case)
    day = run(url, facts, AccountHistoryArgs(tool="account_history", window="24h"))
    week = run(url, facts, AccountHistoryArgs(tool="account_history", window="7d"))
    month = run(url, facts, AccountHistoryArgs(tool="account_history", window="30d"))
    assert day.values == {"history_count_24h": 1}  # h1 only: not late, foreign or stranger
    assert week.values == {"history_count_7d": 2}  # h1, h2
    assert month.values == {"history_median_amount_minor_30d": 6500,
                            "history_max_amount_minor_30d": 9000}  # USD only: h1, h2
    assert month.as_of == facts.alert.created_at
    again = run(url, facts, AccountHistoryArgs(tool="account_history", window="30d"))
    assert again.content_sha256 == month.content_sha256 and again.id != month.id
    evidence = run(url, facts, CaseEvidenceArgs(tool="case_evidence"))
    assert evidence.values == {"amount_minor": 250_000, "transaction_count_1h": 1}
    assert set(evidence.evidence_ids) == {e.id for e in facts.evidence}
    assert run(url, facts, ScoringOutcomeArgs(tool="scoring_outcome")).values == {
        "large_amount_rule_hit": True}


def test_profile_must_be_available_at_the_decision_time(database_url, clock):
    url = ac.runtime_url(database_url)
    owner = Sentinel(database_url, DeterministicInvestigator(), clock)
    svc = Sentinel(url, DeterministicInvestigator(), clock)
    ctx = svc.authenticate(ac.session(url, clock))
    early, late = uuid.uuid4(), uuid.uuid4()
    owner.provision_accounts(ctx.scope.tenant_id, ctx.scope.session_id, [
        {"account_id": early, "home_currency": "USD", "opened_at": clock() - timedelta(days=40)}])
    first = svc.ingest(ctx, txn("e", early, 250_000, clock()))["case"]["id"]
    second = svc.ingest(ctx, txn("l", late, 250_000, clock()))["case"]["id"]
    clock.advance(seconds=5)
    owner.provision_accounts(ctx.scope.tenant_id, ctx.scope.session_id, [
        {"account_id": late, "home_currency": "USD", "opened_at": clock() - timedelta(days=90)}])
    request = AccountProfileArgs(tool="account_profile")
    assert run(url, facts_for(svc, ctx, first), request).values == {"account_age_days": 40}
    assert run(url, facts_for(svc, ctx, second), request).status == "unavailable"
    # A later upsert of the early account cannot rewrite its decision-time value either.
    clock.advance(seconds=5)
    owner.provision_accounts(ctx.scope.tenant_id, ctx.scope.session_id, [
        {"account_id": early, "home_currency": "USD", "opened_at": clock() - timedelta(days=1)}])
    assert run(url, facts_for(svc, ctx, first), request).status == "unavailable"


def test_runtime_role_cannot_rewrite_workflow_steps(database_url, clock, monkeypatch):
    monkeypatch.setenv("SENTINEL_INVESTIGATOR", "three-role")
    url = ac.runtime_url(database_url)
    svc, ctx = (lambda s: (s, s.authenticate(ac.session(url, clock))))(
        ac.service(url, ac.workflow(), clock))
    case = ac.seed(svc, ctx, "D01", clock)["case"]["id"]
    svc.investigate(ctx, case, 1)
    with psycopg.connect(url) as conn:
        for statement in ("UPDATE agent_steps SET payload = NULL",
                          "DELETE FROM agent_steps", "TRUNCATE agent_steps",
                          "DELETE FROM agent_workflows"):
            try:
                conn.execute(statement)
            except psycopg.errors.InsufficientPrivilege:
                conn.rollback()
            else:
                raise AssertionError(f"runtime role could run: {statement}")
    with psycopg.connect(database_url) as conn:  # running-workflow uniqueness holds
        row = conn.execute("SELECT id, tenant_id, session_id, case_id, case_revision, body"
                           " FROM agent_workflows").fetchone()
        try:
            for _ in range(2):
                conn.execute("INSERT INTO agent_workflows (id, tenant_id, session_id, case_id,"
                             " case_revision, status, started_at, deadline_at, body)"
                             " VALUES (%s, %s, %s, %s, %s, 'running', now(),"
                             " now() + interval '1 minute', %s)",
                             (uuid.uuid4(), row[1], row[2], row[3], row[4],
                              psycopg.types.json.Jsonb(row[5])))
        except psycopg.errors.UniqueViolation:
            conn.rollback()
        else:
            raise AssertionError("two running workflows on one case")
