"""G3D-P4a D: offline scoring and the descriptive summary.

Hand-calculated expectations come from tests/fixtures/agent_eval_p4a/run-fixture.json, a
hand-made record (not a real run, not live evidence):
- C1: D01 hold/velocity (acceptable), D02 escalate/velocity (acceptable), D03 hold (wrong),
  D04 inconclusive timeout, D11 error. Latencies 1..5 s.
- C2: D01 recommend escalate/velocity (ok), D02 abstain (permitted), D03 abstain
  (permitted), D04 recommend hold (wrong), D11 refused. Latencies 10, 20, 30, 40 s and a
  0.5 s refusal. Claims supported/unsupported: 4/0, 1/1, 2/1, 3/0.
"""
import copy
import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import agent_eval_score as scoring  # noqa: E402
from agent_eval_support import artifact  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "agent_eval_p4a" / "run-fixture.json"


def fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_metrics_match_the_hand_calculation():
    summary = scoring.score([("fixture", fixture())])
    c1, c2 = summary["comparators"]["C1"], summary["comparators"]["C2"]
    assert c1["counts"] == {"attempts": 5, "dispositions": 3, "inconclusive": 1, "refused": 0,
                            "pending": 0, "error": 1, "not_attempted": 0}
    assert c1["inconclusive_by_code"] == {"timeout": 1}
    assert c1["acceptable_recommendation"]["text"] == "2/3 (0.667)"
    assert c1["wrong_holds"]["attempts"] == ["C1:3:D03"]
    assert c1["useful_abstention"]["status"] == "unobservable"  # escalate is not abstention
    assert (c1["request_latency"]["p50"], c1["request_latency"]["p95"],
            c1["request_latency"]["max"], c1["request_latency"]["n"]) == (3.0, 5.0, 5.0, 5)
    assert c1["calls"]["reserved_invocations"] == 5
    assert c1["calls"]["recorded_role_attempts"] == {"total": 4, "n": 4, "max": 1,
                                                     "unknown_attempts": 1}
    assert c2["counts"]["dispositions"] == 4 and c2["counts"]["refused"] == 1
    assert c2["acceptable_recommendation"]["text"] == "3/4 (0.750)"
    assert c2["wrong_holds"]["attempts"] == ["C2:4:D04"]
    assert c2["useful_abstention"]["text"] == "1/2 (0.500)"  # D03 of {D03, D04}
    assert c2["unnecessary_abstention"]["text"] == "1/2 (0.500)"  # D02 of {D01, D02}
    assert c2["machine_supported_claims"]["text"] == "10/12 (0.833)"
    assert c2["recommend_with_unsupported_claims"]["text"] == "0/2 (0.000)"
    assert (c2["request_latency"]["p50"], c2["request_latency"]["p95"],
            c2["request_latency"]["max"], c2["request_latency"]["n"]) == (20.0, 40.0, 40.0, 4)
    assert c2["refusal_latency"]["n"] == 1 and c2["refusal_latency"]["max"] == 0.5
    assert c2["calls"]["reserved_invocations"] == 25 and c2["calls"]["repeats"] == 1
    assert c2["calls"]["recorded_role_attempts"]["total"] == 15
    for metrics in (c1, c2):
        assert metrics["tokens"] == "unknown" and metrics["calls"]["provider_requests"] == \
            "unknown"
        assert metrics["workflow_elapsed"].startswith("not measured")
    assert summary["human_rubric"] == {"status": "not scored (no completed review sheet)"}
    assert summary["faults_not_applied"]["D11"] == ["adapter_output"]
    assert summary["hard_gates"]["executed_unauthorized_requests"].startswith("0/0")
    text = scoring.markdown(summary)
    assert "not a quality claim" in text and "significance" in text


def test_zero_denominators_and_real_zeros_are_distinct():
    doc = fixture()
    for row in doc["comparators"]["C2"]["attempts"][:4]:  # no abstention-eligible dispositions
        row["outcome"] = "inconclusive"
        row["failure_codes"] = ["budget_exhausted"]
        row.pop("disposition")
    doc["comparators"]["C2"]["counts"] = {"attempts": 5, "inconclusive": 4, "refused": 1}
    c2 = scoring.score([("fixture", doc)])["comparators"]["C2"]
    assert c2["acceptable_recommendation"]["text"] == "n/a (0/0)"
    assert c2["useful_abstention"]["text"] == "n/a (0/0)"
    assert c2["wrong_holds"]["count"] == 0  # a real zero stays 0


def test_a_wrong_hold_stays_scored_when_the_run_stopped():
    doc = fixture()  # C2 stopped at D04 setup: D04 and D11 never attempted
    doc["record"].update(status="incomplete", comparators_not_started=[],
                         stopped={"comparator": "C2", "case": "D04", "phase": "ingest",
                                  "code": "OperationalError"})
    c2 = doc["comparators"]["C2"]
    c2["attempts"] = c2["attempts"][:3]
    c2["cases_not_attempted"] = ["D04", "D11"]
    c2["counts"] = {"attempts": 3, "dispositions": 3}
    summary = scoring.score([("fixture", doc)], pilot_not_attempted=["L09-C1-D01"])
    assert summary["comparators"]["C1"]["wrong_holds"]["attempts"] == ["C1:3:D03"]
    assert summary["comparators"]["C1"]["acceptable_recommendation"]["text"] == "2/3 (0.667)"
    assert summary["comparators"]["C2"]["not_attempted"] == ["C2:D04", "C2:D11"]
    assert summary["pilot_pairs_not_attempted"] == ["L09-C1-D01"]
    assert summary["runs"][0]["status"] == "incomplete"


def test_a_censored_wrong_result_is_refused():
    doc = fixture()
    rows = doc["comparators"]["C1"]["attempts"]
    del rows[2]  # the wrong hold on D03 quietly removed
    for i, row in enumerate(rows, 1):
        row["index"], row["attempt_id"] = i, f"C1:{i}:{row['case']}"
    doc["comparators"]["C1"]["counts"] = {"attempts": 4, "dispositions": 2, "inconclusive": 1,
                                          "error": 1}
    with pytest.raises(scoring.ScoreError, match="planned cases"):
        scoring.score([("censored", doc)])
    relabelled = fixture()  # the hold relabelled as a refusal
    row = relabelled["comparators"]["C1"]["attempts"][2]
    row["outcome"] = "refused"  # its disposition and missing refusal code contradict it
    with pytest.raises(scoring.ScoreError, match="refused"):
        scoring.score([("relabelled", relabelled)])


def test_mismatched_unknown_or_duplicated_records_are_refused():
    doc = fixture()
    doc["record"]["cases"]["D03"]["runtime_sha256"] = "0" * 64
    with pytest.raises(scoring.ScoreError, match="digest"):
        scoring.score([("x", doc)])
    with pytest.raises(scoring.ScoreError, match="second attempt"):
        scoring.score([("a", fixture()), ("b", fixture())])
    old = fixture()
    old["record"]["artifact_version"] = "sentinel.agent-eval.run/0"
    with pytest.raises(scoring.ScoreError, match="unsupported artifact version"):
        scoring.score([("old", old)])


def write_sheet(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["packet_id", "item", "kind", "text", "supported", "acceptable",
                         "reason_code", "would_correct", "correction"])
        writer.writerows(rows)


def bound_key(path, doc, comparators, rows):
    """A key binding each packet's rows (item, kind, text digest), as review_packets does."""
    packets = {pid: {"comparator": name, "attempt_id": f"{name}:1:D01",
                     "run_artifact_sha256": artifact.digest(doc), "items": {}}
               for pid, name in comparators.items()}
    for row in rows:
        packets[row[0]]["items"][row[1]] = {"kind": row[2],
                                            "text_sha256": artifact.text_digest(row[3])}
    path.write_text(json.dumps({"packets": packets}))


def test_human_metrics_need_completed_sheets_and_a_matching_key(tmp_path):
    doc = fixture()
    key = tmp_path / "key.json"
    blank = tmp_path / "blank.csv"
    blank_rows = [["PK-a", "S1", "statement", "t", "", "", "", "", ""],
                  ["PK-a", "R", "recommendation", "r", "", "", "", "", ""]]
    bound_key(key, doc, {"PK-a": "C1"}, blank_rows)
    write_sheet(blank, blank_rows)
    human = scoring.score([("f", doc)], sheet=blank, key=key)["human_rubric"]
    assert human["C1"]["packets_scored"] == 0 and human["C1"]["packets_not_scored"] == 1
    assert human["C1"]["rubric_supported_statements"]["text"] == "n/a (0/0)"
    assert human["C1"]["review_status"].startswith("not scored")
    done = tmp_path / "done.csv"
    done_rows = [["PK-a", "S1", "statement", "t", "supported", "", "", "", ""],
                 ["PK-a", "S2", "statement", "t", "unsupported", "", "", "", ""],
                 ["PK-a", "S3", "statement", "t", "not_checkable", "", "", "", ""],
                 ["PK-a", "R", "recommendation", "r", "", "yes", "", "no", ""],
                 ["PK-b", "S1", "statement", "t", "supported", "", "", "", ""],
                 ["PK-b", "R", "recommendation", "r", "", "no", "x", "yes", "y"]]
    bound_key(key, doc, {"PK-a": "C1", "PK-b": "C2"}, done_rows)
    write_sheet(done, done_rows)
    human = scoring.score([("f", doc)], sheet=done, key=key)["human_rubric"]
    # protocol-v1 section 3: supported / all statements the rubric scored (incl. not_checkable)
    assert human["C1"]["rubric_supported_statements"]["text"] == "1/3 (0.333)"
    assert human["C1"]["not_checkable"] == 1 and human["C1"]["human_correction"]["text"] == \
        "0/1 (0.000)"
    assert human["C2"]["human_correction"]["text"] == "1/1 (1.000)"
    assert human["C1"]["review_status"] == human["C2"]["review_status"] == "complete"
    other = copy.deepcopy(json.loads(key.read_text()))
    other["packets"]["PK-a"]["run_artifact_sha256"] = "f" * 64
    key.write_text(json.dumps(other))
    with pytest.raises(scoring.ScoreError, match="not being scored"):
        scoring.score([("f", doc)], sheet=done, key=key)
