import { spawn, spawnSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const repoRoot = path.resolve(webRoot, "..");
const runtimeDir = path.join(webRoot, "e2e", ".runtime");
const runtimePath = path.join(runtimeDir, "runtime.json");

const portFlag = process.argv.indexOf("--port");
const port = Number(process.argv[portFlag + 1]);
if (!Number.isInteger(port) || port < 1 || port > 65535) {
  process.stderr.write("vite port missing\n");
  process.exit(1);
}

const childEnv = { ...process.env, SENTINEL_LIVE_CLAUDE: "0" };
delete childEnv.VIRTUAL_ENV;

let manifestPath = "";
let vite = null;
let shuttingDown = false;

function redact(text) {
  return text.replace(/postgresql:\/\/\S+/gi, "[dsn]").replace(/Bearer\s+\S+/gi, "Bearer [redacted]");
}

function runStack(args) {
  return spawnSync(
    "uv",
    ["run", "--locked", "python", "tests/support/browser_stack.py", ...args],
    { cwd: repoRoot, encoding: "utf8", windowsHide: true, env: childEnv, timeout: 180_000 },
  );
}

function stopStack() {
  if (!manifestPath) return;
  runStack(["stop", "--manifest", manifestPath]);
}

function killVite() {
  if (!vite?.pid) return;
  spawnSync("taskkill", ["/PID", String(vite.pid), "/T", "/F"], { windowsHide: true });
}

function shutdown(code) {
  if (shuttingDown) return;
  shuttingDown = true;
  killVite();
  stopStack();
  process.exit(code);
}

function startStack() {
  mkdirSync(path.join(runtimeDir, "stacks"), { recursive: true });
  const started = runStack(["start", "--parent-dir", path.join(runtimeDir, "stacks"), "--timeout", "90"]);
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
  return apiOrigin;
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
  const apiOrigin = startStack();
  const baseURL = `http://127.0.0.1:${port}`;
  vite = spawn(process.execPath, [path.join(webRoot, "node_modules", "vite", "bin", "vite.js"), "--host", "127.0.0.1", "--port", String(port), "--strictPort"], {
    cwd: webRoot,
    env: { ...childEnv, SENTINEL_API_ORIGIN: apiOrigin, BROWSER: "none" },
    stdio: ["ignore", "ignore", "pipe"],
    windowsHide: true,
  });
  let viteError = "";
  vite.stderr?.on("data", (chunk) => {
    viteError = `${viteError}${chunk.toString()}`.slice(-2000);
  });
  writeFileSync(runtimePath, `${JSON.stringify({ manifestPath, baseURL, apiOrigin, vitePid: vite.pid }, null, 2)}\n`);
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
