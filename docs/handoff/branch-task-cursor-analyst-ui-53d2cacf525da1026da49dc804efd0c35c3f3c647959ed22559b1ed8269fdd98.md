# Handoff: task/cursor-analyst-ui

- Task and acceptance criteria: U01 review corrections R14–R17 in `web/` and `docs/ui/`. Preserve the analyst workbench from `98ce8ae`. Do not start U02 or merge main.
- Tool and worktree: Cursor, `E:\PHANI\sentinel-wt\cursor-analyst-ui`.
- Updated: October 23, 2026, UTC-7.
- State: ready for review. R14–R17 are implemented on the existing branch. U02 and U03 are not started.
- Code reference tested before this note: `98ce8aef4a3cc7b1cab4b685ff671ee4acc88e6a`, plus the uncommitted R14–R17 changes described below. Accepted C01 dependency: `2e6c2329aafe28b2e7c31ef5078d554cb66ca529` (merge `ed61cc99dfaf754c1b085ffcbb46b9bda7e027fd`).
- Final check evidence: frontend test, typecheck/build, and the headless Chrome contrast check below ran on the working tree before this commit. The strict helper is run after the commit and is not claimed in this note.
- Owned/changed paths: `web/src/api/case.ts`, `web/src/api/format.ts`, `web/src/api/types.ts`, `web/src/styles.css`, `web/src/ui/CaseFile.tsx`, `web/src/ui/CaseFile.test.tsx`, `web/src/ui/Workbench.tsx`, `web/src/ui/Workbench.races.test.tsx`, `web/src/ui/Queue.contrast.test.tsx`, `docs/ui/workflow.md`, `docs/ui/U01-design.md`, and this handoff. No `src/sentinel/`, `contracts/`, migrations, Python dependencies, `docs/STATUS.md`, or `docs/TASK_QUEUE.md`.

## Implemented

- R14: `ActionParameters` is the accepted hold/escalate union. Current proposal, executed result, and history render an escalation's transaction id and reason code. Hold still renders the server amount. No zero or fabricated amount.
- R15: case detail and audit share a generation and are published only for the case that is still selected. Queue loads have their own generation. Next and Previous do not start a second transition while one is in flight. A stale filter or page response does not replace newer queue state or clear its loading flag.
- R16: the re-investigation sentence is shown only when the case is open and the current revision has no proposal. Historical `approval_expired` stays in the audit for a recovered awaiting-approval case, a fresh approval, and a closed case.
- R17: queue row text, including the amount, uses `--ink` for idle, hover, focus, and selected states. Metadata stays muted and scores stay the alert color.

## Verified

- Failing-first on `98ce8ae` source, with these tests kept: 6 failed, 6 passed. Escalation threw `Cannot read properties of undefined (reading 'minor_units')`. Historical expiry still rendered the re-investigation sentence. Double Next recorded `cursor-1` twice. The reversed filter left `open-only` instead of `closed-only`. The later case rationale was absent. Queue amount color resolved to `white`.
- `npm test` in `web/` on the corrected working tree -> 23 passed (7 files).
- `npm run build` in `web/` -> `tsc --noEmit` and Vite production build passed.
- Headless Chrome applied `web/src/styles.css` to queue-row markup. Computed amount color `rgb(20, 36, 28)`: 13.62:1 on the desk, 12.20:1 on hover, 13.62:1 on focus and focus-visible, 15.48:1 selected (idle, hover, and focus). Score color `rgb(141, 46, 46)` stayed at least 6.18:1. This was not a signed-in Postgres session.
- These frontend commands ran before the commit. The strict Python helper runs after it.

## Not verified / gaps

- U02's browser-to-Postgres suite is not run. Reload-clears-token, cross-session denial, rejection, expiry, and restart are not exercised against a real server.
- No live model call. Ordinary tests use fixtures.
- `npm audit` was not re-run. The prior dev-advisory report was not force-upgraded and is not claimed as a new pass.
- Backend strict checks on this commit are recorded after the commit, outside this note.
- U03 is not started. Main was not merged.

## Next action

Codex re-reviews this R14–R17 commit. Do not start U02 until Codex accepts the corrected U01 and the corrected C02.

## Coordination and provenance

- Reviewed U01: `98ce8aef4a3cc7b1cab4b685ff671ee4acc88e6a`. Accepted C01: `2e6c2329aafe28b2e7c31ef5078d554cb66ca529`.
- No backend, contract, migration, or Python dependency edits.
- No reused AgentForge UI source. Public Sans remains `@fontsource/public-sans` (SIL Open Font License), loaded locally.
