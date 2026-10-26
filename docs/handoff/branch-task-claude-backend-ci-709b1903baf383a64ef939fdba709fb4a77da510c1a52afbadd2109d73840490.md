# Handoff: task/claude-backend-ci

- **Task:** C06 review corrections R25 and R27 (docs/prompts/CLAUDE_RELEASE_REVIEW_FIXES.md and docs/reviews/e7fc868.md on task/coordination 6c31516).
- **Tool and worktree:** Claude Code, E:\PHANI\sentinel-wt\claude-backend-ci (branch task/claude-backend-ci).
- **Updated:** 2026-10-25.
- **State:** ready for Codex re-review. The workflow has **not run on a real runner** (no remote).
- **Dependency:**
  - previous C06 commit: e7fc868b52a1d3cc8876d8d993907398663c2d57;
  - refreshed with the accepted I02 f38e92023481a55db1ecf8bcdbe917140bd5d7cd as dependency-merge **034c2edf5b0a95d04e43afc2fe8662c26fd1cd44** (parents e7fc868, f38e920);
  - clean automatic merge: SETUP.md and `scripts/agent_check.py` auto-merged, the latter keeping both the sixth package command and the 1800 s limit; no hand-resolved content.
- **Code reference tested before this note:** the final working tree of this commit. Strict checks run after the commit and are reported in chat.
- **Owned/changed paths:**
  - `.github/workflows/backend.yml`, `scripts/ci_test_gate.py` (new), `scripts/check_package.py`;
  - `tests/test_ci_test_gate.py`, `tests/test_check_package.py` (both new);
  - `docs/ci/README.md`, this note.

  Not changed: production code, contracts, p1 files, the UI, the lockfile and dependencies. `agent_check.py` is unchanged since the merge (its timeout policy is preserved).

## R25 and R27 corrections (this commit)

- **R25, structured gate:** `scripts/ci_test_gate.py` replaces the `grep` gate. It runs pytest with JUnit output and returns pytest's own nonzero code unchanged. It rejects:
  - a missing, malformed or truncated report;
  - failures and errors;
  - zero executed required tests;
  - any skip or xfail other than exactly `tests.test_investigators::test_live_claude_cli_smoke` with its quota reason, and that skip missing.

  A stale report is deleted before each run.
- **R27, release compatibility:**
  - the workflow installs the locked dev and ml extras and runs the full backend suite through the gate;
  - it adds the HTTP contract export check and a bounded (10 min) `python -m ml test --reproduce` gate, requiring exact `{"reproduced": true}` and no tracked or untracked change under `ml/`, `evals/` or `data_pipeline/`;
  - `check_package.py` now requires the 4 migrations and 8 model/data identity assets byte-identical in the wheel and sdist, and no other non-Python file under the wheel's `ml/` and `data_pipeline/`;
  - the installed check (lock ml pins, `python -I`, neutral cwd) proves imports resolve inside the venv, discovers the migrations, binds `hgb_balanced@p1` and loads the frozen results.

  The per-step bounds are 30 min for tests and 10 min each for package and ML, within a 60-minute job.

## Verified (Windows 11, locked dev+ml, `SENTINEL_LIVE_CLAUDE=0`, deterministic investigator, disposable Postgres)

- **R25 baseline before the fix** (034c2ed workflow): `tests/test_ci_test_gate.py` runs the workflow's actual Tests step verbatim under Git bash `-eo pipefail`, with a `uv` shim, against throwaway suites with real skips.
  - **3 failed** for the actual reason: the old gate exited 0 for an extra skipped required test, an extra xfail, and a run with only the live skip.
  - 4 passed: healthy, failure, collection error and missing live skip, already nonzero.
- **After the fix:** 17 passed, adding the validator (missing, malformed, truncated, wrong-reason, no-required), exact pytest exit codes (1, 2, 3) and stale-report cases.
- **R27 asset tests:** 5 passed (`tests/test_check_package.py`).
- **Real package check:** exit 0, about 42 s.
- **Real ML reproduce:** `{"reproduced": true}`, exit 0, 85 s; `git status` under `ml/`, `evals/` and `data_pipeline/` was empty.
- **Full real suite through the gate:** 418 passed and 1 allowed skip; gate exit 0. Its 52.5 min wall time is **not representative**: Windows entered sleep at 17:32:58 and Modern Standby at about 18:02 during the run (System events 42/107/506/507), and a normally seconds-long thin-path test absorbed 1698 s.
- **actionlint:** run offline, no findings.

## Not verified / gaps

- **CI:** GitHub Actions and Linux were not executed (no remote). The upstream action pins were not re-resolved.
- **Duration:** on a Linux runner it is unmeasured. Locally, awake, the suite takes about 14–16 min, within the 30-minute step bound.
- **Local strict check:** check 2 is still plain pytest. The structured skip gate is the CI step, and is not a change to the shared checker.

## Next action

Codex: re-review R25/R27 at the final C06 SHA reported in chat.

## Previous evidence (e7fc868, kept as history)

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
