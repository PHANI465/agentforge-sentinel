import type { AuditEvent, Capability, CaseDetail, IntentView, SessionView } from "./types";

export function currentIntent(detail: CaseDetail): IntentView | null {
  const last = detail.action_intents[detail.action_intents.length - 1];
  if (!last) return null;
  if (last.intent.case_revision !== detail.case.revision) return null;
  return last;
}

export function earlierIntents(detail: CaseDetail): IntentView[] {
  const current = currentIntent(detail);
  return detail.action_intents.filter((item) => item !== current);
}

export function allows(session: SessionView, capability: Capability, human = false): boolean {
  if (human && session.actor_kind !== "human") return false;
  return session.capabilities.includes(capability);
}

export function approvalExpired(audit: AuditEvent[]): boolean {
  return audit.some((event) => event.event_type === "approval_expired");
}
