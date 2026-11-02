"""G3C-A contract candidate: explicit HTTP v1.2 revision with the investigation trace; the v1
and v1.1 snapshots are frozen and v1.2 is a strict superset of v1.1."""
import hashlib
import importlib.util
import json
import re
from pathlib import Path

import pytest

from sentinel.contracts import http_v1, http_v12

ROOT = Path(__file__).resolve().parents[1]
HTTP = ROOT / "contracts" / "http"
spec = importlib.util.spec_from_file_location("export_http_contract",
                                              ROOT / "scripts" / "export_http_contract.py")
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)
V11 = json.loads((HTTP / "openapi.v1.1.json").read_text(encoding="utf-8"))
ACTIVE = json.loads((HTTP / "openapi.v1.2.json").read_text(encoding="utf-8"))
EXAMPLES = sorted((HTTP / "examples-v1.2").glob("*.json"))
TRACE = "/v1/cases/{case_id}/investigation-trace"


def test_v1_and_v11_snapshots_are_frozen():
    for name, digest in (("openapi.v1.json", exporter.LEGACY_V1_SHA256),
                         ("openapi.v1.1.json", exporter.V11_SHA256)):
        assert hashlib.sha256((HTTP / name).read_bytes()).hexdigest() == digest, name
    assert (V11["info"]["version"], ACTIVE["info"]["version"]) == ("1.1.0", "1.2.0")
    assert exporter.legacy_problems() == []


def test_active_snapshot_matches_code():
    assert (HTTP / "openapi.v1.2.json").read_bytes() == exporter.dumps(exporter.openapi())


def test_v12_is_v11_plus_one_read_route():
    assert set(ACTIVE["paths"]) - set(V11["paths"]) == {TRACE}
    for path, operations in V11["paths"].items():
        assert ACTIVE["paths"][path] == operations, path
    old, new = V11["components"]["schemas"], ACTIVE["components"]["schemas"]
    for name, schema in old.items():
        assert new[name] == schema, name  # byte-for-byte identical, not only widened
    assert ACTIVE["components"]["securitySchemes"] == V11["components"]["securitySchemes"]
    assert {k: v for k, v in ACTIVE.items() if k not in ("info", "paths", "components")} == {
        k: v for k, v in V11.items() if k not in ("info", "paths", "components")}


def test_trace_route_is_a_typed_bearer_get_with_one_optional_selector():
    (method,) = ACTIVE["paths"][TRACE]
    operation = ACTIVE["paths"][TRACE]["get"]
    assert method == "get" and "requestBody" not in operation
    assert operation["security"] == [{"bearer": []}]
    ok = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert ok == {"$ref": "#/components/schemas/InvestigationTrace"}
    for status in ("401", "403", "404", "422"):
        error = operation["responses"][status]["content"]["application/json"]["schema"]
        assert error == {"$ref": "#/components/schemas/ErrorResponse"}
    params = {(p["in"], p["name"]): p for p in operation["parameters"]}
    assert set(params) == {("path", "case_id"), ("query", "workflow_id")}
    assert params[("query", "workflow_id")]["required"] is False


def test_trace_components_carry_no_identity_or_secret_fields():
    forbidden = {"scope", "tenant_id", "session_id", "principal_id", "token", "password",
                 "prompt", "raw", "exception", "api_key", "authorization"}
    new = set(ACTIVE["components"]["schemas"]) - set(V11["components"]["schemas"])
    for name in new:
        properties = set(ACTIVE["components"]["schemas"][name].get("properties", {}))
        assert not properties & forbidden, (name, properties & forbidden)


# ---- examples -----------------------------------------------------------------------------

def load(name):
    return json.loads((HTTP / "examples-v1.2" / f"{name}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.stem)
def test_example_validates_and_is_safe(path):
    record = json.loads(path.read_text(encoding="utf-8"))
    if record["status"] >= 400:
        http_v1.ErrorResponse.model_validate(record["response"])
        assert set(record["response"]) == {"error"}
    else:
        assert exporter.EXAMPLE_MODELS_V12[path.stem] == "InvestigationTrace"
        body = http_v12.InvestigationTrace.model_validate(record["response"])
        assert body.model_dump(mode="json") == record["response"]  # exact round trip
    text = path.read_text(encoding="utf-8")
    assert "Bearer " not in text and "postgresql://" not in text
    assert not re.search(r'"(scope|tenant_id|session_id|principal_id|token|password|prompt|'
                         r'api_key|authorization)"', text, re.I)


def test_every_success_example_has_a_model():
    names = {p.stem for p in EXAMPLES if json.loads(p.read_text())["status"] < 400}
    assert names == set(exporter.EXAMPLE_MODELS_V12)


def test_examples_cover_the_declared_states():
    def workflow(name):
        return load(name)["response"]["selected"]["workflow"]
    assert load("trace_no_workflow")["response"]["selected"] is None
    legacy = load("trace_legacy_investigator")["response"]
    assert (legacy["selected"], legacy["legacy_investigator_runs"]) == (None, 1)
    assert workflow("trace_completed_recommend")["disposition"]["kind"] == "recommend"
    assert workflow("trace_abstain_after_challenge")["disposition"]["kind"] == "abstain"
    assert workflow("trace_zero_roles")["recorded_role_invocations"] == 0
    for name, status in (("trace_running_between_roles", "before_deadline"),
                         ("trace_running_recovery_due", "recovery_due")):
        assert (workflow(name)["status"], workflow(name)["deadline_status"],
                workflow(name)["recorded_role_invocations"]) == ("running", status, None)
    assert workflow("trace_recovered")["terminal_by"] == "recovery"
    latest, prior = load("trace_retry_latest")["response"], load("trace_retry_prior")["response"]
    assert latest["workflow_count"] == prior["workflow_count"] == 2
    assert latest["selected"]["workflow"]["id"] == latest["workflows"][0]["id"]
    assert prior["selected"]["workflow"]["id"] == latest["workflows"][1]["id"]
    repeat = load("trace_repeat_after_provider_failure")["response"]["selected"]["attempts"]
    assert [(a["attempt"], a["status"], a["usage"]) for a in repeat
            if a["role"] == "investigator"][0] == (1, "failed", None)
    note = load("trace_untrusted_note")["response"]["selected"]["attempts"][0]["output"]
    assert note["note"] == exporter.UNTRUSTED_NOTE
    recommend = load("trace_completed_recommend")["response"]["selected"]["tool_results"]
    assert [t["status"] for t in recommend][-3:] == ["ok", "unavailable", "denied"]
