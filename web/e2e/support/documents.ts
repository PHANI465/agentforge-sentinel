import { spawnSync } from "node:child_process";
import { existsSync, lstatSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";
import { expect, type Page } from "@playwright/test";
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
  if (!existsSync(docStore)) return null;
  const out: Record<string, string[]> = {};
  for (const sub of ["handles", "runs", "recovery", "api-bridge"]) {
    const dir = path.join(docStore, sub);
    out[sub] = existsSync(dir) ? readdirSync(dir) : [];
  }
  return out;
}

/** Remove the store only when it is the owned, marker-bearing, empty run store. */
export function removeVerifiedStore(): { removed: boolean; reason: string } {
  if (!existsSync(docStore)) return { removed: false, reason: "store_missing" };
  if (lstatSync(docStore).isSymbolicLink()) return { removed: false, reason: "store_is_a_link" };
  if (path.dirname(path.resolve(docStore)) !== path.resolve(runtimeDir)) return { removed: false, reason: "store_outside_runtime" };
  if (!existsSync(path.join(docStore, ".docworker-store"))) return { removed: false, reason: "store_marker_missing" };
  const left = storeLeftovers();
  if (!left || Object.values(left).some((entries) => entries.length > 0)) return { removed: false, reason: "store_not_empty" };
  rmSync(docStore, { recursive: true, force: false });
  return { removed: true, reason: "removed" };
}

/** Scan this run's artifacts for the document-session tokens (the stack's own tokens are
 * scanned by the shared teardown). Reports the relative names of files that contain one,
 * never their content, so a leak can be located. */
export function scanForTokens(tokens: string[]): { files: number; leaks: string[] } {
  if (tokens.length === 0 || tokens.some((token) => token.length < 16)) throw new Error("scan_secrets_missing");
  const runtime = readRuntime();
  const skip = [runtime.stackDir, runtime.secretsPath].filter((item) => item.length > 0).map((item) => path.resolve(item));
  const roots = [path.join(webRoot, "test-results"), runtimeDir];
  const leaks: string[] = [];
  let files = 0;
  const pending = roots.filter((root) => existsSync(root));
  while (pending.length > 0) {
    const current = pending.pop() as string;
    if (skip.some((item) => path.resolve(current) === item || path.resolve(current).startsWith(item + path.sep))) continue;
    for (const entry of readdirSync(current, { withFileTypes: true })) {
      const full = path.join(current, entry.name);
      if (entry.isSymbolicLink()) throw new Error("scan_symlink");
      if (entry.isDirectory()) {
        pending.push(full);
        continue;
      }
      if (skip.includes(path.resolve(full))) continue;
      files += 1;
      const bytes = readFileSync(full);
      if (tokens.some((token) => bytes.includes(token))) leaks.push(path.relative(webRoot, full));
    }
  }
  return { files, leaks };
}
