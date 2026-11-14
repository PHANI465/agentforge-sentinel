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
  | "execute_simulated_action"
  // v1.3 opt-in (DOC01): never part of the default grant.
  | "analyze_document";

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
  score_semantics: "heuristic" | "estimated_probability" | "uncalibrated_score";
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
  score_semantics: "heuristic" | "estimated_probability" | "uncalibrated_score";
  alerted: boolean;
  prior_count_1h: number;
  scored_at: string;
  features_as_of: string;
  scorer: ArtifactRef;
  features: ArtifactRef;
  threshold_policy: ArtifactRef;
  inputs?: ScoringInputs | null;
  model?: ModelProvenance | null;
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

export interface HoldParameters {
  operation: "simulated_hold";
  transaction_id: string;
  amount: Money;
}

export interface EscalateParameters {
  operation: "escalate";
  transaction_id: string;
  reason_code: "velocity_pattern" | "unusual_amount" | "insufficient_evidence";
}

export type ActionParameters = HoldParameters | EscalateParameters;

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
  score_semantics: "heuristic" | "estimated_probability" | "uncalibrated_score";
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

export interface ModelProvenance {
  protocol_version: string;
  protocol_sha256: string;
  selection_sha256: string;
  candidate: string;
  artifact_sha256: string;
  feature_version: string;
  threshold_source: "validation_frozen_threshold";
  results_id: string;
}

export interface ScoringInputs {
  feature_version: "f1";
  values: Record<string, number>;
  currency: Currency;
  history_rows: number;
  disclosures_used: number;
  profile_home_currency: Currency;
  profile_opened_at: string;
}

export interface ScorerInfo {
  mode: "rule" | "model";
  scoring_kind: "rule" | "model";
  score_semantics: "heuristic" | "estimated_probability" | "uncalibrated_score";
  scorer: ArtifactRef;
  features: ArtifactRef;
  threshold_policy: ArtifactRef;
  threshold: number;
  alert_rule: "score >= threshold";
  model: ModelProvenance | null;
  results_id: string | null;
  notes: string[];
}

export interface PolicyStats {
  flagged: number;
  tp: number;
  fp: number;
  fn: number;
  tn: number;
  precision: number | null;
  recall: number | null;
  false_positive_rate: number | null;
}

export interface ModelResultCandidate {
  name: string;
  kind: string;
  validation_average_precision: number;
  test_average_precision: number;
  test_pr_auc_trapezoid: number;
  test_daily_top_k: PolicyStats;
  test_brier: number | null;
}

export interface SliceRow extends PolicyStats {
  dimension: string;
  value: string;
  rows: number;
  fraud: number;
}

export interface ReliabilityBin {
  lo: number;
  hi: number;
  n: number;
  mean_score: number | null;
  fraud_rate: number | null;
}

export interface SplitCounts {
  rows: number;
  legitimate: number;
  fraud: number;
  unknown_excluded: number;
  labels_observable_by_horizon: number | null;
  decision_days: number;
}

export interface ModelResults {
  results_id: string;
  label: "offline synthetic benchmark";
  synthetic: true;
  protocol_version: string;
  protocol_sha256: string;
  selection_sha256: string;
  artifact_sha256: string;
  selected: string;
  windows: Record<string, [number, number]>;
  label_views: Record<string, string>;
  review_k_per_day: number;
  review_ranking: string;
  frozen_threshold: number;
  splits: Record<string, SplitCounts>;
  candidates: ModelResultCandidate[];
  selected_policy: { daily_top_k: PolicyStats; frozen_threshold: PolicyStats };
  uncertainty: {
    method: string;
    replicates: number;
    accounts: number;
    skipped_one_class: number;
    average_precision: [number, number] | null;
    recall_at_capacity: [number, number] | null;
    precision_at_capacity: [number, number] | null;
  };
  calibration: { brier: number; reliability: ReliabilityBin[]; note: string };
  slices: SliceRow[];
  pr_curve: { recall: number; precision: number }[];
  limitations: string[];
}

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
