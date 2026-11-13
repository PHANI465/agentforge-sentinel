"""Format sniffing, typed extraction and result assembly. Runs inside the bounded child.

Typed values (records, page text) come from format parsers (csv, openpyxl, pdfminer.six).
MarkItDown supplies only the bounded narrative Markdown; nothing authoritative is re-parsed
from it.
"""

from __future__ import annotations

import csv
import datetime as _dt
import hashlib
import io
import zipfile
from pathlib import Path

from . import PROTOCOL, WORKER_VERSION
from . import measures
from .limits import Limits, Options
from .tables import Cell, Collector, Layout, Unit, evidence_id, layout_unit, type_records

FORMATS = ("pdf", "csv", "xlsx")
OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
STATUSES = ("complete", "partial", "unsupported", "error")


class Rejection(Exception):
    def __init__(self, status: str, code: str, detail: str = ""):
        super().__init__(code)
        self.status, self.code, self.detail = status, code, detail


def sniff(data: bytes) -> str:
    if not data:
        return "empty"
    if b"%PDF-" in data[:1024]:
        return "pdf"
    if data.startswith(b"PK\x03\x04"):
        return "zip"
    if data.startswith(OLE_MAGIC):
        return "ole"
    if b"\x00" in data[:65536]:
        return "binary"
    try:
        data[:65536].decode("utf-8-sig")
    except UnicodeDecodeError as exc:  # a multi-byte char cut at the boundary is still text
        if exc.start < 65530:
            return "binary"
    return "text"


def source_identity() -> dict:
    here = Path(__file__).resolve().parent
    digest = hashlib.sha256()
    for path in sorted(here.glob("*.py")):
        digest.update(path.name.encode() + b"\0" + path.read_bytes() + b"\0")
    return {"worker_version": WORKER_VERSION, "worker_source_sha256": digest.hexdigest()}


def library_versions() -> dict:
    from importlib.metadata import version
    names = ("markitdown", "pdfminer.six", "pdfplumber", "openpyxl", "pandas")
    return {n: version(n) for n in names}


# ---- narrative (MarkItDown) ------------------------------------------------------------------

def narrative(data: bytes, fmt: str, limits: Limits) -> dict:
    from markitdown import StreamInfo
    from markitdown.converters import CsvConverter, PdfConverter, XlsxConverter
    converter, info = {
        "pdf": (PdfConverter, StreamInfo(extension=".pdf", mimetype="application/pdf")),
        "csv": (CsvConverter, StreamInfo(extension=".csv", mimetype="text/csv",
                                         charset="utf-8")),
        "xlsx": (XlsxConverter, StreamInfo(
            extension=".xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")),
    }[fmt]
    try:
        text = converter().convert(io.BytesIO(data), info).markdown or ""
    except Exception as exc:  # narrative is secondary; its failure is reported, not hidden
        return {"status": "failed", "error_type": type(exc).__name__, "format": "markdown",
                "text": None, "chars": 0, "truncated": False}
    truncated = len(text) > limits.max_narrative_chars
    if truncated:
        text = text[: limits.max_narrative_chars]
    return {"status": "truncated" if truncated else "ok", "format": "markdown", "text": text,
            "chars": len(text), "truncated": truncated,
            "producer": "markitdown converter called directly on owned bytes (no URI, plugins, "
                        "magika, OCR or LLM)",
            "authority": "narrative only; typed records are authoritative"}


# ---- CSV ---------------------------------------------------------------------------------------

def _csv_units(data: bytes, limits: Limits, out: Collector) -> list[Unit]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise Rejection("unsupported", "unsupported_encoding",
                        "CSV must be UTF-8; other encodings are not guessed") from None
    csv.field_size_limit(limits.max_field_chars)
    unit = Unit("csv", None)
    reader = csv.reader(io.StringIO(text, newline=""))
    rownum = 0
    try:
        for rownum, row in enumerate(reader, start=1):
            if rownum > limits.max_table_rows + 1:
                raise Rejection("unsupported", "row_limit_exceeded",
                                f"more than {limits.max_table_rows} data rows")
            if len(row) > limits.max_columns:
                out.add_unparsed({"row": rownum}, "column_limit_exceeded", ",".join(row)[:200])
                continue
            cells = [Cell("text" if v.strip() else "empty", v.strip(), column=i + 1)
                     for i, v in enumerate(row)]
            unit.rows.append((rownum, cells))
    except csv.Error as exc:
        out.add_unparsed({"row": rownum + 1}, "csv_reader_stopped", str(exc)[:200])
        out.add_finding("csv_reader_stopped", "warning",
                        "The CSV reader stopped; later rows were not read.",
                        [{"row": rownum + 1}])
        unit.reason = "reader_stopped"
    return [unit]


# ---- XLSX --------------------------------------------------------------------------------------

def _zip_precheck(data: bytes, limits: Limits, out: Collector, sha: str) -> None:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
        infos = archive.infolist()
    except (zipfile.BadZipFile, ValueError, OSError):
        raise Rejection("error", "malformed_container", "not a readable ZIP/OOXML") from None
    if len(infos) > limits.max_zip_members:
        raise Rejection("unsupported", "zip_member_limit_exceeded")
    total = 0
    names = set()
    for info in infos:
        names.add(info.filename)
        if info.flag_bits & 0x1:
            raise Rejection("unsupported", "encrypted_zip_member")
        if info.file_size > limits.max_zip_member_bytes:
            raise Rejection("unsupported", "zip_member_too_large", info.filename[:80])
        total += info.file_size
        if info.file_size > 1024 * 1024 and info.compress_size and \
                info.file_size / info.compress_size > limits.max_zip_ratio:
            raise Rejection("unsupported", "decompression_ratio_exceeded", info.filename[:80])
    if total > limits.max_zip_total_bytes:
        raise Rejection("unsupported", "zip_total_size_exceeded")
    if "[Content_Types].xml" not in names or "xl/workbook.xml" not in names:
        raise Rejection("error", "content_type_mismatch", "ZIP is not an XLSX workbook")
    try:
        ctypes_xml = archive.read("[Content_Types].xml")[:200_000].lower()
    except (zipfile.BadZipFile, OSError, RuntimeError):
        raise Rejection("error", "malformed_container") from None
    if any(n.lower().endswith("vbaproject.bin") for n in names) or b"macroenabled" in ctypes_xml:
        raise Rejection("unsupported", "macro_content",
                        "macro-enabled workbooks are refused, never executed")
    links = sorted(n for n in names if n.startswith("xl/externalLinks/"))
    for name in links:
        out.add_unparsed({"part": name}, "external_link_not_followed", name)
    if links:
        out.add_finding("external_links_present", "warning",
                        "The workbook declares external links; they were not followed and "
                        "linked values are not evidence.", [{"part": n} for n in links])


def _xlsx_cell(cell, column: int, formula: bool) -> Cell:
    value = getattr(cell, "value", None)
    if value is None:
        return Cell("empty", "", column=column, formula_uncached=formula)
    if isinstance(value, bool):
        return Cell("bool", str(value), value, column)
    if isinstance(value, (int, float)):
        return Cell("number", repr(value), value, column, cached_formula=formula)
    if isinstance(value, (_dt.datetime, _dt.date)):
        return Cell("date", value.isoformat(), value, column, cached_formula=formula)
    if isinstance(value, str):
        if getattr(cell, "data_type", None) == "e":
            return Cell("error", value, column=column, cached_formula=formula)
        stripped = value.strip()
        return Cell("text" if stripped else "empty", stripped, column=column,
                    cached_formula=formula)
    return Cell("error", type(value).__name__, column=column)


def _iter_sheet_rows(ws, limits: Limits, budget: list[int]):
    ws.reset_dimensions()  # never trust a declared dimension; avoids padding to XFD columns
    for index, row in enumerate(ws.iter_rows(), start=1):
        if index > limits.max_table_rows + 1:
            raise Rejection("unsupported", "row_limit_exceeded",
                            f"sheet has more than {limits.max_table_rows} data rows")
        if len(row) > limits.max_columns:
            yield index, None
            continue
        budget[0] += len(row)
        if budget[0] > limits.max_xlsx_cells:
            raise Rejection("unsupported", "cell_limit_exceeded")
        yield index, row


def _xlsx_units(data: bytes, limits: Limits, out: Collector) -> list[Unit]:
    import openpyxl
    _zip_precheck(data, limits, out, out.sha256)
    try:
        wb_f = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=False,
                                      keep_links=False)
        wb_v = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True,
                                      keep_links=False)
    except Rejection:
        raise
    except Exception as exc:
        raise Rejection("error", "malformed_workbook", type(exc).__name__) from None
    if len(wb_v.sheetnames) > limits.max_xlsx_sheets:
        raise Rejection("unsupported", "sheet_limit_exceeded")
    units = []
    budget = [0]
    for name in wb_v.sheetnames:
        unit = Unit("sheet", name)
        ws_v, ws_f = wb_v[name], wb_f[name]
        if getattr(ws_v, "sheet_state", "visible") != "visible":
            out.add_finding("hidden_sheet", "info",
                            "A hidden sheet was read; its content is untrusted like any other.",
                            [{"sheet": name}])
        formulas = set()
        for index, row in _iter_sheet_rows(ws_f, limits, [0]):
            for col, cell in enumerate(row or (), start=1):
                if getattr(cell, "data_type", None) == "f" or (
                        isinstance(getattr(cell, "value", None), str)
                        and cell.value.startswith("=")):
                    formulas.add((index, col))
        for index, row in _iter_sheet_rows(ws_v, limits, budget):
            if row is None:
                out.add_unparsed({"sheet": name, "row": index}, "column_limit_exceeded")
                continue
            unit.rows.append((index, [_xlsx_cell(c, col, (index, col) in formulas)
                                      for col, c in enumerate(row, start=1)]))
        units.append(unit)
    wb_f.close()
    wb_v.close()
    return units


# ---- PDF ---------------------------------------------------------------------------------------

def _pdf_pages(data: bytes, limits: Limits, out: Collector) -> tuple[list[dict], dict]:
    from pdfminer.converter import PDFPageAggregator
    from pdfminer.layout import LAParams, LTImage, LTTextContainer
    from pdfminer.pdfdocument import PDFDocument, PDFEncryptionError, PDFPasswordIncorrect
    from pdfminer.pdfinterp import PDFPageInterpreter, PDFResourceManager
    from pdfminer.pdfpage import PDFPage
    from pdfminer.pdfparser import PDFParser

    try:
        doc = PDFDocument(PDFParser(io.BytesIO(data)), password="")
    except PDFPasswordIncorrect:
        raise Rejection("unsupported", "encrypted_pdf", "a password is required") from None
    except PDFEncryptionError:
        raise Rejection("unsupported", "encrypted_pdf", "unsupported encryption") from None
    except Exception as exc:
        raise Rejection("error", "malformed_pdf", type(exc).__name__) from None
    pages = []
    try:
        for page in PDFPage.create_pages(doc):
            pages.append(page)
            if len(pages) > limits.max_pdf_pages:
                raise Rejection("unsupported", "page_limit_exceeded",
                                f"more than {limits.max_pdf_pages} pages")
    except Rejection:
        raise
    except Exception as exc:
        if not pages:
            raise Rejection("error", "malformed_pdf", type(exc).__name__) from None
        out.add_finding("page_tree_incomplete", "warning",
                        "The page tree could not be read completely; later pages are unknown.",
                        [{"page": len(pages) + 1}])
        pages_note = "incomplete"
    else:
        pages_note = "complete"
    if not pages:
        raise Rejection("unsupported", "no_pages")
    rsrc = PDFResourceManager(caching=True)
    device = PDFPageAggregator(rsrc, laparams=LAParams())
    interp = PDFPageInterpreter(rsrc, device)
    units = []

    def walk(obj, acc):
        if isinstance(obj, LTTextContainer):
            acc["text"].append(obj.get_text())
            return
        if isinstance(obj, LTImage):
            acc["images"] += 1
        for child in getattr(obj, "_objs", ()) or ():
            walk(child, acc)

    for number, page in enumerate(pages, start=1):
        loc = {"page": number}
        entry = {"evidence_id": evidence_id(out.sha256, loc), "locator": loc}
        try:
            interp.process_page(page)
            acc = {"text": [], "images": 0}
            walk(device.get_result(), acc)
        except Exception as exc:
            entry.update(status="failed", reason=f"parser_error:{type(exc).__name__}",
                         chars=0, text=None, images=None)
            units.append(entry)
            continue
        text = "".join(acc["text"]).strip()
        entry["images"] = acc["images"]
        if not text:
            if acc["images"]:
                entry.update(status="unsupported", reason="no_text_layer_image_only",
                             chars=0, text=None)
            else:
                entry.update(status="empty", reason="no_text_or_images", chars=0, text="")
        else:
            truncated = len(text) > limits.max_page_text_chars
            entry.update(status="partial" if truncated else "parsed",
                         reason="page_text_truncated" if truncated else None,
                         chars=min(len(text), limits.max_page_text_chars),
                         text=text[: limits.max_page_text_chars])
        units.append(entry)
    scanned = [u["locator"] for u in units if u["status"] == "unsupported"]
    if scanned:
        out.add_finding("pages_without_text_layer", "warning",
                        "Image-only pages are unsupported (no OCR in Part A); they are not "
                        "counted as extracted and are not empty evidence.", scanned)
    trailer_ok = b"%%EOF" in data[-1024:] and b"startxref" in data[-2048:]
    if not trailer_ok:
        out.add_finding("pdf_trailer_missing", "warning",
                        "The file does not end with a PDF trailer (truncated or appended data); "
                        "the parser may have repaired its structure, so content can be missing.",
                        [{"page": u["locator"]["page"]} for u in units][:1] or [{}])
        out.add_unparsed({"part": "trailer"}, "pdf_trailer_missing")
    meta = {"page_tree": pages_note, "trailer_present": trailer_ok,
            "encrypted": bool(getattr(doc, "encryption", None)),
            "typed_tables": "not extracted from PDF in Part A; reconciliation is not checkable"}
    return units, meta


# ---- assembly ----------------------------------------------------------------------------------

def _overall(units: list[dict], unparsed_total: int, narrative_status: str | None,
             truncated_records: int) -> tuple[str, str | None]:
    statuses = [u["status"] for u in units]
    if not statuses or all(s in ("empty",) for s in statuses):
        return "unsupported", "no_extractable_content"
    if not any(s in ("parsed", "partial") for s in statuses):
        return "unsupported", "no_unit_parsed"
    if any(s in ("partial", "unsupported", "failed") for s in statuses) or unparsed_total \
            or narrative_status not in ("ok", None) or truncated_records:
        return "partial", None
    return "complete", None


def run(data: bytes, fmt: str, sha256: str, limits: Limits, options: Options,
        with_narrative: bool = True) -> dict:
    result = {"protocol": PROTOCOL, "status": None, "format": fmt, "detected": sniff(data),
              "source": {"sha256": sha256, "size_bytes": len(data)},
              "parser": dict(source_identity(), libraries=library_versions(),
                             limits=limits.to_dict(), options=options.to_dict()),
              "units": [], "records": [], "unparsed": [], "unparsed_total": 0, "findings": [],
              "typed": None, "measures": None, "coverage": None, "narrative": None,
              "errors": []}
    out = Collector(sha256, limits)
    try:
        if fmt not in FORMATS:
            raise Rejection("unsupported", "format_not_supported", fmt)
        detected = result["detected"]
        if detected == "empty":
            raise Rejection("error", "empty_input")
        expected = {"pdf": "pdf", "xlsx": "zip", "csv": "text"}[fmt]
        if fmt == "xlsx" and detected == "ole":
            raise Rejection("unsupported", "ole_container",
                            "encrypted OOXML or legacy binary Office file; not supported")
        if detected != expected:
            raise Rejection("error", "content_type_mismatch",
                            f"declared {fmt}, content looks like {detected}")
        if fmt == "pdf":
            units, meta = _pdf_pages(data, limits, out)
            result["units"] = units
            result["typed"] = meta
            result["coverage"] = {
                "unit": "page", "units_total": len(units),
                "unit_status_counts": _counts(u["status"] for u in units),
                "text_chars": sum(u["chars"] for u in units),
                "note": "pages with a text layer; not a calibrated confidence or fidelity"}
            result["measures"] = {"reconciliation": {
                "currencies": [], "status": "not_checkable",
                "reason": "pdf_tables_not_typed_in_part_a"}}
        else:
            units = _csv_units(data, limits, out) if fmt == "csv" else \
                _xlsx_units(data, limits, out)
            layout = Layout()
            for unit in units:
                layout_unit(unit, layout, out)
                if unit.reason == "reader_stopped":
                    unit.status = "partial"
            typed = type_records(layout, options, out)
            result["typed"] = typed
            result["units"] = [{"locator": ({"sheet": u.name} if u.kind == "sheet"
                                            else {"file": "csv"}),
                                "status": u.status, "reason": u.reason,
                                "rows_non_empty": sum(1 for _n, c in u.rows
                                                      if any(x.kind != "empty" for x in c))}
                               for u in units]
            result["records"] = out.records
            result["measures"] = measures.compute(out.records)
            result["coverage"] = measures.table_coverage(result["units"], out.records,
                                                         out.unparsed_total)
        if with_narrative:
            result["narrative"] = narrative(data, fmt, limits)
        status, reason = _overall(result["units"], out.unparsed_total,
                                  result["narrative"]["status"] if result["narrative"] else None,
                                  out.truncated_records)
        result["status"] = status
        if reason:
            result["errors"].append({"code": reason, "detail": ""})
    except Rejection as rej:
        result["status"] = rej.status
        result["errors"].append({"code": rej.code, "detail": rej.detail})
    result["unparsed"] = out.unparsed
    result["unparsed_total"] = out.unparsed_total
    result["findings"] = out.findings
    return result


def _counts(values) -> dict:
    counts: dict[str, int] = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    return dict(sorted(counts.items()))
