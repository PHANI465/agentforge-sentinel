// @vitest-environment node
import { randomBytes } from "node:crypto";
import { existsSync, mkdirSync, mkdtempSync, readdirSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { removeVerifiedStore, scanForTokens, type RunPaths } from "./docArtifacts";

/** R65/R66 regressions for the documents browser suite's own cleanup and token scan. They run
 * on throwaway directories only, never on the suite's real runtime. */

let base: string;
let run: RunPaths;
let store: string;

function makeStore(withBridge = false): void {
  mkdirSync(store);
  writeFileSync(path.join(store, ".docworker-store"), JSON.stringify({ owner: "test", dir: store, version: 1 }));
  for (const sub of ["handles", "runs", "recovery", ...(withBridge ? ["api-bridge"] : [])]) mkdirSync(path.join(store, sub));
}

beforeEach(() => {
  base = mkdtempSync(path.join(tmpdir(), "doc01-artifacts-"));
  const webRoot = path.join(base, "web");
  const runtimeDir = path.join(webRoot, "e2e", ".runtime");
  const stackDir = path.join(runtimeDir, "stacks", "sentinel-browser-test");
  mkdirSync(stackDir, { recursive: true });
  mkdirSync(path.join(webRoot, "test-results"), { recursive: true });
  run = { webRoot, runtimeDir, stackDir, secretsPath: path.join(runtimeDir, "owned-secrets.json") };
  store = path.join(runtimeDir, "doc-store");
});

afterEach(() => {
  rmSync(base, { recursive: true, force: true });
});

describe("R66: the store is removed only when its whole tree is the expected empty layout", () => {
  it.each([false, true])("removes a normal empty store (api-bridge present: %s)", (withBridge) => {
    makeStore(withBridge);
    expect(removeVerifiedStore(store, run.runtimeDir)).toEqual({ removed: true, reason: "removed" });
    expect(existsSync(store)).toBe(false);
  });

  it.each([
    ["a file in the store root", "canary.txt", (dir: string) => writeFileSync(path.join(dir, "canary.txt"), "canary")],
    ["a directory in the store root", "extra", (dir: string) => mkdirSync(path.join(dir, "extra"))],
    ["a file inside runs", "runs", (dir: string) => writeFileSync(path.join(dir, "runs", "canary.txt"), "canary")],
    ["a directory inside handles", "handles", (dir: string) => mkdirSync(path.join(dir, "handles", "h_canary"))],
    ["a known name that is a file", "recovery", (dir: string) => {
      rmSync(path.join(dir, "recovery"), { recursive: true });
      writeFileSync(path.join(dir, "recovery"), "canary");
    }],
    ["a marker that is a directory", ".docworker-store", (dir: string) => {
      rmSync(path.join(dir, ".docworker-store"));
      mkdirSync(path.join(dir, ".docworker-store"));
    }],
    ["a link in the store root", "linked", (dir: string) => {
      const target = path.join(base, "outside");
      mkdirSync(target);
      writeFileSync(path.join(target, "keep.txt"), "outside");
      symlinkSync(target, path.join(dir, "linked"), "junction");
    }],
  ])("refuses %s and leaves everything in place", (_label, entry, plant) => {
    makeStore(true);
    plant(store);
    const before = readdirSync(store).sort();
    const result = removeVerifiedStore(store, run.runtimeDir);
    expect(result.removed).toBe(false);
    expect(result.entry).toBe(entry);
    expect(existsSync(store)).toBe(true);
    expect(readdirSync(store).sort()).toEqual(before);
    if (entry === "linked") expect(existsSync(path.join(base, "outside", "keep.txt"))).toBe(true);
  });

  it("refuses an entry it cannot read", () => {
    makeStore();
    const io = { readdir: (dir: string) => {
      if (path.basename(dir) === "runs") throw Object.assign(new Error("denied"), { code: "EACCES" });
      return readdirSync(dir);
    } };
    expect(removeVerifiedStore(store, run.runtimeDir, io)).toEqual({ removed: false, reason: "store_entry_unreadable", entry: "runs" });
    expect(existsSync(path.join(store, "runs"))).toBe(true);
  });

  it("keeps the marker, parent-path and known-subdirectory checks", () => {
    expect(removeVerifiedStore(store, run.runtimeDir).reason).toBe("store_missing");
    makeStore();
    rmSync(path.join(store, ".docworker-store"));
    expect(removeVerifiedStore(store, run.runtimeDir).reason).toBe("store_marker_missing");
    writeFileSync(path.join(store, ".docworker-store"), "{}");
    rmSync(path.join(store, "handles"), { recursive: true });
    expect(removeVerifiedStore(store, run.runtimeDir)).toMatchObject({ removed: false, entry: "handles" });
    mkdirSync(path.join(store, "handles"));
    const elsewhere = path.join(base, "doc-store");
    makeStoreAt(elsewhere);
    expect(removeVerifiedStore(elsewhere, run.runtimeDir).reason).toBe("store_outside_runtime");
    expect(existsSync(elsewhere)).toBe(true);
    expect(existsSync(store)).toBe(true);
  });
});

function makeStoreAt(dir: string): void {
  mkdirSync(dir);
  writeFileSync(path.join(dir, ".docworker-store"), "{}");
  for (const sub of ["handles", "runs", "recovery"]) mkdirSync(path.join(dir, sub));
}

describe("R65: document tokens are searched for in stack-owned artifacts too", () => {
  const tokens = () => ["doc-analyst-token-" + randomBytes(12).toString("hex"), "doc-other-token-" + randomBytes(12).toString("hex")];

  it("reports a canary token in a stack-owned log by relative name, never by content", () => {
    const canary = `doc01-canary-${randomBytes(16).toString("hex")}`;
    writeFileSync(path.join(run.stackDir, "api.log"), `INFO started\nAuthorization: ${canary}\n`);
    writeFileSync(path.join(run.runtimeDir, "runtime.json"), "{}");
    writeFileSync(path.join(run.webRoot, "test-results", "report.txt"), "no secrets here");
    const result = scanForTokens([...tokens(), canary], run);
    expect(result.leaks).toEqual([path.join("e2e", ".runtime", "stacks", "sentinel-browser-test", "api.log")]);
    expect(result.problems).toEqual([]);
    expect(JSON.stringify(result)).not.toContain(canary);
    expect(result.files).toBe(3);
  });

  it("also searches the stack's own secret file for a document token", () => {
    const [first, second] = tokens();
    writeFileSync(run.secretsPath, JSON.stringify({ runId: "r", secrets: ["stack-secret-value-xyz"], copied: second }));
    const result = scanForTokens([first, second], run);
    expect(result.leaks).toEqual([path.join("e2e", ".runtime", "owned-secrets.json")]);
  });

  it("finds a copy in test results and nested stack directories, and nothing when clean", () => {
    const [first, second] = tokens();
    mkdirSync(path.join(run.stackDir, "pg", "log"), { recursive: true });
    writeFileSync(path.join(run.stackDir, "pg", "log", "postgres.log"), `statement: ${first}`);
    writeFileSync(path.join(run.webRoot, "test-results", "trace.txt"), second);
    expect(scanForTokens([first, second], run).leaks.sort()).toEqual(
      [path.join("e2e", ".runtime", "stacks", "sentinel-browser-test", "pg", "log", "postgres.log"), path.join("test-results", "trace.txt")].sort(),
    );
    rmSync(path.join(run.stackDir, "pg"), { recursive: true });
    rmSync(path.join(run.webRoot, "test-results", "trace.txt"));
    expect(scanForTokens([first, second], run)).toMatchObject({ leaks: [], problems: [] });
  });

  it("reports a link it will not follow as a problem, by relative name", () => {
    const target = path.join(base, "outside");
    mkdirSync(target);
    symlinkSync(target, path.join(run.stackDir, "linked"), "junction");
    const result = scanForTokens(tokens(), run);
    expect(result.problems).toEqual([`link:${path.join("e2e", ".runtime", "stacks", "sentinel-browser-test", "linked")}`]);
  });

  it("refuses to run without the document tokens", () => {
    expect(() => scanForTokens([], run)).toThrow("scan_secrets_missing");
    expect(() => scanForTokens(["short"], run)).toThrow("scan_secrets_missing");
  });
});
