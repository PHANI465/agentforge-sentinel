"""Export the HTTP contract (active v1.1) and verify the frozen legacy v1 contract.

- contracts/http/openapi.v1.json is the FROZEN legacy v1 snapshot: never regenerated, only
  checked against LEGACY_V1_SHA256 (compatibility with v1.1 is tested in
  tests/test_http_contract_v11.py).
- contracts/http/examples/*.json (v1 examples) are still produced by one deterministic
  scripted run in rule mode and must stay byte-identical: v1 bodies are unchanged.
- contracts/http/openapi.v1.1.json and examples-v1.1/*.json are the active revision.
`--check` compares bytes instead of writing.

    uv run --locked python scripts/export_http_contract.py [--check]
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(1, str(ROOT))  # source checkout: top-level ml/ and data_pipeline/
OUT = ROOT / "contracts" / "http"
EXAMPLES = OUT / "examples"
EXAMPLES_V11 = OUT / "examples-v1.1"
LEGACY_V1 = OUT / "openapi.v1.json"
LEGACY_V1_SHA256 = "35b4448dd3d4c0e9b5cdaf5b0ac24dd6f90df773aaf8cab9fd217f8739851196"
START = datetime(2026, 10, 23, 17, 0, tzinfo=timezone.utc)
ACCOUNT = "00000000-0000-4000-8000-0000000000a1"
MODEL_ACCOUNT = "00000000-0000-4000-8000-0000000000a2"
ANALYST = frozenset({"ingest_transaction", "read_case", "approve_action",
                     "execute_simulated_action"})


def dumps(value) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def openapi() -> dict:
    from sentinel.api import create_app
    from sentinel.investigators import DeterministicInvestigator
    from sentinel.service import Sentinel

    # No database connection is made to build the schema.
    return create_app(Sentinel("postgresql://unused", DeterministicInvestigator())).openapi()


class _Clock:
    def __init__(self):
        self.now = START

    def __call__(self):
        return self.now


def _uuid_sequence():
    counter = iter(range(1, 1_000_000))
    return lambda: uuid.UUID(int=(0x5E << 120) | next(counter), version=4)


def examples(database_url: str) -> dict[str, dict]:
    """Run the scripted scenario; returns {name: {request, status, response}}."""
    from fastapi.testclient import TestClient

    from sentinel.api import create_app
    from sentinel.investigators import DeterministicInvestigator
    from sentinel.service import Sentinel

    clock = _Clock()
    out: dict[str, dict] = {}
    with mock.patch("uuid.uuid4", _uuid_sequence()):
        service = Sentinel(database_url, DeterministicInvestigator(), clock)
        token = service.create_session(ANALYST)[0]
        client = TestClient(create_app(service))

        def call(name, method, path, body=None, auth=True):
            headers = {"Authorization": f"Bearer {token}"} if auth else {}
            response = client.request(method, path, json=body, headers=headers)
            record = {"request": {"method": method, "path": path,
                                  "authenticated": auth, "body": body},
                      "status": response.status_code, "response": response.json()}
            if name:
                out[name] = record
            return response.json()

        def txn(external_id, minor_units=1500, minutes_ago=0):
            return {"external_id": external_id, "account_id": ACCOUNT, "direction": "debit",
                    "amount": {"currency": "USD", "minor_units": minor_units,
                               "currency_exponent": 2},
                    "occurred_at": (clock() - timedelta(minutes=minutes_ago))
                    .isoformat().replace("+00:00", "Z")}

        call("session", "GET", "/v1/session")
        call("error_unauthenticated", "GET", "/v1/session", auth=False)
        small = txn("demo-small-1", minutes_ago=30)
        call("ingest_below_threshold", "POST", "/v1/transactions", small)
        call("ingest_replay", "POST", "/v1/transactions", small)
        call("error_idempotency_conflict", "POST", "/v1/transactions",
             {**small, "direction": "credit"})
        call("error_invalid_request", "POST", "/v1/transactions",
             {**small, "external_id": "demo-x", "api_key": "never-echoed"})
        call(None, "POST", "/v1/transactions", txn("demo-small-2", 1600, 20))
        call(None, "POST", "/v1/transactions", txn("demo-small-3", 1700, 10))
        case = call("ingest_alert", "POST", "/v1/transactions",
                    txn("demo-large-1", 250_000))["case"]
        clock.now += timedelta(seconds=1)
        second = call(None, "POST", "/v1/transactions", txn("demo-large-2", 120_000))["case"]
        page = call("cases_page_1", "GET", "/v1/cases?limit=1")
        call("cases_page_2", "GET", f"/v1/cases?limit=1&cursor={page['next_cursor']}")
        call("cases_filtered_open", "GET", "/v1/cases?state=open")
        call("error_not_found", "GET", f"/v1/cases/{uuid.UUID(int=0)}")
        call("error_stale_revision", "POST", f"/v1/cases/{case['id']}/investigations",
             {"expected_revision": 7})
        clock.now += timedelta(seconds=5)
        detail = call("investigate", "POST", f"/v1/cases/{case['id']}/investigations",
                      {"expected_revision": 1})
        intent_id = detail["action_intents"][-1]["intent"]["id"]
        approval = call("approval", "POST", "/v1/approvals",
                        {"action_intent_id": intent_id, "decision": "approved"})
        key = str(uuid.UUID(int=0xE0000001, version=4))
        call("execute", "POST", "/v1/actions",
             {"approval_id": approval["id"], "idempotency_key": key})
        call("execute_replay", "POST", "/v1/actions",
             {"approval_id": approval["id"], "idempotency_key": key})
        call("case_detail_closed", "GET", f"/v1/cases/{case['id']}")
        call("audit", "GET", f"/v1/cases/{case['id']}/audit")

        # Expiry lifecycle on the second case.
        detail2 = call(None, "POST", f"/v1/cases/{second['id']}/investigations",
                       {"expected_revision": 1})
        approval2 = call(None, "POST", "/v1/approvals", {
            "action_intent_id": detail2["action_intents"][-1]["intent"]["id"],
            "decision": "approved"})
        clock.now += timedelta(minutes=6)
        call("error_approval_outside_validity", "POST", "/v1/actions", {
            "approval_id": approval2["id"],
            "idempotency_key": str(uuid.UUID(int=0xE0000002, version=4))})
        call("case_detail_reopened", "GET", f"/v1/cases/{second['id']}")
        call("overview", "GET", "/v1/overview")
    return out


# Example -> response model used by tests to validate the frozen set.
EXAMPLE_MODELS = {
    "session": "SessionView", "ingest_below_threshold": "IngestResponse",
    "ingest_replay": "IngestResponse", "ingest_alert": "IngestResponse",
    "cases_page_1": "CasePage", "cases_page_2": "CasePage", "cases_filtered_open": "CasePage",
    "investigate": "CaseDetail", "approval": "Approval", "execute": "ExecuteResponse",
    "execute_replay": "ExecuteResponse", "case_detail_closed": "CaseDetail",
    "case_detail_reopened": "CaseDetail", "audit": "AuditEventList", "overview": "Overview",
}


def examples_v11(database_url: str) -> dict[str, dict]:
    """v1.1 endpoints exercised on real rule-mode and model-mode servers."""
    from fastapi.testclient import TestClient

    from sentinel.api import create_app
    from sentinel.investigators import DeterministicInvestigator
    from sentinel.scorers import REGISTRY, ModelScorer
    from sentinel.service import Sentinel

    clock = _Clock()
    out: dict[str, dict] = {}
    # Load the model before the deterministic uuid sequence: first-time imports in the ml
    # stack may call uuid4, which would shift every id depending on what ran before.
    scorer = ModelScorer(REGISTRY["hgb_balanced@p1"])
    with mock.patch("uuid.uuid4", _uuid_sequence()):
        rule = Sentinel(database_url, DeterministicInvestigator(), clock)
        token = rule.create_session(ANALYST)[0]
        limited = rule.create_session(frozenset({"ingest_transaction"}))[0]
        model = Sentinel(database_url, DeterministicInvestigator(), clock, scorer=scorer)
        for prefix, service in (("rule", rule), ("model", model)):
            client = TestClient(create_app(service))

            def call(name, path, auth=token, method="GET", body=None):
                response = client.request(method, path, json=body,
                                          headers={"Authorization": f"Bearer {auth}"})
                out[name] = {"request": {"method": method, "path": path, "authenticated": True,
                                         "body": body},
                             "status": response.status_code, "response": response.json()}
                return response.json()

            call(f"scorer_{prefix}_mode", "/v1/scoring")
            if prefix == "model":
                call("model_results_p1", "/v1/model-results/p1")
                call("error_model_results_not_found", "/v1/model-results/p2")
                call("error_model_results_permission", "/v1/model-results/p1", auth=limited)
                body = {"external_id": "model-demo-1", "account_id": MODEL_ACCOUNT,
                        "direction": "debit",
                        "amount": {"currency": "GBP", "minor_units": 250_000,
                                   "currency_exponent": 2},
                        "occurred_at": clock().isoformat().replace("+00:00", "Z")}
                call("error_account_profile_missing", "/v1/transactions", method="POST",
                     body=body)
                # Operator provisioning (CLI in deployments; no HTTP route exists for it).
                scope = model.authenticate(token).scope
                model.provision_accounts(scope.tenant_id, scope.session_id, [
                    {"account_id": MODEL_ACCOUNT, "home_currency": "USD",
                     "opened_at": "2026-09-01T00:00:00Z"}])
                clock.now += timedelta(seconds=1)
                case = call("ingest_model_alert", "/v1/transactions", method="POST",
                            body=body)["case"]
                call("ingest_model_replay", "/v1/transactions", method="POST", body=body)
                call("case_detail_model", f"/v1/cases/{case['id']}")
    return out


EXAMPLE_MODELS_V11 = {"scorer_rule_mode": "ScorerInfo", "scorer_model_mode": "ScorerInfo",
                      "model_results_p1": "ModelResults", "ingest_model_alert": "IngestResponse",
                      "ingest_model_replay": "IngestResponse",
                      "case_detail_model": "CaseDetail"}


def expected_files(database_url: str) -> dict[Path, bytes]:
    files = {OUT / "openapi.v1.1.json": dumps(openapi())}
    for name, record in examples(database_url).items():
        files[EXAMPLES / f"{name}.json"] = dumps(record)
    for name, record in examples_v11(database_url).items():
        files[EXAMPLES_V11 / f"{name}.json"] = dumps(record)
    return files


def legacy_problems() -> list[str]:
    import hashlib
    if not LEGACY_V1.exists():
        return [f"{LEGACY_V1.relative_to(ROOT).as_posix()} is missing"]
    if hashlib.sha256(LEGACY_V1.read_bytes()).hexdigest() != LEGACY_V1_SHA256:
        return [f"{LEGACY_V1.relative_to(ROOT).as_posix()} changed (legacy v1 is frozen)"]
    return []


def compare_or_write(files: dict[Path, bytes], check: bool) -> list[str]:
    stale = []
    for path, content in files.items():
        if check:
            if not path.exists() or path.read_bytes() != content:
                stale.append(path.relative_to(ROOT).as_posix())
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    for directory in (EXAMPLES, EXAMPLES_V11):
        present = set(directory.glob("*.json")) if directory.exists() else set()
        stale.extend(sorted(p.relative_to(ROOT).as_posix() for p in present - files.keys()))
    return stale + legacy_problems()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    from sentinel import db, devdb

    bin_dir = devdb.find_pg_bin()
    if bin_dir is None:
        print("Postgres initdb not found; set SENTINEL_PG_BIN.", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(prefix="sentinel-http-") as tmp:
        cluster = devdb.Cluster(bin_dir, Path(tmp) / "data", devdb.free_port())
        cluster.init()
        cluster.start()
        try:
            url = cluster.create_database("http_examples")
            db.migrate(url)
            stale = compare_or_write(expected_files(url), args.check)
        finally:
            cluster.stop()
    if stale:
        print("HTTP contract differs: " + ", ".join(stale))
        return 1
    print(f"{'Verified' if args.check else 'Exported'} HTTP v1.1 OpenAPI and examples; "
          "legacy v1 frozen and unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
