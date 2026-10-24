import { writeFileSync } from "node:fs";
import path from "node:path";
import { expect, test, type Locator, type Page } from "@playwright/test";
import { api, connect, credentialRecoverable } from "./support/session";
import { inspectCase, postActionDirect, restart, scenario, seed, stackStatus } from "./support/stack";
import { runtimeDir } from "./support/runtime";

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

test("saves a post-login failure artifact without the session credential", async ({ page }, testInfo) => {
  await connect(page, "analyst");
  const snapshot = await page.locator("body").ariaSnapshot();
  await testInfo.attach("deliberate-failure", {
    body: `Error: artifact probe\n\n${snapshot}\n`,
    contentType: "text/plain",
  });
  const leaked = await page.evaluate(async (text) => {
    const token = await window.sentinelTakeToken();
    return text.includes(token);
  }, snapshot);
  expect(leaked).toBe(false);
  expect(snapshot).toContain("Case queue");
  expect(snapshot).not.toContain("Session token");
});
