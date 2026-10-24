#!/usr/bin/env python3
"""Run explicitly configured argv checks and record evidence for a clean commit.

Configure CHECKS before use, for example:
    CHECKS = [[sys.executable, "-m", "ruff", "check", "."],
              [sys.executable, "-m", "pytest", "-q"]]

Commands run sequentially with shell=False. Output stays in the terminal;
command arguments and output are never copied into the evidence report.
"""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
import time
from pathlib import Path

from agent_common import CHECK_FILE, GitError, atomic_report, discover_root, snapshot, utc_now

# Project checks. An explicitly empty list still fails closed as NOT CONFIGURED.
CHECKS: list[list[str]] = [
    [sys.executable, "-m", "ruff", "check", "."],
    [sys.executable, "-m", "pytest", "-q"],
    [sys.executable, "-m", "unittest", "discover", "-s", "tests_handoff", "-v"],
    [sys.executable, "scripts/export_contracts.py", "--check"],
    ["node", "scripts/check_contract_examples.mjs"],
]
# Per command. The full pytest run (real-process browser-fixture stacks included) takes about
# 5 minutes on the reference laptop; 900 s leaves margin without hiding a hang.
CHECK_TIMEOUT_SECONDS = 900


def valid_checks(checks: object, timeout: object) -> bool:
    return (
        isinstance(checks, list)
        and all(isinstance(argv, list) and bool(argv)
                and all(isinstance(arg, str) and bool(arg) and "\x00" not in arg for arg in argv)
                for argv in checks)
        and type(timeout) in (int, float)
        and math.isfinite(timeout)
        and timeout > 0
    )


def run_checks(root: Path, checks: list[list[str]], timeout: float) -> int:
    """Return zero only for complete checks on an unchanged, clean snapshot."""
    record: dict = {
        "schema_version": 1, "time": utc_now(), "state": "running",
        "passed": False, "commit": "", "branch": "", "before": None,
        "after": None, "check_count": 0, "results": [],
    }
    # Invalidate older success BEFORE configuration validation or execution.
    atomic_report(root, record)
    if not valid_checks(checks, timeout):
        record["state"] = "invalid_configuration"
    elif not checks:
        record["state"] = "not_configured"
    else:
        record["check_count"] = len(checks)
        record["checks_digest"] = hashlib.sha256(
            json.dumps(checks, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        try:
            before = snapshot(root)
            record.update(before=before, commit=before["commit"], branch=before["branch"])
            if before["dirty"]:
                record["state"] = "dirty"
            else:
                for index, argv in enumerate(checks, 1):
                    print(f"Running check {index}/{len(checks)}...", flush=True)
                    started = time.monotonic()
                    result = {"check": index, "exit": None, "state": "launch_error"}
                    try:
                        proc = subprocess.run(argv, cwd=root, shell=False, timeout=timeout,
                                              stdin=subprocess.DEVNULL)
                        result.update(exit=proc.returncode,
                                      state="passed" if proc.returncode == 0 else "failed")
                    except subprocess.TimeoutExpired:
                        result["state"] = "timeout"
                    except OSError:
                        pass  # Never persist exception text or potentially sensitive argv.
                    result["duration_seconds"] = round(time.monotonic() - started, 3)
                    record["results"].append(result)
                    print(f"Check {index}: {result['state']}", flush=True)
                after = snapshot(root)
                record["after"] = after
                unchanged = before == after and not after["dirty"]
                successful = all(r["state"] == "passed" and r["exit"] == 0
                                 for r in record["results"])
                record["state"] = "passed" if unchanged and successful else (
                    "changed" if not unchanged else "failed")
                record["passed"] = record["state"] == "passed"
        except KeyboardInterrupt:
            record["state"] = "interrupted"
        except GitError:
            record["state"] = "git_error"
    record["finished_at"] = utc_now()
    atomic_report(root, record)
    state = record["state"].upper().replace("_", " ")
    print(f"{state}: evidence recorded in {CHECK_FILE}")
    if record["state"] == "dirty":
        print("Checks were not run: preserve and review uncommitted work before verifying a commit.")
    elif record["state"] == "changed":
        print("Commit, branch or working tree changed during checks; this run cannot certify HEAD.")
    elif record["state"] == "not_configured":
        print("Edit CHECKS in scripts/agent_check.py with the project's actual argv commands.")
    return 0 if record["passed"] else (130 if record["state"] == "interrupted" else 1)


def main() -> int:
    try:
        root = discover_root(Path(__file__).resolve().parent)
        return run_checks(root, CHECKS, CHECK_TIMEOUT_SECONDS)
    except (GitError, OSError):
        print("ERROR: repository or report unavailable; no successful check is certified.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
