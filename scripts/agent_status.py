#!/usr/bin/env python3
"""Read a local Git/status briefing; never stage, commit, fetch or run checks.

Usage: python scripts/agent_status.py [--full] [--cursor-json]
       python scripts/agent_status.py --note-path [BRANCH]
GitHub issues are offline by default; opt in with AGENT_STATUS_GH=1.
Notes are human/agent-authored claims, not proof of successful verification.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from agent_common import (CHECK_FILE, GitError, discover_root, git, note_name,
                          snapshot, utc_now, valid_success)

MAX_CHARS = 9000
MAX_NOTE_LINES = 60
MAX_OTHER_BRANCHES = 10
HANDOFF_DIR = "docs/handoff"
STATUS_FILE = "docs/STATUS.md"
PLACEHOLDER = re.compile(r"<[^<>]+>")


def default_branch(root: Path) -> str:
    ref = git("symbolic-ref", "--quiet", "refs/remotes/origin/HEAD", cwd=root, optional=True)
    prefix = "refs/remotes/origin/"
    if ref.startswith(prefix):
        return ref[len(prefix):]
    for name in ("main", "master"):
        if git("rev-parse", "--verify", "--quiet", f"refs/heads/{name}", cwd=root, optional=True):
            return name
    return "(unknown)"


def section(md: str, heading: str, max_lines: int = 14) -> str:
    lines, grab, out = md.splitlines(), False, []
    for line in lines:
        if line.startswith("## "):
            if grab:
                break
            grab = line[3:].strip().lower().startswith(heading.lower())
        elif grab and line.strip():
            out.append(line)
    if len(out) > max_lines:
        return "\n".join(out[:max_lines] + ["... (more lines in the source note)"])
    return "\n".join(out)


def field(note: str, name: str) -> str:
    for line in note.splitlines():
        stripped = line.strip().lstrip("-* ").strip()
        if stripped.lower().startswith(name.lower() + ":"):
            return stripped.split(":", 1)[1].strip()
    return ""


def check_state(root: Path, head: str, dirty: bool, branch: str | None = None) -> str:
    try:
        data = json.loads((root / CHECK_FILE).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return "NOT VERIFIED: no report; configure and run python scripts/agent_check.py."
    except (OSError, ValueError):
        return "NOT VERIFIED: unreadable check report."
    if not valid_success(data):
        state = data.get("state") if isinstance(data, dict) else None
        known = {"running", "not_configured", "invalid_configuration", "dirty", "changed",
                 "git_error", "interrupted", "failed"}
        label = state.upper().replace("_", " ") if isinstance(state, str) and state in known else "INVALID REPORT"
        return f"NOT VERIFIED: {label}; no current successful check."
    if data["commit"] != head:
        return f"STALE: checked {data['commit']}; current HEAD is {head}."
    if branch is not None and data["branch"] != branch:
        return "STALE: the branch changed since checks ran."
    if dirty:
        return "STALE: files have changed since checks; the working tree is dirty."
    return f"PASSED at {data.get('finished_at', '?')} on clean commit {head}."


def github_issues(root: Path) -> str:
    if os.environ.get("AGENT_STATUS_GH", "0") != "1" or not shutil.which("gh"):
        return ""
    try:
        proc = subprocess.run(["gh", "issue", "list", "--state", "open", "--limit", "10"],
                              cwd=root, capture_output=True, text=True, timeout=6,
                              encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return ""
    return proc.stdout.strip() if proc.returncode == 0 else ""


def briefing(root: Path | None = None, full: bool = False) -> str:
    root = root or discover_root(Path(__file__).resolve().parent)
    current = snapshot(root)
    branch = current["branch"] or "(detached HEAD)"
    head = current["commit"]
    base = default_branch(root)
    lines = [f"=== STATUS BRIEFING (generated {utc_now()}) ===",
             f"Repo: {root.name}   Branch: {branch}   Default branch: {base}",
             "Local refs only; no fetch or network lookup is performed by default.",
             "Working tree DIRTY; preserve unrelated changes and coordinate before editing."
             if current["dirty"] else "Working tree clean.",
             "Last check: " + check_state(root, head, current["dirty"], current["branch"])]
    if branch == base:
        lines.append(f"You are on {base}; use the task's agreed branch/worktree before edits.")
    recent = git("log", "-8", "--format=%h %ad %s", "--date=short", cwd=root)
    if recent:
        lines.extend(["\nRecent commits:", recent])
    if current["branch"]:
        relative = f"{HANDOFF_DIR}/{note_name(current['branch'])}"
        note_path = root / relative
        if note_path.exists():
            note = note_path.read_text(encoding="utf-8", errors="replace")
            lines.append(f"\n--- Handoff claims: {relative} (verify against Git/check evidence) ---")
            note_lines = note.splitlines()
            lines.extend(note_lines if full else note_lines[:MAX_NOTE_LINES])
            if not full and len(note_lines) > MAX_NOTE_LINES:
                lines.append("... (use --full to read the complete note)")
        elif branch != base:
            lines.append(f"\nNo handoff note: {relative}")
    refs = git("for-each-ref", "--sort=-committerdate", "refs/heads",
               "--format=%(refname:short)|%(objectname)|%(committerdate:short)", cwd=root)
    others = [row.split("|", 2) for row in refs.splitlines()
              if row.split("|", 1)[0] not in (branch, base)]
    if others:
        lines.append("\nOther local branches (committed notes; worktree edits may be newer):")
    for name, oid, date in others[:MAX_OTHER_BRANCHES]:
        note = git("show", f"{oid}:{HANDOFF_DIR}/{note_name(name)}", cwd=root, optional=True)
        lines.append(f"  {name} ({date}, {oid[:12]}): {field(note, 'State') or 'no handoff note'}")
        nxt = section(note, "Next action", 1) or section(note, "Next step", 1)
        if nxt:
            lines.append("    next: " + nxt.splitlines()[0])
    if len(others) > MAX_OTHER_BRANCHES:
        lines.append(f"  ... and {len(others) - MAX_OTHER_BRANCHES} more branches")
    worktrees = git("worktree", "list", cwd=root)
    if len(worktrees.splitlines()) > 1:
        lines.extend(["\nWorktrees:", worktrees])
    status_path = root / STATUS_FILE
    if status_path.exists():
        md = status_path.read_text(encoding="utf-8", errors="replace")
        for heading in ("Next", "Known broken", "Open questions"):
            body = section(md, heading, max_lines=100000 if full else 14)
            if body and not all(PLACEHOLDER.search(line) for line in body.splitlines()):
                lines.extend([f"\n{STATUS_FILE} - {heading}:", body])
    issues = github_issues(root)
    if issues:
        lines.extend(["\nOpen GitHub issues (explicit network opt-in):", issues])
    lines.extend(["\nFollow the reviewed AGENTS.md; no staging, commits or checks were run here.",
                  "=== END STATUS BRIEFING ==="])
    text = "\n".join(lines) + "\n"
    if not full and len(text) > MAX_CHARS:
        text = text[:MAX_CHARS - 90] + "\n... (briefing truncated; use --full for complete output)\n"
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--cursor-json", action="store_true")
    parser.add_argument("--note-path", nargs="?", const="", metavar="BRANCH")
    args = parser.parse_args(argv)
    try:
        if args.note_path is not None:
            branch = args.note_path
            if not branch:
                root = discover_root(Path(__file__).resolve().parent)
                branch = git("symbolic-ref", "--quiet", "--short", "HEAD", cwd=root, optional=True)
            if not branch:
                raise GitError("A branch name is required for detached HEAD")
            text = f"{HANDOFF_DIR}/{note_name(branch)}\n"
        else:
            text = briefing(full=args.full)
    except (GitError, OSError, ValueError):
        text = "=== STATUS BRIEFING ===\nNOT VERIFIED: repository/status unavailable.\n"
    if args.cursor_json:
        sys.stdout.write(json.dumps({"additional_context": text}) + "\n")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
