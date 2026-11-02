import { spawnSync } from "node:child_process";
import { createRequire } from "node:module";
import { EventEmitter } from "node:events";
import { readFileSync } from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath, pathToFileURL } from "node:url";
import { planInvocation } from "./launch.mjs";

if (!process.execArgv.includes("--experimental-vm-modules")) {
  const rerun = spawnSync(process.execPath, ["--experimental-vm-modules", ...process.argv.slice(1)], {
    stdio: "inherit",
    windowsHide: true,
  });
  process.exit(rerun.status ?? 1);
}

const web = path.resolve(path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1")), "../..");
const require = createRequire(path.join(web, "package.json"));
const esbuild = require("esbuild");
const entry = path.join(web, "e2e", "support", "serve.mjs");
const viteScript = path.join(web, "node_modules", "vite", "bin", "vite.js");
const runId = "1".repeat(32);
const manifestPath = "E:/SYNTHETIC-OWNED/sentinel-browser-probe/manifest.json";
const bearer = "SYNTHETIC-BEARER-CANARY";
const dsn = "SYNTHETIC-DSN";
const creation = "2026-10-24T16:00:00.000Z";
const executable = "C:/Program Files/nodejs/node.exe";
const ownedCommand = `"${executable}" ${viteScript} --host 127.0.0.1 --port 45000 --strictPort`;
const foreignCommand = `"${executable}" E:/ANOTHER-WORKSPACE/node_modules/vite/bin/vite.js --port 49001`;
const names = [];

function check(name, value) {
  names.push(name);
  if (!value) throw new Error(name);
}

function identityJson(commandLine, stamp = creation) {
  return JSON.stringify({ found: true, creation: stamp, executable, commandLine });
}

async function runServe(mode) {
  const calls = [];
  const written = new Map();
  let queries = 0;
  let clock = 0;
  class FastDate extends Date {
    static now() {
      clock += 1_000;
      return clock;
    }
  }
  const child = new EventEmitter();
  child.pid = 424242;
  child.exitCode = null;
  child.stderr = new EventEmitter();
  const fakeProcess = {
    argv: ["node", entry, "--port", "45000", "--run-id", runId],
    env: {},
    execPath: process.execPath,
    on() {},
    stderr: { write() {} },
    exit(code) {
      const error = new Error("intercepted exit");
      error.name = "ProbeExit";
      error.code = code;
      throw error;
    },
  };
  const childProcess = {
    spawn() {
      return child;
    },
    spawnSync(command, args) {
      calls.push(command);
      if (command === "uv" && args.includes("start")) {
        return { status: 0, stdout: `SENTINEL_STACK_MANIFEST=${manifestPath}\nbase_url=http://127.0.0.1:45001\n` };
      }
      if (command === "uv" && args.includes("stop")) return { status: 0, stdout: "{\"ok\":true}" };
      if (command === "powershell") {
        queries += 1;
        if (mode === "missing") return { status: 1, stdout: "" };
        if (queries <= 2) return { status: 0, stdout: identityJson(ownedCommand) };
        if (mode === "foreign") return { status: 0, stdout: identityJson(foreignCommand) };
        if (mode === "reused") return { status: 0, stdout: identityJson(ownedCommand, "2026-10-24T18:00:00.000Z") };
        return { status: 0, stdout: identityJson(ownedCommand) };
      }
      if (command === "taskkill") return { status: 0, stdout: "" };
      throw new Error("unexpected process request");
    },
  };
  const fakeFs = {
    mkdirSync() {},
    existsSync(file) {
      return written.has(String(file));
    },
    readFileSync(file) {
      if (String(file) === manifestPath) {
        return JSON.stringify({
          tokens: { analyst: bearer },
          database_url: dsn,
          state_dir: "E:/SYNTHETIC-OWNED/sentinel-browser-probe",
          api: { pid: 434343, port: 45001 },
          database: { port: 45002 },
        });
      }
      return written.get(String(file));
    },
    writeFileSync(file, value) {
      written.set(String(file), String(value));
    },
    renameSync(from, to) {
      written.set(String(to), written.get(String(from)));
      written.delete(String(from));
    },
  };
  const context = vm.createContext({
    process: fakeProcess,
    Date: FastDate,
    console,
    setTimeout(fn) {
      if (mode === "exited") child.exitCode = 0;
      fn();
      return 0;
    },
    clearTimeout() {},
    fetch() {
      throw new Error("vite listener intercepted");
    },
    SharedArrayBuffer,
    Int32Array,
    Atomics: { wait() {} },
  });
  const identity = new vm.SourceTextModule(readFileSync(path.join(web, "e2e", "support", "process-identity.mjs"), "utf8"), { context });
  const suite = new vm.SourceTextModule(readFileSync(path.join(web, "e2e", "support", "suite.mjs"), "utf8"), { context });
  const modules = new Map();
  function synth(key, values) {
    if (modules.has(key)) return modules.get(key);
    const exported = Object.keys(values);
    const module = new vm.SyntheticModule(exported, function exportValues() {
      for (const name of exported) this.setExport(name, values[name]);
    }, { context });
    modules.set(key, module);
    return module;
  }
  const main = new vm.SourceTextModule(readFileSync(entry, "utf8"), {
    context,
    initializeImportMeta(meta) {
      meta.url = pathToFileURL(entry).href;
    },
  });
  await main.link((specifier) => {
    if (specifier === "node:child_process") return synth(specifier, childProcess);
    if (specifier === "node:fs") return synth(specifier, fakeFs);
    if (specifier === "node:path") return synth(specifier, { default: path });
    if (specifier === "node:url") return synth(specifier, { fileURLToPath: pathToFileURL && ((value) => require("node:url").fileURLToPath(value)) });
    if (specifier === "./process-identity.mjs") return identity;
    if (specifier === "./suite.mjs") return suite;
    throw new Error(`unexpected module ${specifier}`);
  });
  try {
    await main.evaluate();
  } catch (error) {
    if (error.name !== "ProbeExit") throw error;
  }
  const recovery = [...written.entries()].find(([file]) => String(file).endsWith("recovery.json"));
  return {
    kills: calls.filter((command) => command === "taskkill").length,
    stops: calls.filter((command) => command === "uv").length,
    recovery: recovery ? recovery[1] : "",
  };
}

function chosenRunSource() {
  const config = readFileSync(path.join(web, "playwright.config.ts"), "utf8");
  const start = config.indexOf("function chosenRun()");
  const end = config.indexOf("\nconst port =", start);
  if (start < 0 || end < 0) throw new Error("chosen_run_missing");
  return esbuild.transformSync(config.slice(start, end), { loader: "ts", format: "cjs" }).code;
}

function callChosenRun({ env, files, open }) {
  const calls = [];
  const writes = [];
  const context = vm.createContext({
    runtimeDir: "E:/SYNTHETIC-RUNTIME",
    path,
    process: { env },
    mkdirSync() {},
    existsSync(file) {
      return Object.prototype.hasOwnProperty.call(files, path.basename(String(file)));
    },
    openSync() {
      if (open === "exists") {
        const error = new Error("exists");
        error.code = "EEXIST";
        throw error;
      }
      return 1;
    },
    readFileSync(file) {
      return files[path.basename(String(file))] ?? "";
    },
    closeSync() {},
    writeFileSync(_file, value) {
      writes.push(String(value));
    },
    randomBytes() {
      throw new Error("new identity was not generated");
    },
    spawnSync(command) {
      calls.push(command);
      throw new Error("destructive command");
    },
  });
  let thrown = "";
  let value = "";
  try {
    value = String(new vm.Script(`${chosenRunSource()}\nchosenRun();`).runInContext(context) ?? "");
  } catch (error) {
    thrown = error instanceof Error ? error.message : "thrown";
  }
  return { value, thrown, writes, calls };
}

const missing = await runServe("missing");
check("missing_identity_sends_no_taskkill", missing.kills === 0);
check("missing_identity_keeps_recovery", missing.recovery.includes("identity_unavailable") && missing.recovery.includes("424242"));
check("missing_identity_recovery_has_no_secret", !missing.recovery.includes(bearer) && !missing.recovery.includes(dsn));

const owned = await runServe("owned");
check("owned_identity_allows_exact_cleanup", owned.kills === 1);

const exited = await runServe("exited");
check("exited_child_is_not_killed", exited.kills === 0);

const foreign = await runServe("foreign");
check("foreign_process_is_not_killed", foreign.kills === 0 && foreign.recovery.includes("command_mismatch"));

const reused = await runServe("reused");
check("reused_pid_is_not_killed", reused.kills === 0 && reused.recovery.includes("creation_mismatch"));

const staleRun = "a".repeat(32);
const adopted = callChosenRun({
  env: {},
  files: { "current-run.json": JSON.stringify({ runId: staleRun }) },
  open: "exists",
});
check("stale_run_file_is_not_adopted", adopted.value !== staleRun && adopted.calls.length === 0 && adopted.writes.length === 0);

const mismatched = callChosenRun({
  env: { SENTINEL_E2E_RUN_ID: runId },
  files: {
    "current-run.json": JSON.stringify({ runId: staleRun }),
    "runtime.json": JSON.stringify({ runId: staleRun, manifestPath }),
    "recovery.json": JSON.stringify({ runId: staleRun, vitePid: 424242 }),
  },
  open: "exists",
});
check(
  "stale_state_does_not_authorize_cleanup",
  mismatched.value !== staleRun && mismatched.value !== runId && mismatched.calls.length === 0 && mismatched.writes.length === 0,
);

const shared = callChosenRun({
  env: { SENTINEL_E2E_RUN_ID: runId },
  files: { "current-run.json": JSON.stringify({ runId }) },
  open: "exists",
});
check("workers_share_invocation_identity", shared.value === runId && shared.calls.length === 0);

const blocked = planInvocation("E:/SYNTHETIC-RUNTIME", (file) => String(file).endsWith("recovery.json") || String(file).endsWith("runtime.json"));
check("launcher_preserves_stale_state", blocked.start === false && blocked.reason === "stale_run_needs_recovery" && blocked.preserved.length === 2);
const fresh = planInvocation("E:/SYNTHETIC-RUNTIME", () => false);
check("launcher_starts_only_without_stale_state", fresh.start === true && /^[0-9a-f]{32}$/.test(fresh.runId ?? ""));

process.stdout.write(`${JSON.stringify({ result: "pass", checks: names.length })}\n`);
