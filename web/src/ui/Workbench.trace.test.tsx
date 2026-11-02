import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { SentinelClient } from "../api/client";
import { acceptTrace, type InvestigationTrace } from "../api/trace";
import type { ApiResult, AuditEvent, CaseDetail, CasePage, Overview, SessionView } from "../api/types";
import { App } from "../App";
import { Workbench } from "./Workbench";

const here = dirname(fileURLToPath(import.meta.url));
const v1 = resolve(here, "../../../contracts/http/examples");
const v12 = resolve(here, "../fixtures/http-v1.2");

function response<T>(dir: string, name: string): T {
  return JSON.parse(readFileSync(resolve(dir, name), "utf8")).response as T;
}

const session = response<SessionView>(v1, "session.json");
const overview = response<Overview>(v1, "overview.json");
const base = response<CaseDetail>(v1, "investigate.json");

function ok<T>(data: T): ApiResult<T> {
  return { ok: true, status: 200, data };
}

function failed(status: number, code: string | null, message: string, ambiguous = false): ApiResult<never> {
  return { ok: false, ambiguous, status, code, message, details: [] };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

function detailFor(id: string, externalId: string, revision = base.case.revision): CaseDetail {
  const next = structuredClone(base);
  next.case = { ...next.case, id, revision };
  next.transaction = { ...next.transaction, external_id: externalId };
  next.action_intents = next.action_intents.map((item) => ({
    ...item,
    intent: { ...item.intent, case_id: id, case_revision: revision },
  }));
  return next;
}

/** An accepted example re-addressed to `caseId`, with a marker note on its first attempt. */
function traceFor(caseId: string, name: string, marker: string, revision?: number): InvestigationTrace {
  const value = structuredClone(JSON.parse(readFileSync(resolve(v12, `${name}.json`), "utf8")).response);
  value.case_id = "00000000-0000-4000-8000-000000000000";
  const parsed = acceptTrace(value)!;
  parsed.case_id = caseId;
  if (revision !== undefined) parsed.case_revision = revision;
  const attempt = parsed.selected?.attempts[0];
  if (attempt?.output) attempt.output = { ...attempt.output, note: marker };
  return parsed;
}

function summary(detail: CaseDetail): CasePage["items"][number] {
  return {
    id: detail.case.id,
    state: detail.case.state,
    revision: detail.case.revision,
    created_at: detail.case.created_at,
    updated_at: detail.case.updated_at,
    alert_id: detail.case.alert_id,
    transaction_id: detail.transaction.id,
    external_id: detail.transaction.external_id,
    amount: detail.transaction.amount,
    direction: detail.transaction.direction,
    score: detail.alert.score,
    threshold: detail.alert.threshold,
    scoring_kind: detail.alert.scoring_kind,
    score_semantics: detail.alert.score_semantics,
  };
}

function clientWith(details: CaseDetail[], trace: SentinelClient["trace"], extra: Partial<SentinelClient> = {}) {
  return {
    overview: vi.fn(async () => ok(overview)),
    listCases: vi.fn(async () => ok({ items: details.map(summary), next_cursor: null, limit: 25 })),
    caseDetail: vi.fn(async (_: string, id: string) => ok(details.find((item) => item.case.id === id)!)),
    audit: vi.fn(async () => ok([] as AuditEvent[])),
    ingest: vi.fn(),
    investigate: vi.fn(),
    decide: vi.fn(),
    execute: vi.fn(),
    trace: vi.fn(trace),
    ...extra,
  } as unknown as SentinelClient & { trace: ReturnType<typeof vi.fn> };
}

async function flush() {
  await act(async () => {
    for (let i = 0; i < 5; i += 1) await Promise.resolve();
  });
}

afterEach(() => cleanup());

describe("trace request ownership", () => {
  it("keeps the later case's trace when the earlier trace arrives last", async () => {
    const a = detailFor("case-a", "external-a");
    const b = detailFor("case-b", "external-b");
    const pending: Record<string, ReturnType<typeof deferred<ApiResult<InvestigationTrace>>>> = {
      "case-a": deferred(),
      "case-b": deferred(),
    };
    const client = clientWith([a, b], (_t, caseId) => pending[caseId].promise);
    render(<Workbench client={client} token="memory-token" session={session} onSignOut={vi.fn()} />);
    (await screen.findByRole("button", { name: /external-a/ })).click();
    await waitFor(() => expect(client.trace).toHaveBeenCalledTimes(1)); // A's read is in flight
    screen.getByRole("button", { name: /external-b/ }).click();
    await waitFor(() => expect(client.trace).toHaveBeenCalledTimes(2));
    expect(screen.queryByText("Trace note for A")).not.toBeInTheDocument();
    await act(async () => pending["case-b"].resolve(ok(traceFor("case-b", "trace_untrusted_note", "Trace note for B", 3))));
    expect(await screen.findByText("Trace note for B")).toBeInTheDocument();
    await act(async () => pending["case-a"].resolve(ok(traceFor("case-a", "trace_untrusted_note", "Trace note for A", 3))));
    await flush();
    expect(screen.getByText("Trace note for B")).toBeInTheDocument();
    expect(screen.queryByText("Trace note for A")).not.toBeInTheDocument();
    // The earlier request was aborted, and the case switch cleared the panel before B loaded.
    const firstSignal = (client.trace.mock.calls[0] as unknown[])[3] as AbortSignal;
    expect(firstSignal.aborted).toBe(true);
  });

  it("applies only the most recent workflow selection", async () => {
    const a = detailFor("case-a", "external-a", 4);
    const latest = traceFor("case-a", "trace_retry_latest", "Newest marker", 4);
    const prior = traceFor("case-a", "trace_retry_prior", "Prior marker", 4);
    const priorId = latest.workflows[1].id;
    const slowPrior = deferred<ApiResult<InvestigationTrace>>();
    const client = clientWith([a], (_t, _c, workflowId) => (workflowId === priorId ? slowPrior.promise : Promise.resolve(ok(latest))));
    render(<Workbench client={client} token="memory-token" session={session} onSignOut={vi.fn()} />);
    (await screen.findByRole("button", { name: /external-a/ })).click();
    expect(await screen.findByText("Newest marker")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "View workflow at case revision 2" }));
    await userEvent.click(screen.getByRole("button", { name: "Follow the newest workflow" }));
    expect(await screen.findByText("Newest marker")).toBeInTheDocument();
    await act(async () => slowPrior.resolve(ok(prior)));
    await flush();
    expect(screen.getByText("Newest marker")).toBeInTheDocument();
    expect(screen.queryByText("Prior marker")).not.toBeInTheDocument();
  });

  it("never shows a trace whose body names another case", async () => {
    const a = detailFor("case-a", "external-a", 3);
    const client = clientWith([a], async () => ok(traceFor("case-z", "trace_untrusted_note", "Foreign marker", 3)));
    render(<Workbench client={client} token="memory-token" session={session} onSignOut={vi.fn()} />);
    (await screen.findByRole("button", { name: /external-a/ })).click();
    expect(await screen.findByText("The trace response did not match this case. Try again.")).toBeInTheDocument();
    expect(screen.queryByText("Foreign marker")).not.toBeInTheDocument();
  });

  it("a sign-out drops a late trace; the next session never sees it", async () => {
    const a = detailFor("case-a", "external-a", 3);
    const late = deferred<ApiResult<InvestigationTrace>>();
    const client = clientWith([a], () => late.promise, {
      health: vi.fn(async () => ok({ status: "ok", investigator: "three-role-workflow" })),
      session: vi.fn(async () => ok(session)),
    } as Partial<SentinelClient>);
    render(<App client={client} />);
    await userEvent.type(screen.getByLabelText("Session token"), "first-token");
    await userEvent.click(screen.getByRole("button", { name: "Connect" }));
    (await screen.findByRole("button", { name: /external-a/ })).click();
    await screen.findByText("Loading the investigation trace.");
    await userEvent.click(screen.getByRole("button", { name: "Sign out" }));
    await act(async () => late.resolve(ok(traceFor("case-a", "trace_untrusted_note", "Old session marker", 3))));
    await flush();
    expect(screen.queryByText("Old session marker")).not.toBeInTheDocument();
    client.trace.mockImplementation(async () => failed(404, "not_found", "Not found."));
    await userEvent.type(screen.getByLabelText("Session token"), "second-token");
    await userEvent.click(screen.getByRole("button", { name: "Connect" }));
    (await screen.findByRole("button", { name: /external-a/ })).click();
    expect(await screen.findByText("No investigation trace is available for this case.")).toBeInTheDocument();
    expect(screen.queryByText("Old session marker")).not.toBeInTheDocument();
    const tokens = client.trace.mock.calls.map((call) => (call as unknown[])[0]);
    expect(tokens).toEqual(["first-token", "second-token"]);
  });
});

describe("refresh and the human action boundary", () => {
  it("re-reads after a mutation, keeps an explicit selection and uses GET only", async () => {
    let revision = 4;
    const latest = traceFor("case-a", "trace_retry_latest", "Newest marker", 4);
    const priorId = latest.workflows[1].id;
    const details = () => [detailFor("case-a", "external-a", revision)];
    const traceCalls: Array<string | null> = [];
    const client = clientWith(details(), async (_t, _c, workflowId) => {
      traceCalls.push(workflowId);
      const value = traceFor("case-a", workflowId ? "trace_retry_prior" : "trace_retry_latest", workflowId ? "Prior marker" : "Newest marker", revision);
      return ok(value);
    }, {
      caseDetail: vi.fn(async () => ok(details()[0])),
      investigate: vi.fn(async () => {
        revision = 5;
        return failed(409, "stale_case_revision", "The case changed. Re-read it.");
      }),
    } as Partial<SentinelClient>);
    const investigable = detailFor("case-a", "external-a", 4);
    investigable.case = { ...investigable.case, state: "open" };
    investigable.action_intents = [];
    (client.caseDetail as ReturnType<typeof vi.fn>).mockImplementation(async () => {
      const value = structuredClone(investigable);
      value.case.revision = revision;
      return ok(value);
    });
    render(<Workbench client={client} token="memory-token" session={session} onSignOut={vi.fn()} />);
    (await screen.findByRole("button", { name: /external-a/ })).click();
    expect(await screen.findByText("Newest marker")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "View workflow at case revision 2" }));
    expect(await screen.findByText("Prior marker")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Investigate case" }));
    await waitFor(() => expect(traceCalls).toEqual([null, priorId, priorId]));
    expect(await screen.findByText("Prior marker")).toBeInTheDocument();
    expect(client.investigate).toHaveBeenCalledTimes(1); // only the explicit button
    await userEvent.click(screen.getByRole("button", { name: "Refresh trace" }));
    await waitFor(() => expect(traceCalls).toHaveLength(4));
    expect(client.investigate).toHaveBeenCalledTimes(1);
    expect(client.decide).not.toHaveBeenCalled();
    expect(client.execute).not.toHaveBeenCalled();
  });

  it("a missing explicit workflow offers the newest; an unconfirmed reply offers retry", async () => {
    const a = detailFor("case-a", "external-a", 4);
    const latest = traceFor("case-a", "trace_retry_latest", "Newest marker", 4);
    let mode: "ok" | "missing" | "ambiguous" = "ok";
    const client = clientWith([a], async (_t, _c, workflowId) => {
      if (mode === "ambiguous") return failed(502, null, "The server's reply could not be confirmed.", true);
      if (workflowId && mode === "missing") return failed(404, "not_found", "Not found.");
      return ok(latest);
    });
    render(<Workbench client={client} token="memory-token" session={session} onSignOut={vi.fn()} />);
    (await screen.findByRole("button", { name: /external-a/ })).click();
    await screen.findByText("Newest marker");
    mode = "missing";
    await userEvent.click(screen.getByRole("button", { name: "View workflow at case revision 2" }));
    expect(await screen.findByText("That workflow is not available for this case.")).toBeInTheDocument();
    mode = "ambiguous";
    await userEvent.click(screen.getByRole("button", { name: "Show the newest workflow" }));
    expect(await screen.findByText("The server's reply could not be confirmed.")).toBeInTheDocument();
    expect(screen.queryByText("Newest marker")).not.toBeInTheDocument(); // not fabricated
    mode = "ok";
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("Newest marker")).toBeInTheDocument();
  });

  it("the case history message does not contradict a zero-role workflow", async () => {
    const empty = detailFor("case-a", "external-a", 3);
    empty.agent_runs = [];
    empty.action_intents = [];
    empty.case = { ...empty.case, state: "open" };
    const client = clientWith([empty], async () => ok(traceFor("case-a", "trace_zero_roles", "", 3)));
    render(<Workbench client={client} token="memory-token" session={session} onSignOut={vi.fn()} />);
    (await screen.findByRole("button", { name: /external-a/ })).click();
    expect(await screen.findByText(/No role run is recorded in this case history\. The investigation trace shows/)).toBeInTheDocument();
    expect(screen.queryByText("No investigation has been recorded.")).not.toBeInTheDocument();
  });

  it("a session without read_case never requests a trace", async () => {
    const a = detailFor("case-a", "external-a", 3);
    const client = clientWith([a], async () => ok(traceFor("case-a", "trace_untrusted_note", "x", 3)));
    const limited = { ...session, capabilities: ["ingest_transaction"] } as SessionView;
    render(<Workbench client={client} token="memory-token" session={limited} onSignOut={vi.fn()} />);
    await flush();
    expect(client.trace).not.toHaveBeenCalled();
  });
});
