"""G3D-P4a A and C: versioned run artifacts with honest measurements, and scoped read-only
exports with partially blinded review packets.

Real-database tests run the accepted runner and service as a least-privilege runtime role
on disposable PostgreSQL with deterministic comparators only. The fixture record under
tests/fixtures/agent_eval_p4a is hand-made test data, never live evidence.
"""
import copy
import csv
import importlib.util
import io
import json
import logging
import sys
from pathlib import Path

import psycopg
import pytest

from test_agent_eval_privileges import assert_no_secrets, runner, runtime_role

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests" / "support"))

import agent_cases as ac  # noqa: E402
from agent_eval_support import artifact, measure  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "agent_eval_p4a" / "run-fixture.json"


def load(path):
    spec = importlib.util.spec_from_file_location(path.stem + "_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def evaluator():
    return load(ROOT / "scripts" / "agent_eval.py")


def fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


# ---- A: rates, quantiles and integrity -----------------------------------------------------

def test_rates_and_nearest_rank_quantiles_match_hand_calculation():
    assert artifact.rate(0, 0) == {"numerator": 0, "denominator": 0, "value": None,
                                   "text": "n/a (0/0)"}
    assert artifact.rate(0, 3)["value"] == 0.0 and artifact.rate(0, 3)["text"].startswith("0/3")
    assert artifact.rate(2, 3)["text"] == "2/3 (0.667)"
    sample = [5.0, 1.0, 3.0, 2.0, 4.0]  # sorted 1..5: p50 = 3rd, p95 = ceil(4.75) = 5th
    assert (artifact.nearest_rank(sample, 0.5), artifact.nearest_rank(sample, 0.95),
            artifact.nearest_rank(sample, 1.0)) == (3.0, 5.0, 5.0)
    assert artifact.nearest_rank([1.0, 2.0, 3.0, 4.0], 0.5) == 2.0  # ceil(2.0) = 2nd
    assert artifact.nearest_rank([], 0.5) is None
    assert artifact.latency_summary([])["n"] == 0


def test_role_intervals_pair_cumulative_markers_and_keep_unknowns():
    steps = [
        {"kind": "role_started", "role": "evidence_analyst", "agent_run_id": "a", "attempt": 1,
         "elapsed_ms": 100},
        {"kind": "tool_executed", "elapsed_ms": 180},
        {"kind": "role_completed", "role": "evidence_analyst", "agent_run_id": "a",
         "elapsed_ms": 250},
        {"kind": "role_started", "role": "investigator", "agent_run_id": "b", "attempt": 1,
         "elapsed_ms": 300},
        {"kind": "role_started", "role": "reviewer", "agent_run_id": "c", "attempt": 1,
         "elapsed_ms": 400},
        {"kind": "role_failed", "role": "reviewer", "agent_run_id": "c",
         "failure_code": "budget_exhausted", "elapsed_ms": 410},
    ]
    a, b, c = measure.role_intervals(steps)
    assert (a["interval_ms"], a["status"], a["pre_submission"]) == (150, "recorded", False)
    assert "not provider latency" in a["label"]
    assert (b["interval_ms"], b["status"]) == (None, "unknown (no end marker)")
    assert (c["interval_ms"], c["failure_code"], c["pre_submission"]) == (
        10, "budget_exhausted", True)


def test_validation_refuses_censored_old_and_relabelled_artifacts():
    good = artifact.validate_run(fixture())
    assert good["record"]["planned_cases"] == ["D01", "D02", "D03", "D04", "D11"]
    censored = fixture()  # the wrong hold on D03 quietly removed
    rows = censored["comparators"]["C1"]["attempts"]
    del rows[2]
    for i, row in enumerate(rows, 1):
        row["index"], row["attempt_id"] = i, f"C1:{i}:{row['case']}"
    censored["comparators"]["C1"]["counts"] = {"attempts": 4, "dispositions": 2,
                                               "inconclusive": 1, "error": 1}
    with pytest.raises(artifact.ArtifactError, match="planned cases"):
        artifact.validate_run(censored)
    old = fixture()
    del old["record"]["artifact_version"]
    with pytest.raises(artifact.ArtifactError, match="pre-P4a"):
        artifact.validate_run(old)
    renamed = fixture()  # request latency must not be passed off as workflow elapsed
    renamed["comparators"]["C2"]["attempts"][0]["workflow_elapsed_ms"] = 10000
    with pytest.raises(artifact.ArtifactError, match="not measured"):
        artifact.validate_run(renamed)
    recounted = fixture()
    recounted["comparators"]["C1"]["counts"]["dispositions"] = 2
    with pytest.raises(artifact.ArtifactError, match="counts"):
        artifact.validate_run(recounted)


def test_late_returns_are_observed_only_until_the_cutoff():
    from sentinel.agents.capacity import late_worker_event
    logger = logging.getLogger(measure.AGENT_LOGGER)
    level = logger.level
    with measure.LateReturnObserver() as observer:
        late_worker_event("wf-1", "investigator", 1, 2.5)
    late_worker_event("wf-1", "reviewer", 1, 9.0)  # after the cutoff: not observed
    assert observer.for_workflows(["wf-1"]) == [
        {"workflow_id": "wf-1", "role": "investigator", "attempt": 1, "seconds": 2.5}]
    assert observer.for_workflows(["wf-2"]) == [] and observer.cutoff is not None
    assert logger.level == level and observer not in logger.handlers


# ---- A: the real runner's additive fields ---------------------------------------------------

def test_runner_records_scoped_ids_pins_and_unmeasured_elapsed(database_url):
    _role, rt = runtime_role(database_url)
    code, output = runner("--comparators", "C0,C2-det", "--cases", "D01,D04",
                          operator=database_url, runtime=rt)
    assert code == 0, output
    assert_no_secrets(output, database_url, rt)
    doc = artifact.validate_run(json.loads(output))
    record = doc["record"]
    assert record["artifact_version"] == artifact.RUN_VERSION and record["quota"] == "unknown"
    assert record["comparator_config"]["C2-det"]["pin"]["name"] == "three-role-workflow"
    assert record["comparator_config"]["C0"]["model_alias"] is None
    with psycopg.connect(database_url) as conn:
        for name, result in doc["comparators"].items():
            for row in result["attempts"]:
                ids = row["ids"]
                stored = conn.execute("SELECT tenant_id::text, session_id::text FROM cases"
                                      " WHERE id = %s", (ids["case_id"],)).fetchone()
                assert stored == (ids["tenant_id"], ids["session_id"])
                assert row["workflow_elapsed_ms"] is None
                assert row["workflow_elapsed_status"] == "not_measured"
                assert row["capacity"]["scope"].startswith("this attempt's service")
                basis = conn.execute("SELECT finding IS NOT NULL FROM agent_runs WHERE id"
                                     " = %s", (row["disposition"]["basis_run_id"],)).fetchone()
                assert basis == (True,)
                assert row["reservation"]["reserved_invocations"] == 0
                if name == "C2-det":
                    assert [i["role"] for i in row["role_intervals"]] == [
                        "evidence_analyst", "investigator", "reviewer"]
                    assert row["late_returns"]["after_cutoff"] == "unknown"
                    assert row["disposition"]["source"] == "workflow_disposition"
                else:
                    assert row["workflow_ids"] == [] and row["role_intervals"] == []


def test_the_adopted_run_is_the_workflow_basis_not_the_last_role(database_url, clock):
    module = evaluator()
    url = ac.runtime_url(database_url)
    from test_trace_api import wrong_count
    revise = ac.FaultyRole("investigator", behaviours=[("map", wrong_count)] * 2)
    svc = ac.service(url, ac.workflow(investigator=revise), clock, ac.Monotonic())
    ctx = svc.authenticate(ac.session(url, clock))
    case = ac.seed(svc, ctx, "D05", clock)["case"]["id"]
    svc.investigate(ctx, case, 1)
    stored = module.stored_measurements(url, case, ctx.scope)
    with psycopg.connect(database_url) as conn:
        runs = conn.execute("SELECT id::text, body->>'role' FROM agent_runs WHERE case_id = %s"
                            " ORDER BY seq", (case,)).fetchall()
    investigators = [i for i, role in runs if role == "investigator"]
    assert runs[-1][1] == "reviewer" and len(investigators) == 2
    assert stored["disposition"]["kind"] == "abstain"
    assert stored["disposition"]["basis_run_id"] == investigators[1]  # the revision
    assert stored["recorded_role_attempts"] == len(runs)


def test_a_telemetry_failure_never_changes_the_recorded_outcome(database_url, monkeypatch):
    module = evaluator()
    _role, rt = runtime_role(database_url)

    def broken(*_args):
        raise psycopg.OperationalError("CANARY-telemetry-8812")
    monkeypatch.setattr(module, "stored_measurements", broken)
    from sentinel.investigators import DeterministicInvestigator
    from sentinel.service import Sentinel
    row = module.attempt(Sentinel(database_url, DeterministicInvestigator()), rt,
                         module.comparator("C0"), "D01")
    assert row["outcome"] == "disposition"
    assert row["telemetry"] == {"status": "unavailable", "error": "OperationalError"}
    assert "CANARY-telemetry-8812" not in json.dumps(row)


def test_annotations_need_a_source_and_time(tmp_path):
    module = evaluator()
    good = tmp_path / "a.json"
    good.write_text(json.dumps([{"field": "quota", "value": "about half left",
                                 "source": "owner, claude.ai usage page",
                                 "recorded_at": "2026-11-06T10:00:00-07:00"}]))
    assert module.load_annotations(good)[0]["source"].startswith("owner")
    bad = tmp_path / "b.json"
    bad.write_text(json.dumps([{"field": "quota", "value": "plenty"}]))
    with pytest.raises(module.Refused) as refusal:
        module.load_annotations(bad)
    assert refusal.value.code == "annotations_invalid"



# ---- C: scoped read-only export and partially blinded review packets -----------------------

def report():
    return load(ROOT / "scripts" / "agent_eval_report.py")


def real_run(database_url, cases="D01,D11"):
    """A real C0 + C2-det run artifact (every attempt has its own fresh session, so the
    database also holds other sessions' data) and the runtime URL that wrote it."""
    _role, rt = runtime_role(database_url)
    code, output = runner("--comparators", "C0,C2-det", "--cases", cases,
                          operator=database_url, runtime=rt)
    assert code == 0, output
    return artifact.validate_run(json.loads(output)), rt


def test_export_is_scoped_read_only_and_matches_storage(database_url):
    doc, rt = real_run(database_url)
    bundle = report().export_run(rt, doc)
    assert bundle["version"] == artifact.BUNDLE_VERSION
    assert bundle["mutation_proof"]["unchanged"] is True
    before = bundle["mutation_proof"]["before"]
    assert before["approvals"][0] == 0 and before["simulated_actions"][0] == 0
    exports = {e["attempt_id"]: e for e in bundle["exports"]}
    assert set(exports) == {r["attempt_id"] for res in doc["comparators"].values()
                            for r in res["attempts"]}
    for result in doc["comparators"].values():
        for row in result["attempts"]:
            export = exports[row["attempt_id"]]
            assert export["ids"] == row["ids"]
            assert export["adopted"]["agent_run_id"] == row["disposition"]["basis_run_id"]
            assert [r["id"] for r in export["runs"] if r["has_finding"]] == [
                row["disposition"]["basis_run_id"]]
    assert "postgresql://" not in json.dumps(bundle)


def test_a_foreign_or_tampered_mapping_is_refused_even_with_a_broken_scope_filter(
        database_url, monkeypatch):
    module = report()
    doc, rt = real_run(database_url)
    rows = doc["comparators"]["C0"]["attempts"]
    tampered = copy.deepcopy(doc)  # attempt 1 now points at attempt 2's case (another session)
    tampered["comparators"]["C0"]["attempts"][0]["ids"]["case_id"] = rows[1]["ids"]["case_id"]
    with pytest.raises(module.ExportError, match="not found in the attempt's scope"):
        module.export_run(rt, tampered)
    monkeypatch.setattr(module, "_scope_clause", lambda: ("", ()))  # a broken filter
    with pytest.raises(module.ExportError, match="outside the attempt's tenant/session"):
        module.export_run(rt, tampered)
    monkeypatch.undo()
    module = report()
    swapped = copy.deepcopy(doc)
    swapped["comparators"]["C2-det"]["attempts"][0]["workflow_ids"] = \
        doc["comparators"]["C2-det"]["attempts"][1]["workflow_ids"]
    with pytest.raises(module.ExportError, match="do not match the run artifact"):
        module.export_run(rt, swapped)
    old = copy.deepcopy(doc)
    del old["record"]["artifact_version"]
    with pytest.raises(artifact.ArtifactError):
        module.export_run(rt, old)


def test_the_export_identity_cannot_write(database_url):
    _role, rt = runtime_role(database_url)
    with psycopg.connect(rt) as conn, conn.transaction():
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            conn.execute("UPDATE cases SET revision = revision")
    with psycopg.connect(rt) as conn, pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("DELETE FROM agent_steps")


def test_review_packets_are_partially_blinded_with_a_separate_key(database_url):
    module = report()
    doc, rt = real_run(database_url, "D01,D02,D11")
    bundle = module.export_run(rt, doc)
    packets, key = module.review_packets([bundle], seed=5)
    text = json.dumps(packets)
    assert len(packets["packets"]) == 6 and set(key["packets"]) == {
        p["packet_id"] for p in packets["packets"]}
    for revealing in ("C0", "C2-det", "three-role-workflow", "deterministic-investigator",
                      "evidence_analyst", "reviewer", "D01", "D02", "D11", "acceptable_not",
                      "sha256", "tenant_id", "agent_run_id"):
        assert revealing not in text, revealing
    for row in doc["comparators"]["C2-det"]["attempts"]:
        assert row["ids"]["case_id"] not in text
    for packet in packets["packets"]:
        assert set(packet) == {"packet_id", "evidence", "recommendation", "statements"}
        facts = packet["evidence"]["facts"]  # the case's stored evidence facts, by name
        assert set(facts) == {"amount_minor", "transaction_count_1h"} and None not in             facts.values()
    again, _ = module.review_packets([bundle], seed=5)
    other, _ = module.review_packets([bundle], seed=6)
    order = [key["packets"][p["packet_id"]]["attempt_id"] for p in packets["packets"]]
    assert order == [key["packets"][p["packet_id"]]["attempt_id"] for p in again["packets"]]
    assert sorted(order) == sorted(e["attempt_id"] for e in bundle["exports"])
    assert other["packets"] != packets["packets"]
    assert "comparator" not in json.dumps(packets["packets"])


def test_hostile_text_stays_inert_and_formulas_are_escaped():
    module = report()
    hostile = ['=HYPERLINK("http://example.invalid","x")', "+1+1", "-2", "@SUM(A1)",
               "\tTAB", "Ünïcødé \u202edlrow <script>alert(1)</script>", "ordinary"]
    export = {"attempt_id": "C1:1:D01", "comparator": "C1", "case": "D01",
              "outcome": "disposition", "transaction": {"amount": {"minor_units": 250000}},
              "evidence": [{"name": "transaction_count_1h", "value": -1, "source": "s"}],
              "tool_results": [], "role_outputs": [{"output": {"note": t}} for t in hostile],
              "adopted": {"agent_run_id": "r1", "verification": module.VERIFIED,
                          "source": "single_investigator_finding", "kind": None,
                          "operation": "simulated_hold", "reason_code": "velocity_pattern",
                          "finding": {"rationale": "=1+1 rationale"}}}
    doc = fixture()  # the bundle carries the run its adopted record must agree with
    packets, _key = module.review_packets(
        [{"run_artifact_sha256": artifact.digest(doc), "run": doc, "exports": [export]}],
        seed=1)
    texts = [s["text"] for s in packets["packets"][0]["statements"]]
    assert texts == ["=1+1 rationale", *hostile]  # data, unchanged, in JSON
    rows = list(csv.reader(io.StringIO(module.sheet_csv(packets))))
    assert rows[0] == list(module.SHEET_COLUMNS)
    by_text = {r[3] for r in rows[1:]}
    for text in ["=1+1 rationale", *hostile[:5]]:
        assert "'" + text in by_text and text not in by_text
    assert hostile[5] in by_text and "ordinary" in by_text
    assert "-1" in by_text  # a typed numeric evidence value is not rewritten
