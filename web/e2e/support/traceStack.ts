import { spawnSync } from "node:child_process";
import { writeFileSync } from "node:fs";
import path from "node:path";
import { readRuntime, repoRoot, runtimeDir } from "./runtime";
export { waitForRuntime } from "./runtime";

/** G3C-B trace fixtures (tests/support/g3c_trace_browser.py): seeded through the real
 * service/coordinator as the stack's runtime role; the CLI prints identifiers and counts. */
export type TraceScenario =
  | "recommend"
  | "abstain_challenge"
  | "repeat_failure"
  | "zero_roles"
  | "running"
  | "overdue"
  | "retry"
  | "hostile_note"
  | "open_three_role";

export type TraceCounts = {
  case_state: string;
  case_revision: number;
  workflow_ids: string[];
  workflow_statuses: string[];
  terminal_by: Array<string | null>;
  steps: number;
  runs: number;
  intents: number;
  approvals: number;
  actions: number;
  audit: number;
};

export type SeededTrace = TraceCounts & { scenario: TraceScenario; case_id: string; external_id: string };

function childEnv(): NodeJS.ProcessEnv {
  const env: NodeJS.ProcessEnv = { ...process.env, SENTINEL_LIVE_CLAUDE: "0" };
  delete env.VIRTUAL_ENV;
  delete env.SENTINEL_TEST_DATABASE_URL;
  return env;
}

function redact(text: string): string {
  return text.replace(/postgresql:\/\/\S+/gi, "[dsn]").replace(/Bearer\s+\S+/gi, "Bearer [redacted]");
}

function run(args: string[]): unknown {
  const result = spawnSync(
    "uv",
    ["run", "--locked", "--extra", "dev", "--extra", "ml", "python", "tests/support/g3c_trace_browser.py", ...args,
      "--manifest", readRuntime().manifestPath],
    { cwd: repoRoot, encoding: "utf8", windowsHide: true, env: childEnv(), timeout: 180_000 },
  );
  if (result.error || result.status !== 0) {
    writeFileSync(path.join(runtimeDir, "last-command.txt"), redact(`${result.stderr || ""}\n${result.stdout || ""}`));
    throw new Error(`trace ${args[0]} exited ${result.status ?? "missing"}`);
  }
  return JSON.parse(result.stdout) as unknown;
}

export function seedTrace(scenario: TraceScenario, ordinal: number): SeededTrace {
  return run(["seed", "--scenario", scenario, "--ordinal", String(ordinal)]) as SeededTrace;
}

export function inspectTrace(caseId: string): TraceCounts {
  return run(["inspect", "--case-id", caseId]) as TraceCounts;
}
