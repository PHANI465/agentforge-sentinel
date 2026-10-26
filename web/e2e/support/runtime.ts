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
