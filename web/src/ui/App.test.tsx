import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SentinelClient } from "../api/client";
import { unconfirmedMessage } from "../api/format";
import type {
  ApiResult,
  AuditEvent,
  CaseDetail,
  CasePage,
  ExecuteResponse,
  Overview,
  SessionView,
  SimulatedAction,
} from "../api/types";
import { App } from "../App";
import { Workbench } from "./Workbench";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../../../contracts/http/examples");

function fixture<T>(name: string): T {
  return JSON.parse(readFileSync(resolve(root, name), "utf8")).response as T;
}

const session = fixture<SessionView>("session.json");
const overview = fixture<Overview>("overview.json");
const investigated = fixture<CaseDetail>("investigate.json");
const approval = fixture<{ id: string; decision: "approved" }>("approval.json");
const audit = fixture<AuditEvent[]>("audit.json");
const emptyPage: CasePage = { items: [], next_cursor: null, limit: 25 };

function ok<T>(data: T): ApiResult<T> {
  return { ok: true, status: 200, data };
}

function handled(status: number, code: string, message: string): ApiResult<never> {
  return { ok: false, ambiguous: false, status, code, message, details: [] };
}

function ambiguous(): ApiResult<never> {
  return { ok: false, ambiguous: true, status: null, code: null, message: unconfirmedMessage(), details: [] };
}

function pageFor(detail: CaseDetail): CasePage {
  return {
    limit: 25,
    next_cursor: null,
    items: [
      {
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
      },
    ],
  };
}

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
});

describe("session memory", () => {
  it("keeps the token out of storage, the URL, and the connected screen", async () => {
    const token = "sentinel-test-token";
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    const user = userEvent.setup();
    const client = {
      health: vi.fn(async () => ok({ status: "ok", investigator: "deterministic-investigator" })),
      session: vi.fn(async () => ok(session)),
      overview: vi.fn(async () => ok(overview)),
      listCases: vi.fn(async () => ok(emptyPage)),
      caseDetail: vi.fn(),
      audit: vi.fn(),
      ingest: vi.fn(),
      investigate: vi.fn(),
      decide: vi.fn(),
      execute: vi.fn(),
    } as SentinelClient;
    render(<App client={client} />);
    const tokenField = screen.getByLabelText("Session token");
    await user.click(tokenField);
    await user.type(tokenField, token);
    await user.tab();
    expect(screen.getByRole("button", { name: "Connect" })).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(await screen.findByRole("heading", { name: "Case queue" })).toBeInTheDocument();
    expect(screen.getByText("Deterministic investigator i1")).toBeInTheDocument();
    expect(screen.getByText("No cases in this session.")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(document.body.textContent).not.toContain(token);
    expect(window.location.href).not.toContain(token);
    expect(setItem).not.toHaveBeenCalled();
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
    await user.click(screen.getByRole("button", { name: "Sign out" }));
    expect(screen.getByRole("button", { name: "Connect" })).toBeInTheDocument();
  });
});

describe("workbench actions", () => {
  it("refreshes server state after a stale revision", async () => {
    const user = userEvent.setup();
    const reopened = fixture<CaseDetail>("case_detail_reopened.json");
    let reads = 0;
    const client = {
      overview: vi.fn(async () => ok(overview)),
      listCases: vi.fn(async () => ok(pageFor(reopened))),
      caseDetail: vi.fn(async () => {
        reads += 1;
        return ok(reopened);
      }),
      audit: vi.fn(async () => ok(audit)),
      investigate: vi.fn(async () =>
        handled(409, "stale_case_revision", "The case changed. The latest server state is shown."),
      ),
      ingest: vi.fn(),
      decide: vi.fn(),
      execute: vi.fn(),
    } as unknown as SentinelClient;
    render(<Workbench client={client} token="memory-token" session={session} onSignOut={vi.fn()} />);
    await user.click(await screen.findByRole("button", { name: /1200\.00 USD/ }));
    await user.click(await screen.findByRole("button", { name: "Investigate case" }));
    expect(await screen.findByText(/latest server state/)).toBeInTheDocument();
    expect(reads).toBeGreaterThan(1);
  });

  it("retries a lost execution with the original key and one stored action", async () => {
    const user = userEvent.setup();
    const detail = structuredClone(investigated);
    detail.action_intents[0].approval = {
      ...fixture<CaseDetail["action_intents"][0]["approval"] & object>("approval.json"),
      id: approval.id,
      decision: "approved",
    };
    const stored = new Map<string, SimulatedAction>();
    let drop = true;
    const keys: string[] = [];
    const action = fixture<ExecuteResponse>("execute.json").action;
    const client = {
      overview: vi.fn(async () => ok(overview)),
      listCases: vi.fn(async () => ok(pageFor(detail))),
      caseDetail: vi.fn(async () => ok(detail)),
      audit: vi.fn(async () => ok(audit)),
      investigate: vi.fn(),
      decide: vi.fn(),
      ingest: vi.fn(),
      execute: vi.fn(async (_token: string, _approvalId: string, key: string) => {
        keys.push(key);
        if (!stored.has(key)) stored.set(key, { ...action, idempotency_key: key });
        if (drop) {
          drop = false;
          return ambiguous();
        }
        return ok({ action: stored.get(key)!, replayed: true });
      }),
    } as unknown as SentinelClient;
    render(<Harness client={client} />);
    await user.click(await screen.findByRole("button", { name: /2500\.00 USD/ }));
    const execute = await screen.findByRole("button", { name: "Execute simulated hold" });
    await user.click(execute);
    expect(await screen.findByText(unconfirmedMessage())).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Execute simulated hold" }));
    expect(await screen.findByText(/already recorded/)).toBeInTheDocument();
    expect(keys).toEqual([keys[0], keys[0]]);
    expect(stored.size).toBe(1);
  });
});

function Harness({ client }: { client: SentinelClient }) {
  const [gone, setGone] = useState(false);
  if (gone) return <p>Signed out</p>;
  return <Workbench client={client} token="memory-token" session={session} onSignOut={() => setGone(true)} />;
}
