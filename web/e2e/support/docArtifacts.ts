import { lstatSync, readdirSync, readFileSync, rmdirSync, unlinkSync, type Stats } from "node:fs";
import path from "node:path";

/**
 * DOC01 Part C: the documents suite's own store cleanup and document-token scan. Pure
 * filesystem helpers with explicit paths (no Playwright import), so the R65/R66 canaries can
 * exercise them on throwaway directories.
 */

export type RunPaths = { webRoot: string; runtimeDir: string; stackDir: string; secretsPath: string };

const MARKER = ".docworker-store";
const REQUIRED_DIRS = ["handles", "runs", "recovery"] as const;
const OPTIONAL_DIRS = ["api-bridge"] as const; // created by the API on first use
const KNOWN_DIRS: readonly string[] = [...REQUIRED_DIRS, ...OPTIONAL_DIRS];

export type StoreIo = { readdir: (dir: string) => string[] };
const defaultIo: StoreIo = { readdir: (dir) => readdirSync(dir) };

export type StoreVerdict = { removed: boolean; reason: string; entry?: string };

function stat(full: string): Stats | null {
  try {
    return lstatSync(full);
  } catch {
    return null;
  }
}

/** Every entry of the store, named relative to it, with what it contains. Read-only. */
export function storeLeftovers(store: string, io: StoreIo = defaultIo): Record<string, string[]> | null {
  if (!stat(store)) return null;
  const out: Record<string, string[]> = {};
  for (const sub of KNOWN_DIRS) {
    const info = stat(path.join(store, sub));
    out[sub] = info?.isDirectory() && !info.isSymbolicLink() ? io.readdir(path.join(store, sub)) : [];
  }
  return out;
}

/**
 * The whole store must be exactly the empty layout `docworker init` creates: the marker file,
 * the three empty run directories and, optionally, an empty `api-bridge`. Anything else (an
 * unknown file, directory, link or unreadable entry, at the root or below) is a refusal that
 * names the store-relative entry and touches nothing.
 */
export function inspectStore(store: string, runtimeDir: string, io: StoreIo = defaultIo): StoreVerdict {
  const root = stat(store);
  if (!root) return { removed: false, reason: "store_missing" };
  if (root.isSymbolicLink()) return { removed: false, reason: "store_is_a_link" };
  if (!root.isDirectory()) return { removed: false, reason: "store_not_a_directory" };
  if (path.dirname(path.resolve(store)) !== path.resolve(runtimeDir)) return { removed: false, reason: "store_outside_runtime" };
  let entries: string[];
  try {
    entries = io.readdir(store);
  } catch {
    return { removed: false, reason: "store_entry_unreadable", entry: "." };
  }
  if (!entries.includes(MARKER)) return { removed: false, reason: "store_marker_missing" };
  for (const name of entries.slice().sort()) {
    const full = path.join(store, name);
    const info = stat(full);
    if (!info) return { removed: false, reason: "store_entry_unreadable", entry: name };
    if (info.isSymbolicLink()) return { removed: false, reason: "store_entry_is_a_link", entry: name };
    if (name === MARKER) {
      if (!info.isFile()) return { removed: false, reason: "store_marker_not_a_file", entry: name };
      continue;
    }
    if (!KNOWN_DIRS.includes(name)) return { removed: false, reason: "store_unexpected_entry", entry: name };
    if (!info.isDirectory()) return { removed: false, reason: "store_entry_not_a_directory", entry: name };
    let inside: string[];
    try {
      inside = io.readdir(full);
    } catch {
      return { removed: false, reason: "store_entry_unreadable", entry: name };
    }
    if (inside.length > 0) return { removed: false, reason: "store_not_empty", entry: name };
  }
  for (const name of REQUIRED_DIRS) {
    if (!entries.includes(name)) return { removed: false, reason: "store_layout_incomplete", entry: name };
  }
  return { removed: false, reason: "verified" };
}

/**
 * Remove the store only after `inspectStore` verifies it, and then only entry by entry without
 * recursion: the marker is unlinked and each empty directory is removed with `rmdir`, so an
 * entry that appeared after the check makes removal stop instead of deleting it.
 */
export function removeVerifiedStore(store: string, runtimeDir: string, io: StoreIo = defaultIo): StoreVerdict {
  const verdict = inspectStore(store, runtimeDir, io);
  if (verdict.reason !== "verified") return verdict;
  const present = io.readdir(store);
  try {
    for (const name of KNOWN_DIRS) if (present.includes(name)) rmdirSync(path.join(store, name));
    unlinkSync(path.join(store, MARKER));
    rmdirSync(store);
  } catch {
    return { removed: false, reason: "store_changed_during_removal" };
  }
  return { removed: true, reason: "removed" };
}

/**
 * Search this run's test results and the whole runtime directory, including the stack's own
 * directory (API log, manifest, PostgreSQL files) and the stack's secret file, for the
 * document-session tokens. Nothing is skipped: a document token has no expected place on
 * disk. A match is reported by its webRoot-relative name only, never by content. A link is
 * not followed and an unreadable entry is not guessed at; both are reported as problems.
 */
export function scanForTokens(tokens: string[], run: RunPaths): { files: number; leaks: string[]; problems: string[] } {
  if (tokens.length === 0 || tokens.some((token) => token.length < 16)) throw new Error("scan_secrets_missing");
  const needles = tokens.map((token) => Buffer.from(token, "utf8"));
  const roots = [path.join(run.webRoot, "test-results"), run.runtimeDir, run.stackDir, path.dirname(run.secretsPath)];
  const seen = new Set<string>();
  const leaks: string[] = [];
  const problems: string[] = [];
  let files = 0;
  const rel = (full: string) => path.relative(run.webRoot, full);
  // The recorded stack path can differ from the walked one only in letter case on Windows.
  const key = (full: string) => (process.platform === "win32" ? path.resolve(full).toLowerCase() : path.resolve(full));
  const pending = roots.filter((root) => root.length > 0 && stat(root)?.isDirectory());
  while (pending.length > 0) {
    const current = path.resolve(pending.pop() as string);
    if (seen.has(key(current))) continue;
    seen.add(key(current));
    let entries: string[];
    try {
      entries = readdirSync(current);
    } catch {
      problems.push(`unreadable:${rel(current)}`);
      continue;
    }
    for (const name of entries) {
      const full = path.join(current, name);
      const info = stat(full);
      if (!info) {
        problems.push(`unreadable:${rel(full)}`);
        continue;
      }
      if (info.isSymbolicLink()) {
        problems.push(`link:${rel(full)}`);
        continue;
      }
      if (info.isDirectory()) {
        pending.push(full);
        continue;
      }
      if (!info.isFile()) {
        problems.push(`special:${rel(full)}`);
        continue;
      }
      if (seen.has(key(full))) continue;
      seen.add(key(full));
      files += 1;
      let bytes: Buffer;
      try {
        bytes = readFileSync(full);
      } catch {
        problems.push(`unreadable:${rel(full)}`);
        continue;
      }
      if (needles.some((needle) => bytes.includes(needle))) leaks.push(rel(full));
    }
  }
  return { files, leaks: leaks.sort(), problems: problems.sort() };
}
