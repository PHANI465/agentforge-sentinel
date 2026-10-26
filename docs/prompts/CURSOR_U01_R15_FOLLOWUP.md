Current state: U01 deb10370352dc62b0abfa2a5776c185494fcb04e is ACCEPTED; R14-R17 are resolved. See docs/reviews/deb1037.md. The current Cursor dispatch is docs/prompts/CURSOR_U02.md. The correction brief below is historical context, not a request to repeat completed work.

# Cursor U01: finish the remaining R15 delayed-refresh race

Continue task/cursor-analyst-ui in E:/PHANI/sentinel-wt/cursor-analyst-ui. Reviewed commit is 5055321cfa810a2108d184e5542785cf44977edc, parent 98ce8ae. Accepted C01 2e6c232 remains an ancestor. R14/R16/R17 are accepted within their correction scope; do not repeat or redesign them. U01 package acceptance still waits for the one remaining R15 failure below.

Read the current shared instructions explicitly:
    git show task/coordination:AGENTS.md
    git show task/coordination:docs/TASK_QUEUE.md
    git show task/coordination:docs/reviews/5055321.md
    git show task/coordination:docs/prompts/CURSOR_U01_R15_FOLLOWUP.md

Inspect actual HEAD/status and preserve newer/unfamiliar work. Do not reset or merge task/coordination just to obtain docs. Own web/, docs/ui/ and your branch handoff only; no backend, contracts, migrations, Python dependency, central STATUS/TASK_QUEUE or main changes.

R15 remaining counterexample at Workbench.tsx refresh (lines 139-147):
- Approve an awaiting-approval case.
- Defer the overview requested by the ensuing refresh.
- Switch the queue to Closed and let closed-only results finish.
- Resolve the old overview.
- The old refresh then dispatches all-state listCases; it gets the newest generation and overwrites Closed rows while the selector stays Closed.

Codex independently reproduced query order all -> closed -> all against this exact source in E:/PHANI/Interview/tmp/u01_r15_refresh_probe.cjs. No server or model call is required to reproduce it.

Write a deferred mutation-refresh regression that fails on 5055321. Correct query ownership for refreshes: dispatch using the latest coherent filter/cursor context or discard work whose initiating query is obsolete. Request-start generation alone is insufficient when a stale closure starts its request later. Apply the same rule to ingest refresh and page changes. Preserve paired selected-case detail/audit, pending navigation guards, explicit approval/execution and stable idempotency keys. Keep current loading/error handling honest.

Keep the fix bounded. Retain existing direct reversed-response, duplicate-Next, escalation, expiry and contrast tests. Run frontend tests and typecheck/build, update your handoff, stage explicit owned paths, commit, then run normal strict checks after the final commit. Ordinary checks stay deterministic with live Claude off; no audit retry, package migration or new dependency is required for this fix. Return exact SHA, actual failing-first/new tests, final results and gaps.

C02 is accepted at 0e72b0bd599ff1707ca5b2507d65a0927894cbe0. U02 remains separate and waits for acceptance of corrected U01; only then include this C02 commit and read its docs/api/browser-fixtures.md (start uses --parent-dir). Keep tokens out of saved artifacts, including captured request headers and traces; authenticated tracing stays disabled unless complete redaction is verified. Do not import unaccepted C05 or merge main.
