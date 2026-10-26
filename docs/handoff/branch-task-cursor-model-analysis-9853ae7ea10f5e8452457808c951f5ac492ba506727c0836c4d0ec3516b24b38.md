# Handoff: task/cursor-model-analysis

- Task and acceptance criteria: U03 contract/UI increment from docs/prompts/CURSOR_U03.md. Typed scoring and model-results clients, scorer versus stored-record display, and an accessible offline benchmark. Real-stack model acceptance is explicitly later.
- Tool and worktree: Cursor, `E:/PHANI/sentinel-wt/cursor-model-analysis`
- Updated: 2026-10-24 16:07 -07:00
- State: ready for review
- Code reference tested before this note: uncommitted working tree on parent `5f2855553ac0a445d96914730a89fc3722682830`
- Final check evidence: post-commit helper is reported in chat, not in this note
- Owned/changed paths: `web/src/api/analysis.ts`, `web/src/api/client.ts`, `web/src/api/client.v11.test.ts`, `web/src/api/format.ts`, `web/src/api/format.test.ts`, `web/src/api/types.ts`, `web/src/fixtures/http-v1.1/`, `web/src/ui/AnalysisPanel.tsx`, `web/src/ui/Analysis.test.tsx`, `web/src/ui/ModelReport.tsx`, `web/src/ui/CaseFile.tsx`, `web/src/ui/Workbench.tsx`, `web/src/ui/App.test.tsx`, `web/src/styles.css`, `docs/ui/U03-analysis.md`, `docs/ui/U01-design.md`, `docs/ui/workflow.md`, this note

## Implemented

- `GET /v1/scoring` and `GET /v1/model-results/{results_id}` parse the accepted v1.1 shapes. The client does not send `X-Request-ID`. A missing scoring route says the analysis view is unavailable and does not render the p1 fixture.
- The configured scorer is separate from the investigator label and from the scorer stored on a case. Rule and model records keep their own kind, semantics, score, and threshold.
- The offline report shows the frozen label, limitations, splits, baseline average precision, trapezoidal area, both policies, uncertainty, calibration, currency and scenario slices, and the reported precision-recall points. The frozen threshold renders as `4.0295386895426815e-6`.

## Verified

- Working tree, before this commit. Windows 10, Node v24.22.1, npm 10.9.2.
- `npm test` -> 37 passed (9 files), including the nine v1.1 fixtures, threshold text, policy counts 442 and 510, stale session, and sign-out.
- `npm run typecheck` and `npm run build` passed.
- `npm run test:e2e` -> scanner pass, shutdown harness 20, entry-point harness 12, 14 passed in 2.0m. That stack has no model routes; the new view stays unavailable there.

## Not verified / gaps

- No accepted model-mode API or Postgres rendering. C07 `62def106af74821040ac54535b8efe87341ca10b` is not merged.
- Linux, macOS, CI, and hosting were not run. This does not measure production fraud detection.
- Live Claude was not called. `npm audit` is not acceptance.

## Next action

Codex reviews this contract/UI commit. Real browser checks of model values start only after an accepted corrected C07, as a separate integration step.

## Coordination and provenance

- Base: accepted U02 `5f2855553ac0a445d96914730a89fc3722682830`. That worktree was not edited.
- Contract source: `62def106af74821040ac54535b8efe87341ca10b`. OpenAPI Git-blob SHA-256 `1f220a5628e3e261776c286c56b502b8d989184bd928bf219f30ebb6e451fd90`. Example copies and file hashes are in `web/src/fixtures/http-v1.1/PROVENANCE.md`.
- No edits to `src/sentinel/`, `contracts/`, migrations, Python dependencies, `docs/STATUS.md`, or `docs/TASK_QUEUE.md`.
