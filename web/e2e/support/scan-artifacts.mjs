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

export function scanTree(root, secrets) {
  let files = 0;
  let hits = 0;
  const pending = [root];
  while (pending.length > 0) {
    const current = pending.pop();
    let entries = [];
    try {
      entries = readdirSync(current, { withFileTypes: true });
    } catch {
      continue;
    }
    for (const entry of entries) {
      if (entry.name === "stacks" || entry.name.startsWith("sentinel-browser-")) continue;
      const full = path.join(current, entry.name);
      if (entry.isDirectory()) {
        pending.push(full);
        continue;
      }
      if (!entry.isFile()) continue;
      files += 1;
      let text = "";
      try {
        text = readFileSync(full).toString("utf8");
      } catch {
        continue;
      }
      for (const secret of secrets) hits += occurrences(text, secret);
      dsnPattern.lastIndex = 0;
      hits += (text.match(dsnPattern) || []).length;
    }
  }
  return { files, hits };
}

function report(result) {
  process.stdout.write(`${JSON.stringify(result)}\n`);
}

function selfTest() {
  const token = randomBytes(24).toString("hex");
  const dsn = `postgresql://sentinel@127.0.0.1:9/scan_${createHash("sha256").update(token).digest("hex").slice(0, 12)}`;
  const root = mkdtempSync(path.join(tmpdir(), "sentinel-scan-"));
  const clean = path.join(root, "clean");
  const dirty = path.join(root, "dirty");
  mkdirSync(clean);
  mkdirSync(dirty);
  writeFileSync(path.join(clean, "error-context.md"), "Error: artifact probe\nheading: Case queue\n");
  writeFileSync(path.join(dirty, "error-context.md"), `Error: artifact probe\n${token}\n${dsn}\n`);
  const cleanResult = scanTree(clean, [token, dsn]);
  const dirtyResult = scanTree(dirty, [token, dsn]);
  rmSync(root, { recursive: true, force: true });
  const pass = cleanResult.hits === 0 && dirtyResult.hits >= 2 && cleanResult.files === 1 && dirtyResult.files === 1;
  report({
    result: pass ? "pass" : "fail",
    clean_files: cleanResult.files,
    clean_hits: cleanResult.hits,
    dirty_files: dirtyResult.files,
    dirty_hits: dirtyResult.hits,
  });
  process.exit(pass ? 0 : 1);
}

function stdinScan() {
  const raw = readFileSync(0, "utf8");
  const request = JSON.parse(raw);
  const secrets = Array.isArray(request.secrets) ? request.secrets.filter((item) => typeof item === "string" && item.length > 0) : [];
  const dirs = Array.isArray(request.dirs) ? request.dirs : [];
  let files = 0;
  let hits = 0;
  for (const dir of dirs) {
    const found = scanTree(dir, secrets);
    files += found.files;
    hits += found.hits;
  }
  report({ result: hits === 0 ? "pass" : "fail", files, hits });
  process.exit(hits === 0 ? 0 : 1);
}

if (process.argv.includes("--self-test")) selfTest();
else stdinScan();
