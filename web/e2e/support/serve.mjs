import { spawn, spawnSync } from "node:child_process";
import { mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { existsSync } from "node:fs";
import {
  commandHasScript,
  executeViteAction,
  interpretStop,
  planChildShutdown,
  queryProcess,
  recoveryDocument,
} from "./process-identity.mjs";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const repoRoot = path.resolve(webRoot, "..");
const runtimeDir = path.join(webRoot, "e2e", ".runtime");
const runtimePath = path.join(runtimeDir, "runtime.json");
const secretsPath = path.join(runtimeDir, "owned-secrets.json");
const viteScript = path.join(webRoot, "node_modules", "vite", "bin", "vite.js");

const portFlag = process.argv.indexOf("--port");
const port = Number(process.argv[portFlag + 1]);
const runFlag = process.argv.indexOf("--run-id");
const runId = process.argv[runFlag + 1] ?? "";
if (!Number.isInteger(port) || port < 1 || port > 65535 || !/^[0-9a-f]{32}$/.test(runId)) {
  process.stderr.write("browser run identity missing\n");
  process.exit(1);
}

const childEnv = { ...process.env, SENTINEL_LIVE_CLAUDE: "0" };
delete childEnv.VIRTUAL_ENV;
delete childEnv.SENTINEL_TEST_DATABASE_URL;

let manifestPath = "";
let stackDir = "";
let vite = null;
let viteIdentity = null;
let shuttingDown = false;

function redact(text) {
  return text.replace(/postgresql:\/\/\S+/gi, "[dsn]").replace(/Bearer\s+\S+/gi, "Bearer [redacted]");
}

function runCommand(command, args, extra = {}) {
  return spawnSync(command, args, { encoding: "utf8", windowsHide: true, ...extra });
}

function runStack(args, timeout = 180_000) {
  return runCommand(
    "uv",
    ["run", "--locked", "--extra", "dev", "--extra", "ml", "python", "tests/support/browser_stack.py", ...args],
    {
      cwd: repoRoot,
      env: childEnv,
      timeout,
    },
  );
}

function preservePrevious(current, previous) {
  if (!existsSync(current)) return;
  try {
    const parsed = JSON.parse(readFileSync(current, "utf8"));
    if (parsed.runId === runId) return;
  } catch {
    // An unreadable leftover is still not this run's authority.
  }
  renameSync(current, previous);
}

function rememberSecrets(manifest) {
  const secrets = [...Object.values(manifest.tokens ?? {}), manifest.database_url ?? ""].filter(
    (item) => typeof item === "string" && item.length > 0,
  );
  if (secrets.length === 0) throw new Error("stack did not provide verification secrets");
  preservePrevious(secretsPath, path.join(runtimeDir, "owned-secrets.previous.json"));
  writeFileSync(secretsPath, `${JSON.stringify({ runId, secrets })}\n`, { mode: 0o600 });
}

function captureProcess(pid) {
  const deadline = Date.now() + 5_000;
  while (Date.now() < deadline) {
    const observed = queryProcess(pid, runCommand);
    if (observed.available && observed.found) {
      return {
        pid,
        creation: observed.creation,
        executable: observed.executable,
        commandLine: observed.commandLine,
      };
    }
    Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 100);
  }
  return null;
}

function stopStack() {
  if (!manifestPath) return interpretStop(null);
  const result = runStack(["stop", "--manifest", manifestPath]);
  if (result.error || result.status !== 0 || !result.stdout) return interpretStop(null);
  try {
    return interpretStop(JSON.parse(result.stdout));
  } catch {
    return interpretStop(null);
  }
}

function killVite() {
  if (!vite || vite.exitCode !== null || !vite.pid) return { killed: false, reason: "child_exited" };
  if (!viteIdentity?.creation || !viteIdentity.commandLine || !viteIdentity.executable || !viteIdentity.script) {
    return { killed: false, reason: "identity_unavailable" };
  }
  const decision = planChildShutdown({
    childExited: false,
    expected: viteIdentity,
    observed: queryProcess(vite.pid, runCommand),
  });
  return executeViteAction(decision, runCommand);
}

function writeRecovery(reasons) {
  const recoveryPath = path.join(runtimeDir, "recovery.json");
  const previous = path.join(runtimeDir, "recovery.previous.json");
  if (existsSync(recoveryPath)) {
    try {
      const existing = JSON.parse(readFileSync(recoveryPath, "utf8"));
      if (existing.runId !== runId) renameSync(recoveryPath, previous);
    } catch {
      renameSync(recoveryPath, previous);
    }
  }
  writeFileSync(
    recoveryPath,
    `${JSON.stringify(recoveryDocument({ runId, reasons, manifestPath, vitePid: vite?.pid, stackDir }))}\n`,
  );
}

function shutdown(code) {
  if (shuttingDown) return;
  shuttingDown = true;
  const reasons = [];
  if (vite) {
    const killed = killVite();
    if (killed.reason === "taskkill_failed" || killed.reason.endsWith("_mismatch") || killed.reason.startsWith("identity_")) {
      reasons.push(killed.reason);
    }
  }
  if (manifestPath) {
    const stopped = stopStack();
    if (!stopped.success) reasons.push(stopped.reason);
  }
  if (reasons.length > 0) {
    writeRecovery(reasons);
    process.exit(code === 0 ? 1 : code);
  }
  process.exit(code);
}

function startStack() {
  mkdirSync(path.join(runtimeDir, "stacks"), { recursive: true });
  const started = runStack(
    ["start", "--parent-dir", path.join(runtimeDir, "stacks"), "--timeout", "120", "--scorer", "rule", "--model-fixtures"],
    300_000,
  );
  if (started.error || started.status !== 0) {
    writeFileSync(path.join(runtimeDir, "last-command.txt"), redact(`${started.stderr || ""}\n${started.stdout || ""}`));
    throw new Error("browser stack failed to start");
  }
  let apiOrigin = "";
  for (const line of started.stdout.split(/\r?\n/)) {
    if (line.startsWith("SENTINEL_STACK_MANIFEST=")) {
      manifestPath = line.slice("SENTINEL_STACK_MANIFEST=".length).trim();
    }
    if (line.startsWith("base_url=")) apiOrigin = line.slice("base_url=".length).trim().split(/\s+/)[0];
  }
  if (!manifestPath || !apiOrigin.startsWith("http://127.0.0.1:")) {
    throw new Error("browser stack did not report a loopback API");
  }
  const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
  stackDir = String(manifest.state_dir ?? "");
  rememberSecrets(manifest);
  return { apiOrigin, manifest };
}

async function waitForVite(url) {
  const deadline = Date.now() + 60_000;
  while (Date.now() < deadline) {
    if (vite?.exitCode !== null) throw new Error("vite exited before it listened");
    try {
      const response = await fetch(url);
      if (response.status < 500) return;
    } catch {
      // The listener is not up yet.
    }
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  throw new Error("vite did not listen");
}

process.on("SIGTERM", () => shutdown(0));
process.on("SIGINT", () => shutdown(0));

try {
  const { apiOrigin, manifest } = startStack();
  const baseURL = `http://127.0.0.1:${port}`;
  vite = spawn(
    process.execPath,
    [viteScript, "--host", "127.0.0.1", "--port", String(port), "--strictPort"],
    {
      cwd: webRoot,
      env: { ...childEnv, SENTINEL_API_ORIGIN: apiOrigin, BROWSER: "none" },
      stdio: ["ignore", "ignore", "pipe"],
      windowsHide: true,
    },
  );
  let viteError = "";
  vite.stderr?.on("data", (chunk) => {
    viteError = `${viteError}${chunk.toString()}`.slice(-2000);
  });
  const capturedVite = vite.pid ? captureProcess(vite.pid) : null;
  viteIdentity = capturedVite && commandHasScript(capturedVite.commandLine, viteScript) ? { ...capturedVite, script: viteScript } : null;
  const apiPid = manifest.api?.pid;
  const apiIdentity = Number.isInteger(apiPid) ? captureProcess(apiPid) : null;
  if (!viteIdentity || !apiIdentity || !stackDir || !Number.isInteger(manifest.api?.port) || !Number.isInteger(manifest.database?.port)) {
    throw new Error("owned process identity unavailable");
  }
  preservePrevious(runtimePath, path.join(runtimeDir, "runtime.previous.json"));
  writeFileSync(
    runtimePath,
    `${JSON.stringify({
      runId,
      manifestPath,
      stackDir,
      secretsPath,
      baseURL,
      apiOrigin,
      api: { pid: apiIdentity.pid, port: manifest.api.port, creation: apiIdentity.creation, executable: apiIdentity.executable, commandLine: apiIdentity.commandLine },
      database: { port: manifest.database.port },
      vite: viteIdentity,
    }, null, 2)}\n`,
  );
  try {
    await waitForVite(`${baseURL}/`);
  } catch (error) {
    writeFileSync(path.join(runtimeDir, "last-command.txt"), redact(viteError));
    throw error;
  }
  await new Promise((resolve) => {
    vite?.on("exit", () => resolve());
  });
  shutdown(vite?.exitCode && vite.exitCode !== 0 ? vite.exitCode : 0);
} catch (error) {
  const message = error instanceof Error ? error.message : "browser stack failed";
  process.stderr.write(`${message}\n`);
  shutdown(1);
}
