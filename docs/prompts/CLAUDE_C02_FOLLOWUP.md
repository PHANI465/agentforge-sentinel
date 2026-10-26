Current state: C02 0e72b0bd599ff1707ca5b2507d65a0927894cbe0 is ACCEPTED for the reviewed Windows local fixture scope; R11/R12/R13 are resolved. See docs/reviews/0e72b0b.md. No further blocking C02 correction is requested. Claude's current dispatch is docs/prompts/CLAUDE_C05_REVIEW_FIXES.md; the brief below is historical context, not a request to repeat completed work.

# Claude C02 re-review follow-up: remaining R11/R12

Continue task/claude-browser-fixtures in E:/PHANI/sentinel-wt/claude-browser-fixtures. Reviewed candidate is 66214bb466fe9810df5a306f12137606ba2c0251; it is NOT accepted. R13 is corrected. R11/R12 have the remaining concrete failures below. Preserve the existing commits and unfamiliar/uncommitted work; inspect actual Git state first. No reset or main merge.

Read current coordination instructions explicitly:
    git show task/coordination:AGENTS.md
    git show task/coordination:docs/TASK_QUEUE.md
    git show task/coordination:docs/reviews/66214bb.md
    git show task/coordination:docs/prompts/CLAUDE_C02_FOLLOWUP.md

Do not merge task/coordination simply to copy documents; its application source remains older c6. C02 continues to include accepted C01 2e6c2329aafe28b2e7c31ef5078d554cb66ca529. Own C02 test support/tests/docs and your task handoff; keep production src/, contracts/, web/ and central STATUS/TASK_QUEUE unchanged.

1. R11: before any pg_ctl stop/restart/status or related helper mutation, reject redirected critical child paths and resolved targets outside the verified owned state directory. Current load accepts pg and pg/data junctions; the deletion guard runs after a foreign-resolving stop command has already been invoked. Include operation-boundary checks on loaded objects and safe startup handling before children exist. Cover api.log/other helper writes consistently. Add safe intercepted regressions for BOTH nested junction variants: zero foreign process mutations and an untouched outside canary. Never launch or stop a real foreign database to prove the bug.
2. R12 partial removal: on Windows, a locked api.log or pg file lets rmtree delete the ownership marker before failing. _save recreates only stack.json, so the documented retry fails ownership validation. Delete removable contents before ownership/recovery metadata, with a defined recoverable finalization path. Never manufacture ownership for an arbitrary path. Test partial deletion and a Windows locked file in a fresh process-free owned tree: manifest remains safely loadable after failure; after releasing the lock, ordinary stop retry completes without hand-editing metadata.
3. R12 unknown status: a pg_ctl status error is not proof the database is stopped. Current stop can report ok:true and remove state when stop fails and status returns 1. Distinguish running/stopped/unknown; status 3 is documented not-running, while errors/inaccessible paths require failure and recovery preservation. Handle pre-init state explicitly. Add intercepted return-code/exception regressions plus real normal shutdown/retry checks.

Keep the corrected R13 descriptions/assertions. Avoid broad API/security redesign: these are helper lifecycle corrections. Preserve exact-process identity checks, private ephemeral tokens and deterministic investigator behavior.

Write failing-first tests safely. All filesystem targets must be fresh, resolved reviewer/test-owned subtrees. Use intercepted process operations for redirected-path and unknown-status counterexamples. Document and verify resolved deletion targets immediately before recursive cleanup. Do not reuse an unrelated test run's database or delete another tool's recovery folder.

Codex's focused real-process command was rejected by automatic approval review because of the known nested-path risk. No test PASS is claimed for that blocked run. Fix and validate the safe intercepted guards before running real-process suites; if execution is blocked, retain the exact reason and evidence instead of bypassing it.

After correction: run focused regressions, ordinary C02 real-process tests, HTTP/domain export checks and normal strict checks, with live Claude off and isolated temporary state. Inspect explicit owned files, update handoff, commit, then run final checks AFTER the final commit. Return exact SHA, actual counts/commands, failing-first evidence, owned-process cleanup results and gaps. A passing old report or another checkout's report is not transferable evidence.

C05 is already authorized: use a separate task/claude-backend-reliability worktree from accepted C01 2e6c232 without C02 code. Follow the current TASK_QUEUE C05 scope: safe diagnostics/trace IDs and metrics, secret canaries, overview read consistency, bounded failure/concurrency/cancellation behavior and least-privilege runtime/migration roles. Preserve Cursor's frozen HTTP boundary; hand off any necessary API contract change before consumers implement it. Claude owns backend, Cursor owns U01 fixes and later U02; no shared-checkout concurrent edits. C03/C06/C08 remain delivered, review pending; C04/C07 retain gates. No WSL/GitHub provisioning, extra spending or main merge is implied.
