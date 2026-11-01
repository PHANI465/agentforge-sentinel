"""Server-side claim verification, policy consistency and rendered rationale (G3A §5).

A citation that exists proves only that the record exists in scope; a claim is supported
only when the cited record (an EvidenceItem of this case, or an `ok` ToolResult recorded in
this workflow) holds that fact and its stored value satisfies the relation. Booleans and
integers are never interchangeable. The rationale shown to the human is rendered from
supported claims and stored values only; role notes never reach it.
"""
from __future__ import annotations

from sentinel.contracts.agents import ClaimCheck, FactClaim, MissingEvidenceClaim, ToolResult
from sentinel.contracts.v1 import CURRENCY_EXPONENT, EvidenceItem

VELOCITY_FACTS = {"transaction_count_1h", "history_count_24h", "history_count_7d"}
AMOUNT_FACTS = {"amount_minor", "large_amount_rule_hit", "history_median_amount_minor_30d",
                "history_max_amount_minor_30d"}


class Ledger:
    """Everything a claim may cite: this case's evidence and this workflow's tool results."""

    def __init__(self, evidence: tuple[EvidenceItem, ...]):
        self.evidence = {item.id: {f.name: f.value for f in item.facts} for item in evidence}
        self.results: dict = {}

    def add(self, result: ToolResult) -> None:
        self.results[result.id] = result

    def available(self, fact: str) -> bool:
        return any(fact in values for values in self.evidence.values()) or any(
            r.status == "ok" and fact in r.values for r in self.results.values())

    def value(self, fact: str):
        for values in self.evidence.values():
            if fact in values:
                return values[fact]
        for result in self.results.values():
            if result.status == "ok" and fact in result.values:
                return result.values[fact]
        return None


def _same_kind(a, b) -> bool:
    return isinstance(a, bool) == isinstance(b, bool)


def _holds(relation: str, stored, claimed) -> bool:
    if not _same_kind(stored, claimed):
        return False
    if isinstance(stored, bool):
        return relation == "eq" and stored == claimed
    return {"eq": stored == claimed, "gte": stored >= claimed,
            "lte": stored <= claimed}[relation]


def check(index: int, claim, ledger: Ledger) -> ClaimCheck:
    def result(status, reason):
        return ClaimCheck(index=index, status=status, reason=reason)
    if isinstance(claim, MissingEvidenceClaim):
        if ledger.available(claim.fact):
            return result("unsupported", "fact_was_available")
        return result("supported", "verified")
    assert isinstance(claim, FactClaim)
    if claim.cite.kind == "evidence":
        values = ledger.evidence.get(claim.cite.id)
    else:
        cited = ledger.results.get(claim.cite.id)
        values = cited.values if cited is not None and cited.status == "ok" else None
    if values is None:
        return result("unsupported", "citation_not_in_scope")
    if claim.fact not in values:
        return result("unsupported", "fact_not_in_cited_record")
    if not _holds(claim.relation, values[claim.fact], claim.value):
        return result("unsupported", "value_mismatch")
    return result("supported", "verified")


def check_all(claims, ledger: Ledger) -> tuple[ClaimCheck, ...]:
    return tuple(check(i, c, ledger) for i, c in enumerate(claims))


def policy_problems(output, checks: tuple[ClaimCheck, ...]) -> list[str]:
    """Server consistency checks for an investigator output, independent of the reviewer."""
    supported = {c.fact for c, k in zip(output.claims, checks)
                 if k.status == "supported" and isinstance(c, FactClaim)}
    problems = []
    if any(k.status != "supported" for k in checks):
        problems.append("unsupported_claim")
    if output.reason_code == "velocity_pattern" and not supported & VELOCITY_FACTS:
        problems.append("reason_mismatch")
    if output.reason_code == "unusual_amount" and not supported & AMOUNT_FACTS:
        problems.append("reason_mismatch")
    if output.operation == "simulated_hold" and output.reason_code == "insufficient_evidence":
        problems.append("operation_not_supported")
    return problems


def money(minor: int, currency: str) -> str:
    exponent = CURRENCY_EXPONENT[currency]
    if exponent == 0:
        return f"{minor:,} {currency}"
    whole, frac = divmod(minor, 10 ** exponent)
    return f"{whole:,}.{frac:0{exponent}d} {currency}"


def _phrase(claim: FactClaim, currency: str) -> str:
    fact, value, rel = claim.fact, claim.value, {"eq": "", "gte": "at least ", "lte": "at most "}[
        claim.relation]
    cite = f"[{claim.cite.kind} …{str(claim.cite.id)[-4:]}]"
    if fact == "amount_minor":
        text = f"amount {rel}{money(value, currency)}"
    elif fact == "large_amount_rule_hit":
        text = "large-amount rule hit" if value else "large-amount rule not hit"
    elif fact == "transaction_count_1h":
        text = f"{rel}{value} transactions in the prior hour"
    elif fact in ("history_count_24h", "history_count_7d"):
        text = f"{rel}{value} transactions in the prior {fact.rsplit('_', 1)[1]}"
    elif fact == "history_median_amount_minor_30d":
        text = f"30-day median same-currency payment {rel}{money(value, currency)}"
    elif fact == "history_max_amount_minor_30d":
        text = f"30-day maximum same-currency payment {rel}{money(value, currency)}"
    elif fact == "account_age_days":
        text = f"account age {rel}{value} days"
    else:
        text = f"{fact} {rel}{value}"
    return f"{text} {cite}"


def render_rationale(kind: str, operation: str, reason: str, claims, checks, currency: str,
                     verdict: str | None) -> str:
    """Bounded (<=600 characters) display text from supported claims and stored values."""
    head = ("Abstained: escalate (insufficient_evidence)." if kind == "abstain"
            else f"{operation} ({reason}).")
    parts = [_phrase(c, currency) for c, k in zip(claims, checks)
             if k.status == "supported" and isinstance(c, FactClaim)]
    unsupported = sum(1 for k in checks if k.status != "supported")
    text = head + (" Supported: " + "; ".join(parts) + "." if parts else "")
    if unsupported:
        text += f" {unsupported} claim(s) failed verification."
    if verdict:
        text += f" Reviewer: {verdict}."
    return text if len(text) <= 600 else text[:597] + "..."
