"""Standard-library helpers shared by the manual handoff scripts."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

CHECK_FILE = ".agent/last-check.json"
FULL_OID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")


class GitError(RuntimeError):
    """Git evidence was unavailable; callers must not interpret this as clean."""


def git(*args: str, cwd: Path, optional: bool = False, timeout: float = 10) -> str:
    try:
        proc = subprocess.run(
            ["git", "--no-pager", "-c", "core.fsmonitor=false", *args], cwd=cwd,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise GitError("Git command unavailable") from exc
    if proc.returncode:
        if optional and proc.returncode in (1, 128):
            return ""
        raise GitError("Git command failed")
    return proc.stdout.rstrip("\r\n")


def discover_root(start: Path) -> Path:
    return Path(git("rev-parse", "--show-toplevel", cwd=start)).resolve()


def snapshot(root: Path) -> dict:
    head = git("rev-parse", "--verify", "HEAD", cwd=root)
    tree = git("rev-parse", "--verify", "HEAD^{tree}", cwd=root)
    if not FULL_OID.fullmatch(head) or not FULL_OID.fullmatch(tree):
        raise GitError("No full commit/tree identity")
    branch = git("symbolic-ref", "--quiet", "--short", "HEAD", cwd=root, optional=True)
    porcelain = git("status", "--porcelain=v1", "--untracked-files=normal", cwd=root)
    return {"commit": head, "tree": tree, "branch": branch, "dirty": bool(porcelain)}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def atomic_report(root: Path, record: dict) -> None:
    """Publish complete evidence only in an ignored, local directory."""
    target = root / CHECK_FILE
    if target.parent.is_symlink() or target.is_symlink():
        raise OSError("Evidence path must not be a symlink")
    if git("ls-files", "--", CHECK_FILE, cwd=root):
        raise OSError("Evidence file must not be tracked")
    if not git("check-ignore", "--", CHECK_FILE, cwd=root, optional=True):
        raise OSError("Ignore .agent/ before recording evidence")
    target.parent.mkdir(exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=target.parent,
            prefix="check-", suffix=".tmp", delete=False,
        ) as stream:
            temp_path = Path(stream.name)
            json.dump(record, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, target)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def note_name(branch: str) -> str:
    """Case-safe, Windows-safe name; slash/__ and Unicode branches stay distinct."""
    slug = re.sub(r"[^A-Za-z0-9-]+", "-", branch).strip("-")[:32] or "branch"
    digest = hashlib.sha256(branch.encode("utf-8")).hexdigest()
    return f"branch-{slug}-{digest}.md"


def valid_success(data: object) -> bool:
    """Reject malformed, partial, empty and internally inconsistent evidence."""
    if (not isinstance(data, dict) or type(data.get("schema_version")) is not int
            or data["schema_version"] != 1):
        return False
    if data.get("passed") is not True or data.get("state") != "passed":
        return False
    before, after, results = data.get("before"), data.get("after"), data.get("results")
    if not isinstance(before, dict) or not isinstance(after, dict) or before != after:
        return False
    if before.get("dirty") is not False or not isinstance(before.get("branch"), str):
        return False
    if any(not isinstance(before.get(k), str) or not FULL_OID.fullmatch(before[k])
           for k in ("commit", "tree")):
        return False
    if data.get("commit") != before["commit"] or data.get("branch") != before["branch"]:
        return False
    count = data.get("check_count")
    if type(count) is not int or count < 1 or not isinstance(results, list) or len(results) != count:
        return False
    return all(isinstance(row, dict) and type(row.get("check")) is int
               and row["check"] == index and type(row.get("exit")) is int
               and row["exit"] == 0 and row.get("state") == "passed"
               for index, row in enumerate(results, 1))
