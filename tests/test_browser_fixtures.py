"""C02: the browser-test stack runs the real API in a real uvicorn process on disposable
PostgreSQL; scenarios behave as documented; restarts are real process restarts; teardown and
failure cleanup are verified. All HTTP here goes over real sockets."""
import json
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psycopg
import pytest

ROOT = Path(__file__).resolve().parents[1]
SUPPORT = ROOT / "tests" / "support"
sys.path.insert(0, str(SUPPORT))

import browser_stack  # noqa: E402
from browser_stack import Stack, StackError, healthy, process_start_time  # noqa: E402
from sentinel import devdb  # noqa: E402

pytestmark = pytest.mark.skipif(devdb.find_pg_bin() is None, reason="needs PostgreSQL binaries")


@pytest.fixture(scope="module")
def stack():
    started = Stack.start()
    yield started
    result = started.stop()
    assert result == {"api_stopped": True, "database_stopped": True, "state_removed": True}


def http(stack, method, path, token=None, body=None):
    data = None if body is None else json.dumps(body).encode()
    headers = {"Content-Type": "application/json"}
    if token is not None:
        headers["Authorization"] = f"Bearer {stack.manifest['tokens'][token]}"
    request = urllib.request.Request(stack.manifest["api"]["base_url"] + path, data=data,
                                     method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def scenario(stack, name):
    return stack.manifest["scenarios"][name]


def case(stack, name, token="analyst"):
    return http(stack, "GET", f"/v1/cases/{scenario(stack, name)['case_id']}", token)


def test_every_scenario_is_in_its_documented_state(stack):
    for name, record in stack.manifest["scenarios"].items():
        status, view = case(stack, name, record["session"])
        assert status == 200, name
        assert (view["case"]["state"], view["case"]["revision"]) == (
            record["state"], record["revision"]), name
    assert http(stack, "GET", "/v1/overview", "analyst")[1]["investigator"]["name"] == \
        "deterministic-fixture-investigator"


def test_foreign_session_is_denied(stack):
    foreign = scenario(stack, "foreign_session_case")["case_id"]
    for path in (f"/v1/cases/{foreign}", f"/v1/cases/{foreign}/audit"):
        assert http(stack, "GET", path, "analyst") == (404, {"error": "not_found"})
    assert http(stack, "POST", f"/v1/cases/{foreign}/investigations", "analyst",
                {"expected_revision": 1}) == (404, {"error": "not_found"})
    listed = {i["id"] for i in http(stack, "GET", "/v1/cases?limit=100", "analyst")[1]["items"]}
    assert foreign not in listed
    assert case(stack, "foreign_session_case", "other_session")[0] == 200


def test_limited_capabilities_and_second_actor(stack):
    record = scenario(stack, "limited_capabilities")
    assert case(stack, "limited_capabilities", "read_only")[0] == 200
    pending = scenario(stack, "awaiting_approval")["intent_id"]
    assert http(stack, "POST", "/v1/approvals", "read_only",
                {"action_intent_id": pending, "decision": "approved"}) == (
        403, {"error": "permission_denied"})
    body = {"approval_id": record["approval_id"], "idempotency_key": str(uuid.uuid4())}
    assert http(stack, "POST", "/v1/actions", "read_only", body) == (
        403, {"error": "action_permission_denied"})
    assert http(stack, "POST", "/v1/actions", "second_actor", body) == (
        403, {"error": "approver_mismatch"})
    audit = http(stack, "GET", f"/v1/cases/{record['case_id']}/audit", "analyst")[1]
    assert [e["event_type"] for e in audit].count("action_denied") == 2


def test_provider_failure_records_failed_run_and_reopens(stack):
    case_id = scenario(stack, "provider_failure")["case_id"]
    status, view = http(stack, "POST", f"/v1/cases/{case_id}/investigations", "analyst",
                        {"expected_revision": 1})
    assert status == 200
    assert (view["case"]["state"], view["case"]["revision"]) == ("open", 3)
    assert view["agent_runs"][-1]["run"]["status"] == "failed"
    assert view["agent_runs"][-1]["run"]["failure_code"] == "provider_unavailable"
    assert view["action_intents"] == []
    retry = http(stack, "POST", f"/v1/cases/{case_id}/investigations", "analyst",
                 {"expected_revision": 3})[1]
    assert retry["case"]["revision"] == 5 and len(retry["agent_runs"]) == 2


def test_seeded_failed_run_can_be_retried(stack):
    record = scenario(stack, "failed_run_reopened")
    view = case(stack, "failed_run_reopened")[1]
    assert view["agent_runs"][0]["run"]["failure_code"] == "provider_unavailable"
    status, after = http(stack, "POST", f"/v1/cases/{record['case_id']}/investigations",
                         "analyst", {"expected_revision": 3})
    assert status == 200
    assert (after["case"]["state"], after["case"]["revision"]) == ("awaiting_approval", 5)


def test_expired_approval_reopens_and_fresh_approval_executes(stack):
    record = scenario(stack, "approval_expired")
    case_id = record["case_id"]
    assert http(stack, "POST", "/v1/actions", "analyst", {
        "approval_id": record["approval_id"], "idempotency_key": str(uuid.uuid4())}) == (
        409, {"error": "approval_outside_validity"})
    view = case(stack, "approval_expired")[1]
    assert (view["case"]["state"], view["case"]["revision"]) == ("open", 4)
    redo = http(stack, "POST", f"/v1/cases/{case_id}/investigations", "analyst",
                {"expected_revision": 4})[1]
    assert redo["case"]["revision"] == 6
    approval = http(stack, "POST", "/v1/approvals", "analyst", {
        "action_intent_id": redo["action_intents"][-1]["intent"]["id"],
        "decision": "approved"})[1]
    assert http(stack, "POST", "/v1/actions", "analyst", {
        "approval_id": record["approval_id"], "idempotency_key": str(uuid.uuid4())})[0] == 409
    status, done = http(stack, "POST", "/v1/actions", "analyst", {
        "approval_id": approval["id"], "idempotency_key": str(uuid.uuid4())})
    assert status == 200 and done["action"]["state"] == "succeeded"
    events = [e["event_type"] for e in http(stack, "GET", f"/v1/cases/{case_id}/audit",
                                            "analyst")[1]]
    assert "approval_expired" in events and events[-1] == "action_succeeded"


def test_executed_replay_and_rejected(stack):
    record = scenario(stack, "executed")
    status, replay = http(stack, "POST", "/v1/actions", "analyst", {
        "approval_id": record["approval_id"], "idempotency_key": record["idempotency_key"]})
    assert status == 200 and replay["replayed"] is True
    assert replay["action"]["id"] == record["action_id"]
    rejected = scenario(stack, "rejected")
    assert http(stack, "POST", "/v1/actions", "analyst", {
        "approval_id": rejected["approval_id"], "idempotency_key": str(uuid.uuid4())}) == (
        409, {"error": "approval_not_available"})


def test_stale_revision(stack):
    case_id = scenario(stack, "stale_revision")["case_id"]
    path = f"/v1/cases/{case_id}/investigations"
    assert http(stack, "POST", path, "analyst", {"expected_revision": 1})[0] == 200  # other tab
    assert http(stack, "POST", path, "analyst", {"expected_revision": 1}) == (
        409, {"error": "stale_case_revision"})


def test_on_demand_approved_and_concurrent_duplicate_execution(stack):
    record = stack.seed("approved", 1)
    with pytest.raises(StackError):
        stack.seed("approved", 1)  # an ordinal is single-use
    body = {"approval_id": record["approval_id"], "idempotency_key": str(uuid.uuid4())}
    with ThreadPoolExecutor(2) as pool:
        results = [f.result(timeout=30) for f in
                   [pool.submit(http, stack, "POST", "/v1/actions", "analyst", body)
                    for _ in range(2)]]
    assert [s for s, _ in results] == [200, 200]
    assert len({r["action"]["id"] for _, r in results}) == 1
    assert sorted(r["replayed"] for _, r in results) == [False, True]
    with psycopg.connect(stack.manifest["database_url"]) as conn:
        assert conn.execute("SELECT count(*) FROM simulated_actions WHERE approval_id = %s",
                            (record["approval_id"],)).fetchone()[0] == 1


def test_real_api_and_database_restart_preserve_state(stack):
    record = stack.seed("approved", 2)
    key = str(uuid.uuid4())
    body = {"approval_id": record["approval_id"], "idempotency_key": key}
    first = http(stack, "POST", "/v1/actions", "analyst", body)[1]
    audit_before = http(stack, "GET", f"/v1/cases/{record['case_id']}/audit", "analyst")[1]
    old_pid = stack.manifest["api"]["pid"]

    stack.restart_api()  # a new uvicorn process, not a reconstructed Python object
    assert stack.manifest["api"]["pid"] != old_pid
    assert process_start_time(old_pid) is None
    replay = http(stack, "POST", "/v1/actions", "analyst", body)[1]
    assert replay["replayed"] is True and replay["action"]["id"] == first["action"]["id"]

    stack.restart_db()  # pg_ctl stop + start of the PostgreSQL server
    view = http(stack, "GET", f"/v1/cases/{record['case_id']}", "analyst")[1]
    assert (view["case"]["state"], view["case"]["revision"]) == ("closed", 4)
    assert view["action_intents"][-1]["approval"]["consumed_at"] is not None
    assert http(stack, "GET", f"/v1/cases/{record['case_id']}/audit", "analyst")[1] == \
        audit_before


def test_fresh_stacks_are_repeatable_and_cli_never_prints_tokens(stack, tmp_path):
    out = subprocess.run([sys.executable, str(SUPPORT / "browser_stack.py"), "start",
                          "--state-dir", str(tmp_path / "s")], capture_output=True, text=True,
                         timeout=180, check=True)
    manifest_path = Path(out.stdout.split("SENTINEL_STACK_MANIFEST=")[1].split()[0])
    other = json.loads(manifest_path.read_text())
    try:
        for token in other["tokens"].values():
            assert token not in out.stdout and token not in out.stderr
        ids = ("case_id", "transaction_id", "intent_id", "approval_id", "action_id",
               "failed_run_id", "idempotency_key")

        def shape(scen):
            return {n: {k: v for k, v in r.items() if k in ids or k in ("state", "revision")}
                    for n, r in scen.items()}
        assert shape(other["scenarios"]) == shape(stack.manifest["scenarios"])
        assert other["sessions"] == stack.manifest["sessions"]
        assert other["tokens"] != stack.manifest["tokens"]  # ephemeral per stack
    finally:
        stopped = subprocess.run([sys.executable, str(SUPPORT / "browser_stack.py"), "stop",
                                  "--manifest", str(manifest_path)], capture_output=True,
                                 text=True, timeout=60)
    assert json.loads(stopped.stdout) == {"api_stopped": True, "database_stopped": True,
                                          "state_removed": True}
    assert healthy(other["api"]["port"]) is None


@pytest.mark.parametrize("app, message", [
    ("fixture_app:create_app_never_ready", "not ready"),
    ("fixture_app:no_such_factory", "exited"),
])
def test_failed_start_cleans_up_processes_and_tokens(tmp_path, app, message):
    state = tmp_path / "state"
    with pytest.raises(StackError, match=message):
        Stack.start(state, app=app, timeout=8)
    assert not (state / "stack.json").exists()
    cluster = devdb.Cluster(devdb.find_pg_bin(), state / "pg" / "data", 0)
    assert not browser_stack._cluster_running(cluster)
    log = (state / "api.log").read_text(errors="replace") if (state / "api.log").exists() else ""
    assert "Bearer" not in log
