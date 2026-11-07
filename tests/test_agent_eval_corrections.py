"""G3D-P4a review corrections R46, R47 and R49 (docs/reviews/G3D-P4a-96293da.md).

R46: an internally contradictory version-1 run record (a wrong hold relabelled `refused`
with matching counts, or a `complete` record whose suffix moved to not-attempted) is
refused; legitimate incomplete, unknown and telemetry-unavailable records stay accepted
and nothing is inferred. R47: review sheets are validated (choices, unique items, binding
to the generated packet material); blank is unknown, never "no"; the rubric-supported
denominator is every statement the rubric scored (not_checkable included, protocol-v1 §3).
R49: the exported adopted recommendation must agree with the stored single-investigator
or workflow disposition; a disagreement is refused before any packet is built.

This is consistency validation of unsigned, editable files, not a tamper-proof claim.
The run fixture is hand-made test data, never live evidence. Real-database tests use the
deterministic runner on test-owned disposable PostgreSQL only.
"""
import copy
import csv
import io
import json
import sys
from pathlib import Path

import psycopg
import pytest
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests" / "support"))

import agent_eval_score as scoring  # noqa: E402
from agent_eval_support import artifact  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "agent_eval_p4a" / "run-fixture.json"


def fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def refused(doc, match):
    with pytest.raises(artifact.ArtifactError, match=match):
        artifact.validate_run(doc)
    with pytest.raises(scoring.ScoreError, match=match):
        scoring.score([("altered", doc)])


# ---- R46: contradictory records are refused ------------------------------------------------

def test_r46_wrong_hold_relabelled_refused_with_consistent_counts_is_refused():
    doc = fixture()
    c1 = doc["comparators"]["C1"]
    c1["attempts"][2]["outcome"] = "refused"  # the D03 hold; its disposition left intact
    c1["counts"]["dispositions"] -= 1
    c1["counts"]["refused"] = 1
    refused(doc, "refused")


def test_r46_complete_record_with_a_censored_suffix_is_refused():
    doc = fixture()
    c1 = doc["comparators"]["C1"]
    c1["attempts"] = c1["attempts"][:2]  # the D03 wrong hold hidden in the "not attempted"
    c1["cases_not_attempted"] = ["D03", "D04", "D11"]
    c1["counts"] = {"attempts": 2, "dispositions": 2}
    c1["request_latency_s"] = [1.0, 2.0]
    refused(doc, "complete")
    doc["record"]["status"] = "incomplete"  # and no stop explains the missing suffix
    refused(doc, "stopped")


@pytest.mark.parametrize("mutate, match", [
    (lambda d: d["record"].update(status="done"), "status"),
    (lambda d: d["comparators"]["C2"]["attempts"][4].pop("code"), "refused"),
    (lambda d: d["comparators"]["C1"]["attempts"][4].update(
        disposition={"operation": "simulated_hold"}), "error"),
    (lambda d: d["comparators"]["C1"]["attempts"][3].update(
        disposition={"operation": "simulated_hold", "reason_code": "x"}), "inconclusive"),
    (lambda d: d["comparators"]["C1"]["attempts"][3].update(case_state="awaiting_approval"),
     "inconclusive"),
    (lambda d: d["comparators"]["C1"]["attempts"][0].update(case_state="open"),
     "disposition"),
    (lambda d: d["comparators"]["C1"]["attempts"][0].update(code="agent_capacity_exhausted"),
     "disposition"),
    (lambda d: d["comparators"]["C1"]["attempts"][0].update(
        disposition=None, telemetry={"status": "read"}), "disposition"),
    (lambda d: d["comparators"]["C1"]["attempts"][0]["disposition"].update(kind="abstain"),
     "kind"),
    (lambda d: d["comparators"]["C2"]["attempts"][0]["disposition"].update(kind=None),
     "kind"),
    (lambda d: d["comparators"]["C2"]["attempts"][4].update(recorded_role_attempts=2),
     "refused"),
    (lambda d: d["comparators"]["C2"]["attempts"][4].update(
        code="investigation_outcome_unknown"), "refused"),
    (lambda d: d["comparators"]["C1"]["attempts"][4].update(code="agent_capacity_exhausted"),
     "error"),
    (lambda d: d["record"].update(planned_comparators=["C2", "C1"]), "order"),
])
def test_r46_other_contradictions_are_refused(mutate, match):
    doc = fixture()
    mutate(doc)
    refused(doc, match)


def stopped_at_c2_d04(doc):
    doc["record"].update(status="incomplete", stopped={
        "comparator": "C2", "case": "D04", "phase": "ingest", "code": "OperationalError"})
    c2 = doc["comparators"]["C2"]
    c2["attempts"] = c2["attempts"][:3]
    c2["cases_not_attempted"] = ["D04", "D11"]
    c2["counts"] = {"attempts": 3, "dispositions": 3}
    c2["request_latency_s"] = c2["request_latency_s"][:3]
    return doc


def test_r46_stop_accounting_must_match_both_sides_of_the_boundary():
    good = stopped_at_c2_d04(fixture())
    artifact.validate_run(good)  # a legitimate setup stop: earlier results kept
    wrong_case = copy.deepcopy(good)
    wrong_case["record"]["stopped"]["case"] = "D11"
    refused(wrong_case, "stopped")
    other = copy.deepcopy(good)  # not-attempted cases on a comparator that did not stop
    c1 = other["comparators"]["C1"]
    c1["attempts"] = c1["attempts"][:4]
    c1["cases_not_attempted"] = ["D11"]
    c1["counts"] = {"attempts": 4, "dispositions": 3, "inconclusive": 1}
    c1["request_latency_s"] = c1["request_latency_s"][:4]
    refused(other, "not attempted")
    phase = fixture()  # the comparator itself could not be built: nothing of it ran
    del phase["comparators"]["C2"]
    phase["record"].update(status="incomplete", comparators_not_started=["C2"], stopped={
        "comparator": "C2", "case": None, "phase": "comparator", "code": "Refused"})
    artifact.validate_run(phase)
    mismatch = copy.deepcopy(phase)
    mismatch["record"]["stopped"]["comparator"] = "C1"
    refused(mismatch, "stopped")


def test_r46_unknown_and_unavailable_telemetry_stay_unknown_without_inference():
    doc = fixture()
    hold = doc["comparators"]["C1"]["attempts"][2]  # D03: the wrong hold's telemetry failed
    hold.pop("disposition")
    hold["telemetry"] = {"status": "unavailable", "error": "OperationalError"}
    c1 = scoring.score([("unavailable", doc)])["comparators"]["C1"]
    assert c1["counts"]["dispositions"] == 3  # the first outcome is kept as recorded
    assert c1["acceptable_recommendation"]["text"] == "2/2 (1.000)"
    assert c1["recommendation_unknown"] == {"count": 1, "attempts": ["C1:3:D03"]}
    assert c1["wrong_holds"]["count"] == 0 and c1["wrong_holds"]["unknown"] == 1
    pending = fixture()  # an unknown commit outcome whose stored state shows a hold
    row = pending["comparators"]["C1"]["attempts"][2]
    row.update(outcome="pending", code="investigation_outcome_unknown")
    pending["comparators"]["C1"]["counts"] = {"attempts": 5, "dispositions": 2,
                                              "pending": 1, "inconclusive": 1, "error": 1}
    c1 = scoring.score([("pending", pending)])["comparators"]["C1"]
    assert c1["counts"]["pending"] == 1 and c1["acceptable_recommendation"]["text"] == \
        "2/2 (1.000)"
    assert c1["wrong_holds"]["count"] == 0  # not inferred to be a completed disposition
    assert c1["wrong_holds"]["pending_with_stored_hold"] == ["C1:3:D03"]


# ---- R47: review sheets ---------------------------------------------------------------------

def report():
    from test_agent_eval_reporting import report as load_report
    return load_report()


def generated(tmp_path, statements=("first statement", "second statement")):
    """A real generated packet/key/sheet for one C1 attempt of the fixture."""
    module = report()
    doc = fixture()
    export = {"attempt_id": "C1:1:D01", "comparator": "C1", "case": "D01",
              "outcome": "disposition", "transaction": {"amount": {"minor_units": 1}},
              "evidence": [{"name": "transaction_count_1h", "value": 7, "source": "s"}],
              "tool_results": [], "role_outputs": [{"output": {"note": t}}
                                                   for t in statements[1:]],
              "adopted": {"agent_run_id": "r1", "verification": "matches stored disposition",
                          "source": "single_investigator_finding", "kind": None,
                          "operation": "simulated_hold", "reason_code": "velocity_pattern",
                          "finding": {"rationale": statements[0]}}}
    packets, key = module.review_packets(
        [{"run_artifact_sha256": artifact.digest(doc), "run": doc, "exports": [export]}],
        seed=3)
    key_path = tmp_path / "key.json"
    key_path.write_text(json.dumps(key), encoding="utf-8")
    rows = list(csv.reader(io.StringIO(module.sheet_csv(packets))))
    return doc, key_path, rows


def answer(rows, item, **values):
    columns = list(rows[0])
    for row in rows[1:]:
        if row[1] == item:
            for name, value in values.items():
                row[columns.index(name)] = value
    return rows


def human(tmp_path, doc, key_path, rows, name="sheet.csv"):
    sheet = tmp_path / name
    with open(sheet, "w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows(rows)
    return scoring.score([("f", doc)], sheet=sheet, key=key_path)["human_rubric"]


def test_r47_blank_recommendation_fields_are_unknown_not_no(tmp_path):
    doc, key, rows = generated(tmp_path)
    answer(rows, "S1", supported="supported")
    answer(rows, "S2", supported="supported")
    c1 = human(tmp_path, doc, key, rows)["C1"]
    assert c1["rubric_supported_statements"]["text"] == "2/2 (1.000)"
    assert c1["human_acceptable"]["text"] == "n/a (0/0)"  # nobody answered: not 0/1
    assert c1["human_correction"]["text"] == "n/a (0/0)"
    assert (c1["acceptable_answered"], c1["acceptable_unanswered"]) == (0, 1)
    assert (c1["correction_answered"], c1["correction_unanswered"]) == (0, 1)
    assert c1["review_status"].startswith("partial")


def test_r47_a_correction_only_answer_is_counted_and_the_rest_stays_unknown(tmp_path):
    doc, key, rows = generated(tmp_path)
    answer(rows, "R", would_correct="yes", correction="change to escalate")
    c1 = human(tmp_path, doc, key, rows)["C1"]
    assert c1["human_correction"]["text"] == "1/1 (1.000)"
    assert c1["human_acceptable"]["text"] == "n/a (0/0)"
    assert c1["statements_unanswered"] == 2
    assert c1["rubric_supported_statements"]["text"] == "n/a (0/0)"
    assert c1["packets_scored"] == 1 and c1["review_status"].startswith("partial")


def test_r47_supported_plus_not_checkable_uses_the_protocol_denominator(tmp_path):
    doc, key, rows = generated(tmp_path)
    answer(rows, "S1", supported="supported")
    answer(rows, "S2", supported="not_checkable")
    answer(rows, "R", acceptable="yes", reason_code="velocity_pattern", would_correct="no")
    c1 = human(tmp_path, doc, key, rows)["C1"]
    assert c1["rubric_supported_statements"]["text"] == "1/2 (0.500)"  # protocol-v1 §3
    assert c1["not_checkable"] == 1 and c1["review_status"] == "complete"
    assert c1["human_acceptable"]["text"] == "1/1 (1.000)"
    assert c1["human_correction"]["text"] == "0/1 (0.000)"


@pytest.mark.parametrize("change, match", [
    (lambda rows: answer(rows, "S1", supported="banana"), "supported"),
    (lambda rows: answer(rows, "R", acceptable="maybe"), "acceptable"),
    (lambda rows: answer(rows, "R", would_correct="perhaps"), "would_correct"),
    (lambda rows: answer(rows, "S1", acceptable="yes"), "does not apply"),
    (lambda rows: answer(rows, "R", supported="supported"), "does not apply"),
    (lambda rows: answer(rows, "R", correction="edit without saying so"), "would_correct"),
    (lambda rows: rows + [list(rows[2])], "duplicate"),
    (lambda rows: rows + [[r if i != 1 else "S9" for i, r in enumerate(rows[2])]],
     "not in the generated packet"),
    (lambda rows: [r for r in rows if r[1] != "S2"], "missing"),
    (lambda rows: [r if r[1] != "S1" else r[:3] + ["a different text"] + r[4:]
                   for r in rows], "text"),
    (lambda rows: [r if r[1] != "S1" else r[:2] + ["recommendation"] + r[3:]
                   for r in rows], "kind"),
    (lambda rows: [rows[0][:-1]] + rows[1:], "columns"),
])
def test_r47_invalid_duplicate_or_unbound_sheets_are_refused(tmp_path, change, match):
    doc, key, rows = generated(tmp_path)
    answer(rows, "S1", supported="supported")
    with pytest.raises(scoring.ScoreError, match=match):
        human(tmp_path, doc, key, change(rows))


def test_r47_blank_templates_stay_unscored_and_text_stays_inert(tmp_path):
    hostile = ('=HYPERLINK("http://example.invalid","x")', "+1+1 <script>x</script>")
    doc, key, rows = generated(tmp_path, statements=hostile)
    texts = {r[3] for r in rows[1:]}
    assert all("'" + t in texts for t in hostile)  # escaped in the CSV, as generated
    c1 = human(tmp_path, doc, key, rows)["C1"]
    assert c1["packets_scored"] == 0 and c1["packets_not_scored"] == 1
    assert c1["review_status"].startswith("not scored")
    assert c1["rubric_supported_statements"]["text"] == "n/a (0/0)"
    assert c1["human_acceptable"]["text"] == "n/a (0/0)"


def test_r47_a_key_without_sheet_binding_is_refused(tmp_path):
    doc, key, rows = generated(tmp_path)
    old = json.loads(key.read_text(encoding="utf-8"))
    for entry in old["packets"].values():
        entry.pop("items", None)
    key.write_text(json.dumps(old), encoding="utf-8")
    answer(rows, "S1", supported="supported")
    with pytest.raises(scoring.ScoreError, match="binding"):
        human(tmp_path, doc, key, rows)


# ---- R49: export agrees with the stored disposition (real deterministic database) ---------

def real_run(database_url, cases):
    from test_agent_eval_reporting import real_run as run
    return run(database_url, cases)


def first(doc, name):
    return doc["comparators"][name]["attempts"][0]


def test_r49_a_stored_escalate_exported_as_hold_is_refused_before_any_packet(database_url):
    module = report()
    doc, runtime = real_run(database_url, "D11")
    assert module.export_run(runtime, doc)["exports"][0]["adopted"]["operation"] == "escalate"
    altered = copy.deepcopy(doc)
    first(altered, "C0")["disposition"]["operation"] = "simulated_hold"
    with pytest.raises(module.ExportError, match="stored"):
        module.export_run(runtime, altered)
    first(altered, "C0")["disposition"]["operation"] = "hold"  # the review probe's value
    with pytest.raises(module.ExportError, match="stored"):
        module.export_run(runtime, altered)


def test_r49_every_recommendation_and_claim_field_must_match_storage(database_url):
    module = report()
    doc, runtime = real_run(database_url, "D01,D11")
    bundle = module.export_run(runtime, doc)
    c2 = [e for e in bundle["exports"] if e["comparator"] == "C2-det"]
    other_basis = first(doc, "C2-det")["disposition"]["basis_run_id"]
    reviewer = next(r["id"] for r in c2[0]["runs"] if r["role"] == "reviewer")
    mutations = {
        "C0 reason": ("C0", lambda d: d.update(reason_code="unusual_amount")),
        "C0 foreign basis": ("C0", lambda d: d.update(basis_run_id=other_basis)),
        "C2 kind": ("C2-det", lambda d: d.update(
            kind="abstain" if d["kind"] == "recommend" else "recommend")),
        "C2 operation": ("C2-det", lambda d: d.update(  # always a real change
            operation="escalate" if d["operation"] == "simulated_hold" else "simulated_hold")),
        "C2 supported": ("C2-det", lambda d: d.update(supported_claims=d["supported_claims"]
                                                       + 1)),
        "C2 unsupported": ("C2-det", lambda d: d.update(unsupported_claims=1)),
        "C2 basis not adopted": ("C2-det", lambda d: d.update(basis_run_id=reviewer)),
        "C2 workflow": ("C2-det", lambda d: d.update(workflow_id=str(
            doc["comparators"]["C2-det"]["attempts"][1]["workflow_ids"][0]))),
    }
    for label, (name, change) in mutations.items():
        altered = copy.deepcopy(doc)
        change(first(altered, name)["disposition"])
        with pytest.raises(module.ExportError, match="stored"):
            module.export_run(runtime, altered)
            pytest.fail(label)
    inconclusive = copy.deepcopy(doc)  # the artifact says no disposition; storage has one
    row = first(inconclusive, "C0")
    row.update(outcome="inconclusive", case_state="open", failure_codes=[], disposition=None)
    inconclusive["comparators"]["C0"]["counts"] = {"attempts": 2, "dispositions": 1,
                                                   "inconclusive": 1}
    inconclusive["comparators"]["C0"]["inconclusive_by_code"] = {"none": 1}
    with pytest.raises(module.ExportError, match="stored"):
        module.export_run(runtime, inconclusive)
    for export in bundle["exports"]:
        assert export["adopted"]["verification"] == "matches stored disposition"
    assert all(e["adopted"]["kind"] in ("recommend", "abstain") for e in c2)


def test_r49_unavailable_telemetry_exports_the_stored_disposition_labelled(database_url):
    module = report()
    doc, runtime = real_run(database_url, "D01")
    stored = first(doc, "C2-det")["disposition"]
    altered = copy.deepcopy(doc)
    row = first(altered, "C2-det")
    row.pop("disposition")
    row["telemetry"] = {"status": "unavailable", "error": "OperationalError"}
    artifact.validate_run(altered)
    export = next(e for e in module.export_run(runtime, altered)["exports"]
                  if e["comparator"] == "C2-det")
    adopted = export["adopted"]
    assert adopted["verification"].startswith("stored only")
    assert (adopted["agent_run_id"], adopted["operation"], adopted["kind"]) == (
        stored["basis_run_id"], stored["operation"], stored["kind"])
    assert export["outcome"] == "disposition"  # the recorded outcome is not rewritten
    c2 = scoring.score([("x", altered)])["comparators"]["C2-det"]
    assert c2["recommendation_unknown"]["count"] == 1  # the run artifact itself stays unknown


def test_r49_a_revision_basis_is_checked_against_the_stored_workflow(database_url, clock):
    import agent_cases as ac
    from test_agent_eval_reporting import evaluator
    from test_trace_api import wrong_count
    module = report()
    url = ac.runtime_url(database_url)
    revise = ac.FaultyRole("investigator", behaviours=[("map", wrong_count)] * 2)
    svc = ac.service(url, ac.workflow(investigator=revise), clock, ac.Monotonic())
    ctx = svc.authenticate(ac.session(url, clock))
    case = ac.seed(svc, ctx, "D05", clock)["case"]["id"]
    svc.investigate(ctx, case, 1)
    stored = evaluator().stored_measurements(url, case, ctx.scope)
    row = {"attempt_id": "C2-det:1:D05", "case": "D05", "outcome": "disposition",
           "ids": {"tenant_id": str(ctx.scope.tenant_id),
                   "session_id": str(ctx.scope.session_id), "case_id": str(case)},
           "workflow_ids": stored["workflow_ids"], "disposition": stored["disposition"]}
    assert stored["disposition"]["kind"] == "abstain"

    def export(candidate):
        with psycopg.connect(url, row_factory=dict_row) as conn, conn.transaction():
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            return module.export_attempt(conn, candidate)
    good = export(row)
    assert good["adopted"]["agent_run_id"] == stored["disposition"]["basis_run_id"]
    assert good["adopted"]["kind"] == "abstain"
    investigators = [r["id"] for r in good["runs"] if r["role"] == "investigator"]
    assert len(investigators) == 2 and investigators[1] == good["adopted"]["agent_run_id"]
    first_try = copy.deepcopy(row)  # the superseded first investigator is not the basis
    first_try["disposition"]["basis_run_id"] = investigators[0]
    with pytest.raises(module.ExportError, match="stored"):
        export(first_try)
    recommend = copy.deepcopy(row)
    recommend["disposition"]["kind"] = "recommend"
    with pytest.raises(module.ExportError, match="stored"):
        export(recommend)


def test_r49_the_export_refuses_the_owner_identity(database_url):
    module = report()
    doc, _runtime = real_run(database_url, "D01")
    with pytest.raises(module.ExportError, match="runtime"):
        module.export_run(database_url, doc)


def test_r49_packets_refuse_a_bundle_whose_adopted_record_disagrees_with_its_run():
    module = report()
    doc = fixture()
    row = first(doc, "C1")
    export = {"attempt_id": row["attempt_id"], "comparator": "C1", "case": "D01",
              "outcome": "disposition", "transaction": {}, "evidence": [],
              "tool_results": [], "role_outputs": [],
              "adopted": {"agent_run_id": "r1", "verification": "matches stored disposition",
                          "finding": {"rationale": "r"}, "kind": None,
                          "operation": "escalate", "reason_code": "velocity_pattern",
                          "source": "single_investigator_finding"}}
    bundle = {"run_artifact_sha256": artifact.digest(doc), "run": doc, "exports": [export]}
    with pytest.raises(module.ExportError, match="disagrees"):
        module.review_packets([bundle], seed=1)  # the run says simulated_hold
    export["adopted"]["operation"] = "simulated_hold"
    packets, _key = module.review_packets([bundle], seed=1)
    assert packets["packets"][0]["recommendation"]["operation"] == "simulated_hold"
    bundle["run_artifact_sha256"] = "0" * 64
    with pytest.raises(module.ExportError, match="digest"):
        module.review_packets([bundle], seed=1)
