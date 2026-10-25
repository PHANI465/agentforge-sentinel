import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { randomBytes } from "node:crypto";
import { evaluateScan } from "./scan-artifacts.mjs";
import {
  executeViteAction,
  planOwnedShutdown,
  recoveryDocument,
} from "./process-identity.mjs";

const script = "E:/PHANI/sentinel-wt/cursor-browser-e2e/web/node_modules/vite/bin/vite.js";
const foreignScript = "E:/ANOTHER-WORKSPACE/node_modules/vite/bin/vite.js";
const executable = "C:/Program Files/nodejs/node.exe";
const creation = "2026-10-24T16:00:00.000Z";
const commandLine = `"${executable}" ${script} --host 127.0.0.1 --port 5173 --strictPort`;
const expected = { pid: 424242, creation, executable, script, commandLine };
const currentRunId = "a".repeat(32);
const names = [];

function check(name, value) {
  names.push(name);
  assert.equal(value, true, name);
}

function intercepted(plan) {
  const commands = [];
  const run = (command) => {
    commands.push(command);
    return { status: 0, stdout: "" };
  };
  if (plan.kill) executeViteAction(plan.vite, run);
  if (plan.stop) run("uv");
  return commands;
}

const owned = {
  pid: 424242,
  creation,
  executable,
  commandLine,
  available: true,
  found: true,
};
const foreign = {
  available: true,
  found: true,
  creation,
  executable,
  commandLine: `"${executable}" ${foreignScript} --port 49001`,
};
const reused = { ...owned, creation: "2026-10-24T18:00:00.000Z" };

const foreignPlan = planOwnedShutdown({
  currentRunId,
  runtimeRunId: currentRunId,
  childExited: false,
  expected,
  observed: foreign,
});
check("foreign_vite_not_killed", foreignPlan.kill === false && foreignPlan.vite.reason === "command_mismatch");
check("foreign_vite_no_taskkill", !intercepted(foreignPlan).includes("taskkill"));

const reusedPlan = planOwnedShutdown({
  currentRunId,
  runtimeRunId: currentRunId,
  childExited: false,
  expected,
  observed: reused,
});
check("reused_pid_not_killed", reusedPlan.kill === false && reusedPlan.vite.reason === "creation_mismatch");
check("reused_pid_no_destructive_kill", intercepted(reusedPlan).every((command) => command !== "taskkill"));

const missingPlan = planOwnedShutdown({
  currentRunId,
  runtimeRunId: currentRunId,
  childExited: false,
  expected: { pid: 424242 },
  observed: owned,
});
check("missing_identity_not_killed", missingPlan.kill === false && missingPlan.vite.reason === "identity_missing");
check("missing_identity_no_taskkill", !intercepted(missingPlan).includes("taskkill"));

const unavailablePlan = planOwnedShutdown({
  currentRunId,
  runtimeRunId: currentRunId,
  childExited: false,
  expected,
  observed: { available: false, reason: "query_failed" },
});
check("unavailable_identity_not_killed", unavailablePlan.kill === false && unavailablePlan.retainRecovery === true);

const exitedPlan = planOwnedShutdown({
  currentRunId,
  runtimeRunId: currentRunId,
  childExited: true,
  expected,
  observed: owned,
});
check("exited_child_not_killed", exitedPlan.kill === false && exitedPlan.vite.reason === "child_exited");
check("exited_child_no_taskkill", !intercepted(exitedPlan).includes("taskkill"));

const stalePlan = planOwnedShutdown({
  currentRunId,
  runtimeRunId: "b".repeat(32),
  childExited: false,
  expected,
  observed: owned,
});
check("stale_runtime_not_authority", stalePlan.stop === false && stalePlan.kill === false && stalePlan.reason === "stale_runtime");
check("stale_runtime_no_destructive_command", intercepted(stalePlan).length === 0);

const failedStop = planOwnedShutdown({
  currentRunId,
  runtimeRunId: currentRunId,
  childExited: true,
  expected,
  observed: { available: true, found: false },
  stopReport: { ok: false, errors: ["stop command failed"] },
});
check("failed_stop_retains_recovery", failedStop.stop === true && failedStop.retainRecovery === true && failedStop.stopResult.reason === "stop_incomplete");

const matched = planOwnedShutdown({
  currentRunId,
  runtimeRunId: currentRunId,
  childExited: false,
  expected,
  observed: owned,
  stopReport: { ok: true },
});
const matchedCommands = [];
executeViteAction(matched.vite, (command) => {
  matchedCommands.push(command);
  return { status: 0, stdout: "" };
});
check("owned_identity_is_the_only_taskkill", matched.kill === true && matchedCommands.length === 1 && matchedCommands[0] === "taskkill");
const failedKill = executeViteAction(matched.vite, () => ({ status: 1, stdout: "" }));
check("taskkill_failure_is_not_success", failedKill.killed === false && failedKill.reason === "taskkill_failed");

const secret = `SYNTHETIC_U02_${randomBytes(8).toString("hex")}`;
const recovery = recoveryDocument({
  runId: currentRunId,
  reasons: ["stop_incomplete"],
  manifestPath: "E:/owned/stack.json",
  vitePid: 424242,
  stackDir: "E:/owned/stack",
});
check("recovery_has_no_secret_fields", !JSON.stringify(recovery).includes(secret) && !("secrets" in recovery) && !("database_url" in recovery));

const root = mkdtempSync(path.join(tmpdir(), "sentinel-shutdown-"));
try {
  const results = path.join(root, "test-results");
  const privateDir = path.join(root, "state", "sentinel-browser-owned");
  const artifactStacks = path.join(results, "stacks");
  mkdirSync(artifactStacks, { recursive: true });
  mkdirSync(privateDir, { recursive: true });
  writeFileSync(path.join(results, "error-context.md"), `${secret}\n`);
  const absentManifest = evaluateScan({
    dirs: [results],
    secrets: [secret],
    exclude: [privateDir],
    requireSecrets: true,
  });
  check("retained_secret_detects_canary_without_manifest", absentManifest.result === "fail" && absentManifest.hits > 0);

  rmSync(path.join(results, "error-context.md"));
  writeFileSync(path.join(artifactStacks, "error-context.md"), `${secret}\n`);
  const nested = evaluateScan({
    dirs: [results],
    secrets: [secret],
    exclude: [privateDir],
    requireSecrets: true,
  });
  check("artifact_stacks_directory_is_scanned", nested.result === "fail" && nested.hits > 0);

  writeFileSync(path.join(privateDir, "manifest.json"), `${secret}\n`);
  const onlyPrivate = evaluateScan({
    dirs: [path.join(root, "state")],
    secrets: [secret],
    exclude: [privateDir],
    requireSecrets: true,
  });
  check("exact_private_directory_is_excluded", onlyPrivate.result === "pass" && onlyPrivate.hits === 0);

  writeFileSync(path.join(root, "blocked.txt"), "plain\n");
  const unreadable = evaluateScan({ dirs: [path.join(root, "blocked.txt")], secrets: [secret], requireSecrets: true });
  check("unreadable_scan_is_not_clean", unreadable.result === "fail" && unreadable.code === "unreadable");
  const emptySecrets = evaluateScan({ dirs: [results], secrets: [], requireSecrets: true });
  check("empty_secret_set_is_not_clean", emptySecrets.result === "fail" && emptySecrets.code === "secrets_unavailable" && emptySecrets.hits !== 0);
} finally {
  rmSync(root, { recursive: true, force: true });
}

process.stdout.write(`${JSON.stringify({ result: "pass", checks: names.length })}\n`);
