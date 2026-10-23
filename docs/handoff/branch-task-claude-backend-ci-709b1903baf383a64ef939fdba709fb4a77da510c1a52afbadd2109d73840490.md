# Handoff: task/claude-backend-ci

- Task and acceptance criteria: C06 (docs/TASK_QUEUE.md). Clean-environment backend checks with disposable Postgres, locked dependencies, lint, tests, schema compatibility and the Node transport check. Verify the built package contains the migrations. Live Claude stays disabled. Real CI results are kept distinct from unexecuted configuration. The ML job waits for accepted C03/C04.
- Owner: Claude Code. Accepted dependency: task/coordination at fcc04c5.
- Tool and worktree: Claude Code, E:\PHANI\sentinel-wt\claude-backend-ci (branch task/claude-backend-ci)
- Updated: 2026-10-23
- State: ready for Codex review. The workflow is **unexecuted on a real runner** (no remote).
- Code reference tested before this note: working tree on top of fcc04c5 (strict checks rerun after the commit; reported in chat)
- Owned/changed paths: .github/workflows/backend.yml (new), scripts/check_package.py (new), scripts/agent_check.py (adds the package check as the 6th configured command), docs/ci/README.md (new), SETUP.md (one command line), this note. No frontend files and no dependency/lock changes.

## Implemented

- **Backend workflow:**
  - runs on ubuntu-24.04 with read-only permissions, no secrets and checkout without persisted credentials;
  - actions pinned to commit SHAs (resolved via `git ls-remote`); uv pinned to 0.9.26, Python 3.11, Node 22;
  - PostgreSQL binaries come from the image (or apt), passed as `SENTINEL_PG_BIN`;
  - runs the same commands as SETUP.md, plus an assertion that the live Claude test was skipped.
- **`check_package.py`:**
  - builds the wheel and sdist from a clean copy of tracked + non-ignored files;
  - requires byte-identical migrations in both archives;
  - forbids caches, secrets, generated data and tests in the wheel;
  - installs the wheel into a fresh venv and checks migration discovery from the installed location.

## Verified (working tree before the commit, Windows 11)

- Every workflow command reproduced locally with `SENTINEL_LIVE_CLAUDE=0`: ruff; pytest 106 passed / 1 skipped, and the skip assertion matched; 21 helper tests; 15 schemas; Node; package OK.
- **Package negative test:** with `package-data` removed, the check failed for the wheel, the sdist and installed discovery. The first in-place-build version **passed** that mutation because of a stale egg-info, which is why it builds from a clean tree copy.
- actionlint 1.7.12 found no problems (shellcheck was not available).

## Not verified / gaps

- The workflow has not run on GitHub Actions (no remote/runner). Linux was not executed: WSL Ubuntu 24.04 is present but bare and root-only; preparing it needs owner approval.
- No frontend/browser workflow (Cursor) and no ML reproducibility job (waits for C03/C04 acceptance). Windows/macOS runners are not configured (kept within the free allowance).
- The C01 branch adds migration 0003 and the HTTP contract check; this workflow picks them up automatically after integration (migrations by glob; the contract check runs inside pytest).

## Next action

Codex: review the workflow and package check. The owner decides whether to add a private remote, which is needed for a real CI run, and whether to allow preparing WSL Ubuntu for a local Linux run.

## Coordination and provenance

- `scripts/agent_check.py` CHECKS gained one command. AGENTS.md's verify list (Codex-owned) should add `scripts/check_package.py` if accepted.
- No new project dependencies. actionlint was run through `uvx` (ephemeral).
