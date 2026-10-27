"""Consistency check for docs/evals/agents/dev-cases-v1.json (development cases only).

    uv run --locked python docs/evals/agents/dev_cases.py

Checks, without any database, model or provider:
- structure: runtime inputs and evaluator expectations are separate typed sections, and the
  runtime section has no evaluator-only field (no expected labels leak into runtime inputs);
- each case's expected alert, rule score and transaction_count_1h equal what the real
  sentinel.scoring rules compute from its runtime inputs;
- the history facts (24h/7d counts, 30-day same-currency median/max) equal the tool
  definitions in docs/agents/G3A-design.md section 4, and every fact is either observable or
  listed as unavailable, never both;
- abstention labels agree with the acceptable outcomes.
"""
from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, StrictBool, StrictInt

from sentinel import scoring
from sentinel.contracts.v1 import Money, Scope, Transaction

CATALOG = Path(__file__).resolve().parent / "dev-cases-v1.json"
FACTS = {"amount_minor", "transaction_count_1h", "large_amount_rule_hit", "history_count_24h",
         "history_count_7d", "history_median_amount_minor_30d", "history_max_amount_minor_30d",
         "account_age_days", "prior_known_fraud"}
EXPONENT = {"USD": 2, "GBP": 2, "INR": 2, "JPY": 0}


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Row(Strict):
    minutes_before: StrictInt
    amount_minor: StrictInt
    currency: Literal["USD", "GBP", "INR", "JPY"]
    direction: Literal["debit", "credit"]


class Alerted(Strict):
    amount_minor: StrictInt
    currency: Literal["USD", "GBP", "INR", "JPY"]
    direction: Literal["debit", "credit"]
    external_id: str


class Runtime(Strict):
    scorer: Literal["rule", "model"]
    account_profile: dict | None
    alerted: Alerted
    history: list[Row]
    faults: list[dict]


class Outcome(Strict):
    operation: Literal["simulated_hold", "escalate"]
    reason_code: Literal["velocity_pattern", "unusual_amount", "insufficient_evidence"]


class Evaluator(Strict):
    expected_alert: StrictBool
    expected_rule_score: float
    observable_facts: dict[str, StrictInt | StrictBool]
    unavailable_facts: list[str]
    acceptable: list[Outcome]
    abstention: Literal["required", "appropriate", "acceptable_not_preferred", "not_applicable"]
    forbidden_claims: list[str]
    expected_failure_behavior: str | None


class Implemented(Strict):
    deterministic_i1: StrictBool
    single_live_c1: StrictBool
    three_role: StrictBool
    note: str | None = None


class Case(Strict):
    id: str
    title: str
    runtime: Runtime
    evaluator: Evaluator
    implemented: Implemented


class Catalog(Strict):
    catalog: Literal["sentinel-agent-dev-cases"]
    version: Literal["v1"]
    purpose: str
    time_unit_note: str
    cases: list[Case]


def expected_facts(rt: Runtime) -> dict[str, int | bool]:
    t = datetime(2026, 10, 27, 15, 0, tzinfo=timezone.utc)
    txn = Transaction(
        id=uuid.uuid4(), scope=Scope(tenant_id=uuid.uuid4(), session_id=uuid.uuid4()),
        external_id="x", account_id=uuid.uuid4(), direction=rt.alerted.direction,
        amount=Money(currency=rt.alerted.currency, minor_units=rt.alerted.amount_minor,
                     currency_exponent=EXPONENT[rt.alerted.currency]),
        occurred_at=t, ingested_at=t, dataset=scoring.DATASET)

    def within(minutes: int) -> list[Row]:
        return [r for r in rt.history if 0 < r.minutes_before <= minutes]
    count_1h = len([r for r in rt.history if 0 < r.minutes_before <= 60])
    facts: dict[str, int | bool] = {
        "amount_minor": rt.alerted.amount_minor, "transaction_count_1h": count_1h,
        "large_amount_rule_hit": scoring.is_large_amount(txn),
        "history_count_24h": len(within(24 * 60)), "history_count_7d": len(within(7 * 24 * 60)),
    }
    same = sorted(r.amount_minor for r in within(30 * 24 * 60)
                  if r.currency == rt.alerted.currency)
    if same:
        mid = len(same) // 2
        facts["history_median_amount_minor_30d"] = (
            same[mid] if len(same) % 2 else (same[mid - 1] + same[mid]) // 2)
        facts["history_max_amount_minor_30d"] = same[-1]
    facts["_score"] = scoring.rule_score(txn, count_1h)
    return facts


def check(catalog: Catalog) -> list[str]:
    problems = []
    ids = [c.id for c in catalog.cases]
    if len(set(ids)) != len(ids):
        problems.append("duplicate case ids")
    for case in catalog.cases:
        ev, rt = case.evaluator, case.runtime
        where = f"{case.id}:"
        computed = expected_facts(rt)
        score = computed.pop("_score")
        if abs(score - ev.expected_rule_score) > 1e-9:
            problems.append(f"{where} rule score {score} != expected {ev.expected_rule_score}")
        if (score >= scoring.THRESHOLD) != ev.expected_alert:
            problems.append(f"{where} alert disagrees with the real threshold")
        for name, value in ev.observable_facts.items():
            if name not in FACTS:
                problems.append(f"{where} unknown fact {name}")
            elif computed.get(name) != value:
                problems.append(f"{where} {name}={value} but the inputs give {computed.get(name)}")
        unknown = set(ev.unavailable_facts) - FACTS
        both = set(ev.unavailable_facts) & set(ev.observable_facts)
        if unknown or both:
            problems.append(f"{where} unavailable facts invalid {sorted(unknown | both)}")
        missing = set(computed) - set(ev.observable_facts) - set(ev.unavailable_facts)
        if missing:
            problems.append(f"{where} computable facts not declared {sorted(missing)}")
        if ev.abstention == "required" and any(
                (o.operation, o.reason_code) != ("escalate", "insufficient_evidence")
                for o in ev.acceptable):
            problems.append(f"{where} abstention required but a committal outcome is acceptable")
        if ev.abstention == "not_applicable" and ev.acceptable:
            problems.append(f"{where} not_applicable abstention needs no acceptable outcome")
        if ev.acceptable == [] and ev.expected_failure_behavior is None:
            problems.append(f"{where} no acceptable outcome and no expected failure behaviour")
    return problems


def main() -> int:
    catalog = Catalog.model_validate(json.loads(CATALOG.read_text(encoding="utf-8")))
    problems = check(catalog)
    for problem in problems:
        print(problem)
    if not problems:
        three = sum(c.implemented.three_role for c in catalog.cases)
        print(f"{len(catalog.cases)} development cases consistent with sentinel.scoring; "
              f"three-role implemented in {three}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
