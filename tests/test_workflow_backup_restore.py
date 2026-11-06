"""G3D-P2: backup/restore (pg_dump -Fc / pg_restore) keeps populated three-role workflow
history faithfully, with its authority, scope and read-only trace semantics.

Sessions are issued by the operator (the schema owner). Every case is seeded and
investigated by the production service and coordinator connected as the least-privilege
runtime role, with deterministic role adapters and the G3B fault harness, so each workflow,
run and step row is a genuine coordinator record. After restore into a new test-owned
database, the documented procedure re-grants that same runtime role (as `local_stack up
--database` does), and the restored case and trace are read over real HTTP by the
production app as that role, with the original session token. No provider is called.
"""
import json
import subprocess
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

sys.path.insert(0, str(Path(__file__).resolve().parent / "support"))

import agent_cases as ac  # noqa: E402
from sentinel import db  # noqa: E402
from sentinel.agents import coordinator  # noqa: E402
from sentinel.api import create_app  # noqa: E402
from sentinel.db import roles  # noqa: E402
from sentinel.investigators import DeterministicInvestigator  # noqa: E402
from sentinel.service import Sentinel, ServiceError  # noqa: E402
from test_backup_restore import TABLES, counts  # noqa: E402
from test_trace_api import LiveServer, assert_matches_store, wrong_count  # noqa: E402

NOT_FOUND = (404, b'{"error":"not_found"}')


@pytest.fixture
def mono():
    return ac.Monotonic()


@pytest.fixture
def cluster(pg_cluster):
    admin_url, cluster = pg_cluster
    if cluster is None:
        pytest.skip("needs local Postgres client binaries (disposable cluster mode)")
    return cluster


@pytest.fixture
def owned(cluster):
    """Restore targets created by this test (fresh, unique names), dropped afterwards."""
    names = []

    def create(prefix):
        name = f"{prefix}_{uuid.uuid4().hex[:8]}"
        names.append(name)
        return cluster.create_database(name)
    yield create
    with psycopg.connect(cluster.url(), autocommit=True) as conn:
        for name in names:
            conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                sql.Identifier(name)))


def code_of(call):
    with pytest.raises(ServiceError) as raised:
        call()
    return raised.value.code


def ts(value):
    return datetime.fromisoformat(value)


def crash_between_roles(svc, ctx, case):
    def die(_run):
        raise ac.SimulatedProcessDeath()
    with pytest.raises(ac.SimulatedProcessDeath):
        coordinator.run_workflow(svc, ctx, case, 1, {"before_role:investigator": die})


def populate(owner_url, clock, mono):
    """Every workflow ending the trace distinguishes, written by the runtime role."""
    runtime = ac.runtime_url(owner_url)
    owner = Sentinel(owner_url, DeterministicInvestigator(), clock)
    token = owner.create_session(ac.ANALYST)[0]
    plain = ac.service(runtime, ac.workflow(), clock, mono)
    ctx = plain.authenticate(token)
    limit = plain.investigator.limits.workflow_deadline_seconds

    def faulty(**roles_kw):
        return ac.service(runtime, ac.workflow(**roles_kw), clock, mono)
    cases = {}
    # Completed recommend: three roles, claims and tools; the case awaits a human.
    cases["completed"] = ac.seed(plain, ctx, "D01", clock)["case"]["id"]
    plain.investigate(ctx, cases["completed"], 1)
    # Reviewer challenge, a revision, then abstain.
    cases["abstained"] = ac.seed(plain, ctx, "D05", clock)["case"]["id"]
    faulty(investigator=ac.FaultyRole("investigator", behaviours=[("map", wrong_count)] * 2)
           ).investigate(ctx, cases["abstained"], 1)
    # A provider failure, then a repeat attempt that completes.
    cases["repeated"] = ac.seed(plain, ctx, "D07", clock)["case"]["id"]
    faulty(investigator=ac.FaultyRole("investigator", behaviours=[
        ("fail", "provider_unavailable")])).investigate(ctx, cases["repeated"], 1)
    # A crash between roles, explicit recovery (inconclusive, terminal_by recovery), and a
    # retry: one case with two workflows.
    cases["recovered"] = ac.seed(plain, ctx, "D14", clock)["case"]["id"]
    crash_between_roles(plain, ctx, cases["recovered"])
    started = ac.workflows(runtime, cases["recovered"])[0]["started_at"]
    clock.now = ts(started) + timedelta(seconds=limit + 31)
    assert code_of(lambda: plain.investigate(ctx, cases["recovered"], 2)) == \
        "investigation_recovered"
    revision = plain.get_case(ctx, cases["recovered"])["case"]["revision"]
    plain.investigate(ctx, cases["recovered"], revision)
    # A crash left running: still before its deadline when the backup is taken.
    cases["running"] = ac.seed(plain, ctx, "D14", clock, prefix="running")["case"]["id"]
    crash_between_roles(plain, ctx, cases["running"])
    # Other scopes: another session of the same tenant, and another tenant with its own case.
    same_tenant = owner.create_session(ac.ANALYST, tenant_id=ctx.scope.tenant_id)[0]
    other_tenant = owner.create_session(ac.ANALYST)[0]
    theirs_ctx = plain.authenticate(other_tenant)
    theirs = ac.seed(plain, theirs_ctx, "D01", clock)["case"]["id"]
    plain.investigate(theirs_ctx, theirs, 1)
    # Operator-only model inputs (the runtime role cannot write them).
    owner.provision_accounts(ctx.scope.tenant_id, ctx.scope.session_id, [
        {"account_id": str(uuid.uuid4()), "home_currency": "USD",
         "opened_at": "2025-01-01T00:00:00Z"}])
    owner.record_disclosures(ctx.scope.tenant_id, ctx.scope.session_id, [
        {"external_id": "p2-disclosed", "account_id": str(uuid.uuid4()), "is_fraud": True,
         "disclosed_at": "2026-10-01T00:00:00Z"}])
    return {"runtime": runtime, "token": token, "same_tenant": same_tenant,
            "other_tenant": other_tenant, "cases": cases, "theirs": theirs, "limit": limit}


def content(url) -> dict:
    """Every stored row of every application table, as canonical JSON, in a stable order."""
    with psycopg.connect(url) as conn:
        return {t: sorted(json.dumps(r[0], sort_keys=True) for r in conn.execute(
            sql.SQL("SELECT to_jsonb(t) FROM {} t").format(sql.Identifier(t))))
            for t in sorted(TABLES)}


def differences(a: dict, b: dict) -> set:
    return {t for t in a if a[t] != b[t]}


def dump(cluster, url, path):
    subprocess.run([str(cluster.bin_dir / "pg_dump"), "--format=custom", "--no-owner",
                    f"--file={path}", url], check=True, capture_output=True)
    return path


def restore(cluster, path, target, use_list=None):
    args = [str(cluster.bin_dir / "pg_restore"), "--no-owner", "--exit-on-error",
            f"--dbname={target}"]
    if use_list is not None:
        args.append(f"--use-list={use_list}")
    subprocess.run([*args, str(path)], check=True, capture_output=True)
    return target


def as_runtime(owner_url, runtime_url):
    """The same runtime role on another database of this cluster."""
    return make_conninfo(owner_url, user=conninfo_to_dict(runtime_url)["user"])


def workflow_ids(url, case):
    return [w["id"] for w in ac.workflows(url, case)]


def traces(server, token, url, cases) -> dict:
    """Each case's default trace, plus every workflow of each case selected by id."""
    found = {}
    for name, case in cases.items():
        route = f"/v1/cases/{case}/investigation-trace"
        status, body, _ = server.get(route, token)
        assert status == 200, (name, status)
        found[name] = json.loads(body)
        for wid in workflow_ids(url, case):
            status, body, _ = server.get(f"{route}?workflow_id={wid}", token)
            assert status == 200, (name, wid, status)
            found[f"{name}:{wid}"] = json.loads(body)
    return found


def without_read_at(found: dict) -> dict:
    return {k: {f: v for f, v in t.items() if f != "read_at"} for k, t in found.items()}


def test_populated_workflow_history_survives_backup_and_restore(database_url, cluster, owned,
                                                                clock, mono, tmp_path):
    world = populate(database_url, clock, mono)
    runtime, token, cases = world["runtime"], world["token"], world["cases"]
    source = content(database_url)
    populated = counts(database_url)  # also checks the exact 16-table inventory
    # Deterministic adapters: the exact counts of this history (the C08 scenario has 0/0).
    assert {t: populated[t] for t in ("agent_workflows", "agent_runs", "agent_steps",
                                      "cases", "action_intents", "approvals",
                                      "simulated_actions", "account_profiles",
                                      "fraud_disclosures")} == {
        "agent_workflows": 7, "agent_runs": 20, "agent_steps": 128, "cases": 6,
        "action_intents": 5, "approvals": 0, "simulated_actions": 0,
        "account_profiles": 1, "fraud_disclosures": 1}, populated
    records = [w for case in [*cases.values(), world["theirs"]]
               for w in ac.workflows(runtime, case)]
    assert sorted((w["status"], w["terminal_by"]) for w in records) == sorted(
        [("completed", "coordinator")] * 5 + [("inconclusive", "recovery"),
                                              ("running", None)])
    kinds = {w["disposition"]["kind"] for w in records if w.get("disposition")}
    assert {"recommend", "abstain", "inconclusive"} <= kinds, kinds
    read_at = clock.now
    with LiveServer(create_app(ac.service(runtime, ac.workflow(), clock, mono))) as server:
        before = traces(server, token, runtime, cases)
    assert content(database_url) == source  # the source reads changed nothing

    archive = dump(cluster, database_url, tmp_path / "workflows.dump")
    restored = restore(cluster, archive, owned("restored"))
    assert counts(restored) == populated
    assert content(restored) == source  # every row of all 16 tables, field for field
    assert db.migrate(restored) == []
    with psycopg.connect(restored) as conn:  # append-only triggers bind even the owner
        for statement in ("DELETE FROM audit_events", "DELETE FROM agent_steps",
                          "UPDATE agent_steps SET payload = '{}'::jsonb"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(statement)
            conn.rollback()

    # The documented procedure: re-grant the runtime role on the restored database.
    rt = as_runtime(restored, runtime)
    roles.grant_runtime(restored, conninfo_to_dict(runtime)["user"])
    with psycopg.connect(rt) as conn:  # still least privilege on the restored copy
        for statement in ("DELETE FROM agent_steps", "DELETE FROM cases",
                          "INSERT INTO api_sessions SELECT * FROM api_sessions LIMIT 0"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(statement)
            conn.rollback()
    restored_svc = ac.service(rt, ac.workflow(), clock, mono)
    granted = content(restored)
    with LiveServer(create_app(restored_svc)) as server:
        after = traces(server, token, rt, cases)
        # Scope and selection denials survive restore.
        for name, case in cases.items():
            route = f"/v1/cases/{case}/investigation-trace"
            for other in (world["same_tenant"], world["other_tenant"]):
                assert server.get(route, other)[:2] == NOT_FOUND, name
                assert server.get(f"/v1/cases/{case}", other)[:2] == NOT_FOUND, name
            their_wid = workflow_ids(rt, world["theirs"])[0]
            assert server.get(f"{route}?workflow_id={their_wid}", token)[:2] == NOT_FOUND
        assert server.get(f"/v1/cases/{world['theirs']}/investigation-trace",
                          token)[:2] == NOT_FOUND
        assert server.get(f"/v1/cases/{cases['completed']}/investigation-trace")[0] == 401
        # A running workflow past its recovery point is reported, never recovered, by GETs.
        running = ac.workflows(rt, cases["running"])[0]
        clock.now = ts(running["started_at"]) + timedelta(seconds=world["limit"] + 31)
        for _ in range(3):
            status, body, _ = server.get(
                f"/v1/cases/{cases['running']}/investigation-trace", token)
            workflow = json.loads(body)["selected"]["workflow"]
            assert (status, workflow["status"], workflow["deadline_status"]) == (
                200, "running", "recovery_due")
    assert content(restored) == granted  # no read changed any row (no approval or action)

    # The restored traces equal the source traces; read_at is a read time, compared apart.
    assert without_read_at(after) == without_read_at(before)
    for found in (before, after):  # each read reports the reading server's clock
        assert {ts(t["read_at"].replace("Z", "+00:00")) for t in found.values()} == {read_at}
    for name, trace in after.items():
        assert_matches_store(rt, trace["selected"])  # projection = restored rows
    recovered = workflow_ids(rt, cases["recovered"])
    assert [w["id"] for w in after["recovered"]["workflows"]] == recovered[::-1]
    assert after[f"recovered:{recovered[0]}"]["selected"]["workflow"]["terminal_by"] == \
        "recovery"
    assert after["repeated"]["selected"]["attempts"][1]["failure_code"] == \
        "provider_unavailable"
    assert after["abstained"]["selected"]["workflow"]["disposition"]["kind"] == "abstain"
    running_trace = after["running"]["selected"]
    assert (running_trace["workflow"]["recorded_role_invocations"],
            running_trace["workflow"]["recorded_tool_calls"],
            running_trace["workflow"]["disposition"]) == (None, None, None)  # unknown, not 0
    repeated = after["repeated"]["selected"]
    assert repeated["attempts"][1]["usage"] is None  # a failed call's usage stays unknown
    assert repeated["usage_summary"] == {"reported_attempts": 0, "not_applicable_attempts": 3,
                                         "unknown_attempts": 1, "input_tokens": None,
                                         "output_tokens": None}

    # The human boundary still holds on the restored copy: one real approval, one key, a
    # retry replays the same single simulated action.
    http = TestClient(create_app(restored_svc))
    auth = {"Authorization": f"Bearer {token}"}
    view = http.get(f"/v1/cases/{cases['completed']}", headers=auth).json()
    assert view["case"]["state"] == "awaiting_approval"
    approval = http.post("/v1/approvals", headers=auth, json={
        "action_intent_id": view["action_intents"][-1]["intent"]["id"],
        "decision": "approved"})
    assert approval.status_code == 201, approval.text
    execute = {"approval_id": approval.json()["id"], "idempotency_key": str(uuid.uuid4())}
    first = http.post("/v1/actions", headers=auth, json=execute)
    retry = http.post("/v1/actions", headers=auth, json=execute)
    assert first.status_code == retry.status_code == 200, (first.text, retry.text)
    assert retry.json() == {**first.json(), "replayed": True}
    assert counts(restored)["simulated_actions"] == 1
    # Recovery of the restored running workflow happens only on an explicit request.
    ctx = restored_svc.authenticate(token)
    assert code_of(lambda: restored_svc.investigate(ctx, cases["running"], 2)) == \
        "investigation_recovered"
    assert content(database_url) == source  # the source was never touched


def test_content_checks_catch_lost_or_altered_workflow_history(database_url, cluster, owned,
                                                               clock, mono, tmp_path):
    """Negative controls on isolated restored copies (the source is never modified)."""
    world = populate(database_url, clock, mono)
    source = content(database_url)
    archive = dump(cluster, database_url, tmp_path / "workflows.dump")
    faithful = restore(cluster, archive, owned("faithful"))
    assert differences(source, content(faithful)) == set()

    # One stored step lost (the append-only trigger is bypassed only in this copy's session).
    lost_step = restore(cluster, archive, owned("lost_step"))
    with psycopg.connect(lost_step, autocommit=True) as conn:
        conn.execute("SET session_replication_role = replica")
        conn.execute("DELETE FROM agent_steps WHERE seq = (SELECT max(seq) FROM agent_steps)")
    assert counts(lost_step)["agent_steps"] == counts(database_url)["agent_steps"] - 1
    assert differences(source, content(lost_step)) == {"agent_steps"}

    # One workflow's persisted content altered, with every row count unchanged.
    altered = restore(cluster, archive, owned("altered"))
    with psycopg.connect(altered, autocommit=True) as conn:
        conn.execute("UPDATE agent_workflows SET body = jsonb_set(body,"
                     " '{input_snapshot_sha256}', to_jsonb(repeat('0', 64)))"
                     " WHERE id = (SELECT id FROM agent_workflows ORDER BY id LIMIT 1)")
    assert counts(altered) == counts(database_url)
    assert differences(source, content(altered)) == {"agent_workflows"}

    # The whole agent_steps content absent from the archive: counts and content both differ.
    listing = subprocess.run([str(cluster.bin_dir / "pg_restore"), "--list", str(archive)],
                             check=True, capture_output=True, text=True).stdout
    kept = [line for line in listing.splitlines()
            if not line.rstrip().endswith("TABLE DATA public agent_steps -")
            and " TABLE DATA public agent_steps " not in line]
    assert len(kept) == len(listing.splitlines()) - 1
    use_list = tmp_path / "without-steps.list"
    use_list.write_text("\n".join(kept) + "\n", encoding="utf-8")
    absent = restore(cluster, archive, owned("absent_steps"), use_list)
    assert counts(absent)["agent_steps"] == 0
    assert differences(source, content(absent)) == {"agent_steps"}

    # And the restored trace exposes the loss: it no longer equals the stored source trace.
    rt = as_runtime(lost_step, world["runtime"])
    roles.grant_runtime(lost_step, conninfo_to_dict(world["runtime"])["user"])
    case = world["theirs"]  # the newest workflow, whose last step was removed
    other = world["other_tenant"]
    with LiveServer(create_app(ac.service(world["runtime"], ac.workflow(), clock, mono))) as s:
        expected = json.loads(s.get(f"/v1/cases/{case}/investigation-trace", other)[1])
    with LiveServer(create_app(ac.service(rt, ac.workflow(), clock, mono))) as s:
        damaged = json.loads(s.get(f"/v1/cases/{case}/investigation-trace", other)[1])
    assert len(damaged["selected"]["steps"]) == len(expected["selected"]["steps"]) - 1
    assert damaged != expected
    assert content(database_url) == source
