# Handoff: task/cursor-analyst-ui

- Task and acceptance criteria: Finish the remaining U01 R15 delayed-refresh race. Preserve the R14, R16, and R17 corrections from `5055321`. Do not start U02 or merge main.
- Tool and worktree: Cursor, `E:\PHANI\sentinel-wt\cursor-analyst-ui`.
- Updated: October 23, 2026, UTC-7.
- State: ready for review. The delayed refresh now uses the queue filter and cursor that are current when overview returns. U02 and U03 are not started.
- Code reference tested before this note: `5055321cfa810a2108d184e5542785cf44977edc`, plus the uncommitted refresh-query changes below. Parent of that commit: `98ce8aef4a3cc7b1cab4b685ff671ee4acc88e6a`. Accepted C01 dependency: `2e6c2329aafe28b2e7c31ef5078d554cb66ca529`.
- Final check evidence: `npm test` and `npm run build` below ran on the working tree before this commit. The strict helper is run after the commit and is not claimed in this note.
- Owned/changed paths: `web/src/ui/Workbench.tsx`, `web/src/ui/Workbench.races.test.tsx`, `docs/ui/workflow.md`, `docs/ui/U01-design.md`, and this handoff. R14/R16/R17 files from `5055321` stay as committed there. No `src/sentinel/`, `contracts/`, migrations, Python dependencies, `docs/STATUS.md`, or `docs/TASK_QUEUE.md`.

## Implemented

- R15 follow-up: mutation and ingest refresh read the authoritative filter and cursor after `loadOverview`, instead of the closure captured when refresh began. Filter changes, Next, and Previous update that query before they dispatch. A queue response whose filter or cursor is no longer current does not replace the page or leave loading stuck.
- Preserved from `5055321`: hold/escalation rendering, paired case detail and audit, duplicate-Next guard, recovery instruction scoped to an open revision without a proposal, and ink queue-amount foregrounds.

## Verified

- Failing-first on `5055321` source: approving a case, deferring the refresh overview, switching to Closed, then resolving overview removed `closed-only` and showed `all-state-row` while the selector stayed Closed.
- `npm test` in `web/` on the corrected working tree -> 24 passed (7 files), including the delayed-approval regression and the existing reversed-response, duplicate-Next, escalation, expiry, and contrast tests.
- `npm run build` in `web/` -> `tsc --noEmit` and Vite production build passed.
- These frontend commands ran before the commit. The strict Python helper runs after it.

## Not verified / gaps

- U02's browser-to-Postgres suite is not run. This follow-up was not exercised in a signed-in browser session.
- No live model call. Ordinary tests use fixtures. The live Claude smoke test stays skipped.
- `npm audit` was not re-run.
- Backend strict checks on this commit are recorded after the commit, outside this note.
- U03 is not started. Main was not merged.

## Next action

Codex re-reviews this delayed-refresh commit. Do not start U02 until Codex accepts the corrected U01 and the corrected C02.

## Coordination and provenance

- Reviewed correction: `5055321cfa810a2108d184e5542785cf44977edc`. Accepted C01: `2e6c2329aafe28b2e7c31ef5078d554cb66ca529`.
- No backend, contract, migration, or Python dependency edits.
- No reused AgentForge UI source. Public Sans remains `@fontsource/public-sans` (SIL Open Font License), loaded locally.
