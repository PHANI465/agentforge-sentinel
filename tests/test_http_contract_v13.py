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


# ---- OpenAPI: v1.3 is v1.2 plus the document routes ---------------------------------------

V12 = json.loads((HTTP / "openapi.v1.2.json").read_text(encoding="utf-8"))
ACTIVE = json.loads((HTTP / "openapi.v1.3.json").read_text(encoding="utf-8"))
DOC_PATHS = {"/v1/documents", "/v1/documents/{handle_id}", "/v1/documents/{handle_id}/analysis",
             "/v1/documents/{handle_id}/records"}


def test_v1_v11_and_v12_snapshots_are_frozen():
    import hashlib
    for name, digest in (("openapi.v1.json", exporter.LEGACY_V1_SHA256),
                         ("openapi.v1.1.json", exporter.V11_SHA256),
                         ("openapi.v1.2.json", exporter.V12_SHA256)):
        assert hashlib.sha256((HTTP / name).read_bytes()).hexdigest() == digest, name
    assert (V12["info"]["version"], ACTIVE["info"]["version"]) == ("1.2.0", "1.3.0")
    assert exporter.legacy_problems() == []


def test_active_snapshot_matches_code():
    assert (HTTP / "openapi.v1.3.json").read_bytes() == exporter.dumps(exporter.openapi())


def test_v13_is_v12_plus_document_routes_and_one_capability_value():
    assert set(ACTIVE["paths"]) - set(V12["paths"]) == DOC_PATHS
    for path, operations in V12["paths"].items():
        assert ACTIVE["paths"][path] == operations, path
    old, new = V12["components"]["schemas"], ACTIVE["components"]["schemas"]
    for name, schema in old.items():
        if name == "SessionView":
            continue
        assert new[name] == schema, name  # byte-for-byte identical
    old_caps = old["SessionView"]["properties"]["capabilities"]["items"]["enum"]
    new_caps = new["SessionView"]["properties"]["capabilities"]["items"]["enum"]
    assert set(new_caps) - set(old_caps) == {"analyze_document"} and set(old_caps) <= set(new_caps)
    sv_old = dict(old["SessionView"], properties={k: v for k, v in
                                                   old["SessionView"]["properties"].items()
                                                   if k != "capabilities"})
    sv_new = dict(new["SessionView"], properties={k: v for k, v in
                                                   new["SessionView"]["properties"].items()
                                                   if k != "capabilities"})
    assert sv_old == sv_new
    assert ACTIVE["components"]["securitySchemes"] == V12["components"]["securitySchemes"]


def test_document_routes_are_bearer_typed_and_upload_is_raw_bytes():
    upload = ACTIVE["paths"]["/v1/documents"]["post"]
    content = upload["requestBody"]["content"]
    assert "multipart/form-data" not in content
    assert set(content) == {"application/octet-stream", "application/pdf", "text/csv",
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
    assert all(c["schema"] == {"type": "string", "format": "binary"} for c in content.values())
    params = {(p["in"], p["name"]): p for p in upload["parameters"]}
    assert set(params) == {("query", "format")} and params[("query", "format")]["required"]
    for path in DOC_PATHS:
        for method, op in ACTIVE["paths"][path].items():
            assert op["security"] == [{"bearer": []}], (path, method)
            for status in ("401", "403", "404", "503"):
                schema = op["responses"][status]["content"]["application/json"]["schema"]
                assert schema == {"$ref": "#/components/schemas/ErrorResponse"}, (path, status)
    analysis = ACTIVE["paths"]["/v1/documents/{handle_id}/analysis"]["post"]
    assert analysis["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/AnalysisRequest"}


def test_new_components_carry_no_identity_or_secret_fields():
    forbidden = {"scope", "tenant_id", "session_id", "principal_id", "token", "password",
                 "prompt", "api_key", "authorization", "path", "filename", "uri", "url"}
    new = set(ACTIVE["components"]["schemas"]) - set(V12["components"]["schemas"])
    assert {"DocumentAnalysis", "DocumentUpload", "RecordPage", "AnalysisRequest"} <= new
    for name in new:
        properties = set(ACTIVE["components"]["schemas"][name].get("properties", {}))
        assert not properties & forbidden, (name, properties & forbidden)
