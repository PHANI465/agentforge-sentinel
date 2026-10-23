"""Deterministic rule scoring. Scores are heuristics, not fraud probabilities.

Each configuration below is content-addressed so cases pin exactly what produced them.
"""
from __future__ import annotations

from sentinel.contracts.v1 import ArtifactRef, Transaction, canonical_digest


def artifact(name: str, version: str, document: dict) -> ArtifactRef:
    return ArtifactRef(name=name, version=version,
                       sha256=canonical_digest("sentinel.artifact.v1", document))


DATASET_CONFIG = {"source": "api-ingest", "synthetic_only": True}
# Large-amount cutoffs in minor units, per currency; deliberately crude placeholders.
RULE_CONFIG = {
    "large_amount_minor": {"USD": 100_000, "GBP": 100_000, "INR": 8_000_000, "JPY": 150_000},
    "large_amount_points": 0.6,
    "velocity_points_per_prior": 0.2,
    "velocity_points_cap": 0.6,
}
FEATURE_CONFIG = {
    "amount_minor": "transaction amount magnitude",
    "transaction_count_1h": "prior transactions for the account in [t-1h, t), same scope",
}
THRESHOLD_CONFIG = {"alert_at_or_above": 0.5}
POLICY_CONFIG = {
    "approval_ttl_seconds": 300,
    "operations": ["simulated_hold", "escalate"],
    "execution": "same human approver, simulated only",
}
TOOL_CONFIG = {"tools": []}

DATASET = artifact("api-synthetic-ingest", "d1", DATASET_CONFIG)
SCORER = artifact("velocity-amount-rules", "r1", RULE_CONFIG)
FEATURES = artifact("thin-path-features", "f1", FEATURE_CONFIG)
THRESHOLD_POLICY = artifact("alert-threshold", "t1", THRESHOLD_CONFIG)
ACTION_POLICY = artifact("simulated-action-policy", "p1", POLICY_CONFIG)
TOOL_PROFILE = artifact("no-tools", "n1", TOOL_CONFIG)
THRESHOLD = THRESHOLD_CONFIG["alert_at_or_above"]
APPROVAL_TTL_SECONDS = POLICY_CONFIG["approval_ttl_seconds"]


def is_large_amount(transaction: Transaction) -> bool:
    amount = transaction.amount
    return amount.minor_units >= RULE_CONFIG["large_amount_minor"][amount.currency]


def rule_score(transaction: Transaction, prior_count_1h: int) -> float:
    score = RULE_CONFIG["large_amount_points"] if is_large_amount(transaction) else 0.0
    score += min(RULE_CONFIG["velocity_points_cap"],
                 RULE_CONFIG["velocity_points_per_prior"] * prior_count_1h)
    return round(min(1.0, score), 6)
