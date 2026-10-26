# Handoff: task/cursor-model-integration

- Task and acceptance criteria: I02 Part A from `docs/prompts/CURSOR_I02.md` on task/coordination. N1: `ReliabilityBin.mean_score` and `fraud_rate` are nullable; `SplitCounts.labels_observable_by_horizon` may be omitted and defaults to null. Missing statistics render as not reported. Wrong types and omitted required fields stay rejected. Frozen p1 fixture bytes stay unchanged. Part B waits for an explicitly accepted I01 SHA.
- Tool and worktree: Cursor, `E:/PHANI/sentinel-wt/cursor-model-integration`
- Updated: 2026-10-25 10:42 -07:00
- State: ready for review (Part A). Part B is blocked until Codex accepts an exact I01 commit.
- Code reference tested before this note: uncommitted working tree on parent `a5716e252af2077a507767a3f819ddf44ea41c12`
- Final check evidence: rerun after the final commit is reported in chat, not in this note
- Owned/changed paths: `web/src/api/analysis.ts`, `web/src/api/types.ts`, `web/src/api/analysis.nullable.test.ts`, `web/src/ui/Analysis.test.tsx`, `web/src/ui/ModelReport.tsx`, `docs/ui/U03-analysis.md`, this note. No Python, contracts, migrations, or p1 fixture edits.

## Implemented

- The model-results parser accepts null `mean_score` and `fraud_rate`, including an empty bin, and treats an omitted `labels_observable_by_horizon` as null.
- Those missing values render as "not reported". A reported zero stays zero.
- Omitting `lo`, `hi`, `n`, `mean_score`, or `fraud_rate`, or sending a non-number, string, boolean, NaN, or non-count horizon, leaves the report unconfirmed. The benchmark is not rendered.
- Client and component regressions use in-memory copies of the frozen report. The fixture file hash remains `41e069f13fb168923e299cc0e17754bf5a3f629d5fc0d3bda662172dd1583d50`.

## Verified

- Working tree, before this commit. Windows 10, Node v24.22.1, npm 10.9.2.
- Before the parser change, the new DTO-valid cases failed: `acceptModelResults` returned null, the client returned `ok: false`, and the reliability table was absent. Wrong-type rejection already passed.
- After the change: `npm test` -> 44 passed (10 files). `npm run typecheck` passed. `npm run build` passed.
- These checks cover the uncommitted working tree, not the commit that contains this note.

## Not verified / gaps

- Part B is not started. task/coordination does not record an accepted I01 SHA. `task/claude-model-browser-fixtures` exists and was not consumed.
- No real browser, API, or Postgres model-mode run. No live model or provider call.
- Linux, CI, hosting, and production fraud detection were not verified.

## Next action

Codex reviews this Part A commit. Start Part B only after Codex accepts the exact I01 fixture SHA, then include that dependency and run the real browser/API/Postgres checks.

## Coordination and provenance

- Base: accepted U03 `a5716e252af2077a507767a3f819ddf44ea41c12` on `task/cursor-model-analysis`. That checkout was not edited.
- DTO: accepted v1.1 `ReliabilityBin` and `SplitCounts` (`mean_score`/`fraud_rate` nullable and required; `labels_observable_by_horizon` optional, default null).
- No edits to `src/sentinel/`, `contracts/`, migrations, Python dependencies, `docs/STATUS.md`, or `docs/TASK_QUEUE.md`.
