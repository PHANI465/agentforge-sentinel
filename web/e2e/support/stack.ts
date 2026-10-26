import { spawnSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { repoRoot, readRuntime, runtimeDir } from "./runtime";

export type ScenarioRecord = {
  case_id: string;
  transaction_id: string;
  intent_id?: string;
  approval_id?: string;
  action_id?: string;
  idempotency_key?: string;
  session: string;
  state: string;
  revision: number;
};

export type InspectedCase = {
  case_id: string;
  case_state: string;
  case_revision: number;
  transaction_id: string | null;
  external_id: string | null;
  action_count: number;
  action_ids: string[];
  intent_count: number;
  approval_count: number;
  consumed_approval_count: number;
  failed_run_count: number;
  run_count: number;
  failure_codes: string[];
  audit_total: number;
  audit_counts: Record<string, number>;
  proposals: Array<{
    revision: number;
    operation: string | null;
    reason_code: string | null;
    transaction_id: string | null;
    amount_minor: number | null;
  }>;
};

type Manifest = {
  api: { base_url: string; port: number; pid: number; scorer?: string; start_time?: string | number; database_user?: string };
  database: { port: number };
  database_url?: string;
  model_fixtures?: boolean;
  tokens: Record<string, string>;
  scenarios: Record<string, ScenarioRecord>;
};

export type SessionRole = "analyst" | "other_session" | "read_only" | "second_actor" | "ingest_only";

export type StoredPresence = {
  external_id: string;
  transactions: number;
  scoring_outcomes: number;
  alerts: number;
  cases: number;
};

export type StoredScoring = {
  external_id: string;
  case_id: string | null;
  scoring_kind: string | null;
  score_semantics: string | null;
  score: number | null;
  threshold: number | null;
  alerted: boolean | null;
  scorer_name: string | null;
  scorer_version: string | null;
  scorer_sha256: string | null;
  features_sha256: string | null;
  threshold_policy_sha256: string | null;
  model_candidate: string | null;
  model_artifact_sha256: string | null;
  model_results_id: string | null;
  input_currency: string | null;
  profile_home_currency: string | null;
  profile_opened_at: string | null;
  history_rows: number | null;
  disclosures_used: number | null;
  feature_values: Record<string, number> | null;
};

const uvPython = ["run", "--locked", "--extra", "dev", "--extra", "ml", "python"];

function childEnv(): NodeJS.ProcessEnv {
  const env: NodeJS.ProcessEnv = { ...process.env, SENTINEL_LIVE_CLAUDE: "0" };
  delete env.VIRTUAL_ENV;
  delete env.SENTINEL_TEST_DATABASE_URL;
  return env;
}

function redact(text: string): string {
  return text.replace(/postgresql:\/\/\S+/gi, "[dsn]").replace(/Bearer\s+\S+/gi, "Bearer [redacted]");
}

function run(args: string[]): { status: number; stdout: string } {
  const result = spawnSync("uv", [...uvPython, "tests/support/browser_stack.py", ...args], {
    cwd: repoRoot,
    encoding: "utf8",
    windowsHide: true,
    env: childEnv(),
    timeout: 180_000,
  });
  if (result.error || result.status !== 0) {
    writeFileSync(path.join(runtimeDir, "last-command.txt"), redact(`${result.stderr || ""}\n${result.stdout || ""}`));
    throw new Error(`stack ${args[0]} exited ${result.status ?? "missing"}`);
  }
  return { status: result.status, stdout: result.stdout };
}

export function readManifest(): Manifest {
  return JSON.parse(readFileSync(readRuntime().manifestPath, "utf8")) as Manifest;
}

export function scenario(name: string): ScenarioRecord {
  const record = readManifest().scenarios[name];
  if (!record) throw new Error(`missing scenario ${name}`);
  return record;
}

export function tokenFor(role: SessionRole): string {
  const token = readManifest().tokens[role];
  if (!token) throw new Error(`missing session ${role}`);
  return token;
}

export function seed(name: string, ordinal: number): ScenarioRecord {
  const result = run(["seed", "--manifest", readRuntime().manifestPath, "--scenario", name, "--ordinal", String(ordinal)]);
  return JSON.parse(result.stdout) as ScenarioRecord;
}

export function restart(kind: "api" | "db"): void {
  run([kind === "api" ? "restart-api" : "restart-db", "--manifest", readRuntime().manifestPath]);
}

export function restartApi(scorer: "rule" | "model"): { pid: number; scorer: string; startTime: string } {
  run(["restart-api", "--manifest", readRuntime().manifestPath, "--scorer", scorer]);
  const api = readManifest().api;
  if (!Number.isInteger(api.pid) || !api.scorer || !api.start_time) throw new Error("restart did not record api identity");
  return { pid: api.pid, scorer: api.scorer, startTime: String(api.start_time) };
}

export function stackStatus(): { api: string; database: string } {
  const result = run(["status", "--manifest", readRuntime().manifestPath]);
  return JSON.parse(result.stdout) as { api: string; database: string };
}

function inspect(args: string[]): unknown {
  const result = spawnSync("uv", [...uvPython, ...args], {
    cwd: repoRoot,
    encoding: "utf8",
    windowsHide: true,
    env: childEnv(),
    timeout: 60_000,
  });
  if (result.error || result.status !== 0) {
    writeFileSync(path.join(runtimeDir, "last-command.txt"), redact(result.stderr || ""));
    throw new Error("case inspection failed");
  }
  return JSON.parse(result.stdout) as unknown;
}

export function inspectCase(query: { caseId?: string; externalId?: string }): InspectedCase {
  const args = ["web/e2e/support/inspect_case.py", "--manifest", readRuntime().manifestPath];
  if (query.caseId) args.push("--case-id", query.caseId);
  if (query.externalId) args.push("--external-id", query.externalId);
  return inspect(args) as InspectedCase;
}

export function inspectPresence(externalId: string): StoredPresence {
  return inspect([
    "web/e2e/support/inspect_case.py",
    "--manifest",
    readRuntime().manifestPath,
    "--external-id",
    externalId,
    "--presence",
  ]) as StoredPresence;
}

export function inspectScoring(query: { caseId?: string; externalId?: string }): StoredScoring {
  const args = ["web/e2e/support/inspect_case.py", "--manifest", readRuntime().manifestPath, "--scoring"];
  if (query.caseId) args.push("--case-id", query.caseId);
  if (query.externalId) args.push("--external-id", query.externalId);
  return inspect(args) as StoredScoring;
}

export type DirectAction = {
  status: number;
  code: string | null;
  actionId: string | null;
  replayed: boolean | null;
};

export async function postActionDirect(body: string): Promise<DirectAction> {
  const manifest = readManifest();
  const token = manifest.tokens.analyst;
  let response: Response;
  try {
    response = await fetch(`${manifest.api.base_url}/v1/actions`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body,
    });
  } catch {
    throw new Error("direct action post failed");
  }
  const text = await response.text();
  let code: string | null = null;
  let actionId: string | null = null;
  let replayed: boolean | null = null;
  try {
    const parsed = JSON.parse(text) as { error?: unknown; replayed?: unknown; action?: { id?: unknown } };
    if (typeof parsed.error === "string") code = parsed.error;
    if (typeof parsed.replayed === "boolean") replayed = parsed.replayed;
    if (typeof parsed.action?.id === "string") actionId = parsed.action.id;
  } catch {
    code = null;
  }
  return { status: response.status, code, actionId, replayed };
}
