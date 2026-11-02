import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const supportDir = path.dirname(fileURLToPath(import.meta.url));

export const webRoot = path.resolve(supportDir, "../..");
export const repoRoot = path.resolve(webRoot, "..");
export const runtimeDir = path.join(webRoot, "e2e", ".runtime");
export const runtimePath = path.join(runtimeDir, "runtime.json");

export const failureProbeMarker = "controlled post-login failure probe";

export type ProcessIdentity = {
  pid: number;
  creation: string;
  executable: string;
  commandLine: string;
  script?: string;
};

export type RuntimeFile = {
  runId: string;
  manifestPath: string;
  stackDir: string;
  secretsPath: string;
  baseURL: string;
  apiOrigin: string;
  api: ProcessIdentity & { port: number };
  database: { port: number };
  vite: ProcessIdentity & { script: string };
};

export function readRuntime(): RuntimeFile {
  return JSON.parse(readFileSync(runtimePath, "utf8")) as RuntimeFile;
}

/** serve.mjs writes runtime.json only after it has captured the Vite and API process
 * identities, which can be seconds after Vite already answers Playwright's readiness probe.
 * Anything that reads the run record at the start of a run waits for this invocation's. */
export async function waitForRuntime(timeoutMs = 60_000): Promise<void> {
  const runId = process.env.SENTINEL_E2E_RUN_ID ?? "";
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      if (readRuntime().runId === runId) return;
    } catch {
      // not written yet
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error("runtime_not_recorded");
}
