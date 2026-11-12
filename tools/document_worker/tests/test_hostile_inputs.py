"""Oversized, malformed and decompression-bomb inputs fail safely through the real child."""
import hashlib
import io
import json
import struct
import subprocess
import sys
import zipfile
import zlib

import pytest

from conftest import FIXTURES, SESSION, leftovers
from docworker import PROTOCOL
from docworker.limits import Limits
from docworker.supervisor import default_child_argv

sys.path.insert(0, str(FIXTURES))
import generate  # noqa: E402  (fixture builders reused for test-time inputs)


def _run(store, ingest, make_supervisor, data, fmt, limits=None):
    handle = ingest(data, fmt)
    result = make_supervisor(limits).extract(handle, SESSION)
    assert result["supervisor"]["stop"]["confirmed"] is True
    assert leftovers(store) == {"runs": [], "recovery": []}
    return result


def _codes(result):
    return [e["code"] for e in result.get("errors", [])]


def test_page_limit(store, ingest, make_supervisor):
    pages = [{"lines": [f"page {i}"]} for i in range(Limits().max_pdf_pages + 1)]
    result = _run(store, ingest, make_supervisor, generate.pdf_bytes(pages), "pdf")
    assert result["status"] == "unsupported" and "page_limit_exceeded" in _codes(result)


def test_csv_row_limit(store, ingest, make_supervisor):
    limits = Limits(max_table_rows=100)
    rows = [["Date", "Amount"]] + [["2026-01-01", "1.00"]] * 101
    result = _run(store, ingest, make_supervisor, generate.csv_bytes(rows), "csv", limits)
    assert result["status"] == "unsupported" and "row_limit_exceeded" in _codes(result)


def test_csv_field_too_large_stops_reader(store, ingest, make_supervisor):
    limits = Limits(max_field_chars=50)
    data = generate.csv_bytes([["Date", "Description", "Amount"],
                               ["2026-01-01", "ok", "1.00"],
                               ["2026-01-02", "x" * 500, "2.00"],
                               ["2026-01-03", "late", "3.00"]])
    result = _run(store, ingest, make_supervisor, data, "csv", limits)
    assert result["status"] == "partial"
    assert "csv_reader_stopped" in {f["kind"] for f in result["findings"]}
    assert [r["locator"]["row"] for r in result["records"]] == [2]


def test_csv_column_limit(store, ingest, make_supervisor):
    limits = Limits(max_columns=4)
    data = generate.csv_bytes([["Date", "Description", "Amount"],
                               ["2026-01-01", "ok", "1.00"],
                               ["2026-01-02", "a", "b", "c", "d", "e"]])
    result = _run(store, ingest, make_supervisor, data, "csv", limits)
    assert result["status"] == "partial"
    assert {u["reason"] for u in result["unparsed"]} == {"column_limit_exceeded"}


def test_non_utf8_csv_not_guessed(store, ingest, make_supervisor):
    data = "Date,Description,Amount\n2026-01-01,Café,1.00\n".encode("latin-1")
    result = _run(store, ingest, make_supervisor, data, "csv")
    assert result["status"] in ("error", "unsupported")
    assert set(_codes(result)) & {"unsupported_encoding", "content_type_mismatch"}


def test_empty_input(store, ingest, make_supervisor):
    result = _run(store, ingest, make_supervisor, b"", "pdf")
    assert result["status"] == "error" and "empty_input" in _codes(result)


def test_xlsx_member_too_large_bomb(store, ingest, make_supervisor):
    """40 MiB of zeros deflates to ~40 KiB: refused from the central directory, unexpanded."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("xl/workbook.xml", "<workbook/>")
        z.writestr("xl/worksheets/sheet1.xml", b"\0" * (40 * 1024 * 1024))
    assert len(buf.getvalue()) < 200_000
    result = _run(store, ingest, make_supervisor, buf.getvalue(), "xlsx")
    assert result["status"] == "unsupported" and "zip_member_too_large" in _codes(result)


def test_xlsx_ratio_bomb(store, ingest, make_supervisor):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("xl/workbook.xml", "<workbook/>")
        z.writestr("xl/sharedStrings.xml", b" " * (8 * 1024 * 1024))
    result = _run(store, ingest, make_supervisor, buf.getvalue(), "xlsx")
    assert result["status"] == "unsupported"
    assert "decompression_ratio_exceeded" in _codes(result)


def _lying_zip() -> bytes:
    """A real workbook whose sheet member claims 1 KiB but inflates to 30 MiB."""
    good = (FIXTURES / "xlsx_statement.xlsx").read_bytes()
    src = zipfile.ZipFile(io.BytesIO(good))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "xl/worksheets/sheet2.xml":
                data = data.replace(b"</sheetData>", b"<!--" + b"A" * (30 * 1024 * 1024)
                                    + b"--></sheetData>")
            z.writestr(info.filename, data)
    raw = bytearray(buf.getvalue())
    name = b"xl/worksheets/sheet2.xml"
    # patch the uncompressed size in both the local header and the central directory
    for sig, offset in ((b"PK\x03\x04", 22), (b"PK\x01\x02", 24)):
        start = 0
        while True:
            pos = raw.find(sig, start)
            if pos < 0:
                break
            name_len_off = 26 if sig == b"PK\x03\x04" else 28
            nlen = struct.unpack_from("<H", raw, pos + name_len_off)[0]
            name_off = pos + (30 if sig == b"PK\x03\x04" else 46)
            if raw[name_off:name_off + nlen] == name:
                struct.pack_into("<I", raw, pos + offset, 1024)
            start = pos + 4
    return bytes(raw)


def test_xlsx_lying_size_header_is_bounded(store, ingest, make_supervisor):
    data = _lying_zip()
    assert zlib  # the inflated payload exceeds the declared size; reading must stop
    result = _run(store, ingest, make_supervisor, data, "xlsx")
    assert result["status"] in ("error", "partial")
    assert result["supervisor"]["outcome"] in ("child_result",)
    if result["status"] == "partial":  # if any sheet was read, the lying one was not trusted
        assert not any(r["locator"].get("sheet") == "Transactions" for r in result["records"])


def _flate_pdf(payload: bytes) -> bytes:
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>",
            b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(payload) + payload
            + b"\nendstream"]
    body, offsets = b"%PDF-1.4\n", []
    for number, obj in enumerate(objs, start=1):
        offsets.append(len(body))
        body += b"%d 0 obj\n" % number + obj + b"\nendobj\n"
    xref = len(body)
    body += b"xref\n0 5\n0000000000 65535 f \n" + b"".join(b"%010d 00000 n \n" % o
                                                         for o in offsets)
    return body + b"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % xref


def test_pdf_flate_bomb_bounded(store, ingest, make_supervisor):
    """A ~100 KiB page stream inflating to 64 MiB of operators stays inside the bounds:
    it ends as a deadline/memory/parser error or a non-complete result, never a hang."""
    payload = zlib.compress(b"0 0 m " * (64 * 1024 * 1024 // 6), 9)
    data = _flate_pdf(payload)
    assert len(data) < 1024 * 1024
    limits = Limits(deadline_seconds=20)
    result = _run(store, ingest, make_supervisor, data, "pdf", limits)
    assert result["status"] != "complete"
    assert result["supervisor"]["elapsed_ms"] < (20 + 10) * 1000
    peak = result["supervisor"]["peak_memory_bytes"]
    if sys.platform == "win32":
        assert peak is not None and peak <= limits.memory_bytes


@pytest.mark.parametrize("header,payload,code", [
    (b"not json\n", b"", "bad_header"),
    (b"x" * 70000, b"", "bad_header"),
], ids=["not_json", "oversized_header"])
def test_child_protocol_errors(header, payload, code):
    proc = subprocess.run(default_child_argv(), input=header + payload, capture_output=True,
                          timeout=60)
    doc = json.loads(proc.stdout)
    assert proc.returncode == 2 and doc["errors"][0]["code"] == code


def _header(**over):
    data = b"Date,Amount\n2026-01-01,1.00\n"
    head = {"protocol": PROTOCOL, "request_id": "q_t", "format": "csv", "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(), "limits": {}, "options": {}}
    head.update(over)
    return (json.dumps(head) + "\n").encode(), data


@pytest.mark.parametrize("over,trim,code", [
    ({"sha256": "0" * 64}, 0, "integrity_mismatch"),
    ({}, 5, "framing_mismatch"),
    ({"size": 11 * 1024 * 1024}, 0, "input_too_large"),
    ({"options": {"decimal_style": "roman"}}, 0, "bad_options"),
    ({"limits": {"deadline_seconds": -1}}, 0, "bad_options"),
], ids=["sha", "short", "too_large", "bad_option", "bad_limit"])
def test_child_rejects_bad_requests(over, trim, code):
    header, data = _header(**over)
    proc = subprocess.run(default_child_argv(), input=header + data[:len(data) - trim],
                          capture_output=True, timeout=60)
    doc = json.loads(proc.stdout)
    assert proc.returncode == 2 and doc["errors"][0]["code"] == code
