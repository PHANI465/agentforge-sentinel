"""Role adapters. A role receives only the server-rendered role input (typed fact values,
citations, enums and earlier roles' *checked* structured output) and returns raw output that
the coordinator validates; output is untrusted.

- Deterministic adapters (default): fixed rules, no provider, no call slot. They are a
  plumbing control and fixture, not evidence of multi-agent quality.
- ClaudeCliRoleAdapter (opt-in, local only): the existing ClaudeCliInvestigator isolation,
  reused unchanged: subscription preflight, scrubbed provider environment, empty working
  directory, no tools/MCP/settings/session, JSON-schema output, typed failures, stdout
  never logged.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from typing import Callable

from pydantic import TypeAdapter

from sentinel import investigators
from sentinel.contracts.agents import AnalystOutput, InvestigatorOutput, ReviewerOutput, Usage
from sentinel.contracts.v1 import ArtifactRef
from sentinel.investigators import InvestigatorError
from sentinel.scoring import artifact

OUTPUT_MODELS = {"evidence_analyst": AnalystOutput, "investigator": InvestigatorOutput,
                 "reviewer": ReviewerOutput}
VERSIONS = {"evidence_analyst": ("analyst", "a1"), "investigator": ("investigator", "i2"),
            "reviewer": ("reviewer", "r1")}
NOT_APPLICABLE = Usage(measured=False, source="not_applicable")
UNKNOWN = Usage(measured=False, source="unknown")


@dataclass
class RoleResult:
    output: object  # raw, untrusted; validated by the coordinator
    usage: Usage


def principal(config: ArtifactRef) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"sentinel:agent:{config.name}:{config.sha256}")


class DeterministicRole:
    live = False
    timeout_seconds = 5

    def __init__(self, role: str):
        short, version = VERSIONS[role]
        self.role = role
        self.config = artifact(f"{short}-deterministic", version, {
            "kind": "deterministic", "role": role, "rules": RULES[role]})
        self.principal_id = principal(self.config)

    def call(self, role_input: dict) -> RoleResult:
        return RoleResult(DECIDE[self.role](role_input), NOT_APPLICABLE)


def _facts(role_input: dict) -> dict:
    return {f["fact"]: f for f in role_input["facts"]}


def _claim(fact: dict) -> dict:
    return {"kind": "fact", "fact": fact["fact"], "relation": "eq", "value": fact["value"],
            "cite": fact["cite"]}


def _analyst(role_input: dict) -> dict:
    facts = _facts(role_input)
    claims = [_claim(facts[k]) for k in ("amount_minor", "transaction_count_1h",
                                         "large_amount_rule_hit") if k in facts]
    wanted = [{"tool": "account_history", "window": "30d"}, {"tool": "account_profile"}]
    requests = [r for r in wanted if r in role_input["tools_not_yet_run"]]
    return {"role": "evidence_analyst", "claims": claims,
            "missing": [f for f in role_input["unavailable"] if f == "account_age_days"],
            "tool_requests": requests[:role_input["tool_requests_allowed"]]}


def _investigator(role_input: dict) -> dict:
    facts = _facts(role_input)
    value = lambda name, default=None: facts[name]["value"] if name in facts else default  # noqa: E731
    large, prior = value("large_amount_rule_hit", False), value("transaction_count_1h", 0)
    if large and prior >= 2:
        operation, reason = "simulated_hold", "velocity_pattern"
        cite = ("amount_minor", "transaction_count_1h", "large_amount_rule_hit",
                "history_max_amount_minor_30d")
    elif prior >= 3:
        operation, reason, cite = "escalate", "velocity_pattern", ("transaction_count_1h",)
    elif large:
        operation, reason, cite = "escalate", "unusual_amount", ("amount_minor",
                                                                 "large_amount_rule_hit")
    else:
        operation, reason, cite = "escalate", "insufficient_evidence", ("amount_minor",)
    claims = [_claim(facts[k]) for k in cite if k in facts] or [_claim(next(iter(facts.values())))]
    return {"role": "investigator", "operation": operation, "reason_code": reason,
            "claims": claims}


def _reviewer(role_input: dict) -> dict:
    review = role_input["investigator"]
    if not review["problems"]:
        return {"role": "reviewer", "verdict": "accept"}
    unsupported = [k["index"] for k in review["checks"] if k["status"] != "supported"]
    reasons = sorted(set(review["problems"]))
    if role_input["revision_available"]:
        return {"role": "reviewer", "verdict": "challenge", "challenged_claims": unsupported,
                "reasons": reasons}
    return {"role": "reviewer", "verdict": "abstain", "reasons": reasons}


DECIDE = {"evidence_analyst": _analyst, "investigator": _investigator, "reviewer": _reviewer}
RULES = {
    "evidence_analyst": "cite amount, 1h count and rule hit; request 30d history and profile",
    "investigator": "hold if large and >=2 prior in 1h; escalate velocity if >=3; else amount",
    "reviewer": "accept iff the server found no problem; else challenge once, then abstain",
}

ROLE_PROMPTS = {
    "evidence_analyst": (
        "You are the evidence analyst for a synthetic fraud-investigation exercise. You receive "
        "server-verified facts, each with a citation. Restate the relevant facts as claims "
        "citing exactly the given citations, list facts that are unavailable, and request at "
        "most the allowed number of tools from tools_not_yet_run. Do not recommend an action. "
        "Reply with the JSON object only."),
    "investigator": (
        "You are the investigator for a synthetic fraud-investigation exercise. Choose exactly "
        "one operation (simulated_hold or escalate) and one reason_code, supported by claims "
        "that cite only the given citations and values. You cannot act; a human decides. "
        "Reply with the JSON object only."),
    "reviewer": (
        "You are the reviewer for a synthetic fraud-investigation exercise. Given the "
        "investigator's claims and the server's claim checks, accept, challenge unsupported or "
        "contradictory claims by index, or abstain. You cannot approve anything. Reply with "
        "the JSON object only."),
}


class ClaudeCliRoleAdapter:
    """Opt-in local subscription role adapter. `runner` is injectable so tests can drive a
    real test-owned subprocess (never a billable call) through the same timeout path."""
    live = True

    def __init__(self, role: str, model: str = "sonnet", timeout_seconds: int = 45,
                 executable: str | None = None,
                 runner: Callable[..., subprocess.CompletedProcess] = subprocess.run):
        short, version = VERSIONS[role]
        self.role, self.model, self.executable, self.runner = role, model, executable, runner
        self.timeout_seconds = timeout_seconds
        self.schema = TypeAdapter(OUTPUT_MODELS[role]).json_schema()
        self.config = artifact(f"{short}-claude-cli", version, {
            "kind": "claude-cli", "role": role, "model": model,
            "system_prompt": ROLE_PROMPTS[role], "output_schema": self.schema, "tools": []})
        self.principal_id = principal(self.config)

    def command(self, executable: str) -> list[str]:
        return [executable, "-p", "--output-format", "json", "--model", self.model,
                "--tools", "", "--strict-mcp-config", "--setting-sources", "",
                "--disable-slash-commands", "--no-session-persistence",
                "--system-prompt", ROLE_PROMPTS[self.role],
                "--json-schema", json.dumps(self.schema, separators=(",", ":"))]

    def call(self, role_input: dict) -> RoleResult:
        executable = self.executable or investigators.resolve_claude_executable()
        if executable is None:
            raise InvestigatorError("provider_unavailable")
        env = investigators.subscription_env()
        prompt = json.dumps(role_input, sort_keys=True)
        try:
            with tempfile.TemporaryDirectory(prefix="sentinel-claude-role-") as cwd:
                # The existing fail-closed preflight, unchanged (needs self.runner only).
                investigators.ClaudeCliInvestigator._require_subscription_login(
                    self, executable, env, cwd)
                completed = self.runner(self.command(executable), input=prompt,
                                        capture_output=True, text=True, encoding="utf-8",
                                        timeout=self.timeout_seconds, cwd=cwd, env=env)
        except subprocess.TimeoutExpired:
            raise InvestigatorError("timeout") from None
        except OSError:
            raise InvestigatorError("provider_unavailable") from None
        if completed.returncode != 0:  # output is never logged
            raise InvestigatorError("provider_unavailable")
        return parse_role_envelope(completed.stdout)


def parse_role_envelope(stdout: str) -> RoleResult:
    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError:
        raise InvestigatorError("invalid_output") from None
    if not isinstance(envelope, dict) or envelope.get("is_error"):
        raise InvestigatorError("provider_unavailable")
    candidate = envelope.get("structured_output")
    if candidate is None and isinstance(envelope.get("result"), str):
        try:
            candidate = json.loads(envelope["result"])
        except json.JSONDecodeError:
            raise InvestigatorError("invalid_output") from None
    return RoleResult(candidate, usage_from(envelope.get("usage")))


def usage_from(raw) -> Usage:
    """Counts only when the envelope reports both as non-negative integers (decision 4)."""
    if isinstance(raw, dict):
        counts = raw.get("input_tokens"), raw.get("output_tokens")
        if all(type(c) is int and c >= 0 for c in counts):
            return Usage(measured=True, source="adapter_reported", input_tokens=counts[0],
                         output_tokens=counts[1])
    return UNKNOWN
