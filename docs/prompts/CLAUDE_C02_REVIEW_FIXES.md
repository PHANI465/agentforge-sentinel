Current follow-up: C02 66214bb was re-reviewed and still has R11/R12 changes requested; R13 is corrected. Read docs/prompts/CLAUDE_C02_FOLLOWUP.md and docs/reviews/66214bb.md from the latest task/coordination reference. The original correction brief below remains historical context, not acceptance or the current dispatch.

# Claude: C02 review corrections R11-R13

C01 remains accepted at 2e6c2329aafe28b2e7c31ef5078d554cb66ca529. Cursor is actively implementing U01 and must continue undisturbed.

C02 c3fd83df78f2d8e90598508f3779c33a3fdad0a5 is CHANGES REQUESTED. U02 is not unblocked by its passing tests.

Read the current review and instructions:
    git show task/coordination:docs/reviews/c3fd83d.md
    git show task/coordination:docs/prompts/CLAUDE_C02_REVIEW_FIXES.md
    git show task/coordination:docs/TASK_QUEUE.md

Use the existing task/claude-browser-fixtures worktree at E:/PHANI/sentinel-wt/claude-browser-fixtures. Inspect actual HEAD/status, preserve newer/unfamiliar work and do not reset history.

## R11: state ownership and deletion safety

The helper accepts an existing --state-dir and later recursively deletes it, including unrelated files. load also trusts a version-only manifest.

Use a dedicated verified helper-owned directory. Either create a fresh private child or reject pre-existing/unowned targets before writes. Validate ownership and resolved paths before stop/restart/delete. Refuse mismatched, redirected/link/reparse targets and accidental reuse of an active stack's directory. Preserve unrelated data.

Write regressions first using only fresh test-owned temporary paths and canaries. Test nonempty directories, invalid/missing ownership, redirected paths where supported, and valid normal ownership. Never test against a real project/home/root directory. Check the resolved absolute deletion target stays inside the intended owned test subtree.

## R12: failure-safe cleanup

stop currently deletes recovery state even if API shutdown raises, provided the DB is stopped. Startup failure handling can also unlink the manifest after an unsuccessful DB stop.

Only remove state after BOTH API and DB shutdowns are verified. Report incomplete cleanup as failure and keep protected recovery metadata for a retry. Do not silently erase the only process/ownership record or claim success. Keep token-retention documentation accurate for that failure case.

Add bounded fault-injection regressions for API-stop and DB-stop failures, preserved recovery metadata, retryable cleanup and successful removal. Retain real readiness/crash/restart coverage. Do not kill an unrelated process when identity is uncertain.

## R13: correct fixture descriptions and missing assertion

A rejected intent's reapproval returns 409 stale_case_revision, not approval_exists. Update docs/api/browser-fixtures.md and scenarios.py and assert the actual response over real HTTP.

Only denied executions emit action_denied. Fix the manifest's "all audited" wording; do not change the production API to match incorrect fixture prose.

## Scope, verification and handoff

Keep production API/contracts unchanged. Own the C02 helpers/tests/docs and its task handoff. Preserve the 900-second timeout while coordinating the eventual scripts/agent_check.py merge with C06; do not integrate C06 here.

Run regression tests first on the unfixed behavior, then the fixes, full C02/HTTP compatibility checks and ordinary checks. Use deterministic investigations and private ephemeral state; no model calls. Review explicit paths, commit and run the strict helper AFTER the final commit. Verify no owned API/Postgres process or unprotected token file is left after successful teardown. If cleanup cannot be completed, retain recovery evidence and report the precise gap rather than deleting it.

Return the new full C02 commit, actual commands/results, test-first evidence and remaining gaps immediately for Codex re-review.

After that correction handoff, C05 may start from accepted C01 in its own worktree while C02 awaits re-review. Include the overview read-consistency follow-up and preserve Cursor's frozen HTTP boundary. Do not merge unaccepted C02 code or write in Cursor's checkout.

C03/C06/C08 remain delivered and awaiting review. C04/C07 retain their dependency gates. No main merge, WSL installation, GitHub provisioning, paid fallback or central STATUS/TASK_QUEUE edits.
