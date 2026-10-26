import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { SentinelClient } from "../api/client";
import type { ApiResult, AuditEvent, CaseDetail, CasePage, Overview, SessionView } from "../api/types";
import { Workbench } from "./Workbench";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../../../contracts/http/examples");

function fixture<T>(name: string): T {
  return JSON.parse(readFileSync(resolve(root, name), "utf8")).response as T;
}

const session = fixture<SessionView>("session.json");
const overview = fixture<Overview>("overview.json");
const base = fixture<CaseDetail>("investigate.json");
const auditBase = fixture<AuditEvent[]>("audit.json");

function ok<T>(data: T): ApiResult<T> {
  return { ok: true, status: 200, data };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

function withIdentity(detail: CaseDetail, id: string, externalId: string, marker: string): CaseDetail {
  const next = structuredClone(detail);
  next.case = { ...next.case, id };
  next.transaction = { ...next.transaction, id: `${id}-txn`, external_id: externalId };
  next.action_intents[0].intent = {
    ...next.action_intents[0].intent,
    case_id: id,
    parameters: { ...next.action_intents[0].intent.parameters, transaction_id: `${id}-txn` },
  };
  next.agent_runs[0].finding = {
    operation: "simulated_hold",
    reason_code: "velocity_pattern",
    rationale: marker,
  };
  return next;
}

function auditFor(caseId: string, marker: string): AuditEvent[] {
  return [{ ...auditBase[0], id: `${caseId}-audit`, case_id: caseId, event_type: "alert_raised", outcome: "success" },
    { ...auditBase[0], id: `${caseId}-note`, case_id: caseId, event_type: marker }];
}

function page(items: CasePage["items"], cursor: string | null = null): CasePage {
  return { items, next_cursor: cursor, limit: 25 };
}

function summary(detail: CaseDetail, externalId: string): CasePage["items"][number] {
  return {
    id: detail.case.id,
    state: detail.case.state,
    revision: detail.case.revision,
    created_at: detail.case.created_at,
    updated_at: detail.case.updated_at,
    alert_id: detail.case.alert_id,
    transaction_id: detail.transaction.id,
    external_id: externalId,
    amount: detail.transaction.amount,
    direction: detail.transaction.direction,
    score: detail.alert.score,
    threshold: detail.alert.threshold,
    scoring_kind: detail.alert.scoring_kind,
    score_semantics: detail.alert.score_semantics,
  };
}

afterEach(() => cleanup());

describe("request ownership", () => {
  it("keeps the later case and its audit when the earlier response arrives last", async () => {
    const caseA = withIdentity(base, "case-a", "external-a", "Rationale for case A");
    const caseB = withIdentity(base, "case-b", "external-b", "Rationale for case B");
    const detailA = deferred<ApiResult<CaseDetail>>();
    const detailB = deferred<ApiResult<CaseDetail>>();
    const auditA = deferred<ApiResult<AuditEvent[]>>();
    const auditB = deferred<ApiResult<AuditEvent[]>>();
    const client = {
      overview: vi.fn(async () => ok(overview)),
      listCases: vi.fn(async () => ok(page([summary(caseA, "external-a"), summary(caseB, "external-b")], "cursor-1"))),
      caseDetail: vi.fn((_: string, id: string) => (id === "case-a" ? detailA.promise : detailB.promise)),
      audit: vi.fn((_: string, id: string) => (id === "case-a" ? auditA.promise : auditB.promise)),
      ingest: vi.fn(),
      investigate: vi.fn(),
      decide: vi.fn(),
      execute: vi.fn(),
    } as unknown as SentinelClient;
    render(<Workbench client={client} token="memory-token" session={session} onSignOut={vi.fn()} />);
    const rowA = await screen.findByRole("button", { name: /external-a/ });
    const rowB = screen.getByRole("button", { name: /external-b/ });
    rowA.click();
    rowB.click();
    await act(async () => {
      detailB.resolve(ok(caseB));
      auditB.resolve(ok(auditFor("case-b", "case_b_audit_marker")));
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(await screen.findByText("Rationale for case B")).toBeInTheDocument();
    expect(screen.getByText(/Case b audit marker/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next page" })).toBeEnabled();
    await act(async () => {
      detailA.resolve(ok(caseA));
      auditA.resolve(ok(auditFor("case-a", "case_a_audit_marker")));
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(screen.getByText("Rationale for case B")).toBeInTheDocument();
    expect(screen.getByText(/Case b audit marker/)).toBeInTheDocument();
    expect(screen.queryByText("Rationale for case A")).not.toBeInTheDocument();
    expect(screen.queryByText(/Case a audit marker/)).not.toBeInTheDocument();
    expect(screen.queryByText("Select a case to read its evidence, proposal, and audit.")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next page" })).toBeEnabled();
  });

  it("ignores a duplicate Next and returns to the first page on Previous", async () => {
    const cursors: Array<string | null> = [];
    const second = deferred<ApiResult<CasePage>>();
    const firstDetail = withIdentity(base, "case-page", "page-one", "Page one rationale");
    const client = {
      overview: vi.fn(async () => ok(overview)),
      listCases: vi.fn(async (_token: string, query: { cursor?: string | null }) => {
        const cursor = query.cursor ?? null;
        cursors.push(cursor);
        if (cursor === "cursor-1") return second.promise;
        return ok(page([summary(firstDetail, "page-one")], "cursor-1"));
      }),
      caseDetail: vi.fn(async () => ok(firstDetail)),
      audit: vi.fn(async () => ok([])),
      ingest: vi.fn(),
      investigate: vi.fn(),
      decide: vi.fn(),
      execute: vi.fn(),
    } as unknown as SentinelClient;
    render(<Workbench client={client} token="memory-token" session={session} onSignOut={vi.fn()} />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Next page" })).toBeEnabled());
    const next = screen.getByRole("button", { name: "Next page" });
    next.click();
    next.click();
    expect(cursors.filter((cursor) => cursor === "cursor-1")).toHaveLength(1);
    await act(async () => {
      second.resolve(ok(page([summary(withIdentity(base, "case-two", "page-two", "Page two"), "page-two")], "cursor-2")));
    });
    await screen.findByRole("button", { name: /page-two/ });
    expect(screen.queryByText("Loading cases.")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous page" })).toBeEnabled();
    screen.getByRole("button", { name: "Previous page" }).click();
    await waitFor(() => {
      expect(cursors.at(-1)).toBeNull();
    });
    expect(cursors.filter((cursor) => cursor === "cursor-1")).toHaveLength(1);
    await screen.findByRole("button", { name: /page-one/ });
    expect(screen.queryByRole("button", { name: /page-two/ })).not.toBeInTheDocument();
    expect(screen.queryByText("Loading cases.")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous page" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next page" })).toBeEnabled();
  });

  it("keeps the latest filter when an older filter response arrives later", async () => {
    const openResult = deferred<ApiResult<CasePage>>();
    const closedResult = deferred<ApiResult<CasePage>>();
    const openDetail = withIdentity(base, "case-open", "open-only", "Open rationale");
    const closedDetail = withIdentity(base, "case-closed", "closed-only", "Closed rationale");
    const client = {
      overview: vi.fn(async () => ok(overview)),
      listCases: vi.fn(async (_token: string, query: { state?: string }) => {
        if (query.state === "open") return openResult.promise;
        if (query.state === "closed") return closedResult.promise;
        return ok(page([summary(openDetail, "open-only")]));
      }),
      caseDetail: vi.fn(async () => ok(openDetail)),
      audit: vi.fn(async () => ok([])),
      ingest: vi.fn(),
      investigate: vi.fn(),
      decide: vi.fn(),
      execute: vi.fn(),
    } as unknown as SentinelClient;
    render(<Workbench client={client} token="memory-token" session={session} onSignOut={vi.fn()} />);
    const filter = await screen.findByLabelText("Case state");
    await userEvent.selectOptions(filter, "open");
    await userEvent.selectOptions(filter, "closed");
    await act(async () => {
      closedResult.resolve(ok(page([summary(closedDetail, "closed-only")], "cursor-closed")));
    });
    expect(await screen.findByRole("button", { name: /closed-only/ })).toBeInTheDocument();
    expect(screen.queryByText("Loading cases.")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next page" })).toBeEnabled();
    expect((filter as HTMLSelectElement).value).toBe("closed");
    await act(async () => {
      openResult.resolve(ok(page([summary(openDetail, "open-only")], "cursor-open")));
    });
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /closed-only/ })).toBeInTheDocument();
    });
    expect(screen.queryByRole("button", { name: /open-only/ })).not.toBeInTheDocument();
    expect(screen.queryByText("Loading cases.")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next page" })).toBeEnabled();
    expect((filter as HTMLSelectElement).value).toBe("closed");
  });

  it("keeps a closed filter when a delayed approval refresh resumes", async () => {
    const queries: string[] = [];
    const refreshOverview = deferred<ApiResult<Overview>>();
    const waiting = withIdentity(base, "case-wait", "all-state-row", "Waiting rationale");
    const closedDetail = withIdentity(base, "case-closed", "closed-only", "Closed rationale");
    closedDetail.case = { ...closedDetail.case, state: "closed" };
    let overviews = 0;
    const client = {
      overview: vi.fn(async () => {
        overviews += 1;
        if (overviews === 1) return ok(overview);
        return refreshOverview.promise;
      }),
      listCases: vi.fn(async (_token: string, query: { state?: string }) => {
        const state = query.state ?? "";
        queries.push(state);
        if (state === "closed") return ok(page([summary(closedDetail, "closed-only")]));
        return ok(page([summary(waiting, "all-state-row")], "cursor-all"));
      }),
      caseDetail: vi.fn(async () => ok(waiting)),
      audit: vi.fn(async () => ok([])),
      ingest: vi.fn(),
      investigate: vi.fn(),
      decide: vi.fn(async () => ok({ id: "approval-refresh", decision: "approved" as const })),
      execute: vi.fn(),
    } as unknown as SentinelClient;
    const user = userEvent.setup();
    render(<Workbench client={client} token="memory-token" session={session} onSignOut={vi.fn()} />);
    await user.click(await screen.findByRole("button", { name: /all-state-row/ }));
    await user.click(await screen.findByRole("button", { name: "Approve" }));
    await waitFor(() => expect(overviews).toBe(2));
    const detailReads = vi.mocked(client.caseDetail).mock.calls.length;
    const filter = screen.getByLabelText("Case state");
    await user.selectOptions(filter, "closed");
    expect(await screen.findByRole("button", { name: /closed-only/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /all-state-row/ })).not.toBeInTheDocument();
    expect(filter).toHaveValue("closed");
    await act(async () => {
      refreshOverview.resolve(ok(overview));
    });
    await waitFor(() => expect(vi.mocked(client.caseDetail).mock.calls.length).toBeGreaterThan(detailReads));
    expect(screen.getByRole("button", { name: /closed-only/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /all-state-row/ })).not.toBeInTheDocument();
    expect(filter).toHaveValue("closed");
    expect(queries.slice(queries.indexOf("closed") + 1).every((state) => state === "closed")).toBe(true);
  });
});
