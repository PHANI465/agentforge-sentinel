import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { SentinelClient } from "../api/client";
import {
  MAX_UPLOAD_BYTES,
  type DocumentAnalysis,
  type DocumentClient,
  type DocumentFormat,
  type DocumentResult,
  type DocumentUpload,
  type RecordPage,
} from "../api/documents";
import type { Overview, SessionView } from "../api/types";
import { DocumentReview } from "./DocumentReview";
import { Workbench } from "./Workbench";

const here = dirname(fileURLToPath(import.meta.url));
const v13 = resolve(here, "../fixtures/http-v1.3");
const v1 = resolve(here, "../../../contracts/http/examples");
const workerFixtures = resolve(here, "../../../tools/document_worker/fixtures");

function body<T>(name: string): T {
  return JSON.parse(readFileSync(resolve(v13, `${name}.json`), "utf8")).response as T;
}

const UPLOAD = body<DocumentUpload>("document_upload_csv");
const HANDLE = UPLOAD.handle_id;

function ok<T>(data: T): DocumentResult<T> {
  return { ok: true, status: 200, data };
}

function failure(kind: "refused" | "worker" | "unconfirmed" | "network", status: number | null, code: string | null) {
  return { ok: false as const, kind, status, code };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

/** A frozen analysis rebound to the uploaded document (handle and source), as the server
 * would answer for that upload. Its format and options stay the fixture's own. */
function analysisFor(name: string): DocumentAnalysis {
  const data = body<DocumentAnalysis>(name);
  return { ...data, handle_id: HANDLE, source: { sha256: UPLOAD.sha256, size_bytes: UPLOAD.size_bytes } };
}

const PAGE = body<RecordPage>("document_records_page");

function fakeClient(over: Partial<DocumentClient> = {}): DocumentClient & Record<string, ReturnType<typeof vi.fn>> {
  return {
    upload: vi.fn(async (_t: string, _f: File, format: DocumentFormat) => ok({ ...UPLOAD, format })),
    analyze: vi.fn(async () => ok(analysisFor("document_analysis_complete_paged"))),
    records: vi.fn(async (_t: string, _h: string, offset: number, limit: number) => ok({ ...PAGE, offset, limit })),
    remove: vi.fn(async () => ok({ handle_id: HANDLE, deleted: true })),
    ...over,
  } as unknown as DocumentClient & Record<string, ReturnType<typeof vi.fn>>;
}

// The bytes the frozen CSV upload receipt describes (547 bytes, its SHA-256).
const CSV = readFileSync(resolve(workerFixtures, "csv_statement_usd.csv"));

async function uploadCsv(user: ReturnType<typeof userEvent.setup>, name = "C:\\Users\\private\\bank-statement.csv") {
  const file = new File([CSV], name, { type: "text/csv" });
  await user.upload(screen.getByLabelText(/Local file/), file);
  await user.click(screen.getByRole("button", { name: "Upload" }));
  await screen.findByText("Uploaded document");
  return file;
}

async function analyse(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: "Run the analysis" }));
}

afterEach(() => cleanup());

describe("visibility and authority", () => {
  const session = JSON.parse(readFileSync(resolve(v1, "session.json"), "utf8")).response as SessionView;
  const overview = JSON.parse(readFileSync(resolve(v1, "overview.json"), "utf8")).response as Overview;
  const client = {
    overview: vi.fn(async () => ({ ok: true, status: 200, data: overview })),
    listCases: vi.fn(async () => ({ ok: true, status: 200, data: { items: [], next_cursor: null, limit: 25 } })),
    scoring: vi.fn(async () => ({ ok: false, ambiguous: false, status: 403, code: "permission_denied", message: "x", details: [] })),
    modelResults: vi.fn(async () => ({ ok: false, ambiguous: false, status: 403, code: "permission_denied", message: "x", details: [] })),
    trace: vi.fn(),
  } as unknown as SentinelClient;

  it("is absent for the default grant and present only with analyze_document", async () => {
    const documents = fakeClient();
    const { unmount } = render(<Workbench client={client} token="t" session={session} onSignOut={vi.fn()} documents={documents} />);
    await screen.findByRole("heading", { name: "Case queue" });
    expect(screen.queryByRole("heading", { name: "Document review" })).not.toBeInTheDocument();
    unmount();
    const opted = { ...session, capabilities: [...session.capabilities, "analyze_document" as const] };
    render(<Workbench client={client} token="t" session={opted} onSignOut={vi.fn()} documents={documents} />);
    expect(await screen.findByRole("heading", { name: "Document review" })).toBeInTheDocument();
    expect(screen.getByText(/review local documents/)).toBeInTheDocument();
  });
});

describe("upload", () => {
  it("sends raw bytes with the chosen format and never shows the file name or path", async () => {
    const user = userEvent.setup();
    const documents = fakeClient();
    const { container } = render(<DocumentReview documents={documents} token="tok" sessionId="s1" />);
    expect(screen.getByText(/10 MiB at most/)).toBeInTheDocument(); // the cap is shown before selection
    const file = await uploadCsv(user);
    expect(documents.upload).toHaveBeenCalledWith("tok", file, "csv", expect.any(AbortSignal));
    expect(container.textContent).not.toContain("bank-statement");
    expect(container.textContent).not.toContain("private");
    expect(screen.getByText(UPLOAD.sha256)).toBeInTheDocument();
  });

  it("rejects an oversized file before sending it", async () => {
    const user = userEvent.setup();
    const documents = fakeClient();
    render(<DocumentReview documents={documents} token="tok" sessionId="s1" />);
    const big = new File([new Uint8Array(MAX_UPLOAD_BYTES + 1)], "big.csv", { type: "text/csv" });
    await user.upload(screen.getByLabelText(/Local file/), big);
    expect(await screen.findByRole("alert")).toHaveTextContent(/above the 10 MiB limit/);
    expect(screen.queryByRole("button", { name: "Upload" })).not.toBeInTheDocument();
    expect(documents.upload).not.toHaveBeenCalled();
  });

  it("requires a format when the extension does not say", async () => {
    const user = userEvent.setup({ applyAccept: false });
    render(<DocumentReview documents={fakeClient()} token="tok" sessionId="s1" />);
    await user.upload(screen.getByLabelText(/Local file/), new File(["x"], "statement.txt"));
    expect(screen.getByRole("button", { name: "Upload" })).toBeDisabled();
    await user.click(screen.getByLabelText("PDF with a text layer"));
    expect(screen.getByRole("button", { name: "Upload" })).toBeEnabled();
  });

  it.each([
    [failure("refused", 413, "body_too_large"), /larger than 10 MiB/],
    [failure("refused", 415, "format_mismatch"), /do not match the chosen format/],
    [failure("refused", 415, "unsupported_container"), /Encrypted or legacy/],
    [failure("worker", 503, "document_worker_unavailable"), /not available on this server/],
    [failure("unconfirmed", 500, null), /did not confirm/],
    [failure("network", null, null), /could not be reached/],
  ])("treats the server's refusal as authoritative (%j)", async (result, text) => {
    const user = userEvent.setup();
    render(<DocumentReview documents={fakeClient({ upload: vi.fn(async () => result) })} token="tok" sessionId="s1" />);
    await user.upload(screen.getByLabelText(/Local file/), new File([CSV], "a.csv"));
    await user.click(screen.getByRole("button", { name: "Upload" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(text);
    expect(alert).toHaveFocus(); // focus moves to the error
    expect(screen.queryByText("Uploaded document")).not.toBeInTheDocument();
  });
});

describe("analysis results", () => {
  it("shows a complete result, separate currency reconciliation and provenance", async () => {
    const user = userEvent.setup();
    render(<DocumentReview documents={fakeClient()} token="tok" recordsLimit={5} sessionId="s1" />);
    await uploadCsv(user);
    await analyse(user);
    expect(await screen.findByRole("heading", { name: "Extraction result: complete" })).toBeInTheDocument();
    expect(screen.getByText(/not fraud detection/)).toBeInTheDocument();
    expect(screen.getByText(/equals the closing balance \(difference 0.00 USD\)/)).toBeInTheDocument();
    expect(screen.getByText("Records 1–5 of 10.")).toBeInTheDocument();
    expect(screen.getByText("Source and parser provenance")).toBeInTheDocument();
  });

  it("explains a reconciliation difference in plain language", async () => {
    const user = userEvent.setup();
    render(<DocumentReview documents={fakeClient({ analyze: vi.fn(async () => ok(analysisFor("document_analysis_difference"))) })} token="tok" sessionId="s1" />);
    await uploadCsv(user);
    await analyse(user);
    expect(await screen.findByText(/differs by -1.00 USD/)).toBeInTheDocument();
    expect(screen.getByText(/not a finding of fraud/)).toBeInTheDocument();
  });

  it("keeps two currencies separate with no combined total", async () => {
    const user = userEvent.setup();
    const { container } = render(
      <DocumentReview documents={fakeClient({ analyze: vi.fn(async () => ok(analysisFor("document_analysis_two_currency"))) })} token="tok" sessionId="s1" />,
    );
    await uploadCsv(user);
    await analyse(user);
    expect(await screen.findByRole("heading", { name: "EUR: not checkable" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "USD: reconciled" })).toBeInTheDocument();
    expect(container.textContent).toContain("never combined or converted");
    expect(container.textContent).not.toMatch(/combined total|converted to/i);
  });

  it("partial results say how much was not read", async () => {
    const user = userEvent.setup();
    render(<DocumentReview documents={fakeClient({ analyze: vi.fn(async () => ok(analysisFor("document_analysis_partial_comma_decimal"))) })} token="tok" sessionId="s1" />);
    await uploadCsv(user);
    await analyse(user);
    expect(await screen.findByText(/Partly extracted/)).toBeInTheDocument();
    expect(screen.getByText(/Rows not parsed \(1 shown of 1\)/)).toBeInTheDocument();
  });

  it.each([
    ["document_analysis_xlsx_macro_unsupported", "unsupported", /Not supported: nothing was extracted/],
    ["document_analysis_pdf_truncated_error", "error", /Could not be read: nothing was extracted/],
    ["document_analysis_pdf_encrypted_unsupported", "unsupported", /Not supported/],
  ])("%s is shown as no result, with its reason codes", async (name, status, text) => {
    const user = userEvent.setup();
    const analysis = analysisFor(name);
    render(<DocumentReview documents={fakeClient({ analyze: vi.fn(async () => ok(analysis)) })} token="tok" sessionId="s1" />);
    await uploadCsv(user, `statement.${analysis.format}`);
    await analyse(user);
    expect(await screen.findByRole("heading", { name: `Extraction result: ${status}` })).toBeInTheDocument();
    expect(screen.getByText(text)).toBeInTheDocument();
    for (const error of analysis.errors) expect(screen.getByText(error.code)).toBeInTheDocument();
    expect(screen.queryByText("Extracted records")).not.toBeInTheDocument();
    expect(screen.queryByText(/equals the closing balance/)).not.toBeInTheDocument();
  });

  it("states that PDF tables are not typed and there is no OCR", async () => {
    const user = userEvent.setup();
    render(<DocumentReview documents={fakeClient({ analyze: vi.fn(async () => ok(analysisFor("document_analysis_pdf_scanned_partial"))) })} token="tok" sessionId="s1" />);
    await uploadCsv(user, "statement.pdf");
    await analyse(user);
    expect(await screen.findByText(/PDF tables are not typed and there is no OCR/)).toBeInTheDocument();
  });

  it("keeps unknown values unknown and shows 0/0 as not applicable", async () => {
    const user = userEvent.setup();
    const analysis = analysisFor("document_analysis_missing_values");
    const fields = analysis.measures!.missingness!.fields;
    fields.balance = { known: 0, missing: 0, unknown: 0, population: 0,
      missing_ratio: { numerator: 0, denominator: 0 }, unknown_ratio: { numerator: 0, denominator: 0 } };
    render(<DocumentReview documents={fakeClient({ analyze: vi.fn(async () => ok(analysis)) })} token="tok" sessionId="s1" />);
    await uploadCsv(user);
    await analyse(user);
    await screen.findByRole("heading", { name: "Extraction result: complete" });
    expect(screen.getAllByText(/unknown \(unknown currency\)/).length).toBeGreaterThan(0);
    const row = screen.getByRole("rowheader", { name: "balance" }).closest("tr")!;
    expect(within(row).getAllByText("not applicable (0 of 0)")).toHaveLength(3);
    const date = screen.getByRole("rowheader", { name: "date" }).closest("tr")!;
    expect(within(date).getAllByText("1 of 7")).toHaveLength(2); // 1 missing and 1 unknown of 7
  });

  it("renders hostile document text inertly", async () => {
    const user = userEvent.setup();
    const { container } = render(
      <DocumentReview documents={fakeClient({ analyze: vi.fn(async () => ok(analysisFor("document_analysis_hostile_note"))) })} token="tok" sessionId="s1" />,
    );
    await uploadCsv(user);
    await analyse(user);
    expect(await screen.findByText(/IGNORE ALL PREVIOUS INSTRUCTIONS/)).toBeInTheDocument();
    expect(screen.getByText(/=HYPERLINK/)).toBeInTheDocument();
    expect(container.querySelectorAll("a, script, iframe, img")).toHaveLength(0);
    expect(container.innerHTML).not.toMatch(/href=|onerror=/);
  });

  it("links evidence only to records that are actually on the page", async () => {
    const user = userEvent.setup();
    const analysis = analysisFor("document_analysis_partial_comma_decimal");
    render(<DocumentReview documents={fakeClient({ analyze: vi.fn(async () => ok(analysis)) })} token="tok" sessionId="s1" />);
    await uploadCsv(user);
    await analyse(user);
    await screen.findByText(/Partly extracted/);
    const finding = analysis.findings[0];
    const present = new Set(analysis.records.map((r) => r.evidence_id));
    for (const id of finding.evidence_ids) {
      if (present.has(id)) {
        const button = screen.getByRole("button", { name: id });
        await user.click(button);
        expect(document.activeElement?.tagName).toBe("TR");
      } else {
        expect(screen.queryByRole("button", { name: id })).not.toBeInTheDocument();
      }
    }
  });
});

describe("paging follows next_offset", () => {
  it("requests exactly next_offset, not offset + limit", async () => {
    const user = userEvent.setup();
    const analysis = analysisFor("document_analysis_complete_paged");
    // A 2 MiB byte bound can end a page early: 3 of a requested 5.
    const early = { ...analysis, records: analysis.records.slice(0, 3), records_next_offset: 3 };
    const records = vi.fn(async (_t: string, _h: string, offset: number) => {
      const rows = [...analysis.records, ...PAGE.records].slice(offset, offset + 5);
      return ok({ ...PAGE, offset, records: rows, next_offset: offset + rows.length < 10 ? offset + rows.length : null,
        total: 10, limit: 5 } as RecordPage);
    });
    render(<DocumentReview documents={fakeClient({ analyze: vi.fn(async () => ok(early)), records })} token="tok" recordsLimit={5} sessionId="s1" />);
    await uploadCsv(user);
    await analyse(user);
    expect(await screen.findByText("Records 1–3 of 10.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Next records" }));
    expect(records).toHaveBeenCalledWith("tok", HANDLE, 3, 5, expect.any(AbortSignal));
  });

  it("moves forward and back and ends where the server says", async () => {
    const user = userEvent.setup();
    const documents = fakeClient();
    render(<DocumentReview documents={documents} token="tok" recordsLimit={5} sessionId="s1" />);
    await uploadCsv(user);
    await analyse(user);
    await screen.findByText("Records 1–5 of 10.");
    await user.click(screen.getByRole("button", { name: "Next records" }));
    expect(await screen.findByText("Records 6–10 of 10.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next records" })).toBeDisabled();
    expect(documents.records).toHaveBeenCalledWith("tok", HANDLE, 5, 5, expect.any(AbortSignal));
  });

  it("a deleted, expired or foreign handle (404) clears stale content", async () => {
    const user = userEvent.setup();
    render(<DocumentReview documents={fakeClient({ records: vi.fn(async () => failure("refused", 404, "not_found")) })} token="tok" recordsLimit={5} sessionId="s1" />);
    await uploadCsv(user);
    await analyse(user);
    await screen.findByText("Records 1–5 of 10.");
    await user.click(screen.getByRole("button", { name: "Next records" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/no longer available/);
    expect(screen.queryByText("Uploaded document")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /Extraction result/ })).not.toBeInTheDocument();
  });
});

describe("worker failures are not document results", () => {
  it.each([
    [failure("worker", 503, "document_worker_recovery_pending"), /still confirming that an earlier run stopped/],
    [failure("worker", 503, "document_worker_busy"), /Another analysis is running/],
    [failure("worker", 504, "document_worker_timeout"), /did not finish in time/],
    [failure("worker", 502, "document_worker_failed"), /worker failed/],
    [failure("worker", 503, "document_worker_identity_changed"), /changed since it was registered/],
    [failure("unconfirmed", 502, null), /did not confirm/],
    [failure("network", null, null), /could not be reached/],
  ])("%j clears the shown result and offers a retry", async (result, text) => {
    const user = userEvent.setup();
    const analyze = vi
      .fn()
      .mockResolvedValueOnce(ok(analysisFor("document_analysis_complete_paged")))
      .mockResolvedValueOnce(result)
      .mockResolvedValueOnce(ok(analysisFor("document_analysis_complete_paged")));
    render(<DocumentReview documents={fakeClient({ analyze })} token="tok" recordsLimit={5} sessionId="s1" />);
    await uploadCsv(user);
    await analyse(user);
    await screen.findByRole("heading", { name: "Extraction result: complete" });
    await user.click(screen.getByRole("button", { name: "Analyse again" }));
    await user.click(screen.getByRole("button", { name: "Replace the stored result" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(text);
    expect(screen.queryByRole("heading", { name: /Extraction result/ })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try the analysis again" }));
    expect(await screen.findByRole("heading", { name: "Extraction result: complete" })).toBeInTheDocument();
  });

  it("explains re-analysis before replacing the stored result", async () => {
    const user = userEvent.setup();
    const documents = fakeClient();
    render(<DocumentReview documents={documents} token="tok" recordsLimit={5} sessionId="s1" />);
    await uploadCsv(user);
    await analyse(user);
    await screen.findByRole("heading", { name: "Extraction result: complete" });
    await user.click(screen.getByRole("button", { name: "Analyse again" }));
    expect(screen.getByText(/replaces the stored result/)).toBeInTheDocument();
    expect(documents.analyze).toHaveBeenCalledTimes(1);
    await user.click(screen.getByRole("button", { name: "Keep the current result" }));
    expect(documents.analyze).toHaveBeenCalledTimes(1);
  });
});

describe("delete and fencing", () => {
  it("delete clears every piece of local content", async () => {
    const user = userEvent.setup();
    const documents = fakeClient();
    render(<DocumentReview documents={documents} token="tok" recordsLimit={5} sessionId="s1" />);
    await uploadCsv(user);
    await analyse(user);
    await screen.findByRole("heading", { name: "Extraction result: complete" });
    await user.click(screen.getByRole("button", { name: "Delete document" }));
    expect(await screen.findByText(/Deleted. Nothing from that document/)).toBeInTheDocument();
    expect(documents.remove).toHaveBeenCalledWith("tok", HANDLE, expect.any(AbortSignal));
    expect(screen.queryByText("Uploaded document")).not.toBeInTheDocument();
    expect(screen.queryByText(/Coffee|Opening/)).not.toBeInTheDocument();
  });

  it("locks the controls while analysing, and a late analysis after a session change is ignored", async () => {
    const user = userEvent.setup();
    const pending = deferred<DocumentResult<DocumentAnalysis>>();
    const documents = fakeClient({ analyze: vi.fn(() => pending.promise) });
    const { rerender } = render(<DocumentReview documents={documents} token="tok" recordsLimit={5} sessionId="s1" />);
    await uploadCsv(user);
    await analyse(user);
    expect(screen.getByLabelText(/Local file/)).toBeDisabled();
    expect(screen.getByRole("button", { name: "Delete document" })).toBeDisabled();
    rerender(<DocumentReview documents={documents} token="tok-2" recordsLimit={5} sessionId="s2" />);
    await act(async () => {
      pending.resolve(ok(analysisFor("document_analysis_complete_paged")));
      await Promise.resolve();
    });
    expect(screen.queryByRole("heading", { name: /Extraction result/ })).not.toBeInTheDocument();
    expect(screen.queryByText("Uploaded document")).not.toBeInTheDocument();
    expect(screen.getByLabelText(/Local file/)).toBeEnabled();
  });

  it("a session switch clears content at once and suppresses late responses", async () => {
    const user = userEvent.setup();
    const pending = deferred<DocumentResult<RecordPage>>();
    const documents = fakeClient({ records: vi.fn(() => pending.promise) });
    const { rerender } = render(<DocumentReview documents={documents} token="tok" recordsLimit={5} sessionId="s1" />);
    await uploadCsv(user);
    await analyse(user);
    await screen.findByText("Records 1–5 of 10.");
    await user.click(screen.getByRole("button", { name: "Next records" }));
    rerender(<DocumentReview documents={documents} token="other-token" recordsLimit={5} sessionId="s2" />);
    expect(screen.queryByText("Uploaded document")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /Extraction result/ })).not.toBeInTheDocument();
    await act(async () => {
      pending.resolve(ok(body<RecordPage>("document_records_page")));
      await Promise.resolve();
    });
    expect(screen.queryByText(/Records 6–10/)).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /Extraction result/ })).not.toBeInTheDocument();
  });

  it("a reversed upload response for an earlier file is ignored", async () => {
    const user = userEvent.setup();
    const first = deferred<DocumentResult<DocumentUpload>>();
    const upload = vi.fn().mockReturnValueOnce(first.promise).mockResolvedValueOnce(ok(UPLOAD));
    render(<DocumentReview documents={fakeClient({ upload })} token="tok" sessionId="s1" />);
    await user.upload(screen.getByLabelText(/Local file/), new File([CSV], "first.csv"));
    await user.click(screen.getByRole("button", { name: "Upload" }));
    // While the first upload is pending the controls are locked; abandoning it by unmount
    // and remount (sign-out and back) must still suppress its late answer.
    cleanup();
    render(<DocumentReview documents={fakeClient({ upload })} token="tok" sessionId="s1" />);
    await act(async () => {
      first.resolve(ok({ ...UPLOAD, sha256: "f".repeat(64) }));
      await Promise.resolve();
    });
    expect(screen.queryByText("f".repeat(64))).not.toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText("Uploaded document")).not.toBeInTheDocument());
  });
});

describe("R64: every success is bound to the current document", () => {
  const OTHER_DIGEST = "a".repeat(64);
  const OTHER_HANDLE = "h_0000000000000000000099";

  it("an upload receipt whose size disagrees with the chosen file is unconfirmed", async () => {
    const user = userEvent.setup();
    render(<DocumentReview documents={fakeClient()} token="tok" sessionId="s1" />);
    await user.upload(screen.getByLabelText(/Local file/), new File(["x"], "one-byte.csv")); // the receipt says 547
    await user.click(screen.getByRole("button", { name: "Upload" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/did not confirm this upload/);
    expect(screen.queryByText("Uploaded document")).not.toBeInTheDocument();
    expect(screen.queryByText(UPLOAD.sha256)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Run the analysis" })).not.toBeInTheDocument();
  });

  it("an upload receipt for another format is unconfirmed", async () => {
    const user = userEvent.setup();
    render(<DocumentReview documents={fakeClient({ upload: vi.fn(async () => ok({ ...UPLOAD, format: "pdf" as const })) })} token="tok" sessionId="s1" />);
    await user.upload(screen.getByLabelText(/Local file/), new File([CSV], "a.csv"));
    await user.click(screen.getByRole("button", { name: "Upload" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/did not confirm this upload/);
    expect(screen.queryByText("Uploaded document")).not.toBeInTheDocument();
  });

  const paged = () => analysisFor("document_analysis_complete_paged");
  it.each([
    ["another handle", () => ({ ...paged(), handle_id: OTHER_HANDLE })],
    ["another source digest", () => ({ ...paged(), source: { ...paged().source, sha256: OTHER_DIGEST } })],
    ["another source size", () => ({ ...paged(), source: { ...paged().source, size_bytes: 548 } })],
    ["another format", () => ({ ...paged(), format: "pdf" as const })],
    ["other interpretation options", () => ({ ...paged(), parser: { ...paged().parser, options: { ...paged().parser.options, decimal_style: "comma" as const } } })],
    ["another default currency", () => ({ ...paged(), parser: { ...paged().parser, options: { ...paged().parser.options, default_currency: "EUR" } } })],
    ["another records limit", () => ({ ...paged(), parser: { ...paged().parser, options: { ...paged().parser.options, records_limit: 100 } } })],
  ])("an analysis for %s is unconfirmed and offers a retry", async (_label, make) => {
    const user = userEvent.setup();
    render(<DocumentReview documents={fakeClient({ analyze: vi.fn(async () => ok(make())) })} token="tok" recordsLimit={5} sessionId="s1" />);
    await uploadCsv(user);
    await analyse(user);
    expect(await screen.findByRole("alert")).toHaveTextContent(/did not confirm a result for this document/);
    expect(screen.queryByRole("heading", { name: /Extraction result/ })).not.toBeInTheDocument();
    expect(screen.queryByText(/Records 1–5/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try the analysis again" })).toBeInTheDocument();
  });

  it("a contradictory re-analysis does not leave the old result presented as current", async () => {
    const user = userEvent.setup();
    const analyze = vi
      .fn()
      .mockResolvedValueOnce(ok(paged()))
      .mockResolvedValueOnce(ok({ ...paged(), source: { ...paged().source, sha256: OTHER_DIGEST } }));
    render(<DocumentReview documents={fakeClient({ analyze })} token="tok" recordsLimit={5} sessionId="s1" />);
    await uploadCsv(user);
    await analyse(user);
    await screen.findByRole("heading", { name: "Extraction result: complete" });
    await user.click(screen.getByRole("button", { name: "Analyse again" }));
    await user.click(screen.getByRole("button", { name: "Replace the stored result" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/did not confirm a result for this document/);
    expect(screen.queryByRole("heading", { name: /Extraction result/ })).not.toBeInTheDocument();
    expect(screen.queryByText(/Records 1–5/)).not.toBeInTheDocument();
  });

  it.each([
    ["a different status", { status: "partial" as const }],
    ["a different total", { total: 11 }],
    ["another source digest", { source_sha256: OTHER_DIGEST }],
    ["another handle", { handle_id: OTHER_HANDLE }],
    ["another offset", { offset: 6 }],
    ["another limit", { limit: 100 }],
    ["a broken page rule", { next_offset: 9 }],
  ])("a records page with %s is refused and the analysis is no longer shown as current", async (_label, change) => {
    const user = userEvent.setup();
    const records = vi.fn(async (_t: string, _h: string, offset: number, limit: number) => ok({ ...PAGE, offset, limit, ...change }));
    render(<DocumentReview documents={fakeClient({ records })} token="tok" recordsLimit={5} sessionId="s1" />);
    await uploadCsv(user);
    await analyse(user);
    await screen.findByText("Records 1–5 of 10.");
    await user.click(screen.getByRole("button", { name: "Next records" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/do not match the analysis shown/);
    expect(screen.queryByText(/Records 6–10/)).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /Extraction result/ })).not.toBeInTheDocument();
    expect(screen.getByText("Uploaded document")).toBeInTheDocument(); // the handle is still ours
  });

  it.each([
    ["deleted: false", { handle_id: HANDLE, deleted: false }],
    ["another handle", { handle_id: OTHER_HANDLE, deleted: true }],
  ])("a delete answer with %s is not reported as deleted", async (_label, answer) => {
    const user = userEvent.setup();
    render(<DocumentReview documents={fakeClient({ remove: vi.fn(async () => ok(answer)) })} token="tok" recordsLimit={5} sessionId="s1" />);
    await uploadCsv(user);
    await analyse(user);
    await screen.findByRole("heading", { name: "Extraction result: complete" });
    await user.click(screen.getByRole("button", { name: "Delete document" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/did not confirm the deletion/);
    expect(screen.queryByText(/^Deleted\./)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete document" })).toBeEnabled(); // it can be tried again
  });
});
