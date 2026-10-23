import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { AuditEvent, CaseDetail, SessionView } from "../api/types";
import { CaseFile } from "./CaseFile";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../../../contracts/http/examples");

function fixture<T>(name: string): T {
  return JSON.parse(readFileSync(resolve(root, name), "utf8")).response as T;
}

const session = fixture<SessionView>("session.json");
const investigated = fixture<CaseDetail>("investigate.json");
const reopened = fixture<CaseDetail>("case_detail_reopened.json");
const audit = fixture<AuditEvent[]>("audit.json");

function renderCase(detail: CaseDetail, nextSession = session, nextAudit = audit) {
  cleanup();
  const onInvestigate = vi.fn();
  const onDecide = vi.fn();
  const onExecute = vi.fn();
  render(
    <CaseFile
      detail={detail}
      audit={nextAudit}
      session={nextSession}
      busy={false}
      replayed={false}
      onInvestigate={onInvestigate}
      onDecide={onDecide}
      onExecute={onExecute}
    />,
  );
  return { onInvestigate, onDecide, onExecute };
}

describe("case file", () => {
  it("renders the frozen investigation fixture as text", () => {
    renderCase(investigated);
    expect(screen.getByText("2500.00 USD")).toBeInTheDocument();
    expect(screen.getByText("Rule score 1, threshold 0.5, at or above threshold")).toBeInTheDocument();
    expect(screen.getByText(/velocity-amount-rules r1/)).toBeInTheDocument();
    expect(screen.getByText("Large amount with 3 prior transactions in the last hour.")).toBeInTheDocument();
    expect(screen.getByText("Transactions in the prior hour: 3")).toBeInTheDocument();
    expect(screen.getByText(/Simulated hold of 2500.00 USD/)).toBeInTheDocument();
    expect(screen.getByText(/simulated-action-policy p1/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reject" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Execute/ })).not.toBeInTheDocument();
    expect(screen.getByText(/Transaction received/)).toBeInTheDocument();
  });

  it("renders model rationale as inert text", () => {
    const hostile = structuredClone(investigated);
    hostile.agent_runs[0].finding = {
      operation: "simulated_hold",
      reason_code: "velocity_pattern",
      rationale: '<img src=x onerror=alert(1)>',
    };
    renderCase(hostile);
    expect(screen.getByText('<img src=x onerror=alert(1)>')).toBeInTheDocument();
    expect(document.querySelector("img")).toBeNull();
  });

  it("hides decisions the session cannot perform", () => {
    const limited: SessionView = { ...session, capabilities: ["read_case"] };
    renderCase(investigated, limited);
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
    expect(screen.getByText("This session cannot approve or reject actions.")).toBeInTheDocument();
  });

  it("offers investigate on a reopened case and does not revive the old approval", () => {
    const expired: AuditEvent[] = [
      { ...audit[0], event_type: "approval_expired", id: "expired-event" },
    ];
    const { onInvestigate, onExecute } = renderCase(reopened, session, expired);
    expect(screen.getByText("1200.00 USD")).toBeInTheDocument();
    expect(screen.getByText("No action is proposed for revision 4.")).toBeInTheDocument();
    expect(screen.getByText(/earlier approval expired/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Execute/ })).not.toBeInTheDocument();
    expect(onExecute).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Investigate case" })).toBeInTheDocument();
    void onInvestigate;
  });

  it("shows a provider failure without a rationale", async () => {
    const failed = structuredClone(investigated);
    failed.case = { ...failed.case, state: "open", revision: 4 };
    failed.action_intents = [];
    failed.agent_runs = [
      {
        run: {
          ...failed.agent_runs[0].run,
          status: "failed",
          failure_code: "provider_unavailable",
        },
        finding: null,
      },
    ];
    const user = userEvent.setup();
    const { onInvestigate } = renderCase(failed, session, []);
    expect(screen.getByText(/investigator was unavailable/i)).toBeInTheDocument();
    expect(screen.queryByText(/Large amount/)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Investigate case" }));
    expect(onInvestigate).toHaveBeenCalledOnce();
  });
});
