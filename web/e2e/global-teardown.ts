import { spawnSync } from "node:child_process";
import { existsSync, lstatSync, readdirSync, readFileSync, rmdirSync, rmSync } from "node:fs";
import net from "node:net";
import path from "node:path";
import { webRoot, readRuntime, runtimeDir, type RuntimeFile } from "./support/runtime";

type StopReport = {
  ok?: boolean;
  state_removed?: boolean;
  errors?: string[];
};

function commandLine(pid: number): string {
  const result = spawnSync(
    "powershell",
    ["-NoProfile", "-Command", `(Get-CimInstance Win32_Process -Filter "ProcessId=${pid}").CommandLine`],
    { encoding: "utf8", windowsHide: true },
  );
  return result.stdout || "";
}

function pidAlive(pid: number): boolean {
  const result = spawnSync("tasklist", ["/FI", `PID eq ${pid}`, "/FO", "CSV", "/NH"], {
    encoding: "utf8",
    windowsHide: true,
  });
  return (result.stdout || "").includes(`"${pid}"`);
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

function stopStack(manifestPath: string): StopReport {
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
  if (result.error || !result.stdout) return { ok: false, errors: ["stop command failed"] };
  try {
    return JSON.parse(result.stdout) as StopReport;
  } catch {
    return { ok: false, errors: [sanitize(result.stdout).slice(0, 200)] };
  }
}

function secretsFrom(manifestPath: string): string[] {
  if (!existsSync(manifestPath)) return [];
  const manifest = JSON.parse(readFileSync(manifestPath, "utf8")) as {
    tokens?: Record<string, string>;
    database_url?: string;
  };
  return [...Object.values(manifest.tokens ?? {}), manifest.database_url ?? ""].filter((item) => item.length > 0);
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

function scan(secrets: string[]): { result: string; files: number; hits: number } {
  const result = spawnSync(process.execPath, [path.join(webRoot, "e2e", "support", "scan-artifacts.mjs")], {
    cwd: webRoot,
    encoding: "utf8",
    windowsHide: true,
    input: JSON.stringify({
      secrets,
      dirs: [path.join(webRoot, "test-results"), runtimeDir],
    }),
  });
  if (!result.stdout) return { result: "fail", files: 0, hits: -1 };
  return JSON.parse(result.stdout) as { result: string; files: number; hits: number };
}

export default async function globalTeardown(): Promise<void> {
  try {
    await stopOwnedStack();
  } finally {
    rmSync(path.join(runtimeDir, "vite-port.txt"), { force: true });
  }
}

async function stopOwnedStack(): Promise<void> {
  let runtime: RuntimeFile;
  try {
    runtime = readRuntime();
  } catch {
    return;
  }
  const manifestPath = runtime.manifestPath;
  const secrets = secretsFrom(manifestPath);
  let manifest: { api?: { port?: number; pid?: number }; database?: { port?: number }; state_dir?: string } = {};
  if (existsSync(manifestPath)) {
    try {
      manifest = JSON.parse(readFileSync(manifestPath, "utf8")) as typeof manifest;
    } catch {
      manifest = {};
    }
  }
  const apiPort = manifest.api?.port;
  const dbPort = manifest.database?.port;
  const apiPid = manifest.api?.pid;
  const stackDir = manifest.state_dir ?? path.dirname(manifestPath);
  const stop = existsSync(manifestPath) ? stopStack(manifestPath) : { ok: true, state_removed: true, errors: [] };
  const apiClosed = apiPort ? await waitClosed(apiPort) : true;
  const dbClosed = dbPort ? await waitClosed(dbPort) : true;
  const apiGone = apiPid ? !pidAlive(apiPid) : true;
  const emptyRemoved = !existsSync(stackDir) ? false : removeVerifiedEmpty(stackDir, path.dirname(stackDir));
  if (runtime.vitePid && pidAlive(runtime.vitePid) && commandLine(runtime.vitePid).includes("vite.js")) {
    spawnSync("taskkill", ["/PID", String(runtime.vitePid), "/T", "/F"], { windowsHide: true });
  }
  const scanned = scan(secrets);
  const problems: string[] = [];
  if (!stop.ok) problems.push(`stop incomplete: ${sanitize((stop.errors ?? []).join("; "))}`);
  if (!apiClosed || !dbClosed) problems.push("owned API or database port still accepts connections");
  if (!apiGone) problems.push("owned API process still running");
  if (existsSync(manifestPath)) problems.push("private manifest still present");
  if (scanned.result !== "pass" || scanned.hits !== 0) {
    problems.push(`credential scan ${scanned.result} files=${scanned.files} hits=${scanned.hits}`);
  }
  if (emptyRemoved) problems.push("removed one verified empty owned stack directory");
  const hard = problems.filter((item) => !item.startsWith("removed one verified"));
  if (hard.length > 0) throw new Error(hard.join("; "));
}
