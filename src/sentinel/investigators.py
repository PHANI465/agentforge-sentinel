"""Bounded investigators. Output is an untrusted InvestigationFinding; the server builds any
action from stored records, and only an authenticated human can approve it.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from pydantic import ValidationError

from sentinel.contracts.v1 import ArtifactRef, InvestigationFinding
from sentinel.scoring import artifact

FailureCode = str  # one of AgentRun.failure_code values


class InvestigatorError(Exception):
    def __init__(self, code: FailureCode):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class InvestigationView:
    """The only material an investigator sees: typed synthetic facts and the rule score."""
    facts: dict[str, int]
    currency: str
    large_amount: bool
    rule_score: float
    threshold: float


class Investigator(Protocol):
    config: ArtifactRef
    principal_id: uuid.UUID
    timeout_seconds: int

    def investigate(self, view: InvestigationView) -> InvestigationFinding: ...


def _principal(config: ArtifactRef) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"sentinel:agent:{config.name}:{config.sha256}")


class DeterministicInvestigator:
    """Fixed rules standing in for an agent. Not live AI; used as the default and baseline."""
    timeout_seconds = 5

    def __init__(self):
        self.config = artifact("deterministic-investigator", "i1", {
            "kind": "deterministic", "hold_if": "large_amount and transaction_count_1h >= 2",
            "velocity_if": "transaction_count_1h >= 3",
        })
        self.principal_id = _principal(self.config)

    def investigate(self, view: InvestigationView) -> InvestigationFinding:
        prior = view.facts.get("transaction_count_1h", 0)
        if view.large_amount and prior >= 2:
            return InvestigationFinding(
                operation="simulated_hold", reason_code="velocity_pattern",
                rationale=f"Large amount with {prior} prior transactions in the last hour.")
        if prior >= 3:
            return InvestigationFinding(
                operation="escalate", reason_code="velocity_pattern",
                rationale=f"{prior} prior transactions in the last hour.")
        if view.large_amount:
            return InvestigationFinding(
                operation="escalate", reason_code="unusual_amount",
                rationale="Amount exceeds the large-amount rule for this currency.")
        return InvestigationFinding(
            operation="escalate", reason_code="insufficient_evidence",
            rationale="Rule score reached the threshold without a dominant signal.")


CLAUDE_SYSTEM_PROMPT = (
    "You are a fraud-investigation assistant for a synthetic training system. You receive "
    "typed facts about one synthetic transaction. Recommend exactly one option: "
    "simulated_hold (pause funds pending review) or escalate (send to a senior analyst), "
    "with one reason_code, and a short factual rationale citing only the given facts. "
    "You cannot take actions; a human decides. Reply with the JSON object only."
)
# Provider routing/credential controls removed from the child environment (review R1): every
# ANTHROPIC_* variable (API keys, auth tokens, base URLs, Bedrock/Vertex/Foundry settings),
# every CLAUDE_CODE_USE_* provider switch, and the Bedrock bearer token.
_ROUTE_PREFIXES = ("ANTHROPIC_", "CLAUDE_CODE_USE_")
_ROUTE_NAMES = {"AWS_BEARER_TOKEN_BEDROCK"}
# The only accepted profile, as reported by `claude auth status --json`.
SUBSCRIPTION_PROFILE = {"loggedIn": True, "authMethod": "claude.ai", "apiProvider": "firstParty"}


def subscription_env() -> dict[str, str]:
    return {name: value for name, value in os.environ.items()
            if not name.upper().startswith(_ROUTE_PREFIXES) and name.upper() not in _ROUTE_NAMES}


def resolve_claude_executable(name: str = "claude") -> str | None:
    """SENTINEL_CLAUDE_EXECUTABLE, else PATH. A Windows .cmd/.bat shim is never run (cmd.exe
    would re-parse the JSON arguments); the npm package's native binary is used instead."""
    found = os.environ.get("SENTINEL_CLAUDE_EXECUTABLE") or shutil.which(name)
    if found is None:
        return None
    path = Path(found)
    if path.suffix.lower() in {".cmd", ".bat"}:
        native = path.parent / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
        return str(native) if native.is_file() else None
    return str(path)


class ClaudeCliInvestigator:
    """Local-only: calls the user's logged-in Claude Code CLI headless, with no tools, MCP
    servers, skills, settings files, project instructions or saved session. Before any model
    call, `claude auth status` (same environment) must report first-party claude.ai login;
    otherwise nothing is sent. Never enable in public mode."""

    def __init__(self, model: str = "sonnet", executable: str | None = None,
                 timeout_seconds: int = 60,
                 runner: Callable[..., subprocess.CompletedProcess] = subprocess.run):
        self.model = model
        self.executable = executable
        self.timeout_seconds = timeout_seconds
        self.runner = runner
        self.schema = InvestigationFinding.model_json_schema()
        self.config = artifact("claude-cli-investigator", "c1", {
            "kind": "claude-cli", "model": model, "system_prompt": CLAUDE_SYSTEM_PROMPT,
            "output_schema": self.schema, "tools": [],
        })
        self.principal_id = _principal(self.config)

    def command(self, executable: str) -> list[str]:
        return [executable, "-p", "--output-format", "json", "--model", self.model,
                "--tools", "", "--strict-mcp-config", "--setting-sources", "",
                "--disable-slash-commands",
                "--no-session-persistence", "--system-prompt", CLAUDE_SYSTEM_PROMPT,
                "--json-schema", json.dumps(self.schema, separators=(",", ":"))]

    def investigate(self, view: InvestigationView) -> InvestigationFinding:
        prompt = json.dumps({"facts": view.facts, "currency": view.currency,
                             "large_amount_rule_hit": view.large_amount,
                             "rule_score": view.rule_score, "alert_threshold": view.threshold},
                            sort_keys=True)
        executable = self.executable or resolve_claude_executable()
        if executable is None:
            raise InvestigatorError("provider_unavailable")
        env = subscription_env()
        try:
            # Empty working directory: no project files or CLAUDE.md are visible to the model.
            with tempfile.TemporaryDirectory(prefix="sentinel-claude-") as cwd:
                self._require_subscription_login(executable, env, cwd)
                completed = self.runner(self.command(executable), input=prompt, capture_output=True,
                                        text=True, encoding="utf-8", timeout=self.timeout_seconds,
                                        cwd=cwd, env=env)
        except subprocess.TimeoutExpired:
            raise InvestigatorError("timeout") from None
        except OSError:
            raise InvestigatorError("provider_unavailable") from None
        # Output is never logged: it is untrusted and may echo account details.
        if completed.returncode != 0:
            raise InvestigatorError("provider_unavailable")
        return parse_claude_result(completed.stdout)


    def _require_subscription_login(self, executable: str, env: dict, cwd: str) -> None:
        """Fail closed unless the CLI, as configured here (including any managed settings it
        applies), resolves to subscription login. Output is not logged: it contains the email."""
        status = self.runner([executable, "auth", "status", "--json"], capture_output=True,
                             text=True, encoding="utf-8", timeout=15, cwd=cwd, env=env)
        try:
            profile = json.loads(status.stdout) if status.returncode == 0 else None
        except json.JSONDecodeError:
            profile = None
        if not isinstance(profile, dict) or any(
                profile.get(key) != value for key, value in SUBSCRIPTION_PROFILE.items()):
            raise InvestigatorError("provider_unavailable")


def parse_claude_result(stdout: str) -> InvestigationFinding:
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
    try:
        return InvestigationFinding.model_validate(candidate)
    except ValidationError:
        raise InvestigatorError("invalid_output") from None


def from_environment() -> Investigator:
    kind = os.environ.get("SENTINEL_INVESTIGATOR", "deterministic")
    if kind == "deterministic":
        return DeterministicInvestigator()
    if kind == "claude-cli":
        if os.environ.get("SENTINEL_MODE", "local") != "local":
            raise RuntimeError("claude-cli uses a personal subscription and is local-only")
        return ClaudeCliInvestigator(model=os.environ.get("SENTINEL_CLAUDE_MODEL", "sonnet"))
    if kind == "three-role":  # G3B; explicit operator choice, deterministic roles by default
        from sentinel.agents import coordinator
        adapter = os.environ.get("SENTINEL_AGENT_ADAPTER", "deterministic")
        if adapter == "deterministic":
            return coordinator.deterministic_workflow()
        if adapter == "claude-cli":
            if os.environ.get("SENTINEL_MODE", "local") != "local":
                raise RuntimeError("claude-cli uses a personal subscription and is local-only")
            return coordinator.claude_cli_workflow(
                model=os.environ.get("SENTINEL_CLAUDE_MODEL", "sonnet"))
        raise RuntimeError("SENTINEL_AGENT_ADAPTER must be deterministic or claude-cli")
    raise RuntimeError("SENTINEL_INVESTIGATOR must be deterministic, claude-cli or three-role")
