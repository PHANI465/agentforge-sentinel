"""The four allowlisted read-only tools (`agent-read-tools` t1, G3A-design section 4).

A role can only *name* a tool (and a history window); it never supplies an identifier.
Scope comes from the TrustedContext, the case/alert/transaction from records loaded and
snapshot-verified at the claim, and the account from that stored transaction. Queries run
through the workflow's BoundedTransaction on the API's runtime connection. Decision time T
is alert.created_at: only rows ingested (profiles provisioned) by T count, so results are
reproducible; the alerted row itself is excluded. Nothing here reads simulator truth,
labels, benchmark gold or another session.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta

from sentinel import scoring
from sentinel.contracts.agents import TOOL_RESULT_NAMESPACE, ToolResult
from sentinel.contracts.v1 import (
    Alert, Case, EvidenceItem, ScoringOutcome, Transaction, TrustedContext, canonical_digest,
)

TOOLS = ("case_evidence", "scoring_outcome", "account_history", "account_profile")
TOOL_PROFILE_DOCUMENT = {
    "profile": "agent-read-tools",
    "tools": {
        "case_evidence": {"arguments": [], "values": ["amount_minor", "transaction_count_1h"]},
        "scoring_outcome": {"arguments": [],
                            "values": ["large_amount_rule_hit", "prior_known_fraud (model)"]},
        "account_history": {"arguments": {"window": ["24h", "7d", "30d"]},
                            "values": {"24h": ["history_count_24h"], "7d": ["history_count_7d"],
                                       "30d": ["history_median_amount_minor_30d",
                                               "history_max_amount_minor_30d"]}},
        "account_profile": {"arguments": [], "values": ["account_age_days"]},
    },
    "decision_time": "alert.created_at; rows ingested/provisioned by then; alerted row excluded",
    "scope": "TrustedContext tenant and session; case, account from stored records",
}
WINDOWS = {"24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30)}


@dataclass(frozen=True)
class CaseFacts:
    """Records loaded once in the claim transaction (snapshot verified there)."""
    ctx: TrustedContext
    case: Case
    alert: Alert
    txn: Transaction
    scoring: ScoringOutcome | None
    evidence: tuple[EvidenceItem, ...]

    @property
    def decision_time(self):
        return self.alert.created_at


def _result(facts: CaseFacts, tool: str, status: str, *, window: str | None = None,
            values: dict | None = None, evidence_ids=(), denial: str | None = None
            ) -> ToolResult:
    values = values or {}
    content = {"tool": tool, "window": window, "status": status, "denial": denial,
               "values": dict(sorted(values.items())),
               "evidence_ids": sorted(str(i) for i in evidence_ids),
               "as_of": facts.decision_time.isoformat()}
    return ToolResult(id=uuid.uuid4(), tool=tool, window=window, status=status,
                      denial=denial, values=values, evidence_ids=tuple(evidence_ids),
                      as_of=facts.decision_time,
                      content_sha256=canonical_digest(TOOL_RESULT_NAMESPACE, content))


def denied(facts: CaseFacts, tool: str, denial: str, window: str | None = None) -> ToolResult:
    return _result(facts, tool, "denied", window=window if tool == "account_history" else None,
                   denial=denial)


def run_tool(tx, facts: CaseFacts, request, statement_cap_ms: int) -> ToolResult:
    """Execute one validated ToolRequest. `tx` is the step's BoundedTransaction."""
    tool = request.tool
    if tool == "case_evidence":
        values = {fact.name: fact.value for item in facts.evidence for fact in item.facts
                  if fact.name in ("amount_minor", "transaction_count_1h")}
        return _result(facts, tool, "ok", values=values,
                       evidence_ids=tuple(item.id for item in facts.evidence))
    if tool == "scoring_outcome":
        values = {"large_amount_rule_hit": scoring.is_large_amount(facts.txn)}
        if facts.scoring is not None and facts.scoring.inputs is not None:
            values["prior_known_fraud"] = facts.scoring.inputs.values["prior_known_fraud"]
        return _result(facts, tool, "ok", values=values)
    tenant, session = facts.ctx.scope.tenant_id, facts.ctx.scope.session_id
    if tool == "account_history":
        window = request.window
        since = facts.txn.occurred_at - WINDOWS[window]
        rows = tx.execute(
            "SELECT (body->'amount'->>'minor_units')::bigint AS minor,"
            " body->'amount'->>'currency' AS currency FROM transactions"
            " WHERE tenant_id = %s AND session_id = %s AND account_id = %s"
            " AND occurred_at >= %s AND occurred_at < %s AND ingested_at <= %s AND id <> %s",
            (tenant, session, facts.txn.account_id, since, facts.txn.occurred_at,
             facts.decision_time, facts.txn.id), cap_ms=statement_cap_ms).fetchall()
        if window in ("24h", "7d"):
            return _result(facts, tool, "ok", window=window,
                           values={f"history_count_{window}": len(rows)})
        same = sorted(int(r["minor"]) for r in rows if r["currency"] == facts.txn.amount.currency)
        if not same:
            return _result(facts, tool, "unavailable", window=window)
        mid = len(same) // 2
        median = same[mid] if len(same) % 2 else (same[mid - 1] + same[mid]) // 2
        return _result(facts, tool, "ok", window=window,
                       values={"history_median_amount_minor_30d": median,
                               "history_max_amount_minor_30d": same[-1]})
    if tool == "account_profile":
        row = tx.execute(
            "SELECT opened_at, provisioned_at FROM account_profiles WHERE tenant_id = %s"
            " AND session_id = %s AND account_id = %s",
            (tenant, session, facts.txn.account_id), cap_ms=statement_cap_ms).fetchone()
        decision = facts.decision_time
        if row is None or row["provisioned_at"] > decision or row["opened_at"] > decision:
            return _result(facts, tool, "unavailable")
        return _result(facts, tool, "ok",
                       values={"account_age_days": (decision - row["opened_at"]).days})
    raise ValueError("unknown tool")  # unreachable: requests are schema-validated
