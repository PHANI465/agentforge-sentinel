import type {
  ClaimCheck,
  DeadlineStatus,
  Disposition,
  FailureCode,
  Role,
  RoleAttempt,
  Usage,
  WorkflowStatus,
  WorkflowView,
} from "./trace";

export function roleLabel(role: Role): string {
  if (role === "evidence_analyst") return "Evidence analyst";
  if (role === "investigator") return "Investigator";
  return "Reviewer";
}

export function workflowStatusLabel(status: WorkflowStatus): string {
  if (status === "running") return "Running";
  if (status === "completed") return "Completed";
  return "Inconclusive";
}

export function deadlineLabel(status: DeadlineStatus | null): string | null {
  if (status === "before_deadline") return "Within its deadline when read.";
  if (status === "past_deadline") return "Past its deadline when read. It has not been recovered.";
  if (status === "recovery_due") {
    return "Overdue and due for recovery when read. It has not been recovered; it stays running until a new investigation request recovers it.";
  }
  return null;
}

export function terminalLabel(workflow: WorkflowView): string | null {
  if (workflow.terminal_by === "coordinator") return "Ended by the coordinator.";
  if (workflow.terminal_by === "recovery") return "Ended by recovery after the workflow was interrupted.";
  return null;
}

const INCONCLUSIVE: Record<string, string> = {
  provider_unavailable: "a role provider was unavailable",
  timeout: "a role timed out",
  invalid_output: "a role returned output the server rejected",
  budget_exhausted: "a workflow budget or limit was used up",
  stale_evidence_snapshot: "the case evidence changed during the workflow",
  call_capacity_exhausted: "no provider call slot was free in this API process",
  coordinator_error: "the coordinator could not finish the workflow",
  interrupted: "the workflow was interrupted",
};

export function dispositionLabel(disposition: Disposition | null): string {
  if (!disposition) return "No outcome is recorded yet.";
  if (disposition.kind === "inconclusive") {
    const reason = disposition.inconclusive_code ? INCONCLUSIVE[disposition.inconclusive_code] : undefined;
    return `Inconclusive: ${reason ?? `code ${disposition.inconclusive_code ?? "not recorded"}`}. No action was proposed.`;
  }
  const operation = disposition.operation === "simulated_hold" ? "a simulated hold" : "escalation";
  const lead = disposition.kind === "recommend" ? "Recommended" : "Abstained and recommended";
  return `${lead} ${operation}, reason ${disposition.reason_code ?? "not recorded"}.`;
}

export function attemptStatusLabel(attempt: RoleAttempt): string {
  if (attempt.status === "completed") return "Completed";
  if (attempt.status === "running") return "Running when read (no end was recorded)";
  if (attempt.status === "failed") return "Failed";
  return attempt.status.charAt(0).toUpperCase() + attempt.status.slice(1);
}

export function failureText(code: FailureCode | null, source: RoleAttempt["failure_source"]): string | null {
  if (!code) return null;
  const what: Record<FailureCode, string> = {
    provider_unavailable: "The role provider was unavailable.",
    timeout: "The role call timed out.",
    invalid_output: "The role returned output the server rejected.",
    budget_exhausted: "The workflow budget did not allow this call. A provider call may not have been made.",
  };
  const by =
    source === "workflow_terminal"
      ? " Recorded when the workflow ended (by the coordinator or recovery), not by the role itself."
      : "";
  return `${what[code]}${by}`;
}

export function usageText(usage: Usage | null): string {
  if (usage === null) return "Usage not recorded (unknown, not zero).";
  if (usage.source === "not_applicable") return "Usage not applicable (no provider was involved).";
  if (usage.source === "unknown") return "Usage unknown.";
  return `Adapter-reported usage: ${usage.input_tokens} input and ${usage.output_tokens} output tokens.`;
}

export function elapsedText(elapsed: number | null): string {
  if (elapsed === null) return "Coordinator time not recorded.";
  return `Coordinator time ${elapsed} ms (includes persistence; not provider latency).`;
}

export function checkText(check: ClaimCheck | undefined, recorded: boolean): string {
  if (!recorded) return "Server check not recorded.";
  if (!check) return "No server check is recorded for this claim.";
  const status =
    check.status === "supported" ? "supported" : check.status === "unsupported" ? "not supported" : "could not be checked";
  return `Server check: ${status} (${check.reason.replace(/_/g, " ")}).`;
}

export function countOrUnknown(value: number | null, noun: string): string {
  return value === null ? `${noun}: not yet recorded` : `${noun}: ${value}`;
}

export function factName(name: string): string {
  return name.replace(/_/g, " ");
}
