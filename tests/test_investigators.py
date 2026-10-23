"""Investigator adapters without live calls: the Claude CLI runner is faked."""
import json
import os
import subprocess
from pathlib import Path

import pytest

from sentinel import investigators
from sentinel.investigators import (
    ClaudeCliInvestigator, DeterministicInvestigator, InvestigationView, InvestigatorError,
    parse_claude_result,
)

VIEW = InvestigationView(facts={"amount_minor": 250_000, "transaction_count_1h": 3},
                         currency="USD", large_amount=True, rule_score=1.0, threshold=0.5)
FINDING = {"operation": "escalate", "reason_code": "velocity_pattern",
           "rationale": "Three prior transactions in one hour."}


SUBSCRIPTION = {"loggedIn": True, "authMethod": "claude.ai", "apiProvider": "firstParty",
                "subscriptionType": "pro", "email": "redacted@example.invalid"}


def fake_runner(stdout="", returncode=0, raises=None, seen=None, auth=SUBSCRIPTION, calls=None):
    """Answers `claude auth status` with `auth`; records the model call in `seen`."""
    def run(cmd, **kwargs):
        if calls is not None:
            calls.append({"cmd": cmd, **kwargs})
        if cmd[1:3] == ["auth", "status"]:
            return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(auth), stderr="")
        if seen is not None:
            seen.update(cmd=cmd, **kwargs)
        if raises:
            raise raises
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr="")
    return run


def envelope(**fields):
    return json.dumps({"type": "result", "is_error": False, **fields})


def test_structured_output_becomes_finding(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "DUMMY_SECRET_NOT_REAL")
    seen = {}
    agent = ClaudeCliInvestigator(executable="claude", runner=fake_runner(
        envelope(structured_output=FINDING), seen=seen))
    finding = agent.investigate(VIEW)
    assert finding.operation == "escalate"
    # Locked-down invocation: no tools, MCP, settings or session; subscription login only.
    cmd = seen["cmd"]
    assert cmd[cmd.index("--tools") + 1] == ""
    assert "--strict-mcp-config" in cmd and "--no-session-persistence" in cmd
    assert cmd[cmd.index("--setting-sources") + 1] == ""
    assert "--bare" not in cmd and "--dangerously-skip-permissions" not in cmd
    assert "--disable-slash-commands" in cmd
    assert "ANTHROPIC_API_KEY" not in seen["env"]
    assert Path(seen["cwd"]).resolve() != Path.cwd().resolve()
    assert json.loads(seen["input"])["facts"] == VIEW.facts
    assert seen["timeout"] == agent.timeout_seconds


# Every documented alternate provider route/credential (dummy values only).
ALTERNATE_ROUTES = {
    "ANTHROPIC_API_KEY": "DUMMY_NOT_REAL", "ANTHROPIC_AUTH_TOKEN": "DUMMY_NOT_REAL",
    "ANTHROPIC_BASE_URL": "https://example.invalid", "CLAUDE_CODE_USE_BEDROCK": "1",
    "AWS_BEARER_TOKEN_BEDROCK": "DUMMY_NOT_REAL", "ANTHROPIC_BEDROCK_BASE_URL": "https://x.invalid",
    "CLAUDE_CODE_USE_VERTEX": "1", "ANTHROPIC_VERTEX_PROJECT_ID": "dummy",
    "CLAUDE_CODE_USE_FOUNDRY": "1", "ANTHROPIC_FOUNDRY_API_KEY": "DUMMY_NOT_REAL",
    "ANTHROPIC_FOUNDRY_RESOURCE": "dummy", "ANTHROPIC_FOUNDRY_BASE_URL": "https://y.invalid",
}


def test_r1_no_alternate_provider_route_reaches_any_child(monkeypatch):
    for name, value in ALTERNATE_ROUTES.items():
        monkeypatch.setenv(name, value)
    calls = []
    ClaudeCliInvestigator(executable="claude", runner=fake_runner(
        envelope(structured_output=FINDING), calls=calls)).investigate(VIEW)
    assert [c["cmd"][1] for c in calls] == ["auth", "-p"]  # preflight, then the model call
    for call in calls:
        leaked = sorted(set(ALTERNATE_ROUTES) & set(call["env"]))
        assert leaked == [], leaked


@pytest.mark.parametrize("auth", [
    {**SUBSCRIPTION, "authMethod": "api_key"},
    {**SUBSCRIPTION, "apiProvider": "foundry"},
    {**SUBSCRIPTION, "apiProvider": "bedrock"},
    {**SUBSCRIPTION, "loggedIn": False},
    {"unexpected": "shape"},
])
def test_r1_model_is_never_called_without_verified_subscription_login(auth):
    calls = []
    agent = ClaudeCliInvestigator(executable="claude", runner=fake_runner(
        envelope(structured_output=FINDING), auth=auth, calls=calls))
    with pytest.raises(InvestigatorError) as raised:
        agent.investigate(VIEW)
    assert raised.value.code == "provider_unavailable"
    assert [c["cmd"][1] for c in calls] == ["auth"]


def test_windows_cmd_shim_is_never_executed(tmp_path, monkeypatch):
    shim = tmp_path / "claude.cmd"
    shim.write_text("@echo off", encoding="utf-8")
    monkeypatch.setenv("SENTINEL_CLAUDE_EXECUTABLE", str(shim))
    assert investigators.resolve_claude_executable() is None
    native = tmp_path / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
    native.parent.mkdir(parents=True)
    native.write_bytes(b"")
    assert investigators.resolve_claude_executable() == str(native)


def test_result_text_fallback():
    assert parse_claude_result(envelope(result=json.dumps(FINDING))).reason_code == \
        "velocity_pattern"


@pytest.mark.parametrize("stdout, code", [
    ("not json", "invalid_output"),
    (envelope(result="I recommend holding."), "invalid_output"),
    (json.dumps({"is_error": True, "result": "usage limit reached"}), "provider_unavailable"),
    # Hostile output trying to smuggle authority or targets is rejected outright.
    (envelope(structured_output={**FINDING, "approved": True}), "invalid_output"),
    (envelope(structured_output={**FINDING, "transaction_id": "x"}), "invalid_output"),
    (envelope(structured_output={**FINDING, "operation": "transfer_funds"}), "invalid_output"),
    (envelope(structured_output={**FINDING, "rationale": "x" * 601}), "invalid_output"),
])
def test_bad_output_is_typed_failure(stdout, code):
    with pytest.raises(InvestigatorError) as raised:
        parse_claude_result(stdout)
    assert raised.value.code == code


@pytest.mark.parametrize("runner, code", [
    (fake_runner(raises=subprocess.TimeoutExpired("claude", 60)), "timeout"),
    (fake_runner(raises=FileNotFoundError()), "provider_unavailable"),
    (fake_runner(stdout=envelope(structured_output=FINDING), returncode=1),
     "provider_unavailable"),
])
def test_process_failures_are_typed(runner, code):
    with pytest.raises(InvestigatorError) as raised:
        ClaudeCliInvestigator(executable="claude", runner=runner).investigate(VIEW)
    assert raised.value.code == code


def test_config_pins_model_and_prompt():
    assert ClaudeCliInvestigator(model="sonnet").config != ClaudeCliInvestigator(
        model="opus").config
    assert DeterministicInvestigator().config.name == "deterministic-investigator"


def test_claude_cli_is_local_only(monkeypatch):
    monkeypatch.setenv("SENTINEL_INVESTIGATOR", "claude-cli")
    monkeypatch.setenv("SENTINEL_MODE", "public")
    with pytest.raises(RuntimeError):
        investigators.from_environment()
    monkeypatch.setenv("SENTINEL_MODE", "local")
    assert isinstance(investigators.from_environment(), ClaudeCliInvestigator)
    monkeypatch.delenv("SENTINEL_INVESTIGATOR")
    assert isinstance(investigators.from_environment(), DeterministicInvestigator)


@pytest.mark.skipif(os.environ.get("SENTINEL_LIVE_CLAUDE") != "1",
                    reason="live Claude smoke test uses subscription quota; set "
                           "SENTINEL_LIVE_CLAUDE=1 to run")
def test_live_claude_cli_smoke():
    finding = ClaudeCliInvestigator(timeout_seconds=120).investigate(VIEW)
    assert finding.operation in {"simulated_hold", "escalate"}
