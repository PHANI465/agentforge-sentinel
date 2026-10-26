# C08 R28 acceptance

Accepted exact clean **353ecec2fadbba43f939a27f5ad2b9227ff6fe87**, task/claude-operator-prep, October 26, 2026 (America/Phoenix). Direct parent is reviewed 784e1014044920706a41bd91c61b965a03379999. **No blocking findings remain for the Windows-local operator scope.** POSIX support is not accepted by this review.

## Resolved finding

R28A: start_api persists pending recovery before Popen and saves the raw PID before identity inspection. Unknown identity remains unresolved, cannot be killed, and blocks down/restore and the database stop. Resolution requires the launcher to be gone, no surviving descendants and a free port. A known failed launch clears its pending record. A verified launcher that exits while a child survives is refused too.

R28B: startup success requires a live owned process tree and an actual successful health response. An owned listening port alone cannot make a readiness timeout succeed. Failure follows verified cleanup or retains recovery and returns a nonzero result. The wait return itself is not used as authority; the final serving predicate enforces the health/ownership condition.

## Independent evidence

- Read the actual parent-to-candidate implementation, tests, runbook and handoff. Only the four intended operator/test/document paths changed; production source, contracts, model/data/evaluation files, dependencies and UI are unchanged from accepted I02 f38e920.
- Focused real-process suite: **15 passed in 108.37s**, exit 0: tests/test_local_stack_startup.py, test_local_stack.py, test_local_rollback_drill.py and test_backup_restore.py. Includes five startup regressions, identity refusals, failed-stop retry, failed-factory cleanup, actual two-version rollback and backup round trip. The only warning is the existing Starlette/httpx deprecation warning.
- Six independent intercepted cases passed: pre-launch recovery plus known launch-failure cleanup; identity-error down/restore refusal; missing-PID refusal; an exited launcher with a non-listening child; clearing a fully resolved launch without killing; and rejecting readiness without health. No real process launch/kill or database operation occurs in these probes.
- Ruff passed on the operator and four focused test files using this worktree's interpreter. The initial uv lint invocation could not access the shared cache in the sandbox; the direct no-cache Ruff rerun passed. This is not a test failure or an accepted-checkout source edit.
- Focused JUnit: E:/PHANI/Interview/tmp/c08-r28-review-20261026.xml. Independent probe: E:/PHANI/Interview/tmp/review_c08_r28_20261026.py. No postmaster.pid remains in the review pytest root, and no Python/Postgres command line points to it. The initial broad cleanup query matched its own inspection shell; a query restricted to API/database executable names confirmed no review resource remained. No process was killed by that inspection.
- Candidate remains clean at 353ecec. Its existing owner strict metadata still matches five passed checks. The full **411 passed + one opt-in live skip** and baseline failures remain Claude's attributed evidence, not a new independent full-suite rerun.

## Limits and next step

Windows only. POSIX orphan reparenting remains a known limitation; the disclosed PID check-to-kill race is not atomically closed. Model-mode and local Claude operator smoke were not run in this review. No hosted deployment, Linux/CI run, model call, external database or actual financial action was involved.

Preserve 353ecec, accepted C06 4f06e32 and I02 f38e920. I03 is now assigned through prompts/CLAUDE_RELEASE_INTEGRATION.md: combine these components in a separate task branch/worktree and verify the final combined commit. This is task-branch integration, not designation or authorization to merge main. H01 remains non-blocking and unassigned.
