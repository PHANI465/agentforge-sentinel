"""DOC01 Part B bridge: the only interface the Sentinel API uses (one request per process)."""
import json
import os
import subprocess
import sys

import pytest

from conftest import FIXTURES, OTHER_SESSION, SESSION, leftovers
from docworker import bridge
from docworker.handles import HandleStore

HEADER = bridge.BRIDGE_PROTOCOL


def call(store_root, header, body=b"", session=SESSION, raw_header=None):
    env = {k: v for k, v in os.environ.items() if k != bridge.SESSION_ENV}
    if session is not None:
        env[bridge.SESSION_ENV] = session
    line = raw_header if raw_header is not None else (
        json.dumps({"protocol": HEADER, **header}) + "\n").encode()
    proc = subprocess.run([sys.executable, "-I", "-m", "docworker.bridge", "--store",
                           str(store_root)], input=line + body, capture_output=True,
                          env=env, timeout=120)
    assert proc.returncode == 0, proc.stderr[-2000:]
    lines = proc.stdout.decode("utf-8").splitlines()
    assert len(lines) == 1
    return json.loads(lines[0])


def ingest(store, name, fmt=None, session=SESSION):
    data = (FIXTURES / name).read_bytes()
    out = call(store.root, {"op": "ingest", "format": fmt or name.rsplit(".", 1)[1],
                            "size": len(data)}, data, session=session)
    assert out["ok"], out
    return out["handle"]


def test_status_reports_identity_and_refuses_an_unowned_store(store, tmp_path):
    out = call(store.root, {"op": "status"}, session=None)
    assert out["ok"] and out["store"] == "ready"
    assert out["worker_protocol"] == "sentinel.doc01.worker/0.1"
    assert len(out["worker_source_sha256"]) == 64
    (tmp_path / "plain").mkdir()
    refused = call(tmp_path / "plain", {"op": "status"}, session=None)
    assert {k: refused[k] for k in ("protocol", "ok", "code")} == {
        "protocol": HEADER, "ok": False, "code": "not_owned"}


@pytest.mark.parametrize("raw", [b"not json\n", b'{"protocol": "x", "op": "status"}\n',
                                 b'{"protocol": "%s", "op": "rm"}\n' % HEADER.encode(),
                                 b'{"protocol": "%s", "op": "status"}' % HEADER.encode()])
def test_malformed_headers_are_refused(store, raw):
    assert call(store.root, {}, raw_header=raw)["code"] == "bad_header"


def test_ingest_checks_size_framing_session_and_content(store):
    data = (FIXTURES / "csv_statement_usd.csv").read_bytes()
    big = store.limits.max_input_bytes + 1
    assert call(store.root, {"op": "ingest", "format": "csv", "size": big}, b"")["code"] \
        == "bad_header"
    assert call(store.root, {"op": "ingest", "format": "csv", "size": len(data) + 5},
                data)["code"] == "framing_mismatch"
    assert call(store.root, {"op": "ingest", "format": "csv", "size": len(data)}, data + b"x"
                )["code"] == "framing_mismatch"
    assert call(store.root, {"op": "ingest", "format": "csv", "size": len(data)}, data,
                session=None)["code"] == "invalid_session"
    pdf = (FIXTURES / "pdf_text_statement.pdf").read_bytes()
    assert call(store.root, {"op": "ingest", "format": "csv", "size": len(pdf)}, pdf
                )["code"] == "format_mismatch"
    assert call(store.root, {"op": "ingest", "format": "xlsx", "size": len(data)}, data
                )["code"] == "format_mismatch"
    ole = (FIXTURES / "xlsx_ole_container.xlsx").read_bytes()
    assert call(store.root, {"op": "ingest", "format": "xlsx", "size": len(ole)}, ole
                )["code"] == "unsupported_container"
    assert call(store.root, {"op": "ingest", "format": "docx", "size": 3}, b"abc"
                )["code"] == "format_not_supported"
    assert leftovers(store) == {"runs": [], "recovery": []}
    assert list((store.root / "handles").iterdir()) == []


def test_analyze_is_compact_persisted_and_session_owned(store):
    h = ingest(store, "csv_statement_usd.csv")
    out = call(store.root, {"op": "analyze", "handle": h["handle_id"], "page_limit": 3,
                            "options": {}})
    assert out["ok"], out
    analysis = out["analysis"]
    assert analysis["status"] == "complete" and analysis["narrative"] is None
    assert "records" not in analysis
    page = analysis["records_page"]
    assert (page["total"], len(page["records"]), page["next_offset"]) == (10, 3, 3)
    assert analysis["source"]["sha256"] == h["sha256"]
    rest = call(store.root, {"op": "records", "handle": h["handle_id"], "offset": 3,
                             "limit": 500})
    assert rest["ok"] and rest["records_page"]["next_offset"] is None
    assert len(rest["records_page"]["records"]) == 7
    for op in ({"op": "records", "handle": h["handle_id"], "offset": 0, "limit": 1},
               {"op": "analyze", "handle": h["handle_id"], "page_limit": 1, "options": {}},
               {"op": "delete", "handle": h["handle_id"]}):
        assert call(store.root, op, session=OTHER_SESSION)["code"] == "not_found"
    assert call(store.root, {"op": "delete", "handle": h["handle_id"]})["deleted"] is True
    assert call(store.root, {"op": "records", "handle": h["handle_id"], "offset": 0,
                             "limit": 1})["code"] == "not_found"
    assert leftovers(store) == {"runs": [], "recovery": []}


def test_records_before_analysis_and_bad_options(store):
    h = ingest(store, "csv_statement_usd.csv")
    assert call(store.root, {"op": "records", "handle": h["handle_id"], "offset": 0,
                             "limit": 5})["code"] == "analysis_not_found"
    assert call(store.root, {"op": "analyze", "handle": h["handle_id"], "page_limit": 5,
                             "options": {"decimal_style": "roman"}})["code"] == \
        "invalid_option"
    assert call(store.root, {"op": "analyze", "handle": h["handle_id"], "page_limit": 0,
                             "options": {}})["code"] == "bad_header"


def test_pdf_page_text_is_not_returned(store):
    h = ingest(store, "pdf_scanned_mixed.pdf")
    analysis = call(store.root, {"op": "analyze", "handle": h["handle_id"], "page_limit": 10,
                                 "options": {}})["analysis"]
    assert analysis["status"] == "partial"
    assert all("text" not in u for u in analysis["units"])
    assert [u["chars"] for u in analysis["units"]][0] > 0
    assert analysis["records_page"]["total"] == 0


def test_large_documents_are_paged_and_byte_bounded(store):
    rows = ["Date,Description,Amount,Currency"] + [
        f"2026-05-{1 + i % 28:02d},{'x' * 4000} {i},-1.{i % 100:02d},USD" for i in range(1200)]
    data = ("\n".join(rows) + "\n").encode()
    out = call(store.root, {"op": "ingest", "format": "csv", "size": len(data)}, data)
    hid = out["handle"]["handle_id"]
    first = call(store.root, {"op": "analyze", "handle": hid, "page_limit": 500,
                              "options": {}})["analysis"]["records_page"]
    assert first["total"] == 1200
    assert 0 < len(first["records"]) < 500  # stopped by MAX_PAGE_BYTES, not the count
    assert len(json.dumps(first["records"]).encode()) <= bridge.MAX_PAGE_BYTES
    seen, offset = len(first["records"]), first["next_offset"]
    while offset is not None:
        nxt = call(store.root, {"op": "records", "handle": hid, "offset": offset,
                                "limit": 500})["records_page"]
        assert nxt["offset"] == offset and nxt["records"]
        seen += len(nxt["records"])
        offset = nxt["next_offset"]
    assert seen == 1200


def test_long_evidence_lists_are_capped_with_totals():
    doc = {"records": [], "units": [], "unparsed": [{"x": i} for i in range(300)],
           "findings": [{"finding_id": "F1", "evidence_ids": ["e"] * 50, "evidence_count": 80}],
           "measures": {"duplicates": {"groups": [{"evidence_ids": ["a"] * 70, "count": 70}]
                                       * 150},
                        "running_balance": {"mismatches": [{}] * 120}},
           "narrative": {"status": "ok", "text": "secret page text", "chars": 16}}
    out = bridge.compact(doc, 10)
    assert len(out["unparsed"]) == 100
    assert out["findings"] == doc["findings"]  # already capped by the worker
    assert out["measures"]["duplicates"]["groups_total"] == 150
    assert len(out["measures"]["duplicates"]["groups"]) == 100
    group = out["measures"]["duplicates"]["groups"][0]
    assert (len(group["evidence_ids"]), group["count"]) == (50, 70)
    assert out["measures"]["running_balance"]["mismatches_total"] == 120
    assert out["narrative"] == {"status": "ok", "chars": 16, "truncated": False}


def test_expired_handles_are_not_found_and_purged(tmp_path):
    clock = {"now": 1000.0}
    store = HandleStore(tmp_path / "s", clock=lambda: clock["now"])
    store.init()
    h = store.ingest_bytes(b"Date,Amount\n2026-01-01,1.00\n", "csv", SESSION)
    clock["now"] += store.limits.handle_ttl_seconds + 1
    with pytest.raises(Exception) as exc:
        store.resolve(h["handle_id"], SESSION)
    assert getattr(exc.value, "code", None) == "not_found"
    assert store.purge_expired() == {"removed": 1, "kept": 0}


def test_recover_reports_nothing_kept_on_a_clean_store(store):
    out = call(store.root, {"op": "recover"}, session=None)
    assert out["ok"] and out["recovery"] == {"results": {}, "kept": 0}


# ---- review R63: identity on every answer; a different registered digest is refused first ----

def test_every_answer_carries_this_worker_identity(store):
    from docworker.extract import source_identity
    digest = source_identity()["worker_source_sha256"]
    for header, session in (({"op": "status"}, None), ({"op": "recover"}, None),
                            ({"op": "records", "handle": "h_" + "A" * 22, "offset": 0,
                              "limit": 1}, SESSION), ({"op": "nope"}, None)):
        out = call(store.root, header, session=session)
        assert (out["worker_protocol"], out["worker_source_sha256"]) == (
            "sentinel.doc01.worker/0.1", digest), header


def test_a_mismatched_registered_digest_is_refused_before_any_operation(store):
    data = (FIXTURES / "csv_statement_usd.csv").read_bytes()
    out = call(store.root, {"op": "ingest", "format": "csv", "size": len(data),
                            "expect_source_sha256": "0" * 64}, data)
    assert (out["ok"], out["code"]) == (False, "identity_mismatch")
    assert list((store.root / "handles").iterdir()) == []  # nothing was ingested
    h = ingest(store, "csv_statement_usd.csv")
    out = call(store.root, {"op": "analyze", "handle": h["handle_id"], "page_limit": 5,
                            "options": {}, "expect_source_sha256": "0" * 64})
    assert out["code"] == "identity_mismatch"
    assert call(store.root, {"op": "records", "handle": h["handle_id"], "offset": 0,
                             "limit": 1})["code"] == "analysis_not_found"  # never parsed
    assert call(store.root, {"op": "status", "expect_source_sha256": "zz"},
                session=None)["code"] == "bad_header"


def test_the_matching_registered_digest_is_accepted(store):
    from docworker.extract import source_identity
    digest = source_identity()["worker_source_sha256"]
    data = (FIXTURES / "csv_statement_usd.csv").read_bytes()
    out = call(store.root, {"op": "ingest", "format": "csv", "size": len(data),
                            "expect_source_sha256": digest}, data)
    assert out["ok"] and out["worker_source_sha256"] == digest
