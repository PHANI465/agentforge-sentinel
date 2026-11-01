"""The opt-in Claude CLI role adapter, driven through a real test-owned subprocess (a fake CLI
script, never a billable call): isolation flags, preflight, scrubbed environment, output and
usage parsing, and the local worker lifetime when the child outlives its timeout."""
import json
import os
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path

import pytest

from sentinel.agents import adapters, coordinator
from sentinel.agents.capacity import AgentCapacity
from sentinel.investigators import InvestigatorError

FAKE_CLI = textwrap.dedent("""
    import json, os, sys, time
    args = sys.argv[1:]
    if args[:2] == ["auth", "status"]:
        print(json.dumps({"loggedIn": True, "authMethod": os.environ.get("FAKE_AUTH",
                          "claude.ai"), "apiProvider": "firstParty"}))
        sys.exit(0)
    with open(os.environ["FAKE_PID_FILE"], "w") as f:
        f.write(str(os.getpid()))
    with open(os.environ["FAKE_ENV_FILE"], "w") as f:
        json.dump(sorted(os.environ), f)
    sys.stdin.read()
    time.sleep(float(os.environ.get("FAKE_SLEEP", "0")))
    print(os.environ.get("FAKE_STDOUT", json.dumps({
        "structured_output": {"role": "reviewer", "verdict": "accept"},
        "usage": {"input_tokens": 812, "output_tokens": 164}})))
""")


@pytest.fixture
def fake(tmp_path, monkeypatch):
    script = tmp_path / "fake_claude.py"
    script.write_text(FAKE_CLI, encoding="utf-8")
    monkeypatch.setenv("FAKE_PID_FILE", str(tmp_path / "pid"))
    monkeypatch.setenv("FAKE_ENV_FILE", str(tmp_path / "env"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "SYNTHETIC-NOT-A-KEY")
    monkeypatch.setenv("CLAUDE_CODE_USE_BEDROCK", "1")
    seen = []

    def runner(command, **kwargs):  # the real subprocess.run, on the fake script
        seen.append(command)
        return subprocess.run([sys.executable, str(script), *command[1:]], **kwargs)
    return {"runner": runner, "seen": seen, "dir": tmp_path}


def adapter(fake, role="reviewer", timeout=10):
    return adapters.ClaudeCliRoleAdapter(role, timeout_seconds=timeout, executable="claude",
                                         runner=fake["runner"])


def alive(pid: int) -> bool:
    if os.name == "nt":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True,
                             text=True).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def test_isolated_command_scrubbed_env_and_reported_usage(fake):
    result = adapter(fake).call({"role": "reviewer"})
    assert result.output == {"role": "reviewer", "verdict": "accept"}
    assert (result.usage.source, result.usage.input_tokens, result.usage.output_tokens) == (
        "adapter_reported", 812, 164)
    auth, call = fake["seen"]
    assert auth[1:] == ["auth", "status", "--json"]
    for flag in ("-p", "--strict-mcp-config", "--disable-slash-commands",
                 "--no-session-persistence"):
        assert flag in call
    assert call[call.index("--tools") + 1] == "" and \
        call[call.index("--setting-sources") + 1] == ""
    env = json.loads((fake["dir"] / "env").read_text())
    assert not any(n.upper().startswith(("ANTHROPIC_", "CLAUDE_CODE_USE_")) for n in env)


def test_preflight_fails_closed_without_subscription_login(fake, monkeypatch):
    monkeypatch.setenv("FAKE_AUTH", "apiKey")
    with pytest.raises(InvestigatorError) as raised:
        adapter(fake).call({"role": "reviewer"})
    assert raised.value.code == "provider_unavailable" and len(fake["seen"]) == 1


@pytest.mark.parametrize("stdout, expected", [
    ("not json", "invalid_output"), (json.dumps({"is_error": True}), "provider_unavailable")])
def test_bad_envelopes_are_typed_failures(fake, monkeypatch, stdout, expected):
    monkeypatch.setenv("FAKE_STDOUT", stdout)
    with pytest.raises(InvestigatorError) as raised:
        adapter(fake).call({"role": "reviewer"})
    assert raised.value.code == expected


def test_unreported_or_malformed_usage_stays_unknown():
    assert adapters.usage_from(None).source == "unknown"
    assert adapters.usage_from({"input_tokens": 5}).source == "unknown"
    assert adapters.usage_from({"input_tokens": -1, "output_tokens": 2}).source == "unknown"
    assert adapters.usage_from({"input_tokens": True, "output_tokens": 2}).source == "unknown"


def test_timed_out_child_is_ended_and_the_call_slot_follows_the_worker(fake, monkeypatch):
    """The real child outlives its 2 s timeout: subprocess.run kills it, the worker thread
    returns a typed timeout, and only then is the call slot released."""
    monkeypatch.setenv("FAKE_SLEEP", "30")
    role = adapter(fake, timeout=2)
    capacity = AgentCapacity(1, 2)
    slot = capacity.reserve_call()
    returned = threading.Event()
    future = slot.start(role.call, {"role": "reviewer"}, on_return=lambda _f: returned.set())
    for _ in range(100):
        if (fake["dir"] / "pid").exists() and (fake["dir"] / "pid").read_text():
            break
        time.sleep(0.05)
    pid = int((fake["dir"] / "pid").read_text())
    assert alive(pid) and capacity.snapshot()["calls"] == 1
    with pytest.raises(InvestigatorError) as raised:
        future.result(timeout=20)
    assert raised.value.code == "timeout"
    assert returned.wait(5)
    for _ in range(100):
        if not alive(pid) and capacity.snapshot()["calls"] == 0:
            break
        time.sleep(0.05)
    assert not alive(pid)  # the local process ended; provider-side work is not claimed
    assert capacity.snapshot()["calls"] == 0


def test_operator_modes(monkeypatch):
    from sentinel import investigators
    monkeypatch.setenv("SENTINEL_INVESTIGATOR", "three-role")
    monkeypatch.setenv("SENTINEL_AGENT_ADAPTER", "claude-cli")
    monkeypatch.setenv("SENTINEL_MODE", "public")
    with pytest.raises(RuntimeError):
        investigators.from_environment()
    monkeypatch.setenv("SENTINEL_MODE", "local")
    live = investigators.from_environment()
    assert live.live and isinstance(live, coordinator.Workflow)
    assert {a.config.name for a in live.adapters.values()} == {
        "analyst-claude-cli", "investigator-claude-cli", "reviewer-claude-cli"}
    monkeypatch.setenv("SENTINEL_AGENT_ADAPTER", "unknown")
    with pytest.raises(RuntimeError):
        investigators.from_environment()
    monkeypatch.setenv("SENTINEL_AGENT_ADAPTER", "deterministic")
    default = investigators.from_environment()
    assert not default.live and default.config != live.config
    assert default.config.name == "three-role-workflow" and default.tool_profile.name == \
        "agent-read-tools"


def test_manual_comparator_refuses_live_runs_without_explicit_consent():
    root = Path(__file__).resolve().parents[1]
    done = subprocess.run([sys.executable, str(root / "scripts" / "agent_eval.py"),
                           "--database-url", "host=192.0.2.1 dbname=none",
                           "--comparators", "C0,C1"], capture_output=True, text=True,
                          timeout=60)
    assert done.returncode == 2 and "--allow-live" in done.stdout
