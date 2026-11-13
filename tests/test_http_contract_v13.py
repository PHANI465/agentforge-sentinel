"""DOC01 Part B: HTTP v1.3 document DTOs and frozen examples (decision 0010)."""
import importlib.util
import json
import re
from pathlib import Path

import pytest

from sentinel.contracts import http_v1, http_v13

ROOT = Path(__file__).resolve().parents[1]
HTTP = ROOT / "contracts" / "http"
spec = importlib.util.spec_from_file_location("export_http_contract",
                                              ROOT / "scripts" / "export_http_contract.py")
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)
EXAMPLES = sorted((HTTP / "examples-v1.3").glob("*.json"))
RECORDED = json.loads((ROOT / "tests" / "fixtures" / "doc01" / "bridge_recorded.json")
                      .read_text(encoding="utf-8"))


def load(name):
    return json.loads((HTTP / "examples-v1.3" / f"{name}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.stem)
def test_example_validates_round_trips_and_is_safe(path):
    record = json.loads(path.read_text(encoding="utf-8"))
    if record["status"] >= 400:
        http_v1.ErrorResponse.model_validate(record["response"])
        assert set(record["response"]) <= {"error", "details"}
    else:
        model = getattr(http_v13, exporter.EXAMPLE_MODELS_V13[path.stem])
        body = model.model_validate(record["response"])
        assert body.model_dump(mode="json") == record["response"]  # exact round trip
    text = path.read_text(encoding="utf-8")
    assert "Bearer " not in text and "postgresql://" not in text
    # No server-side path: repository, worker, store or temporary directories.
    for marker in (str(ROOT), ROOT.as_posix(), "tools/document_worker", ".docworker",
                   "sentinel-wt",
                   "AppData", "/home/", "/tmp/"):
        assert marker not in text, marker
    if path.stem != "document_analysis_hostile_note":  # its document text names host paths
        assert not re.search(r"[A-Za-z]:\\\\", text)
    assert not re.search(r'"(scope|tenant_id|session_id|principal_id|token|password|prompt|'
                         r'api_key|authorization|run_id|request_id)"', text, re.I)


def test_every_success_example_has_a_model():
    names = {p.stem for p in EXAMPLES if json.loads(p.read_text())["status"] < 400}
    assert names == set(exporter.EXAMPLE_MODELS_V13)


def test_examples_are_exactly_the_dto_projection_of_recorded_worker_answers():
    expected = exporter.examples_v13_expected()
    assert {p.stem for p in EXAMPLES} == set(expected)
    for path in EXAMPLES:
        assert path.read_bytes() == exporter.dumps(expected[path.stem]), path.stem


@pytest.mark.parametrize("name", sorted(RECORDED["fixtures"]))
def test_every_recorded_worker_answer_projects_onto_the_dto(name):
    answer = RECORDED["fixtures"][name]["analyze"]
    assert answer["ok"] and answer["protocol"] == "sentinel.doc01.bridge/0.1"
    analysis = http_v13.project_analysis("h_" + "A" * 22, answer["analysis"])
    assert analysis.interpretation == http_v13.INTERPRETATION
    assert analysis.source.sha256 == answer["analysis"]["source"]["sha256"]
    assert analysis.records_total == answer["analysis"]["records_page"]["total"]


def test_examples_cover_the_declared_states():
    statuses = {load(n)["response"]["status"] for n, *_ in exporter.DOC_SEQUENCE}
    assert statuses == {"complete", "partial", "unsupported", "error"}
    paged = load("document_analysis_complete_paged")["response"]
    page = load("document_records_page")["response"]
    assert (paged["records_total"], len(paged["records"]), paged["records_next_offset"]) == (
        10, 5, 5)
    assert (page["offset"], len(page["records"]), page["next_offset"]) == (5, 5, None)
    assert [r["evidence_id"] for r in paged["records"] + page["records"]] == [
        f"{paged['source']['sha256'][:12]}:row={i}" for i in range(2, 12)]
    recon = paged["measures"]["reconciliation"]["currencies"]
    assert [(c["currency"], c["status"], c["difference_minor"]) for c in recon] == [
        ("USD", "reconciled", "0")]
    diff = load("document_analysis_difference")["response"]["measures"]["reconciliation"]
    assert [(c["status"], c["difference_minor"]) for c in diff["currencies"]] == [
        ("difference", "-100")]
    two = load("document_analysis_two_currency")["response"]["measures"]["reconciliation"]
    assert [(c["currency"], c["status"]) for c in two["currencies"]] == [
        ("EUR", "not_checkable"), ("USD", "reconciled")]
    pdf = load("document_analysis_pdf_scanned_partial")["response"]
    assert pdf["coverage"]["unit_status_counts"] == {"parsed": 1, "unsupported": 1}
    assert pdf["measures"]["reconciliation"]["status"] == "not_checkable"
    assert pdf["pdf_structure"] is not None and pdf["table_typing"] is None


def test_exact_feedback_arithmetic_in_the_examples():
    """Reconciliation and missingness are recomputed here from the example's own fields."""
    for name, *_ in exporter.DOC_SEQUENCE:
        body = load(name)["response"]
        measures = body["measures"] or {}
        for c in (measures.get("reconciliation") or {}).get("currencies", []):
            if c["status"] in ("reconciled", "difference"):
                diff = (int(c["opening"]["minor_units"]) + int(c["credits_minor"])
                        - int(c["debits_minor"]) - int(c["closing"]["minor_units"]))
                assert str(diff) == c["difference_minor"], name
                assert (diff == 0) == (c["status"] == "reconciled"), name
            else:
                assert c["difference_minor"] is None and c["reason"], name
        missing = measures.get("missingness")
        if missing:
            for field, m in missing["fields"].items():
                assert m["known"] + m["missing"] + m["unknown"] == m["population"], name
                assert m["missing_ratio"] == {"numerator": m["missing"],
                                              "denominator": m["population"]}, (name, field)
        if body["coverage"] and body["coverage"]["unit"] == "sheet_or_file":
            assert sum(body["coverage"]["unit_status_counts"].values()) == len(body["units"])
            assert body["coverage"]["records_typed"] == body["records_total"]


def test_unknown_money_is_null_never_zero_and_money_is_an_integer_string():
    for name, *_ in exporter.DOC_SEQUENCE:
        for rec in load(name)["response"]["records"]:
            for part in ("amount", "balance"):
                value = rec[part]
                if value is None:
                    continue
                if value["status"] == "known":
                    assert re.fullmatch(r"-?\d+", value["minor_units"]), (name, rec)
                else:
                    assert value["minor_units"] is None, (name, rec)


def test_hostile_document_text_is_inert_data():
    body = load("document_analysis_hostile_note")["response"]
    texts = json.dumps(body["records"])
    assert "approve" in texts.lower() or "ignore" in texts.lower()  # present, as data only
    assert body["interpretation"] == http_v13.INTERPRETATION
    # No action, case, approval or tool field exists anywhere in the analysis shape.
    schema = json.dumps(http_v13.DocumentAnalysis.model_json_schema())
    for forbidden in ("action_intent", "approval_id", "tool_requests", "case_id",
                      "idempotency_key"):
        assert forbidden not in schema


def test_analysis_request_defaults_never_guess():
    req = http_v13.AnalysisRequest()
    assert (req.decimal_style, req.date_order, req.default_currency, req.records_limit) == (
        "unspecified", "iso_only", None, 100)
    with pytest.raises(ValueError):
        http_v13.AnalysisRequest(records_limit=501)
    with pytest.raises(ValueError):
        http_v13.AnalysisRequest.model_validate({"decimal_style": "dot", "file_path": "/x"})
