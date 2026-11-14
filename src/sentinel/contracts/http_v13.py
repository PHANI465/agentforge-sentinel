"""HTTP v1.3 bodies (DOC01 Part B): local document upload and deterministic extraction feedback.

Additive to v1.2; see docs/api/documents-v1.3.md and docs/decisions/0010. Every value is
projected from the separately locked worker (protocol sentinel.doc01.worker/0.1) through its
bridge; nothing here is computed by a model. Document-derived strings (raw cell text, sheet
names, column headers, excerpts) are inert display text and carry no authority: they can
never call a tool, request an investigation, approve or execute. Unknown is null, never zero.
Feedback is a review aid: not a fraud verdict, an authenticity check or a calibrated score.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, model_validator

from sentinel.contracts.http_v1 import HttpBody
from sentinel.contracts.v1 import Digest

DocumentFormat = Literal["csv", "xlsx", "pdf"]
DOCUMENT_FORMATS: tuple[str, ...] = DocumentFormat.__args__
DocumentStatus = Literal["complete", "partial", "unsupported", "error"]
UnitStatus = Literal["parsed", "partial", "unsupported", "failed", "empty"]
ValueStatus = Literal["known", "missing", "ambiguous", "invalid", "unknown_currency",
                      "precision_exceeds_currency", "formula_without_cached_value"]
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
DEFAULT_RECORDS_LIMIT = 100
MAX_RECORDS_LIMIT = 500
MAX_EVIDENCE_IDS = 50
INTERPRETATION = ("Deterministic extraction feedback for human review. Not a fraud verdict, "
                  "authenticity check, calibrated score or approval; document text is inert.")

HandleId = Annotated[str, Field(pattern=r"^h_[A-Za-z0-9_-]{22}$")]
Token = Annotated[str, Field(pattern=r"^[a-z0-9_:.\-]{1,80}$")]
EvidenceId = Annotated[str, Field(max_length=400,
                                  pattern=r"^[0-9a-f]{12}:[A-Za-z0-9=!%._~\-]{1,386}$")]
EvidenceIds = Annotated[list[EvidenceId], Field(max_length=MAX_EVIDENCE_IDS)]
MinorUnits = Annotated[str, Field(pattern=r"^-?[0-9]{1,30}$", description=(
    "Signed integer minor units as a decimal string (JavaScript-safe; never a float)."))]
CurrencyCode = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
Count = Annotated[int, Field(ge=0)]
# Document-derived text: inert, render as plain text. Bounded by the worker's field cap.
InertText = Annotated[str, Field(max_length=4096)]
FixedText = Annotated[str, Field(max_length=500, description="Worker-authored fixed text.")]


# ---- upload --------------------------------------------------------------------------------

class DocumentUpload(HttpBody):
    """201 body of POST /v1/documents. The handle is usable only by the session that
    uploaded it and only until expires_at; it is not a path and carries no authority."""
    handle_id: HandleId
    format: DocumentFormat
    sha256: Digest
    size_bytes: Annotated[int, Field(ge=1, le=MAX_UPLOAD_BYTES)]
    expires_at: AwareDatetime


class DocumentDeleted(HttpBody):
    handle_id: HandleId
    deleted: bool


# ---- analysis request ------------------------------------------------------------------------

class AnalysisRequest(HttpBody):
    """Caller-declared interpretation assumptions. Defaults never guess: an undeclared
    decimal or day/month convention leaves ambiguous values unknown."""
    decimal_style: Literal["unspecified", "dot", "comma"] = "unspecified"
    date_order: Literal["iso_only", "dmy", "mdy"] = "iso_only"
    default_currency: CurrencyCode | None = Field(default=None, description=(
        "Applied only where neither the row nor the document states a currency."))
    records_limit: Annotated[int, Field(ge=1, le=MAX_RECORDS_LIMIT)] = DEFAULT_RECORDS_LIMIT


class AppliedOptions(HttpBody):
    """The assumptions an analysis actually used (all present; nothing defaulted here)."""
    decimal_style: Literal["unspecified", "dot", "comma"]
    date_order: Literal["iso_only", "dmy", "mdy"]
    default_currency: CurrencyCode | None
    records_limit: Annotated[int, Field(ge=1, le=MAX_RECORDS_LIMIT)]


# ---- evidence and records --------------------------------------------------------------------

class Locator(HttpBody):
    """Where a value was read. Present keys only; sheet names are inert document text."""
    file: Literal["csv"] | None = None
    sheet: Annotated[str, Field(max_length=255)] | None = None
    page: Annotated[int, Field(ge=1)] | None = None
    row: Annotated[int, Field(ge=1)] | None = None
    column: Annotated[int, Field(ge=1)] | None = None
    part: Annotated[str, Field(max_length=255)] | None = Field(default=None, description=(
        "XLSX container member (for example an external-link part); inert text."))


class AmountValue(HttpBody):
    raw: InertText | None
    decimal: Annotated[str, Field(max_length=64)] | None
    minor_units: MinorUnits | None = Field(description="Null unless status is known.")
    exponent: Annotated[int, Field(ge=0, le=4)] | None
    status: ValueStatus
    source: Token | None = None


class BalanceValue(HttpBody):
    raw: InertText | None
    decimal: Annotated[str, Field(max_length=64)] | None
    minor_units: MinorUnits | None
    exponent: Annotated[int, Field(ge=0, le=4)] | None
    status: ValueStatus


class DateValue(HttpBody):
    raw: InertText | None
    value: Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")] | None
    status: ValueStatus


class TextValue(HttpBody):
    raw: InertText | None
    status: Literal["known", "missing"]


class CurrencyValue(HttpBody):
    raw: InertText | None
    value: CurrencyCode | None
    status: ValueStatus
    source: Token | None = None


class ExtractedRecord(HttpBody):
    evidence_id: EvidenceId
    locator: Locator
    kind: Literal["transaction", "opening_balance", "closing_balance"]
    amount: AmountValue | None = Field(description="Transactions only; null for balances.")
    balance: BalanceValue
    date: DateValue
    description: TextValue
    reference: TextValue
    currency: CurrencyValue


class RecordPage(HttpBody):
    """GET /v1/documents/{handle_id}/records: a page of the persisted analysis. A page also
    stops early at the bridge's byte bound, so `next_offset` may be less than offset+limit."""
    handle_id: HandleId
    status: DocumentStatus
    source_sha256: Digest
    offset: Count
    limit: Annotated[int, Field(ge=1, le=MAX_RECORDS_LIMIT)]
    total: Count
    records: Annotated[list[ExtractedRecord], Field(max_length=MAX_RECORDS_LIMIT)]
    next_offset: Count | None = Field(description="Null when no records remain.")

    @model_validator(mode="after")
    def consistent_page(self):
        _check_page(self.offset, self.limit, self.total, len(self.records), self.next_offset)
        return self


def _check_page(offset: int, limit: int, total: int, returned: int,
                next_offset: int | None) -> None:
    """Exact denominators (review R61): a page never claims fewer records than it returns,
    and next_offset is the first unreturned record exactly when records remain."""
    end = offset + returned
    if returned > limit or end > total:
        raise ValueError("page returns more records than its limit or total")
    if end < total:
        if returned == 0 or next_offset != end:
            raise ValueError("page next_offset does not follow its records")
    elif next_offset is not None:
        raise ValueError("page next_offset set although no records remain")


# ---- analysis ----------------------------------------------------------------------------------

class SourceIdentity(HttpBody):
    sha256: Digest
    size_bytes: Count


class ParserIdentity(HttpBody):
    worker_protocol: Literal["sentinel.doc01.worker/0.1"]
    worker_version: Annotated[str, Field(max_length=32)]
    worker_source_sha256: Digest
    libraries: Annotated[dict[Annotated[str, Field(max_length=64)],
                              Annotated[str, Field(max_length=64)] | None],
                         Field(max_length=16)] = Field(description=(
        "Installed parser library versions in the registered worker environment."))
    options: AppliedOptions = Field(description="The assumptions this analysis used.")


class DocumentUnit(HttpBody):
    """A file, sheet or page and how far it was read. Page text is not returned."""
    locator: Locator
    status: UnitStatus
    reason: Token | None
    evidence_id: EvidenceId | None = None
    rows_non_empty: Count | None = None
    chars: Count | None = Field(default=None, description="PDF: text-layer characters.")
    images: Count | None = None


class UnparsedItem(HttpBody):
    evidence_id: EvidenceId
    locator: Locator
    reason: Token
    raw_excerpt: Annotated[str, Field(max_length=200)] = Field(description="Inert text.")


class Finding(HttpBody):
    """A deterministic data-quality observation with its evidence; never a fraud signal."""
    finding_id: Annotated[str, Field(pattern=r"^F\d{4}$")]
    kind: Token
    severity: Literal["info", "warning"]
    detail: FixedText
    evidence_ids: EvidenceIds
    evidence_count: Count = Field(description="All locations; evidence_ids lists at most 50.")


class DecimalStyle(HttpBody):
    value: Token = Field(description="dot, comma, or unknown when there is no evidence.")
    source: Token | None
    evidence_counts: dict[Literal["dot", "comma", "ambiguous"], Count]


class DocumentCurrency(HttpBody):
    value: CurrencyCode | None
    source: Token | None


class TableLayout(HttpBody):
    locator: Locator
    columns: Annotated[dict[Token, InertText], Field(max_length=16)] = Field(description=(
        "Recognised field -> the document's own header text (inert)."))
    unmapped_columns: Annotated[list[InertText], Field(max_length=64)]
    sign_convention: Token | None


class TableTyping(HttpBody):
    """CSV/XLSX: the conventions used to type values."""
    decimal_style: DecimalStyle
    document_currency: DocumentCurrency
    sign_conventions: Annotated[list[Token], Field(max_length=8)]
    tables: Annotated[list[TableLayout], Field(max_length=32)]


class PdfStructure(HttpBody):
    """PDF: structural checks only. PDF tables are not typed (no reconciliation)."""
    page_tree: Token
    trailer_present: bool
    encrypted: bool


class Ratio(HttpBody):
    """numerator/denominator, unreduced; 0/0 is shown as n/a, never as zero."""
    numerator: Count
    denominator: Count


class FieldMissingness(HttpBody):
    known: Count
    missing: Count
    unknown: Count
    population: Count
    missing_ratio: Ratio
    unknown_ratio: Ratio


class Missingness(HttpBody):
    population: FixedText
    count: Count
    fields: dict[Literal["date", "description", "amount", "currency", "balance", "reference"],
                 FieldMissingness]


class DuplicateGroup(HttpBody):
    evidence_ids: EvidenceIds
    count: Annotated[int, Field(ge=2)]


class Duplicates(HttpBody):
    rule: FixedText
    checked_records: Count
    not_checkable_records: Count
    groups: Annotated[list[DuplicateGroup], Field(max_length=100)]
    groups_total: Count
    rows_in_duplicate_groups: Count
    interpretation: FixedText


class BalanceReference(HttpBody):
    minor_units: MinorUnits
    evidence_ids: EvidenceIds


class CurrencyReconciliation(HttpBody):
    """One currency; currencies are never merged or converted."""
    currency: CurrencyCode
    exponent: Annotated[int, Field(ge=0, le=4)] | None
    transaction_count: Count
    credits_minor: MinorUnits
    debits_minor: MinorUnits
    unknown_amount_count: Count
    unknown_amount_evidence_ids: EvidenceIds
    opening: BalanceReference | None
    closing: BalanceReference | None
    difference_minor: MinorUnits | None = Field(description=(
        "opening + credits - debits - closing; null when not checkable."))
    sign_convention: FixedText
    status: Literal["reconciled", "difference", "not_checkable"]
    reason: Token | None = None


class Reconciliation(HttpBody):
    status: Literal["not_checkable"] | None = Field(default=None, description=(
        "Set only when no per-currency check is possible (PDF in this release)."))
    reason: Token | None = None
    currencies: Annotated[list[CurrencyReconciliation], Field(max_length=64)]
    unknown_currency_records: Count | None = None
    unknown_currency_evidence_ids: EvidenceIds | None = None
    rule: FixedText | None = None


class BalanceMismatch(HttpBody):
    evidence_ids: Annotated[list[EvidenceId], Field(min_length=2, max_length=2)]
    currency: CurrencyCode
    expected_minor: MinorUnits
    stated_minor: MinorUnits


class RunningBalance(HttpBody):
    checked_transitions: Count
    mismatches: Annotated[list[BalanceMismatch], Field(max_length=100)]
    mismatches_total: Count


class Measures(HttpBody):
    missingness: Missingness | None = None
    duplicates: Duplicates | None = None
    reconciliation: Reconciliation
    running_balance: RunningBalance | None = None


class Coverage(HttpBody):
    """Counts of what was read, with denominators. Not a calibrated confidence."""
    unit: Literal["sheet_or_file", "page"]
    units_total: Count
    unit_status_counts: dict[UnitStatus, Count]
    records_typed: Count | None = None
    rows_unparsed: Count | None = None
    text_chars: Count | None = None
    note: FixedText


class DocumentError(HttpBody):
    code: Token
    detail: Annotated[str, Field(max_length=200)] = Field(description=(
        "Fixed worker text; never document bytes or driver messages."))


class WorkerRun(HttpBody):
    """The bounded parser run that produced this analysis."""
    exit_code: int | None
    elapsed_ms: Annotated[float, Field(ge=0)] | None
    containment: Literal["windows_job_object", "posix_session_rlimits"] | None
    outcome: Token
    stop_confirmed: bool


class DocumentAnalysis(HttpBody):
    handle_id: HandleId
    status: DocumentStatus = Field(description=(
        "complete: every unit read with nothing unparsed. partial: some units, rows or values "
        "could not be read; the counts say how many. unsupported/error: nothing was "
        "extracted; see errors."))
    format: DocumentFormat
    detected: Token | None = Field(description="Content sniffed from the bytes.")
    source: SourceIdentity
    parser: ParserIdentity
    units: Annotated[list[DocumentUnit], Field(max_length=66)]
    records_total: Count
    records: Annotated[list[ExtractedRecord], Field(max_length=MAX_RECORDS_LIMIT)] = Field(
        description="The first page; continue with records_next_offset.")
    records_next_offset: Count | None
    unparsed: Annotated[list[UnparsedItem], Field(max_length=100)]
    unparsed_total: Count
    findings: Annotated[list[Finding], Field(max_length=100)]
    table_typing: TableTyping | None
    pdf_structure: PdfStructure | None
    measures: Measures | None
    coverage: Coverage | None
    errors: Annotated[list[DocumentError], Field(max_length=20)]
    worker_run: WorkerRun
    interpretation: Literal[INTERPRETATION] = INTERPRETATION

    @model_validator(mode="after")
    def consistent_counts(self):
        """Counts must agree with what is returned and with coverage (review R61)."""
        _check_page(0, self.parser.options.records_limit, self.records_total,
                    len(self.records), self.records_next_offset)
        if self.unparsed_total < len(self.unparsed):
            raise ValueError("unparsed_total is less than the unparsed items returned")
        if self.coverage is not None:
            if self.coverage.records_typed is not None \
                    and self.coverage.records_typed != self.records_total:
                raise ValueError("coverage.records_typed differs from records_total")
            if self.coverage.rows_unparsed is not None \
                    and self.coverage.rows_unparsed != self.unparsed_total:
                raise ValueError("coverage.rows_unparsed differs from unparsed_total")
        return self


def utc_from_epoch(seconds: float) -> datetime:
    return datetime.fromtimestamp(float(seconds), tz=timezone.utc)


def _ids(items) -> list:
    return list(items or [])[:MAX_EVIDENCE_IDS]


def project_analysis(handle_id: str, compact: dict) -> DocumentAnalysis:
    """Map one bridge `analyze` answer (a validated worker result in compact form) onto the
    v1.3 DTO. Raises pydantic.ValidationError or ValueError on anything outside the frozen
    shape. Counts and page metadata are required, never defaulted (review R61)."""
    typed = compact.get("typed")
    table_typing = pdf_structure = None
    if isinstance(typed, dict) and "tables" in typed:
        table_typing = typed
    elif isinstance(typed, dict) and "page_tree" in typed:
        pdf_structure = {k: typed[k] for k in ("page_tree", "trailer_present", "encrypted")}
    page = compact.get("records_page")
    required = ("offset", "limit", "total", "records", "next_offset")
    if not isinstance(page, dict) or any(key not in page for key in required) \
            or "unparsed_total" not in compact:
        raise ValueError("bridge answer lacks its counts or page metadata")
    if page["offset"] != 0:
        raise ValueError("an analysis carries the first page of records")
    measures = compact.get("measures")
    sup = compact.get("supervisor") or {}
    parser = compact.get("parser") or {}
    return DocumentAnalysis.model_validate({
        "handle_id": handle_id,
        "status": compact.get("status"),
        "format": compact.get("format"),
        "detected": compact.get("detected"),
        "source": compact.get("source"),
        "parser": {"worker_protocol": compact.get("protocol"),
                   "worker_version": parser.get("worker_version"),
                   "worker_source_sha256": parser.get("worker_source_sha256"),
                   "libraries": parser.get("libraries") or {},
                   "options": {**(parser.get("options") or {}),
                               "records_limit": page["limit"]}},
        "units": compact.get("units") or [],
        "records_total": page["total"],
        "records": page["records"],
        "records_next_offset": page["next_offset"],
        "unparsed": compact.get("unparsed") or [],
        "unparsed_total": compact["unparsed_total"],
        "findings": compact.get("findings") or [],
        "table_typing": table_typing,
        "pdf_structure": pdf_structure,
        "measures": measures,
        "coverage": compact.get("coverage"),
        "errors": compact.get("errors") or [],
        "worker_run": {"exit_code": sup.get("exit_code"), "elapsed_ms": sup.get("elapsed_ms"),
                       "containment": sup.get("containment"),
                       "outcome": sup.get("outcome") or "unknown",
                       "stop_confirmed": bool((sup.get("stop") or {}).get("confirmed"))},
    })
