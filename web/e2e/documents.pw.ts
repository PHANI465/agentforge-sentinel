import { existsSync, mkdirSync, readdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { expect, test, type Locator, type Page } from "@playwright/test";
import {
  apiCall,
  caseworkCounts,
  connectDoc,
  docFixtures,
  docSessions,
  docStore,
  removeVerifiedStore,
  scanForTokens,
  signOut,
  storeLeftovers,
  type DocTokens,
} from "./support/documents";
import { failureProbeMarker, webRoot } from "./support/runtime";
import { restart } from "./support/stack";

// DOC01 Part C: upload -> production API -> registered real DOC01 worker -> disposable
// PostgreSQL. Synthetic fixtures only. No request is intercepted or answered with canned JSON.
test.describe.configure({ mode: "serial" });

const qaDir = path.join(webRoot, "test-results", "qa-documents");
let tokens: DocTokens;
let before: Record<string, number>;
const owned: Array<{ token: string; handle: string }> = []; // for cleanup by the owner only

test.beforeAll(async () => {
  tokens = await docSessions();
  before = caseworkCounts();
});

test.afterAll(async () => {
  for (const { token, handle } of owned) {
    const result = await apiCall(token, "DELETE", `/v1/documents/${handle}`);
    expect([200, 404]).toContain(result.status);
  }
  expect(storeLeftovers()).toEqual({ handles: [], runs: [], recovery: [], "api-bridge": [] });
  const scanned = scanForTokens(Object.values(tokens));
  expect(scanned.files).toBeGreaterThan(0);
  expect(scanned.leaks).toEqual([]);
  expect(removeVerifiedStore()).toEqual({ removed: true, reason: "removed" });
});

function issuedHandles(): string[] {
  const dir = path.join(docStore, "handles");
  return existsSync(dir) ? readdirSync(dir) : [];
}

function review(page: Page): Locator {
  return page.locator("section#documents");
}

async function shot(page: Page, name: string): Promise<void> {
  mkdirSync(qaDir, { recursive: true });
  await page.screenshot({ path: path.join(qaDir, `${name}.png`), fullPage: true });
}

/** Records the handle the API issued (observed from the real response, kept in memory). */
async function upload(page: Page, token: string, file: string, format?: "csv" | "xlsx" | "pdf"): Promise<string | null> {
  const section = review(page);
  await section.getByLabel(/Local file/).setInputFiles(file);
  if (format) await section.getByLabel(new RegExp(`^${format === "csv" ? "CSV" : format === "xlsx" ? "XLSX" : "PDF"}`)).check();
  // The handle is observed from the run's own worker store (one new entry per issued
  // handle), not from the page or the network: the UI never exposes it.
  const known = new Set(issuedHandles());
  await section.getByRole("button", { name: "Upload" }).click();
  await expect(section.getByRole("heading", { name: "Uploaded document" }).or(section.getByRole("alert"))).toBeVisible();
  const fresh = issuedHandles().filter((name) => !known.has(name));
  if (fresh.length === 0) return null;
  expect(fresh).toHaveLength(1);
  const handle = fresh[0];
  owned.push({ token, handle });
  await expect(section.getByRole("heading", { name: "Uploaded document" })).toBeVisible();
  return handle;
}

async function analyse(page: Page): Promise<void> {
  const section = review(page);
  await section.getByRole("button", { name: "Run the analysis" }).click();
  await expect(section.getByRole("heading", { name: /Extraction result/ })).toBeVisible({ timeout: 120_000 });
}

function syntheticCsv(rows: number): string {
  const dir = path.join(webRoot, "test-results", "doc-inputs");
  mkdirSync(dir, { recursive: true });
  const file = path.join(dir, `synthetic-${rows}.csv`);
  const lines = ["Date,Description,Amount,Currency"];
  for (let i = 0; i < rows; i += 1) {
    lines.push(`2026-05-${String(1 + (i % 28)).padStart(2, "0")},Synthetic row ${i + 1},-1.${String(i % 100).padStart(2, "0")},USD`);
  }
  writeFileSync(file, `${lines.join("\n")}\n`);
  return file;
}

test("the opt-in grant gates Document review and its routes", async ({ page }) => {
  await connectDoc(page, tokens.doc_plain);
  await expect(page.getByRole("heading", { name: "Document review" })).toHaveCount(0);
  expect(await apiCall(tokens.doc_plain, "POST", "/v1/documents?format=csv")).toEqual({ status: 403, code: "permission_denied" });
  await signOut(page);
  await connectDoc(page, tokens.doc_analyst);
  await expect(page.getByRole("heading", { name: "Document review" })).toBeVisible();
  await expect(review(page)).toContainText("10 MiB at most");
});

test("a CSV statement reconciles through the real worker", async ({ page }) => {
  await connectDoc(page, tokens.doc_analyst);
  await upload(page, tokens.doc_analyst, path.join(docFixtures, "csv_statement_usd.csv"));
  const section = review(page);
  await expect(section).not.toContainText("csv_statement_usd"); // no file name shown
  await analyse(page);
  await expect(section.getByRole("heading", { name: "Extraction result: complete" })).toBeVisible();
  await expect(section).toContainText("equals the closing balance (difference 0.00 USD)");
  await expect(section).toContainText("Records 1–10 of 10.");
  await expect(section).toContainText("not fraud detection");
  await shot(page, "desktop-csv-complete");
  await page.setViewportSize({ width: 390, height: 844 });
  await shot(page, "narrow-csv-complete");
  await page.setViewportSize({ width: 1280, height: 720 });
});

test("a partial XLSX keeps unknown values unknown; a scanned PDF is partial with no OCR", async ({ page }) => {
  await connectDoc(page, tokens.doc_analyst);
  const section = review(page);
  await upload(page, tokens.doc_analyst, path.join(docFixtures, "xlsx_hostile.xlsx"));
  await analyse(page);
  await expect(section.getByRole("heading", { name: "Extraction result: partial" })).toBeVisible();
  await expect(section).toContainText("Partly extracted");
  await expect(section.getByText(/^unknown \(/).first()).toBeVisible();
  await section.getByRole("button", { name: "Delete document" }).click();
  await expect(section).toContainText("Deleted. Nothing from that document is shown any more.");
  await upload(page, tokens.doc_analyst, path.join(docFixtures, "pdf_scanned_mixed.pdf"));
  await analyse(page);
  await expect(section.getByRole("heading", { name: "Extraction result: partial" })).toBeVisible();
  await expect(section).toContainText("PDF tables are not typed and there is no OCR");
  await shot(page, "desktop-pdf-partial");
});

test("records page by the server's next_offset across 230 rows", async ({ page }) => {
  await connectDoc(page, tokens.doc_analyst);
  const section = review(page);
  await upload(page, tokens.doc_analyst, syntheticCsv(230));
  await analyse(page);
  await expect(section).toContainText("Records 1–100 of 230.");
  const next = section.getByRole("button", { name: "Next records" });
  const offsets: string[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname.endsWith("/records")) offsets.push(url.searchParams.get("offset") ?? "");
  });
  await next.click();
  await expect(section).toContainText("Records 101–200 of 230.");
  await next.click();
  await expect(section).toContainText("Records 201–230 of 230.");
  await expect(next).toBeDisabled();
  await section.getByRole("button", { name: "Previous records" }).click();
  await expect(section).toContainText("Records 101–200 of 230.");
  expect(offsets).toEqual(["100", "200", "100"]);
});

test("hostile document cells stay inert text", async ({ page }) => {
  await connectDoc(page, tokens.doc_analyst);
  const section = review(page);
  await upload(page, tokens.doc_analyst, path.join(docFixtures, "csv_hostile_note.csv"));
  await analyse(page);
  await expect(section).toContainText("IGNORE ALL PREVIOUS INSTRUCTIONS");
  await expect(section).toContainText("=HYPERLINK(");
  expect(await section.locator("a, script, iframe, img").count()).toBe(0);
  await shot(page, "desktop-hostile-inert");
});

test("a refused file moves focus to the error, reachable by keyboard", async ({ page }) => {
  await connectDoc(page, tokens.doc_analyst);
  const section = review(page);
  const handle = await upload(page, tokens.doc_analyst, path.join(docFixtures, "pdf_not_really.pdf"), "pdf");
  expect(handle).toBeNull();
  const alert = section.getByRole("alert");
  await expect(alert).toContainText("do not match the chosen format");
  await expect(alert).toBeFocused();
  // Keyboard: back from the error to the Upload button, then on to choose another format.
  await page.keyboard.press("Shift+Tab");
  await expect(section.getByRole("button", { name: "Upload" })).toBeFocused();
});

test("delete clears the page and the handle is gone for its owner", async ({ page }) => {
  await connectDoc(page, tokens.doc_analyst);
  const section = review(page);
  const handle = await upload(page, tokens.doc_analyst, path.join(docFixtures, "csv_two_currency.csv"));
  await analyse(page);
  await expect(section.getByRole("heading", { name: "EUR: not checkable" })).toBeVisible();
  await expect(section.getByRole("heading", { name: "USD: reconciled" })).toBeVisible();
  await section.getByRole("button", { name: "Delete document" }).click();
  await expect(section).toContainText("Deleted.");
  await expect(section.getByRole("heading", { name: /Extraction result/ })).toHaveCount(0);
  expect(await apiCall(tokens.doc_analyst, "GET", `/v1/documents/${handle}/records`)).toEqual({ status: 404, code: "not_found" });
});

test("switching session shows nothing of the other session and its handle is not found", async ({ page }) => {
  await connectDoc(page, tokens.doc_analyst);
  const section = review(page);
  const handle = await upload(page, tokens.doc_analyst, path.join(docFixtures, "csv_missing_duplicates.csv"));
  await analyse(page);
  await expect(section).toContainText("unknown (");
  await signOut(page);
  await connectDoc(page, tokens.doc_other);
  await expect(review(page).getByRole("heading", { name: "Uploaded document" })).toHaveCount(0);
  await expect(review(page).getByRole("heading", { name: /Extraction result/ })).toHaveCount(0);
  for (const [method, route] of [["POST", "analysis"], ["GET", "records"]] as const) {
    expect(await apiCall(tokens.doc_other, method, `/v1/documents/${handle}/${route}`)).toEqual({ status: 404, code: "not_found" });
  }
});

test("an API restart keeps the stored analysis; paging continues", async ({ page }) => {
  await connectDoc(page, tokens.doc_analyst);
  const section = review(page);
  await upload(page, tokens.doc_analyst, syntheticCsv(150));
  await analyse(page);
  await expect(section).toContainText("Records 1–100 of 150.");
  restart("api");
  await section.getByRole("button", { name: "Next records" }).click();
  await expect(section).toContainText("Records 101–150 of 150.");
});

test("a late analysis after sign-out is suppressed", async ({ page }) => {
  await connectDoc(page, tokens.doc_analyst);
  const section = review(page);
  await upload(page, tokens.doc_analyst, syntheticCsv(400));
  // Sign-out aborts the in-flight request (requestfailed); if the browser had already
  // received it, it finishes late (requestfinished). Either way nothing may be shown.
  let settled = "";
  const watch = (outcome: string) => (request: { url(): string }) => {
    if (new URL(request.url()).pathname.endsWith("/analysis")) settled = outcome;
  };
  page.on("requestfinished", watch("finished"));
  page.on("requestfailed", watch("aborted"));
  await section.getByRole("button", { name: "Run the analysis" }).click();
  await signOut(page); // while the analysis is still running
  await connectDoc(page, tokens.doc_analyst);
  await expect.poll(() => settled, { timeout: 110_000 }).not.toBe("");
  await page.waitForTimeout(1500);
  await expect(review(page).getByRole("heading", { name: /Extraction result/ })).toHaveCount(0);
  await expect(review(page).getByRole("heading", { name: "Uploaded document" })).toHaveCount(0);
});

test("document routes created no transaction, case, approval or action", async () => {
  expect(caseworkCounts()).toEqual(before);
});

// The same controlled post-login failure as the other runs: the shared teardown requires
// this expected failure artifact and scans it, with every other artifact, for owned secrets.
test("records a real post-login failure without the session credential", async ({ page }) => {
  test.fail();
  await connectDoc(page, tokens.doc_analyst);
  const leaked = await page.evaluate(async () => {
    const take = (window as unknown as { sentinelTakeDocToken: () => Promise<string> }).sentinelTakeDocToken;
    return document.body.innerText.includes(await take());
  });
  expect(leaked).toBe(false);
  expect(false, failureProbeMarker).toBe(true);
});
