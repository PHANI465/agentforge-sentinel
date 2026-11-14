import { spawn, spawnSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { resolveSuite } from "./suite.mjs";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const runtimeDir = path.join(webRoot, "e2e", ".runtime");
const preservedNames = ["current-run.json", "runtime.json", "recovery.json", "owned-secrets.json"];

// DOC01 Part C: the registered worker environment and a fresh, marker-owned store for the
// documents suite. The production API reads both from its environment (decision 0010).
export const DOC_STORE = path.join(runtimeDir, "doc-store");
const repoRoot = path.resolve(webRoot, "..");
const workerPython = path.join(repoRoot, "tools", "document_worker", ".venv",
  process.platform === "win32" ? "Scripts/python.exe" : "bin/python");

export function prepareDocuments(exists = existsSync, run = spawnSync) {
  if (exists(DOC_STORE)) return { ok: false, reason: "stale_doc_store_needs_recovery" };
  if (!exists(workerPython)) return { ok: false, reason: "document_worker_env_missing" };
  // The venv's own interpreter path, never a resolved symlink (that would lose the venv).
  const init = run(workerPython, ["-I", "-m", "docworker", "init", "--store", DOC_STORE],
    { encoding: "utf8", windowsHide: true, timeout: 120_000 });
  if (init.error || init.status !== 0) return { ok: false, reason: "doc_store_init_failed" };
  return { ok: true, env: { SENTINEL_DOC_WORKER_PYTHON: workerPython, SENTINEL_DOC_STORE: DOC_STORE } };
}

export function planInvocation(dir, exists = existsSync) {
  const preserved = preservedNames.filter((name) => exists(path.join(dir, name)));
  if (preserved.length > 0) return { start: false, reason: "stale_run_needs_recovery", preserved };
  return { start: true, runId: randomBytes(16).toString("hex"), reason: "new_invocation", preserved: [] };
}

function main() {
  const flag = process.argv.indexOf("--suite");
  const suite = resolveSuite(flag === -1 ? undefined : process.argv[flag + 1]);
  const plan = planInvocation(runtimeDir);
  if (!plan.start || !plan.runId) {
    process.stderr.write(`${plan.reason}\n`);
    process.exit(1);
  }
  let documentsEnv = {};
  if (suite === "documents") {
    const prepared = prepareDocuments();
    if (!prepared.ok) {
      process.stderr.write(`${prepared.reason}\n`);
      process.exit(1);
    }
    documentsEnv = prepared.env;
  }
  const child = spawn(
    process.execPath,
    [path.join(webRoot, "node_modules", "@playwright", "test", "cli.js"), "test", "--reporter=line"],
    {
      cwd: webRoot,
      env: { ...process.env, ...documentsEnv, SENTINEL_E2E_RUN_ID: plan.runId, SENTINEL_LIVE_CLAUDE: "0", SENTINEL_E2E_SUITE: suite },
      stdio: "inherit",
      windowsHide: true,
    },
  );
  child.on("exit", (code) => process.exit(code ?? 1));
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main();
