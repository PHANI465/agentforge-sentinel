import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { createClient } from "./client";
import { formatScore } from "./format";
import type { ModelResults, ScorerInfo } from "./types";

const examples = resolve(dirname(fileURLToPath(import.meta.url)), "../fixtures/http-v1.1");

function load(name: string): { request: { path: string }; status: number; response: unknown } {
  return JSON.parse(readFileSync(resolve(examples, name), "utf8")) as {
    request: { path: string };
    status: number;
    response: unknown;
  };
}

describe("accepted v1.1 fixtures", () => {
  it("keeps the frozen threshold literal and the recorded file hash", () => {
    const raw = readFileSync(resolve(examples, "model_results_p1.json"), "utf8");
    expect(raw).toContain("4.0295386895426815e-06");
    expect(createHash("sha256").update(readFileSync(resolve(examples, "model_results_p1.json"))).digest("hex")).toBe(
      "41e069f13fb168923e299cc0e17754bf5a3f629d5fc0d3bda662172dd1583d50",
    );
    expect(readFileSync(resolve(examples, "PROVENANCE.md"), "utf8")).toContain(
      "1f220a5628e3e261776c286c56b502b8d989184bd928bf219f30ebb6e451fd90",
    );
  });

  it("parses both configured scorers and the p1 report without adding a request id", async () => {
    for (const name of ["scorer_rule_mode.json", "scorer_model_mode.json", "model_results_p1.json"]) {
      const fixture = load(name);
      let url = "";
      let requestId: string | null = "present";
      const client = createClient(async (input, init) => {
        url = String(input);
        requestId = new Headers(init?.headers).get("X-Request-ID");
        return new Response(JSON.stringify(fixture.response), {
          status: fixture.status,
          headers: { "content-type": "application/json" },
        });
      });
      const result =
        name === "model_results_p1.json" ? await client.modelResults("session-token", "p1") : await client.scoring("session-token");
      expect(result.ok, name).toBe(true);
      expect(url, name).toBe(name === "model_results_p1.json" ? "/v1/model-results/p1" : "/v1/scoring");
      expect(url, name).not.toContain("session-token");
      expect(requestId, name).toBeNull();
    }
    const model = load("scorer_model_mode.json").response as ScorerInfo;
    const report = load("model_results_p1.json").response as ModelResults;
    expect(formatScore(model.threshold)).toBe("4.0295386895426815e-6");
    expect(formatScore(report.frozen_threshold)).toBe("4.0295386895426815e-6");
  });

  it("keeps model-result and profile errors definite and non-JSON scoring unconfirmed", async () => {
    const denied = load("error_model_results_permission.json");
    const missing = load("error_model_results_not_found.json");
    const profile = load("error_account_profile_missing.json");
    const client = createClient(async (input) => {
      const path = String(input);
      const fixture = path.endsWith("/p2") ? missing : path.endsWith("/p1") ? denied : profile;
      return new Response(JSON.stringify(fixture.response), {
        status: fixture.status,
        headers: { "content-type": "application/json" },
      });
    });
    const permission = await client.modelResults("session-token", "p1");
    const absent = await client.modelResults("session-token", "p2");
    const ingestBody = JSON.parse(readFileSync(resolve(examples, "error_account_profile_missing.json"), "utf8")).request
      .body as { external_id: string };
    const ingest = await client.ingest("session-token", ingestBody as never);
    expect(permission).toMatchObject({ ok: false, status: 403, code: "permission_denied", ambiguous: false });
    expect(absent).toMatchObject({ ok: false, status: 404, code: "not_found", ambiguous: false });
    expect(ingest).toMatchObject({ ok: false, status: 422, code: "account_profile_missing", ambiguous: false });
    if (!ingest.ok) expect(ingest.message).toContain("no profile");

    const stale = createClient(async () => new Response("nope", { status: 404, headers: { "content-type": "text/plain" } }));
    const unavailable = await stale.scoring("session-token");
    expect(unavailable).toMatchObject({ ok: false, ambiguous: true, status: 404 });

    const foreign = createClient(
      async () =>
        new Response(JSON.stringify({ detail: "Not Found" }), {
          status: 404,
          headers: { "content-type": "application/json" },
        }),
    );
    const routed = await foreign.scoring("session-token");
    expect(routed).toMatchObject({ ok: false, ambiguous: true, status: 404, code: null });
    if (!routed.ok) expect(routed.message).not.toContain("Not Found");
  });
});
