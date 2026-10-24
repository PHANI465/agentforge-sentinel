import { defineConfig } from "@playwright/test";
import { spawnSync } from "node:child_process";
import { closeSync, existsSync, mkdirSync, openSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const runtimeDir = path.join(path.dirname(fileURLToPath(import.meta.url)), "e2e", ".runtime");
const portFile = path.join(runtimeDir, "vite-port.txt");

function freePort(): number {
  const result = spawnSync(
    process.execPath,
    [
      "-e",
      "const net=require('net'); const server=net.createServer(); server.listen(0,'127.0.0.1',()=>{ process.stdout.write(String(server.address().port)); server.close(); });",
    ],
    { encoding: "utf8", windowsHide: true },
  );
  const port = Number(result.stdout.trim());
  if (!Number.isInteger(port) || port < 1) throw new Error("no free port");
  return port;
}

function chosenPort(): number {
  mkdirSync(runtimeDir, { recursive: true });
  try {
    const fd = openSync(portFile, "wx");
    try {
      const port = freePort();
      writeFileSync(fd, String(port));
      return port;
    } finally {
      closeSync(fd);
    }
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "EEXIST") throw error;
    const deadline = Date.now() + 2_000;
    while (Date.now() < deadline) {
      if (!existsSync(portFile)) continue;
      const port = Number(readFileSync(portFile, "utf8").trim());
      if (Number.isInteger(port) && port > 0) return port;
    }
    throw new Error("vite port was not recorded");
  }
}

const port = chosenPort();
const baseURL = `http://127.0.0.1:${port}`;

export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/*.pw.ts",
  fullyParallel: false,
  workers: 1,
  forbidOnly: true,
  retries: 0,
  timeout: 120_000,
  expect: { timeout: 20_000 },
  outputDir: "test-results",
  reporter: "line",
  globalTeardown: "./e2e/global-teardown.ts",
  use: {
    baseURL,
    trace: "off",
    video: "off",
    screenshot: "off",
  },
  webServer: {
    command: `node e2e/support/serve.mjs --port ${port}`,
    url: `${baseURL}/`,
    timeout: 180_000,
    reuseExistingServer: false,
    stdout: "pipe",
    stderr: "pipe",
  },
});
