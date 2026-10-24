# Handoff: task/cursor-browser-e2e

- Task and acceptance criteria: U02. Drive the accepted analyst UI through the accepted C02 API into disposable Postgres, including approval, rejection, expiry recovery, stale revision, provider failure, ambiguous execution, capability isolation, restarts, and sign-out. Do not import unaccepted C05 or merge main.
- Tool and worktree: Cursor, `E:\PHANI\sentinel-wt\cursor-browser-e2e`.
- Updated: October 24, 2026, 09:50 UTC-7.
- State: ready for review.
- Code reference tested before this note: uncommitted working tree whose parent is `ab82c3ecd4d8252c99934a381becbf0289d78175` (U01 `deb10370352dc62b0abfa2a5776c185494fcb04e` merged with C02 `0e72b0bd599ff1707ca5b2507d65a0927894cbe0`). This note does not name the commit that contains it.
- Final check evidence: the commands in Verified ran on that working tree before the commit. The post-commit browser rerun and the strict helper are reported in chat after the commit, not here.
- Owned/changed paths: `web/e2e/`, `web/playwright.config.ts`, `web/tsconfig.e2e.json`, `web/package.json`, `web/package-lock.json`, `web/.gitignore`, `web/vite.config.ts`, `web/src/ui/Workbench.tsx`, `web/src/ui/App.test.tsx`, `docs/ui/workflow.md`, and this handoff. No `src/sentinel/`, `contracts/`, migrations, Python dependencies, `tests/support/`, `docs/STATUS.md`, or `docs/TASK_QUEUE.md`. The accepted U01 checkout remains `deb1037`. Its uncommitted contrast-test edit was not imported.

## Implemented

- `npm run test:e2e` starts the C02 stack with `--parent-dir`, then Vite on the printed API origin and a chosen loopback port, then Playwright. Teardown stops that manifest, checks the recorded ports, and scans saved artifacts for bearers and database URLs.
- `web/e2e/support/inspect_case.py` reads the private manifest and queries only that disposable database. It prints ids, counts, and codes.
- Fourteen serial browser flows cover ingest through execute, hold, reject, expired approval, selected-case ordering, stale revision plus the closed filter, provider failure, a dropped committed response, an in-flight duplicate, a second Execute activation, session isolation, API and database restart, and sign-out.
- A second Execute activation in the same turn sent two requests. `Workbench` now keeps one mutation in flight. The unit test failed with two calls before that guard.

## Verified

- Working tree, parent `ab82c3ecd4d8252c99934a381becbf0289d78175`. Windows 10, Node `v24.22.1`, npm `10.9.2`, Playwright `1.64.1`, Chromium `156.0.8078.4`.
- `npm test` in `web/` -> 25 passed (7 files), including the duplicate-activation regression.
- `npm run typecheck` and `npm run build` in `web/` -> passed.
- `npm run test:e2e` in `web/` -> scanner self-test `clean_hits` 0 and `dirty_hits` 3, then 14 passed (1.7m). Teardown exited 0.
- These checks are the pre-commit working tree. They are not the post-commit helper record.

## Not verified / gaps

- Linux, macOS, CI, and hosting were not run. This is not a production fraud-detection result.
- C05 is not in this branch. `main` was not merged. C07 and U03 were not started.
- Backend ruff, pytest, handoff unit tests, contract export, contract examples, and `scripts/agent_check.py` are run after the commit and are not claimed here.
- `npm audit` was not used as acceptance.

## Next action

Codex reviews this U02 commit against the browser-to-database acceptance. Do not merge main and do not start the model-gated work.

## Coordination and provenance

- Accepted U01 `deb10370352dc62b0abfa2a5776c185494fcb04e` is the branch base. Accepted C02 `0e72b0bd599ff1707ca5b2507d65a0927894cbe0` is merged at `ab82c3ecd4d8252c99934a381becbf0289d78175`. Frozen C01 is `2e6c2329aafe28b2e7c31ef5078d554cb66ca529`.
- No backend, contract, migration, or Python dependency edits. The inspection adapter uses the existing `sentinel.db` connection and refuses a non-loopback or wrong-port database.
- No reused AgentForge UI source. Public Sans remains `@fontsource/public-sans` (SIL Open Font License), loaded locally.
- No session tokens or database URLs are in the committed files.
