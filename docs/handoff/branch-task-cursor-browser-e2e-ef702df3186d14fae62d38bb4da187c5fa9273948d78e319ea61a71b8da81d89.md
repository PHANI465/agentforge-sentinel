# Handoff: task/cursor-browser-e2e

- Task and acceptance criteria: Finish the remaining R21 entry-point wiring. Preserve R22, the mutation guard, and the real browser-to-Postgres flows. Do not import C05 or merge main.
- Tool and worktree: Cursor, `E:\PHANI\sentinel-wt\cursor-browser-e2e`.
- Updated: October 24, 2026, 12:05 UTC-7.
- State: ready for review.
- Code reference tested before this note: uncommitted working tree whose parent is `bb318a1d283b1802e6f87e484393b50bf4a7673b`. Integration base remains `ab82c3ecd4d8252c99934a381becbf0289d78175`. This note does not name the commit that contains it.
- Final check evidence: the commands in Verified ran on that working tree before the commit. The post-commit browser rerun and the strict helper are reported in chat after the commit, not here.
- Owned/changed paths: `web/e2e/support/serve.mjs`, `web/e2e/support/launch.mjs`, `web/e2e/support/entrypoint-harness.mjs`, `web/playwright.config.ts`, `web/package.json`, `docs/ui/workflow.md`, and this handoff. No backend, contract, migration, Python dependency, or `tests/support/` edits.

## Implemented

- `serve.mjs` no longer terminates a child when Vite identity is missing or unavailable. Shutdown keeps the raw PID, manifest, stack, run id, and reason in `recovery.json`. That file is not used as permission to kill.
- `chosenRun` uses only `SENTINEL_E2E_RUN_ID` from the current invocation. A leftover run file or another run's runtime, recovery, or secrets file fails startup and is left untouched.
- `launch.mjs` is the browser command. It refuses to start while those preserved files exist, and it does not stop or delete them.
- The entry-point harness evaluates the actual wrapper and config function with taskkill, stack stop, and filesystem writes intercepted.

## Verified

- Working tree, parent `bb318a1d283b1802e6f87e484393b50bf4a7673b`. Windows 10, Node `v24.22.1`.
- Before the wrapper change, the entry-point harness failed on `missing_identity_sends_no_taskkill`.
- After the change, `node e2e/support/entrypoint-harness.mjs` passed 12 checks: no taskkill without identity, recovery retained without the synthetic bearer or DSN, one taskkill for a verified owned identity, and no taskkill for exited, foreign, or reused processes. Stale config state issued no cleanup command. The launcher refused stale files and did not start.
- `npm run test:e2e` on this working tree -> scanner self-test pass, shutdown harness 20 checks, entry-point harness 12 checks, then 14 browser tests passed (1.8m) through `launch.mjs`, including the expected post-login failure. Teardown exited 0.
- `tsc --noEmit` and `tsc --noEmit -p tsconfig.e2e.json` passed.
- These checks are the pre-commit working tree. The post-commit rerun and the strict helper are reported in chat after the commit.

## Not verified / gaps

- Linux, macOS, CI, and hosting were not run. This is not a production fraud-detection result.
- C05 is not in this branch. `main` was not merged. C07 and U03 were not started.
- Backend ruff, pytest, handoff unit tests, contract checks, and `scripts/agent_check.py` are run after the commit and are not claimed here.

## Next action

Codex re-reviews this R21 entry-point commit. Do not merge main and do not start U03.

## Coordination and provenance

- Parent: `bb318a1d283b1802e6f87e484393b50bf4a7673b`. Integration base: `ab82c3ecd4d8252c99934a381becbf0289d78175` (U01 `deb10370352dc62b0abfa2a5776c185494fcb04e`, C02 `0e72b0bd599ff1707ca5b2507d65a0927894cbe0`, C01 `2e6c2329aafe28b2e7c31ef5078d554cb66ca529`).
- R22 scanner and expected-failure behavior are unchanged.
- No session tokens or database URLs are in the committed files.
