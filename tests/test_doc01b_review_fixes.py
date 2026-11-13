"""DOC01 Part B review 612934b: R60 upload cap, R61 exact counts, R62 uncertain bridge stop,
R63 per-call worker identity. Failing-first against 612934b; see the branch handoff."""
import asyncio
import copy
import json
import os
import subprocess
import tracemalloc

import pytest
from pydantic import ValidationError

from sentinel import documents as docs
from sentinel.api import read_limited
from sentinel.contracts import http_v13
from sentinel.service import ServiceError
from test_documents_api import RECORDED, Stack, _handle, _pid_alive

RECORDED_ANSWERS = json.loads(RECORDED.read_text(encoding="utf-8"))
USD = RECORDED_ANSWERS["fixtures"]["csv_statement_usd.csv"]["analyze"]["analysis"]
HANDLE = "h_" + "A" * 22


@pytest.fixture
def stack(database_url, clock, tmp_path):
    s = Stack(database_url, clock, tmp_path / "store")
    s.fake()
    return s


# ---- R60: one oversize stream chunk is refused before it is copied -------------------------

class _OneChunk:
    def __init__(self, chunk: bytes):
        self.headers = {}  # no Content-Length: streamed
        self.chunk = chunk

    async def stream(self):
        yield self.chunk


def test_r60_single_oversize_chunk_is_refused_without_a_second_copy():
    chunk = b"x" * (32 * 1024 * 1024)
    tracemalloc.start()
    try:
        with pytest.raises(ServiceError) as error:
            asyncio.run(read_limited(_OneChunk(chunk), http_v13.MAX_UPLOAD_BYTES))
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert (error.value.code, error.value.status) == ("body_too_large", 413)
    assert peak < 4 * 1024 * 1024, peak  # the 32 MiB chunk was never appended


def test_r60_a_body_exactly_at_the_cap_is_still_accepted():
    data = asyncio.run(read_limited(_OneChunk(b"y" * http_v13.MAX_UPLOAD_BYTES),
                                    http_v13.MAX_UPLOAD_BYTES))
    assert len(data) == http_v13.MAX_UPLOAD_BYTES


# ---- R61: counts and page metadata are required and consistent --------------------------------

def _mutated(**changes):
    answer = copy.deepcopy(USD)
    for path, value in changes.items():
        target = answer
        *parents, leaf = path.split("__")
        for key in parents:
            target = target[key]
        if value is _DELETE:
            del target[leaf]
        else:
            target[leaf] = value
    return answer


_DELETE = object()


@pytest.mark.parametrize("changes", [
    {"records_page__total": _DELETE}, {"unparsed_total": _DELETE},
    {"records_page__total": _DELETE, "unparsed_total": _DELETE},
    {"records_page__total": 0}, {"records_page__total": 4},  # fewer than the 5 returned
    {"records_page__next_offset": None},  # 5 of 10 returned but "no more"
    {"records_page__next_offset": 7}, {"records_page__offset": 3},
    {"records_page__limit": 2},  # 5 records cannot fit a limit of 2
    {"records_page__limit": _DELETE}, {"records_page__offset": _DELETE},
    {"records_page__next_offset": _DELETE}, {"records_page__records": _DELETE},
    {"records_page": _DELETE}, {"unparsed_total": -1},
    {"coverage__records_typed": 3}, {"coverage__rows_unparsed": 2},
])
def test_r61_missing_or_contradictory_counts_are_rejected(changes):
    with pytest.raises((ValidationError, ValueError)):
        http_v13.project_analysis(HANDLE, _mutated(**changes))


def test_r61_genuine_zero_partial_unsupported_and_error_answers_still_project():
    for name, entry in RECORDED_ANSWERS["fixtures"].items():
        analysis = http_v13.project_analysis(HANDLE, entry["analyze"]["analysis"])
        assert analysis.records_total >= len(analysis.records), name


@pytest.mark.parametrize("mode", ["drop_totals", "zero_total"])
def test_r61_malformed_counts_through_the_api_are_502(stack, mode):
    token = stack.session()
    handle = _handle(stack, token)
    stack.fake(modes={"analyze": mode})
    response = stack.analyze(token, handle)
    assert (response.status_code, response.json()) == (502, {"error": "document_worker_failed"})


def test_r61_contradictory_record_page_is_502(stack):
    token = stack.session()
    handle = _handle(stack, token)
    assert stack.analyze(token, handle).status_code == 200
    stack.fake(modes={"records": "bad_page"})
    response = stack.request("GET", f"/v1/documents/{handle}/records?offset=5&limit=100",
                             token)
    assert (response.status_code, response.json()) == (502, {"error": "document_worker_failed"})


@pytest.mark.parametrize("page", [
    {"offset": 0, "limit": 5, "total": 2, "records": [], "next_offset": None},
    {"offset": 5, "limit": 5, "total": 10, "records": [], "next_offset": None},
    {"offset": 0, "limit": 5, "total": 0, "records": [], "next_offset": 0},
])
def test_r61_record_page_relations(page):
    with pytest.raises(ValidationError):
        http_v13.RecordPage(handle_id=HANDLE, status="complete", source_sha256="a" * 64,
                            **page)


# ---- R62: an unconfirmed bridge stop is durable and blocks analysis ---------------------------

def _bridge_records(stack):
    folder = stack.store / docs.BRIDGE_RECORD_DIR
    return sorted(folder.glob("*.json")) if folder.is_dir() else []


def _hung_bridge(database_url, clock, tmp_path):
    stack = Stack(database_url, clock, tmp_path / "store", analyze_timeout_seconds=2.0)
    stack.fake(modes={"analyze": "hang"})
    return stack


def test_r62_kill_failure_is_recorded_blocks_analysis_and_restart_recovers(
        database_url, clock, tmp_path, monkeypatch, caplog):
    stack = _hung_bridge(database_url, clock, tmp_path)
    token = stack.session()
    handle = _handle(stack, token)

    def refuse_kill(self):
        raise PermissionError(13, "Access is denied: C:\\secret\\bridge")

    monkeypatch.setattr(subprocess.Popen, "kill", refuse_kill)
    monkeypatch.setattr(docs, "_terminate_pid", lambda pid: None)  # recovery cannot stop it
    response = stack.analyze(token, handle)
    assert (response.status_code, response.json()) == (504, {"error": "document_worker_timeout"})
    assert "secret" not in response.text and "secret" not in caplog.text
    (hung,) = [c for c in stack.calls() if c["op"] == "analyze"]
    assert _pid_alive(hung["pid"])  # the kill really failed: an owned, live bridge
    records = _bridge_records(stack)
    # The recorded pid is the launched bridge: on Windows a venv launcher whose child
    # reported its own pid, elsewhere the interpreter itself.
    assert len(records) == 1
    assert json.loads(records[0].read_text())["pid"] in (hung["pid"], hung["ppid"])
    assert token not in records[0].read_text()
    # Same process: still alive and still unkillable -> refused, parser not run again.
    stack.fake(modes={})
    response = stack.analyze(token, handle)
    assert response.json() == {"error": "document_worker_recovery_pending"}
    assert len([c for c in stack.calls() if c["op"] == "analyze"]) == 1
    monkeypatch.undo()
    # API restart: recovery re-verifies the recorded identity, stops it and confirms exit.
    restarted = Stack(database_url, clock, stack.store)
    assert restarted.analyze(token, handle).status_code == 200
    assert not _pid_alive(hung["pid"]) and _bridge_records(stack) == []


def test_r62_unconfirmed_exit_after_kill_is_recorded_until_absence_is_verified(
        database_url, clock, tmp_path, monkeypatch):
    stack = _hung_bridge(database_url, clock, tmp_path)
    token = stack.session()
    handle = _handle(stack, token)
    real_wait = subprocess.Popen.wait
    state = {"calls": 0}

    def unconfirmed_wait(self, timeout=None):
        state["calls"] += 1
        if state["calls"] >= 2:  # the confirmation after kill() never succeeds
            raise subprocess.TimeoutExpired(self.args, timeout)
        return real_wait(self, timeout=timeout)

    monkeypatch.setattr(subprocess.Popen, "wait", unconfirmed_wait)
    response = stack.analyze(token, handle)
    monkeypatch.undo()
    assert (response.status_code, response.json()) == (504, {"error": "document_worker_timeout"})
    assert len(_bridge_records(stack)) == 1
    stack.fake(modes={})
    assert stack.analyze(token, handle).status_code == 200  # kill had worked: verified gone
    assert _bridge_records(stack) == []


def test_r62_a_reused_pid_is_never_signalled(database_url, clock, tmp_path, monkeypatch):
    stack = Stack(database_url, clock, tmp_path / "store")
    stack.fake()
    folder = stack.store / docs.BRIDGE_RECORD_DIR
    folder.mkdir(parents=True)
    me = os.getpid()
    (folder / f"bridge-{me}.json").write_text(json.dumps(
        {"pid": me, "identity": "forged-identity", "op": "analyze"}))
    killed = []
    monkeypatch.setattr(docs, "_terminate_pid", lambda pid: killed.append(pid))
    token = stack.session()
    handle = _handle(stack, token)
    assert stack.analyze(token, handle).status_code == 200
    assert killed == [] and _pid_alive(me)
    assert _bridge_records(stack) == []  # the recorded process is gone (pid reused)


def test_r62_an_unreadable_bridge_record_keeps_analysis_blocked(stack):
    folder = stack.store / docs.BRIDGE_RECORD_DIR
    folder.mkdir(parents=True)
    (folder / "bridge-1.json").write_text("{torn")
    token = stack.session()
    handle = _handle(stack, token)
    assert stack.analyze(token, handle).json() == {"error": "document_worker_recovery_pending"}
    assert len(_bridge_records(stack)) == 1


# ---- R63: every bridge call and every analysis is bound to the registered worker ---------------

def test_r63_worker_change_after_a_successful_call_fails_closed(stack):
    token = stack.session()
    handle = _handle(stack, token)  # registers the recorded worker identity
    assert stack.analyze(token, handle).status_code == 200
    stack.fake(status_override={"worker_source_sha256": "2" * 64})  # worker changed on disk
    for response in (stack.analyze(token, handle), stack.upload(token),
                     stack.request("GET", f"/v1/documents/{handle}/records", token),
                     stack.request("DELETE", f"/v1/documents/{handle}", token)):
        assert (response.status_code, response.json()) == (
            503, {"error": "document_worker_identity_changed"})
    # The changed worker refused before running (its own check of expect_source_sha256,
    # tested in the worker's bridge tests); no report was returned.


def test_r63_analysis_reporting_another_source_is_never_a_success(stack):
    token = stack.session()
    handle = _handle(stack, token)
    stack.fake(modes={"analyze": "parser_digest_changed"})
    response = stack.analyze(token, handle)
    assert (response.status_code, response.json()) == (
        503, {"error": "document_worker_identity_changed"})
    stack.fake(modes={})
    # Parsing may have started under an unregistered worker: recovery runs before reuse.
    before = [c["op"] for c in stack.calls()].count("recover")
    assert stack.analyze(token, handle).status_code == 200
    assert [c["op"] for c in stack.calls()].count("recover") == before + 1


def test_r63_answer_without_identity_is_rejected(stack):
    token = stack.session()
    handle = _handle(stack, token)
    stack.fake(modes={"records": "omit_identity"})
    stack.analyze(token, handle)
    response = stack.request("GET", f"/v1/documents/{handle}/records", token)
    assert (response.status_code, response.json()) == (
        503, {"error": "document_worker_identity_changed"})


def test_r63_pin_is_enforced_on_every_call(database_url, clock, tmp_path):
    pinned = RECORDED_ANSWERS["status"]["worker_source_sha256"]
    stack = Stack(database_url, clock, tmp_path / "store", expected_source_sha256=pinned)
    stack.fake()
    token = stack.session()
    handle = _handle(stack, token)
    assert stack.analyze(token, handle).status_code == 200
    stack.fake(status_override={"worker_source_sha256": "3" * 64})
    assert stack.analyze(token, handle).json() == {"error": "document_worker_identity_changed"}
    restarted = Stack(database_url, clock, stack.store, expected_source_sha256=pinned)
    assert restarted.upload(token).json() == {"error": "document_worker_unavailable"}

