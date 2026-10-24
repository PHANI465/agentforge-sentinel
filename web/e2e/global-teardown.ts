import { spawnSync } from "node:child_process";
import { existsSync, lstatSync, readdirSync, readFileSync, rmdirSync, rmSync, writeFileSync } from "node:fs";
import net from "node:net";
import path from "node:path";
import { executeViteAction, interpretStop, planChildShutdown, queryProcess, recoveryDocument, runAuthority } from "./support/process-identity.mjs";
import { failureProbeMarker, readRuntime, runtimeDir, runtimePath, webRoot, type RuntimeFile } from "./support/runtime";

type StopReport = { ok?: boolean; errors?: string[] };
type ScanReport = { result: string; files: number; hits: number; code?: string };

function run(command: string, args: string[]) {
  const result = spawnSync(command, args, { encoding: "utf8", windowsHide: true });
  return { status: result.status, stdout: result.stdout ?? "" };
}

function portOpen(port: number): Promise<boolean> {
  return new Promise((resolve) => {
    const socket = net.connect({ host: "127.0.0.1", port });
    const finish = (open: boolean) => {
      socket.removeAllListeners();
      socket.destroy();
      resolve(open);
    };
    socket.once("connect", () => finish(true));
    socket.once("error", () => finish(false));
    socket.setTimeout(1000, () => finish(false));
  });
}

async function waitClosed(port: number): Promise<boolean> {
  const deadline = Date.now() + 8_000;
  while (Date.now() < deadline) {
    if (!(await portOpen(port))) return true;
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  return !(await portOpen(port));
}

function sanitize(text: string): string {
  return text.replace(/postgresql:\/\/\S+/gi, "[dsn]").replace(/Bearer\s+\S+/gi, "Bearer [redacted]");
}

function stopStack(manifestPath: string): StopReport | null {
  const result = spawnSync(
    "uv",
    ["run", "--locked", "python", "tests/support/browser_stack.py", "stop", "--manifest", manifestPath],
    {
      cwd: path.resolve(webRoot, ".."),
      encoding: "utf8",
      windowsHide: true,
      env: (() => {
        const env: NodeJS.ProcessEnv = { ...process.env, SENTINEL_LIVE_CLAUDE: "0" };
        delete env.VIRTUAL_ENV;
        return env;
      })(),
      timeout: 180_000,
    },
  );
  if (result.error || result.status !== 0 || !result.stdout) return null;
  try {
    return JSON.parse(result.stdout) as StopReport;
  } catch {
    return null;
  }
}

function readJson(file: string): unknown {
  return JSON.parse(readFileSync(file, "utf8"));
}

function currentRunId(): string {
  const parsed = readJson(path.join(runtimeDir, "current-run.json")) as { runId?: unknown };
  return typeof parsed.runId === "string" ? parsed.runId : "";
}

function retainedSecrets(file: string, runId: string): string[] | null {
  try {
    const parsed = readJson(file) as { runId?: unknown; secrets?: unknown };
    if (parsed.runId !== runId || !Array.isArray(parsed.secrets)) return null;
    const secrets = parsed.secrets.filter((item): item is string => typeof item === "string" && item.length > 0);
    return secrets.length === parsed.secrets.length && secrets.length > 0 ? secrets : null;
  } catch {
    return null;
  }
}

function removeVerifiedEmpty(stackDir: string, parentDir: string): boolean {
  if (!existsSync(stackDir)) return false;
  const info = lstatSync(stackDir);
  if (info.isSymbolicLink()) return false;
  const resolved = path.resolve(stackDir);
  const parent = path.resolve(parentDir);
  if (path.dirname(resolved) !== parent) return false;
  if (!path.basename(resolved).startsWith("sentinel-browser-")) return false;
  const entries = readdirSync(resolved);
  if (entries.length > 0) return false;
  rmdirSync(resolved);
  return true;
}

function scan(secrets: string[], exclude: string[]): ScanReport {
  const result = spawnSync(process.execPath, [path.join(webRoot, "e2e", "support", "scan-artifacts.mjs")], {
    cwd: webRoot,
    encoding: "utf8",
    windowsHide: true,
    input: JSON.stringify({
      secrets,
      dirs: [path.join(webRoot, "test-results"), runtimeDir],
      exclude,
      requireSecrets: true,
    }),
  });
  if (result.status === null || !result.stdout) return { result: "fail", files: 0, hits: -1, code: "scan_failed" };
  try {
    return JSON.parse(result.stdout) as ScanReport;
  } catch {
    return { result: "fail", files: 0, hits: -1, code: "scan_unreadable" };
  }
}

function markerState(dir: string): "present" | "absent" | "unreadable" {
  if (!existsSync(dir)) return "absent";
  const pending = [dir];
  let found = false;
  while (pending.length > 0) {
    const current = pending.pop();
    if (!current) continue;
    let entries;
    try {
      entries = readdirSync(current, { withFileTypes: true });
    } catch {
      return "unreadable";
    }
    for (const entry of entries) {
      const full = path.join(current, entry.name);
      if (entry.isSymbolicLink()) return "unreadable";
      if (entry.isDirectory()) {
        pending.push(full);
        continue;
      }
      if (!entry.isFile()) return "unreadable";
      try {
        if (readFileSync(full, "utf8").includes(failureProbeMarker)) found = true;
      } catch {
        return "unreadable";
      }
    }
  }
  return found ? "present" : "absent";
}

function ownedApiStillRunning(runtime: RuntimeFile): "yes" | "no" | "unknown" {
  const api = runtime.api;
  if (!api?.pid || !api.creation || !api.commandLine || !api.executable) return "unknown";
  const observed = queryProcess(api.pid, run);
  if (!observed.available) return "unknown";
  if (!observed.found || !observed.creation || !observed.executable) return "no";
  const sameProcess =
    observed.creation === api.creation &&
    observed.executable.replaceAll("/", "\\").toLowerCase() === api.executable.replaceAll("/", "\\").toLowerCase();
  return sameProcess ? "yes" : "no";
}

function preserve(runtime: RuntimeFile, reasons: string[]): void {
  const recoveryPath = path.join(runtimeDir, "recovery.json");
  if (existsSync(recoveryPath)) {
    try {
      const existing = readJson(recoveryPath) as { runId?: unknown };
      if (existing.runId !== runtime.runId) {
        writeFileSync(path.join(runtimeDir, "recovery.previous.json"), readFileSync(recoveryPath));
      }
    } catch {
      writeFileSync(path.join(runtimeDir, "recovery.previous.json"), readFileSync(recoveryPath));
    }
  }
  writeFileSync(
    recoveryPath,
    `${JSON.stringify(
      recoveryDocument({
        runId: runtime.runId,
        reasons,
        manifestPath: runtime.manifestPath,
        vitePid: runtime.vite?.pid,
        stackDir: runtime.stackDir,
      }),
    )}\n`,
  );
}

function previousStackDir(): string {
  const previous = path.join(runtimeDir, "runtime.previous.json");
  if (!existsSync(previous)) return "";
  try {
    const parsed = readJson(previous) as { stackDir?: unknown };
    return typeof parsed.stackDir === "string" ? parsed.stackDir : "";
  } catch {
    return "";
  }
}

export default async function globalTeardown(): Promise<void> {
  try {
    await stopOwnedStack();
  } finally {
    rmSync(path.join(runtimeDir, "vite-port.txt"), { force: true });
    rmSync(path.join(runtimeDir, "current-run.json"), { force: true });
  }
}

async function stopOwnedStack(): Promise<void> {
  let runId = "";
  try {
    runId = currentRunId();
  } catch {
    runId = "";
  }
  let runtime: RuntimeFile;
  try {
    runtime = readRuntime();
  } catch {
    throw new Error(runAuthority(runId, undefined).reason);
  }
  const auth = runAuthority(runId, runtime.runId);
  if (!auth.ok) throw new Error(auth.reason);

  const secrets = retainedSecrets(runtime.secretsPath, runId);
  const problems: string[] = [];
  if (!secrets) problems.push("secrets_unavailable");
  const manifestPresent = existsSync(runtime.manifestPath);
  const stopped = manifestPresent ? interpretStop(stopStack(runtime.manifestPath)) : interpretStop({ ok: true });
  if (!stopped.success) problems.push(stopped.reason);
  const apiPort = runtime.api?.port;
  const dbPort = runtime.database?.port;
  if (!Number.isInteger(apiPort) || !Number.isInteger(dbPort)) problems.push("ports_unrecorded");
  const apiClosed = Number.isInteger(apiPort) ? await waitClosed(apiPort as number) : false;
  const dbClosed = Number.isInteger(dbPort) ? await waitClosed(dbPort as number) : false;
  if (!apiClosed || !dbClosed) problems.push("owned_ports_open");
  const apiState = ownedApiStillRunning(runtime);
  if (apiState === "yes") problems.push("owned_api_still_running");
  if (apiState === "unknown") problems.push("api_identity_unavailable");
  const emptyRemoved = existsSync(runtime.stackDir) ? removeVerifiedEmpty(runtime.stackDir, path.dirname(runtime.stackDir)) : false;
  const decision = planChildShutdown({
    childExited: false,
    expected: runtime.vite,
    observed: queryProcess(runtime.vite?.pid ?? 0, run),
  });
  const killed = executeViteAction(decision, run);
  if (decision.action === "refuse" || killed.reason === "taskkill_failed") problems.push(killed.reason);
  if (existsSync(runtime.manifestPath)) problems.push("manifest_still_present");
  const exclude = [runtime.stackDir, runtime.secretsPath, path.join(runtimeDir, "owned-secrets.previous.json"), previousStackDir()].filter(
    (item) => item.length > 0,
  );
  if (secrets) {
    const scanned = scan(secrets, exclude);
    if (scanned.result !== "pass" || scanned.hits !== 0 || scanned.code) {
      problems.push(`credential_scan ${scanned.code ?? scanned.result} files=${scanned.files} hits=${scanned.hits}`);
    }
  }
  const marker = markerState(path.join(webRoot, "test-results"));
  if (marker !== "present") problems.push(marker === "unreadable" ? "failure_artifact_unreadable" : "controlled_failure_artifact_missing");
  if (emptyRemoved) problems.push("removed_empty_owned_directory");
  const hard = problems.filter((item) => item !== "removed_empty_owned_directory");
  if (hard.length > 0) {
    preserve(runtime, hard.map((item) => sanitize(item)));
    throw new Error(hard.map((item) => sanitize(item)).join("; "));
  }
  rmSync(runtime.secretsPath, { force: true });
  rmSync(runtimePath, { force: true });
  const previousRuntime = path.join(runtimeDir, "runtime.previous.json");
  const previousDir = previousStackDir();
  if (!previousDir || !existsSync(previousDir)) rmSync(previousRuntime, { force: true });
  const recoveryPath = path.join(runtimeDir, "recovery.json");
  if (existsSync(recoveryPath)) {
    try {
      const existing = readJson(recoveryPath) as { runId?: unknown };
      if (existing.runId === runId) rmSync(recoveryPath, { force: true });
    } catch {
      // Leave an unreadable recovery file in place.
    }
  }
}
