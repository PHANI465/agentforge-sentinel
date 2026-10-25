import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { expect, test, type Locator, type Page } from "@playwright/test";
import { formatCount, formatScore } from "../src/api/format";
import { api, connect, credentialRecoverable } from "./support/session";
import {
  inspectCase,
  inspectPresence,
  inspectScoring,
  postActionDirect,
  readManifest,
  restart,
  restartApi,
  scenario,
  seed,
  stackStatus,
  tokenFor,
  type StoredScoring,
} from "./support/stack";
import { failureProbeMarker, readRuntime, runtimeDir } from "./support/runtime";

test.describe.configure({ mode: "serial" });

function caseFile(page: Page): Locator {
  return page.locator("article.case");
}

function minutesAgo(minutes: number): string {
  return new Date(Date.now() - minutes * 60_000).toISOString().replace(/\.\d{3}Z$/, "Z");
}

function queueName(externalId: string): RegExp {
  const escaped = externalId.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`(?:^|\\s)${escaped}(?:\\s|$)`);
}

async function openQueued(page: Page, externalId: string): Promise<Locator> {
  await page.getByRole("button", { name: queueName(externalId) }).click();
  const file = caseFile(page);
  await expect(file).toContainText(`Synthetic transaction ${externalId}`);
  return file;
}

async function record(page: Page, input: { externalId: string; accountId: string; minor: string; occurredAt: string }, expected: string): Promise<void> {
  await page.getByLabel("External id").fill(input.externalId);
  await page.getByLabel("Account id").fill(input.accountId);
  await page.getByLabel("Amount in minor units").fill(input.minor);
  await page.getByLabel("Occurred at").fill(input.occurredAt);
  await page.getByRole("button", { name: "Record transaction" }).click();
  await expect(page.locator("form.ingest .status")).toContainText(expected);
}

function requireId(value: string | undefined, label: string): string {
  if (!value) throw new Error(`${label} missing`);
  return value;
}

test("ingests, investigates, approves, and executes an escalation", async ({ page, browser }) => {
  writeFileSync(path.join(runtimeDir, "browser.txt"), `${browser.browserType().name()} ${browser.version()}\n`);
  await connect(page, "analyst");
  await expect(page.getByText("deterministic-fixture-investigator x1")).toBeVisible();
  const externalId = "u02-escalate-1";
  await record(page, {
    externalId,
    accountId: crypto.randomUUID(),
    minor: "250000",
    occurredAt: minutesAgo(5),
  }, "A case was opened.");
  const file = caseFile(page);
  await expect(file).toContainText(`Synthetic transaction ${externalId}`);
  await expect(file).toContainText("2500.00 USD");
  await page.getByRole("button", { name: "Investigate case", exact: true }).click();
  await expect(file.getByRole("heading", { name: "Awaiting approval" })).toBeVisible();
  await expect(file).toContainText("Revision 3");
  const text = await file.innerText();
  const rendered = text.match(/Escalate transaction ([0-9a-f-]{36}), reason unusual_amount/);
  expect(rendered).not.toBeNull();
  const proposed = inspectCase({ externalId });
  expect(proposed.proposals.at(-1)).toMatchObject({
    operation: "escalate",
    reason_code: "unusual_amount",
    transaction_id: rendered?.[1],
    amount_minor: null,
  });
  expect(text).not.toContain("Simulated hold");
  expect(text).not.toContain("Amount unavailable");
  await page.getByRole("button", { name: "Approve", exact: true }).click();
  await expect(page.getByRole("button", { name: "Execute escalate", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Execute escalate", exact: true }).click();
  await expect(file.getByRole("heading", { name: "Closed" })).toBeVisible();
  await expect(file).toContainText("No action is proposed for revision 4.");
  await expect(file).toContainText(
    `Revision 3: Escalate transaction ${rendered?.[1]}, reason unusual_amount, approved, executed`,
  );
  await expect(file).toContainText("Action succeeded");
  const closed = inspectCase({ externalId });
  expect(closed.case_state).toBe("closed");
  expect(closed.case_revision).toBe(4);
  expect(closed.action_count).toBe(1);
  expect(closed.consumed_approval_count).toBe(1);
  expect(closed.audit_counts.action_succeeded).toBe(1);
});

test("ingests a velocity history and executes the server-built hold", async ({ page }) => {
  await connect(page, "analyst");
  const accountId = crypto.randomUUID();
  await record(page, { externalId: "u02-hold-a", accountId, minor: "1500", occurredAt: minutesAgo(40) }, "No case was opened.");
  await record(page, { externalId: "u02-hold-b", accountId, minor: "1500", occurredAt: minutesAgo(30) }, "No case was opened.");
  await record(page, { externalId: "u02-hold-large", accountId, minor: "250000", occurredAt: minutesAgo(10) }, "A case was opened.");
  const file = caseFile(page);
  await expect(file).toContainText("Synthetic transaction u02-hold-large");
  await expect(file).toContainText("Transactions in the prior hour: 2");
  await page.getByRole("button", { name: "Investigate case", exact: true }).click();
  await expect(file.getByRole("heading", { name: "Awaiting approval" })).toBeVisible();
  const text = await file.innerText();
  const rendered = text.match(/Simulated hold of 2500\.00 USD on transaction ([0-9a-f-]{36})/);
  expect(rendered).not.toBeNull();
  const proposed = inspectCase({ externalId: "u02-hold-large" });
  expect(proposed.proposals.at(-1)).toMatchObject({
    operation: "simulated_hold",
    transaction_id: rendered?.[1],
    amount_minor: 250000,
    reason_code: null,
  });
  expect(text).not.toContain("Escalate transaction");
  await page.getByRole("button", { name: "Approve", exact: true }).click();
  await expect(page.getByRole("button", { name: "Execute simulated hold", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Execute simulated hold", exact: true }).click();
  await expect(file.getByRole("heading", { name: "Closed" })).toBeVisible();
  await expect(file).toContainText(
    `Revision 3: Simulated hold of 2500.00 USD on transaction ${rendered?.[1]}, approved, executed`,
  );
  const closed = inspectCase({ externalId: "u02-hold-large" });
  expect(closed.action_count).toBe(1);
  expect(closed.case_state).toBe("closed");
  expect(closed.audit_counts.action_succeeded).toBe(1);
});

test("rejects a proposal without persisting a simulated action", async ({ page }) => {
  const seeded = seed("awaiting_approval", 1);
  await connect(page, "analyst");
  const file = await openQueued(page, "c02-awaiting_approval-1");
  await page.getByRole("button", { name: "Reject", exact: true }).click();
  await expect(file.getByRole("heading", { name: "Closed" })).toBeVisible();
  await expect(file).toContainText("Revision 4");
  await expect(file).toContainText("No action is proposed for revision 4.");
  await expect(file).toContainText("reason unusual_amount, rejected");
  await expect(file).not.toContainText(", executed");
  await expect(file).not.toContainText("was recorded");
  const stored = inspectCase({ caseId: seeded.case_id });
  expect(stored.case_state).toBe("closed");
  expect(stored.case_revision).toBe(4);
  expect(stored.action_count).toBe(0);
  expect(stored.audit_counts.approval_recorded).toBe(1);
  expect(stored.audit_counts.action_succeeded ?? 0).toBe(0);
});

test("reopens an expired approval and keeps the historical expiry after recovery", async ({ page }) => {
  const seeded = seed("approval_expired", 1);
  const oldApproval = requireId(seeded.approval_id, "approval");
  await connect(page, "analyst");
  const file = await openQueued(page, "c02-approval_expired-1");
  await page.getByRole("button", { name: "Execute escalate", exact: true }).click();
  await expect(page.getByText("The approval is outside its validity window. The case was reloaded.")).toBeVisible();
  await expect(file.getByRole("heading", { name: "Open" })).toBeVisible();
  await expect(file).toContainText("Revision 4");
  await expect(file).toContainText("An earlier approval expired. Investigate this revision before making a new decision.");
  await expect(file).toContainText("Approval expired");
  await page.getByRole("button", { name: "Investigate case", exact: true }).click();
  await expect(file.getByRole("heading", { name: "Awaiting approval" })).toBeVisible();
  await expect(file).not.toContainText("Investigate this revision before making a new decision.");
  await expect(file).toContainText("Approval expired");
  await page.getByRole("button", { name: "Approve", exact: true }).click();
  await page.getByRole("button", { name: "Execute escalate", exact: true }).click();
  await expect(file.getByRole("heading", { name: "Closed" })).toBeVisible();
  await expect(file).not.toContainText("Investigate this revision before making a new decision.");
  await expect(file).toContainText("Approval expired");
  await expect(file).toContainText(", executed");
  await expect(file).toContainText("Action succeeded");
  const old = await api(page, "POST", "/v1/actions", { approval_id: oldApproval, idempotency_key: crypto.randomUUID() });
  expect(old.status).toBe(409);
  expect(old.code).toBe("approval_outside_validity");
  const stored = inspectCase({ caseId: seeded.case_id });
  expect(stored.action_count).toBe(1);
  expect(stored.case_state).toBe("closed");
  expect(stored.audit_counts.approval_expired).toBe(1);
  expect(stored.audit_counts.action_succeeded).toBe(1);
});

test("keeps the later selected case when the earlier detail arrives last", async ({ page }) => {
  await connect(page, "analyst");
  const openId = scenario("open_case").case_id;
  const staleId = scenario("stale_revision").case_id;
  const held: Array<{ id: string; release: () => void }> = [];
  await page.route(/\/v1\/cases\/[0-9a-f-]{36}$/i, async (route) => {
    if (route.request().method() !== "GET") {
      await route.continue();
      return;
    }
    const id = new URL(route.request().url()).pathname.split("/").pop() ?? "";
    await new Promise<void>((resolve) => held.push({ id, release: resolve }));
    await route.continue();
  });
  await page.getByRole("button", { name: queueName("c02-open_case") }).click();
  await expect.poll(() => held.some((item) => item.id === openId)).toBe(true);
  await page.getByRole("button", { name: queueName("c02-stale_revision") }).click();
  await expect.poll(() => held.some((item) => item.id === staleId)).toBe(true);
  held.find((item) => item.id === staleId)?.release();
  await expect(caseFile(page)).toContainText("Synthetic transaction c02-stale_revision");
  const late = page.waitForResponse((response) => response.url().includes(openId) && response.request().method() === "GET");
  held.find((item) => item.id === openId)?.release();
  await late;
  await expect(caseFile(page)).toContainText("Synthetic transaction c02-stale_revision");
  await expect(caseFile(page)).not.toContainText("Synthetic transaction c02-open_case");
});

test("refetches after a stale revision and keeps the closed filter across a delayed refresh", async ({ page }) => {
  await connect(page, "analyst");
  const seeded = scenario("stale_revision");
  const file = await openQueued(page, "c02-stale_revision");
  await expect(file).toContainText("Revision 1");
  const outOfBand = await api(page, "POST", `/v1/cases/${seeded.case_id}/investigations`, { expected_revision: 1 });
  expect(outOfBand.status).toBe(200);
  expect(outOfBand.revision).toBe(3);
  await expect(file).toContainText("Revision 1");
  await page.getByRole("button", { name: "Investigate case", exact: true }).click();
  await expect(page.getByText("The case changed. The latest server state is shown.")).toBeVisible();
  await expect(file.getByRole("heading", { name: "Awaiting approval" })).toBeVisible();
  await expect(file).toContainText("Revision 3");
  await expect(file).toContainText(`Escalate transaction ${seeded.transaction_id}, reason unusual_amount`);

  await expect(page.getByRole("button", { name: queueName("c02-open_case") })).toBeVisible();
  await expect(page.getByRole("button", { name: queueName("c02-rejected") })).toBeVisible();
  let releaseOverview: (() => void) | undefined;
  const overviewHeld = new Promise<void>((resolve) => {
    releaseOverview = resolve;
  });
  let overviews = 0;
  const lists: string[] = [];
  await page.route("**/v1/overview", async (route) => {
    overviews += 1;
    await overviewHeld;
    await route.continue();
  });
  await page.route("**/v1/cases?*", async (route) => {
    lists.push(new URL(route.request().url()).search);
    await route.continue();
  });
  await openQueued(page, "c02-awaiting_approval");
  await page.getByRole("button", { name: "Approve", exact: true }).click();
  await expect.poll(() => overviews).toBe(1);
  await page.getByLabel("Case state").selectOption("closed");
  await expect(page.getByRole("button", { name: queueName("c02-rejected") })).toBeVisible();
  await expect(page.getByRole("button", { name: queueName("c02-open_case") })).toHaveCount(0);
  const before = lists.length;
  releaseOverview?.();
  await expect.poll(() => lists.length).toBeGreaterThan(before);
  await expect(page.getByText("Loading cases.")).toHaveCount(0);
  await expect(page.getByLabel("Case state")).toHaveValue("closed");
  await expect(page.getByRole("button", { name: queueName("c02-open_case") })).toHaveCount(0);
  await expect(page.getByRole("button", { name: queueName("c02-rejected") })).toBeVisible();
  await expect(caseFile(page)).toContainText("Synthetic transaction c02-awaiting_approval");
  expect(lists.slice(before).every((query) => query.includes("state=closed"))).toBe(true);
});

test("shows a provider failure and recovers a seeded failed run without a model call", async ({ page }) => {
  await connect(page, "analyst");
  const failure = await openQueued(page, "c02-provider_failure");
  await expect(failure).toContainText("7777.77 USD");
  await page.getByRole("button", { name: "Investigate case", exact: true }).click();
  await expect(failure).toContainText("The investigator was unavailable. No model result was recorded.");
  await expect(failure).toContainText("No action is proposed for revision 3.");
  await expect(failure.getByRole("heading", { name: "Open" })).toBeVisible();
  await page.getByRole("button", { name: "Investigate case", exact: true }).click();
  await expect(failure).toContainText("No action is proposed for revision 5.");
  const failed = inspectCase({ caseId: scenario("provider_failure").case_id });
  expect(failed.failed_run_count).toBeGreaterThanOrEqual(2);
  expect(failed.failure_codes.every((code) => code === "provider_unavailable")).toBe(true);
  expect(failed.action_count).toBe(0);
  expect(failed.intent_count).toBe(0);

  const reopened = await openQueued(page, "c02-failed_run_reopened");
  await expect(reopened).toContainText("The investigator was unavailable. No model result was recorded.");
  await page.getByRole("button", { name: "Investigate case", exact: true }).click();
  await expect(reopened.getByRole("heading", { name: "Awaiting approval" })).toBeVisible();
  await expect(reopened).toContainText("Revision 5");
  await expect(reopened).toContainText("The investigator was unavailable. No model result was recorded.");
  await expect(reopened).toContainText("Escalate transaction");
  const recovered = inspectCase({ caseId: scenario("failed_run_reopened").case_id });
  expect(recovered.failed_run_count).toBe(1);
  expect(recovered.run_count).toBeGreaterThanOrEqual(2);
  expect(recovered.intent_count).toBe(1);
  expect(recovered.action_count).toBe(0);
});

test("retries a dropped execution and keeps one database action", async ({ page }) => {
  const seeded = seed("approved", 1);
  await connect(page, "analyst");
  const file = await openQueued(page, "c02-approved-1");
  let dropped = false;
  let blockDetail = false;
  let actionId: string | null = null;
  await page.route("**/v1/actions", async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    if (!dropped) {
      dropped = true;
      blockDetail = true;
      const response = await route.fetch();
      await response.body();
      await route.fulfill({ status: 500, contentType: "text/plain", body: "" });
      return;
    }
    const response = await route.fetch();
    const payload = (await response.json()) as { action?: { id?: unknown } };
    actionId = typeof payload.action?.id === "string" ? payload.action.id : null;
    await route.fulfill({ status: response.status(), contentType: "application/json", body: JSON.stringify(payload) });
  });
  await page.route(/\/v1\/cases\/[0-9a-f-]{36}$/i, async (route) => {
    if (blockDetail && route.request().method() === "GET") {
      blockDetail = false;
      await route.fulfill({ status: 500, contentType: "text/plain", body: "" });
      return;
    }
    await route.continue();
  });
  await page.getByRole("button", { name: "Execute escalate", exact: true }).click();
  await expect(page.getByText("The server did not confirm a result.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Execute escalate", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "Execute escalate", exact: true }).click();
  await expect(file).toContainText("This execution was already recorded. No second action was created.");
  await expect(file.getByRole("heading", { name: "Closed" })).toBeVisible();
  const stored = inspectCase({ caseId: seeded.case_id });
  expect(actionId).toBeTruthy();
  expect(stored.action_count).toBe(1);
  expect(stored.action_ids).toEqual([actionId]);
});

test("returns one action when the same execution is in flight twice", async ({ page }) => {
  const seeded = seed("approved", 2);
  await connect(page, "analyst");
  const file = await openQueued(page, "c02-approved-2");
  const seen: Array<{ id: string | null; replayed: boolean | null }> = [];
  await page.route("**/v1/actions", async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    const body = route.request().postData() ?? "";
    const primary = route.fetch();
    const concurrent = postActionDirect(body);
    const [response, other] = await Promise.all([primary, concurrent]);
    const payload = (await response.json()) as { action?: { id?: unknown }; replayed?: unknown };
    seen.push(
      {
        id: typeof payload.action?.id === "string" ? payload.action.id : null,
        replayed: typeof payload.replayed === "boolean" ? payload.replayed : null,
      },
      { id: other.actionId, replayed: other.replayed },
    );
    await route.fulfill({ status: response.status(), contentType: "application/json", body: JSON.stringify(payload) });
  });
  await page.getByRole("button", { name: "Execute escalate", exact: true }).click();
  await expect(file.getByRole("heading", { name: "Closed" })).toBeVisible();
  expect(seen).toHaveLength(2);
  expect(new Set(seen.map((item) => item.id)).size).toBe(1);
  expect(seen.filter((item) => item.replayed === false)).toHaveLength(1);
  expect(seen.filter((item) => item.replayed === true)).toHaveLength(1);
  const stored = inspectCase({ caseId: seeded.case_id });
  expect(stored.action_count).toBe(1);
  expect(stored.action_ids).toEqual([seen[0]?.id]);
});

test("a second activation does not start a second execution", async ({ page }) => {
  const seeded = seed("approved", 3);
  await connect(page, "analyst");
  const file = await openQueued(page, "c02-approved-3");
  let posts = 0;
  let release: (() => void) | undefined;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/v1/actions", async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    posts += 1;
    await gate;
    await route.continue();
  });
  try {
    await page.evaluate(() => {
      const button = [...document.querySelectorAll("button")].find((item) => item.textContent?.includes("Execute escalate"));
      if (!(button instanceof HTMLButtonElement)) throw new Error("execute control missing");
      button.click();
      button.click();
    });
    await expect.poll(() => posts).toBe(1);
  } finally {
    release?.();
  }
  await expect(file.getByRole("heading", { name: "Closed" })).toBeVisible();
  const stored = inspectCase({ caseId: seeded.case_id });
  expect(stored.action_count).toBe(1);
});

test("hides a foreign case and enforces read-only and second-actor limits", async ({ page }) => {
  const pending = seed("awaiting_approval", 2);
  const limited = seed("limited_capabilities", 1);
  await connect(page, "analyst");
  await expect(page.getByRole("button", { name: queueName("c02-foreign_session_case") })).toHaveCount(0);
  const foreign = scenario("foreign_session_case");
  const detail = await api(page, "GET", `/v1/cases/${foreign.case_id}`);
  const audit = await api(page, "GET", `/v1/cases/${foreign.case_id}/audit`);
  const investigate = await api(page, "POST", `/v1/cases/${foreign.case_id}/investigations`, { expected_revision: 1 });
  expect(detail).toMatchObject({ status: 404, code: "not_found" });
  expect(audit).toMatchObject({ status: 404, code: "not_found" });
  expect(investigate).toMatchObject({ status: 404, code: "not_found" });

  const reader = await page.context().newPage();
  await connect(reader, "read_only");
  await expect(reader.getByText("This session cannot record transactions.")).toBeVisible();
  const pendingFile = await openQueued(reader, "c02-awaiting_approval-2");
  await expect(pendingFile).toContainText("This session cannot approve or reject actions.");
  await expect(reader.getByRole("button", { name: "Approve", exact: true })).toHaveCount(0);
  const deniedApproval = await api(reader, "POST", "/v1/approvals", {
    action_intent_id: requireId(pending.intent_id, "intent"),
    decision: "approved",
  });
  expect(deniedApproval).toMatchObject({ status: 403, code: "permission_denied" });
  const limitedFile = await openQueued(reader, "c02-limited_capabilities-1");
  await expect(limitedFile).toContainText("This session cannot execute simulated actions.");
  await expect(limitedFile.getByRole("button", { name: /Execute/ })).toHaveCount(0);
  const deniedExecute = await api(reader, "POST", "/v1/actions", {
    approval_id: requireId(limited.approval_id, "approval"),
    idempotency_key: crypto.randomUUID(),
  });
  expect(deniedExecute).toMatchObject({ status: 403, code: "action_permission_denied" });

  const actor = await page.context().newPage();
  await connect(actor, "second_actor");
  const actorFile = await openQueued(actor, "c02-limited_capabilities-1");
  await actor.getByRole("button", { name: "Execute escalate", exact: true }).click();
  await expect(actor.getByText("Only the person who approved this action can execute it.")).toBeVisible();
  await expect(actorFile.getByRole("heading", { name: "Awaiting approval" })).toBeVisible();
  const stored = inspectCase({ caseId: limited.case_id });
  expect(stored.action_count).toBe(0);
  expect(stored.audit_counts.action_denied).toBeGreaterThanOrEqual(2);
  const pendingStored = inspectCase({ caseId: pending.case_id });
  expect(pendingStored.approval_count).toBe(0);
  expect(pendingStored.audit_counts.approval_recorded ?? 0).toBe(0);
});

test("preserves the case, action, and replay across API and database restarts", async ({ page }) => {
  test.setTimeout(180_000);
  const seeded = scenario("executed");
  const approvalId = requireId(seeded.approval_id, "approval");
  const actionId = requireId(seeded.action_id, "action");
  const idempotencyKey = requireId(seeded.idempotency_key, "idempotency key");
  const before = inspectCase({ caseId: seeded.case_id });
  expect(before.action_ids).toEqual([actionId]);
  expect(before.case_state).toBe("closed");

  restart("api");
  expect(stackStatus()).toEqual({ api: "up", database: "up" });
  await page.goto("/");
  await connect(page, "analyst");
  let file = await openQueued(page, "c02-executed");
  await expect(file.getByRole("heading", { name: "Closed" })).toBeVisible();
  await expect(file).toContainText(", executed");
  await expect(file).toContainText("Action succeeded");
  const replay = await api(page, "POST", "/v1/actions", { approval_id: approvalId, idempotency_key: idempotencyKey });
  expect(replay).toMatchObject({ status: 200, replayed: true, actionId });

  restart("db");
  expect(stackStatus()).toEqual({ api: "up", database: "up" });
  await page.reload();
  await connect(page, "analyst");
  file = await openQueued(page, "c02-executed");
  await expect(file.getByRole("heading", { name: "Closed" })).toBeVisible();
  const again = await api(page, "POST", "/v1/actions", { approval_id: approvalId, idempotency_key: idempotencyKey });
  expect(again).toMatchObject({ status: 200, replayed: true, actionId });
  const after = inspectCase({ caseId: seeded.case_id });
  expect(after.action_count).toBe(1);
  expect(after.action_ids).toEqual([actionId]);
  expect(after.audit_total).toBe(before.audit_total);
  expect(after.case_revision).toBe(before.case_revision);
});

test("sign-out and reload do not recover the session credential", async ({ page }) => {
  await connect(page, "analyst");
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByLabel("Session token")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Case queue" })).toHaveCount(0);
  expect(await credentialRecoverable(page)).toBe(false);
  await page.reload();
  await expect(page.getByLabel("Session token")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Case queue" })).toHaveCount(0);
  expect(await credentialRecoverable(page)).toBe(false);
});

test("records a real post-login failure without the session credential", async ({ page }) => {
  test.fail();
  await connect(page, "analyst");
  await expect(page.getByRole("heading", { name: "Case queue" })).toBeVisible();
  const leaked = await page.evaluate(async () => {
    const token = await window.sentinelTakeToken();
    return document.body.innerText.includes(token);
  });
  expect(leaked).toBe(false);
  expect(false, failureProbeMarker).toBe(true);
});

type TransactionBody = {
  external_id: string;
  account_id: string;
  direction: "debit" | "credit";
  amount: { currency: "USD" | "INR" | "GBP" | "JPY"; minor_units: number; currency_exponent: number };
  occurred_at: string;
};

type ScorerPayload = {
  mode: string;
  scoring_kind: string;
  score_semantics: string;
  threshold: number;
  results_id: string | null;
  notes: string[];
  scorer: { name: string; version: string; sha256: string };
  features: { name: string; version: string; sha256: string };
  threshold_policy: { name: string; version: string; sha256: string };
  model: { artifact_sha256: string; candidate: string; results_id: string } | null;
};

type ReportPayload = {
  label: string;
  synthetic: boolean;
  selected: string;
  artifact_sha256: string;
  frozen_threshold: number;
  review_k_per_day: number;
  limitations: string[];
  candidates: Array<{ name: string; test_average_precision: number; test_pr_auc_trapezoid: number }>;
  selected_policy: { frozen_threshold: { flagged: number }; daily_top_k: { flagged: number } };
  uncertainty: { average_precision: [number, number] | null; method: string };
  slices: Array<{ dimension: string; value: string }>;
  pr_curve: Array<{ recall: number; precision: number }>;
  calibration: { reliability: unknown[] };
};

type ModelRecord = {
  case_id?: string;
  request_body: TransactionBody;
  expected_scoring: {
    score: number;
    threshold: number;
    scoring_kind: string;
    inputs?: { values: Record<string, number>; currency: string; profile_home_currency: string; history_rows: number; disclosures_used: number };
    values?: Record<string, number>;
    history_rows?: number;
    disclosures_used?: number;
    profile_home_currency?: string;
  };
};

const MODEL_SCORE = 0.802130558706;
const RECORDED_MODEL_SCORE = 0.61962960122;
const MODEL_THRESHOLD = 4.0295386895426815e-06;
const ARTIFACT_SHA = "6c2982d1df12184f704bc45dbc5882d8f85dba16c50bd9829dda9e674602575b";

function modelRequest(name: string): Pick<ModelRecord, "request_body"> {
  const record = readManifest().scenarios[name] as unknown as ModelRecord | undefined;
  if (!record?.request_body) throw new Error(`missing model scenario ${name}`);
  return record;
}

function modelRecord(name: string): ModelRecord {
  const record = modelRequest(name) as ModelRecord;
  if (!record.expected_scoring) throw new Error(`missing model scoring for ${name}`);
  return record;
}

function tokenIsOwnedSecret(role: "analyst" | "ingest_only"): boolean {
  const token = tokenFor(role);
  const parsed = JSON.parse(readFileSync(readRuntime().secretsPath, "utf8")) as { secrets?: unknown };
  return Array.isArray(parsed.secrets) && parsed.secrets.includes(token);
}

async function readApi(page: Page, apiPath: string): Promise<{ status: number; text: string; body: unknown }> {
  return page.evaluate(async (path) => {
    const token = await window.sentinelTakeToken();
    const response = await fetch(path, {
      headers: { Accept: "application/json", Authorization: `Bearer ${token}` },
    });
    const text = await response.text();
    let body: unknown = null;
    try {
      body = JSON.parse(text);
    } catch {
      body = null;
    }
    return { status: response.status, text, body };
  }, apiPath);
}

async function recordBody(page: Page, body: TransactionBody, expected: string): Promise<void> {
  await page.getByLabel("External id").fill(body.external_id);
  await page.getByLabel("Account id").fill(body.account_id);
  await page.getByLabel("Amount in minor units").fill(String(body.amount.minor_units));
  await page.getByLabel("Currency").selectOption(body.amount.currency);
  await page.getByLabel("Direction").selectOption(body.direction);
  await page.getByLabel("Occurred at").fill(body.occurred_at);
  await page.getByRole("button", { name: "Record transaction" }).click();
  await expect(page.locator("form.ingest .status")).toContainText(expected);
}

function featureValues(record: ModelRecord): Record<string, number> {
  return record.expected_scoring.inputs?.values ?? record.expected_scoring.values ?? {};
}

test.afterAll(() => {
  try {
    if (readManifest().api.scorer && readManifest().api.scorer !== "rule") restartApi("rule");
  } catch {
    // A stack that is already stopped stays with teardown.
  }
});

test("renders the live model scorer and frozen report from the API", async ({ page }) => {
  test.setTimeout(180_000);
  const initial = readManifest().api;
  expect(initial.scorer).toBe("rule");
  expect(readManifest().model_fixtures).toBe(true);
  expect(initial.database_user).toBe("sentinel_browser_runtime");
  expect(tokenIsOwnedSecret("analyst")).toBe(true);
  expect(tokenIsOwnedSecret("ingest_only")).toBe(true);
  const switched = restartApi("model");
  expect(switched.scorer).toBe("model:hgb_balanced@p1");
  expect(switched.pid).not.toBe(initial.pid);
  expect(switched.startTime).not.toBe(String(initial.start_time));
  const status = stackStatus();
  expect(status).toEqual({ api: "up", database: "up" });
  expect(Object.keys(status).sort()).toEqual(["api", "database"]);

  await connect(page, "analyst");
  await expect(page.getByText("deterministic-fixture-investigator x1")).toBeVisible();
  const scoringResponse = await readApi(page, "/v1/scoring");
  expect(scoringResponse.status).toBe(200);
  const scoring = scoringResponse.body as ScorerPayload;
  expect(scoring.threshold).toBe(MODEL_THRESHOLD);
  expect(scoring.threshold).toBeGreaterThan(0);
  expect(scoring).toMatchObject({
    mode: "model",
    scoring_kind: "model",
    score_semantics: "uncalibrated_score",
    threshold: MODEL_THRESHOLD,
    results_id: "p1",
  });
  expect(scoring.scorer).toMatchObject({ name: "hgb_balanced", version: "p1", sha256: ARTIFACT_SHA });
  expect(scoring.model?.artifact_sha256).toBe(ARTIFACT_SHA);
  expect(scoring.model?.candidate).toBe("hgb_balanced");
  const scoringSection = page.locator("#scoring");
  await expect(scoringSection).toContainText("hgb_balanced p1 (model, uncalibrated_score)");
  await expect(scoringSection).toContainText("sentinel-features f1");
  await expect(scoringSection.locator(".threshold-figure")).toHaveText("4.0295386895426815e-6");
  await expect(scoringSection).toContainText("not a fraud probability");
  await expect(scoringSection).not.toContainText("deterministic-fixture-investigator");
  await expect(scoringSection).not.toContainText(ARTIFACT_SHA);

  const reportResponse = await readApi(page, "/v1/model-results/p1");
  expect(reportResponse.status).toBe(200);
  const report = reportResponse.body as ReportPayload;
  expect(report.label).toBe("offline synthetic benchmark");
  expect(report.synthetic).toBe(true);
  expect(report.artifact_sha256).toBe(ARTIFACT_SHA);
  expect(report.frozen_threshold).toBe(MODEL_THRESHOLD);
  expect(report.selected_policy.frozen_threshold.flagged).toBe(442);
  expect(report.selected_policy.daily_top_k.flagged).toBe(510);
  await expect(page.getByRole("heading", { name: "offline synthetic benchmark" })).toBeVisible();
  await expect(page.getByText("Synthetic data. This is an offline benchmark, not a live tenant statistic and not a production result.")).toBeVisible();
  const frozen = page.getByRole("table", { name: `Frozen online threshold ${formatScore(report.frozen_threshold)}` });
  const daily = page.getByRole("table", { name: `Offline daily top-${formatCount(report.review_k_per_day)} review` });
  await expect(frozen.getByText("442", { exact: true })).toBeVisible();
  await expect(frozen.getByText("510", { exact: true })).toHaveCount(0);
  await expect(daily.getByText("510", { exact: true })).toBeVisible();
  await expect(daily.getByText("442", { exact: true })).toHaveCount(0);
  const selected = report.candidates.find((item) => item.name === report.selected);
  expect(selected).toBeTruthy();
  const comparison = page.getByRole("table", { name: "Validation and test average precision" });
  await expect(comparison.getByRole("row", { name: new RegExp(report.selected) })).toContainText(formatScore(selected?.test_average_precision));
  await expect(comparison.getByRole("row", { name: new RegExp(report.selected) })).toContainText("selected");
  await expect(comparison.getByRole("row", { name: new RegExp(report.selected) })).toContainText(formatScore(selected?.test_pr_auc_trapezoid));
  if (report.uncertainty.average_precision) {
    await expect(page.getByText(new RegExp(`${formatScore(report.uncertainty.average_precision[0])} to ${formatScore(report.uncertainty.average_precision[1])}`))).toBeVisible();
  }
  const currency = page.getByRole("table", { name: "Currency slices, kept separate" });
  const scenarioTable = page.getByRole("table", { name: /Scenario slices/ });
  await expect(scenarioTable).toContainText("Offline hidden synthetic truth");
  for (const row of report.slices.filter((item) => item.dimension === "currency")) {
    await expect(currency.getByRole("row", { name: new RegExp(row.value) })).toBeVisible();
    await expect(scenarioTable.getByRole("row", { name: new RegExp(`^${row.value}\\b`) })).toHaveCount(0);
  }
  for (const row of report.slices.filter((item) => item.dimension === "scenario")) {
    await expect(scenarioTable.getByRole("row", { name: new RegExp(row.value) })).toBeVisible();
  }
  await expect(page.getByRole("table", { name: "Reliability bins" }).getByRole("row")).toHaveCount(report.calibration.reliability.length + 1);
  await page.getByRole("button", { name: "Show precision-recall points" }).click();
  await expect(page.getByRole("table", { name: "Test precision-recall points" }).getByRole("row")).toHaveCount(report.pr_curve.length + 1);
  for (const limitation of report.limitations) await expect(page.getByText(limitation)).toBeVisible();
});

test("stores nothing when a model ingestion has no account profile", async ({ page }) => {
  const record = modelRequest("model_missing_profile");
  await connect(page, "analyst");
  await recordBody(page, record.request_body, "The account has no profile, so nothing was scored or stored.");
  await expect(page.locator("form.ingest .status")).not.toContainText("A case was opened");
  await expect(page.locator("form.ingest .status")).not.toContainText("Uncalibrated ranking");
  await expect(page.locator("form.ingest .status")).not.toContainText("Rule score");
  expect(inspectPresence(record.request_body.external_id)).toEqual({
    alerts: 0,
    cases: 0,
    external_id: record.request_body.external_id,
    scoring_outcomes: 0,
    transactions: 0,
  });
});

test("investigates, approves, and executes a fresh model score", async ({ page }) => {
  test.setTimeout(180_000);
  const seeded = seed("model_live_alert", 1) as unknown as ModelRecord;
  expect(seeded.expected_scoring.score).toBe(MODEL_SCORE);
  expect(seeded.expected_scoring.threshold).toBe(MODEL_THRESHOLD);
  expect(seeded.expected_scoring.scoring_kind).toBe("model");
  expect(seeded.expected_scoring.disclosures_used).toBe(0);
  expect(seeded.expected_scoring.history_rows).toBe(0);
  expect(seeded.expected_scoring.profile_home_currency).toBe("USD");
  expect(seeded.expected_scoring.values).toMatchObject({
    amount_minor: 250000,
    is_foreign_currency: 0,
    prior_known_fraud: 0,
    account_age_days: 400,
  });
  await connect(page, "analyst");
  await recordBody(page, seeded.request_body, "A case was opened.");
  const status = page.locator("form.ingest .status");
  await expect(status).toContainText(`Uncalibrated ranking ${formatScore(MODEL_SCORE)}`);
  await expect(status).not.toContainText("Rule score");
  const file = caseFile(page);
  await expect(file).toContainText(`Synthetic transaction ${seeded.request_body.external_id}`);
  await expect(file).toContainText("2500.00 USD");
  await expect(file).toContainText(`Uncalibrated ranking ${formatScore(MODEL_SCORE)}, threshold ${formatScore(MODEL_THRESHOLD)}`);
  await expect(file).toContainText("Not a fraud probability.");
  await expect(file).toContainText("Transaction currency USD.");
  await expect(file).toContainText("Profile home currency USD.");
  await expect(file).toContainText("History rows 0. Disclosures used 0.");
  const inputs = file.getByRole("table", { name: "Decision-time feature values" });
  for (const [name, value] of Object.entries(featureValues(seeded))) {
    await expect(inputs.getByRole("row", { name: new RegExp(`^${name}\\b`) })).toContainText(String(value));
  }
  const stored = inspectScoring({ externalId: seeded.request_body.external_id });
  expect(stored.score).toBe(MODEL_SCORE);
  expect(stored.scorer_sha256).toBe(ARTIFACT_SHA);
  expect(stored.model_artifact_sha256).toBe(ARTIFACT_SHA);
  expect(stored.model_results_id).toBe("p1");
  expect(stored.feature_values).toEqual(featureValues(seeded));
  const detail = await readApi(page, `/v1/cases/${stored.case_id}`);
  expect(detail.status).toBe(200);
  const body = detail.body as { scoring: { score: number; scorer: { sha256: string }; model: { artifact_sha256: string } } };
  expect(body.scoring.score).toBe(stored.score);
  expect(body.scoring.scorer.sha256).toBe(stored.scorer_sha256);
  expect(body.scoring.model.artifact_sha256).toBe(stored.model_artifact_sha256);
  await expect(file).not.toContainText(ARTIFACT_SHA);

  await page.getByRole("button", { name: "Investigate case", exact: true }).click();
  await expect(file.getByRole("heading", { name: "Awaiting approval" })).toBeVisible();
  await expect(file).toContainText("Run by deterministic-fixture-investigator x1");
  const text = await file.innerText();
  const escalate = text.match(/Escalate transaction ([0-9a-f-]{36}), reason unusual_amount/);
  const hold = text.match(/Simulated hold of 2500\.00 USD on transaction ([0-9a-f-]{36})/);
  expect(escalate ?? hold).not.toBeNull();
  const proposed = inspectCase({ externalId: seeded.request_body.external_id });
  expect(proposed.proposals.at(-1)?.transaction_id).toBe((escalate ?? hold)?.[1]);
  await page.getByRole("button", { name: "Approve", exact: true }).click();
  const executeName = escalate ? "Execute escalate" : "Execute simulated hold";
  await page.getByRole("button", { name: executeName, exact: true }).click();
  await expect(file.getByRole("heading", { name: "Closed" })).toBeVisible();
  await expect(file).toContainText("Action succeeded");
  const closed = inspectCase({ externalId: seeded.request_body.external_id });
  expect(closed.case_state).toBe("closed");
  expect(closed.action_count).toBe(1);
  expect(closed.consumed_approval_count).toBe(1);
  expect(closed.audit_counts.action_succeeded).toBe(1);
  expect(inspectScoring({ externalId: seeded.request_body.external_id }).score).toBe(MODEL_SCORE);
});

test("keeps stored model and rule identities across real API and database restarts", async ({ page }) => {
  test.setTimeout(240_000);
  const recorded = modelRecord("model_alert");
  const open = scenario("open_case");
  expect(recorded.expected_scoring.score).toBe(RECORDED_MODEL_SCORE);
  await connect(page, "analyst");
  let file = await openQueued(page, recorded.request_body.external_id);
  await expect(file).toContainText("2500.00 GBP");
  await expect(file).toContainText(`Uncalibrated ranking ${formatScore(RECORDED_MODEL_SCORE)}, threshold ${formatScore(MODEL_THRESHOLD)}`);
  await expect(file).toContainText("Transaction currency GBP.");
  await expect(file).toContainText("Profile home currency USD.");
  await expect(file).toContainText("Disclosures used 1.");
  await expect(file.getByRole("row", { name: /prior_known_fraud/ })).toContainText("1");
  await expect(file.getByRole("row", { name: /is_foreign_currency/ })).toContainText("1");
  let stored = inspectScoring({ externalId: recorded.request_body.external_id });
  expect(stored).toMatchObject({
    score: RECORDED_MODEL_SCORE,
    threshold: MODEL_THRESHOLD,
    scoring_kind: "model",
    score_semantics: "uncalibrated_score",
    scorer_name: "hgb_balanced",
    scorer_version: "p1",
    scorer_sha256: ARTIFACT_SHA,
    model_artifact_sha256: ARTIFACT_SHA,
    input_currency: "GBP",
    profile_home_currency: "USD",
    disclosures_used: 1,
    history_rows: 0,
  } satisfies Partial<StoredScoring>);

  const modelPid = readManifest().api.pid;
  const ruled = restartApi("rule");
  expect(ruled.scorer).toBe("rule");
  expect(ruled.pid).not.toBe(modelPid);
  expect(stackStatus()).toEqual({ api: "up", database: "up" });
  await page.goto("/");
  await connect(page, "analyst");
  const ruleResponse = await readApi(page, "/v1/scoring");
  const ruleScorer = ruleResponse.body as ScorerPayload;
  expect(ruleScorer).toMatchObject({ mode: "rule", scoring_kind: "rule", score_semantics: "heuristic", results_id: null });
  expect(ruleScorer.scorer).toMatchObject({ name: "velocity-amount-rules", version: "r1" });
  await expect(page.locator("#scoring")).toContainText("velocity-amount-rules r1 (rule, heuristic)");
  await expect(page.getByText("This server has no offline model report for the configured scorer.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "offline synthetic benchmark" })).toHaveCount(0);

  file = await openQueued(page, recorded.request_body.external_id);
  await expect(file).toContainText(`Uncalibrated ranking ${formatScore(RECORDED_MODEL_SCORE)}`);
  await expect(file).toContainText("The configured scorer is velocity-amount-rules r1 (rule, heuristic).");
  await expect(file).toContainText("This record keeps hgb_balanced p1.");
  await expect(file).toContainText("Not a fraud probability.");
  const ruleCase = await openQueued(page, "c02-open_case");
  await expect(ruleCase).toContainText("Rule score 0.6, threshold 0.5");
  await expect(ruleCase).toContainText("Not a probability.");
  await expect(ruleCase).toContainText("This record keeps velocity-amount-rules r1.");
  await expect(ruleCase).not.toContainText("Stored feature inputs");
  const ruleStored = inspectScoring({ caseId: open.case_id });
  expect(ruleStored).toMatchObject({
    scoring_kind: "rule",
    score_semantics: "heuristic",
    score: 0.6,
    threshold: 0.5,
    scorer_name: "velocity-amount-rules",
    model_candidate: null,
    feature_values: null,
  });

  await recordBody(page, recorded.request_body, "This repeated an earlier ingest.");
  await expect(page.locator("form.ingest .status")).toContainText(`Uncalibrated ranking ${formatScore(RECORDED_MODEL_SCORE)}`);
  await expect(page.locator("form.ingest .status")).not.toContainText("Rule score");
  expect(inspectScoring({ externalId: recorded.request_body.external_id }).score).toBe(RECORDED_MODEL_SCORE);

  const freshRule = `i02-rule-mode-${crypto.randomUUID()}`;
  await record(page, { externalId: freshRule, accountId: crypto.randomUUID(), minor: "1500", occurredAt: minutesAgo(3) }, "No case was opened.");
  await expect(page.locator("form.ingest .status")).toContainText("Rule score");
  const freshStored = inspectScoring({ externalId: freshRule });
  expect(freshStored.scoring_kind).toBe("rule");
  expect(freshStored.model_candidate).toBeNull();
  expect(freshStored.feature_values).toBeNull();

  const restored = restartApi("model");
  expect(restored.scorer).toBe("model:hgb_balanced@p1");
  expect(restored.pid).not.toBe(ruled.pid);
  const apiPid = restored.pid;
  restart("db");
  expect(readManifest().api.pid).toBe(apiPid);
  expect(stackStatus()).toEqual({ api: "up", database: "up" });
  await page.goto("/");
  await connect(page, "analyst");
  file = await openQueued(page, recorded.request_body.external_id);
  await expect(file).toContainText(`Uncalibrated ranking ${formatScore(RECORDED_MODEL_SCORE)}`);
  await expect(file).toContainText("This record keeps hgb_balanced p1.");
  stored = inspectScoring({ externalId: recorded.request_body.external_id });
  expect(stored.score).toBe(RECORDED_MODEL_SCORE);
  expect(stored.scorer_sha256).toBe(ARTIFACT_SHA);
  await recordBody(page, recorded.request_body, "This repeated an earlier ingest.");
  expect(inspectScoring({ externalId: recorded.request_body.external_id }).score).toBe(RECORDED_MODEL_SCORE);
  const ruleAgain = await openQueued(page, "c02-open_case");
  await expect(ruleAgain).toContainText("Rule score 0.6, threshold 0.5");
  await expect(ruleAgain).toContainText("The configured scorer is hgb_balanced p1 (model, uncalibrated_score).");
  await expect(ruleAgain).toContainText("This record keeps velocity-amount-rules r1.");
});

test("denies ingest-only and foreign model access and ignores a late report after sign-out", async ({ page }) => {
  test.setTimeout(180_000);
  const recorded = modelRecord("model_alert");
  if (!recorded.case_id) throw new Error("recorded model case missing");
  await connect(page, "ingest_only");
  await expect(page.getByText("This session cannot read the configured scorer.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "offline synthetic benchmark" })).toHaveCount(0);
  await expect(page.getByText("4.0295386895426815e-6")).toHaveCount(0);
  const deniedScoring = await readApi(page, "/v1/scoring");
  const deniedReport = await readApi(page, "/v1/model-results/p1");
  expect(deniedScoring.status).toBe(403);
  expect(deniedScoring.text).toContain("permission_denied");
  expect(deniedReport.status).toBe(403);
  expect(deniedReport.text).toContain("permission_denied");
  expect(deniedReport.text).not.toContain("offline synthetic benchmark");

  await page.getByRole("button", { name: "Sign out" }).click();
  await connect(page, "other_session");
  await expect(page.getByRole("button", { name: queueName("c02-foreign_session_case") })).toBeVisible();
  await expect(page.getByRole("button", { name: queueName(recorded.request_body.external_id) })).toHaveCount(0);
  const hidden = await api(page, "GET", `/v1/cases/${recorded.case_id}`);
  expect(hidden).toMatchObject({ status: 404, code: "not_found" });
  const hiddenAudit = await api(page, "GET", `/v1/cases/${recorded.case_id}/audit`);
  expect(hiddenAudit).toMatchObject({ status: 404, code: "not_found" });

  await page.getByRole("button", { name: "Sign out" }).click();
  await page.route("**/v1/model-results/p1", async (route) => {
    const url = new URL(route.request().url());
    url.pathname = "/v1/model-results/not-a-report";
    const response = await route.fetch({ url: url.toString() });
    await route.fulfill({ response });
  });
  await connect(page, "analyst");
  await expect(page.getByText("That model report is not on this server.")).toBeVisible();
  await expect(page.locator("#scoring")).toContainText("hgb_balanced p1 (model, uncalibrated_score)");
  await expect(page.getByRole("heading", { name: "offline synthetic benchmark" })).toHaveCount(0);
  await expect(page.getByText("No claim of real-bank effectiveness, savings or production efficacy.")).toHaveCount(0);
  await page.unroute("**/v1/model-results/p1");

  let release: () => void = () => undefined;
  const held = new Promise<void>((resolve) => {
    release = () => resolve();
  });
  await page.route("**/v1/model-results/p1", async (route) => {
    await held;
    await route.continue();
  });
  await page.getByRole("button", { name: "Sign out" }).click();
  await connect(page, "analyst");
  await expect(page.getByText("Loading the offline benchmark.")).toBeVisible();
  await page.getByRole("button", { name: "Sign out" }).click();
  release();
  await expect(page.getByLabel("Session token")).toBeVisible();
  await expect(page.getByRole("heading", { name: "offline synthetic benchmark" })).toHaveCount(0);
  expect(await credentialRecoverable(page)).toBe(false);
});
