import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { acceptModelResults } from "./analysis";
import { createClient } from "./client";
import { unconfirmedMessage } from "./format";

const examples = resolve(dirname(fileURLToPath(import.meta.url)), "../fixtures/http-v1.1");
const FROZEN_HASH = "41e069f13fb168923e299cc0e17754bf5a3f629d5fc0d3bda662172dd1583d50";

interface Report {
  calibration: { reliability: Array<Record<string, unknown>> };
  splits: Record<string, Record<string, unknown>>;
  frozen_threshold: number;
}

function frozenReport(): Report {
  const raw = JSON.parse(readFileSync(resolve(examples, "model_results_p1.json"), "utf8")) as { response: Report };
  return structuredClone(raw.response);
}

function scorerBody(): unknown {
  return (JSON.parse(readFileSync(resolve(examples, "scorer_model_mode.json"), "utf8")) as { response: unknown }).response;
}

function nullableReport(): Report {
  const report = frozenReport();
  const bins = report.calibration.reliability;
  bins[0] = { lo: 0, hi: 0.1, n: 0, mean_score: null, fraud_rate: null };
  bins[1] = { ...bins[1], fraud_rate: null };
  bins[2] = { ...bins[2], mean_score: null };
  delete report.splits.test.labels_observable_by_horizon;
  return report;
}

describe("nullable model statistics", () => {
  it("leaves the frozen p1 fixture bytes unchanged", () => {
    const bytes = readFileSync(resolve(examples, "model_results_p1.json"));
    expect(createHash("sha256").update(bytes).digest("hex")).toBe(FROZEN_HASH);
    expect(bytes.toString("utf8")).toContain("4.0295386895426815e-06");
  });

  it("accepts an empty bin with null statistics and an omitted horizon", () => {
    const report = nullableReport();
    const parsed = acceptModelResults(report);
    expect(parsed).not.toBeNull();
    expect(parsed?.calibration.reliability[0]).toMatchObject({ n: 0, mean_score: null, fraud_rate: null });
    expect(parsed?.calibration.reliability[0].mean_score).not.toBe(0);
    expect(parsed?.calibration.reliability[0].fraud_rate).not.toBe(0);
    expect(parsed?.calibration.reliability[1]).toMatchObject({ mean_score: 0.165465, fraud_rate: null });
    expect(parsed?.calibration.reliability[2]).toMatchObject({ mean_score: null, fraud_rate: 0.5 });
    const observedZero = parsed?.calibration.reliability.find((bin) => bin.mean_score === 0.589552);
    expect(observedZero).toMatchObject({ n: 3, fraud_rate: 0 });
    expect(parsed?.splits.test.labels_observable_by_horizon).toBeNull();
    expect(parsed?.splits.train.labels_observable_by_horizon).toBeNull();
    expect(parsed?.frozen_threshold).toBe(4.0295386895426815e-06);
  });

  it("keeps an explicit zero horizon distinct from an omitted one", () => {
    const report = frozenReport();
    report.splits.validation.labels_observable_by_horizon = 0;
    delete report.splits.train.labels_observable_by_horizon;
    const parsed = acceptModelResults(report);
    expect(parsed?.splits.validation.labels_observable_by_horizon).toBe(0);
    expect(parsed?.splits.train.labels_observable_by_horizon).toBeNull();
  });

  it("rejects wrong statistic types and omitted required bin or split fields", () => {
    const cases: Array<{ name: string; edit: (report: Report) => void }> = [
      { name: "mean omitted", edit: (report) => delete report.calibration.reliability[0].mean_score },
      { name: "fraud rate omitted", edit: (report) => delete report.calibration.reliability[0].fraud_rate },
      { name: "count omitted", edit: (report) => delete report.calibration.reliability[0].n },
      { name: "lower edge omitted", edit: (report) => delete report.calibration.reliability[0].lo },
      { name: "upper edge omitted", edit: (report) => delete report.calibration.reliability[0].hi },
      { name: "mean string", edit: (report) => { report.calibration.reliability[0].mean_score = "0"; } },
      { name: "fraud string", edit: (report) => { report.calibration.reliability[0].fraud_rate = "0"; } },
      { name: "mean boolean", edit: (report) => { report.calibration.reliability[0].mean_score = true; } },
      { name: "fraud boolean", edit: (report) => { report.calibration.reliability[0].fraud_rate = false; } },
      { name: "mean nan", edit: (report) => { report.calibration.reliability[0].mean_score = Number.NaN; } },
      { name: "fraud infinity", edit: (report) => { report.calibration.reliability[0].fraud_rate = Number.POSITIVE_INFINITY; } },
      { name: "mean object", edit: (report) => { report.calibration.reliability[0].mean_score = {}; } },
      { name: "horizon string", edit: (report) => { report.splits.test.labels_observable_by_horizon = "2219"; } },
      { name: "horizon fraction", edit: (report) => { report.splits.test.labels_observable_by_horizon = 2219.5; } },
      { name: "horizon boolean", edit: (report) => { report.splits.test.labels_observable_by_horizon = true; } },
      { name: "horizon negative", edit: (report) => { report.splits.test.labels_observable_by_horizon = -1; } },
      { name: "rows omitted", edit: (report) => delete report.splits.train.rows },
    ];
    for (const item of cases) {
      const report = frozenReport();
      item.edit(report);
      expect(acceptModelResults(report), item.name).toBeNull();
    }
  });

  it("parses the nullable report through the client and rejects a missing mean", async () => {
    const valid = nullableReport();
    const client = createClient(async (input) => {
      const path = String(input);
      const body = path.endsWith("/p1") ? valid : scorerBody();
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    });
    const parsed = await client.modelResults("session-token", "p1");
    expect(parsed.ok).toBe(true);
    if (parsed.ok) {
      expect(parsed.data.calibration.reliability[0].mean_score).toBeNull();
      expect(parsed.data.calibration.reliability[0].fraud_rate).toBeNull();
      expect(parsed.data.splits.test.labels_observable_by_horizon).toBeNull();
    }

    const missingMean = frozenReport();
    delete missingMean.calibration.reliability[0].mean_score;
    const rejected = createClient(async () => new Response(JSON.stringify(missingMean), {
      status: 200,
      headers: { "content-type": "application/json" },
    }));
    const result = await rejected.modelResults("session-token", "p1");
    expect(result).toMatchObject({ ok: false, ambiguous: true, status: 200, message: unconfirmedMessage() });
  });
});
