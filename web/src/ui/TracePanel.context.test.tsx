import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { act, cleanup, render, screen } from "@testing-library/react";
import { useLayoutEffect } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { SentinelClient } from "../api/client";
import { acceptTrace, type InvestigationTrace } from "../api/trace";
import { TracePanel, useTrace, type TraceControl } from "./TracePanel";

/**
 * R39 (review G3C-B-bb5943e): render-visible trace content belongs to its session, case,
 * workflow selection and read permission. These tests observe the DOM committed by React in
 * a layout effect, before any passive effect runs, so a payload that is only cleared later
 * by an effect fails them. (A committed DOM is not proof of a browser paint.)
 */
const fixtures = resolve(dirname(fileURLToPath(import.meta.url)), "../fixtures/http-v1.2");

function load(name: string): InvestigationTrace {
  const parsed = acceptTrace(JSON.parse(readFileSync(resolve(fixtures, `${name}.json`), "utf8")).response);
  if (!parsed) throw new Error(name);
  return parsed;
}

const source = load("trace_untrusted_note");
const marker = (source.selected!.attempts[0].output as { note: string }).note;
const firstCase = source.case_id;
const otherCase = "00000000-0000-4000-8000-000000000002";

afterEach(() => cleanup());

type Props = { caseId: string; token: string; canRead: boolean };
type Commit = Props & { workflowId: string | null; text: string };

function harness(client: SentinelClient) {
  const commits: Commit[] = [];
  const controls: TraceControl[] = [];
  function Probe({ caseId, token, canRead }: Props) {
    const control = useTrace({ client, token, caseId, canRead, refreshKey: 0 });
    controls.push(control);
    useLayoutEffect(() => {
      commits.push({ caseId, token, canRead, workflowId: control.workflowId,
        text: document.querySelector("#trace")?.textContent ?? "" });
    });
    return <TracePanel control={control} caseRevision={source.case_revision} evidenceIds={new Set()} />;
  }
  return { Probe, commits, control: () => controls[controls.length - 1] };
}

describe("no committed trace content under a changed context", () => {
  const contexts: Array<[string, Props, (commit: Commit) => boolean]> = [
    ["case", { caseId: otherCase, token: "first-session", canRead: true }, (c) => c.caseId === otherCase],
    ["session", { caseId: firstCase, token: "second-session", canRead: true }, (c) => c.token === "second-session"],
    ["read permission", { caseId: firstCase, token: "first-session", canRead: false }, (c) => !c.canRead],
  ];

  it.each(contexts)("%s change", async (_name, next, changed) => {
    const client = {
      trace: vi.fn((token: string, caseId: string) =>
        token === "first-session" && caseId === firstCase
          ? Promise.resolve({ ok: true, status: 200, data: structuredClone(source) })
          : new Promise(() => {})),
    } as unknown as SentinelClient;
    const { Probe, commits } = harness(client);
    const view = render(<Probe caseId={firstCase} token="first-session" canRead />);
    await screen.findByText(marker);
    view.rerender(<Probe {...next} />);
    const after = commits.filter(changed);
    expect(after.length).toBeGreaterThan(0);
    // Not even the first commit under the new context may contain the old trace or its list.
    expect(after.filter((commit) => commit.text.includes(marker))).toEqual([]);
    expect(after.filter((commit) => commit.text.includes("Workflow history"))).toEqual([]);
  });

  it("an explicit workflow selection never commits the previously selected workflow", async () => {
    const latest = load("trace_retry_latest");
    const newest = "Newest workflow marker";
    const attempt = latest.selected!.attempts[0];
    attempt.output = { ...attempt.output!, note: newest } as typeof attempt.output;
    const priorId = latest.workflows[1].id;
    const client = {
      trace: vi.fn((_token: string, _case: string, workflowId: string | null) =>
        workflowId === null ? Promise.resolve({ ok: true, status: 200, data: latest }) : new Promise(() => {})),
    } as unknown as SentinelClient;
    const { Probe, commits, control } = harness(client);
    render(<Probe caseId={latest.case_id} token="first-session" canRead />);
    await screen.findByText(newest);
    act(() => control().select(priorId));
    const selected = commits.filter((commit) => commit.workflowId === priorId);
    expect(selected.length).toBeGreaterThan(0);
    expect(selected.filter((commit) => commit.text.includes(newest))).toEqual([]);
    // Same session and case: the workflow list stays, so the choice can change again.
    expect(selected.every((commit) => commit.text.includes("Workflow history"))).toBe(true);
    expect(screen.getByText("Loading the investigation trace.")).toBeInTheDocument();
  });
});

describe("same-context history and selection are kept", () => {
  it("a refresh of an explicit earlier workflow keeps it selected and its list visible", async () => {
    const latest = load("trace_retry_latest");
    const prior = load("trace_retry_prior");
    const priorId = latest.workflows[1].id;
    let hold = false;
    const client = {
      trace: vi.fn((_t: string, _c: string, workflowId: string | null) =>
        hold ? new Promise(() => {}) : Promise.resolve({ ok: true, status: 200, data: workflowId ? prior : latest })),
    } as unknown as SentinelClient;
    const { Probe, commits, control } = harness(client);
    render(<Probe caseId={latest.case_id} token="first-session" canRead />);
    await screen.findByRole("heading", { name: /Newest workflow/ });
    act(() => control().select(priorId));
    await screen.findByRole("heading", { name: /Earlier workflow/ });
    hold = true;
    const before = commits.length;
    act(() => control().retry());
    const refreshing = commits.slice(before);
    expect(refreshing.length).toBeGreaterThan(0);
    expect(refreshing.every((commit) => commit.workflowId === priorId)).toBe(true);
    expect(refreshing.every((commit) => commit.text.includes("Workflow history"))).toBe(true);
    expect((client.trace as ReturnType<typeof vi.fn>).mock.calls.at(-1)?.[2]).toBe(priorId);
  });

  it("a new session or case starts at the newest workflow, not the old selection", async () => {
    const latest = load("trace_retry_latest");
    const priorId = latest.workflows[1].id;
    const client = {
      trace: vi.fn(() => Promise.resolve({ ok: true, status: 200, data: latest })),
    } as unknown as SentinelClient;
    const { Probe, control } = harness(client);
    const view = render(<Probe caseId={latest.case_id} token="first-session" canRead />);
    await screen.findByRole("heading", { name: /Newest workflow/ });
    act(() => control().select(priorId));
    expect(control().workflowId).toBe(priorId);
    view.rerender(<Probe caseId={latest.case_id} token="second-session" canRead />);
    expect(control().workflowId).toBeNull();
    const calls = (client.trace as ReturnType<typeof vi.fn>).mock.calls;
    expect(calls.at(-1)?.slice(0, 3)).toEqual(["second-session", latest.case_id, null]);
  });
});
