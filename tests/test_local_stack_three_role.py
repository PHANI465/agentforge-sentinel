"""G3D-P3: the local operator helper launches the three-role workflow by explicit choice,
passes its effective configuration explicitly, and reproduces it across a restart.

End-to-end tests run the real helper as a subprocess against a task-owned cluster on random
free ports: the owner migrates, grants and issues the session; the API runs as the restricted
runtime role. The inherited environment is hostile on purpose (SENTINEL_AGENT_ADAPTER and
SENTINEL_INVESTIGATOR set to claude-cli, another model) and the Claude executable points at
a path that does not exist, so no provider or account can be reached even by a defect.
Configuration-only tests use the real `main(argv)`; process launch and termination are
intercepted there, and nothing is killed.
"""
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

import psycopg
import pytest
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import local_stack  # noqa: E402
from sentinel import devdb  # noqa: E402

needs_pg = pytest.mark.skipif(devdb.find_pg_bin() is None, reason="needs PostgreSQL binaries")
ROLES = ["evidence_analyst", "investigator", "reviewer"]
HOSTILE = {"SENTINEL_AGENT_ADAPTER": "claude-cli", "SENTINEL_INVESTIGATOR": "claude-cli",
           "SENTINEL_CLAUDE_MODEL": "opus"}


def cli(state_dir, *argv, port=None, db_port=None):
    args = ["--state-dir", str(state_dir)]
    if port:
        args += ["--port", str(port)]
    if db_port:
        args += ["--db-port", str(db_port)]
    return local_stack.main([*args, *argv])


@pytest.fixture
def hostile(monkeypatch, tmp_path):
    for key, value in HOSTILE.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("SENTINEL_CLAUDE_EXECUTABLE", str(tmp_path / "no-such-claude"))


@pytest.fixture
def kills(monkeypatch):
    requested = []
    monkeypatch.setattr(local_stack, "terminate_tree", lambda pid: requested.append(pid) or True)
    return requested


def owned_record(stack, **fields):
    """An API record this test process owns (its own identity) on a free port."""
    data = stack.load(create=True)
    data["api"] = {**local_stack.identity(os.getpid()), "port": devdb.free_port(),
                   "scorer": "rule", "database": "sentinel", **fields}
    data["database"] = {"port": devdb.free_port()}
    stack.save(data)
    return data


def gone_record(stack, **fields):
    done = subprocess.run([sys.executable, "-c", "import os; print(os.getpid())"],
                          capture_output=True, text=True, check=True)
    data = stack.load(create=True)
    data["api"] = {"pid": int(done.stdout), "start": 1, "exe": "gone", "port": devdb.free_port(),
                   "scorer": "rule", "database": "sentinel", **fields}
    stack.save(data)
    return data


# ---- explicit selection and refusals (configuration only) ----------------------------------

@pytest.mark.parametrize("investigator", ["deterministic", "claude-cli"])
def test_an_adapter_with_a_single_investigator_is_refused_before_any_state(tmp_path, capsys,
                                                                         investigator):
    state = tmp_path / "stack"
    code = cli(state, "up", "--investigator", investigator, "--agent-adapter", "deterministic")
    assert code == 1
    assert "--agent-adapter applies only to --investigator three-role" in capsys.readouterr().err
    assert not state.exists()  # no state, database or API was created


def restart_environment(monkeypatch, stack, record_fields):
    """Run `smoke --restart-api` on an owned record with the smoke stages and the stop
    intercepted; capture the environment the restarted API would be launched with."""
    owned_record(stack, **record_fields)
    (stack.dir / "session.json").write_text(json.dumps({"token": "t"}))
    calls, launched = [], {}
    monkeypatch.setattr(local_stack.subprocess, "run", lambda argv, **kw: calls.append(argv)
                        or subprocess.CompletedProcess(argv, 0, "CASE_ID=c\n", ""))

    def stopped(stack_, data):
        data["api"] = None
        stack_.save(data)
        return "api stopped"
    monkeypatch.setattr(local_stack, "stop_api", stopped)

    def popen(argv, env=None, **kw):
        launched.update(env)
        raise OSError("intercepted")
    monkeypatch.setattr(local_stack.subprocess, "Popen", popen)
    code = cli(stack.dir, "smoke", "--restart-api")
    return code, calls, launched


CONFIG_KEYS = ("SENTINEL_INVESTIGATOR", "SENTINEL_AGENT_ADAPTER", "SENTINEL_CLAUDE_MODEL")


@needs_pg
@pytest.mark.parametrize("fields, expected", [
    ({"investigator": "three-role", "adapter": "deterministic", "claude_model": None},
     {"SENTINEL_INVESTIGATOR": "three-role", "SENTINEL_AGENT_ADAPTER": "deterministic"}),
    ({"investigator": "claude-cli", "adapter": None, "claude_model": "haiku"},
     {"SENTINEL_INVESTIGATOR": "claude-cli", "SENTINEL_CLAUDE_MODEL": "haiku"}),
    ({"investigator": "deterministic", "adapter": None, "claude_model": None},
     {"SENTINEL_INVESTIGATOR": "deterministic"}),
], ids=["three-role", "claude-cli-model", "deterministic"])
def test_restart_uses_the_recorded_configuration_not_the_environment(
        tmp_path, monkeypatch, hostile, fields, expected):
    code, calls, env = restart_environment(monkeypatch, local_stack.Stack(tmp_path / "s"),
                                           fields)
    assert code == 1 and len(calls) == 1  # investigate ran; the intercepted launch failed
    assert {k: env.get(k) for k in CONFIG_KEYS} == {k: expected.get(k) for k in CONFIG_KEYS}
    assert env["SENTINEL_MODE"] == "local" and "SENTINEL_TEST_DATABASE_URL" not in env


@pytest.mark.parametrize("fields", [
    {"investigator": "three-role"},  # which adapter? never guessed
    {"investigator": "claude-cli"},  # a pre-P3 live record: which model?
    {"investigator": "deterministic", "adapter": "claude-cli"},
], ids=["three-role-no-adapter", "claude-cli-no-model", "adapter-without-three-role"])
def test_an_ambiguous_record_refuses_restart_before_any_work(tmp_path, monkeypatch, capsys,
                                                             hostile, kills, fields):
    stack = local_stack.Stack(tmp_path / "s")
    data = owned_record(stack, **fields)
    (stack.dir / "session.json").write_text(json.dumps({"token": "t"}))
    ran = []
    monkeypatch.setattr(local_stack.subprocess, "run", lambda argv, **kw: ran.append("smoke")
                        or subprocess.CompletedProcess(argv, 0, "CASE_ID=c\n", ""))
    monkeypatch.setattr(local_stack, "stop_api", lambda *a: ran.append("stop") or "stopped")

    def popen(*a, **kw):
        ran.append("launch")
        raise OSError("intercepted")
    monkeypatch.setattr(local_stack.subprocess, "Popen", popen)
    assert cli(stack.dir, "smoke", "--restart-api") == 1
    assert "restart refused" in capsys.readouterr().err
    assert ran == [] and kills == []
    assert stack.load()["api"] == data["api"]  # the record is intact


def test_legacy_single_records_stay_readable_and_recoverable(tmp_path, capsys, kills):
    """A pre-P3 record (no adapter or model fields) still shows status and stops."""
    stack = local_stack.Stack(tmp_path / "s")
    owned_record(stack, investigator="deterministic")
    assert cli(stack.dir, "status") == 1  # no database is running here
    assert "api: owned (port" in (err := capsys.readouterr().err)
    assert "investigator deterministic, database sentinel" in err
    other = local_stack.Stack(tmp_path / "t")
    gone_record(other, investigator="three-role")  # even an ambiguous one needs no metadata
    assert cli(other.dir, "down") == 0
    assert other.load()["api"] is None and kills == []


THREE_ROLE = {"investigator": "three-role", "adapter": "deterministic", "claude_model": None}
LEGACY = {"investigator": "deterministic"}  # a pre-P3 record


@pytest.mark.parametrize("fields, argv, change", [
    (THREE_ROLE, [], "investigator three-role (adapter deterministic) -> deterministic"),
    (THREE_ROLE, ["--investigator", "three-role", "--agent-adapter", "claude-cli"],
     "-> three-role (adapter claude-cli) (model opus)"),
    (LEGACY, ["--investigator", "claude-cli"], "investigator deterministic -> claude-cli"),
    (LEGACY, ["--scorer", "model"], "scorer rule -> model"),
    (LEGACY, ["--database", "other"], "database sentinel -> other"),
    (LEGACY, ["port"], "port "),
], ids=["investigator", "adapter", "single-live", "scorer", "database", "port"])
def test_up_against_a_running_api_refuses_a_different_configuration(
        tmp_path, monkeypatch, capsys, hostile, kills, fields, argv, change):
    stack = local_stack.Stack(tmp_path / "s")
    data = owned_record(stack, **fields)
    touched = []

    def start_database(*a):
        touched.append("db")
        raise local_stack.StackError("the database was touched")
    monkeypatch.setattr(local_stack, "start_database", start_database)
    monkeypatch.setattr(local_stack, "start_api", lambda *a: touched.append("api"))
    port = data["api"]["port"]
    if argv == ["port"]:
        argv, port = [], devdb.free_port()
    code = cli(stack.dir, "up", *argv, port=port, db_port=data["database"]["port"])
    err = capsys.readouterr().err
    assert code == 1, err
    assert "already running with a different configuration" in err and change in err, err
    assert "nothing was changed" in err
    assert touched == [] and kills == []
    assert stack.load()["api"] == data["api"]


# ---- end to end on a real stack -------------------------------------------------------------

class Helper:
    """The real helper as a subprocess on a task-owned state directory and free ports."""

    def __init__(self, tmp_path):
        self.state, self.port, self.db_port = tmp_path / "state", devdb.free_port(), \
            devdb.free_port()
        self.env = {k: v for k, v in os.environ.items()
                    if k not in ("PYTHONPATH", "SENTINEL_TEST_DATABASE_URL")}
        self.env.update(HOSTILE, SENTINEL_LIVE_CLAUDE="0",
                        SENTINEL_CLAUDE_EXECUTABLE=str(tmp_path / "no-such-claude"))
        self.outputs = []

    def run(self, *args, ok=True):
        done = subprocess.run([sys.executable, str(ROOT / "scripts" / "local_stack.py"),
                               "--state-dir", str(self.state), "--port", str(self.port),
                               "--db-port", str(self.db_port), *args], cwd=ROOT, env=self.env,
                              capture_output=True, text=True, timeout=600)
        self.outputs.append(done.stdout + done.stderr)
        assert (done.returncode == 0) == ok, (args, done.stdout[-2000:], done.stderr[-2000:])
        return done.stdout + done.stderr

    def stage(self, *args):
        """One smoke_thin_path stage against the running API (token via environment)."""
        env = {**self.env, "SENTINEL_TOKEN": self.token}
        done = subprocess.run([sys.executable, str(ROOT / "scripts" / "smoke_thin_path.py"),
                               "--base-url", f"http://127.0.0.1:{self.port}", *args],
                              env=env, capture_output=True, text=True, timeout=300)
        self.outputs.append(done.stdout + done.stderr)
        assert done.returncode == 0, (args, done.stdout[-2000:], done.stderr[-2000:])
        return done.stdout

    @property
    def token(self):
        return json.loads((self.state / "session.json").read_text())["token"]

    @property
    def record(self):
        return local_stack.Stack(self.state).load()["api"]

    def get(self, path):
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}",
                                         headers={"Authorization": f"Bearer {self.token}"})
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read())

    def owner(self):
        return psycopg.connect(local_stack.cluster(local_stack.Stack(self.state),
                                                   self.db_port).url("sentinel"),
                               row_factory=dict_row)

    def down(self):
        done = subprocess.run([sys.executable, str(ROOT / "scripts" / "local_stack.py"),
                               "--state-dir", str(self.state), "down"], cwd=ROOT, env=self.env,
                              capture_output=True, text=True, timeout=120)
        assert done.returncode == 0, done.stderr[-1000:]
        assert local_stack.port_state(self.port, None) == "free"
        assert local_stack.port_state(self.db_port, None) == "free"

    def assert_safe(self):
        token = self.token
        log = (self.state / "api.log").read_text(encoding="utf-8", errors="replace")
        for text in [*self.outputs, log]:
            assert token not in text and "postgresql://" not in text
            assert "password" not in text.lower()


def case_id(output):
    return output.rsplit("CASE_ID=", 1)[1].split()[0]


def stored(conn, case):
    workflows = conn.execute("SELECT id, status, body FROM agent_workflows WHERE case_id = %s"
                             " ORDER BY started_at", (case,)).fetchall()
    runs = conn.execute("SELECT body FROM agent_runs WHERE case_id = %s ORDER BY seq",
                        (case,)).fetchall()
    steps = conn.execute("SELECT body FROM agent_steps WHERE case_id = %s ORDER BY step_seq",
                         (case,)).fetchall()
    pins = conn.execute("SELECT body->'pins' AS pins FROM cases WHERE id = %s",
                        (case,)).fetchone()["pins"]
    counts = conn.execute(
        "SELECT (SELECT count(*) FROM action_intents WHERE case_id = %(c)s) AS intents,"
        " (SELECT count(*) FROM approvals ap JOIN action_intents i ON i.id = ap.intent_id"
        "  WHERE i.case_id = %(c)s) AS approvals,"
        " (SELECT count(*) FROM simulated_actions sa JOIN approvals ap ON ap.id ="
        "  sa.approval_id JOIN action_intents i ON i.id = ap.intent_id WHERE i.case_id = %(c)s)"
        "  AS actions", {"c": case}).fetchone()
    return {"workflows": workflows, "runs": [r["body"] for r in runs],
            "steps": [s["body"] for s in steps], "pins": pins, **counts}


@needs_pg
def test_default_single_investigator_ignores_an_inherited_live_adapter(tmp_path):
    helper = Helper(tmp_path)
    try:
        started = helper.run("up")
        assert "investigator deterministic, database sentinel" in started
        assert (helper.record["investigator"], helper.record["adapter"],
                helper.record["claude_model"]) == ("deterministic", None, None)
        assert "investigator deterministic," in helper.run("status")
        smoked = helper.run("smoke", "--restart-api")
        assert "runs=investigator:completed" in smoked
        assert "trace workflows=0 legacy_runs=1" in smoked
        assert "before approval runs=1 approvals=0 actions=0" in smoked
        assert "retry_replayed=True same_action=True" in smoked
        assert "case state=closed revision=4" in smoked
        assert helper.get("/healthz")["investigator"] == "deterministic-investigator"
        with helper.owner() as conn:
            record = stored(conn, case_id(smoked))
        assert (record["workflows"], record["actions"]) == ([], 1)
        assert [r["role"] for r in record["runs"]] == ["investigator"]
        helper.assert_safe()
    finally:
        helper.down()


@needs_pg
def test_three_role_deterministic_workflow_survives_restart_and_executes_once(tmp_path):
    helper = Helper(tmp_path)
    try:
        started = helper.run("up", "--investigator", "three-role")  # adapter left implicit
        assert "investigator three-role (adapter deterministic)," in started
        assert (helper.record["investigator"], helper.record["adapter"],
                helper.record["claude_model"]) == ("three-role", "deterministic", None)
        assert "investigator three-role (adapter deterministic)" in helper.run("status")
        config = helper.get("/healthz")["investigator"]
        assert config == "three-role-workflow"

        # Investigation phase: a real persisted workflow, no approval or action yet.
        first = helper.stage("investigate")
        case = case_id(first)
        assert "runs=evidence_analyst:completed,investigator:completed,reviewer:completed" \
            in first
        assert "trace workflows=1 legacy_runs=0 status=completed disposition=recommend" in first
        with helper.owner() as conn:
            before = stored(conn, case)
        (workflow,) = before["workflows"]
        assert workflow["status"] == "completed"
        assert [r["role"] for r in before["runs"]] == ROLES
        assert all(r["status"] == "completed" and "claude" not in r["config"]["name"]
                   for r in before["runs"])
        assert [s["seq"] for s in before["steps"]] == list(
            range(1, len(before["steps"]) + 1))
        assert before["steps"][-1]["kind"] == "workflow_terminated"
        assert before["pins"]["agent_config"] == workflow["body"]["config"]
        assert before["pins"]["agent_config"]["name"] == config
        assert (before["intents"], before["approvals"], before["actions"]) == (1, 0, 0)
        trace = helper.get(f"/v1/cases/{case}/investigation-trace")
        assert trace["selected"]["workflow"]["id"] == str(workflow["id"])
        assert [a["role"] for a in trace["selected"]["attempts"]] == ROLES
        assert [s["seq"] for s in trace["selected"]["steps"]] == [
            s["seq"] for s in before["steps"]]
        intent = helper.get(f"/v1/cases/{case}")["action_intents"][-1]["intent"]
        assert intent["parameters"]["operation"] == workflow["body"]["disposition"]["operation"]

        # The helper's own restart path, between investigation and approval/execution.
        pid = helper.record["pid"]
        smoked = helper.run("smoke", "--restart-api")
        assert "api stopped" in smoked and "investigator three-role (adapter deterministic)," \
            in smoked
        assert "before approval runs=3 approvals=0 actions=0" in smoked
        assert "retry_replayed=True same_action=True" in smoked
        assert helper.record["pid"] != pid
        assert (helper.record["adapter"], helper.record["claude_model"]) == (
            "deterministic", None)

        # After the restart: the first case's history is unchanged and readable, and it
        # executes once without being investigated again.
        again = helper.get(f"/v1/cases/{case}/investigation-trace")
        assert {k: v for k, v in again.items() if k != "read_at"} == {
            k: v for k, v in trace.items() if k != "read_at"}
        executed = helper.stage("execute", case)
        assert "before approval runs=3 approvals=0 actions=0" in executed
        assert "retry_replayed=True same_action=True" in executed
        assert "case state=closed" in executed
        with helper.owner() as conn:
            after = stored(conn, case)
            # A case created by the restarted API pins exactly the same configuration.
            fresh = case_id(helper.stage("investigate"))
            later = stored(conn, fresh)
        assert after["workflows"] == before["workflows"] and after["runs"] == before["runs"]
        assert (after["approvals"], after["actions"]) == (1, 1)
        assert later["pins"]["agent_config"] == before["pins"]["agent_config"]
        assert later["pins"]["tool_config"] == before["pins"]["tool_config"]
        assert [r["role"] for r in later["runs"]] == ROLES
        assert later["workflows"][0]["status"] == "completed"

        # Repeating up: equal is idempotent; a different mode is refused and changes nothing.
        pid = helper.record["pid"]
        assert "already running" in helper.run("up", "--investigator", "three-role")
        refused = helper.run("up", ok=False)
        assert "already running with a different configuration" in refused
        assert "investigator three-role (adapter deterministic) -> deterministic" in refused
        assert helper.record["pid"] == pid
        assert "investigator three-role (adapter deterministic)" in helper.run("status")
        helper.assert_safe()
    finally:
        helper.down()
