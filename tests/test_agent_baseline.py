"""G3B behaviour visible through interfaces that already exist on the accepted base 2919f76.

These are the failing-first regressions: they use only pre-existing entry points (operator
configuration, the migrated schema, the HTTP investigate route and the API document), so on
the base they fail for a behavioural reason, not because a new module cannot be imported."""
import uuid
from datetime import timedelta
from pathlib import Path

import psycopg
from fastapi.testclient import TestClient

from sentinel import investigators
from sentinel.api import create_app
from sentinel.service import Sentinel

ROOT = Path(__file__).resolve().parents[1]
ANALYST = frozenset({"ingest_transaction", "read_case", "approve_action",
                     "execute_simulated_action"})


def test_three_role_is_an_explicit_operator_mode(monkeypatch):
    monkeypatch.setenv("SENTINEL_INVESTIGATOR", "three-role")
    monkeypatch.delenv("SENTINEL_AGENT_ADAPTER", raising=False)
    workflow = investigators.from_environment()
    assert workflow.config.name == "three-role-workflow"
    monkeypatch.setenv("SENTINEL_INVESTIGATOR", "deterministic")
    assert investigators.from_environment().config.name == "deterministic-investigator"


def test_migration_adds_scoped_workflow_and_append_only_step_tables(database_url):
    with psycopg.connect(database_url) as conn:
        tables = {row[0] for row in conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'")}
        columns = {row[0] for row in conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'agent_runs'")}
    assert {"agent_workflows", "agent_steps"} <= tables
    assert {"workflow_id", "attempt"} <= columns


def test_three_role_investigation_runs_three_roles_through_the_existing_route(
        database_url, clock, monkeypatch):
    monkeypatch.setenv("SENTINEL_INVESTIGATOR", "three-role")
    monkeypatch.delenv("SENTINEL_AGENT_ADAPTER", raising=False)
    service = Sentinel(database_url, investigators.from_environment(), clock)
    client = TestClient(create_app(service))
    token = service.create_session(ANALYST)[0]
    auth = {"Authorization": f"Bearer {token}"}
    account = str(uuid.uuid4())
    for i, (minor, minutes) in enumerate([(4000, 20), (3500, 40), (250_000, 0)]):
        body = {"external_id": f"base-{i}", "account_id": account, "direction": "debit",
                "amount": {"currency": "USD", "minor_units": minor, "currency_exponent": 2},
                "occurred_at": (clock() - timedelta(minutes=minutes)).isoformat()}
        response = client.post("/v1/transactions", json=body, headers=auth)
        assert response.status_code == 201
    case = response.json()["case"]
    assert case["pins"]["tool_config"]["name"] == "agent-read-tools"
    result = client.post(f"/v1/cases/{case['id']}/investigations",
                         json={"expected_revision": 1}, headers=auth)
    assert result.status_code == 200, result.text
    detail = result.json()
    assert detail["case"]["state"] == "awaiting_approval"
    assert [r["run"]["role"] for r in detail["agent_runs"]] == [
        "evidence_analyst", "investigator", "reviewer"]


def test_api_documents_both_additive_workflow_codes():
    text = (ROOT / "docs" / "api" / "README.md").read_text(encoding="utf-8")
    assert "agent_capacity_exhausted" in text and "investigation_outcome_unknown" in text
