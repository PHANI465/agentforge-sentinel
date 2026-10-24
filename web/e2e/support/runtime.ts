import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const supportDir = path.dirname(fileURLToPath(import.meta.url));

export const webRoot = path.resolve(supportDir, "../..");
export const repoRoot = path.resolve(webRoot, "..");
export const runtimeDir = path.join(webRoot, "e2e", ".runtime");
export const runtimePath = path.join(runtimeDir, "runtime.json");

export type RuntimeFile = {
  manifestPath: string;
  baseURL: string;
  apiOrigin: string;
  vitePid: number;
};

export function readRuntime(): RuntimeFile {
  return JSON.parse(readFileSync(runtimePath, "utf8")) as RuntimeFile;
}
