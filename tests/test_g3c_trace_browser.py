"""G3C-B trace browser fixtures: the test-only three-role app factory on a real Stack (uvicorn
plus disposable PostgreSQL), and every seeded trace scenario read over real HTTP from the
unchanged production trace route. The CLI output carries no secret."""
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SUPPORT = ROOT / "tests" / "support"
sys.path.insert(0, str(SUPPORT))

import g3c_trace_browser as trace_browser  # noqa: E402
from browser_stack import Stack  # noqa: E402
from sentinel import devdb  # noqa: E402

pytestmark = pytest.mark.skipif(devdb.find_pg_bin() is None, reason="needs PostgreSQL binaries")


@pytest.fixture(scope="module")
def stack():
    started = Stack.start(app="g3c_trace_browser:create_app")
    yield started
    result = started.stop()
    assert result == {"ok": True, "api_stopped": True, "database_stopped": True,
                      "state_removed": True, "errors": []}


def cli(stack, *args):
    completed = subprocess.run(
        [sys.executable, str(SUPPORT / "g3c_trace_browser.py"), *args, "--manifest",
         str(stack.path)], capture_output=True, text=True, timeout=180, cwd=ROOT)
    for secret in [*stack.manifest["tokens"].values(), stack.manifest["database_url"]]:
        assert secret not in completed.stdout and secret not in completed.stderr
    return completed.returncode, json.loads(completed.stdout)


def get(stack, path, token="analyst"):
    request = urllib.request.Request(stack.manifest["api"]["base_url"] + path, headers={
        "Authorization": f"Bearer {stack.manifest['tokens'][token]}"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def trace(stack, case_id, token="analyst"):
    return get(stack, f"/v1/cases/{case_id}/investigation-trace", token)


def test_the_factory_serves_the_three_role_workflow(stack):
    status, health = get(stack, "/healthz")
    assert status == 200 and health["investigator"] == "three-role-workflow"
    assert stack.manifest["app"] == "g3c_trace_browser:create_app"


EXPECTED = {
    "recommend": ("awaiting_approval", ["completed"], "recommend"),
    "abstain_challenge": ("awaiting_approval", ["completed"], "abstain"),
    "repeat_failure": ("awaiting_approval", ["completed"], "recommend"),
    "hostile_note": ("awaiting_approval", ["completed"], "recommend"),
    "zero_roles": ("open", ["inconclusive"], "inconclusive"),
    "running": ("investigating", ["running"], None),
    "overdue": ("investigating", ["running"], None),
    "retry": ("awaiting_approval", ["completed", "inconclusive"], "recommend"),
    "open_three_role": ("open", [], None),
}


@pytest.mark.parametrize("scenario", trace_browser.SCENARIOS)
def test_each_scenario_is_stored_and_served_as_documented(stack, scenario):
    code, record = cli(stack, "seed", "--scenario", scenario, "--ordinal", "1")
    assert code == 0, record
    state, statuses, kind = EXPECTED[scenario]
    assert (record["case_state"], record["workflow_statuses"]) == (state, statuses)
    status, body = trace(stack, record["case_id"])
    assert status == 200
    assert [w["id"] for w in body["workflows"]] == record["workflow_ids"]
    selected = body["selected"]
    if not statuses:
        assert selected is None and body["legacy_investigator_runs"] == 0
        return
    disposition = selected["workflow"]["disposition"]
    assert (disposition or {}).get("kind") == kind
    if scenario == "running":
        assert selected["workflow"]["deadline_status"] == "before_deadline"
    if scenario == "overdue":
        assert selected["workflow"]["deadline_status"] == "recovery_due"
    if scenario == "retry":
        assert body["workflows"][1]["terminal_by"] == "recovery"
    if scenario == "zero_roles":
        assert selected["attempts"] == [] and selected["limits"] is None  # other config
    if scenario == "hostile_note":
        assert selected["attempts"][0]["output"]["note"] == trace_browser.HOSTILE_NOTE
    if scenario == "repeat_failure":
        assert [(a["role"], a["attempt"], a["status"]) for a in selected["attempts"]][1:3] == [
            ("investigator", 1, "failed"), ("investigator", 2, "completed")]
    # Reading the trace changed nothing.
    assert cli(stack, "inspect", "--case-id", record["case_id"])[1] == {
        k: v for k, v in record.items() if k not in ("scenario", "case_id", "external_id")}


def test_legacy_and_empty_stack_scenarios_have_no_workflow(stack):
    legacy = stack.manifest["scenarios"]["awaiting_approval"]["case_id"]
    empty = stack.manifest["scenarios"]["open_case"]["case_id"]
    assert trace(stack, legacy)[1]["legacy_investigator_runs"] == 1
    assert (trace(stack, empty)[1]["legacy_investigator_runs"], trace(stack, empty)[1]["selected"]) == (0, None)


def test_another_session_cannot_read_a_seeded_trace(stack):
    _code, record = cli(stack, "seed", "--scenario", "recommend", "--ordinal", "2")
    assert trace(stack, record["case_id"], "other_session") == (404, {"error": "not_found"})


def test_failures_print_codes_only(stack):
    code, out = cli(stack, "inspect", "--case-id", "00000000-0000-4000-8000-000000000000")
    assert (code, out) == (1, {"error": "LookupError"})
    completed = subprocess.run(
        [sys.executable, str(SUPPORT / "g3c_trace_browser.py"), "seed", "--manifest",
         str(stack.path.parent / "missing.json"), "--scenario", "recommend", "--ordinal", "1"],
        capture_output=True, text=True, timeout=60, cwd=ROOT)
    assert completed.returncode == 1 and json.loads(completed.stdout) == {"error": "StackError"}


def test_inspection_connection_refuses_writes(stack):
    import psycopg
    with trace_browser.read_only(stack.manifest["database_url"]) as conn:
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            conn.execute("UPDATE cases SET body = body WHERE false")
