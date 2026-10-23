import { messageFor, safeCode, unconfirmedMessage, unreachableMessage } from "./format";
import type {
  ApiFailure,
  ApiResult,
  AuditEvent,
  CaseDetail,
  CasePage,
  CaseState,
  ErrorBody,
  ExecuteResponse,
  Health,
  IngestResponse,
  Overview,
  SessionView,
  TransactionInput,
} from "./types";

export interface SentinelClient {
  health(): Promise<ApiResult<Health>>;
  session(token: string): Promise<ApiResult<SessionView>>;
  overview(token: string): Promise<ApiResult<Overview>>;
  listCases(
    token: string,
    query: { limit?: number; state?: CaseState | ""; cursor?: string | null },
  ): Promise<ApiResult<CasePage>>;
  caseDetail(token: string, caseId: string): Promise<ApiResult<CaseDetail>>;
  audit(token: string, caseId: string): Promise<ApiResult<AuditEvent[]>>;
  ingest(token: string, body: TransactionInput): Promise<ApiResult<IngestResponse>>;
  investigate(
    token: string,
    caseId: string,
    expectedRevision: number,
  ): Promise<ApiResult<CaseDetail>>;
  decide(
    token: string,
    actionIntentId: string,
    decision: "approved" | "rejected",
  ): Promise<ApiResult<{ id: string; decision: "approved" | "rejected" }>>;
  execute(
    token: string,
    approvalId: string,
    idempotencyKey: string,
  ): Promise<ApiResult<ExecuteResponse>>;
}

type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

function failure(
  status: number | null,
  ambiguous: boolean,
  code: string | null,
  message: string,
  details: string[] = [],
): ApiFailure {
  return { ok: false, ambiguous, status, code, message, details };
}

function ambiguous(status: number | null, network = false): ApiFailure {
  return failure(status, true, null, network ? unreachableMessage() : unconfirmedMessage());
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isErrorBody(value: unknown): value is ErrorBody {
  if (!isRecord(value) || typeof value.error !== "string" || safeCode(value.error) === null) {
    return false;
  }
  if (value.details === undefined || value.details === null) return true;
  if (!Array.isArray(value.details)) return false;
  return value.details.every((item) => isRecord(item) && typeof item.code === "string");
}

function jsonContentType(header: string | null): boolean {
  if (!header) return false;
  return header.split(";")[0]?.trim().toLowerCase() === "application/json";
}

function asString(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function isMoney(value: unknown): boolean {
  return (
    isRecord(value) &&
    asString(value.currency) !== null &&
    typeof value.currency_exponent === "number" &&
    typeof value.minor_units === "number"
  );
}

function acceptSession(value: unknown): SessionView | null {
  if (!isRecord(value) || !Array.isArray(value.capabilities)) return null;
  if (
    !asString(value.tenant_id) ||
    !asString(value.session_id) ||
    !asString(value.actor_id) ||
    (value.actor_kind !== "human" && value.actor_kind !== "system") ||
    !asString(value.expires_at)
  ) {
    return null;
  }
  if (!value.capabilities.every((item) => typeof item === "string")) return null;
  return value as unknown as SessionView;
}

function acceptOverview(value: unknown): Overview | null {
  if (!isRecord(value) || !isRecord(value.cases_by_state) || !isRecord(value.investigator)) {
    return null;
  }
  if (
    asNumber(value.transactions) === null ||
    asNumber(value.alerts) === null ||
    asNumber(value.simulated_actions) === null ||
    !asString(value.investigator.name) ||
    !asString(value.investigator.version)
  ) {
    return null;
  }
  return value as unknown as Overview;
}

function acceptPage(value: unknown): CasePage | null {
  if (!isRecord(value) || !Array.isArray(value.items) || asNumber(value.limit) === null) return null;
  if (value.next_cursor !== null && typeof value.next_cursor !== "string") return null;
  return value as unknown as CasePage;
}

function acceptDetail(value: unknown): CaseDetail | null {
  if (!isRecord(value) || !isRecord(value.case) || !isRecord(value.transaction)) return null;
  if (!asString(value.case.id) || typeof value.case.revision !== "number") return null;
  if (!isMoney(value.transaction.amount) || !Array.isArray(value.evidence)) return null;
  if (!Array.isArray(value.agent_runs) || !Array.isArray(value.action_intents)) return null;
  return value as unknown as CaseDetail;
}

function acceptAudit(value: unknown): AuditEvent[] | null {
  if (!Array.isArray(value)) return null;
  for (const event of value) {
    if (!isRecord(event) || !asString(event.id) || !asString(event.event_type)) return null;
  }
  return value as AuditEvent[];
}

function acceptIngest(value: unknown): IngestResponse | null {
  if (!isRecord(value) || typeof value.replayed !== "boolean" || !isRecord(value.transaction)) {
    return null;
  }
  if (!asString(value.transaction.id)) return null;
  if (value.case !== null && (!isRecord(value.case) || !asString(value.case.id))) return null;
  return value as unknown as IngestResponse;
}

function acceptExecute(value: unknown): ExecuteResponse | null {
  if (!isRecord(value) || typeof value.replayed !== "boolean" || !isRecord(value.action)) return null;
  if (!asString(value.action.id) || !asString(value.action.idempotency_key)) return null;
  return value as unknown as ExecuteResponse;
}

function acceptHealth(value: unknown): Health | null {
  if (!isRecord(value) || value.status !== "ok" || !asString(value.investigator)) return null;
  return value as unknown as Health;
}

function acceptDecision(value: unknown): { id: string; decision: "approved" | "rejected" } | null {
  if (!isRecord(value)) return null;
  const id = asString(value.id);
  const decision = value.decision;
  if (!id || (decision !== "approved" && decision !== "rejected")) return null;
  return { id, decision };
}

export function createClient(fetchImpl: FetchLike = (input, init) => fetch(input, init)): SentinelClient {
  async function request<T>(
    path: string,
    method: string,
    token: string | null,
    body: unknown,
    accept: (value: unknown) => T | null,
  ): Promise<ApiResult<T>> {
    let response: Response;
    try {
      response = await fetchImpl(path, {
        method,
        cache: "no-store",
        headers: {
          Accept: "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
        },
        body: body !== undefined ? JSON.stringify(body) : undefined,
      });
    } catch {
      return ambiguous(null, true);
    }

    let text = "";
    try {
      text = await response.text();
    } catch {
      return ambiguous(response.status);
    }

    const parsed = parseJson(text, response.headers.get("content-type"));
    if (response.status >= 500) return ambiguous(response.status);
    if (!response.ok) {
      if (!parsed.ok || !isErrorBody(parsed.value)) return ambiguous(response.status);
      const details = (parsed.value.details ?? [])
        .map((item) => item.code)
        .filter((code) => safeCode(code) !== null);
      return failure(
        response.status,
        false,
        parsed.value.error,
        messageFor(parsed.value.error, details),
        details,
      );
    }
    if (!parsed.ok) return ambiguous(response.status);
    const data = accept(parsed.value);
    if (data === null) return ambiguous(response.status);
    return { ok: true, status: response.status, data };
  }

  return {
    health: () => request("/healthz", "GET", null, undefined, acceptHealth),
    session: (token) => request("/v1/session", "GET", token, undefined, acceptSession),
    overview: (token) => request("/v1/overview", "GET", token, undefined, acceptOverview),
    listCases: (token, query) => {
      const params = new URLSearchParams();
      params.set("limit", String(query.limit ?? 25));
      if (query.state) params.set("state", query.state);
      if (query.cursor) params.set("cursor", query.cursor);
      return request(`/v1/cases?${params.toString()}`, "GET", token, undefined, acceptPage);
    },
    caseDetail: (token, caseId) =>
      request(`/v1/cases/${encodeURIComponent(caseId)}`, "GET", token, undefined, acceptDetail),
    audit: (token, caseId) =>
      request(`/v1/cases/${encodeURIComponent(caseId)}/audit`, "GET", token, undefined, acceptAudit),
    ingest: (token, body) => request("/v1/transactions", "POST", token, body, acceptIngest),
    investigate: (token, caseId, expectedRevision) =>
      request(
        `/v1/cases/${encodeURIComponent(caseId)}/investigations`,
        "POST",
        token,
        { expected_revision: expectedRevision },
        acceptDetail,
      ),
    decide: (token, actionIntentId, decision) =>
      request("/v1/approvals", "POST", token, { action_intent_id: actionIntentId, decision }, acceptDecision),
    execute: (token, approvalId, idempotencyKey) =>
      request(
        "/v1/actions",
        "POST",
        token,
        { approval_id: approvalId, idempotency_key: idempotencyKey },
        acceptExecute,
      ),
  };
}

function parseJson(
  text: string,
  contentType: string | null,
): { ok: true; value: unknown } | { ok: false } {
  if (!jsonContentType(contentType) || text.trim() === "") return { ok: false };
  try {
    return { ok: true, value: JSON.parse(text) as unknown };
  } catch {
    return { ok: false };
  }
}
