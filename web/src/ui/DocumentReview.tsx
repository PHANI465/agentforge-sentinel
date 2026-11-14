import { useCallback, useEffect, useRef, useState, type ChangeEvent } from "react";
import {
  DEFAULT_RECORDS_LIMIT,
  DOCUMENT_FORMATS,
  documentMessage,
  INTERPRETATION,
  locatorText,
  MAX_UPLOAD_BYTES,
  minorToDecimal,
  ratioText,
  type AnalysisRequest,
  type CurrencyReconciliation,
  type DocumentAnalysis,
  type DocumentClient,
  type DocumentFailure,
  type DocumentFormat,
  type DocumentUpload,
  type ExtractedRecord,
  type MissingnessField,
} from "../api/documents";

/**
 * DOC01 Part C: Document review. Shown only to sessions holding `analyze_document`.
 * Extraction and consistency checks only: not fraud detection, document authenticity or a
 * risk score. Nothing here creates a transaction, case, investigation, approval or action.
 * The token and the opaque handle stay in memory; no file name or path is shown or sent.
 */

type Phase = "idle" | "uploading" | "analyzing" | "paging" | "deleting";
type Notice = { tone: "error" | "info"; text: string; retry?: boolean } | null;
type PageView = {
  offset: number;
  limit: number;
  total: number;
  records: ExtractedRecord[];
  nextOffset: number | null;
  history: number[];
};

const FORMAT_LABEL: Record<DocumentFormat, string> = {
  csv: "CSV (UTF-8 text)",
  xlsx: "XLSX spreadsheet",
  pdf: "PDF with a text layer",
};

const STATUS_TEXT: Record<DocumentAnalysis["status"], string> = {
  complete: "Extraction complete: every unit was read and nothing was left unparsed.",
  partial: "Partly extracted: some units, rows or values could not be read. The counts below say how many.",
  unsupported: "Not supported: nothing was extracted from this document.",
  error: "Could not be read: nothing was extracted from this document.",
};

const MiB = 1024 * 1024;

function guessFormat(name: string): DocumentFormat | null {
  const match = /\.([A-Za-z0-9]{1,8})$/.exec(name);
  const ext = match?.[1]?.toLowerCase();
  return ext === "csv" || ext === "xlsx" || ext === "pdf" ? ext : null;
}

function sizeText(bytes: number): string {
  if (bytes < 1024) return `${bytes} bytes`;
  if (bytes < MiB) return `${(bytes / 1024).toFixed(1)} KiB (${bytes} bytes)`;
  return `${(bytes / MiB).toFixed(2)} MiB (${bytes} bytes)`;
}

function valueText(part: { status: string; minor_units: string | null; exponent: number | null } | null): string {
  if (part === null) return "not applicable";
  if (part.status !== "known" || part.minor_units === null) return `unknown (${part.status.replaceAll("_", " ")})`;
  return minorToDecimal(part.minor_units, part.exponent);
}

function textOrUnknown(part: { status: string; raw: string | null }): string {
  if (part.status === "missing" || part.raw === null) return "missing";
  return part.raw;
}

function reconciliationSentence(entry: CurrencyReconciliation): string {
  const exp = entry.exponent;
  if (entry.status === "reconciled") {
    return `Opening balance plus credits minus debits equals the closing balance (difference ${minorToDecimal("0", exp)} ${entry.currency}).`;
  }
  if (entry.status === "difference" && entry.difference_minor !== null) {
    return `Opening balance plus credits minus debits does not equal the closing balance: it differs by ${minorToDecimal(entry.difference_minor, exp)} ${entry.currency}. This is a consistency check of the document's own figures, not a finding of fraud.`;
  }
  return `Not checkable for ${entry.currency}${entry.reason ? `: ${entry.reason.replaceAll("_", " ")}` : ""}.`;
}

export function DocumentReview({
  documents,
  token,
  sessionId,
}: {
  documents: DocumentClient;
  token: string;
  sessionId: string;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [format, setFormat] = useState<DocumentFormat | null>(null);
  const [upload, setUpload] = useState<DocumentUpload | null>(null);
  const [analysis, setAnalysis] = useState<DocumentAnalysis | null>(null);
  const [page, setPage] = useState<PageView | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [notice, setNotice] = useState<Notice>(null);
  const [confirmReanalyze, setConfirmReanalyze] = useState(false);
  const [options, setOptions] = useState<AnalysisRequest>({
    decimal_style: "unspecified",
    date_order: "iso_only",
    default_currency: null,
    records_limit: DEFAULT_RECORDS_LIMIT,
  });
  const [currencyText, setCurrencyText] = useState("");
  const generation = useRef(0);
  const controller = useRef<AbortController | null>(null);
  const handleRef = useRef<string | null>(null);
  const noticeRef = useRef<HTMLParagraphElement | null>(null);
  const fileInput = useRef<HTMLInputElement | null>(null);
  const rowRefs = useRef(new Map<string, HTMLTableRowElement>());

  const clearAll = useCallback(() => {
    generation.current += 1; // every response still in flight is now stale
    controller.current?.abort();
    controller.current = null;
    handleRef.current = null;
    setFile(null);
    setFormat(null);
    setUpload(null);
    setAnalysis(null);
    setPage(null);
    setPhase("idle");
    setConfirmReanalyze(false);
    if (fileInput.current) fileInput.current.value = "";
  }, []);

  // A different session (or sign-out, which unmounts) clears private content at once.
  useEffect(() => {
    clearAll();
    setNotice(null);
    return () => {
      generation.current += 1;
      controller.current?.abort();
    };
  }, [token, sessionId, clearAll]);

  useEffect(() => {
    if (notice?.tone === "error") noticeRef.current?.focus();
  }, [notice]);

  function begin(next: Phase): { gen: number; signal: AbortSignal } {
    controller.current?.abort();
    const abort = new AbortController();
    controller.current = abort;
    generation.current += 1;
    setPhase(next);
    return { gen: generation.current, signal: abort.signal };
  }

  function stillCurrent(gen: number, handle: string | null): boolean {
    return gen === generation.current && handleRef.current === handle;
  }

  function finish(gen: number) {
    if (gen === generation.current) setPhase("idle");
  }

  function failed(result: DocumentFailure, context: "upload" | "analyze" | "records" | "delete") {
    if (result.kind === "aborted") return;
    if (result.kind === "refused" && result.code === "not_found" && context !== "upload") {
      // Missing, deleted, expired or foreign: one answer. Drop the stale content.
      const message = documentMessage(result);
      clearAll();
      setNotice({ tone: "error", text: message });
      return;
    }
    if (context === "analyze" && result.kind !== "refused") {
      // A worker failure or unconfirmed answer is not a document result. The stored
      // result may have changed, so the previous one is no longer shown.
      setAnalysis(null);
      setPage(null);
    }
    if (context === "records" && result.kind === "refused" && result.code === "analysis_not_found") {
      setAnalysis(null);
      setPage(null);
    }
    setNotice({
      tone: "error",
      text: documentMessage(result),
      retry: context === "analyze" && (result.kind === "worker" || result.kind === "unconfirmed" || result.kind === "network"),
    });
  }

  function chooseFile(event: ChangeEvent<HTMLInputElement>) {
    const chosen = event.target.files?.[0] ?? null;
    clearAll();
    if (!chosen) {
      setNotice(null);
      return;
    }
    if (chosen.size === 0) {
      setNotice({ tone: "error", text: "The chosen file is empty." });
      if (fileInput.current) fileInput.current.value = "";
      return;
    }
    if (chosen.size > MAX_UPLOAD_BYTES) {
      setNotice({ tone: "error", text: `The chosen file is ${sizeText(chosen.size)}, above the 10 MiB limit. It was not sent.` });
      if (fileInput.current) fileInput.current.value = "";
      return;
    }
    setFile(chosen);
    setFormat(guessFormat(chosen.name));
    setNotice({ tone: "info", text: `Selected a file of ${sizeText(chosen.size)}. Choose its format, then upload.` });
  }

  async function doUpload() {
    if (!file || !format || phase !== "idle") return;
    const { gen, signal } = begin("uploading");
    setNotice({ tone: "info", text: "Uploading." });
    const result = await documents.upload(token, file, format, signal);
    if (!stillCurrent(gen, null)) return;
    finish(gen);
    if (!result.ok) {
      failed(result, "upload");
      return;
    }
    handleRef.current = result.data.handle_id;
    setUpload(result.data);
    setFile(null); // the bytes now live only on the server, under this session
    if (fileInput.current) fileInput.current.value = "";
    setNotice({ tone: "info", text: "Uploaded. Run the analysis when you are ready." });
  }

  async function doAnalyze() {
    const handle = handleRef.current;
    if (!handle || phase !== "idle") return;
    if (analysis && !confirmReanalyze) {
      setConfirmReanalyze(true);
      return;
    }
    setConfirmReanalyze(false);
    const { gen, signal } = begin("analyzing");
    setNotice({ tone: "info", text: "Analysing. This can take up to a minute and a half." });
    const result = await documents.analyze(token, handle, options, signal);
    if (!stillCurrent(gen, handle)) return;
    finish(gen);
    if (!result.ok) {
      failed(result, "analyze");
      return;
    }
    if (result.data.handle_id !== handle) {
      setNotice({ tone: "error", text: "The server did not confirm a result for this document." });
      return;
    }
    setAnalysis(result.data);
    setPage({
      offset: 0,
      limit: result.data.parser.options.records_limit,
      total: result.data.records_total,
      records: result.data.records,
      nextOffset: result.data.records_next_offset,
      history: [],
    });
    setNotice({ tone: "info", text: `Analysis returned: ${result.data.status}.` });
  }

  async function goToPage(offset: number, history: number[]) {
    const handle = handleRef.current;
    if (!handle || !analysis || !page || phase !== "idle") return;
    const { gen, signal } = begin("paging");
    const result = await documents.records(token, handle, offset, page.limit, signal);
    if (!stillCurrent(gen, handle)) return;
    finish(gen);
    if (!result.ok) {
      failed(result, "records");
      return;
    }
    if (result.data.handle_id !== handle || result.data.source_sha256 !== analysis.source.sha256 ||
        result.data.offset !== offset) {
      setNotice({ tone: "error", text: "The server did not confirm this page of records." });
      return;
    }
    setPage({
      offset: result.data.offset,
      limit: result.data.limit,
      total: result.data.total,
      records: result.data.records,
      nextOffset: result.data.next_offset,
      history,
    });
    setNotice(null);
  }

  async function doDelete() {
    const handle = handleRef.current;
    if (!handle || phase !== "idle") return;
    const { gen, signal } = begin("deleting");
    const result = await documents.remove(token, handle, signal);
    if (!stillCurrent(gen, handle)) return;
    finish(gen);
    if (result.ok || (result.kind === "refused" && result.code === "not_found")) {
      clearAll();
      setNotice({ tone: "info", text: "Deleted. Nothing from that document is shown any more." });
      return;
    }
    failed(result, "delete");
  }

  function setCurrency(value: string) {
    const upper = value.toUpperCase().slice(0, 3);
    setCurrencyText(upper);
    setOptions((current) => ({ ...current, default_currency: /^[A-Z]{3}$/.test(upper) ? upper : null }));
  }

  const busy = phase !== "idle";
  const evidenceOnPage = new Set(page?.records.map((r) => r.evidence_id) ?? []);
  const showRecordsSection = analysis && (analysis.status === "complete" || analysis.status === "partial");

  function focusEvidence(id: string) {
    const row = rowRefs.current.get(id);
    row?.focus();
  }

  function evidenceList(ids: string[], total?: number) {
    return (
      <span className="evidence">
        {ids.map((id) => (
          <span key={id}>
            {evidenceOnPage.has(id) ? (
              <button type="button" className="linkish" onClick={() => focusEvidence(id)}>
                {id}
              </button>
            ) : (
              <code>{id}</code>
            )}{" "}
          </span>
        ))}
        {total !== undefined && total > ids.length ? <span>(and {total - ids.length} more)</span> : null}
      </span>
    );
  }

  return (
    <section className="documents" aria-labelledby="documents-heading" id="documents">
      <h2 id="documents-heading">Document review</h2>
      <p className="meta">
        Upload a local public or synthetic PDF, CSV or XLSX file (10 MiB at most) to check what can be
        extracted from it and whether its own figures are consistent. This is extraction feedback, not fraud
        detection, an authenticity check or a risk score. It never creates a transaction, case, approval or
        action, and the file is not sent to a model.
      </p>

      <div className="doc-step">
        <label>
          Local file (PDF, CSV or XLSX, up to 10 MiB)
          <input
            ref={fileInput}
            type="file"
            accept=".csv,.xlsx,.pdf,text/csv,application/pdf,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            onChange={chooseFile}
            disabled={busy}
          />
        </label>
        {file ? (
          <fieldset className="doc-format">
            <legend>Format of the selected file</legend>
            {DOCUMENT_FORMATS.map((item) => (
              <label key={item}>
                <input
                  type="radio"
                  name="document-format"
                  value={item}
                  checked={format === item}
                  onChange={() => setFormat(item)}
                  disabled={busy}
                />
                {FORMAT_LABEL[item]}
              </label>
            ))}
          </fieldset>
        ) : null}
        {file ? (
          <button type="button" onClick={() => void doUpload()} disabled={busy || !format}>
            Upload
          </button>
        ) : null}
      </div>

      {notice ? (
        <p
          className={notice.tone === "error" ? "status doc-error" : "status"}
          role={notice.tone === "error" ? "alert" : "status"}
          tabIndex={-1}
          ref={noticeRef}
        >
          {notice.text}
          {notice.retry && upload ? (
            <>
              {" "}
              <button type="button" className="secondary" onClick={() => void doAnalyze()} disabled={busy}>
                Try the analysis again
              </button>
            </>
          ) : null}
        </p>
      ) : null}
      {busy ? (
        <p className="status" role="status">
          {phase === "uploading" ? "Uploading…" : phase === "analyzing" ? "Analysing…" : phase === "paging" ? "Loading records…" : "Deleting…"}
        </p>
      ) : null}

      {upload ? (
        <div className="doc-step">
          <h3>Uploaded document</h3>
          <dl className="doc-facts">
            <div>
              <dt>Format</dt>
              <dd>{FORMAT_LABEL[upload.format]}</dd>
            </div>
            <div>
              <dt>Size</dt>
              <dd>{sizeText(upload.size_bytes)}</dd>
            </div>
            <div>
              <dt>Available until</dt>
              <dd>{upload.expires_at}</dd>
            </div>
            <div>
              <dt>SHA-256</dt>
              <dd className="hash">{upload.sha256}</dd>
            </div>
          </dl>
          <fieldset className="doc-options" disabled={busy}>
            <legend>Interpretation assumptions</legend>
            <p className="meta">Undeclared conventions are never guessed: ambiguous values stay unknown.</p>
            <label>
              Decimal style
              <select
                value={options.decimal_style}
                onChange={(event) =>
                  setOptions((current) => ({ ...current, decimal_style: event.target.value as AnalysisRequest["decimal_style"] }))
                }
              >
                <option value="unspecified">Not declared</option>
                <option value="dot">1,234.56 (dot decimal)</option>
                <option value="comma">1.234,56 (comma decimal)</option>
              </select>
            </label>
            <label>
              Date order
              <select
                value={options.date_order}
                onChange={(event) =>
                  setOptions((current) => ({ ...current, date_order: event.target.value as AnalysisRequest["date_order"] }))
                }
              >
                <option value="iso_only">ISO dates only (YYYY-MM-DD)</option>
                <option value="dmy">Day, month, year</option>
                <option value="mdy">Month, day, year</option>
              </select>
            </label>
            <label>
              Default currency (three letters, optional)
              <input value={currencyText} onChange={(event) => setCurrency(event.target.value)} maxLength={3} spellCheck={false} />
            </label>
          </fieldset>
          {confirmReanalyze ? (
            <div className="doc-confirm" role="group" aria-label="Confirm a new analysis">
              <p>
                Running the analysis again replaces the stored result for this document. The result shown now will be
                replaced by the new one.
              </p>
              <button type="button" onClick={() => void doAnalyze()} disabled={busy}>
                Replace the stored result
              </button>{" "}
              <button type="button" className="secondary" onClick={() => setConfirmReanalyze(false)}>
                Keep the current result
              </button>
            </div>
          ) : (
            <div className="actions">
              <button type="button" onClick={() => void doAnalyze()} disabled={busy}>
                {analysis ? "Analyse again" : "Run the analysis"}
              </button>
              <button type="button" className="secondary" onClick={() => void doDelete()} disabled={busy}>
                Delete document
              </button>
            </div>
          )}
        </div>
      ) : null}

      {analysis ? (
        <div className="doc-result" aria-labelledby="doc-result-heading">
          <h3 id="doc-result-heading">Extraction result: {analysis.status}</h3>
          <p className={analysis.status === "complete" || analysis.status === "partial" ? "doc-status" : "doc-status doc-error"}>
            {STATUS_TEXT[analysis.status]}
          </p>
          <p className="meta">{INTERPRETATION}</p>
          {analysis.errors.length > 0 ? (
            <>
              <h4>Reason codes</h4>
              <ul className="doc-list">
                {analysis.errors.map((error, index) => (
                  <li key={`${error.code}-${index}`}>
                    <code>{error.code}</code>
                    {error.detail ? <> — {error.detail}</> : null}
                  </li>
                ))}
              </ul>
            </>
          ) : null}

          {analysis.coverage ? (
            <>
              <h4>Coverage</h4>
              <ul className="doc-list">
                <li>
                  {analysis.coverage.units_total} {analysis.coverage.unit === "page" ? "page(s)" : "file or sheet unit(s)"}:{" "}
                  {Object.entries(analysis.coverage.unit_status_counts)
                    .map(([status, n]) => `${n} ${status}`)
                    .join(", ")}
                </li>
                {analysis.coverage.records_typed !== null ? <li>{analysis.coverage.records_typed} record(s) typed</li> : null}
                {analysis.coverage.rows_unparsed !== null ? <li>{analysis.coverage.rows_unparsed} row(s) not parsed</li> : null}
                {analysis.coverage.text_chars !== null ? <li>{analysis.coverage.text_chars} text-layer character(s)</li> : null}
                <li className="meta">{analysis.coverage.note}</li>
              </ul>
            </>
          ) : null}

          {analysis.measures?.missingness ? (
            <div className="table-wrap">
              <table className="data">
                <caption>Missing and unknown values ({analysis.measures.missingness.count} {analysis.measures.missingness.population})</caption>
                <thead>
                  <tr>
                    <th scope="col">Field</th>
                    <th scope="col">Known</th>
                    <th scope="col">Missing</th>
                    <th scope="col">Unknown</th>
                  </tr>
                </thead>
                <tbody>
                  {(Object.keys(analysis.measures.missingness.fields) as MissingnessField[]).map((name) => {
                    const field = analysis.measures?.missingness?.fields[name];
                    if (!field) return null;
                    return (
                      <tr key={name}>
                        <th scope="row">{name}</th>
                        <td>{field.population === 0 ? "not applicable (0 of 0)" : `${field.known} of ${field.population}`}</td>
                        <td>{ratioText(field.missing_ratio)}</td>
                        <td>{ratioText(field.unknown_ratio)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : null}

          {analysis.measures ? (
            <>
              <h4>Reconciliation by currency</h4>
              <p className="meta">Each currency is checked on its own. Currencies are never combined or converted.</p>
              {analysis.measures.reconciliation.status === "not_checkable" ? (
                <p>
                  Not checkable for this document
                  {analysis.measures.reconciliation.reason ? `: ${analysis.measures.reconciliation.reason.replaceAll("_", " ")}` : ""}.
                </p>
              ) : null}
              {analysis.measures.reconciliation.currencies.map((entry) => (
                <div className="doc-currency" key={entry.currency}>
                  <h5>
                    {entry.currency}: {entry.status.replace("_", " ")}
                  </h5>
                  <p>{reconciliationSentence(entry)}</p>
                  <dl className="doc-facts">
                    <div>
                      <dt>Opening</dt>
                      <dd>{entry.opening ? minorToDecimal(entry.opening.minor_units, entry.exponent) : "not stated"}</dd>
                    </div>
                    <div>
                      <dt>Credits</dt>
                      <dd>{minorToDecimal(entry.credits_minor, entry.exponent)}</dd>
                    </div>
                    <div>
                      <dt>Debits</dt>
                      <dd>{minorToDecimal(entry.debits_minor, entry.exponent)}</dd>
                    </div>
                    <div>
                      <dt>Closing</dt>
                      <dd>{entry.closing ? minorToDecimal(entry.closing.minor_units, entry.exponent) : "not stated"}</dd>
                    </div>
                    <div>
                      <dt>Transactions</dt>
                      <dd>
                        {entry.transaction_count} ({entry.unknown_amount_count} with an unknown amount)
                      </dd>
                    </div>
                  </dl>
                </div>
              ))}
              {analysis.measures.reconciliation.unknown_currency_records ? (
                <p>{analysis.measures.reconciliation.unknown_currency_records} record(s) have an unknown currency and are not in any total.</p>
              ) : null}
              {analysis.measures.running_balance ? (
                <p>
                  Running balance: {analysis.measures.running_balance.checked_transitions} transition(s) checked,{" "}
                  {analysis.measures.running_balance.mismatches_total} mismatch(es).
                </p>
              ) : null}
              {analysis.measures.duplicates ? (
                <p>
                  Possible duplicate rows: {analysis.measures.duplicates.groups_total} group(s) covering{" "}
                  {analysis.measures.duplicates.rows_in_duplicate_groups} row(s); {analysis.measures.duplicates.checked_records} checked,{" "}
                  {analysis.measures.duplicates.not_checkable_records} not checkable ({analysis.measures.duplicates.interpretation}).
                </p>
              ) : null}
            </>
          ) : null}

          {analysis.findings.length > 0 ? (
            <>
              <h4>Data-quality observations</h4>
              <ul className="doc-list">
                {analysis.findings.map((item) => (
                  <li key={item.finding_id}>
                    <strong>{item.severity === "warning" ? "Warning" : "Note"}</strong>{" "}
                    <code>{item.kind}</code>: {item.detail} Evidence: {evidenceList(item.evidence_ids, item.evidence_count)}
                  </li>
                ))}
              </ul>
            </>
          ) : null}

          {analysis.table_typing ? (
            <>
              <h4>How values were typed</h4>
              <ul className="doc-list">
                <li>
                  Decimal style: {analysis.table_typing.decimal_style.value}
                  {analysis.table_typing.decimal_style.source ? ` (${analysis.table_typing.decimal_style.source.replaceAll("_", " ")})` : ""}
                </li>
                <li>Document currency: {analysis.table_typing.document_currency.value ?? "not stated"}</li>
                <li>Sign conventions: {analysis.table_typing.sign_conventions.join(", ") || "none recognised"}</li>
                {analysis.table_typing.tables.map((table, index) => (
                  <li key={index}>
                    Table at {locatorText(table.locator)}:{" "}
                    {Object.entries(table.columns)
                      .map(([field, header]) => `${field} ← "${header}"`)
                      .join("; ")}
                    {table.unmapped_columns.length > 0 ? `; unmapped: ${table.unmapped_columns.map((c) => `"${c}"`).join(", ")}` : ""}
                  </li>
                ))}
              </ul>
            </>
          ) : null}
          {analysis.pdf_structure ? (
            <>
              <h4>PDF structure</h4>
              <p>
                Page tree {analysis.pdf_structure.page_tree}; trailer {analysis.pdf_structure.trailer_present ? "present" : "missing"};{" "}
                {analysis.pdf_structure.encrypted ? "encrypted" : "not encrypted"}. PDF tables are not typed and there is no OCR, so no
                reconciliation is possible from a PDF.
              </p>
            </>
          ) : null}

          <div className="table-wrap">
            <table className="data">
              <caption>Units read</caption>
              <thead>
                <tr>
                  <th scope="col">Unit</th>
                  <th scope="col">Status</th>
                  <th scope="col">Reason</th>
                  <th scope="col">Detail</th>
                </tr>
              </thead>
              <tbody>
                {analysis.units.map((item, index) => (
                  <tr key={index}>
                    <td>{locatorText(item.locator)}</td>
                    <td>{item.status}</td>
                    <td>{item.reason ?? "—"}</td>
                    <td>
                      {item.rows_non_empty !== null ? `${item.rows_non_empty} non-empty row(s)` : ""}
                      {item.chars !== null ? `${item.chars} character(s)` : ""}
                      {item.images !== null ? `, ${item.images} image(s)` : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {analysis.unparsed_total > 0 ? (
            <>
              <h4>
                Rows not parsed ({analysis.unparsed.length} shown of {analysis.unparsed_total})
              </h4>
              <ul className="doc-list">
                {analysis.unparsed.map((item) => (
                  <li key={item.evidence_id}>
                    {locatorText(item.locator)}: <code>{item.reason}</code> — <q>{item.raw_excerpt}</q>
                  </li>
                ))}
              </ul>
            </>
          ) : null}

          {showRecordsSection && page ? (
            <>
              <h4>Extracted records</h4>
              <p role="status">
                {page.total === 0
                  ? "No records were extracted."
                  : `Records ${page.records.length === 0 ? 0 : page.offset + 1}–${page.offset + page.records.length} of ${page.total}.`}
              </p>
              {page.records.length > 0 ? (
                <div className="table-wrap">
                  <table className="data">
                    <caption>Records (document text is shown as plain text)</caption>
                    <thead>
                      <tr>
                        <th scope="col">Evidence</th>
                        <th scope="col">Kind</th>
                        <th scope="col">Date</th>
                        <th scope="col">Description</th>
                        <th scope="col">Amount</th>
                        <th scope="col">Balance</th>
                        <th scope="col">Currency</th>
                        <th scope="col">Reference</th>
                      </tr>
                    </thead>
                    <tbody>
                      {page.records.map((item) => (
                        <tr
                          key={item.evidence_id}
                          tabIndex={-1}
                          ref={(row) => {
                            if (row) rowRefs.current.set(item.evidence_id, row);
                            else rowRefs.current.delete(item.evidence_id);
                          }}
                        >
                          <td>
                            <code>{item.evidence_id}</code>
                            <br />
                            {locatorText(item.locator)}
                          </td>
                          <td>{item.kind.replace("_", " ")}</td>
                          <td>{item.date.status === "known" ? item.date.value : `unknown (${item.date.status.replaceAll("_", " ")})`}</td>
                          <td>{textOrUnknown(item.description)}</td>
                          <td>{valueText(item.amount)}</td>
                          <td>{valueText(item.balance)}</td>
                          <td>{item.currency.status === "known" ? item.currency.value : `unknown (${item.currency.status.replaceAll("_", " ")})`}</td>
                          <td>{textOrUnknown(item.reference)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
              <div className="pager">
                <button
                  type="button"
                  className="secondary"
                  disabled={busy || page.history.length === 0}
                  onClick={() => {
                    const history = page.history.slice(0, -1);
                    void goToPage(page.history[page.history.length - 1] ?? 0, history);
                  }}
                >
                  Previous records
                </button>
                <button
                  type="button"
                  className="secondary"
                  disabled={busy || page.nextOffset === null}
                  onClick={() => {
                    if (page.nextOffset !== null) void goToPage(page.nextOffset, [...page.history, page.offset]);
                  }}
                >
                  Next records
                </button>
              </div>
            </>
          ) : null}

          <details className="tech">
            <summary>Source and parser provenance</summary>
            <dl className="doc-facts">
              <div>
                <dt>Source SHA-256</dt>
                <dd className="hash">{analysis.source.sha256}</dd>
              </div>
              <div>
                <dt>Size</dt>
                <dd>{sizeText(analysis.source.size_bytes)}</dd>
              </div>
              <div>
                <dt>Declared / detected</dt>
                <dd>
                  {analysis.format} / {analysis.detected ?? "unknown"}
                </dd>
              </div>
              <div>
                <dt>Worker</dt>
                <dd>
                  {analysis.parser.worker_protocol}, version {analysis.parser.worker_version}
                </dd>
              </div>
              <div>
                <dt>Worker source SHA-256</dt>
                <dd className="hash">{analysis.parser.worker_source_sha256}</dd>
              </div>
              <div>
                <dt>Libraries</dt>
                <dd>
                  {Object.entries(analysis.parser.libraries)
                    .map(([name, version]) => `${name} ${version ?? "unknown"}`)
                    .join(", ")}
                </dd>
              </div>
              <div>
                <dt>Assumptions used</dt>
                <dd>
                  decimal {analysis.parser.options.decimal_style}, dates {analysis.parser.options.date_order}, default currency{" "}
                  {analysis.parser.options.default_currency ?? "none"}, {analysis.parser.options.records_limit} records per page
                </dd>
              </div>
              <div>
                <dt>Parser run</dt>
                <dd>
                  outcome {analysis.worker_run.outcome}, exit {analysis.worker_run.exit_code ?? "unknown"},{" "}
                  {analysis.worker_run.stop_confirmed ? "stop confirmed" : "stop not confirmed"}
                  {analysis.worker_run.containment ? `, ${analysis.worker_run.containment.replaceAll("_", " ")}` : ""}
                </dd>
              </div>
            </dl>
          </details>
        </div>
      ) : null}
    </section>
  );
}
