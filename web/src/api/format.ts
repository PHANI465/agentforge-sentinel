import type { ActionParameters, Currency, InvestigatorInfo, Money } from "./types";
import { CURRENCY_EXPONENT } from "./types";

const UNCONFIRMED = "The server did not confirm a result. Reload before trying that step again.";

const ERROR_TEXT: Record<string, string> = {
  unauthenticated: "This session token was not accepted.",
  permission_denied: "This session does not have permission for that step.",
  action_permission_denied: "This session cannot execute the simulated action.",
  approver_mismatch: "Only the person who approved this action can execute it.",
  not_found: "That record is not in this session.",
  method_not_allowed: "That request is not available.",
  invalid_content_length: "The request size could not be read.",
  body_too_large: "The request is too large.",
  invalid_request: "The request was rejected.",
  invalid_cursor: "The case list could not continue from that page.",
  future_event_time: "The transaction time is in the future.",
  stale_case_revision: "The case changed. The latest server state is shown.",
  case_not_investigable: "This case cannot be investigated in its current state.",
  case_not_executable: "This case cannot be executed in its current state.",
  investigation_in_progress: "An investigation is already running.",
  investigation_recovered: "A previous investigation was recovered. The case was reloaded.",
  investigation_superseded: "That investigation is no longer current. The case was reloaded.",
  approval_expired: "The approval expired and the case was reopened.",
  approval_outside_validity: "The approval is outside its validity window. The case was reloaded.",
  approval_exists: "This proposal already has a decision.",
  approval_not_available: "That approval is not available.",
  stale_agent_config: "The investigator configuration changed. The case was reloaded.",
  stale_evidence_snapshot: "The evidence snapshot changed. The case was reloaded.",
  stale_policy: "The action policy changed. The case was reloaded.",
  stale_action_intent: "The proposed action changed. The case was reloaded.",
  inactive_policy: "The action policy is not active.",
  idempotency_conflict: "That key was already used for a different request.",
  account_profile_missing: "The account has no profile, so nothing was scored or stored.",
  conflict: "The case changed. The latest server state is shown.",
};

export function unconfirmedMessage(): string {
  return UNCONFIRMED;
}

export function unreachableMessage(): string {
  return "Sentinel could not be reached.";
}

export function safeCode(code: string): string | null {
  return /^[a-z0-9_]{1,64}$/.test(code) ? code : null;
}

export function messageFor(code: string, details: string[]): string {
  const safe = safeCode(code);
  const extra = details.map(safeCode).filter((item): item is string => item !== null);
  const base = (safe && ERROR_TEXT[safe]) || (safe ? `The server returned ${safe}.` : UNCONFIRMED);
  if (extra.length === 0) return base;
  return `${base} (${extra.join(", ")})`;
}

/** Integer minor units, decimal point placed by the currency exponent. No binary float. */
export function formatMoney(amount: Money): string {
  const units = amount.minor_units;
  if (!Number.isSafeInteger(units) || units <= 0) return "Amount unavailable";
  const exponent = amount.currency_exponent;
  if (!Number.isInteger(exponent) || exponent < 0 || exponent > 2) return "Amount unavailable";
  const digits = String(units);
  const body =
    exponent === 0
      ? digits
      : digits.length <= exponent
        ? `0.${digits.padStart(exponent, "0")}`
        : `${digits.slice(0, -exponent)}.${digits.slice(-exponent)}`;
  return `${body} ${amount.currency}`;
}

export function moneyFromParts(currency: Currency, minorUnits: number): Money {
  return {
    currency,
    currency_exponent: CURRENCY_EXPONENT[currency],
    minor_units: minorUnits,
  };
}

export function scoreLabel(kind: string, semantics: string): string {
  if (kind === "rule" && semantics === "heuristic") return "Rule score";
  if (kind === "model" && semantics === "uncalibrated_score") return "Uncalibrated ranking";
  if (kind === "model" && semantics === "estimated_probability") return "Recorded model score";
  return "Recorded score";
}

export function probabilityCaution(kind: string, semantics: string): string | null {
  if (kind === "model" || semantics === "uncalibrated_score") return "Not a fraud probability.";
  if (kind === "rule" && semantics === "heuristic") return "Not a probability.";
  return null;
}

/** Full precision. A non-zero value below 1e-4 stays exponential so 4.0295386895426815e-06 cannot render as 0. */
export function formatScore(score: number | null | undefined): string {
  if (typeof score !== "number" || !Number.isFinite(score)) return "Unknown";
  if (Object.is(score, -0)) return "0";
  if (score !== 0 && Math.abs(score) < 1e-4) return score.toExponential();
  return String(score);
}

export function formatRate(value: number | null): string {
  if (value === null) return "not available";
  return formatScore(value);
}

export function formatCount(value: number): string {
  if (!Number.isSafeInteger(value)) return "Unknown";
  return String(value);
}

export function analysisUnavailableMessage(): string {
  return "The analysis view is unavailable on this server.";
}

export function modelReportMissingMessage(): string {
  return "That model report is not on this server.";
}

export function investigatorLabel(info: Pick<InvestigatorInfo, "name" | "version">): string {
  const version = info.version ? ` ${info.version}` : "";
  if (info.name === "deterministic-investigator") return `Deterministic investigator${version}`;
  if (info.name === "claude-cli-investigator") return `Local Claude investigator${version}`;
  return `${info.name}${version}`;
}

export function stateLabel(state: string): string {
  return state.replaceAll("_", " ").replace(/^\w/, (letter) => letter.toUpperCase());
}

export function eventLabel(eventType: string): string {
  const safe = safeCode(eventType);
  if (!safe) return "Audit event";
  return safe.replaceAll("_", " ").replace(/^\w/, (letter) => letter.toUpperCase());
}

export function operationLabel(operation: string): string {
  if (operation === "simulated_hold") return "Simulated hold";
  if (operation === "escalate") return "Escalate";
  return operation;
}

export function describeProposal(parameters: ActionParameters): string {
  if (parameters.operation === "escalate") {
    return `Escalate transaction ${parameters.transaction_id}, reason ${parameters.reason_code}`;
  }
  return `Simulated hold of ${formatMoney(parameters.amount)} on transaction ${parameters.transaction_id}`;
}

export function describeRecorded(parameters: ActionParameters): string {
  if (parameters.operation === "escalate") {
    return `Escalation of transaction ${parameters.transaction_id} for ${parameters.reason_code} was recorded`;
  }
  return `Simulated hold of ${formatMoney(parameters.amount)} was recorded`;
}

export function factLabel(name: string, value: number): string {
  if (!Number.isSafeInteger(value)) return "Fact unavailable";
  if (name === "amount_minor") return `Amount in minor units: ${value}`;
  if (name === "transaction_count_1h") return `Transactions in the prior hour: ${value}`;
  if (name === "account_age_days") return `Account age in days: ${value}`;
  return `${name}: ${value}`;
}

export function artifactLabel(artifact: { name: string; version: string }): string {
  return `${artifact.name} ${artifact.version}`;
}

export function failureLabel(code: string | null): string {
  if (code === "provider_unavailable") {
    return "The investigator was unavailable. No model result was recorded.";
  }
  if (code === "timeout") return "The investigation timed out. The case can be investigated again.";
  if (code === "invalid_output") {
    return "The investigator returned output the server rejected. The case can be investigated again.";
  }
  if (code === "budget_exhausted") {
    return "The investigation used its budget. The case can be investigated again.";
  }
  return "The investigation failed. The case can be investigated again.";
}

export function aboveThreshold(score: number, threshold: number): boolean {
  return Number.isFinite(score) && Number.isFinite(threshold) && score >= threshold;
}
