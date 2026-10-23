# Claude next task: C02 browser fixtures

C01 is accepted at 2e6c2329aafe28b2e7c31ef5078d554cb66ca529 after independent Codex re-review. R9/R10 are resolved. This is the next implementation prompt; do not repeat the completed C01 fixes.

Read the latest shared instructions without merging the coordination branch:
    git show task/coordination:AGENTS.md
    git show task/coordination:docs/TASK_QUEUE.md
    git show task/coordination:docs/reviews/2e6c232.md
    git show task/coordination:docs/prompts/CLAUDE_C02.md

The coordination checkout carries older application code plus current documents. The accepted application dependency for this task is the full C01 commit above, not main or the coordination branch tip. Older STATUS/handoffs in task worktrees are historical snapshots; use the named current coordination reference for task state.

## Worktree and ownership

Inspect Git branches/worktrees first. Create or reuse task/claude-browser-fixtures in its own worktree from the exact accepted C01 commit. Preserve unfamiliar changes; no resets or history rewrites. Cursor already has E:/PHANI/sentinel-wt/cursor-analyst-ui and owns web/, docs/ui/ and browser tests. Do not edit its files or checkout.

C02 owns tests/support/, private backend seed/startup helpers, relevant backend tests and docs/api/browser-fixtures.md. Keep the accepted production HTTP contract stable. Request any necessary contract change through a concrete example before consumers diverge.

## Deliver C02

- A reproducible deterministic fixture and real test-server lifecycle that Cursor can invoke from Playwright/browser tests.
- Disposable PostgreSQL migration/seed/start/stop with readiness and bounded cleanup. Verify the actual child API process and database stop; no broad process-name termination.
- Synthetic cases for approve/execute, rejection, expired approval/reopening/fresh investigation and approval, stale revision, duplicate execution, cross-session denial and limited capabilities.
- A deterministic failing-investigator scenario with an actual failed run and reopened case. No provider/model call.
- A real process restart scenario proving persisted case/approval/action/audit state. Distinguish restarting Uvicorn/Postgres from reconstructing Python objects.
- Stable fixture identifiers and ephemeral auth delivered through private test-process fixtures/IPC. Keep tokens out of committed files, URLs, terminal evidence and browser traces; clean any restricted temporary files on teardown.
- Expiry scenarios without long sleeps or public clock controls. Test-only seed/clock configuration belongs outside normal application routes.
- Document an explicit process/fixture interface for Cursor, setup/teardown commands, available scenarios and exact responses/state transitions.

Do not add a public seed, token-issuing, capability-granting or clock-changing endpoint. Do not expose owner credentials or make production depend on a test fixture. Use the accepted real API for the browser path; no mock-only claim of integration.

## Acceptance and handoff

Run tests that prove fixture repeatability, real server readiness, timeout/failure cleanup, foreign-session isolation, failed-provider recovery and restart persistence. Existing C01 tests, review regressions, HTTP export and domain schema checks remain green.

Use deterministic investigations; live Claude is off. Review explicit task files, update your branch handoff and API fixture documentation, commit, then run final checks on that commit. Report the full commit, accepted base, worktree, commands/results, process cleanup and any unverified behavior. Ordinary checks never call a model.

Immediately hand off the C02 commit for Codex review and Cursor U02. U02 waits for accepted C02 and U01.

After the C02 implementation is handed off and no writer is changing the backend, C05 may begin in its own branch/worktree from accepted C01 while C02 awaits review. Do not merge unaccepted C02 code. Coordinate any API/migration changes; include the nonblocking overview snapshot-consistency follow-up from the C01 review.

C03, C06 and C08 remain delivered and awaiting review. C04 still waits for accepted C03, and C07/U03 wait for their model gates. Do not rebuild delivered packages to use quota.

Do not merge main or edit central STATUS/TASK_QUEUE. WSL installation, Linux-user creation, GitHub/remote setup and hosting remain separate pending decisions. Existing subscriptions/free resources only; stop on quota exhaustion without paid fallback.
