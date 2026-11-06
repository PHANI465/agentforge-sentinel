"""G3D-P4a B: the development pilot supervisor. A seeded schedule, an owned database-only
cluster reusing local_stack's Stack and identity checks, fresh databases per pair, the
consent and reservation boundary for live pairs, and outcomes kept as recorded.

The preflight test runs the real runner (C0, C2-det) on a real owned cluster. Live pairs
are never run: their tests intercept the runner subprocess and the database lifecycle, so
no Claude executable, auth command or provider is reached.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import agent_eval_pilot as pilot  # noqa: E402
import local_stack  # noqa: E402
from agent_eval_support import artifact, catalog  # noqa: E402
from sentinel import devdb  # noqa: E402

needs_pg = pytest.mark.skipif(devdb.find_pg_bin() is None, reason="needs PostgreSQL binaries")
URL_CANARY = "postgresql://canary-owner@127.0.0.1:1/never"


def make_run(comparators, cases, outcomes=None, status="complete"):
    """A valid version-1 artifact (test data, not a real run). outcomes maps
    (comparator, case) -> (outcome, operation, reason)."""
    outcomes = outcomes or {}
    result = {}
    for name in comparators:
        rows = []
        for i, case in enumerate(cases, 1):
            outcome, operation, reason = outcomes.get((name, case),
                                                      ("disposition", "escalate", "velocity_pattern"))
            row = {"index": i, "attempt_id": f"{name}:{i}:{case}", "case": case,
                   "outcome": outcome, "request_latency_s": 0.1, "workflow_elapsed_ms": None}
            if outcome == "disposition":
                row["disposition"] = {"kind": "recommend" if name.startswith("C2") else None,
                                      "operation": operation, "reason_code": reason}
            rows.append(row)
        counts = {"attempts": len(rows)}
        for row in rows:
            key = "dispositions" if row["outcome"] == "disposition" else row["outcome"]
            counts[key] = counts.get(key, 0) + 1
        result[name] = {"counts": counts, "attempts": rows, "cases_not_attempted": []}
    return json.dumps({"record": {
        "artifact_version": artifact.RUN_VERSION, "status": status, "stopped": None,
        "comparators_not_started": [], "planned_comparators": list(comparators),
        "planned_cases": list(cases), "authorities": {"runtime_verified": True},
        "cases": {c: {"runtime_sha256": catalog.runtime_digest(c), "faults_not_applied": []}
                  for c in cases}}, "comparators": result})


def seed_where(predicate) -> int:
    """The first seed whose live schedule satisfies predicate (deterministic)."""
    return next(seed for seed in range(1000)
                if predicate(pilot.schedule(list(pilot.CASES), seed)[1:]))


@pytest.fixture
def intercepted(monkeypatch):
    """No database or runner: a scripted runner output per call, recorded argv/env."""
    calls, outputs = [], []

    def provision(stack, data, manifest, root, pair_id):
        manifest["databases"][pair_id] = pilot.database_name(manifest, pair_id)
        return manifest["databases"][pair_id]
    monkeypatch.setattr(pilot, "start", lambda root, manifest, create=False: ("stack", {}))
    monkeypatch.setattr(pilot, "stop", lambda stack, data: None)
    monkeypatch.setattr(pilot, "provision", provision)
    monkeypatch.setattr(pilot, "urls", lambda stack, data, name: (URL_CANARY,
                                                                   URL_CANARY + "-runtime"))

    def invoke(argv, env):
        calls.append({"argv": argv, "env": env})
        return outputs.pop(0)
    monkeypatch.setattr(pilot, "invoke_runner", invoke)
    return calls, outputs


def test_the_plan_is_seeded_complete_and_never_adopts_a_directory(tmp_path):
    one = pilot.plan(tmp_path / "a", 7)["pairs"]
    assert [p["pair_id"] for p in one] == [p["pair_id"] for p in
                                           pilot.plan(tmp_path / "b", 7)["pairs"]]
    assert one[0] == {"pair_id": "P00-det", "comparators": ["C0", "C2-det"],
                      "cases": list(pilot.CASES), "live": False, "reservation": 0,
                      "status": "planned"}
    live = one[1:]
    assert sorted((p["comparators"][0], p["cases"][0]) for p in live) == sorted(
        (c, case) for c in ("C1", "C2") for case in pilot.CASES)
    assert sum(p["reservation"] for p in live) == pilot.ALLOWANCE == 30
    (tmp_path / "used").mkdir()
    (tmp_path / "used" / "old.txt").write_text("someone else's state")
    with pytest.raises(pilot.PilotError, match="never adopted"):
        pilot.plan(tmp_path / "used", 7)


def test_live_pairs_need_the_flag_the_order_and_the_full_reservation(tmp_path, intercepted):
    calls, outputs = intercepted
    root = tmp_path / "p"
    seed = seed_where(lambda live: live[0]["comparators"] == ["C1"]
                      and live[1]["comparators"] == ["C2"])
    pairs = pilot.plan(root, seed)["pairs"]
    first_live = pairs[1]["pair_id"]
    with pytest.raises(pilot.PilotError, match="recorded order"):
        pilot.run_pair(root, first_live, allow_live=True)  # the preflight comes first
    outputs.append((0, make_run(["C0", "C2-det"], list(pilot.CASES)), ""))
    assert pilot.run_pair(root, "P00-det")["status"] == "complete"
    with pytest.raises(pilot.PilotError, match="--allow-live"):
        pilot.run_pair(root, first_live)
    assert len(calls) == 1  # refused before any database or runner work
    name, case = pairs[1]["comparators"][0], pairs[1]["cases"][0]
    outputs.append((0, make_run([name], [case]), ""))
    pilot.run_pair(root, first_live, allow_live=True)
    argv, env = calls[-1]["argv"], calls[-1]["env"]
    assert argv[-1] == "--allow-live" and URL_CANARY not in " ".join(argv)
    assert env["SENTINEL_EVAL_OPERATOR_URL"] == URL_CANARY  # DSNs only via environment
    manifest = pilot.load(root)
    assert manifest["reserved"] == artifact.RESERVATIONS[name] == 1
    nxt = pairs[2]  # a C2 pair: all 5 reservations are needed before anything starts
    manifest["reserved"] = 26
    pilot.save(root, manifest)
    with pytest.raises(pilot.PilotError, match="5 reservations needed, 4 left"):
        pilot.run_pair(root, nxt["pair_id"], allow_live=True)
    assert pilot.load(root)["reserved"] == 26 and len(calls) == 2
    manifest = pilot.load(root)
    manifest["reserved"] = 25  # exactly enough
    pilot.save(root, manifest)
    outputs.append((0, make_run(nxt["comparators"], nxt["cases"]), ""))
    pilot.run_pair(root, nxt["pair_id"], allow_live=True)
    assert pilot.load(root)["reserved"] == 30 and len(calls) == 3


def test_a_wrong_hold_is_kept_scored_and_stops_the_pass(tmp_path, intercepted):
    calls, outputs = intercepted
    root = tmp_path / "p"
    pilot.plan(root, seed_where(lambda live: live[0]["cases"][0] in ("D03", "D04", "D11")))
    outputs.append((0, make_run(["C0", "C2-det"], list(pilot.CASES)), ""))
    pilot.run_pair(root, "P00-det")
    manifest = pilot.load(root)
    pair = next(p for p in manifest["pairs"] if p["status"] == "planned")
    name, case = pair["comparators"][0], pair["cases"][0]
    hold = ("disposition", "simulated_hold", "unusual_amount")
    outputs.append((0, make_run([name], [case], {(name, case): hold}), ""))
    result = pilot.run_pair(root, pair["pair_id"], allow_live=True)
    manifest = pilot.load(root)
    assert catalog.wrong_hold(case, {"operation": "simulated_hold"})
    assert result["status"] == "complete"  # the disposition happened; it is not erased
    assert "wrong hold scored unacceptable" in result["stop_reason"]
    assert manifest["status"] == "incomplete"
    assert manifest["not_attempted"] == [p["pair_id"] for p in manifest["pairs"]
                                         if p["status"] == "planned"]
    kept = json.loads((root / result["run_file"]).read_text(encoding="utf-8"))
    assert kept["comparators"][name]["attempts"][0]["disposition"]["operation"] == \
        "simulated_hold"
    with pytest.raises(pilot.PilotError, match="incomplete"):
        pilot.run_pair(root, manifest["not_attempted"][0], allow_live=True)


def test_a_hold_the_case_permits_does_not_stop_the_pass(tmp_path, intercepted):
    _calls, outputs = intercepted
    root = tmp_path / "p"
    pilot.plan(root, seed_where(lambda live: live[0]["cases"][0] == "D01"))
    outputs.append((0, make_run(["C0", "C2-det"], list(pilot.CASES)), ""))
    pilot.run_pair(root, "P00-det")
    pair = next(p for p in pilot.load(root)["pairs"] if p["status"] == "planned")
    name = pair["comparators"][0]
    outputs.append((0, make_run([name], ["D01"], {(name, "D01"): (
        "disposition", "simulated_hold", "velocity_pattern")}), ""))
    assert pilot.run_pair(root, pair["pair_id"], allow_live=True)["stop_reason"] is None
    assert pilot.load(root)["status"] == "planned"


@pytest.mark.parametrize("code, outcome, expected", [
    (3, None, "incomplete"), (0, "error", "complete"), (2, None, "failed")])
def test_setup_refusal_and_typed_failures_stop_with_earlier_results_kept(
        tmp_path, intercepted, code, outcome, expected):
    _calls, outputs = intercepted
    root = tmp_path / "p"
    pilot.plan(root, 3)
    if code == 2:
        output = "refused: runtime_unsafe: the runtime login is not least privilege"
    elif code == 3:
        output = make_run(["C0", "C2-det"], list(pilot.CASES), status="incomplete")
    else:
        output = make_run(["C0", "C2-det"], list(pilot.CASES),
                          {("C0", "D02"): (outcome, None, None)})
    outputs.append((code, output, ""))
    result = pilot.run_pair(root, "P00-det")
    assert result["status"] == expected and result["stop_reason"]
    manifest = pilot.load(root)
    assert manifest["status"] == "incomplete" and len(manifest["not_attempted"]) == 10
    assert (root / "runs" / "P00-det.json").read_text(encoding="utf-8") == output


def test_tampered_or_foreign_state_is_refused_without_touching_it(tmp_path, intercepted):
    root = tmp_path / "p"
    pilot.plan(root, 3)
    manifest = pilot.load(root)
    manifest["owner"] = "0" * 32
    (root / pilot.MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(pilot.PilotError, match="does not match"):
        pilot.load(root)
    with pytest.raises(pilot.PilotError, match="not an owned pilot root"):
        pilot.load(tmp_path)
    other = tmp_path / "q"
    pilot.plan(other, 3)
    (other / "stack").mkdir()
    (other / "stack" / "someone.txt").write_text("not ours")
    with pytest.raises(pilot.PilotError, match="cluster state refused"):
        pilot.stack_of(other, pilot.load(other))


@needs_pg
def test_cleanup_refuses_a_database_that_is_not_this_pilots(tmp_path):
    root = tmp_path / "p"
    pilot.plan(root, 3)
    manifest = pilot.load(root)
    stack, data = pilot.start(root, manifest, create=True)
    pilot.stop(stack, data)
    manifest["databases"]["P00-det"] = "postgres"  # a tampered mapping
    pilot.save(root, manifest)
    with pytest.raises(pilot.PilotError, match="not this pilot's"):
        pilot.cleanup(root, drop=True)
    stack, data = pilot.stack_of(root, pilot.load(root))
    assert local_stack.database_state(stack, data) == "stopped"  # stopped again, kept


@needs_pg
def test_the_real_preflight_uses_a_fresh_owned_database_and_keeps_it_stopped(tmp_path):
    root = tmp_path / "p"
    pilot.plan(root, 11)
    result = pilot.run_pair(root, "P00-det")
    assert (result["status"], result["exit_code"], result["stop_reason"]) == (
        "complete", 0, None)
    doc = artifact.validate_run(json.loads((root / result["run_file"]).read_text("utf-8")))
    assert doc["record"]["authorities"]["runtime_verified"] is True
    for name in ("C0", "C2-det"):
        assert doc["comparators"][name]["counts"] == {"attempts": 5, "dispositions": 5}
    for path in (root / "runs").iterdir():
        assert "postgresql://" not in path.read_text(encoding="utf-8")
    manifest = pilot.load(root)
    stack, data = pilot.stack_of(root, manifest)
    assert local_stack.database_state(stack, data) == "stopped"  # kept for scoring
    assert manifest["status"] == "planned" and manifest["reserved"] == 0
    with pytest.raises(pilot.PilotError, match="no rerun"):
        pilot.run_pair(root, "P00-det")
    assert pilot.cleanup(root, drop=True) == [manifest["databases"]["P00-det"]]
    assert local_stack.database_state(stack, data) == "stopped"
    assert local_stack.port_state(manifest["db_port"], None) == "free"
