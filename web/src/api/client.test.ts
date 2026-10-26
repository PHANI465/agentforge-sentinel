import { readdirSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { createClient } from "./client";
import { unconfirmedMessage, unreachableMessage } from "./format";
import type { SentinelClient } from "./client";

const examplesDir = resolve(dirname(fileURLToPath(import.meta.url)), "../../../contracts/http/examples");

interface Fixture {
  request: { method: string; path: string; body: Record<string, unknown> | null; authenticated: boolean };
  status: number;
  response: Record<string, unknown> | unknown[];
}

function load(name: string): Fixture {
  return JSON.parse(readFileSync(resolve(examplesDir, name), "utf8")) as Fixture;
}

function respond(fixture: Fixture, contentType = "application/json", raw?: string): Response {
  return new Response(raw ?? JSON.stringify(fixture.response), {
    status: fixture.status,
    headers: { "content-type": contentType },
  });
}

async function call(client: SentinelClient, fixture: Fixture) {
  const path = fixture.request.path;
  const token = "session-token";
  const body = fixture.request.body;
  if (path === "/healthz") return client.health();
  if (path === "/v1/session") return client.session(token);
  if (path === "/v1/overview") return client.overview(token);
  if (path === "/v1/transactions") return client.ingest(token, body as never);
  if (path === "/v1/approvals") {
    return client.decide(token, String(body?.action_intent_id), body?.decision as "approved");
  }
  if (path === "/v1/actions") {
    return client.execute(token, String(body?.approval_id), String(body?.idempotency_key));
  }
  const id = path.split("/")[3] ?? "";
  if (path.endsWith("/audit")) return client.audit(token, id);
  if (path.endsWith("/investigations")) {
    return client.investigate(token, id, Number(body?.expected_revision));
  }
  if (path.startsWith("/v1/cases?")) {
    const query = new URL(path, "http://sentinel.local").searchParams;
    return client.listCases(token, {
      limit: Number(query.get("limit") ?? 25),
      state: (query.get("state") ?? "") as never,
      cursor: query.get("cursor"),
    });
  }
  return client.caseDetail(token, id);
}

describe("accepted HTTP examples", () => {
  const files = readdirSync(examplesDir).filter((name) => name.endsWith(".json")).sort();

  it("covers the 21 frozen examples", () => {
    expect(files).toHaveLength(21);
  });

  it("parses every frozen example and sends the bearer token only as a header", async () => {
    for (const file of files) {
      const fixture = load(file);
      let requested = "";
      let authorization = "";
      const client = createClient(async (url, init) => {
        requested = String(url);
        authorization = new Headers(init?.headers).get("Authorization") ?? "";
        return respond(fixture);
      });
      const result = await call(client, fixture);
      expect(requested.includes("session-token"), file).toBe(false);
      if (fixture.request.path !== "/healthz") expect(authorization, file).toBe("Bearer session-token");
      if (fixture.status >= 400) {
        expect(result.ok, file).toBe(false);
        if (!result.ok) {
          expect(result.ambiguous, file).toBe(false);
          expect(result.code, file).toBe((fixture.response as { error: string }).error);
          expect(result.message, file).not.toContain("never-echoed");
        }
      } else {
        expect(result.ok, file).toBe(true);
      }
    }
  });

  it("passes a cursor back unchanged", async () => {
    const fixture = load("cases_page_2.json");
    let requested = "";
    const client = createClient(async (url) => {
      requested = String(url);
      return respond(fixture);
    });
    const cursor = new URL(fixture.request.path, "http://sentinel.local").searchParams.get("cursor");
    await client.listCases("token", { limit: 1, cursor });
    expect(requested).toContain(`cursor=${encodeURIComponent(cursor ?? "")}`);
  });

  it("treats non-JSON, empty, invalid, and network failures as unconfirmed", async () => {
    const cases: Array<{ name: string; impl: () => Promise<Response> | Response; network?: boolean }> = [
      {
        name: "plain-text 500",
        impl: () => new Response("Internal Server Error", { status: 500, headers: { "content-type": "text/plain" } }),
      },
      {
        name: "empty 502",
        impl: () => new Response("", { status: 502, headers: { "content-type": "text/html" } }),
      },
      {
        name: "invalid json",
        impl: () => new Response("{", { status: 500, headers: { "content-type": "application/json" } }),
      },
      { name: "network", impl: () => Promise.reject(new TypeError("offline")), network: true },
    ];
    for (const item of cases) {
      const client = createClient(async () => item.impl());
      const result = await client.execute("token", "approval", "key-kept");
      expect(result.ok, item.name).toBe(false);
      if (!result.ok) {
        expect(result.ambiguous, item.name).toBe(true);
        expect(result.message, item.name).toBe(item.network ? unreachableMessage() : unconfirmedMessage());
        expect(result.message, item.name).not.toContain("Internal Server Error");
      }
    }
  });
});
