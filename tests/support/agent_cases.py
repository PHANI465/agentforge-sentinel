"""Test harness for the three-role workflow: development cases, fault adapters and clocks.

Only each case's `runtime` section is used to create data. `faults` are applied here, by
wrapping role adapters, coordinator hooks, clocks or an owner connection; `evaluator` data
is read by the tests only. Nothing from either reaches a role input.
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import timedelta
from pathlib import Path

import psycopg
from psycopg.conninfo import make_conninfo

from sentinel.agents import coordinator
from sentinel.agents.adapters import DeterministicRole, RoleResult
from sentinel.contracts.v1 import TransactionInput
from sentinel.db import roles
from sentinel.investigators import InvestigatorError
from sentinel.service import Sentinel

ROOT = Path(__file__).resolve().parents[2]
CATALOG = json.loads((ROOT / "docs/evals/agents/dev-cases-v1.json").read_text(encoding="utf-8"))
CASES = {case["id"]: case for case in CATALOG["cases"]}
ANALYST = frozenset({"ingest_transaction", "read_case", "approve_action",
                     "execute_simulated_action"})
EXPONENT = {"USD": 2, "GBP": 2, "INR": 2, "JPY": 0}


class SimulatedProcessDeath(BaseException):
    """Stands in for the API process dying: not an Exception, so no terminal write runs."""


class Monotonic:
    """Real elapsed milliseconds plus a test-controlled offset."""

    def __init__(self):
        self.offset = 0.0

    def __call__(self) -> float:
        return time.monotonic() * 1000 + self.offset

    def advance(self, ms: float) -> None:
        self.offset += ms


class FaultyRole:
    """Wraps a deterministic role. Per call (in order) it may: transform the output, raise a
    typed failure, return raw (even invalid) output, or block on an Event (a held worker).
    `live=True` makes the coordinator treat it as a provider call (call slot, timeout)."""

    def __init__(self, role: str, *, live: bool = False, timeout_seconds: int | None = None,
                 behaviours=None, record: list | None = None):
        self.base = DeterministicRole(role)
        self.role, self.config, self.principal_id = role, self.base.config, self.base.principal_id
        self.live = live
        self.timeout_seconds = timeout_seconds or self.base.timeout_seconds
        self.behaviours = list(behaviours or [])
        self.record = record
        self.calls = 0
        self.returned = threading.Event()

    def call(self, role_input: dict) -> RoleResult:
        self.calls += 1
        if self.record is not None:
            self.record.append((self.role, json.loads(json.dumps(role_input))))
        behaviour = self.behaviours.pop(0) if self.behaviours else None
        try:
            if behaviour is None:
                return self.base.call(role_input)
            kind = behaviour[0]
            if kind == "fail":
                raise InvestigatorError(behaviour[1])
            if kind == "raw":
                return RoleResult(behaviour[1](role_input), self.base.call(role_input).usage)
            if kind == "map":
                result = self.base.call(role_input)
                return RoleResult(behaviour[1](role_input, result.output), result.usage)
            if kind == "hold":
                behaviour[1].wait(60)
                return self.base.call(role_input)
            if kind == "die":
                raise SimulatedProcessDeath()
            if kind == "do":
                behaviour[1](role_input)
                return self.base.call(role_input)
            raise AssertionError(kind)
        finally:
            self.returned.set()


def workflow(**roles_kw) -> coordinator.Workflow:
    built = {}
    for role in coordinator.ROLES:
        built[role] = roles_kw.get(role) or DeterministicRole(role)
    return coordinator.Workflow(built)


OWNERS: dict[str, str] = {}


def runtime_url(database_url: str) -> str:
    """The production least-privilege runtime role for this test database."""
    role = f"sentinel_rt_{uuid.uuid4().hex[:10]}"
    roles.grant_runtime(database_url, role)
    url = make_conninfo(database_url, user=role)
    OWNERS[url] = database_url
    return url


def session(url: str, clock, capabilities=ANALYST):
    """Sessions are issued by the operator (the runtime role cannot); the API, tools and
    workflow then run as the runtime role."""
    from sentinel.investigators import DeterministicInvestigator
    owner = Sentinel(OWNERS[url], DeterministicInvestigator(), clock)
    return owner.create_session(capabilities)[0]


def service(url: str, investigator, clock, monotonic=None) -> Sentinel:
    return Sentinel(url, investigator, clock, monotonic=monotonic)


def seed(svc: Sentinel, ctx, case_id: str, clock, *, account=None, prefix=None) -> dict:
    """Ingest a case's runtime history and its alerted transaction; return the ingest
    result for the alerted one (its case)."""
    runtime = CASES[case_id]["runtime"]
    account = account or uuid.uuid4()
    alerted_id = runtime["alerted"]["external_id"] + (f".{prefix}" if prefix else "")
    prefix = prefix or f"{case_id.lower()}-{uuid.uuid4().hex[:6]}"
    for i, row in enumerate(runtime["history"]):
        svc.ingest(ctx, _input(f"{prefix}-h{i}", account, row,
                               clock() - timedelta(minutes=row["minutes_before"])))
    alerted = runtime["alerted"]
    return svc.ingest(ctx, _input(alerted_id, account, alerted, clock()))


def _input(external_id, account, row, occurred) -> TransactionInput:
    return TransactionInput.model_validate({
        "external_id": external_id, "account_id": str(account), "direction": row["direction"],
        "amount": {"currency": row["currency"], "minor_units": row["amount_minor"],
                   "currency_exponent": EXPONENT[row["currency"]]},
        "occurred_at": occurred.isoformat()})


def tool_values(url: str, case_id) -> dict:
    """Every value the case's workflows' ok tool results recorded."""
    values = {}
    with psycopg.connect(url) as conn:
        for (payload,) in conn.execute(
                "SELECT s.payload FROM agent_steps s WHERE s.case_id = %s"
                " AND s.body->>'kind' = 'tool_executed' ORDER BY s.seq", (case_id,)):
            if payload["status"] == "ok":
                values.update(payload["values"])
    return values


def workflows(url: str, case_id) -> list[dict]:
    with psycopg.connect(url) as conn:
        return [row[0] for row in conn.execute(
            "SELECT body FROM agent_workflows WHERE case_id = %s ORDER BY started_at, id",
            (case_id,))]


def steps(url: str, case_id) -> list[dict]:
    with psycopg.connect(url) as conn:
        return [row[0] for row in conn.execute(
            "SELECT body FROM agent_steps WHERE case_id = %s ORDER BY seq", (case_id,))]
