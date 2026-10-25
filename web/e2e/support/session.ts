import { expect, type Page } from "@playwright/test";
import { tokenFor, type SessionRole } from "./stack";

declare global {
  interface Window {
    sentinelTakeToken: () => Promise<string>;
  }
}

export type ApiObservation = {
  status: number;
  code: string | null;
  actionId: string | null;
  replayed: boolean | null;
  revision: number | null;
};

async function installToken(page: Page, role: SessionRole): Promise<void> {
  const present = await page.evaluate(() => typeof window.sentinelTakeToken === "function").catch(() => false);
  if (present) return;
  const token = tokenFor(role);
  await page.exposeBinding("sentinelTakeToken", () => token);
}

export async function connect(page: Page, role: SessionRole): Promise<void> {
  await page.goto("/");
  await installToken(page, role);
  await page.getByLabel("Session token").waitFor();
  const filled = await page.evaluate(async () => {
    const input = document.querySelector('input[name="session-token"]');
    if (!(input instanceof HTMLInputElement)) return "missing";
    const value = await window.sentinelTakeToken();
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
    if (!setter) return "missing";
    setter.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
    return input.value.length > 0 ? "set" : "empty";
  });
  if (filled !== "set") throw new Error("session field was not set");
  await page.getByRole("button", { name: "Connect" }).click();
  try {
    await expect(page.getByRole("heading", { name: "Case queue" })).toBeVisible();
  } catch {
    await page.evaluate(() => {
      const input = document.querySelector('input[name="session-token"]');
      if (input instanceof HTMLInputElement) input.value = "";
    });
    throw new Error("analyst session did not open");
  }
}

export async function credentialRecoverable(page: Page): Promise<boolean> {
  return page.evaluate(async () => {
    const token = await window.sentinelTakeToken();
    const stored = [location.href, document.cookie, JSON.stringify({ ...localStorage }), JSON.stringify({ ...sessionStorage })].join("\n");
    return stored.includes(token);
  });
}

export async function api(page: Page, method: string, apiPath: string, body?: unknown): Promise<ApiObservation> {
  return page.evaluate(
    async ({ method, apiPath, body }) => {
      const token = await window.sentinelTakeToken();
      const headers = new Headers({ Accept: "application/json", Authorization: `Bearer ${token}` });
      let payload: string | undefined;
      if (body !== undefined) {
        headers.set("Content-Type", "application/json");
        payload = JSON.stringify(body);
      }
      let response: Response;
      try {
        response = await fetch(apiPath, { method, headers, body: payload });
      } catch {
        return { status: 0, code: null, actionId: null, replayed: null, revision: null };
      }
      const text = await response.text();
      let code: string | null = null;
      let actionId: string | null = null;
      let replayed: boolean | null = null;
      let revision: number | null = null;
      try {
        const parsed = JSON.parse(text) as {
          error?: unknown;
          replayed?: unknown;
          action?: { id?: unknown };
          case?: { revision?: unknown };
        };
        if (typeof parsed.error === "string") code = parsed.error;
        if (typeof parsed.replayed === "boolean") replayed = parsed.replayed;
        if (typeof parsed.action?.id === "string") actionId = parsed.action.id;
        if (typeof parsed.case?.revision === "number") revision = parsed.case.revision;
      } catch {
        code = null;
      }
      return { status: response.status, code, actionId, replayed, revision };
    },
    { method, apiPath, body },
  );
}
