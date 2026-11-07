"""The frozen development catalog, read by evaluator tools after case execution only.

The `evaluator` section (acceptable outcomes, abstention labels) never reaches a role,
tool or prompt: the runner seeds from `runtime` alone, and only the supervisor's
post-run quality check and the offline scorer call these functions.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "docs" / "evals" / "agents" / "dev-cases-v1.json"
PERMITS_ABSTENTION = frozenset({"required", "appropriate", "acceptable_not_preferred"})


@lru_cache(maxsize=1)
def cases() -> dict:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    return {case["id"]: case for case in data["cases"]}


def runtime_digest(case_id: str) -> str:
    """The same digest the runner records (sorted, compact JSON of `runtime`)."""
    body = json.dumps(cases()[case_id]["runtime"], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode()).hexdigest()


def acceptable(case_id: str, disposition: dict) -> bool:
    """protocol-v1 §3: (operation, reason) in the case's acceptable list, or an explicit
    abstention the case permits. A hold on a case not listing hold is never acceptable."""
    expected = cases()[case_id]["evaluator"]
    pair = {"operation": disposition.get("operation"),
            "reason_code": disposition.get("reason_code")}
    if pair in expected["acceptable"]:
        return True
    return disposition.get("kind") == "abstain" and \
        expected["abstention"] in PERMITS_ABSTENTION and pair["operation"] != "simulated_hold"


def wrong_hold(case_id: str, disposition: dict | None) -> bool:
    """A completed hold on a case whose acceptable list has no hold (e.g. D03, D04, D11)."""
    if not disposition or disposition.get("operation") != "simulated_hold":
        return False
    return all(item["operation"] != "simulated_hold"
               for item in cases()[case_id]["evaluator"]["acceptable"])
