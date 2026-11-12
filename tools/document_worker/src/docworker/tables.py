"""Typed statement-table extraction shared by CSV and XLSX.

Pipeline: (1) lay out each unit — find the header row, metadata key/value rows, balance-marker
rows and unparsed rows; (2) collect decimal-convention evidence across the whole document;
(3) type every value with an explicit status. Values are never derived from Markdown.
"""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass, field
from decimal import Decimal
from urllib.parse import quote

from . import normalize as nz
from .limits import Limits, Options

COLUMN_SYNONYMS = {
    "date": {"date", "transaction date", "posting date", "value date", "booking date"},
    "description": {"description", "details", "narrative", "memo", "payee",
                    "transaction description"},
    "amount": {"amount", "signed amount", "transaction amount"},
    "debit": {"debit", "withdrawal", "withdrawals", "money out", "paid out"},
    "credit": {"credit", "deposit", "deposits", "money in", "paid in"},
    "currency": {"currency", "ccy", "currency code"},
    "balance": {"balance", "running balance"},
    "reference": {"reference", "ref", "transaction id", "id"},
}
_HEADER_SCAN_ROWS = 10
_BALANCE_KEY = re.compile(r"^(opening|closing) balance(?:\s*\(?\s*([A-Za-z]{3})\s*\)?)?$")
_META_SIMPLE = {"currency", "account", "period start", "period end", "statement period"}
FORMULA_PREFIXES = ("=", "+", "-", "@")


@dataclass
class Cell:
    """One source cell. kind: text | number | date | empty | bool | error."""
    kind: str
    raw: str
    value: object = None
    column: int = 0           # 1-based
    formula_uncached: bool = False
    cached_formula: bool = False


@dataclass
class Unit:
    """A page (PDF), the CSV file, or one XLSX sheet."""
    kind: str                 # csv | sheet | page
    name: str | None
    rows: list[tuple[int, list[Cell]]] = field(default_factory=list)  # (1-based row, cells)
    status: str = "pending"
    reason: str | None = None


def norm_label(text: str) -> str:
    return " ".join(text.strip().lower().replace("_", " ").split())


def locator_for(unit: Unit, row: int | None = None) -> dict:
    loc: dict = {}
    if unit.kind == "sheet":
        loc["sheet"] = unit.name
    if row is not None:
        loc["row"] = row
    return loc


def evidence_id(sha256: str, loc: dict) -> str:
    parts = []
    if "sheet" in loc:
        parts.append("sheet=" + quote(str(loc["sheet"]), safe=""))
    if "page" in loc:
        parts.append(f"page={loc['page']}")
    if "row" in loc:
        parts.append(f"row={loc['row']}")
    if "column" in loc:
        parts.append(f"col={loc['column']}")
    if "part" in loc:
        parts.append("part=" + quote(str(loc["part"]), safe=""))
    return f"{sha256[:12]}:" + "!".join(parts or ["document"])


class Collector:
    """Accumulates typed output with explicit bounds."""

    def __init__(self, sha256: str, limits: Limits):
        self.sha256 = sha256
        self.limits = limits
        self.records: list[dict] = []
        self.unparsed: list[dict] = []
        self.unparsed_total = 0
        self.findings: list[dict] = []
        self.truncated_records = 0

    def bound(self, text: str) -> str:
        return text if len(text) <= self.limits.max_field_chars else (
            text[: self.limits.max_field_chars])

    def add_unparsed(self, loc: dict, reason: str, raw: str = "") -> None:
        self.unparsed_total += 1
        if len(self.unparsed) < self.limits.max_unparsed_items:
            self.unparsed.append({"evidence_id": evidence_id(self.sha256, loc), "locator": loc,
                                  "reason": reason, "raw_excerpt": raw[:200]})

    def add_finding(self, kind: str, severity: str, detail: str, locs: list[dict]) -> None:
        self.findings.append({
            "finding_id": f"F{len(self.findings) + 1:04d}", "kind": kind, "severity": severity,
            "detail": detail,
            "evidence_ids": [evidence_id(self.sha256, loc) for loc in locs[:50]],
            "evidence_count": len(locs),
        })


def _cell_text(cell: Cell | None) -> str:
    return "" if cell is None else cell.raw


def _map_header(cells: list[Cell]) -> dict[str, int] | None:
    mapping: dict[str, int] = {}
    for idx, cell in enumerate(cells):
        if cell.kind != "text":
            continue
        label = norm_label(cell.raw)
        for name, synonyms in COLUMN_SYNONYMS.items():
            if label in synonyms and name not in mapping:
                mapping[name] = idx
    has_value = "amount" in mapping or "debit" in mapping or "credit" in mapping \
        or "balance" in mapping
    return mapping if len(mapping) >= 2 and has_value else None


@dataclass
class PendingRow:
    unit: Unit
    row: int
    kind: str                       # transaction | opening_balance | closing_balance
    cells: dict[str, Cell]          # logical field -> cell
    currency_hint: str | None = None  # from a metadata key like "Opening balance (EUR)"


@dataclass
class Layout:
    pending: list[PendingRow] = field(default_factory=list)
    doc_currency_cells: list[tuple[Unit, int, Cell]] = field(default_factory=list)
    sign_conventions: set[str] = field(default_factory=set)
    tables: list[dict] = field(default_factory=list)


def _metadata_row(unit: Unit, rownum: int, cells: list[Cell], layout: Layout,
                  out: Collector) -> bool:
    non_empty = [c for c in cells if c.kind != "empty"]
    if len(non_empty) != 2 or non_empty[0].kind != "text":
        return False
    key = norm_label(non_empty[0].raw)
    value = non_empty[1]
    match = _BALANCE_KEY.match(key)
    if match:
        kind = f"{match.group(1)}_balance"
        layout.pending.append(PendingRow(unit, rownum, kind, {"balance": value},
                                         currency_hint=(match.group(2) or "").upper() or None))
        return True
    if key == "currency":
        layout.doc_currency_cells.append((unit, rownum, value))
        return True
    if key in _META_SIMPLE:
        return True
    return False


def layout_unit(unit: Unit, layout: Layout, out: Collector) -> None:
    """Classify the rows of one tabular unit; sets unit.status."""
    rows = [(n, cells) for n, cells in unit.rows if any(c.kind != "empty" for c in cells)]
    if not rows:
        unit.status, unit.reason = "empty", "no_non_empty_rows"
        return
    header_at = None
    mapping = None
    for i, (_n, cells) in enumerate(rows[:_HEADER_SCAN_ROWS]):
        mapping = _map_header(cells)
        if mapping:
            header_at = i
            break
    unparsed_here = 0
    meta_rows = rows if header_at is None else rows[:header_at]
    for rownum, cells in meta_rows:
        if not _metadata_row(unit, rownum, cells, layout, out):
            out.add_unparsed(locator_for(unit, rownum), "unrecognised_row",
                             " | ".join(c.raw for c in cells if c.kind != "empty"))
            unparsed_here += 1
    if header_at is None:
        recognised = len(meta_rows) - unparsed_here
        if recognised == 0:
            unit.status, unit.reason = "unsupported", "no_recognised_table_or_metadata"
        else:
            unit.status = "partial" if unparsed_here else "parsed"
            unit.reason = "metadata_only"
        return
    header_row, header_cells = rows[header_at]
    width = len(header_cells)
    mapped_cols = set(mapping.values())
    unmapped = [c.raw for i, c in enumerate(header_cells)
                if i not in mapped_cols and c.kind != "empty"]
    convention = "signed_amount_column" if "amount" in mapping else "debit_credit_columns"
    layout.sign_conventions.add(convention)
    layout.tables.append({"locator": locator_for(unit, header_row),
                          "columns": {k: header_cells[v].raw for k, v in sorted(mapping.items())},
                          "unmapped_columns": unmapped, "sign_convention": convention})
    if unmapped:
        out.add_finding("unmapped_columns", "info",
                        "Columns without a recognised meaning are kept only as raw text: "
                        + ", ".join(u[:40] for u in unmapped[:10]),
                        [locator_for(unit, header_row)])
    for rownum, cells in rows[header_at + 1:]:
        extra = [c for c in cells[width:] if c.kind != "empty"]
        if extra:
            out.add_unparsed(locator_for(unit, rownum), "column_count_mismatch",
                             " | ".join(c.raw for c in cells))
            unparsed_here += 1
            continue
        fields = {name: cells[idx] for name, idx in mapping.items() if idx < len(cells)}
        desc = norm_label(_cell_text(fields.get("description")))
        has_amount = any(fields.get(k) is not None and fields[k].kind != "empty"
                         for k in ("amount", "debit", "credit"))
        kind = "transaction"
        if desc in ("opening balance", "closing balance") and not has_amount:
            kind = desc.replace(" ", "_")
        layout.pending.append(PendingRow(unit, rownum, kind, fields))
    unit.status = "partial" if unparsed_here else "parsed"


# ---- typing ---------------------------------------------------------------------------------

_AMOUNT_FIELDS = ("amount", "debit", "credit", "balance")


def decide_style(layout: Layout, options: Options, out: Collector) -> tuple[str, dict]:
    """Effective decimal style for text amounts: 'dot', 'comma' or 'unknown'."""
    seen: dict[str, list[dict]] = {"dot": [], "comma": [], "ambiguous": []}
    for p in layout.pending:
        for name in _AMOUNT_FIELDS:
            cell = p.cells.get(name)
            if cell is not None and cell.kind == "text":
                style = nz.text_amount_style(cell.raw)
                if style:
                    seen[style].append(locator_for(p.unit, p.row))
    counts = {k: len(v) for k, v in seen.items()}
    if options.decimal_style != "unspecified":
        effective, source = options.decimal_style, "declared"
        other = "comma" if effective == "dot" else "dot"
        if seen[other]:
            out.add_finding("decimal_convention_contradiction", "warning",
                            f"{len(seen[other])} amount(s) contradict the declared "
                            f"{effective}-decimal convention; they are left unknown.",
                            seen[other])
    elif seen["dot"] and seen["comma"]:
        effective, source = "unknown", "conflicting"
        out.add_finding("conflicting_decimal_conventions", "warning",
                        "Both 1,234.56-style and 1.234,56-style amounts appear; every amount "
                        "with a separator is left unknown until a convention is confirmed.",
                        seen["dot"][:25] + seen["comma"][:25])
    elif seen["dot"] or seen["comma"]:
        effective = "dot" if seen["dot"] else "comma"
        source = "inferred_from_unambiguous_tokens"
    else:
        effective, source = "unknown", "no_evidence"
    if seen["ambiguous"] and options.decimal_style == "unspecified":
        out.add_finding("ambiguous_amount_grouping", "warning",
                        "Amounts like 1,234 or 1.234 depend on an undeclared convention and "
                        "are left unknown.", seen["ambiguous"])
    return effective, {"value": effective, "source": source, "evidence_counts": counts}


def _type_amount(cell: Cell | None, style: str, declared: bool, currency: str | None) -> dict:
    out = {"raw": None, "decimal": None, "minor_units": None, "exponent": None,
           "status": nz.MISSING}
    if cell is None or cell.kind == "empty":
        if cell is not None and cell.formula_uncached:
            out["status"] = nz.FORMULA_NO_VALUE
        return out
    out["raw"] = cell.raw
    if cell.kind == "number":
        value, status = nz.decimal_from_cell_number(cell.value), nz.KNOWN
    elif cell.kind == "text":
        evidence = nz.text_amount_style(cell.raw)
        if evidence == "ambiguous" and not declared:
            value, status = None, nz.AMBIGUOUS
        else:
            value, status = nz.parse_text_amount(cell.raw, style)
    else:
        value, status = None, nz.INVALID
    if status != nz.KNOWN:
        out["status"] = status
        return out
    out["decimal"] = str(value)
    minor, exponent, mstatus = nz.to_minor_units(value, currency)
    out.update(minor_units=minor, exponent=exponent, status=mstatus)
    return out


def _signed_from_debit_credit(debit: dict, credit: dict, currency: str | None) -> dict:
    """Signed amount = credit − debit, from two non-negative columns."""
    raw = " / ".join(str(p["raw"]) for p in (debit, credit) if p["raw"] is not None) or None
    for part in (debit, credit):
        if part["decimal"] is None and part["status"] != nz.MISSING:
            return dict(part, raw=raw, source="debit_credit")  # ambiguous/invalid/formula
    d = Decimal(debit["decimal"]) if debit["decimal"] is not None else None
    c = Decimal(credit["decimal"]) if credit["decimal"] is not None else None
    ambiguous = dict(debit, raw=raw, decimal=None, minor_units=None, status=nz.AMBIGUOUS,
                     source="debit_credit")
    if d is None and c is None:
        return dict(debit, raw=raw, source="debit_credit")
    if (d is not None and c is not None and d != 0 and c != 0) or (d is not None and d < 0) \
            or (c is not None and c < 0):
        return ambiguous
    if d is not None and (d != 0 or c is None):
        value, source = -d, "debit"
    else:
        value, source = c, "credit"
    minor, exponent, status = nz.to_minor_units(value, currency)
    return {"raw": raw, "decimal": str(value), "minor_units": minor, "exponent": exponent,
            "status": status, "source": source}


def _type_date(cell: Cell | None, options: Options) -> dict:
    if cell is None or cell.kind == "empty":
        status = nz.FORMULA_NO_VALUE if cell is not None and cell.formula_uncached else nz.MISSING
        return {"raw": None, "value": None, "status": status}
    if cell.kind == "date":
        value = cell.value.date() if isinstance(cell.value, _dt.datetime) else cell.value
        return {"raw": cell.raw, "value": value.isoformat(), "status": nz.KNOWN}
    if cell.kind == "text":
        value, status = nz.parse_text_date(cell.raw, options.date_order)
        return {"raw": cell.raw, "value": value, "status": status}
    return {"raw": cell.raw, "value": None, "status": nz.INVALID}


def type_records(layout: Layout, options: Options, out: Collector) -> dict:
    style, style_info = decide_style(layout, options, out)
    declared = options.decimal_style != "unspecified"
    doc_currency = None
    doc_currency_source = None
    codes = set()
    for unit, rownum, cell in layout.doc_currency_cells:
        code, status = nz.normalize_currency(cell.raw)
        if code:
            codes.add(code)
    if len(codes) == 1:
        doc_currency, doc_currency_source = codes.pop(), "document"
    elif len(codes) > 1:
        out.add_finding("conflicting_document_currency", "warning",
                        "More than one document-level currency is stated; none is applied.",
                        [locator_for(u, r) for u, r, _c in layout.doc_currency_cells])
    if doc_currency is None and options.default_currency:
        doc_currency, doc_currency_source = options.default_currency, "option"
    formula_locs, ambiguous_dates = [], []
    for p in layout.pending:
        if len(out.records) >= out.limits.max_records:
            out.truncated_records += 1
            out.add_unparsed(locator_for(p.unit, p.row), "record_limit")
            continue
        loc = locator_for(p.unit, p.row)
        ccell = p.cells.get("currency")
        if ccell is not None and ccell.kind != "empty":
            code, cstatus = nz.normalize_currency(ccell.raw)
            currency = {"raw": ccell.raw, "value": code, "status": cstatus, "source": "row"}
        elif p.currency_hint:
            code, cstatus = nz.normalize_currency(p.currency_hint)
            currency = {"raw": p.currency_hint, "value": code, "status": cstatus,
                        "source": "metadata_key"}
        elif doc_currency:
            currency = {"raw": None, "value": doc_currency,
                        "status": nz.KNOWN if doc_currency in nz.CURRENCY_EXPONENTS
                        else nz.UNKNOWN_CURRENCY, "source": doc_currency_source}
        else:
            currency = {"raw": None, "value": None, "status": nz.MISSING, "source": None}
        code = currency["value"]
        record = {"evidence_id": evidence_id(out.sha256, loc), "locator": loc, "kind": p.kind}
        if p.kind == "transaction":
            if "amount" in p.cells:
                amount = dict(_type_amount(p.cells.get("amount"), style, declared, code),
                              source="amount")
            else:
                amount = _signed_from_debit_credit(
                    _type_amount(p.cells.get("debit"), style, declared, code),
                    _type_amount(p.cells.get("credit"), style, declared, code), code)
            record["amount"] = amount
        else:
            src = p.cells.get("balance")
            if src is None or src.kind == "empty":
                src = p.cells.get("amount") or p.cells.get("credit")
            record["amount"] = None
        balance_cell = p.cells.get("balance") if p.kind == "transaction" else src
        record["balance"] = _type_amount(balance_cell, style, declared, code)
        record["date"] = _type_date(p.cells.get("date"), options)
        for name in ("description", "reference"):
            cell = p.cells.get(name)
            raw = None if cell is None or cell.kind == "empty" else out.bound(cell.raw)
            record[name] = {"raw": raw, "status": nz.KNOWN if raw else nz.MISSING}
        record["currency"] = currency
        for cell in p.cells.values():
            if cell.formula_uncached or cell.cached_formula:
                formula_locs.append(dict(loc, column=cell.column))
        if record["date"]["status"] == nz.AMBIGUOUS:
            ambiguous_dates.append(loc)
        desc = record["description"]["raw"] or ""
        if desc.startswith(FORMULA_PREFIXES) and not nz.text_amount_style(desc):
            out.add_finding("formula_like_text", "info",
                            "Description begins with a spreadsheet formula character; it was "
                            "stored as inert text and was not evaluated.", [loc])
        out.records.append(record)
    if formula_locs:
        out.add_finding("formula_cells", "info",
                        "Formula cells use the workbook's cached value when present (not "
                        "recomputed); formulas without a cached value are unknown.",
                        formula_locs)
    if ambiguous_dates:
        out.add_finding("date_order_not_declared", "warning",
                        "Non-ISO dates need a declared day/month order; they are left unknown.",
                        ambiguous_dates)
    return {"decimal_style": style_info,
            "document_currency": {"value": doc_currency, "source": doc_currency_source},
            "sign_conventions": sorted(layout.sign_conventions),
            "tables": layout.tables}
