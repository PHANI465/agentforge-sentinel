import { spawn } from "node:child_process";
import { randomBytes } from "node:crypto";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const runtimeDir = path.join(webRoot, "e2e", ".runtime");
const preservedNames = ["current-run.json", "runtime.json", "recovery.json", "owned-secrets.json"];

export function planInvocation(dir, exists = existsSync) {
  const preserved = preservedNames.filter((name) => exists(path.join(dir, name)));
  if (preserved.length > 0) return { start: false, reason: "stale_run_needs_recovery", preserved };
  return { start: true, runId: randomBytes(16).toString("hex"), reason: "new_invocation", preserved: [] };
}

function main() {
  const plan = planInvocation(runtimeDir);
  if (!plan.start || !plan.runId) {
    process.stderr.write(`${plan.reason}\n`);
    process.exit(1);
  }
  const child = spawn(
    process.execPath,
    [path.join(webRoot, "node_modules", "@playwright", "test", "cli.js"), "test", "--reporter=line"],
    {
      cwd: webRoot,
      env: { ...process.env, SENTINEL_E2E_RUN_ID: plan.runId, SENTINEL_LIVE_CLAUDE: "0" },
      stdio: "inherit",
      windowsHide: true,
    },
  );
  child.on("exit", (code) => process.exit(code ?? 1));
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main();
