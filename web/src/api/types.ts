/** Shapes consumed from accepted C01 `contracts/http/openapi.v1.json` at 2e6c232. */

export type CaseState =
  | "open"
  | "investigating"
  | "awaiting_approval"
  | "closed"
  | "inconclusive";

export type Capability =
  | "ingest_transaction"
  | "read_case"
  | "approve_action"
  | "execute_simulated_action";

export type Currency = "USD" | "INR" | "GBP" | "JPY";

export interface Money {
  currency: Currency;
  currency_exponent: number;
  minor_units: number;
}

export interface ArtifactRef {
  name: string;
  version: string;
  sha256?: string;
}

export interface SessionView {
  tenant_id: string;
  session_id: string;
  actor_id: string;
  actor_kind: "human" | "system";
  capabilities: Capability[];
  expires_at: string;
}

export interface InvestigatorInfo {
  name: string;
  version: string;
}

export interface Overview {
  cases_by_state: Record<CaseState, number>;
  transactions: number;
  alerts: number;
  simulated_actions: number;
  investigator: InvestigatorInfo;
}

export interface CaseSummary {
  id: string;
  state: CaseState;
  revision: number;
  created_at: string;
  updated_at: string;
  alert_id: string;
  transaction_id: string;
  external_id: string;
  amount: Money;
  direction: "debit" | "credit";
  score: number;
  threshold: number;
  scoring_kind: "rule" | "model";
  score_semantics: "heuristic" | "estimated_probability";
}

export interface CasePage {
  items: CaseSummary[];
  next_cursor: string | null;
  limit: number;
}

export interface Health {
  status: "ok";
  investigator: string;
}

export interface Fact {
  name: string;
  value: number;
}

export interface EvidenceItem {
  id: string;
  source: string;
  source_ref: string;
  observed_at: string;
  available_at: string;
  facts: Fact[];
}

export interface ScoringOutcome {
  score: number;
  threshold: number;
  scoring_kind: "rule" | "model";
  score_semantics: "heuristic" | "estimated_probability";
  alerted: boolean;
  prior_count_1h: number;
  scored_at: string;
  features_as_of: string;
  scorer: ArtifactRef;
  features: ArtifactRef;
  threshold_policy: ArtifactRef;
}

export interface Transaction {
  id: string;
  external_id: string;
  account_id: string;
  amount: Money;
  direction: "debit" | "credit";
  occurred_at: string;
  ingested_at: string;
  synthetic: true;
}

export interface InvestigationFinding {
  operation: "simulated_hold" | "escalate";
  reason_code: string;
  rationale: string;
}

export interface AgentRun {
  id: string;
  status: "queued" | "running" | "completed" | "failed";
  failure_code: "provider_unavailable" | "timeout" | "invalid_output" | "budget_exhausted" | null;
  role: string;
  config: ArtifactRef;
  case_revision: number;
}

export interface AgentRunView {
  run: AgentRun;
  finding: InvestigationFinding | null;
}

export interface ActionParameters {
  operation: "simulated_hold" | "escalate";
  amount: Money;
  transaction_id: string;
}

export interface ActionIntent {
  id: string;
  case_id: string;
  case_revision: number;
  evidence_snapshot_sha256: string;
  policy: ArtifactRef;
  parameters: ActionParameters;
}

export interface Approval {
  id: string;
  decision: "approved" | "rejected";
  actor_id: string;
  actor_kind: "human";
  decided_at: string;
  expires_at: string;
  consumed_at: string | null;
}

export interface SimulatedAction {
  id: string;
  approval_id: string;
  idempotency_key: string;
  state: string;
  mode: "simulated";
  created_at: string;
  completed_at: string | null;
  intent: ActionIntent;
}

export interface IntentView {
  intent: ActionIntent;
  intent_sha256: string;
  approval: Approval | null;
  action: SimulatedAction | null;
}

export interface CaseRecord {
  id: string;
  state: CaseState;
  revision: number;
  alert_id: string;
  created_at: string;
  updated_at: string;
}

export interface AlertRecord {
  id: string;
  score: number;
  threshold: number;
  scoring_kind: "rule" | "model";
  score_semantics: "heuristic" | "estimated_probability";
  scorer: ArtifactRef;
  features: ArtifactRef;
  threshold_policy: ArtifactRef;
}

export interface CaseDetail {
  case: CaseRecord;
  alert: AlertRecord;
  transaction: Transaction;
  scoring: ScoringOutcome | null;
  evidence: EvidenceItem[];
  agent_runs: AgentRunView[];
  action_intents: IntentView[];
}

export interface AuditEvent {
  id: string;
  case_id: string;
  case_revision: number;
  actor_kind: "human" | "agent" | "system";
  event_type: string;
  outcome: "success" | "denied" | "failure";
  occurred_at: string;
  recorded_at: string;
}

export interface IngestResponse {
  transaction: { id: string };
  rule_score: number | null;
  scoring: ScoringOutcome | null;
  alert: { id: string } | null;
  case: { id: string } | null;
  replayed: boolean;
}

export interface ExecuteResponse {
  action: SimulatedAction;
  replayed: boolean;
}

export interface TransactionInput {
  external_id: string;
  account_id: string;
  amount: Money;
  direction: "debit" | "credit";
  occurred_at: string;
}

export interface ErrorBody {
  error: string;
  details?: { code: string }[] | null;
}

export type ApiSuccess<T> = { ok: true; status: number; data: T };

export type ApiFailure = {
  ok: false;
  ambiguous: boolean;
  status: number | null;
  code: string | null;
  message: string;
  details: string[];
};

export type ApiResult<T> = ApiSuccess<T> | ApiFailure;

export const CASE_STATES: CaseState[] = [
  "open",
  "investigating",
  "awaiting_approval",
  "closed",
  "inconclusive",
];

export const CURRENCY_EXPONENT: Record<Currency, number> = {
  USD: 2,
  INR: 2,
  GBP: 2,
  JPY: 0,
};
