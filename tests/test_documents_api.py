"""DOC01 Part B: the v1.3 document API over real HTTP, real sessions and a bridge process
per request. The bridge is the fake (tests/support/doc01_fake_bridge.py), which replays
answers recorded from the real worker and can be scripted to fail; the real worker runs in
scripts/doc01_api_e2e.py."""
import json
import logging
import os
import sys
import threading
import time
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient

from sentinel import cli
from sentinel.api import create_app
from sentinel.contracts import http_v13
from sentinel.documents import DocumentService, WorkerConfig, owner_key
from sentinel.investigators import DeterministicInvestigator
from sentinel.service import Sentinel

ROOT = Path(__file__).resolve().parents[1]
FAKE = ROOT / "tests" / "support" / "doc01_fake_bridge.py"
RECORDED = ROOT / "tests" / "fixtures" / "doc01" / "bridge_recorded.json"
FIXTURES = ROOT / "tools" / "document_worker" / "fixtures"
ANALYST = frozenset(cli.ALL_CAPABILITIES)
DOCS = ANALYST | {"analyze_document"}
CSV = (FIXTURES / "csv_statement_usd.csv").read_bytes()
ALLOWED_ENV = {"PYTHONIOENCODING", "PYTHONDONTWRITEBYTECODE", "SYSTEMROOT", "WINDIR", "PATH",
               "LANG", "LC_ALL", "SENTINEL_DOC_SESSION"}


class Stack:
    """One API 'process' (service, document service, app, client); recreate to restart."""

    def __init__(self, database_url, clock, store: Path, **config):
        self.store = store
        self.service = Sentinel(database_url, DeterministicInvestigator(), clock)
        self.config = WorkerConfig(argv=(sys.executable, "-I", str(FAKE)), store=str(store),
                                   **config)
        self.documents = DocumentService(self.config)
        self.client = TestClient(create_app(self.service, self.documents))

    def fake(self, **settings):
        path = self.store / "fake.json"
        current = json.loads(path.read_text()) if path.exists() else {
            "recorded": str(RECORDED), "fixtures": str(FIXTURES), "now": time.time()}
        current.update(settings)
        self.store.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(current))

    def calls(self):
        path = self.store / "calls.jsonl"
        return [json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []

    def session(self, grants=DOCS, **kw):
        return self.service.create_session(frozenset(grants), **kw)[0]

    def request(self, method, path, token, **kw):
        headers = dict(kw.pop("headers", {}))
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        return self.client.request(method, path, headers=headers, **kw)

    def upload(self, token, data=CSV, fmt="csv", media="text/csv", **kw):
        return self.request("POST", f"/v1/documents?format={fmt}", token, content=data,
                            headers={"Content-Type": media}, **kw)

    def analyze(self, token, handle, body=None):
        return self.request("POST", f"/v1/documents/{handle}/analysis", token,
                            json={} if body is None else body)


@pytest.fixture
def stack(database_url, clock, tmp_path):
    s = Stack(database_url, clock, tmp_path / "store")
    s.fake()
    return s


def _handle(stack, token, data=CSV, fmt="csv", media="text/csv"):
    response = stack.upload(token, data, fmt, media)
    assert response.status_code == 201, response.text
    return response.json()["handle_id"]


# ---- authority -------------------------------------------------------------------------------

def test_default_grant_is_unchanged_and_document_routes_need_the_opt_in(stack):
    assert cli.ALL_CAPABILITIES == ("ingest_transaction", "read_case", "approve_action",
                                    "execute_simulated_action")
    plain = stack.session(ANALYST)
    doc_token = stack.session()
    handle = _handle(stack, doc_token)
    for response in (stack.upload(plain), stack.analyze(plain, handle),
                     stack.request("GET", f"/v1/documents/{handle}/records", plain),
                     stack.request("DELETE", f"/v1/documents/{handle}", plain)):
        assert (response.status_code, response.json()) == (403, {"error": "permission_denied"})
    session = stack.request("GET", "/v1/session", doc_token).json()
    assert "analyze_document" in session["capabilities"]
    assert "analyze_document" not in stack.request("GET", "/v1/session", plain).json()[
        "capabilities"]
    assert stack.upload(None).status_code == 401
    assert stack.request("GET", f"/v1/documents/{handle}/records", "wrong-token"
                         ).status_code == 401


def test_cli_document_opt_in_adds_exactly_one_grant(database_url, monkeypatch, capsys):
    monkeypatch.setenv("SENTINEL_DATABASE_URL", database_url)
    assert cli.main(["create-session", "--with-document-analysis"]) == 0
    token = capsys.readouterr().out.split("token=")[1].strip()
    ctx = Sentinel(database_url, DeterministicInvestigator()).authenticate(token)
    assert ctx.capabilities == DOCS
    assert cli.main(["create-session"]) == 0
    token = capsys.readouterr().out.split("token=")[1].strip()
    assert Sentinel(database_url, DeterministicInvestigator()).authenticate(token
                                                                            ).capabilities == ANALYST


# ---- happy path, paging, deletion, restart ---------------------------------------------------

def test_upload_analyze_page_delete(stack):
    token = stack.session()
    upload = stack.upload(token)
    assert upload.status_code == 201
    body = http_v13.DocumentUpload.model_validate(upload.json())
    handle = body.handle_id
    analysis = stack.analyze(token, handle, {"records_limit": 5})
    assert analysis.status_code == 200, analysis.text
    doc = http_v13.DocumentAnalysis.model_validate(analysis.json())
    assert (doc.status, doc.records_total, len(doc.records)) == ("complete", 10, 5)
    assert doc.source.sha256 == body.sha256
    page = stack.request("GET", f"/v1/documents/{handle}/records?offset=5&limit=100", token)
    assert page.status_code == 200 and len(page.json()["records"]) == 5
    assert stack.request("DELETE", f"/v1/documents/{handle}", token).json() == {
        "handle_id": handle, "deleted": True}
    for response in (stack.analyze(token, handle),
                     stack.request("GET", f"/v1/documents/{handle}/records", token),
                     stack.request("DELETE", f"/v1/documents/{handle}", token)):
        assert (response.status_code, response.json()) == (404, {"error": "not_found"})


def test_records_before_analysis_is_visible_only_to_the_owner(stack):
    token, other = stack.session(), stack.session()
    handle = _handle(stack, token)
    assert stack.request("GET", f"/v1/documents/{handle}/records", token).json() == {
        "error": "analysis_not_found"}
    assert stack.request("GET", f"/v1/documents/{handle}/records", other).json() == {
        "error": "not_found"}


def test_handles_survive_an_api_restart_for_their_own_session(stack, database_url, clock):
    token = stack.session()
    handle = _handle(stack, token)
    restarted = Stack(database_url, clock, stack.store)  # new service, app and client
    assert restarted.analyze(token, handle).status_code == 200


# ---- handles: foreign, tampered, malformed, expired --------------------------------------------

def test_foreign_tampered_malformed_and_expired_handles_are_indistinguishable(stack, clock):
    token = stack.session()
    other_tenant = stack.session()
    same_tenant = stack.service.create_session(
        DOCS, tenant_id=stack.service.authenticate(token).scope.tenant_id)[0]
    handle = _handle(stack, token)
    tampered = handle[:-1] + ("A" if handle[-1] != "A" else "B")
    cases = [(other_tenant, handle), (same_tenant, handle), (token, tampered),
             (token, "not-a-handle"), (token, "h_" + "x" * 30), (token, "..%2F..%2Fetc")]
    for who, h in cases:
        for response in (stack.analyze(who, h),
                         stack.request("GET", f"/v1/documents/{h}/records", who),
                         stack.request("DELETE", f"/v1/documents/{h}", who)):
            assert (response.status_code, response.json()) == (404, {"error": "not_found"}), h
    stack.fake(now=time.time() + 3601)  # the worker's lease has ended
    assert stack.analyze(token, handle).json() == {"error": "not_found"}
    assert stack.analyze(token, handle).status_code == 404


def test_owner_key_is_derived_never_the_token(stack):
    token = stack.session()
    ctx = stack.service.authenticate(token)
    key = owner_key(ctx, token)
    assert token not in key and len(key) == 64
    assert key != owner_key(stack.service.authenticate(stack.session()), token)


# ---- upload refusals ----------------------------------------------------------------------------

def test_oversize_bodies_are_refused_before_the_worker_sees_them(stack):
    token = stack.session()
    big = b"a" * (http_v13.MAX_UPLOAD_BYTES + 1)
    response = stack.upload(token, big)
    assert (response.status_code, response.json()) == (413, {"error": "body_too_large"})

    def chunks():  # no Content-Length: streamed and stopped at the cap
        for _ in range(11):
            yield b"b" * (1024 * 1024)

    response = stack.upload(token, chunks())
    assert (response.status_code, response.json()) == (413, {"error": "body_too_large"})
    assert [c["op"] for c in stack.calls() if c["op"] == "ingest"] == []


def test_media_type_format_and_content_are_checked(stack):
    token = stack.session()
    for media in ("application/json", "multipart/form-data; boundary=x", "", "text/plain"):
        response = stack.upload(token, media=media)
        assert (response.status_code, response.json()) == (
            415, {"error": "unsupported_media_type"}), media
    assert stack.upload(token, media="application/pdf").status_code == 415  # csv declared
    assert stack.upload(token, fmt="docx").json() == {"error": "invalid_request"}
    assert stack.upload(token, b"").json() == {"error": "invalid_request"}
    pdf = (FIXTURES / "pdf_not_really.pdf").read_bytes()
    assert stack.upload(token, pdf, "pdf", "application/pdf").json() == {
        "error": "format_mismatch"}
    ole = (FIXTURES / "xlsx_ole_container.xlsx").read_bytes()
    response = stack.upload(token, ole, "xlsx", "application/octet-stream")
    assert (response.status_code, response.json()) == (415, {"error": "unsupported_container"})
    assert stack.upload(token, media="text/csv; charset=utf-8").status_code == 201


def test_filenames_and_paths_from_the_request_are_ignored(stack):
    token = stack.session()
    response = stack.request(
        "POST", "/v1/documents?format=csv&path=/etc/passwd&file=../../x", token, content=CSV,
        headers={"Content-Type": "text/csv",
                 "Content-Disposition": 'attachment; filename="../../../evil.csv"'})
    assert response.status_code == 201
    assert not (stack.store.parent / "evil.csv").exists()
    assert set(response.json()) == {"handle_id", "format", "sha256", "size_bytes", "expires_at"}


# ---- document outcomes -----------------------------------------------------------------------

@pytest.mark.parametrize("fixture,fmt,status", [
    ("csv_comma_decimal.csv", "csv", "partial"), ("pdf_scanned_mixed.pdf", "pdf", "partial"),
    ("xlsx_macro.xlsx", "xlsx", "unsupported"), ("pdf_encrypted.pdf", "pdf", "unsupported"),
    ("pdf_truncated.pdf", "pdf", "error")])
def test_malformed_partial_and_unsupported_documents_are_honest_200s(stack, fixture, fmt,
                                                                     status):
    token = stack.session()
    handle = _handle(stack, token, (FIXTURES / fixture).read_bytes(), fmt,
                     "application/octet-stream")
    response = stack.analyze(token, handle)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == status
    if status in ("unsupported", "error"):
        assert body["errors"] and body["records"] == [] and body["records_total"] == 0
    assert body["interpretation"] == http_v13.INTERPRETATION


def test_invalid_analysis_options_are_422_and_never_reach_the_parser(stack):
    token = stack.session()
    handle = _handle(stack, token)
    for bad in ({"decimal_style": "roman"}, {"records_limit": 501}, {"records_limit": 0},
                {"default_currency": "usd"}, {"path": "/etc"}):
        response = stack.analyze(token, handle, bad)
        assert response.status_code == 422 and response.json()["error"] == "invalid_request"
    assert stack.request("GET", f"/v1/documents/{handle}/records?limit=501", token
                         ).status_code == 422
    assert [c["op"] for c in stack.calls() if c["op"] == "analyze"] == []


# ---- worker availability, faults and recovery gating -----------------------------------------

def test_unconfigured_or_invalid_worker_fails_closed(database_url, clock, tmp_path):
    store = tmp_path / "store"
    stack = Stack(database_url, clock, store)
    stack.fake()
    token = stack.session()
    for documents in (DocumentService(None),
                      DocumentService(WorkerConfig(argv=("python",), store=str(store))),
                      DocumentService(WorkerConfig(argv=(sys.executable, "-I", str(FAKE)),
                                                   store="relative/store")),
                      DocumentService(WorkerConfig(argv=(sys.executable, "-I", str(FAKE)),
                                                   store=str(tmp_path / "missing"))),
                      DocumentService(WorkerConfig(argv=(sys.executable, "-I", str(FAKE)),
                                                   store=str(store),
                                                   expected_source_sha256="0" * 64))):
        client = TestClient(create_app(stack.service, documents))
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "text/csv"}
        response = client.post("/v1/documents?format=csv", content=CSV, headers=headers)
        assert (response.status_code, response.json()) == (
            503, {"error": "document_worker_unavailable"})
    stack.fake(status_override={"worker_protocol": "sentinel.doc01.worker/9"})
    response = stack.upload(token)
    assert response.json() == {"error": "document_worker_unavailable"}


def test_environment_configuration_is_opt_in(monkeypatch):
    for key in ("SENTINEL_DOC_WORKER_PYTHON", "SENTINEL_DOC_STORE"):
        monkeypatch.delenv(key, raising=False)
    assert WorkerConfig.from_environment() is None
    monkeypatch.setenv("SENTINEL_DOC_WORKER_PYTHON", sys.executable)
    monkeypatch.setenv("SENTINEL_DOC_STORE", str(ROOT))
    config = WorkerConfig.from_environment()
    assert config.argv == (sys.executable, "-I", "-m", "docworker.bridge")


def _pid_alive(pid: int) -> bool:
    if os.name == "nt":
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(handle)
        return code.value == 259
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def test_timeout_stops_the_bridge_and_blocks_until_recovery_keeps_nothing(database_url, clock,
                                                                          tmp_path):
    stack = Stack(database_url, clock, tmp_path / "store", analyze_timeout_seconds=2.0)
    stack.fake(modes={"analyze": "hang"})
    token = stack.session()
    handle = _handle(stack, token)
    started = time.monotonic()
    response = stack.analyze(token, handle)
    assert (response.status_code, response.json()) == (504, {"error": "document_worker_timeout"})
    assert time.monotonic() - started < 20
    (hung,) = [c for c in stack.calls() if c["op"] == "analyze"]
    assert not _pid_alive(hung["pid"])  # the API stopped the bridge process
    stack.fake(modes={}, recover_kept=1)  # recovery still keeps a record
    response = stack.analyze(token, handle)
    assert (response.status_code, response.json()) == (
        503, {"error": "document_worker_recovery_pending"})
    analyses = [c for c in stack.calls() if c["op"] == "analyze"]
    assert len(analyses) == 1  # blocked: the parser was not run again
    stack.fake(recover_kept=0)
    assert stack.analyze(token, handle).status_code == 200
    assert [c["op"] for c in stack.calls()].count("recover") >= 3


@pytest.mark.parametrize("mode", ["crash", "garbage", "two_lines", "flood", "wrong_protocol",
                                  "invalid_shape"])
def test_bridge_faults_are_502_and_never_a_successful_extraction(stack, mode, caplog):
    token = stack.session()
    handle = _handle(stack, token)
    stack.fake(modes={"analyze": mode})
    with caplog.at_level(logging.INFO):
        response = stack.analyze(token, handle)
    assert (response.status_code, response.json()) == (502, {"error": "document_worker_failed"})
    assert "secret" not in caplog.text and "Traceback" not in response.text
    stack.fake(modes={})
    before = [c["op"] for c in stack.calls()].count("recover")
    assert stack.analyze(token, handle).status_code == 200
    if mode != "invalid_shape":  # a bridge fault requires a recovery pass first
        assert [c["op"] for c in stack.calls()].count("recover") == before + 1


def test_unconfirmed_stop_is_an_error_result_and_blocks_further_runs(stack):
    token = stack.session()
    handle = _handle(stack, token)
    stack.fake(modes={"analyze": "stop_unconfirmed"})
    response = stack.analyze(token, handle)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error" and body["worker_run"]["stop_confirmed"] is False
    assert "stop_unconfirmed" in [e["code"] for e in body["errors"]]
    stack.fake(modes={}, recover_kept=2)
    assert stack.analyze(token, handle).json() == {"error": "document_worker_recovery_pending"}
    stack.fake(recover_kept=0)
    assert stack.analyze(token, handle).json()["status"] == "complete"


def test_one_analysis_at_a_time(database_url, clock, tmp_path):
    stack = Stack(database_url, clock, tmp_path / "store", analyze_timeout_seconds=4.0)
    stack.fake(modes={"analyze": "hang"})
    token = stack.session()
    handle = _handle(stack, token)
    results = []
    first = threading.Thread(target=lambda: results.append(stack.analyze(token, handle)))
    first.start()
    deadline = time.monotonic() + 10
    while not [c for c in stack.calls() if c["op"] == "analyze"] and time.monotonic() < deadline:
        time.sleep(0.05)
    second = stack.analyze(token, handle)
    first.join(timeout=30)
    assert (second.status_code, second.json()) == (503, {"error": "document_worker_busy"})
    assert results[0].status_code == 504


# ---- bounds, environment, secrets and the action boundary ------------------------------------

def test_response_is_bounded_by_the_page_limit(stack):
    token = stack.session()
    handle = _handle(stack, token)
    body = stack.analyze(token, handle, {"records_limit": 5}).json()
    assert len(body["records"]) == 5 and body["records_next_offset"] == 5
    assert body["parser"]["options"]["records_limit"] == 5
    for name in ("records", "unparsed", "findings", "units"):
        limit = http_v13.DocumentAnalysis.model_fields[name].metadata[0].max_length
        assert len(body[name]) <= limit
    assert all("text" not in unit for unit in body["units"])


def test_bridge_gets_a_minimal_environment_and_no_secret(stack, monkeypatch, caplog):
    monkeypatch.setenv("SENTINEL_DATABASE_URL", "postgresql://user:SECRET-PW@db/x")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-SECRET-KEY")
    token = stack.session()
    with caplog.at_level(logging.DEBUG):
        handle = _handle(stack, token)
        stack.analyze(token, handle)
        stack.request("GET", f"/v1/documents/{handle}/records", token)
        stack.request("DELETE", f"/v1/documents/{handle}", token)
    calls = stack.calls()
    assert {c["op"] for c in calls} >= {"status", "ingest", "recover", "analyze", "records",
                                        "delete"}
    for call in calls:
        assert set(call["env"]) <= ALLOWED_ENV, call["env"]
        assert call["cwd_is_store"]
        assert call["owner"] == (call["op"] not in ("status", "recover"))
    stored = "".join(p.read_text(errors="ignore") for p in stack.store.rglob("*") if p.is_file())
    ours = " | ".join(r.getMessage() for r in caplog.records if r.name.startswith("sentinel"))
    assert "/v1/documents/{handle_id}/records" in ours  # the app logged these requests
    for secret in (token, "SECRET-PW", "sk-SECRET-KEY"):
        assert secret not in stored and secret not in ours
    assert handle not in ours  # routes are logged as templates, never handle ids


def test_documents_never_touch_casework(stack, database_url):
    token = stack.session()
    hostile = (FIXTURES / "csv_hostile_note.csv").read_bytes()
    handle = _handle(stack, token, hostile)
    body = stack.analyze(token, handle).json()
    assert body["status"] == "complete"
    with psycopg.connect(database_url) as conn:
        for table in ("transactions", "alerts", "cases", "evidence_items", "agent_runs",
                      "agent_workflows", "action_intents", "approvals", "simulated_actions",
                      "audit_events", "scoring_outcomes"):
            assert conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0, table
