"""I01: the browser stack in model mode. Real uvicorn processes on disposable PostgreSQL, the
API connected as the least-privilege runtime role, the accepted registered scorer, model
scenarios seeded through the accepted operator methods, and real restarts between modes.
All HTTP goes over real sockets; no route is added."""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import psycopg
import pytest

ROOT = Path(__file__).resolve().parents[1]
SUPPORT = ROOT / "tests" / "support"
sys.path.insert(0, str(SUPPORT))

import browser_stack  # noqa: E402
from browser_stack import SCORERS, Stack, StackError, healthy  # noqa: E402
from sentinel import devdb, model_results  # noqa: E402
from sentinel.contracts.http_v1 import ModelResults  # noqa: E402
from test_browser_fixtures import http  # noqa: E402

pytestmark = pytest.mark.skipif(devdb.find_pg_bin() is None, reason="needs PostgreSQL binaries")
MODEL = SCORERS["model"]
MODEL_SCENARIOS = ("model_alert", "model_missing_profile", "model_live_alert")
CLEAN = {"ok": True, "api_stopped": True, "database_stopped": True, "state_removed": True,
         "errors": []}
ARTIFACT_SHA = "6c2982d1df12184f704bc45dbc5882d8f85dba16c50bd9829dda9e674602575b"
THRESHOLD = 4.0295386895426815e-06


@pytest.fixture(scope="module")
def stack():
    started = Stack.start(scorer=MODEL, model_fixtures=True)
    yield started
    assert started.stop() == CLEAN


def rec(stack, name):
    return stack.manifest["scenarios"][name]


def owner(stack):
    return psycopg.connect(stack.manifest["database_url"])


def stored(stack, external_id):
    with owner(stack) as conn:
        return conn.execute(
            "SELECT t.id, o.body AS outcome FROM transactions t LEFT JOIN scoring_outcomes o"
            " ON o.transaction_id = t.id WHERE t.external_id = %s", (external_id,)).fetchall()


def status_only(stack, path, token):
    """Status of a request whose error body may not be JSON (an unhandled 500 is plain)."""
    request = urllib.request.Request(stack.manifest["api"]["base_url"] + path, headers={
        "Authorization": f"Bearer {stack.manifest['tokens'][token]}"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


def test_api_connects_as_the_runtime_role(stack):
    assert stack.manifest["api"]["database_user"] == browser_stack.RUNTIME_ROLE
    assert http(stack, "GET", "/v1/session", "analyst")[0] == 200
    with owner(stack) as conn:  # take the runtime role's login away: the API must fail
        conn.execute(f'ALTER ROLE "{browser_stack.RUNTIME_ROLE}" NOLOGIN')
        conn.commit()
    try:
        assert status_only(stack, "/v1/session", "analyst") >= 500
    finally:
        with owner(stack) as conn:
            conn.execute(f'ALTER ROLE "{browser_stack.RUNTIME_ROLE}" LOGIN')
            conn.commit()
    assert http(stack, "GET", "/v1/session", "analyst")[0] == 200
    runtime = psycopg.conninfo.make_conninfo(stack.manifest["database_url"],
                                             user=browser_stack.RUNTIME_ROLE)
    with psycopg.connect(runtime) as conn:  # it can read model inputs but never write them
        assert conn.execute("SELECT count(*) FROM account_profiles").fetchone()[0] >= 2
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("UPDATE account_profiles SET home_currency = 'GBP'")


def test_scoring_and_results_routes_and_permissions(stack):
    status, info = http(stack, "GET", "/v1/scoring", "analyst")
    assert status == 200 and info["mode"] == "model"
    assert info["score_semantics"] == "uncalibrated_score" and info["threshold"] == THRESHOLD
    assert info["scorer"]["sha256"] == ARTIFACT_SHA and info["results_id"] == "p1"
    status, results = http(stack, "GET", "/v1/model-results/p1", "read_only")
    assert status == 200
    # The frozen report, as the accepted ModelResults DTO serializes it.
    assert results == ModelResults.model_validate(model_results.load("p1")).model_dump(
        mode="json")
    assert results["label"] == "offline synthetic benchmark" and results["synthetic"] is True
    assert results["frozen_threshold"] == THRESHOLD
    for path in ("/v1/scoring", "/v1/model-results/p1"):
        assert http(stack, "GET", path, "ingest_only") == (403, {"error": "permission_denied"})
        assert http(stack, "GET", path)[0] == 401
    assert http(stack, "GET", "/v1/model-results/p2", "analyst") == (404, {"error": "not_found"})


def test_recorded_model_case_has_exact_stored_inputs_and_provenance(stack):
    record = rec(stack, "model_alert")
    status, view = http(stack, "GET", f"/v1/cases/{record['case_id']}", "analyst")
    assert status == 200 and (view["case"]["state"], view["case"]["revision"]) == ("open", 1)
    scoring = view["scoring"]
    assert {k: scoring[k] for k in record["expected_scoring"]} == record["expected_scoring"]
    assert (scoring["scoring_kind"], scoring["score_semantics"]) == ("model",
                                                                     "uncalibrated_score")
    assert scoring["score"] == 0.61962960122 and scoring["threshold"] == THRESHOLD
    inputs = scoring["inputs"]
    assert inputs["values"] == {
        "amount_minor": 250000, "is_credit": 0, "is_foreign_currency": 1,
        "account_age_days": 400, "count_1h": 0, "count_24h": 0, "small_count_1h": 0,
        "same_currency_sum_24h": 0, "credit_sum_24h": 0, "seconds_since_prev": -1,
        "amount_to_median_bps": -1, "prior_known_fraud": 1}
    assert (inputs["currency"], inputs["history_rows"], inputs["disclosures_used"],
            inputs["profile_home_currency"]) == ("GBP", 0, 1, "USD")
    assert scoring["model"]["artifact_sha256"] == ARTIFACT_SHA
    assert scoring["model"]["threshold_source"] == "validation_frozen_threshold"
    assert view["case"]["pins"]["scorer"]["name"] == "hgb_balanced"
    assert view["alert"]["scoring_kind"] == "model"
    rule = http(stack, "GET", f"/v1/cases/{rec(stack, 'open_case')['case_id']}", "analyst")[1]
    assert rule["scoring"]["scoring_kind"] == "rule" and "model" not in rule["scoring"]
    assert "inputs" not in rule["scoring"]
    summaries = {i["id"]: i for i in http(stack, "GET", "/v1/cases?limit=100", "analyst")[1][
        "items"]}
    assert summaries[record["case_id"]]["scoring_kind"] == "model"
    assert summaries[rec(stack, "open_case")["case_id"]]["scoring_kind"] == "rule"


def test_model_case_is_invisible_to_another_session(stack):
    case_id = rec(stack, "model_alert")["case_id"]
    for path in (f"/v1/cases/{case_id}", f"/v1/cases/{case_id}/audit"):
        assert http(stack, "GET", path, "other_session") == (404, {"error": "not_found"})
    assert http(stack, "POST", f"/v1/cases/{case_id}/investigations", "other_session",
                {"expected_revision": 1}) == (404, {"error": "not_found"})
    listed = http(stack, "GET", "/v1/cases?limit=100", "other_session")[1]["items"]
    assert case_id not in {i["id"] for i in listed}


def test_missing_profile_is_refused_and_nothing_is_stored(stack):
    record = rec(stack, "model_missing_profile")
    with owner(stack) as conn:
        before = conn.execute("SELECT (SELECT count(*) FROM transactions),"
                              " (SELECT count(*) FROM cases)").fetchone()
    assert http(stack, "POST", "/v1/transactions", "analyst", record["request_body"]) == (
        422, {"error": "account_profile_missing"})
    assert stored(stack, record["request_body"]["external_id"]) == []
    with owner(stack) as conn:
        assert conn.execute("SELECT (SELECT count(*) FROM transactions),"
                            " (SELECT count(*) FROM cases)").fetchone() == before


def test_live_ingestion_equals_the_artifact_expectation(stack):
    for record in (rec(stack, "model_live_alert"),
                   stack.seed("model_live_alert", 1)):  # an on-demand fresh account
        expected = record["expected_scoring"]
        status, body = http(stack, "POST", "/v1/transactions", "analyst",
                            record["request_body"])
        assert status == 201 and body["replayed"] is False
        scoring = body["scoring"]
        assert {k: scoring[k] for k in ("scoring_kind", "score_semantics", "score",
                                        "threshold", "alerted", "model")} == {
            k: expected[k] for k in ("scoring_kind", "score_semantics", "score", "threshold",
                                     "alerted", "model")}
        assert scoring["inputs"]["values"] == expected["values"]
        assert (scoring["inputs"]["history_rows"], scoring["inputs"]["disclosures_used"],
                scoring["inputs"]["profile_home_currency"]) == (0, 0, "USD")
        assert scoring["score"] == 0.802130558706 and scoring["alerted"] is True
        assert body["case"]["pins"]["scorer"]["sha256"] == ARTIFACT_SHA
        (row,) = stored(stack, record["request_body"]["external_id"])
        assert row[1]["score"] == scoring["score"] and row[1]["inputs"] == scoring["inputs"]


def test_model_seed_ids_are_stable_and_cli_prints_no_tokens(stack, tmp_path):
    out = subprocess.run([sys.executable, str(SUPPORT / "browser_stack.py"), "start",
                          "--parent-dir", str(tmp_path), "--scorer", "model"],
                         capture_output=True, text=True, timeout=240, check=True)
    manifest_path = Path(out.stdout.split("SENTINEL_STACK_MANIFEST=")[1].split()[0])
    other = json.loads(manifest_path.read_text())
    try:
        assert "scorer=model" in out.stdout and other["model_fixtures"] is True
        for token in other["tokens"].values():
            assert token not in out.stdout and token not in out.stderr
        assert other["database_url"] not in out.stdout + out.stderr
        for name in MODEL_SCENARIOS:
            mine, theirs = rec(stack, name), other["scenarios"][name]
            assert {k: theirs.get(k) for k in ("case_id", "transaction_id", "account_id")} == \
                {k: mine.get(k) for k in ("case_id", "transaction_id", "account_id")}
            if "expected_scoring" in mine:
                assert theirs["expected_scoring"]["score"] == mine["expected_scoring"]["score"]
        status = subprocess.run([sys.executable, str(SUPPORT / "browser_stack.py"), "status",
                                 "--manifest", str(manifest_path)], capture_output=True,
                                text=True, timeout=60, check=True)
        assert json.loads(status.stdout) == {"api": "up", "database": "up"}  # C02 shape
        assert json.loads(manifest_path.read_text())["api"]["scorer"] == MODEL
    finally:
        stopped = subprocess.run([sys.executable, str(SUPPORT / "browser_stack.py"), "stop",
                                  "--manifest", str(manifest_path)], capture_output=True,
                                 text=True, timeout=60)
    assert stopped.returncode == 0 and json.loads(stopped.stdout) == CLEAN
    assert not list(tmp_path.glob("sentinel-browser-*"))
    assert healthy(other["api"]["port"]) is None


def test_default_stack_is_rule_mode_without_model_fixtures(tmp_path):
    rule = Stack.start(tmp_path)
    try:
        assert rule.manifest["api"]["scorer"] == "rule" and not rule.manifest["model_fixtures"]
        assert not set(MODEL_SCENARIOS) & set(rule.manifest["scenarios"])
        assert "ingest_only" not in rule.manifest["tokens"]
        assert http(rule, "GET", "/v1/scoring", "analyst")[1]["mode"] == "rule"
        with pytest.raises(StackError, match="--model-fixtures"):
            rule.seed("model_live_alert", 1)
        # A restart into an unbindable scorer fails closed; the stack stays recoverable.
        with pytest.raises(StackError, match="exited"):
            rule.restart_api(timeout=30, scorer="model:not-registered")
        assert healthy(rule.manifest["api"]["port"]) is None
        rule.restart_api(scorer="rule")
        assert http(rule, "GET", "/v1/scoring", "analyst")[1]["mode"] == "rule"
    finally:
        assert rule.stop() == CLEAN
    assert not list(tmp_path.glob("sentinel-browser-*"))


def test_failed_model_start_cleans_up(tmp_path, monkeypatch):
    seen = []
    real_stop = Stack.stop

    def recording_stop(self):
        seen.append((self.state_dir, self.manifest["api"].get("port")))
        return real_stop(self)

    monkeypatch.setattr(Stack, "stop", recording_stop)
    with pytest.raises(StackError, match="exited"):
        Stack.start(tmp_path, scorer="model:not-registered", model_fixtures=True, timeout=60)
    (state_dir, port), = seen
    assert Path(os.path.realpath(state_dir)).parent == Path(os.path.realpath(tmp_path))
    assert not state_dir.exists() and not list(tmp_path.glob("sentinel-browser-*"))
    assert healthy(port) is None


def test_scorer_switch_restarts_preserve_identity_and_replay(stack):
    """Last in this module: it changes the shared stack's mode (and restores it)."""
    record = rec(stack, "model_alert")
    path = f"/v1/cases/{record['case_id']}"
    before = http(stack, "GET", path, "analyst")[1]
    audit = http(stack, "GET", f"{path}/audit", "analyst")[1]
    pid = stack.manifest["api"]["pid"]
    cli = subprocess.run([sys.executable, str(SUPPORT / "browser_stack.py"), "restart-api",
                          "--manifest", str(stack.path), "--scorer", "rule"],
                         capture_output=True, text=True, timeout=120, check=True)
    assert "scorer=rule" in cli.stdout
    stack.manifest = json.loads(stack.path.read_text())  # the CLI rewrote the manifest
    assert stack.manifest["api"]["pid"] != pid and stack.manifest["api"]["scorer"] == "rule"
    assert stack.status() == {"api": "up", "database": "up"}
    assert http(stack, "GET", "/v1/scoring", "analyst")[1]["mode"] == "rule"
    assert http(stack, "GET", path, "analyst")[1] == before  # historical identity kept
    status, replay = http(stack, "POST", "/v1/transactions", "analyst", record["request_body"])
    assert status == 201 and replay["replayed"] is True
    assert replay["scoring"] == before["scoring"]
    fresh = dict(rec(stack, "model_missing_profile")["request_body"],
                 external_id="i01-rule-mode-fresh")
    status, ruled = http(stack, "POST", "/v1/transactions", "analyst", fresh)
    assert status == 201 and ruled["scoring"]["scoring_kind"] == "rule"
    assert "model" not in ruled["scoring"] and "inputs" not in ruled["scoring"]
    stack.restart_db()
    stack.restart_api(scorer=MODEL)
    assert http(stack, "GET", "/v1/scoring", "analyst")[1]["mode"] == "model"
    assert http(stack, "GET", path, "analyst")[1] == before
    assert http(stack, "GET", f"{path}/audit", "analyst")[1] == audit
    replay = http(stack, "POST", "/v1/transactions", "analyst", fresh)[1]  # rule record stays
    assert replay["replayed"] is True and replay["scoring"] == ruled["scoring"]
