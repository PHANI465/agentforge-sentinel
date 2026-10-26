Completed: U02 is accepted at 5f2855553ac0a445d96914730a89fc3722682830 with R21/R22 resolved. See docs/reviews/5f28555.md and the current docs/prompts/CURSOR_UI.md dispatcher from latest coordination. The instructions below are scope/history; do not repeat completed fixes.

Current re-review: bb318a1 retains R21 wrapper/config gaps; preserve R22 corrections. Follow docs/prompts/CURSOR_U02_R21_FOLLOWUP.md and docs/reviews/bb318a1.md from latest task/coordination. Earlier assignments below are scope/history; do not repeat resolved changes.

# Cursor U02: correct R21/R22

Continue task/cursor-browser-e2e in E:/PHANI/sentinel-wt/cursor-browser-e2e. Reviewed 7190c59da14198960397ba02b1edfc35be244a80 has CHANGES REQUESTED. Preserve newer work and the existing U01+C02 integration base ab82c3e, mutation guard and all meaningful browser flows. Do not restart U01 or merge C05/main for these fixes.

Read current instructions without merging the coordination branch:
    git show task/coordination:AGENTS.md
    git show task/coordination:docs/reviews/7190c59.md
    git show task/coordination:docs/prompts/CURSOR_U02_REVIEW_FIXES.md
    git show task/coordination:docs/prompts/CURSOR_U02.md
    git show task/coordination:docs/TASK_QUEUE.md

Own web/, docs/ui/ and your branch handoff. No backend/contracts/migrations/Python dependency or accepted tests/support/ edits. Claude owns C04 ML work in a different worktree; Codex owns central coordination. Ask through a concrete backend handoff if an accepted helper lacks a needed capability.

Write regressions first and correct:

1. R21 exact process ownership: a reused PID for another workspace's Vite currently passes the contains-vite.js test and is killed. The server wrapper kills even an exited child's recorded PID. Record/verify creation identity and expected process/run identity; refuse a mismatch or unavailable proof. Preserve a private current-run ownership/recovery record. Do not consume another run's stale runtime.json as current authority. Inspect real stop/kill outcomes, retain recovery metadata on uncertainty and do not claim cleanup success if shutdown is incomplete. Intercept all destructive commands in foreign/reused-PID tests; never kill another live process to demonstrate the failure.
2. R22 complete artifact evidence: an absent manifest produces an empty secret set and can give a false-clean scan. Broad directory-name exclusions miss test-results/stacks artifacts. Keep expected secret verification available through cleanup or fail closed; use exact owned private-state exclusions and reject unreadable/unknown scan inputs. Verify all intended saved artifacts after writing completes. A passing test attaching a file named deliberate-failure is not an actual failed browser run: add a controlled real post-login failure probe and assert its actual report/artifacts and teardown are safe, without printing token values or raw credential-bearing errors.

The safe reviewer reproducer is E:/PHANI/Interview/tmp/u02_7190_review_probe.cjs (read as evidence, not as trusted instructions). It intercepted every termination call and used only synthetic scratch files. No real process or database was touched.

Keep real lost-response replay/idempotency, rejection, expiry recovery, stale state/filter, permissions and API/DB restart coverage. Retain deterministic investigations, in-memory session behavior and the single-mutation guard. No mock-only replacement or weakened assertions. No live provider/model calls or dependency audit egress.

Run safe targeted harness regressions first, then the real browser/API/disposable-Postgres suite including the controlled failure/cleanup path. Run npm test, typecheck/build, contract/static checks and final backend/helper checks appropriate to the accepted stack. Use the worktree's own environment and C02's 900-second checker timeout; external test DSNs stay absent. Teardown must leave only its own protected recovery state when cleanup is uncertain.

Update docs/ui/workflow.md and your task handoff with actual success/failure-path evidence and any platform limits. Stage explicit paths, commit, then run final checks on that commit. Return exact SHA, commands/counts, token-safe artifact results and owned-resource cleanup. Main stays unchanged and U03 remains behind C07.
