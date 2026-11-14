/**
 * DOC01 Part C: the v1.3 document routes (accepted contract, docs/api/documents-v1.3.md;
 * OpenAPI contracts/http/openapi.v1.3.json at 813b0db, SHA-256 d4306c65…).
 *
 * Strict parsing: a required field that is missing or of the wrong type, or a count that
 * contradicts what was returned, makes the whole response "unconfirmed". It never becomes
 * an empty report. Document-derived strings are returned as plain data for inert text
 * rendering only. Money stays as integer minor-unit strings; nothing is converted.
 */

export type DocumentFormat = "csv" | "xlsx" | "pdf";
export const DOCUMENT_FORMATS: readonly DocumentFormat[] = ["csv", "xlsx", "pdf"];
export const DOCUMENT_MEDIA: Record<DocumentFormat, string> = {
  csv: "text/csv",
  xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  pdf: "application/pdf",
};
export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
export const DEFAULT_RECORDS_LIMIT = 100;
export const MAX_RECORDS_LIMIT = 500;
export const INTERPRETATION =
  "Deterministic extraction feedback for human review. Not a fraud verdict, authenticity check, " +
  "calibrated score or approval; document text is inert.";

export type DocumentStatus = "complete" | "partial" | "unsupported" | "error";
export type UnitStatus = "parsed" | "partial" | "unsupported" | "failed" | "empty";
export type ValueStatus =
  | "known"
  | "missing"
  | "ambiguous"
  | "invalid"
  | "unknown_currency"
  | "precision_exceeds_currency"
  | "formula_without_cached_value";

export interface DocumentUpload {
  handle_id: string;
  format: DocumentFormat;
  sha256: string;
  size_bytes: number;
  expires_at: string;
}

export interface Locator {
  file: "csv" | null;
  sheet: string | null;
  page: number | null;
  row: number | null;
  column: number | null;
  part: string | null;
}

export interface AmountValue {
  raw: string | null;
  decimal: string | null;
  minor_units: string | null;
  exponent: number | null;
  status: ValueStatus;
  source: string | null;
}

export interface BalanceValue {
  raw: string | null;
  decimal: string | null;
  minor_units: string | null;
  exponent: number | null;
  status: ValueStatus;
}

export interface DateValue {
  raw: string | null;
  value: string | null;
  status: ValueStatus;
}

export interface TextValue {
  raw: string | null;
  status: "known" | "missing";
}

export interface CurrencyValue {
  raw: string | null;
  value: string | null;
  status: ValueStatus;
  source: string | null;
}

export interface ExtractedRecord {
  evidence_id: string;
  locator: Locator;
  kind: "transaction" | "opening_balance" | "closing_balance";
  amount: AmountValue | null;
  balance: BalanceValue;
  date: DateValue;
  description: TextValue;
  reference: TextValue;
  currency: CurrencyValue;
}

export interface RecordPage {
  handle_id: string;
  status: DocumentStatus;
  source_sha256: string;
  offset: number;
  limit: number;
  total: number;
  records: ExtractedRecord[];
  next_offset: number | null;
}

export interface AppliedOptions {
  decimal_style: "unspecified" | "dot" | "comma";
  date_order: "iso_only" | "dmy" | "mdy";
  default_currency: string | null;
  records_limit: number;
}

export interface DocumentUnit {
  locator: Locator;
  status: UnitStatus;
  reason: string | null;
  evidence_id: string | null;
  rows_non_empty: number | null;
  chars: number | null;
  images: number | null;
}

export interface UnparsedItem {
  evidence_id: string;
  locator: Locator;
  reason: string;
  raw_excerpt: string;
}

export interface Finding {
  finding_id: string;
  kind: string;
  severity: "info" | "warning";
  detail: string;
  evidence_ids: string[];
  evidence_count: number;
}

export interface Ratio {
  numerator: number;
  denominator: number;
}

export interface FieldMissingness {
  known: number;
  missing: number;
  unknown: number;
  population: number;
  missing_ratio: Ratio;
  unknown_ratio: Ratio;
}

export interface CurrencyReconciliation {
  currency: string;
  exponent: number | null;
  transaction_count: number;
  credits_minor: string;
  debits_minor: string;
  unknown_amount_count: number;
  unknown_amount_evidence_ids: string[];
  opening: { minor_units: string; evidence_ids: string[] } | null;
  closing: { minor_units: string; evidence_ids: string[] } | null;
  difference_minor: string | null;
  sign_convention: string;
  status: "reconciled" | "difference" | "not_checkable";
  reason: string | null;
}

export interface Measures {
  missingness: {
    population: string;
    count: number;
    fields: Partial<Record<MissingnessField, FieldMissingness>>;
  } | null;
  duplicates: {
    rule: string;
    checked_records: number;
    not_checkable_records: number;
    groups: { evidence_ids: string[]; count: number }[];
    groups_total: number;
    rows_in_duplicate_groups: number;
    interpretation: string;
  } | null;
  reconciliation: {
    status: "not_checkable" | null;
    reason: string | null;
    currencies: CurrencyReconciliation[];
    unknown_currency_records: number | null;
    unknown_currency_evidence_ids: string[] | null;
    rule: string | null;
  };
  running_balance: {
    checked_transitions: number;
    mismatches: { evidence_ids: string[]; currency: string; expected_minor: string; stated_minor: string }[];
    mismatches_total: number;
  } | null;
}

export type MissingnessField = "date" | "description" | "amount" | "currency" | "balance" | "reference";

export interface DocumentAnalysis {
  handle_id: string;
  status: DocumentStatus;
  format: DocumentFormat;
  detected: string | null;
  source: { sha256: string; size_bytes: number };
  parser: {
    worker_protocol: string;
    worker_version: string;
    worker_source_sha256: string;
    libraries: Record<string, string | null>;
    options: AppliedOptions;
  };
  units: DocumentUnit[];
  records_total: number;
  records: ExtractedRecord[];
  records_next_offset: number | null;
  unparsed: UnparsedItem[];
  unparsed_total: number;
  findings: Finding[];
  table_typing: {
    decimal_style: { value: string; source: string | null; evidence_counts: Record<string, number> };
    document_currency: { value: string | null; source: string | null };
    sign_conventions: string[];
    tables: { locator: Locator; columns: Record<string, string>; unmapped_columns: string[]; sign_convention: string | null }[];
  } | null;
  pdf_structure: { page_tree: string; trailer_present: boolean; encrypted: boolean } | null;
  measures: Measures | null;
  coverage: {
    unit: "sheet_or_file" | "page";
    units_total: number;
    unit_status_counts: Partial<Record<UnitStatus, number>>;
    records_typed: number | null;
    rows_unparsed: number | null;
    text_chars: number | null;
    note: string;
  } | null;
  errors: { code: string; detail: string }[];
  worker_run: {
    exit_code: number | null;
    elapsed_ms: number | null;
    containment: "windows_job_object" | "posix_session_rlimits" | null;
    outcome: string;
    stop_confirmed: boolean;
  };
  interpretation: string;
}

export interface DocumentDeleted {
  handle_id: string;
  deleted: boolean;
}

export interface AnalysisRequest {
  decimal_style: AppliedOptions["decimal_style"];
  date_order: AppliedOptions["date_order"];
  default_currency: string | null;
  records_limit: number;
}

// ---- strict parsing ---------------------------------------------------------------------------

class Reject extends Error {}

function fail(): never {
  throw new Reject();
}

const HANDLE = /^h_[A-Za-z0-9_-]{22}$/;
const DIGEST = /^[0-9a-f]{64}$/;
const TOKEN = /^[a-z0-9_:.-]{1,80}$/;
const EVIDENCE = /^[0-9a-f]{12}:[A-Za-z0-9=!%._~-]{1,386}$/;
const MINOR = /^-?[0-9]{1,30}$/;
const CURRENCY = /^[A-Z]{3}$/;
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
const VALUE_STATUSES: readonly ValueStatus[] = [
  "known", "missing", "ambiguous", "invalid", "unknown_currency",
  "precision_exceeds_currency", "formula_without_cached_value",
];
const UNIT_STATUSES: readonly UnitStatus[] = ["parsed", "partial", "unsupported", "failed", "empty"];
const MISSINGNESS_FIELDS: readonly MissingnessField[] = [
  "date", "description", "amount", "currency", "balance", "reference",
];

function record(value: unknown): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) fail();
  return value as Record<string, unknown>;
}

function has(obj: Record<string, unknown>, key: string): unknown {
  if (!(key in obj)) fail(); // required: absent is never defaulted
  return obj[key];
}

function str(value: unknown, max = 100_000): string {
  if (typeof value !== "string" || value.length > max) fail();
  return value;
}

function nstr(value: unknown, max = 100_000): string | null {
  return value === null ? null : str(value, max);
}

function match(value: unknown, pattern: RegExp): string {
  const text = str(value);
  if (!pattern.test(text)) fail();
  return text;
}

function nmatch(value: unknown, pattern: RegExp): string | null {
  return value === null ? null : match(value, pattern);
}

function count(value: unknown): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 0) fail();
  return value;
}

function ncount(value: unknown): number | null {
  return value === null ? null : count(value);
}

function int(value: unknown): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value)) fail();
  return value;
}

function bool(value: unknown): boolean {
  if (typeof value !== "boolean") fail();
  return value;
}

function oneOf<T extends string>(value: unknown, options: readonly T[]): T {
  if (typeof value !== "string" || !options.includes(value as T)) fail();
  return value as T;
}

function list<T>(value: unknown, item: (entry: unknown) => T, max: number): T[] {
  if (!Array.isArray(value) || value.length > max) fail();
  return value.map(item);
}

function optional(obj: Record<string, unknown>, key: string): unknown {
  return key in obj ? obj[key] : null; // fields the contract defaults to null
}

function locator(value: unknown): Locator {
  const obj = record(value);
  const file = optional(obj, "file");
  if (file !== null && file !== "csv") fail();
  const position = (key: string) => {
    const raw = optional(obj, key);
    if (raw === null) return null;
    const n = count(raw);
    if (n < 1) fail();
    return n;
  };
  return {
    file: file as "csv" | null,
    sheet: nstr(optional(obj, "sheet"), 255),
    page: position("page"),
    row: position("row"),
    column: position("column"),
    part: nstr(optional(obj, "part"), 255),
  };
}

function evidenceIds(value: unknown, max = 50): string[] {
  return list(value, (entry) => match(entry, EVIDENCE), max);
}

/** Known value <=> a value is present (null otherwise); money is an integer string. */
function money(obj: Record<string, unknown>, status: ValueStatus): string | null {
  const minor = nmatch(has(obj, "minor_units"), MINOR);
  if ((status === "known") !== (minor !== null)) fail();
  return minor;
}

function exponent(value: unknown): number | null {
  if (value === null) return null;
  const n = count(value);
  if (n > 4) fail();
  return n;
}

function amount(value: unknown): AmountValue {
  const obj = record(value);
  const status = oneOf(has(obj, "status"), VALUE_STATUSES);
  return {
    raw: nstr(has(obj, "raw"), 4096),
    decimal: nstr(has(obj, "decimal"), 64),
    minor_units: money(obj, status),
    exponent: exponent(has(obj, "exponent")),
    status,
    source: nmatch(optional(obj, "source"), TOKEN),
  };
}

function balance(value: unknown): BalanceValue {
  const obj = record(value);
  const status = oneOf(has(obj, "status"), VALUE_STATUSES);
  return {
    raw: nstr(has(obj, "raw"), 4096),
    decimal: nstr(has(obj, "decimal"), 64),
    minor_units: money(obj, status),
    exponent: exponent(has(obj, "exponent")),
    status,
  };
}

function dateValue(value: unknown): DateValue {
  const obj = record(value);
  const status = oneOf(has(obj, "status"), VALUE_STATUSES);
  const iso = nmatch(has(obj, "value"), ISO_DATE);
  if ((status === "known") !== (iso !== null)) fail();
  return { raw: nstr(has(obj, "raw"), 4096), value: iso, status };
}

function textValue(value: unknown): TextValue {
  const obj = record(value);
  return { raw: nstr(has(obj, "raw"), 4096), status: oneOf(has(obj, "status"), ["known", "missing"] as const) };
}

function currencyValue(value: unknown): CurrencyValue {
  const obj = record(value);
  const status = oneOf(has(obj, "status"), VALUE_STATUSES);
  const code = nmatch(has(obj, "value"), CURRENCY);
  if ((status === "known") !== (code !== null)) fail();
  return { raw: nstr(has(obj, "raw"), 4096), value: code, status, source: nmatch(optional(obj, "source"), TOKEN) };
}

function extracted(value: unknown): ExtractedRecord {
  const obj = record(value);
  const kind = oneOf(has(obj, "kind"), ["transaction", "opening_balance", "closing_balance"] as const);
  const amountRaw = has(obj, "amount");
  if ((kind === "transaction") !== (amountRaw !== null)) fail();
  return {
    evidence_id: match(has(obj, "evidence_id"), EVIDENCE),
    locator: locator(has(obj, "locator")),
    kind,
    amount: amountRaw === null ? null : amount(amountRaw),
    balance: balance(has(obj, "balance")),
    date: dateValue(has(obj, "date")),
    description: textValue(has(obj, "description")),
    reference: textValue(has(obj, "reference")),
    currency: currencyValue(has(obj, "currency")),
  };
}

/** The same page rule the server enforces: next_offset follows the returned records exactly. */
function checkPage(offset: number, limit: number, total: number, returned: number, next: number | null): void {
  const end = offset + returned;
  if (returned > limit || end > total) fail();
  if (end < total) {
    if (returned === 0 || next !== end) fail();
  } else if (next !== null) {
    fail();
  }
}

function ratio(value: unknown, numerator: number, denominator: number): Ratio {
  const obj = record(value);
  const r = { numerator: count(has(obj, "numerator")), denominator: count(has(obj, "denominator")) };
  if (r.numerator !== numerator || r.denominator !== denominator) fail(); // exact, unreduced
  return r;
}

function missingness(value: unknown): Measures["missingness"] {
  if (value === null) return null;
  const obj = record(value);
  const fieldsObj = record(has(obj, "fields"));
  const fields: Partial<Record<MissingnessField, FieldMissingness>> = {};
  for (const [name, entry] of Object.entries(fieldsObj)) {
    const field = oneOf(name, MISSINGNESS_FIELDS);
    const f = record(entry);
    const known = count(has(f, "known"));
    const missing = count(has(f, "missing"));
    const unknown = count(has(f, "unknown"));
    const population = count(has(f, "population"));
    if (known + missing + unknown !== population) fail();
    fields[field] = {
      known, missing, unknown, population,
      missing_ratio: ratio(has(f, "missing_ratio"), missing, population),
      unknown_ratio: ratio(has(f, "unknown_ratio"), unknown, population),
    };
  }
  return { population: str(has(obj, "population"), 500), count: count(has(obj, "count")), fields };
}

function balanceRef(value: unknown): { minor_units: string; evidence_ids: string[] } | null {
  if (value === null) return null;
  const obj = record(value);
  return { minor_units: match(has(obj, "minor_units"), MINOR), evidence_ids: evidenceIds(has(obj, "evidence_ids")) };
}

function reconciliationCurrency(value: unknown): CurrencyReconciliation {
  const obj = record(value);
  const status = oneOf(has(obj, "status"), ["reconciled", "difference", "not_checkable"] as const);
  const entry: CurrencyReconciliation = {
    currency: match(has(obj, "currency"), CURRENCY),
    exponent: exponent(has(obj, "exponent")),
    transaction_count: count(has(obj, "transaction_count")),
    credits_minor: match(has(obj, "credits_minor"), MINOR),
    debits_minor: match(has(obj, "debits_minor"), MINOR),
    unknown_amount_count: count(has(obj, "unknown_amount_count")),
    unknown_amount_evidence_ids: evidenceIds(has(obj, "unknown_amount_evidence_ids")),
    opening: balanceRef(has(obj, "opening")),
    closing: balanceRef(has(obj, "closing")),
    difference_minor: nmatch(has(obj, "difference_minor"), MINOR),
    sign_convention: str(has(obj, "sign_convention"), 500),
    status,
    reason: nmatch(optional(obj, "reason"), TOKEN),
  };
  if (status === "not_checkable") {
    if (entry.difference_minor !== null) fail();
  } else {
    // Recompute exactly (BigInt): opening + credits - debits - closing.
    if (!entry.opening || !entry.closing || entry.difference_minor === null) fail();
    const diff =
      BigInt(entry.opening.minor_units) + BigInt(entry.credits_minor) -
      BigInt(entry.debits_minor) - BigInt(entry.closing.minor_units);
    if (diff.toString() !== entry.difference_minor) fail();
    if ((diff === 0n) !== (status === "reconciled")) fail();
  }
  return entry;
}

function measures(value: unknown): Measures | null {
  if (value === null) return null;
  const obj = record(value);
  const dupRaw = optional(obj, "duplicates");
  const rbRaw = optional(obj, "running_balance");
  const rec = record(has(obj, "reconciliation"));
  const reconStatus = optional(rec, "status");
  if (reconStatus !== null && reconStatus !== "not_checkable") fail();
  const ids = optional(rec, "unknown_currency_evidence_ids");
  return {
    missingness: missingness(optional(obj, "missingness")),
    duplicates: dupRaw === null ? null : (() => {
      const d = record(dupRaw);
      const groups = list(has(d, "groups"), (g) => {
        const group = record(g);
        const n = count(has(group, "count"));
        if (n < 2) fail();
        return { evidence_ids: evidenceIds(has(group, "evidence_ids")), count: n };
      }, 100);
      const total = count(has(d, "groups_total"));
      if (total < groups.length) fail();
      return {
        rule: str(has(d, "rule"), 500),
        checked_records: count(has(d, "checked_records")),
        not_checkable_records: count(has(d, "not_checkable_records")),
        groups,
        groups_total: total,
        rows_in_duplicate_groups: count(has(d, "rows_in_duplicate_groups")),
        interpretation: str(has(d, "interpretation"), 500),
      };
    })(),
    reconciliation: {
      status: reconStatus as "not_checkable" | null,
      reason: nmatch(optional(rec, "reason"), TOKEN),
      currencies: list(has(rec, "currencies"), reconciliationCurrency, 64),
      unknown_currency_records: ncount(optional(rec, "unknown_currency_records")),
      unknown_currency_evidence_ids: ids === null ? null : evidenceIds(ids),
      rule: nstr(optional(rec, "rule"), 500),
    },
    running_balance: rbRaw === null ? null : (() => {
      const r = record(rbRaw);
      const mismatches = list(has(r, "mismatches"), (m) => {
        const item = record(m);
        const ids2 = evidenceIds(has(item, "evidence_ids"), 2);
        if (ids2.length !== 2) fail();
        return {
          evidence_ids: ids2,
          currency: match(has(item, "currency"), CURRENCY),
          expected_minor: match(has(item, "expected_minor"), MINOR),
          stated_minor: match(has(item, "stated_minor"), MINOR),
        };
      }, 100);
      const total = count(has(r, "mismatches_total"));
      if (total < mismatches.length) fail();
      return { checked_transitions: count(has(r, "checked_transitions")), mismatches, mismatches_total: total };
    })(),
  };
}

function unit(value: unknown): DocumentUnit {
  const obj = record(value);
  return {
    locator: locator(has(obj, "locator")),
    status: oneOf(has(obj, "status"), UNIT_STATUSES),
    reason: nmatch(has(obj, "reason"), TOKEN),
    evidence_id: nmatch(optional(obj, "evidence_id"), EVIDENCE),
    rows_non_empty: ncount(optional(obj, "rows_non_empty")),
    chars: ncount(optional(obj, "chars")),
    images: ncount(optional(obj, "images")),
  };
}

function finding(value: unknown): Finding {
  const obj = record(value);
  const ids = evidenceIds(has(obj, "evidence_ids"));
  const total = count(has(obj, "evidence_count"));
  if (total < ids.length) fail();
  return {
    finding_id: match(has(obj, "finding_id"), /^F\d{4}$/),
    kind: match(has(obj, "kind"), TOKEN),
    severity: oneOf(has(obj, "severity"), ["info", "warning"] as const),
    detail: str(has(obj, "detail"), 500),
    evidence_ids: ids,
    evidence_count: total,
  };
}

function options(value: unknown): AppliedOptions {
  const obj = record(value);
  const limit = count(has(obj, "records_limit"));
  if (limit < 1 || limit > MAX_RECORDS_LIMIT) fail();
  return {
    decimal_style: oneOf(has(obj, "decimal_style"), ["unspecified", "dot", "comma"] as const),
    date_order: oneOf(has(obj, "date_order"), ["iso_only", "dmy", "mdy"] as const),
    default_currency: nmatch(has(obj, "default_currency"), CURRENCY),
    records_limit: limit,
  };
}

function tableTyping(value: unknown): DocumentAnalysis["table_typing"] {
  if (value === null) return null;
  const obj = record(value);
  const ds = record(has(obj, "decimal_style"));
  const counts = record(has(ds, "evidence_counts"));
  const evidence: Record<string, number> = {};
  for (const [key, n] of Object.entries(counts)) evidence[oneOf(key, ["dot", "comma", "ambiguous"] as const)] = count(n);
  const dc = record(has(obj, "document_currency"));
  return {
    decimal_style: { value: match(has(ds, "value"), TOKEN), source: nmatch(has(ds, "source"), TOKEN), evidence_counts: evidence },
    document_currency: { value: nmatch(has(dc, "value"), CURRENCY), source: nmatch(has(dc, "source"), TOKEN) },
    sign_conventions: list(has(obj, "sign_conventions"), (s) => match(s, TOKEN), 8),
    tables: list(has(obj, "tables"), (t) => {
      const table = record(t);
      const cols = record(has(table, "columns"));
      const columns: Record<string, string> = {};
      for (const [key, header] of Object.entries(cols)) columns[match(key, TOKEN)] = str(header, 4096);
      return {
        locator: locator(has(table, "locator")),
        columns,
        unmapped_columns: list(has(table, "unmapped_columns"), (c) => str(c, 4096), 64),
        sign_convention: nmatch(has(table, "sign_convention"), TOKEN),
      };
    }, 32),
  };
}

function coverage(value: unknown): DocumentAnalysis["coverage"] {
  if (value === null) return null;
  const obj = record(value);
  const countsObj = record(has(obj, "unit_status_counts"));
  const statusCounts: Partial<Record<UnitStatus, number>> = {};
  for (const [key, n] of Object.entries(countsObj)) statusCounts[oneOf(key, UNIT_STATUSES)] = count(n);
  return {
    unit: oneOf(has(obj, "unit"), ["sheet_or_file", "page"] as const),
    units_total: count(has(obj, "units_total")),
    unit_status_counts: statusCounts,
    records_typed: ncount(optional(obj, "records_typed")),
    rows_unparsed: ncount(optional(obj, "rows_unparsed")),
    text_chars: ncount(optional(obj, "text_chars")),
    note: str(has(obj, "note"), 500),
  };
}

function parseAnalysis(value: unknown): DocumentAnalysis {
  const obj = record(value);
  const parser = record(has(obj, "parser"));
  const libraries = record(has(parser, "libraries"));
  const libs: Record<string, string | null> = {};
  for (const [name, version] of Object.entries(libraries)) libs[str(name, 64)] = nstr(version, 64);
  const source = record(has(obj, "source"));
  const run = record(has(obj, "worker_run"));
  const elapsed = has(run, "elapsed_ms");
  if (elapsed !== null && (typeof elapsed !== "number" || !Number.isFinite(elapsed) || elapsed < 0)) fail();
  const exit = has(run, "exit_code");
  const containment = has(run, "containment");
  if (containment !== null) oneOf(containment, ["windows_job_object", "posix_session_rlimits"] as const);
  const analysis: DocumentAnalysis = {
    handle_id: match(has(obj, "handle_id"), HANDLE),
    status: oneOf(has(obj, "status"), ["complete", "partial", "unsupported", "error"] as const),
    format: oneOf(has(obj, "format"), DOCUMENT_FORMATS),
    detected: nmatch(has(obj, "detected"), TOKEN),
    source: { sha256: match(has(source, "sha256"), DIGEST), size_bytes: count(has(source, "size_bytes")) },
    parser: {
      worker_protocol: oneOf(has(parser, "worker_protocol"), ["sentinel.doc01.worker/0.1"] as const),
      worker_version: str(has(parser, "worker_version"), 32),
      worker_source_sha256: match(has(parser, "worker_source_sha256"), DIGEST),
      libraries: libs,
      options: options(has(parser, "options")),
    },
    units: list(has(obj, "units"), unit, 66),
    records_total: count(has(obj, "records_total")),
    records: list(has(obj, "records"), extracted, MAX_RECORDS_LIMIT),
    records_next_offset: ncount(has(obj, "records_next_offset")),
    unparsed: list(has(obj, "unparsed"), (u) => {
      const item = record(u);
      return {
        evidence_id: match(has(item, "evidence_id"), EVIDENCE),
        locator: locator(has(item, "locator")),
        reason: match(has(item, "reason"), TOKEN),
        raw_excerpt: str(has(item, "raw_excerpt"), 200),
      };
    }, 100),
    unparsed_total: count(has(obj, "unparsed_total")),
    findings: list(has(obj, "findings"), finding, 100),
    table_typing: tableTyping(has(obj, "table_typing")),
    pdf_structure: (() => {
      const raw = has(obj, "pdf_structure");
      if (raw === null) return null;
      const p = record(raw);
      return { page_tree: match(has(p, "page_tree"), TOKEN), trailer_present: bool(has(p, "trailer_present")), encrypted: bool(has(p, "encrypted")) };
    })(),
    measures: measures(has(obj, "measures")),
    coverage: coverage(has(obj, "coverage")),
    errors: list(has(obj, "errors"), (e) => {
      const err = record(e);
      return { code: match(has(err, "code"), TOKEN), detail: str(has(err, "detail"), 200) };
    }, 20),
    worker_run: {
      exit_code: exit === null ? null : int(exit),
      elapsed_ms: elapsed as number | null,
      containment: containment as DocumentAnalysis["worker_run"]["containment"],
      outcome: match(has(run, "outcome"), TOKEN),
      stop_confirmed: bool(has(run, "stop_confirmed")),
    },
    interpretation: str(has(obj, "interpretation"), 500),
  };
  if (analysis.interpretation !== INTERPRETATION) fail();
  // Exact denominators: counts agree with what is returned and with coverage.
  checkPage(0, analysis.parser.options.records_limit, analysis.records_total, analysis.records.length,
    analysis.records_next_offset);
  if (analysis.unparsed_total < analysis.unparsed.length) fail();
  const cov = analysis.coverage;
  if (cov) {
    if (cov.records_typed !== null && cov.records_typed !== analysis.records_total) fail();
    if (cov.rows_unparsed !== null && cov.rows_unparsed !== analysis.unparsed_total) fail();
    const sum = Object.values(cov.unit_status_counts).reduce((a, b) => a + (b ?? 0), 0);
    if (sum !== cov.units_total) fail();
  }
  if ((analysis.status === "unsupported" || analysis.status === "error") &&
      (analysis.records.length > 0 || analysis.errors.length === 0)) fail();
  return analysis;
}

function parseOrNull<T>(parse: (value: unknown) => T): (value: unknown) => T | null {
  return (value) => {
    try {
      return parse(value);
    } catch (error) {
      if (error instanceof Reject) return null;
      throw error;
    }
  };
}

export const acceptAnalysis = parseOrNull(parseAnalysis);

export const acceptUpload = parseOrNull((value): DocumentUpload => {
  const obj = record(value);
  const size = count(has(obj, "size_bytes"));
  if (size < 1 || size > MAX_UPLOAD_BYTES) fail();
  const expires = str(has(obj, "expires_at"), 64);
  if (Number.isNaN(Date.parse(expires))) fail();
  return {
    handle_id: match(has(obj, "handle_id"), HANDLE),
    format: oneOf(has(obj, "format"), DOCUMENT_FORMATS),
    sha256: match(has(obj, "sha256"), DIGEST),
    size_bytes: size,
    expires_at: expires,
  };
});

export const acceptRecordPage = parseOrNull((value): RecordPage => {
  const obj = record(value);
  const page: RecordPage = {
    handle_id: match(has(obj, "handle_id"), HANDLE),
    status: oneOf(has(obj, "status"), ["complete", "partial", "unsupported", "error"] as const),
    source_sha256: match(has(obj, "source_sha256"), DIGEST),
    offset: count(has(obj, "offset")),
    limit: count(has(obj, "limit")),
    total: count(has(obj, "total")),
    records: list(has(obj, "records"), extracted, MAX_RECORDS_LIMIT),
    next_offset: ncount(has(obj, "next_offset")),
  };
  if (page.limit < 1 || page.limit > MAX_RECORDS_LIMIT) fail();
  checkPage(page.offset, page.limit, page.total, page.records.length, page.next_offset);
  return page;
});

export const acceptDeleted = parseOrNull((value): DocumentDeleted => {
  const obj = record(value);
  return { handle_id: match(has(obj, "handle_id"), HANDLE), deleted: bool(has(obj, "deleted")) };
});

// ---- binding a success to the current document (R64) -----------------------------------------
//
// Each response is valid on its own; these checks reject a valid-shaped success that describes
// a different document, upload, option set or analysis from the one the UI holds. v1.3 has no
// analysis revision, so a replacement made elsewhere with the same status and total cannot be
// detected from these fields; nothing here claims a pinned snapshot.

/** The upload receipt describes the file that was chosen and the format it was sent as. */
export function uploadMatches(receipt: DocumentUpload, file: { size: number }, format: DocumentFormat): boolean {
  return receipt.format === format && receipt.size_bytes === file.size;
}

/** The analysis is of this handle's uploaded bytes, under exactly the options submitted. */
export function analysisMatches(
  analysis: DocumentAnalysis,
  upload: DocumentUpload,
  request: AnalysisRequest,
): boolean {
  const applied = analysis.parser.options;
  return (
    analysis.handle_id === upload.handle_id &&
    analysis.source.sha256 === upload.sha256 &&
    analysis.source.size_bytes === upload.size_bytes &&
    analysis.format === upload.format &&
    applied.decimal_style === request.decimal_style &&
    applied.date_order === request.date_order &&
    applied.default_currency === request.default_currency &&
    applied.records_limit === request.records_limit
  );
}

/** The page belongs to the analysis shown, answers the request made and keeps the page rule. */
export function pageMatches(
  page: RecordPage,
  analysis: DocumentAnalysis,
  offset: number,
  limit: number,
): boolean {
  if (
    page.handle_id !== analysis.handle_id ||
    page.source_sha256 !== analysis.source.sha256 ||
    page.status !== analysis.status ||
    page.total !== analysis.records_total ||
    page.offset !== offset ||
    page.limit !== limit
  ) {
    return false;
  }
  try {
    checkPage(page.offset, page.limit, page.total, page.records.length, page.next_offset);
  } catch (error) {
    if (error instanceof Reject) return false;
    throw error;
  }
  return true;
}

/** Only an answer naming this handle with `deleted: true` confirms the deletion. */
export function deletionConfirmed(answer: DocumentDeleted, handle: string): boolean {
  return answer.handle_id === handle && answer.deleted === true;
}

// ---- formatting --------------------------------------------------------------------------------

/** Signed integer minor units -> decimal text by exponent; string arithmetic only. */
export function minorToDecimal(minor: string, exp: number | null): string {
  if (!MINOR.test(minor)) return "unavailable";
  if (exp === null) return `${minor} minor units (exponent unknown)`;
  const negative = minor.startsWith("-");
  const digits = negative ? minor.slice(1) : minor;
  if (exp === 0) return `${negative ? "-" : ""}${digits}`;
  const padded = digits.padStart(exp + 1, "0");
  const whole = padded.slice(0, -exp).replace(/^0+(?=\d)/, "");
  return `${negative ? "-" : ""}${whole}.${padded.slice(-exp)}`;
}

/** n/d with the exact denominator; 0/0 is not applicable rather than zero. */
export function ratioText(r: Ratio): string {
  if (r.denominator === 0) return "not applicable (0 of 0)";
  return `${r.numerator} of ${r.denominator}`;
}

export function locatorText(loc: Locator): string {
  const parts: string[] = [];
  if (loc.sheet !== null) parts.push(`sheet ${loc.sheet}`);
  if (loc.page !== null) parts.push(`page ${loc.page}`);
  if (loc.row !== null) parts.push(`row ${loc.row}`);
  if (loc.column !== null) parts.push(`column ${loc.column}`);
  if (loc.part !== null) parts.push(`part ${loc.part}`);
  if (loc.file !== null && parts.length === 0) parts.push("file");
  return parts.length > 0 ? parts.join(", ") : "document";
}

// ---- client -----------------------------------------------------------------------------------

export type DocumentFailure = {
  ok: false;
  /** refused: a documented 4xx. worker: a documented worker 5xx. unconfirmed: anything the
   * contract does not describe (malformed JSON, empty/non-JSON 5xx, wrong shape). */
  kind: "refused" | "worker" | "unconfirmed" | "network" | "aborted";
  status: number | null;
  code: string | null;
};
export type DocumentResult<T> = { ok: true; status: number; data: T } | DocumentFailure;

const WORKER_CODES = new Set([
  "document_worker_unavailable",
  "document_worker_busy",
  "document_worker_recovery_pending",
  "document_worker_timeout",
  "document_worker_failed",
  "document_worker_identity_changed",
]);

type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

export interface DocumentClient {
  upload(token: string, file: Blob, format: DocumentFormat, signal?: AbortSignal): Promise<DocumentResult<DocumentUpload>>;
  analyze(token: string, handleId: string, request: AnalysisRequest, signal?: AbortSignal): Promise<DocumentResult<DocumentAnalysis>>;
  records(token: string, handleId: string, offset: number, limit: number, signal?: AbortSignal): Promise<DocumentResult<RecordPage>>;
  remove(token: string, handleId: string, signal?: AbortSignal): Promise<DocumentResult<DocumentDeleted>>;
}

function errorCode(value: unknown): string | null {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return null;
  const code = (value as Record<string, unknown>).error;
  return typeof code === "string" && /^[a-z0-9_]{1,64}$/.test(code) ? code : null;
}

export function createDocumentClient(fetchImpl: FetchLike = (input, init) => fetch(input, init)): DocumentClient {
  async function call<T>(
    path: string,
    init: RequestInit,
    accept: (value: unknown) => T | null,
  ): Promise<DocumentResult<T>> {
    let response: Response;
    try {
      response = await fetchImpl(path, { cache: "no-store", ...init });
    } catch {
      return { ok: false, kind: init.signal?.aborted ? "aborted" : "network", status: null, code: null };
    }
    let text = "";
    try {
      text = await response.text();
    } catch {
      return { ok: false, kind: init.signal?.aborted ? "aborted" : "unconfirmed", status: response.status, code: null };
    }
    let parsed: unknown = undefined;
    const json = (response.headers.get("content-type") ?? "").split(";")[0]?.trim().toLowerCase() === "application/json";
    if (json && text.trim() !== "") {
      try {
        parsed = JSON.parse(text) as unknown;
      } catch {
        parsed = undefined;
      }
    }
    if (response.status >= 500) {
      const code = errorCode(parsed);
      return code && WORKER_CODES.has(code)
        ? { ok: false, kind: "worker", status: response.status, code }
        : { ok: false, kind: "unconfirmed", status: response.status, code: null };
    }
    if (!response.ok) {
      const code = errorCode(parsed);
      return code
        ? { ok: false, kind: "refused", status: response.status, code }
        : { ok: false, kind: "unconfirmed", status: response.status, code: null };
    }
    const data = parsed === undefined ? null : accept(parsed);
    return data === null
      ? { ok: false, kind: "unconfirmed", status: response.status, code: null }
      : { ok: true, status: response.status, data };
  }

  const auth = (token: string) => ({ Authorization: `Bearer ${token}`, Accept: "application/json" });

  return {
    upload: (token, file, format, signal) =>
      call(`/v1/documents?format=${format}`, {
        method: "POST",
        // Raw bytes with the format's media type: no multipart body, no filename.
        headers: { ...auth(token), "Content-Type": DOCUMENT_MEDIA[format] },
        body: file,
        signal,
      }, acceptUpload),
    analyze: (token, handleId, request, signal) =>
      call(`/v1/documents/${encodeURIComponent(handleId)}/analysis`, {
        method: "POST",
        headers: { ...auth(token), "Content-Type": "application/json" },
        body: JSON.stringify(request),
        signal,
      }, acceptAnalysis),
    records: (token, handleId, offset, limit, signal) =>
      call(`/v1/documents/${encodeURIComponent(handleId)}/records?offset=${offset}&limit=${limit}`, {
        method: "GET",
        headers: auth(token),
        signal,
      }, acceptRecordPage),
    remove: (token, handleId, signal) =>
      call(`/v1/documents/${encodeURIComponent(handleId)}`, {
        method: "DELETE",
        headers: auth(token),
        signal,
      }, acceptDeleted),
  };
}

// ---- messages ----------------------------------------------------------------------------------

const MESSAGES: Record<string, string> = {
  unauthenticated: "This session token was not accepted.",
  permission_denied: "This session cannot review documents.",
  not_found: "This document is no longer available here. It was deleted, its one-hour lease ended, or it belongs to another session.",
  analysis_not_found: "There is no stored analysis for this document yet. Run the analysis first.",
  body_too_large: "The file is larger than 10 MiB, so the server refused it.",
  unsupported_media_type: "The server refused the file type for the chosen format.",
  format_mismatch: "The file's contents do not match the chosen format.",
  unsupported_container: "Encrypted or legacy Office containers are not supported.",
  invalid_request: "The server rejected the request.",
  invalid_content_length: "The request size could not be read.",
  document_worker_unavailable: "Document analysis is not available on this server.",
  document_worker_busy: "Another analysis is running on this server. Try again shortly.",
  document_worker_recovery_pending:
    "The document worker is still confirming that an earlier run stopped. Analysis is paused until that is verified. Try again later.",
  document_worker_timeout:
    "The analysis did not finish in time and was stopped. No result was produced. Try again later.",
  document_worker_failed: "The document worker failed. No result was produced.",
  document_worker_identity_changed:
    "The document worker on the server changed since it was registered, so analysis is refused.",
};

export function documentMessage(failure: DocumentFailure): string {
  if (failure.kind === "network") return "Sentinel could not be reached. Nothing was confirmed.";
  if (failure.kind === "unconfirmed" || failure.code === null) {
    return "The server did not confirm a result. Nothing is shown for this request.";
  }
  return MESSAGES[failure.code] ?? `The server returned ${failure.code}.`;
}
