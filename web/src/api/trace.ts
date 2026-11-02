/**
 * HTTP v1.2 investigation trace (G3C-A, accepted at 16b67fd): types and a strict parser.
 *
 * The parser rebuilds every object field by field. A required field that is missing, an
 * unknown enum value or a wrong type makes the whole response unusable (shown as
 * unconfirmed), never silently empty. Null stays null: an unknown count is not zero.
 * Text fields (notes, rationale) are returned as plain strings and must be rendered inert.
 */

export type WorkflowStatus = "running" | "completed" | "inconclusive";
export type TerminalBy = "coordinator" | "recovery";
export type DeadlineStatus = "before_deadline" | "past_deadline" | "recovery_due";
export type Role = "evidence_analyst" | "investigator" | "reviewer";
export type RunStatus = "queued" | "running" | "completed" | "failed" | "inconclusive" | "cancelled";
export type FailureCode = "provider_unavailable" | "timeout" | "invalid_output" | "budget_exhausted";
export type ToolName = "case_evidence" | "scoring_outcome" | "account_history" | "account_profile";
export type DispositionKind = "recommend" | "abstain" | "inconclusive";
export type StepKind =
  | "transition"
  | "role_started"
  | "role_completed"
  | "role_failed"
  | "tool_executed"
  | "tool_denied"
  | "claims_checked"
  | "workflow_terminated";

export interface TraceArtifact {
  name: string;
  version: string;
  sha256: string;
}

export interface Disposition {
  kind: DispositionKind;
  operation: "simulated_hold" | "escalate" | null;
  reason_code: string | null;
  basis_run_id: string | null;
  inconclusive_code: string | null;
  supported_claims: number;
  unsupported_claims: number;
}

export interface WorkflowSummary {
  id: string;
  case_revision: number;
  status: WorkflowStatus;
  terminal_by: TerminalBy | null;
  started_at: string;
  deadline_at: string;
  finished_at: string | null;
  disposition_kind: DispositionKind | null;
  inconclusive_code: string | null;
}

export interface WorkflowView {
  id: string;
  case_revision: number;
  status: WorkflowStatus;
  terminal_by: TerminalBy | null;
  started_at: string;
  deadline_at: string;
  finished_at: string | null;
  config: TraceArtifact;
  tool_profile: TraceArtifact;
  input_snapshot_sha256: string;
  disposition: Disposition | null;
  recorded_role_invocations: number | null;
  recorded_tool_calls: number | null;
  deadline_status: DeadlineStatus | null;
}

export interface Citation {
  kind: "evidence" | "tool_result";
  id: string;
}

export type Claim =
  | { kind: "fact"; fact: string; relation: "eq" | "gte" | "lte"; value: number | boolean; cite: Citation }
  | { kind: "missing"; fact: string };

export interface ToolRequest {
  tool: ToolName;
  window: string | null;
}

export type RoleOutput =
  | { role: "evidence_analyst"; claims: Claim[]; missing: string[]; tool_requests: ToolRequest[]; note: string | null }
  | {
      role: "investigator";
      operation: "simulated_hold" | "escalate";
      reason_code: string;
      claims: Claim[];
      tool_requests: ToolRequest[];
      note: string | null;
    }
  | {
      role: "reviewer";
      verdict: "accept" | "challenge" | "abstain";
      challenged_claims: number[];
      reasons: string[];
      note: string | null;
    };

export interface ClaimCheck {
  index: number;
  status: "supported" | "unsupported" | "uncheckable";
  reason: string;
}

export interface Usage {
  measured: boolean;
  input_tokens: number | null;
  output_tokens: number | null;
  source: "not_applicable" | "adapter_reported" | "unknown";
}

export interface Finding {
  operation: "simulated_hold" | "escalate";
  reason_code: string;
  rationale: string;
}

export interface RoleAttempt {
  agent_run_id: string;
  role: Role;
  attempt: number;
  status: RunStatus;
  failure_code: FailureCode | null;
  failure_source: "role_step" | "workflow_terminal" | null;
  worker_unresolved: boolean | null;
  started_at: string;
  finished_at: string | null;
  config: TraceArtifact;
  output: RoleOutput | null;
  output_sha256: string | null;
  claim_checks: ClaimCheck[] | null;
  elapsed_ms: number | null;
  usage: Usage | null;
  basis: boolean;
  finding: Finding | null;
}

export interface TraceStep {
  seq: number;
  kind: StepKind;
  state: string;
  role: Role | null;
  agent_run_id: string | null;
  attempt: number | null;
  tool: ToolName | null;
  tool_result_id: string | null;
  output_sha256: string | null;
  checks: ClaimCheck[];
  failure_code: FailureCode | null;
  worker_unresolved: boolean;
  elapsed_ms: number;
  at: string;
}

export interface ToolResult {
  id: string;
  tool: ToolName;
  window: string | null;
  status: "ok" | "unavailable" | "denied";
  denial: string | null;
  values: Record<string, number | boolean>;
  evidence_ids: string[];
  as_of: string;
  content_sha256: string;
}

export interface UsageSummary {
  reported_attempts: number;
  not_applicable_attempts: number;
  unknown_attempts: number;
  input_tokens: number | null;
  output_tokens: number | null;
}

export interface WorkflowTrace {
  workflow: WorkflowView;
  limits: Record<string, number> | null;
  attempts: RoleAttempt[];
  steps: TraceStep[];
  tool_results: ToolResult[];
  usage_summary: UsageSummary;
}

export interface InvestigationTrace {
  case_id: string;
  case_state: string;
  case_revision: number;
  read_at: string;
  legacy_investigator_runs: number;
  workflow_count: number;
  workflows: WorkflowSummary[];
  selected: WorkflowTrace | null;
}

export const MAX_LISTED_WORKFLOWS = 25;

// ---- primitive checks ---------------------------------------------------------------------

type Obj = Record<string, unknown>;
class Reject extends Error {}

const HASH = /^[0-9a-f]{64}$/;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const TIMESTAMP = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?(Z|[+-]\d{2}:\d{2})$/;
const CODE = /^[a-z][a-z0-9_]{0,63}$/;

function obj(value: unknown): Obj {
  if (typeof value !== "object" || value === null || Array.isArray(value)) throw new Reject();
  return value as Obj;
}

/** A field that must be present (it may still be allowed to be null by the caller). */
function field(record: Obj, key: string): unknown {
  if (!Object.hasOwn(record, key)) throw new Reject();
  return record[key];
}

/** A field with a schema default: absent means the default. */
function withDefault(record: Obj, key: string, fallback: unknown): unknown {
  return Object.hasOwn(record, key) ? record[key] : fallback;
}

function str(value: unknown, pattern?: RegExp): string {
  if (typeof value !== "string" || value.length === 0) throw new Reject();
  if (pattern && !pattern.test(value)) throw new Reject();
  return value;
}

function nullable<T>(value: unknown, parse: (item: unknown) => T): T | null {
  return value === null ? null : parse(value);
}

function count(value: unknown): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 0) throw new Reject();
  return value;
}

function int(value: unknown): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value)) throw new Reject();
  return value;
}

function bool(value: unknown): boolean {
  if (typeof value !== "boolean") throw new Reject();
  return value;
}

function oneOf<T extends string>(values: readonly T[]): (value: unknown) => T {
  return (value) => {
    if (typeof value !== "string" || !(values as readonly string[]).includes(value)) throw new Reject();
    return value as T;
  };
}

function list<T>(value: unknown, parse: (item: unknown) => T, max = 64): T[] {
  if (!Array.isArray(value) || value.length > max) throw new Reject();
  return value.map(parse);
}

const id = (value: unknown) => str(value, UUID);
const hash = (value: unknown) => str(value, HASH);
const time = (value: unknown) => str(value, TIMESTAMP);
const code = (value: unknown) => str(value, CODE);
const roleOf = oneOf<Role>(["evidence_analyst", "investigator", "reviewer"]);
const toolOf = oneOf<ToolName>(["case_evidence", "scoring_outcome", "account_history", "account_profile"]);
const failureOf = oneOf<FailureCode>(["provider_unavailable", "timeout", "invalid_output", "budget_exhausted"]);
const operationOf = oneOf(["simulated_hold", "escalate"] as const);
const statusOf = oneOf<WorkflowStatus>(["running", "completed", "inconclusive"]);
const terminalOf = oneOf<TerminalBy>(["coordinator", "recovery"]);
const dispositionKindOf = oneOf<DispositionKind>(["recommend", "abstain", "inconclusive"]);
const windowOf = oneOf(["24h", "7d", "30d"] as const);

function artifact(value: unknown): TraceArtifact {
  const record = obj(value);
  return { name: str(field(record, "name")), version: str(field(record, "version")), sha256: hash(field(record, "sha256")) };
}

function disposition(value: unknown): Disposition {
  const record = obj(value);
  return {
    kind: dispositionKindOf(field(record, "kind")),
    operation: nullable(withDefault(record, "operation", null), operationOf),
    reason_code: nullable(withDefault(record, "reason_code", null), code),
    basis_run_id: nullable(withDefault(record, "basis_run_id", null), id),
    inconclusive_code: nullable(withDefault(record, "inconclusive_code", null), code),
    supported_claims: count(field(record, "supported_claims")),
    unsupported_claims: count(field(record, "unsupported_claims")),
  };
}

function summary(value: unknown): WorkflowSummary {
  const record = obj(value);
  return {
    id: id(field(record, "id")),
    case_revision: count(field(record, "case_revision")),
    status: statusOf(field(record, "status")),
    terminal_by: nullable(field(record, "terminal_by"), terminalOf),
    started_at: time(field(record, "started_at")),
    deadline_at: time(field(record, "deadline_at")),
    finished_at: nullable(field(record, "finished_at"), time),
    disposition_kind: nullable(field(record, "disposition_kind"), dispositionKindOf),
    inconclusive_code: nullable(field(record, "inconclusive_code"), code),
  };
}

function workflowView(value: unknown): WorkflowView {
  const record = obj(value);
  const view: WorkflowView = {
    id: id(field(record, "id")),
    case_revision: count(field(record, "case_revision")),
    status: statusOf(field(record, "status")),
    terminal_by: nullable(field(record, "terminal_by"), terminalOf),
    started_at: time(field(record, "started_at")),
    deadline_at: time(field(record, "deadline_at")),
    finished_at: nullable(field(record, "finished_at"), time),
    config: artifact(field(record, "config")),
    tool_profile: artifact(field(record, "tool_profile")),
    input_snapshot_sha256: hash(field(record, "input_snapshot_sha256")),
    disposition: nullable(field(record, "disposition"), disposition),
    recorded_role_invocations: nullable(field(record, "recorded_role_invocations"), count),
    recorded_tool_calls: nullable(field(record, "recorded_tool_calls"), count),
    deadline_status: nullable(field(record, "deadline_status"), oneOf<DeadlineStatus>([
      "before_deadline",
      "past_deadline",
      "recovery_due",
    ])),
  };
  // The documented lifecycle: running has no terminal fields; a terminal record has them.
  const running = view.status === "running";
  if (running !== (view.terminal_by === null && view.finished_at === null && view.disposition === null)) {
    throw new Reject();
  }
  if (running !== (view.deadline_status !== null)) throw new Reject();
  return view;
}

function citation(value: unknown): Citation {
  const record = obj(value);
  return { kind: oneOf(["evidence", "tool_result"] as const)(field(record, "kind")), id: id(field(record, "id")) };
}

function claim(value: unknown): Claim {
  const record = obj(value);
  const kind = field(record, "kind");
  if (kind === "missing") return { kind: "missing", fact: code(field(record, "fact")) };
  if (kind !== "fact") throw new Reject();
  const raw = field(record, "value");
  return {
    kind: "fact",
    fact: code(field(record, "fact")),
    relation: oneOf(["eq", "gte", "lte"] as const)(field(record, "relation")),
    value: typeof raw === "boolean" ? raw : int(raw),
    cite: citation(field(record, "cite")),
  };
}

function toolRequest(value: unknown): ToolRequest {
  const record = obj(value);
  return { tool: toolOf(field(record, "tool")), window: nullable(withDefault(record, "window", null), windowOf) };
}

function note(record: Obj): string | null {
  const value = withDefault(record, "note", null);
  if (value === null) return null;
  // maxLength 400 in the frozen DTO counts Unicode code points, not UTF-16 units (R38).
  if (typeof value !== "string" || value.length === 0 || [...value].length > 400) throw new Reject();
  return value;
}

function roleOutput(value: unknown): RoleOutput {
  const record = obj(value);
  const role = roleOf(field(record, "role"));
  if (role === "evidence_analyst") {
    return {
      role,
      claims: list(withDefault(record, "claims", []), claim, 12),
      missing: list(withDefault(record, "missing", []), code, 8),
      tool_requests: list(withDefault(record, "tool_requests", []), toolRequest, 4),
      note: note(record),
    };
  }
  if (role === "investigator") {
    return {
      role,
      operation: operationOf(field(record, "operation")),
      reason_code: code(field(record, "reason_code")),
      claims: list(field(record, "claims"), claim, 12),
      tool_requests: list(withDefault(record, "tool_requests", []), toolRequest, 2),
      note: note(record),
    };
  }
  return {
    role,
    verdict: oneOf(["accept", "challenge", "abstain"] as const)(field(record, "verdict")),
    challenged_claims: list(withDefault(record, "challenged_claims", []), int, 12),
    reasons: list(withDefault(record, "reasons", []), code, 5),
    note: note(record),
  };
}

function claimCheck(value: unknown): ClaimCheck {
  const record = obj(value);
  return {
    index: count(field(record, "index")),
    status: oneOf(["supported", "unsupported", "uncheckable"] as const)(field(record, "status")),
    reason: code(field(record, "reason")),
  };
}

function usage(value: unknown): Usage {
  const record = obj(value);
  const parsed: Usage = {
    measured: bool(field(record, "measured")),
    input_tokens: nullable(withDefault(record, "input_tokens", null), count),
    output_tokens: nullable(withDefault(record, "output_tokens", null), count),
    source: oneOf(["not_applicable", "adapter_reported", "unknown"] as const)(field(record, "source")),
  };
  const counted = parsed.input_tokens !== null && parsed.output_tokens !== null;
  const none = parsed.input_tokens === null && parsed.output_tokens === null;
  if (parsed.source === "adapter_reported" ? !(parsed.measured && counted) : parsed.measured || !none) {
    throw new Reject();
  }
  return parsed;
}

function finding(value: unknown): Finding {
  const record = obj(value);
  const rationale = field(record, "rationale");
  if (typeof rationale !== "string" || rationale.length === 0) throw new Reject();
  return {
    operation: operationOf(field(record, "operation")),
    reason_code: code(field(record, "reason_code")),
    rationale,
  };
}

function attempt(value: unknown): RoleAttempt {
  const record = obj(value);
  return {
    agent_run_id: id(field(record, "agent_run_id")),
    role: roleOf(field(record, "role")),
    attempt: count(field(record, "attempt")),
    status: oneOf<RunStatus>(["queued", "running", "completed", "failed", "inconclusive", "cancelled"])(
      field(record, "status"),
    ),
    failure_code: nullable(field(record, "failure_code"), failureOf),
    failure_source: nullable(field(record, "failure_source"), oneOf(["role_step", "workflow_terminal"] as const)),
    worker_unresolved: nullable(field(record, "worker_unresolved"), bool),
    started_at: time(field(record, "started_at")),
    finished_at: nullable(field(record, "finished_at"), time),
    config: artifact(field(record, "config")),
    output: nullable(field(record, "output"), roleOutput),
    output_sha256: nullable(field(record, "output_sha256"), hash),
    claim_checks: nullable(field(record, "claim_checks"), (item) => list(item, claimCheck, 12)),
    elapsed_ms: nullable(field(record, "elapsed_ms"), count),
    usage: nullable(field(record, "usage"), usage),
    basis: bool(field(record, "basis")),
    finding: nullable(field(record, "finding"), finding),
  };
}

function step(value: unknown): TraceStep {
  const record = obj(value);
  return {
    seq: count(field(record, "seq")),
    kind: oneOf<StepKind>([
      "transition",
      "role_started",
      "role_completed",
      "role_failed",
      "tool_executed",
      "tool_denied",
      "claims_checked",
      "workflow_terminated",
    ])(field(record, "kind")),
    state: code(field(record, "state")),
    role: nullable(field(record, "role"), roleOf),
    agent_run_id: nullable(field(record, "agent_run_id"), id),
    attempt: nullable(field(record, "attempt"), count),
    tool: nullable(field(record, "tool"), toolOf),
    tool_result_id: nullable(field(record, "tool_result_id"), id),
    output_sha256: nullable(field(record, "output_sha256"), hash),
    checks: list(field(record, "checks"), claimCheck, 12),
    failure_code: nullable(field(record, "failure_code"), failureOf),
    worker_unresolved: bool(field(record, "worker_unresolved")),
    elapsed_ms: count(field(record, "elapsed_ms")),
    at: time(field(record, "at")),
  };
}

function toolResult(value: unknown): ToolResult {
  const record = obj(value);
  const values: Record<string, number | boolean> = {};
  for (const [key, item] of Object.entries(obj(withDefault(record, "values", {})))) {
    values[code(key)] = typeof item === "boolean" ? item : int(item);
  }
  return {
    id: id(field(record, "id")),
    tool: toolOf(field(record, "tool")),
    window: nullable(withDefault(record, "window", null), windowOf),
    status: oneOf(["ok", "unavailable", "denied"] as const)(field(record, "status")),
    denial: nullable(withDefault(record, "denial", null), code),
    values,
    evidence_ids: list(withDefault(record, "evidence_ids", []), id, 32),
    as_of: time(field(record, "as_of")),
    content_sha256: hash(field(record, "content_sha256")),
  };
}

function usageSummary(value: unknown): UsageSummary {
  const record = obj(value);
  return {
    reported_attempts: count(field(record, "reported_attempts")),
    not_applicable_attempts: count(field(record, "not_applicable_attempts")),
    unknown_attempts: count(field(record, "unknown_attempts")),
    input_tokens: nullable(field(record, "input_tokens"), count),
    output_tokens: nullable(field(record, "output_tokens"), count),
  };
}

function limits(value: unknown): Record<string, number> {
  const parsed: Record<string, number> = {};
  for (const [key, item] of Object.entries(obj(value))) {
    if (key === "schema_version") continue;
    parsed[code(key)] = count(item);
  }
  return parsed;
}

function workflowTrace(value: unknown): WorkflowTrace {
  const record = obj(value);
  const trace: WorkflowTrace = {
    workflow: workflowView(field(record, "workflow")),
    limits: nullable(field(record, "limits"), limits),
    attempts: list(field(record, "attempts"), attempt),
    steps: list(field(record, "steps"), step),
    tool_results: list(field(record, "tool_results"), toolResult),
    usage_summary: usageSummary(field(record, "usage_summary")),
  };
  // agent_run_id is the attempt key (role + attempt is not unique); duplicates are unusable.
  if (new Set(trace.attempts.map((item) => item.agent_run_id)).size !== trace.attempts.length) throw new Reject();
  if (new Set(trace.steps.map((item) => item.seq)).size !== trace.steps.length) throw new Reject();
  return trace;
}

/** The accepted InvestigationTrace, or null when the body is not a usable trace. */
export function acceptTrace(value: unknown): InvestigationTrace | null {
  try {
    const record = obj(value);
    const trace: InvestigationTrace = {
      case_id: id(field(record, "case_id")),
      case_state: code(field(record, "case_state")),
      case_revision: count(field(record, "case_revision")),
      read_at: time(field(record, "read_at")),
      legacy_investigator_runs: count(field(record, "legacy_investigator_runs")),
      workflow_count: count(field(record, "workflow_count")),
      workflows: list(field(record, "workflows"), summary, MAX_LISTED_WORKFLOWS),
      selected: nullable(field(record, "selected"), workflowTrace),
    };
    if (trace.workflows.length > trace.workflow_count) return null;
    if ((trace.workflow_count === 0) !== (trace.workflows.length === 0)) return null;
    if (trace.workflow_count === 0 && trace.selected !== null) return null;
    return trace;
  } catch (error) {
    if (error instanceof Reject) return null;
    throw error;
  }
}
