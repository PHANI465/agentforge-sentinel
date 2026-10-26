import { createHash, randomBytes } from "node:crypto";
import { mkdtempSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

const dsnPattern = /postgresql:\/\/\S+/gi;

function occurrences(haystack, needle) {
  if (!needle) return 0;
  let count = 0;
  let from = 0;
  while (from <= haystack.length) {
    const at = haystack.indexOf(needle, from);
    if (at < 0) return count;
    count += 1;
    from = at + needle.length;
  }
  return count;
}

function excluded(full, roots) {
  const resolved = path.resolve(full);
  for (const root of roots) {
    const target = path.resolve(root);
    if (resolved === target || resolved.startsWith(target + path.sep)) return true;
  }
  return false;
}

export function scanTree(root, secrets, exclude = []) {
  let files = 0;
  let hits = 0;
  const pending = [root];
  const roots = exclude.filter((item) => typeof item === "string" && item.length > 0);
  while (pending.length > 0) {
    const current = pending.pop();
    if (excluded(current, roots)) continue;
    let entries;
    try {
      entries = readdirSync(current, { withFileTypes: true });
    } catch {
      return { files, hits, error: "unreadable" };
    }
    for (const entry of entries) {
      const full = path.join(current, entry.name);
      if (excluded(full, roots)) continue;
      if (entry.isSymbolicLink()) return { files, hits, error: "unknown" };
      if (entry.isDirectory()) {
        pending.push(full);
        continue;
      }
      if (!entry.isFile()) return { files, hits, error: "unknown" };
      files += 1;
      let text;
      try {
        text = readFileSync(full).toString("utf8");
      } catch {
        return { files, hits, error: "unreadable" };
      }
      for (const secret of secrets) hits += occurrences(text, secret);
      dsnPattern.lastIndex = 0;
      hits += (text.match(dsnPattern) || []).length;
    }
  }
  return { files, hits };
}

export function evaluateScan(request) {
  const secrets = Array.isArray(request?.secrets)
    ? request.secrets.filter((item) => typeof item === "string" && item.length > 0)
    : [];
  const dirs = Array.isArray(request?.dirs) ? request.dirs.filter((item) => typeof item === "string" && item.length > 0) : [];
  const exclude = Array.isArray(request?.exclude) ? request.exclude : [];
  if (request?.requireSecrets === true && secrets.length === 0) {
    return { result: "fail", files: 0, hits: -1, code: "secrets_unavailable" };
  }
  if (dirs.length === 0) return { result: "fail", files: 0, hits: -1, code: "unreadable" };
  let files = 0;
  let hits = 0;
  for (const dir of dirs) {
    const found = scanTree(dir, secrets, exclude);
    files += found.files;
    hits += found.hits;
    if (found.error) return { result: "fail", files, hits: -1, code: found.error };
  }
  return { result: hits === 0 ? "pass" : "fail", files, hits };
}

function report(result) {
  process.stdout.write(`${JSON.stringify(result)}\n`);
}

function selfTest() {
  const token = randomBytes(24).toString("hex");
  const dsn = `postgresql://sentinel@127.0.0.1:9/scan_${createHash("sha256").update(token).digest("hex").slice(0, 12)}`;
  const root = mkdtempSync(path.join(tmpdir(), "sentinel-scan-"));
  try {
    const clean = path.join(root, "clean");
    const dirty = path.join(root, "dirty");
    const nested = path.join(root, "nested", "stacks");
    mkdirSync(clean);
    mkdirSync(dirty);
    mkdirSync(nested, { recursive: true });
    writeFileSync(path.join(clean, "error-context.md"), "Error: artifact probe\nheading: Case queue\n");
    writeFileSync(path.join(dirty, "error-context.md"), `Error: artifact probe\n${token}\n${dsn}\n`);
    writeFileSync(path.join(nested, "error-context.md"), `${token}\n`);
    writeFileSync(path.join(root, "not-a-directory.txt"), "plain\n");
    const cleanResult = scanTree(clean, [token, dsn]);
    const dirtyResult = scanTree(dirty, [token, dsn]);
    const stacksResult = scanTree(path.join(root, "nested"), [token, dsn]);
    const unreadable = evaluateScan({ dirs: [path.join(root, "not-a-directory.txt")], secrets: [token], requireSecrets: true });
    const missingSecrets = evaluateScan({ dirs: [clean], secrets: [], requireSecrets: true });
    const pass =
      cleanResult.hits === 0 &&
      dirtyResult.hits >= 2 &&
      cleanResult.files === 1 &&
      dirtyResult.files === 1 &&
      stacksResult.hits > 0 &&
      unreadable.result === "fail" &&
      unreadable.code === "unreadable" &&
      missingSecrets.result === "fail" &&
      missingSecrets.code === "secrets_unavailable";
    report({
      result: pass ? "pass" : "fail",
      clean_files: cleanResult.files,
      clean_hits: cleanResult.hits,
      dirty_files: dirtyResult.files,
      dirty_hits: dirtyResult.hits,
      stacks_hits: stacksResult.hits,
      unreadable: unreadable.code ?? unreadable.result,
      missing_secrets: missingSecrets.code ?? missingSecrets.result,
    });
    return pass ? 0 : 1;
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
}

function finishSelfTest() {
  process.exit(selfTest());
}

function stdinScan() {
  let request;
  try {
    request = JSON.parse(readFileSync(0, "utf8"));
  } catch {
    report({ result: "fail", files: 0, hits: -1, code: "unreadable" });
    process.exit(1);
  }
  const result = evaluateScan(request);
  report(result);
  process.exit(result.result === "pass" && result.hits === 0 ? 0 : 1);
}

if (process.argv.includes("--self-test")) finishSelfTest();
else if (process.argv[1] && process.argv[1].endsWith("scan-artifacts.mjs")) stdinScan();
