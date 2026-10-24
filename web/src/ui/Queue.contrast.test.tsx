import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { CasePage } from "../api/types";
import { Queue } from "./Queue";

// Assemble the filename so Vite does not rewrite a static stylesheet literal.
const stylesheet = readFileSync(
  resolve(dirname(fileURLToPath(import.meta.url)), ["..", ["styles", "css"].join(".")].join("/")),
  "utf8",
);

const page: CasePage = {
  items: [
    {
      id: "case-contrast",
      state: "awaiting_approval",
      revision: 3,
      created_at: "2026-10-23T17:00:00Z",
      updated_at: "2026-10-23T17:00:00Z",
      alert_id: "alert-contrast",
      transaction_id: "txn-contrast",
      external_id: "contrast-ext",
      amount: { currency: "USD", currency_exponent: 2, minor_units: 250000 },
      direction: "debit",
      score: 0.6,
      threshold: 0.5,
      scoring_kind: "rule",
      score_semantics: "heuristic",
    },
  ],
  next_cursor: null,
  limit: 25,
};

type Spec = [number, number, number];
type NodeDesc = { tag: string; classes: string[]; pseudos: string[] };

interface Rule {
  selector: string;
  prop: string;
  value: string;
  order: number;
}

function channel(value: number): number {
  const scaled = value / 255;
  return scaled <= 0.04045 ? scaled / 12.92 : ((scaled + 0.055) / 1.055) ** 2.4;
}

function hexColor(input: string): string {
  const named: Record<string, string> = { white: "#ffffff", black: "#000000" };
  const value = named[input.toLowerCase()] ?? input;
  if (!/^#[0-9a-fA-F]{6}$/.test(value)) throw new Error(`unparsed color ${input}`);
  return value;
}

function contrast(foreground: string, background: string): number {
  const parse = (hex: string) => {
    const value = hexColor(hex).slice(1);
    const channels = [0, 2, 4].map((index) => channel(parseInt(value.slice(index, index + 2), 16)));
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
  };
  const front = parse(foreground);
  const back = parse(background);
  return (Math.max(front, back) + 0.05) / (Math.min(front, back) + 0.05);
}

function specificity(selector: string): Spec {
  const ids = selector.match(/#[\w-]+/g)?.length ?? 0;
  const classes = selector.match(/\.[\w-]+|:(?![:])[\w-]+/g)?.length ?? 0;
  const stripped = selector
    .replace(/#[\w-]+/g, " ")
    .replace(/\.[\w-]+/g, " ")
    .replace(/:(?![:])[\w-]+/g, " ")
    .replace(/::[\w-]+/g, " element ");
  const elements = stripped.match(/[a-zA-Z][\w-]*/g)?.length ?? 0;
  return [ids, classes, elements];
}

function parseRules(css: string): { rules: Rule[]; vars: Record<string, string> } {
  const rules: Rule[] = [];
  const vars: Record<string, string> = {};
  let order = 0;
  const source = css.replace(/\/\*[\s\S]*?\*\//g, "");
  for (const block of source.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    const body = block[2];
    for (const selector of block[1].split(",")) {
      const trimmed = selector.trim().replace(/\s+/g, " ");
      if (!trimmed) continue;
      for (const part of body.split(";")) {
        const split = part.split(":");
        if (split.length < 2) continue;
        const prop = split[0].trim();
        const value = split.slice(1).join(":").trim();
        if (!prop || !value) continue;
        order += 1;
        if (trimmed === ":root" && prop.startsWith("--")) vars[prop] = value;
        rules.push({ selector: trimmed, prop, value, order });
      }
    }
  }
  return { rules, vars };
}

function compoundMatches(part: string, node: NodeDesc): boolean {
  const tag = part.match(/^[a-zA-Z][\w-]*/)?.[0] ?? null;
  if (tag && tag !== node.tag) return false;
  const classes = [...part.matchAll(/\.([\w-]+)/g)].map((match) => match[1]);
  if (!classes.every((name) => node.classes.includes(name))) return false;
  const pseudos = [...part.matchAll(/:([\w-]+)/g)].map((match) => match[1]);
  return pseudos.every((name) => node.pseudos.includes(name));
}

function selectorMatches(selector: string, ancestry: NodeDesc[]): boolean {
  const parts = selector.split(" ");
  let index = 0;
  for (let cursor = parts.length - 1; cursor >= 0; cursor -= 1) {
    let found = false;
    const start = index;
    while (index < ancestry.length) {
      const node = ancestry[index];
      index += 1;
      if (compoundMatches(parts[cursor], node)) {
        found = true;
        break;
      }
      if (cursor === parts.length - 1 && index === start + 1) return false;
    }
    if (!found) return false;
  }
  return true;
}

function compareSpec(left: Spec, right: Spec): number {
  for (let index = 0; index < 3; index += 1) {
    if (left[index] !== right[index]) return left[index] - right[index];
  }
  return 0;
}

function declared(rules: Rule[], ancestry: NodeDesc[], prop: string): string | null {
  let best: Rule | null = null;
  for (const rule of rules) {
    if (rule.prop !== prop || !selectorMatches(rule.selector, ancestry)) continue;
    if (!best) {
      best = rule;
      continue;
    }
    const spec = compareSpec(specificity(rule.selector), specificity(best.selector));
    if (spec > 0 || (spec === 0 && rule.order > best.order)) best = rule;
  }
  return best?.value ?? null;
}

function resolveVars(value: string, vars: Record<string, string>): string {
  return value.replace(/var\(\s*(--[\w-]+)\s*\)/g, (_match, name: string) => vars[name] ?? name);
}

function usedColor(css: string, ancestry: NodeDesc[]): string {
  const { rules, vars } = parseRules(css);
  for (let index = 0; index < ancestry.length; index += 1) {
    const value = declared(rules, ancestry.slice(index), "color");
    if (!value || value === "inherit") continue;
    return resolveVars(value, vars);
  }
  return "#000000";
}

function opaqueBackground(css: string, ancestry: NodeDesc[]): string {
  const { rules, vars } = parseRules(css);
  for (let index = 0; index < ancestry.length; index += 1) {
    const value = declared(rules, ancestry.slice(index), "background") ?? declared(rules, ancestry.slice(index), "background-color");
    if (!value || value === "inherit" || value === "transparent") continue;
    return resolveVars(value, vars);
  }
  throw new Error("no opaque background");
}

const body: NodeDesc = { tag: "body", classes: [], pseudos: [] };
const queue: NodeDesc = { tag: "section", classes: ["queue"], pseudos: [] };

function row(selected: boolean, pseudos: string[]): NodeDesc[] {
  return [
    { tag: "strong", classes: [], pseudos: [] },
    { tag: "button", classes: selected ? ["row", "selected"] : ["row"], pseudos },
    queue,
    body,
  ];
}

function score(selected: boolean, pseudos: string[]): NodeDesc[] {
  return [
    { tag: "p", classes: ["meta", "alert-score"], pseudos: [] },
    { tag: "button", classes: selected ? ["row", "selected"] : ["row"], pseudos },
    queue,
    body,
  ];
}

const states: Array<{ selected: boolean; pseudos: string[] }> = [
  { selected: false, pseudos: [] },
  { selected: false, pseudos: ["hover"] },
  { selected: false, pseudos: ["focus-visible"] },
  { selected: true, pseudos: [] },
  { selected: true, pseudos: ["hover"] },
  { selected: true, pseudos: ["focus-visible"] },
];

function renderQueue(selected: boolean) {
  cleanup();
  render(
    <Queue
      page={page}
      loading={false}
      state=""
      selectedId={selected ? "case-contrast" : null}
      hasPrevious={false}
      busy={false}
      onState={() => undefined}
      onSelect={() => undefined}
      onPrevious={() => undefined}
      onNext={() => undefined}
    />,
  );
  return screen.getByRole("button", { name: /2500\.00 USD/ });
}

afterEach(() => cleanup());

describe("queue contrast", () => {
  it("fails the reviewed white-on-pale amount pairing", () => {
    const broken = `
      :root { --desk: #e4eee8; --sheet: #f7fbf8; }
      body { background: var(--desk); color: #14241c; }
      .row { background: transparent; }
      .row.selected, button.row.selected { background: var(--sheet); }
      button { color: white; background: #143e63; }
    `;
    for (const state of states) {
      const ratio = contrast(usedColor(broken, row(state.selected, state.pseudos)), opaqueBackground(broken, row(state.selected, state.pseudos)));
      expect(ratio).toBeLessThan(2);
    }
  });

  it("keeps the amount and score readable for idle, hover, focus, and selected rows", () => {
    const idle = renderQueue(false);
    idle.focus();
    expect(document.activeElement).toBe(idle);
    expect(idle.classList.contains("selected")).toBe(false);
    expect(idle.querySelector("strong")?.textContent).toBe("2500.00 USD");
    expect(idle.querySelector(".alert-score")?.textContent).toMatch(/Rule score 0\.6/);

    const selected = renderQueue(true);
    selected.focus();
    expect(document.activeElement).toBe(selected);
    expect(selected.classList.contains("selected")).toBe(true);

    for (const state of states) {
      const amountChain = row(state.selected, state.pseudos);
      const scoreChain = score(state.selected, state.pseudos);
      const amountColor = usedColor(stylesheet, amountChain);
      const scoreColor = usedColor(stylesheet, scoreChain);
      const background = opaqueBackground(stylesheet, amountChain);
      expect(amountColor).not.toBe("#ffffff");
      expect(amountColor).not.toBe("white");
      expect(contrast(amountColor, background)).toBeGreaterThanOrEqual(4.5);
      expect(contrast(scoreColor, opaqueBackground(stylesheet, scoreChain))).toBeGreaterThanOrEqual(4.5);
      expect(scoreColor).not.toBe(amountColor);
      expect(scoreColor).not.toBe("#ffffff");
    }
  });
});
