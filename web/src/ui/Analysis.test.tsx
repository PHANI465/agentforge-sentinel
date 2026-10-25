import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { App } from "../App";
import { createClient, type SentinelClient } from "../api/client";
import { formatScore, unconfirmedMessage } from "../api/format";
import type { ApiResult, CaseDetail, CasePage, ModelResults, Overview, ScorerInfo, SessionView } from "../api/types";
import { CaseFile } from "./CaseFile";
import { ModelSection, ScorerStrip, useAnalysis } from "./AnalysisPanel";

const here = dirname(fileURLToPath(import.meta.url));
const v11 = resolve(here, "../fixtures/http-v1.1");
const v1 = resolve(here, "../../../contracts/http/examples");
const CANARY = "No claim of real-bank effectiveness, savings or production efficacy.";

function response<T>(name: string, root = v11): T {
  return JSON.parse(readFileSync(resolve(root, name), "utf8")).response as T;
}

const modelScorer = response<ScorerInfo>("scorer_model_mode.json");
const ruleScorer = response<ScorerInfo>("scorer_rule_mode.json");
const report = response<ModelResults>("model_results_p1.json");
const session = response<SessionView>("session.json", v1);
const overview = response<Overview>("overview.json", v1);
const investigated = response<CaseDetail>("investigate.json", v1);
const modelCase = response<CaseDetail>("case_detail_model.json");

function ok<T>(data: T): ApiResult<T> {
  return { ok: true, status: 200, data };
}

function AnalysisHarness({
  client,
  token,
  current = session,
}: {
  client: SentinelClient;
  token: string;
  current?: SessionView;
}) {
  const state = useAnalysis({ client, token, session: current });
  return (
    <>
      <ScorerStrip state={state} />
      <ModelSection state={state} />
    </>
  );
}

describe("model analysis view", () => {
  it("renders the frozen report without inventing a second policy or a probability", async () => {
    const user = userEvent.setup();
    const client = {
      scoring: vi.fn(async () => ok(modelScorer)),
      modelResults: vi.fn(async () => ok(report)),
    } as unknown as SentinelClient;
    render(<AnalysisHarness client={client} token="memory-token" />);
    expect(await screen.findByRole("heading", { name: "offline synthetic benchmark" })).toBeInTheDocument();
    expect(screen.getAllByText("4.0295386895426815e-6").length).toBeGreaterThan(0);
    expect(screen.getByText(CANARY)).toBeInTheDocument();
    expect(screen.getByText(/not a fraud probability/i)).toBeInTheDocument();
    expect(screen.queryByText(/ROC/)).not.toBeInTheDocument();
    expect(client.modelResults).toHaveBeenCalledWith("memory-token", "p1");

    const frozen = screen.getByRole("table", { name: "Frozen online threshold 4.0295386895426815e-6" });
    const daily = screen.getByRole("table", { name: "Offline daily top-15 review" });
    expect(within(frozen).getByText("442")).toBeInTheDocument();
    expect(within(frozen).queryByText("510")).not.toBeInTheDocument();
    expect(within(daily).getByText("510")).toBeInTheDocument();
    expect(within(daily).queryByText("442")).not.toBeInTheDocument();

    const comparison = screen.getByRole("table", { name: "Validation and test average precision" });
    const selected = within(comparison).getByRole("row", { name: /hgb_balanced/ });
    expect(selected).toHaveTextContent("selected");
    expect(selected).toHaveTextContent(formatScore(report.candidates.find((item) => item.name === "hgb_balanced")!.test_average_precision));
    expect(within(comparison).getByRole("row", { name: /rule_r1/ })).toBeInTheDocument();
    expect(within(comparison).getAllByRole("row")).toHaveLength(report.candidates.length + 1);

    const currency = screen.getByRole("table", { name: "Currency slices, kept separate" });
    const scenario = screen.getByRole("table", { name: /Scenario slices/ });
    for (const row of report.slices.filter((item) => item.dimension === "currency")) {
      expect(within(currency).getByRole("row", { name: new RegExp(row.value) })).toBeInTheDocument();
      expect(within(scenario).queryByRole("row", { name: new RegExp(`^${row.value}\\b`) })).not.toBeInTheDocument();
    }
    for (const row of report.slices.filter((item) => item.dimension === "scenario")) {
      expect(within(scenario).getByRole("row", { name: new RegExp(row.value) })).toBeInTheDocument();
      expect(within(currency).queryByText(row.value)).not.toBeInTheDocument();
    }
    expect(within(screen.getByRole("table", { name: "Reliability bins" })).getAllByRole("row")).toHaveLength(
      report.calibration.reliability.length + 1,
    );
    const interval = report.uncertainty.average_precision;
    expect(interval).not.toBeNull();
    expect(
      screen.getByText(
        new RegExp(`${formatScore(interval![0])} to ${formatScore(interval![1])}`),
      ),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/Test precision-recall curve for hgb_balanced, 200 points/)).toBeInTheDocument();

    const points = screen.getByRole("button", { name: "Show precision-recall points" });
    points.focus();
    expect(points).toHaveFocus();
    await user.keyboard("{Enter}");
    const pointTable = screen.getByRole("table", { name: "Test precision-recall points" });
    expect(within(pointTable).getAllByRole("row")).toHaveLength(report.pr_curve.length + 1);
    expect(screen.getByRole("button", { name: "Hide precision-recall points" })).toHaveAttribute("aria-expanded", "true");
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });

  it("keeps a rule configuration from showing the model benchmark", async () => {
    const client = {
      scoring: vi.fn(async () => ok(ruleScorer)),
      modelResults: vi.fn(),
    } as unknown as SentinelClient;
    render(<AnalysisHarness client={client} token="memory-token" />);
    expect(await screen.findByText(/velocity-amount-rules r1 \(rule, heuristic\)/)).toBeInTheDocument();
    expect(screen.getByText("This server has no offline model report for the configured scorer.")).toBeInTheDocument();
    expect(screen.queryByText(CANARY)).not.toBeInTheDocument();
    expect(screen.queryByText("4.0295386895426815e-6")).not.toBeInTheDocument();
    expect(client.modelResults).not.toHaveBeenCalled();
  });

  it("says the analysis view is unavailable when the route is missing and does not substitute the fixture", async () => {
    const client = {
      scoring: vi.fn(async () => ({
        ok: false,
        ambiguous: true,
        status: 404,
        code: null,
        message: "The server did not confirm a result. Reload before trying that step again.",
        details: [],
      })),
      modelResults: vi.fn(),
    } as unknown as SentinelClient;
    render(<AnalysisHarness client={client} token="memory-token" />);
    expect(await screen.findByText("The analysis view is unavailable on this server.")).toBeInTheDocument();
    expect(screen.queryByText(CANARY)).not.toBeInTheDocument();
    expect(screen.queryByText("4.0295386895426815e-6")).not.toBeInTheDocument();
    expect(screen.queryByText("The server did not confirm a result. Reload before trying that step again.")).not.toBeInTheDocument();
    expect(client.modelResults).not.toHaveBeenCalled();
  });

  it("shows permission, authentication, network, and malformed report failures without fixture numbers", async () => {
    const failures: Array<{ name: string; scoring: ApiResult<ScorerInfo>; report?: ApiResult<ModelResults> }> = [
      {
        name: "permission",
        scoring: {
          ok: false,
          ambiguous: false,
          status: 403,
          code: "permission_denied",
          message: "This session does not have permission for that step.",
          details: [],
        },
      },
      {
        name: "authentication",
        scoring: {
          ok: false,
          ambiguous: false,
          status: 401,
          code: "unauthenticated",
          message: "This session token was not accepted.",
          details: [],
        },
      },
      {
        name: "network",
        scoring: {
          ok: false,
          ambiguous: true,
          status: null,
          code: null,
          message: "Sentinel could not be reached.",
          details: [],
        },
      },
    ];
    for (const item of failures) {
      const client = {
        scoring: vi.fn(async () => item.scoring),
        modelResults: vi.fn(),
      } as unknown as SentinelClient;
      const view = render(<AnalysisHarness client={client} token="memory-token" />);
      expect(await screen.findByText(item.scoring.ok ? "" : item.scoring.message)).toBeInTheDocument();
      expect(screen.queryByText(CANARY)).not.toBeInTheDocument();
      view.unmount();
    }
    const malformed = {
      scoring: vi.fn(async () => ok(modelScorer)),
      modelResults: vi.fn(async () => ({
        ok: false as const,
        ambiguous: true,
        status: 200,
        code: null,
        message: "The server did not confirm a result. Reload before trying that step again.",
        details: [],
      })),
    } as unknown as SentinelClient;
    render(<AnalysisHarness client={malformed} token="memory-token" />);
    expect(await screen.findByText(/hgb_balanced p1/)).toBeInTheDocument();
    expect(screen.getByText("The server did not confirm a result. Reload before trying that step again.")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "offline synthetic benchmark" })).not.toBeInTheDocument();
    expect(screen.queryByText(CANARY)).not.toBeInTheDocument();
  });

  it("ignores a late report from the previous session", async () => {
    const scoringQueue: Array<(value: ApiResult<ScorerInfo>) => void> = [];
    const reportQueue: Array<(value: ApiResult<ModelResults>) => void> = [];
    const client = {
      scoring: vi.fn(() => new Promise<ApiResult<ScorerInfo>>((resolve) => scoringQueue.push(resolve))),
      modelResults: vi.fn(() => new Promise<ApiResult<ModelResults>>((resolve) => reportQueue.push(resolve))),
    } as unknown as SentinelClient;
    const nextSession = { ...session, session_id: "later-session" };
    const view = render(<AnalysisHarness client={client} token="old-token" />);
    await waitFor(() => expect(scoringQueue).toHaveLength(1));
    await act(async () => {
      scoringQueue[0](ok(modelScorer));
    });
    await waitFor(() => expect(reportQueue).toHaveLength(1));
    view.rerender(<AnalysisHarness client={client} token="new-token" current={nextSession} />);
    await waitFor(() => expect(scoringQueue).toHaveLength(2));
    await act(async () => {
      reportQueue[0](ok(report));
      scoringQueue[1](ok(ruleScorer));
    });
    expect(await screen.findByText(/velocity-amount-rules r1 \(rule, heuristic\)/)).toBeInTheDocument();
    expect(screen.queryByText(CANARY)).not.toBeInTheDocument();
    expect(screen.queryByText("4.0295386895426815e-6")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "offline synthetic benchmark" })).not.toBeInTheDocument();
  });

  it("drops analysis state on sign-out before a late response arrives", async () => {
    const user = userEvent.setup();
    let release: (value: ApiResult<ScorerInfo>) => void = () => undefined;
    const emptyPage: CasePage = { items: [], next_cursor: null, limit: 25 };
    const client = {
      health: vi.fn(async () => ok({ status: "ok" as const, investigator: "deterministic-investigator" })),
      session: vi.fn(async () => ok(session)),
      overview: vi.fn(async () => ok(overview)),
      listCases: vi.fn(async () => ok(emptyPage)),
      caseDetail: vi.fn(),
      audit: vi.fn(),
      ingest: vi.fn(),
      investigate: vi.fn(),
      decide: vi.fn(),
      execute: vi.fn(),
      scoring: vi.fn(() => new Promise<ApiResult<ScorerInfo>>((resolve) => {
        release = resolve;
      })),
      modelResults: vi.fn(async () => ok(report)),
    } as unknown as SentinelClient;
    render(<App client={client} />);
    await user.type(screen.getByLabelText("Session token"), "memory-token");
    await user.click(screen.getByRole("button", { name: "Connect" }));
    expect(await screen.findByText("Deterministic investigator i1")).toBeInTheDocument();
    expect(screen.getByText("Loading the configured scorer.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Sign out" }));
    await act(async () => {
      release(ok(modelScorer));
    });
    expect(screen.getByRole("button", { name: "Connect" })).toBeInTheDocument();
    expect(screen.queryByText(CANARY)).not.toBeInTheDocument();
    expect(screen.queryByText("4.0295386895426815e-6")).not.toBeInTheDocument();
    expect(screen.queryByText("hgb_balanced p1")).not.toBeInTheDocument();
  });

  it("keeps a stored rule score when the server is configured with the model", () => {
    render(
      <CaseFile
        detail={investigated}
        audit={[]}
        session={session}
        busy={false}
        replayed={false}
        configured={modelScorer}
        onInvestigate={vi.fn()}
        onDecide={vi.fn()}
        onExecute={vi.fn()}
      />,
    );
    expect(screen.getByText("Rule score 1, threshold 0.5, at or above threshold")).toBeInTheDocument();
    expect(screen.getByText(/This record keeps velocity-amount-rules r1/)).toBeInTheDocument();
    expect(screen.getByText(/The configured scorer is hgb_balanced p1 \(model, uncalibrated_score\)/)).toBeInTheDocument();
    expect(screen.queryByText("4.0295386895426815e-6")).not.toBeInTheDocument();
    expect(screen.getByText("Not a probability.")).toBeInTheDocument();
  });

  it("keeps a stored model score, inputs, and threshold when the server is configured with the rule", () => {
    render(
      <CaseFile
        detail={modelCase}
        audit={[]}
        session={session}
        busy={false}
        replayed={false}
        configured={ruleScorer}
        onInvestigate={vi.fn()}
        onDecide={vi.fn()}
        onExecute={vi.fn()}
      />,
    );
    expect(screen.getByText(/Uncalibrated ranking 0.228303811968, threshold 4.0295386895426815e-6/)).toBeInTheDocument();
    expect(screen.getByText("Not a fraud probability.")).toBeInTheDocument();
    expect(screen.getByText(/This record keeps hgb_balanced p1/)).toBeInTheDocument();
    expect(screen.getByText(/The configured scorer is velocity-amount-rules r1 \(rule, heuristic\)/)).toBeInTheDocument();
    expect(screen.getByText("Transaction currency GBP.")).toBeInTheDocument();
    expect(screen.getByText(/Profile home currency USD/)).toBeInTheDocument();
    const inputs = screen.getByRole("table", { name: "Decision-time feature values" });
    expect(within(inputs).getByRole("row", { name: /amount_minor/ })).toHaveTextContent("250000");
    expect(within(inputs).queryByText(/scenario/i)).not.toBeInTheDocument();
    expect(document.querySelector("img")).toBeNull();
  });
});

describe("nullable report statistics", () => {
  function rawReport(): {
    calibration: { reliability: Array<Record<string, unknown>> };
    splits: Record<string, Record<string, unknown>>;
  } {
    return structuredClone(response<typeof report>("model_results_p1.json")) as unknown as {
      calibration: { reliability: Array<Record<string, unknown>> };
      splits: Record<string, Record<string, unknown>>;
    };
  }

  function clientFor(body: unknown) {
    return createClient(async (input) => {
      const path = String(input);
      const payload = path.startsWith("/v1/model-results/") ? body : modelScorer;
      return new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    });
  }

  it("shows null bin statistics and an omitted horizon as not reported", async () => {
    const body = rawReport();
    body.calibration.reliability[0] = { lo: 0, hi: 0.1, n: 0, mean_score: null, fraud_rate: null };
    body.calibration.reliability[1] = { ...body.calibration.reliability[1], fraud_rate: null };
    body.calibration.reliability[2] = { ...body.calibration.reliability[2], mean_score: null };
    delete body.splits.test.labels_observable_by_horizon;
    render(<AnalysisHarness client={clientFor(body)} token="memory-token" />);

    const bins = await screen.findByRole("table", { name: "Reliability bins" });
    const binRows = within(bins).getAllByRole("row");
    const emptyCells = within(binRows[1]).getAllByRole("cell");
    expect(emptyCells[2]).toHaveTextContent("0");
    expect(emptyCells[3]).toHaveTextContent("not reported");
    expect(emptyCells[4]).toHaveTextContent("not reported");
    expect(emptyCells[3]).not.toHaveTextContent("0");
    expect(emptyCells[4]).not.toHaveTextContent("0");

    const partialFraud = within(binRows[2]).getAllByRole("cell");
    expect(partialFraud[3]).toHaveTextContent("0.165465");
    expect(partialFraud[4]).toHaveTextContent("not reported");

    const partialMean = within(binRows[3]).getAllByRole("cell");
    expect(partialMean[0]).toHaveTextContent("0.2");
    expect(partialMean[3]).toHaveTextContent("not reported");
    expect(partialMean[4]).toHaveTextContent("0.5");

    const observedZero = within(bins).getByRole("row", { name: /0\.589552/ });
    expect(within(observedZero).getAllByRole("cell")[4]).toHaveTextContent("0");
    expect(within(observedZero).getAllByRole("cell")[3]).toHaveTextContent("0.589552");

    const counts = screen.getByRole("table", { name: "Train, validation, and test counts" });
    const testRow = within(counts).getByRole("row", { name: /^Test\b/ });
    const horizon = within(testRow).getAllByRole("cell")[4];
    expect(horizon).toHaveTextContent("not reported");
    expect(horizon).not.toHaveTextContent("2219");
    expect(horizon).not.toHaveTextContent("0");
    expect(within(counts).getByRole("row", { name: /^Train\b/ }).textContent).toContain("not reported");
    expect(screen.getByText(CANARY)).toBeInTheDocument();
    expect(screen.getAllByText("4.0295386895426815e-6").length).toBeGreaterThan(0);
  });

  it("does not render a benchmark when a required bin statistic is missing or mistyped", async () => {
    const missing = rawReport();
    delete missing.calibration.reliability[0].mean_score;
    const omitted = render(<AnalysisHarness client={clientFor(missing)} token="memory-token" />);
    expect(await screen.findByText(unconfirmedMessage())).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "offline synthetic benchmark" })).not.toBeInTheDocument();
    expect(screen.queryByText(CANARY)).not.toBeInTheDocument();
    omitted.unmount();

    const mistyped = rawReport();
    mistyped.calibration.reliability[0].fraud_rate = "0";
    delete mistyped.splits.validation.labels_observable_by_horizon;
    mistyped.splits.test.labels_observable_by_horizon = "2219";
    render(<AnalysisHarness client={clientFor(mistyped)} token="memory-token" />);
    expect(await screen.findByText(unconfirmedMessage())).toBeInTheDocument();
    expect(screen.queryByRole("table", { name: "Reliability bins" })).not.toBeInTheDocument();
    expect(screen.queryByText("2219")).not.toBeInTheDocument();
  });
});

describe("session without case reading", () => {
  it("does not request scoring", async () => {
    const client = { scoring: vi.fn(), modelResults: vi.fn() } as unknown as SentinelClient;
    const limited = { ...session, capabilities: [] as SessionView["capabilities"] };
    render(<AnalysisHarness client={client} token="memory-token" current={limited} />);
    expect(await screen.findByText("This session cannot read the configured scorer.")).toBeInTheDocument();
    expect(client.scoring).not.toHaveBeenCalled();
  });
});
