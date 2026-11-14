import { createHash } from "node:crypto";
import { readdirSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it, vi } from "vitest";
import {
  acceptAnalysis,
  acceptDeleted,
  acceptRecordPage,
  acceptUpload,
  analysisMatches,
  createDocumentClient,
  deletionConfirmed,
  documentMessage,
  INTERPRETATION,
  minorToDecimal,
  pageMatches,
  ratioText,
  uploadMatches,
  type DocumentAnalysis,
} from "./documents";

const here = dirname(fileURLToPath(import.meta.url));
const fixtures = resolve(here, "../fixtures/http-v1.3");
const frozen = resolve(here, "../../../contracts/http/examples-v1.3");

type Example = { status: number; request: { method: string; path: string }; response: Record<string, unknown> };

export function docExample(name: string): Example {
  return JSON.parse(readFileSync(resolve(fixtures, `${name}.json`), "utf8")) as Example;
}

export function docBody(name: string): Record<string, unknown> {
  return structuredClone(docExample(name).response);
}

function parsed(name: string): DocumentAnalysis {
  const analysis = acceptAnalysis(docBody(name));
  if (!analysis) throw new Error(`${name} did not parse`);
  return analysis;
}

const analysisNames = readdirSync(fixtures)
  .filter((file) => file.startsWith("document_analysis_"))
  .map((file) => file.replace(/\.json$/, ""));

describe("accepted v1.3 fixtures", () => {
  it("are byte-identical to the recorded provenance and the frozen examples", () => {
    const provenance = readFileSync(resolve(fixtures, "PROVENANCE.md"), "utf8");
    const files = readdirSync(fixtures).filter((file) => file.endsWith(".json"));
    expect(files).toHaveLength(29);
    for (const file of files) {
      const bytes = readFileSync(resolve(fixtures, file));
      const digest = createHash("sha256").update(bytes).digest("hex");
      expect(provenance).toContain(`${file} sha256 ${digest} (${bytes.length} bytes)`);
      expect(bytes.equals(readFileSync(resolve(frozen, file)))).toBe(true);
    }
    const openapi = readFileSync(resolve(here, "../../../contracts/http/openapi.v1.3.json"));
    expect(createHash("sha256").update(openapi).digest("hex")).toBe(
      "d4306c651f8a555fca6e309a27c7bd5b2c133f07d4cfc2f07f1fcde772eae4dc",
    );
  });

  it.each(analysisNames)("%s parses strictly", (name) => {
    const analysis = parsed(name);
    expect(analysis.interpretation).toBe(INTERPRETATION);
    expect(analysis.records_total).toBeGreaterThanOrEqual(analysis.records.length);
  });

  it("parses the upload, record page and delete examples", () => {
    for (const name of ["document_upload_csv", "document_upload_xlsx", "document_upload_pdf"]) {
      expect(acceptUpload(docBody(name))).not.toBeNull();
    }
    const page = acceptRecordPage(docBody("document_records_page"));
    expect(page && [page.offset, page.records.length, page.next_offset]).toEqual([5, 5, null]);
    expect(acceptDeleted(docBody("document_deleted"))).toEqual({
      handle_id: "h_0000000000000000000001",
      deleted: true,
    });
  });

  it("covers every document status in the examples", () => {
    expect(new Set(analysisNames.map((name) => parsed(name).status))).toEqual(
      new Set(["complete", "partial", "unsupported", "error"]),
    );
  });
});

describe("strict parsing makes contradictions unconfirmed, never an empty report", () => {
  const base = () => docBody("document_analysis_complete_paged");
  const variants: Array<[string, (b: Record<string, unknown>) => void]> = [
    ["records_total missing", (b) => delete b.records_total],
    ["unparsed_total missing", (b) => delete b.unparsed_total],
    ["records_total zero with records", (b) => (b.records_total = 0)],
    ["next offset not following the page", (b) => (b.records_next_offset = 7)],
    ["next offset absent while records remain", (b) => (b.records_next_offset = null)],
    ["records as an object", (b) => (b.records = {})],
    ["status outside the contract", (b) => (b.status = "success")],
    ["interpretation changed", (b) => (b.interpretation = "Fraud detected.")],
    ["handle malformed", (b) => (b.handle_id = "../etc")],
    ["parser missing", (b) => delete b.parser],
    ["measures wrong type", (b) => (b.measures = "none")],
    ["worker_run missing", (b) => delete b.worker_run],
    ["money as a float", (b) => {
      const record = (b.records as Record<string, Record<string, unknown>>[])[1];
      (record.amount as Record<string, unknown>).minor_units = 12.5;
    }],
    ["known amount without money", (b) => {
      const record = (b.records as Record<string, Record<string, unknown>>[])[1];
      (record.amount as Record<string, unknown>).minor_units = null;
    }],
    ["unknown amount with money", (b) => {
      const record = (b.records as Record<string, Record<string, unknown>>[])[1];
      (record.amount as Record<string, unknown>).status = "ambiguous";
    }],
    ["reconciliation difference does not add up", (b) => {
      const recon = (b.measures as Record<string, Record<string, unknown>>).reconciliation;
      (recon.currencies as Record<string, unknown>[])[0].difference_minor = "5";
    }],
    ["reconciled with a non-zero difference", (b) => {
      const recon = (b.measures as Record<string, Record<string, unknown>>).reconciliation;
      const entry = (recon.currencies as Record<string, Record<string, unknown>>[])[0];
      (entry.closing as Record<string, unknown>).minor_units = "1";
    }],
    ["missingness ratio not exact", (b) => {
      const m = (b.measures as Record<string, Record<string, Record<string, Record<string, unknown>>>>).missingness;
      m.fields.date.missing_ratio = { numerator: 1, denominator: 10 };
    }],
    ["coverage count disagrees", (b) => {
      (b.coverage as Record<string, unknown>).records_typed = 3;
    }],
  ];
  it.each(variants)("%s", (_label, mutate) => {
    const body = base();
    expect(acceptAnalysis(body)).not.toBeNull();
    mutate(body);
    expect(acceptAnalysis(body)).toBeNull();
  });

  it("rejects record pages whose offsets contradict their records", () => {
    const page = docBody("document_records_page");
    page.total = 0;
    expect(acceptRecordPage(page)).toBeNull();
    const early = docBody("document_records_page");
    early.next_offset = 10;
    expect(acceptRecordPage(early)).toBeNull();
  });

  it("an unsupported or error document cannot carry records", () => {
    const body = docBody("document_analysis_pdf_truncated_error");
    expect(acceptAnalysis(body)).not.toBeNull();
    body.errors = [];
    expect(acceptAnalysis(body)).toBeNull();
  });
});

describe("values: unknown stays unknown, zero stays zero", () => {
  it("formats signed integer minor units without floats", () => {
    expect(minorToDecimal("0", 2)).toBe("0.00");
    expect(minorToDecimal("-100", 2)).toBe("-1.00");
    expect(minorToDecimal("5", 2)).toBe("0.05");
    expect(minorToDecimal("123456789012345678901234567890", 2)).toBe("1234567890123456789012345678.90");
    expect(minorToDecimal("42", 0)).toBe("42");
    expect(minorToDecimal("42", null)).toBe("42 minor units (exponent unknown)");
  });

  it("shows 0/0 as not applicable and keeps exact denominators", () => {
    expect(ratioText({ numerator: 0, denominator: 0 })).toBe("not applicable (0 of 0)");
    expect(ratioText({ numerator: 0, denominator: 7 })).toBe("0 of 7");
    expect(ratioText({ numerator: 6, denominator: 7 })).toBe("6 of 7");
  });

  it("keeps unknown amounts null and real zero as zero", () => {
    const missing = parsed("document_analysis_missing_values");
    const amounts = missing.records.map((r) => r.amount);
    expect(amounts.every((a) => a === null || a.status === "known" || a.minor_units === null)).toBe(true);
    const usd = parsed("document_analysis_complete_paged");
    const recon = usd.measures?.reconciliation.currencies[0];
    expect(recon?.difference_minor).toBe("0");
    expect(recon?.status).toBe("reconciled");
  });

  it("keeps two currencies separate", () => {
    const two = parsed("document_analysis_two_currency");
    expect(two.measures?.reconciliation.currencies.map((c) => [c.currency, c.status])).toEqual([
      ["EUR", "not_checkable"],
      ["USD", "reconciled"],
    ]);
  });
});

describe("document client", () => {
  function respond(status: number, body: string, type = "application/json") {
    return vi.fn(async () => new Response(body, { status, headers: { "content-type": type } }));
  }

  it("uploads raw bytes with the format media type, no multipart and no filename", async () => {
    const fetchImpl = respond(201, JSON.stringify(docBody("document_upload_csv")));
    const client = createDocumentClient(fetchImpl);
    const file = new File(["Date,Amount\n"], "C:\\private\\statement.csv", { type: "text/csv" });
    const result = await client.upload("tok", file, "csv");
    expect(result.ok).toBe(true);
    const [path, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe("/v1/documents?format=csv");
    expect(init.method).toBe("POST");
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe("text/csv");
    expect(init.body).toBe(file); // the Blob itself: raw bytes
    expect(path).not.toContain("statement");
    expect(JSON.stringify(init.headers)).not.toContain("statement");
  });

  it.each([
    [413, { error: "body_too_large" }, "refused", "body_too_large"],
    [415, { error: "format_mismatch" }, "refused", "format_mismatch"],
    [404, { error: "not_found" }, "refused", "not_found"],
    [403, { error: "permission_denied" }, "refused", "permission_denied"],
    [503, { error: "document_worker_recovery_pending" }, "worker", "document_worker_recovery_pending"],
    [503, { error: "document_worker_busy" }, "worker", "document_worker_busy"],
    [504, { error: "document_worker_timeout" }, "worker", "document_worker_timeout"],
    [502, { error: "document_worker_failed" }, "worker", "document_worker_failed"],
    [503, { error: "document_worker_identity_changed" }, "worker", "document_worker_identity_changed"],
  ])("maps HTTP %i %j", async (status, body, kind, code) => {
    const client = createDocumentClient(respond(status, JSON.stringify(body)));
    const result = await client.analyze("tok", "h_0000000000000000000001", {
      decimal_style: "unspecified", date_order: "iso_only", default_currency: null, records_limit: 100,
    });
    expect(result).toEqual({ ok: false, kind, status, code });
    if (!result.ok) expect(documentMessage(result)).not.toMatch(/tok|Bearer/);
  });

  it.each([
    ["empty 502", 502, "", "application/json"],
    ["non-JSON 500", 500, "<html>Internal Server Error</html>", "text/html"],
    ["unknown 503 code", 503, JSON.stringify({ error: "something_else" }), "application/json"],
    ["malformed JSON 200", 200, "{not json", "application/json"],
    ["200 with the wrong shape", 200, JSON.stringify({ status: "complete" }), "application/json"],
    ["200 as text", 200, JSON.stringify(docBody("document_analysis_complete_paged")), "text/plain"],
  ])("%s is unconfirmed, never a document result", async (_label, status, body, type) => {
    const client = createDocumentClient(respond(status, body, type));
    const result = await client.analyze("tok", "h_0000000000000000000001", {
      decimal_style: "unspecified", date_order: "iso_only", default_currency: null, records_limit: 100,
    });
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.kind).toBe("unconfirmed");
      expect(documentMessage(result)).toContain("did not confirm");
    }
  });

  it("separates network failure from an aborted request", async () => {
    const failing = createDocumentClient(vi.fn(async () => {
      throw new TypeError("network down");
    }));
    const result = await failing.records("tok", "h_0000000000000000000001", 0, 100);
    expect(result).toEqual({ ok: false, kind: "network", status: null, code: null });
    const controller = new AbortController();
    controller.abort();
    const aborted = await failing.records("tok", "h_0000000000000000000001", 0, 100, controller.signal);
    expect(aborted.ok === false && aborted.kind).toBe("aborted");
  });
});

describe("R64 binding of frozen examples to one document", () => {
  const upload = acceptUpload(docBody("document_upload_csv"))!;
  const analysis = parsed("document_analysis_complete_paged");
  const page = acceptRecordPage(docBody("document_records_page"))!;
  const request = { ...analysis.parser.options };

  it("accepts the frozen CSV upload, analysis and page as one document", () => {
    expect(uploadMatches(upload, { size: 547 }, "csv")).toBe(true);
    expect(analysisMatches(analysis, upload, request)).toBe(true);
    // The frozen page was requested at offset 5 with limit 100 (a page of the stored analysis).
    expect(pageMatches(page, analysis, 5, 100)).toBe(true);
    expect(deletionConfirmed(acceptDeleted(docBody("document_deleted"))!, upload.handle_id)).toBe(true);
  });

  it("rejects each contradiction", () => {
    expect(uploadMatches(upload, { size: 1 }, "csv")).toBe(false);
    expect(uploadMatches(upload, { size: 547 }, "pdf")).toBe(false);
    expect(analysisMatches({ ...analysis, source: { ...analysis.source, sha256: "a".repeat(64) } }, upload, request)).toBe(false);
    expect(analysisMatches({ ...analysis, source: { ...analysis.source, size_bytes: 546 } }, upload, request)).toBe(false);
    expect(analysisMatches({ ...analysis, format: "xlsx" }, upload, request)).toBe(false);
    expect(analysisMatches(analysis, upload, { ...request, date_order: "dmy" })).toBe(false);
    expect(analysisMatches(analysis, { ...upload, handle_id: "h_0000000000000000000099" }, request)).toBe(false);
    expect(pageMatches({ ...page, status: "partial" }, analysis, 5, 100)).toBe(false);
    expect(pageMatches({ ...page, total: 9 }, analysis, 5, 100)).toBe(false);
    expect(pageMatches(page, analysis, 0, 100)).toBe(false);
    expect(pageMatches(page, analysis, 5, 5)).toBe(false);
    expect(pageMatches({ ...page, next_offset: 10 }, analysis, 5, 100)).toBe(false);
    expect(deletionConfirmed({ handle_id: upload.handle_id, deleted: false }, upload.handle_id)).toBe(false);
    expect(deletionConfirmed({ handle_id: "h_0000000000000000000099", deleted: true }, upload.handle_id)).toBe(false);
  });
});
