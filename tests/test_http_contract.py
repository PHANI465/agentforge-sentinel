"""C01: the frozen HTTP v1 contract (OpenAPI snapshot + deterministic examples) matches the
running code, and every example validates against its typed response model."""
import importlib.util
import json
import re
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from sentinel.contracts import http_v1
from sentinel.contracts.v1 import Approval, AuditEvent

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("export_http_contract",
                                              ROOT / "scripts" / "export_http_contract.py")
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)
EXAMPLES = sorted((ROOT / "contracts" / "http" / "examples").glob("*.json"))
MODELS = {"Approval": TypeAdapter(Approval), "AuditEventList": TypeAdapter(list[AuditEvent])}


def adapter(name):
    return MODELS.get(name) or TypeAdapter(getattr(http_v1, name))


def test_openapi_snapshot_is_current():
    # Since C07 the live schema is the active v1.1 revision; openapi.v1.json is the frozen
    # legacy snapshot, checked by hash and for v1.1 compatibility in test_http_contract_v11.
    committed = (ROOT / "contracts" / "http" / "openapi.v1.1.json").read_bytes()
    assert committed == exporter.dumps(exporter.openapi()), (
        "run: uv run --locked python scripts/export_http_contract.py")


def test_openapi_declares_typed_responses_and_request_bodies():
    doc = exporter.openapi()
    paths = doc["paths"]
    ok = paths["/v1/cases"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert ok == {"$ref": "#/components/schemas/CasePage"}
    body = paths["/v1/actions"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    assert body == {"$ref": "#/components/schemas/ExecuteActionInput"}
    error = paths["/v1/cases"]["get"]["responses"]["422"]["content"]["application/json"]
    assert error["schema"] == {"$ref": "#/components/schemas/ErrorResponse"}
    assert paths["/v1/session"]["get"]["security"] == [{"bearer": []}]


def test_examples_reproduce_byte_for_byte(database_url):
    expected = exporter.expected_files(database_url)
    stale = exporter.compare_or_write(expected, check=True)
    assert stale == [], "run: uv run --locked python scripts/export_http_contract.py"


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.stem)
def test_example_validates_against_its_model(path):
    record = json.loads(path.read_text(encoding="utf-8"))
    if record["status"] >= 400:
        http_v1.ErrorResponse.model_validate(record["response"])
        assert set(record["response"]) <= {"error", "details"}
    else:
        adapter(exporter.EXAMPLE_MODELS[path.stem]).validate_python(record["response"])
    # The recorded request may carry a deliberately injected field; the response never echoes it.
    text = json.dumps(record["response"])
    assert "never-echoed" not in text and "api_key" not in text
    assert "Bearer " not in path.read_text(encoding="utf-8")  # no auth header is recorded
    assert not re.search(r'"(authorization|token|bearer_token|api_key|password|email)"', text, re.I)


def test_every_success_example_has_a_model():
    names = {p.stem for p in EXAMPLES if json.loads(p.read_text())["status"] < 400}
    assert names == set(exporter.EXAMPLE_MODELS)
