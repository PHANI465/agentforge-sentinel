"""Regressions for Codex review 0a6fb0e: R9 (cursor structure/member types) and R10 (the error
contract covers handled errors only; unexpected failures need client fallback)."""
import base64
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sentinel.api import create_app
from test_api_contracts import open_cases
from test_thin_path import ANALYST, Harness

ROOT = Path(__file__).resolve().parents[1]
TS = "2026-10-23T17:00:00+00:00"
UUID = "5e000000-0000-4000-8000-000000000001"


def b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def cursor(value) -> str:
    return b64(json.dumps(value).encode())


@pytest.fixture
def h(database_url, clock):
    return Harness(database_url, clock)


# ---- R9 ----------------------------------------------------------------------------------

MALFORMED = {
    # UUID member of the wrong JSON type (AttributeError -> 500 before the fix)
    "uuid_int": cursor([TS, 123]), "uuid_true": cursor([TS, True]),
    "uuid_object": cursor([TS, {"a": 1}]), "uuid_array": cursor([TS, [UUID]]),
    "uuid_null": cursor([TS, None]), "uuid_float": cursor([TS, 1.5]),
    # timestamp member of the wrong type
    "time_int": cursor([1700000000, UUID]), "time_null": cursor([None, UUID]),
    "time_array": cursor([[TS], UUID]), "time_object": cursor([{"t": TS}, UUID]),
    # root shape and length
    "root_object": cursor({"created": TS, "id": UUID}), "root_two_key_object": cursor({TS: 1,
                                                                                        UUID: 2}),
    "root_string": cursor(TS), "root_number": cursor(7), "root_null": cursor(None),
    "root_true": cursor(True), "empty_list": cursor([]), "one_member": cursor([TS]),
    "three_members": cursor([TS, UUID, "x"]),
    # invalid strings and encodings
    "bad_uuid": cursor([TS, "not-a-uuid"]), "naive_time": cursor(["2026-10-23T17:00:00", UUID]),
    "bad_time": cursor(["yesterday", UUID]), "not_json": b64(b"[not json"),
    "not_utf8": b64(b"\xff\xfe\xfd"), "not_base64": "!!!!", "non_ascii": "été",
}


@pytest.mark.parametrize("name", sorted(MALFORMED))
def test_r9_malformed_cursor_is_a_safe_422(h, name):
    token = h.service.create_session(ANALYST)[0]
    response = h.client.get("/v1/cases", params={"cursor": MALFORMED[name]},
                            headers={"Authorization": f"Bearer {token}"})
    assert (response.status_code, response.json()) == (422, {"error": "invalid_cursor"}), name


def test_r9_valid_cursor_still_paginates(h, clock):
    token = h.service.create_session(ANALYST)[0]
    ids = open_cases(h, token, clock, 3)
    page1 = h.call("GET", "/v1/cases?limit=2", token).json()
    page2 = h.call("GET", f"/v1/cases?limit=2&cursor={page1['next_cursor']}", token).json()
    assert [i["id"] for i in page1["items"] + page2["items"]] == sorted(ids, reverse=True)
    assert page2["next_cursor"] is None
    # A hand-built well-formed cursor is accepted (it carries position, not authority).
    built = h.call("GET", f"/v1/cases?cursor={cursor([TS, UUID])}", token)
    assert built.status_code == 200


# ---- R10 ---------------------------------------------------------------------------------

def test_r10_unexpected_failure_is_a_500_without_echo(h, monkeypatch):
    """Unhandled failures are not ErrorResponse JSON; the body must not echo internals."""
    token = h.service.create_session(ANALYST)[0]
    canary = "SYNTHETIC-STORAGE-FAILURE-7731"

    def broken(*_args, **_kwargs):
        raise RuntimeError(canary)

    monkeypatch.setattr(h.service, "list_cases", broken)
    client = TestClient(create_app(h.service), raise_server_exceptions=False)
    response = client.get("/v1/cases", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 500
    assert canary not in response.text
    assert not response.headers.get("content-type", "").startswith("application/json")


def test_r10_contract_promises_json_only_for_handled_errors():
    schema = json.loads((ROOT / "contracts" / "http" / "openapi.v1.json").read_text())
    description = schema["components"]["schemas"]["ErrorResponse"]["description"]
    assert "Every non-2xx" not in description
    assert "handled" in description and "non-JSON" in description
    readme = (ROOT / "docs" / "api" / "README.md").read_text(encoding="utf-8")
    assert "Every non-2xx body is" not in readme
    for required in ("non-JSON", "network failure", "same `idempotency_key`"):
        assert required in readme, required
