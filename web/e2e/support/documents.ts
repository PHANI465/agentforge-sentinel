import { spawnSync } from "node:child_process";
import { writeFileSync } from "node:fs";
import path from "node:path";
import { expect, type Page } from "@playwright/test";
import * as artifacts from "./docArtifacts";
import { readRuntime, repoRoot, runtimeDir, waitForRuntime, webRoot } from "./runtime";

/** DOC01 Part C: helpers for the documents suite. Tokens stay in this process's memory; the
 * page receives one through a binding, never through a URL, storage or a log. */

export const docFixtures = path.join(repoRoot, "tools", "document_worker", "fixtures");
export const docStore = path.join(runtimeDir, "doc-store");
export type DocRole = "doc_analyst" | "doc_other" | "doc_plain";
export type DocTokens = Record<DocRole, string>;

function childEnv(): NodeJS.ProcessEnv {
  const env: NodeJS.ProcessEnv = { ...process.env, SENTINEL_LIVE_CLAUDE: "0" };
  delete env.VIRTUAL_ENV;
  delete env.SENTINEL_TEST_DATABASE_URL;
  return env;
}

function redact(text: string): string {
  return text.replace(/postgresql:\/\/\S+/gi, "[dsn]").replace(/Bearer\s+\S+/gi, "Bearer [redacted]");
}

function helper(command: "sessions" | "counts"): unknown {
  const result = spawnSync(
    "uv",
    ["run", "--locked", "--extra", "dev", "--extra", "ml", "python", "tests/support/doc01_browser.py", command,
      "--manifest", readRuntime().manifestPath],
    { cwd: repoRoot, encoding: "utf8", windowsHide: true, env: childEnv(), timeout: 180_000 },
  );
  if (result.error || result.status !== 0) {
    // stderr only: stdout of `sessions` carries tokens.
    writeFileSync(path.join(runtimeDir, "last-command.txt"), redact(result.stderr || ""));
    throw new Error(`doc01_browser ${command} exited ${result.status ?? "missing"}`);
  }
  return JSON.parse(result.stdout) as unknown;
}

export async function docSessions(): Promise<DocTokens> {
  await waitForRuntime();
  return helper("sessions") as DocTokens;
}

export function caseworkCounts(): Record<string, number> {
  return helper("counts") as Record<string, number>;
}

const pageTokens = new WeakMap<Page, { token: string }>();

/** Sign in with an explicit document-session token (kept in this process). */
export async function connectDoc(page: Page, token: string): Promise<void> {
  if (!page.url().startsWith("http")) await page.goto("/");
  const holder = pageTokens.get(page);
  if (holder) holder.token = token;
  else {
    const current = { token };
    await page.exposeBinding("sentinelTakeDocToken", async () => current.token);
    pageTokens.set(page, current);
  }
  await page.getByLabel("Session token").waitFor();
  const filled = await page.evaluate(async () => {
    const input = document.querySelector('input[name="session-token"]');
    if (!(input instanceof HTMLInputElement)) return "missing";
    const take = (window as unknown as { sentinelTakeDocToken: () => Promise<string> }).sentinelTakeDocToken;
    const value = await take();
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
    if (!setter) return "missing";
    setter.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
    return input.value.length > 0 ? "set" : "empty";
  });
  if (filled !== "set") throw new Error("session field was not set");
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page.getByRole("heading", { name: "Case queue" })).toBeVisible();
}

export async function signOut(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByLabel("Session token")).toBeVisible();
}

/** A direct API call from this test process (never through the browser). */
export async function apiCall(
  token: string,
  method: string,
  apiPath: string,
): Promise<{ status: number; code: string | null }> {
  const uploading = method === "POST" && apiPath.startsWith("/v1/documents?");
  const analysing = method === "POST" && apiPath.endsWith("/analysis");
  const response = await fetch(`${readRuntime().apiOrigin}${apiPath}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/json",
      ...(uploading ? { "Content-Type": "text/csv" } : analysing ? { "Content-Type": "application/json" } : {}),
    },
    body: uploading ? "Date,Amount\n2026-01-01,1.00\n" : analysing ? "{}" : undefined,
  });
  let code: string | null = null;
  try {
    const body = (await response.json()) as { error?: unknown };
    code = typeof body.error === "string" ? body.error : null;
  } catch {
    code = null;
  }
  return { status: response.status, code };
}

/** Owned store contents that must be empty after the suite. */
export function storeLeftovers(): Record<string, string[]> | null {
  return artifacts.storeLeftovers(docStore);
}

/** Remove the store only when its whole tree is the owned, marker-bearing, empty layout
 * (see docArtifacts.ts). Anything unexpected is left in place as recovery evidence. */
export function removeVerifiedStore(): artifacts.StoreVerdict {
  return artifacts.removeVerifiedStore(docStore, runtimeDir);
}

/** Scan this run's test results, runtime files and the stack's own artifacts for the given
 * tokens while the stack still exists. Reports relative names only, never content. */
export function scanForTokens(tokens: string[]): { files: number; leaks: string[]; problems: string[] } {
  const runtime = readRuntime();
  return artifacts.scanForTokens(tokens, { webRoot, runtimeDir, stackDir: runtime.stackDir, secretsPath: runtime.secretsPath });
}

/** The stack directory of the current run (for the test-owned canary only). */
export function currentStackDir(): string {
  return readRuntime().stackDir;
}
