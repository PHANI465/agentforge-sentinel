# Handoff: task/cursor-browser-e2e

- Task and acceptance criteria: Correct U02 review R21 and R22 on the existing browser suite. Keep the accepted U01+C02 integration, the mutation guard, and the real browser-to-Postgres flows. Do not import C05 or merge main.
- Tool and worktree: Cursor, `E:\PHANI\sentinel-wt\cursor-browser-e2e`.
- Updated: October 24, 2026, 11:20 UTC-7.
- State: ready for review.
- Code reference tested before this note: uncommitted working tree whose parent is `7190c59da14198960397ba02b1edfc35be244a80`. Integration base remains `ab82c3ecd4d8252c99934a381becbf0289d78175`. This note does not name the commit that contains it.
- Final check evidence: the commands in Verified ran on that working tree before the commit. The post-commit browser rerun and the strict helper are reported in chat after the commit, not here.
- Owned/changed paths: `web/e2e/`, `web/playwright.config.ts`, `web/package.json`, `docs/ui/workflow.md`, and this handoff. No `src/sentinel/`, `contracts/`, migrations, Python dependencies, `tests/support/`, `docs/STATUS.md`, or `docs/TASK_QUEUE.md`. The mutation guard in `web/src/ui/Workbench.tsx` stays as committed in the parent.

## Implemented

- R21: the current run id is the only shutdown authority. Vite is killed only when creation time, executable, command line, and this worktree's `vite.js` path still match. An exited child, a reused PID, a foreign Vite path, and a missing identity are not killed. The server wrapper checks the C02 stop result. Uncertain shutdown writes `e2e/.runtime/recovery.json` with reasons and paths, not tokens.
- R22: verification secrets are copied to `owned-secrets.json` before the manifest can disappear. The scanner requires that set, scans a `test-results/stacks` artifact, excludes only the exact owned stack directory and secrets file, and fails closed on unreadable input. The last browser test is an expected post-login failure whose real `error-context.md` is required by teardown.
- The shutdown harness intercepts taskkill and stack stop. It does not target a live process.

## Verified

- Working tree, parent `7190c59da14198960397ba02b1edfc35be244a80`. Windows 10, Node `v24.22.1`, Playwright `1.64.1`.
- `node e2e/support/scan-artifacts.mjs --self-test` -> pass, `clean_hits` 0, `dirty_hits` 3, `stacks_hits` 1, unreadable and missing-secret codes fail closed.
- `node e2e/support/shutdown-harness.mjs` -> pass, 20 checks. No taskkill for foreign, reused, missing, exited, or stale cases.
- `npm run test:e2e` -> scanner self-test pass (`clean_hits` 0, `dirty_hits` 3, `stacks_hits` 1), shutdown harness 20 checks, then 14 browser tests passed (1.8m), including the expected post-login failure. Teardown exited 0.
- `tsc --noEmit` and `tsc --noEmit -p tsconfig.e2e.json` passed on this working tree.
- These checks are the pre-commit working tree. They are not the post-commit helper record.

## Not verified / gaps

- Linux, macOS, CI, and hosting were not run. This is not a production fraud-detection result.
- C05 is not in this branch. `main` was not merged. C07 and U03 were not started.
- Backend ruff, pytest, handoff unit tests, contract checks, and `scripts/agent_check.py` are run after the commit and are not claimed here.

## Next action

Codex re-reviews this R21/R22 commit. Do not merge main and do not start U03.

## Coordination and provenance

- Parent under review: `7190c59da14198960397ba02b1edfc35be244a80`. Integration base: `ab82c3ecd4d8252c99934a381becbf0289d78175` (U01 `deb10370352dc62b0abfa2a5776c185494fcb04e`, C02 `0e72b0bd599ff1707ca5b2507d65a0927894cbe0`, C01 `2e6c2329aafe28b2e7c31ef5078d554cb66ca529`).
- No backend, contract, migration, or Python dependency edits. C02's stack helper is unchanged.
- No session tokens or database URLs are in the committed files.
