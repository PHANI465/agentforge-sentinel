import { Component, useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import type { SentinelClient } from "../api/client";
import { allows } from "../api/case";
import { investigatorLabel } from "../api/format";
import { beginExecution, finishExecution } from "../api/idempotency";
import type { ExecutionAttempt } from "../api/idempotency";
import type {
  AuditEvent,
  CaseDetail,
  CasePage,
  CaseState,
  Overview,
  SessionView,
} from "../api/types";
import { CaseFile } from "./CaseFile";
import { IngestForm } from "./IngestForm";
import { Queue } from "./Queue";

class CasePaneBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError(): { failed: boolean } {
    return { failed: true };
  }

  render() {
    if (this.state.failed) {
      return (
        <p className="case" role="alert">
          This case could not be shown. The queue is unchanged.
        </p>
      );
    }
    return this.props.children;
  }
}

function capabilityLine(session: SessionView): string {
  const granted = [
    allows(session, "read_case") ? "read cases" : "",
    allows(session, "ingest_transaction") ? "record transactions" : "",
    allows(session, "approve_action", true) ? "approve or reject" : "",
    allows(session, "execute_simulated_action", true) ? "execute simulated actions" : "",
  ].filter(Boolean);
  return granted.length > 0 ? `Can ${granted.join(", ")}.` : "This session has no case permissions.";
}

export function Workbench({
  client,
  token,
  session,
  onSignOut,
}: {
  client: SentinelClient;
  token: string;
  session: SessionView;
  onSignOut: () => void;
}) {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [page, setPage] = useState<CasePage | null>(null);
  const [stateFilter, setStateFilter] = useState<CaseState | "">("");
  const [cursors, setCursors] = useState<(string | null)[]>([null]);
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [replayed, setReplayed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [loadingQueue, setLoadingQueue] = useState(true);
  const [queuePending, setQueuePending] = useState(false);
  const attempt = useRef<ExecutionAttempt | null>(null);
  const caseGeneration = useRef(0);
  const queueGeneration = useRef(0);
  const queueFlight = useRef(false);
  const mutation = useRef(false);
  const selectedRef = useRef<string | null>(null);
  const queryRef = useRef<{ filter: CaseState | ""; cursor: string | null }>({ filter: "", cursor: null });
  const pageIndex = cursors.length - 1;

  const finishQueue = useCallback((generation: number) => {
    if (generation !== queueGeneration.current) return;
    queueFlight.current = false;
    setQueuePending(false);
    setLoadingQueue(false);
  }, []);

  const loadQueue = useCallback(
    async (cursor: string | null, filter: CaseState | "") => {
      const generation = ++queueGeneration.current;
      queueFlight.current = true;
      setQueuePending(true);
      setLoadingQueue(true);
      const result = await client.listCases(token, { limit: 25, state: filter, cursor });
      const stillCurrent = () =>
        generation === queueGeneration.current &&
        queryRef.current.filter === filter &&
        queryRef.current.cursor === cursor;
      if (!stillCurrent()) {
        if (generation === queueGeneration.current) finishQueue(generation);
        return;
      }
      if (!result.ok) {
        if (result.code === "invalid_cursor") {
          queryRef.current = { filter, cursor: null };
          setCursors([null]);
          const first = await client.listCases(token, { limit: 25, state: filter, cursor: null });
          const retryCurrent =
            generation === queueGeneration.current &&
            queryRef.current.filter === filter &&
            queryRef.current.cursor === null;
          if (!retryCurrent) {
            if (generation === queueGeneration.current) finishQueue(generation);
            return;
          }
          if (first.ok) setPage(first.data);
          else setNotice(first.message);
          finishQueue(generation);
          return;
        }
        setNotice(result.message);
        finishQueue(generation);
        return;
      }
      setPage(result.data);
      finishQueue(generation);
    },
    [client, finishQueue, token],
  );

  const loadOverview = useCallback(async () => {
    const result = await client.overview(token);
    if (result.ok) setOverview(result.data);
    else setNotice(result.message);
  }, [client, token]);

  const loadCase = useCallback(
    async (caseId: string) => {
      const generation = ++caseGeneration.current;
      const [nextDetail, nextAudit] = await Promise.all([
        client.caseDetail(token, caseId),
        client.audit(token, caseId),
      ]);
      if (generation !== caseGeneration.current || selectedRef.current !== caseId) return false;
      if (!nextDetail.ok) {
        setNotice(nextDetail.message);
        return true;
      }
      setDetail(nextDetail.data);
      setAudit(nextAudit.ok ? nextAudit.data : []);
      if (!nextAudit.ok) setNotice(nextAudit.message);
      return true;
    },
    [client, token],
  );

  const refresh = useCallback(
    async (caseId: string | null) => {
      await loadOverview();
      const query = queryRef.current;
      await loadQueue(query.cursor, query.filter);
      const currentId = selectedRef.current ?? caseId;
      if (currentId) await loadCase(currentId);
    },
    [loadCase, loadOverview, loadQueue],
  );

  useEffect(() => {
    void loadOverview();
    void loadQueue(null, "");
  }, [loadOverview, loadQueue]);

  async function selectCase(caseId: string) {
    selectedRef.current = caseId;
    setSelectedId(caseId);
    setReplayed(false);
    setNotice(null);
    setBusy(true);
    const applied = await loadCase(caseId);
    if (applied) setBusy(false);
  }

  async function changeFilter(filter: CaseState | "") {
    queryRef.current = { filter, cursor: null };
    setStateFilter(filter);
    setCursors([null]);
    await loadQueue(null, filter);
  }

  async function mutate(task: () => Promise<{ refreshCase: boolean; ambiguous: boolean; message: string | null }>) {
    if (!detail || mutation.current) return;
    mutation.current = true;
    const caseId = detail.case.id;
    setBusy(true);
    try {
      const outcome = await task();
      if (selectedRef.current !== caseId) return;
      setNotice(outcome.message);
      if (outcome.refreshCase) await refresh(caseId);
      if (selectedRef.current === caseId) setBusy(false);
    } finally {
      mutation.current = false;
    }
  }

  return (
    <>
      <a className="skip" href="#case">
        Skip to case
      </a>
      <header className="top">
        <div>
          <h1>Sentinel analyst</h1>
          <p className="session-line">
            {overview ? investigatorLabel(overview.investigator) : "Loading investigator mode"}
          </p>
          <p className="session-line">
            {session.actor_kind === "human" ? "Human session" : "System session"} expires{" "}
            {session.expires_at}. {capabilityLine(session)}
          </p>
        </div>
        <button type="button" className="secondary" onClick={onSignOut}>
          Sign out
        </button>
      </header>
      <p className="status" role="status">
        {notice}
      </p>
      {overview ? (
        <dl className="counts" aria-label="Session overview">
          <div>
            <dt>Open</dt>
            <dd>{overview.cases_by_state.open}</dd>
          </div>
          <div>
            <dt>Investigating</dt>
            <dd>{overview.cases_by_state.investigating}</dd>
          </div>
          <div>
            <dt>Awaiting approval</dt>
            <dd>{overview.cases_by_state.awaiting_approval}</dd>
          </div>
          <div>
            <dt>Closed</dt>
            <dd>{overview.cases_by_state.closed}</dd>
          </div>
          <div>
            <dt>Inconclusive</dt>
            <dd>{overview.cases_by_state.inconclusive}</dd>
          </div>
          <div>
            <dt>Transactions</dt>
            <dd>{overview.transactions}</dd>
          </div>
          <div>
            <dt>Alerts</dt>
            <dd>{overview.alerts}</dd>
          </div>
          <div>
            <dt>Simulated actions</dt>
            <dd>{overview.simulated_actions}</dd>
          </div>
        </dl>
      ) : null}
      <div className="desk">
        <div>
          <Queue
            page={page}
            loading={loadingQueue}
            state={stateFilter}
            selectedId={selectedId}
            hasPrevious={pageIndex > 0}
            busy={busy || queuePending}
            onState={(filter) => void changeFilter(filter)}
            onSelect={(caseId) => void selectCase(caseId)}
            onPrevious={() => {
              if (queueFlight.current || pageIndex <= 0) return;
              const next = cursors.slice(0, -1);
              const cursor = next[next.length - 1] ?? null;
              queryRef.current = { filter: queryRef.current.filter, cursor };
              setCursors(next);
              void loadQueue(cursor, queryRef.current.filter);
            }}
            onNext={() => {
              if (queueFlight.current || !page?.next_cursor) return;
              const cursor = page.next_cursor;
              queryRef.current = { filter: queryRef.current.filter, cursor };
              setCursors((current) => [...current, cursor]);
              void loadQueue(cursor, queryRef.current.filter);
            }}
          />
          {allows(session, "ingest_transaction") ? (
            <IngestForm
              client={client}
              token={token}
              onRecorded={(caseId) => {
                if (caseId) {
                  selectedRef.current = caseId;
                  setSelectedId(caseId);
                }
                void refresh(caseId);
              }}
            />
          ) : (
            <p className="queue">This session cannot record transactions.</p>
          )}
        </div>
        <CasePaneBoundary key={selectedId ?? "none"}>
        {detail && selectedId === detail.case.id ? (
          <CaseFile
            detail={detail}
            audit={audit}
            session={session}
            busy={busy}
            replayed={replayed}
            onInvestigate={() =>
              void mutate(async () => {
                const result = await client.investigate(token, detail.case.id, detail.case.revision);
                return {
                  refreshCase: true,
                  ambiguous: !result.ok && result.ambiguous,
                  message: result.ok ? null : result.message,
                };
              })
            }
            onDecide={(decision) =>
              void mutate(async () => {
                const intent = detail.action_intents[detail.action_intents.length - 1];
                if (!intent || intent.intent.case_revision !== detail.case.revision) {
                  return { refreshCase: true, ambiguous: false, message: "The proposed action is no longer current." };
                }
                const result = await client.decide(token, intent.intent.id, decision);
                return {
                  refreshCase: true,
                  ambiguous: !result.ok && result.ambiguous,
                  message: result.ok ? null : result.message,
                };
              })
            }
            onExecute={() =>
              void mutate(async () => {
                const intent = detail.action_intents[detail.action_intents.length - 1];
                const approvalId = intent?.approval?.id;
                if (!approvalId || intent.intent.case_revision !== detail.case.revision) {
                  return { refreshCase: true, ambiguous: false, message: "There is no current approval to execute." };
                }
                const next = beginExecution(attempt.current, approvalId);
                attempt.current = next;
                const result = await client.execute(token, approvalId, next.key);
                const ambiguous = !result.ok && result.ambiguous;
                attempt.current = finishExecution(attempt.current, approvalId, ambiguous);
                if (result.ok) setReplayed(result.data.replayed);
                return {
                  refreshCase: true,
                  ambiguous,
                  message: result.ok ? null : result.message,
                };
              })
            }
          />
        ) : (
          <p className="case">Select a case to read its evidence, proposal, and audit.</p>
        )}
        </CasePaneBoundary>
      </div>
    </>
  );
}
