Current dispatch: U01 5055321 resolves R14/R16/R17; only the R15 delayed-refresh query-context counterexample remains. Read docs/prompts/CURSOR_U01_R15_FOLLOWUP.md and docs/reviews/5055321.md from current task/coordination. The original correction brief below is historical scope, not a request to redo resolved work.

# Cursor U01 review corrections: R14-R17

Continue in E:/PHANI/sentinel-wt/cursor-analyst-ui on task/cursor-analyst-ui. Reviewed U01 is 98ce8aef4a3cc7b1cab4b685ff671ee4acc88e6a; accepted C01 is 2e6c2329aafe28b2e7c31ef5078d554cb66ca529. U01 has changes requested, not acceptance. Preserve your implementation/planning commits and any uncommitted work. Inspect actual Git status/HEAD and C01 ancestry; do not reset, repeat an already completed dependency merge or merge task/coordination to copy its docs.

Read current instructions explicitly:
    git show task/coordination:AGENTS.md
    git show task/coordination:docs/TASK_QUEUE.md
    git show task/coordination:docs/reviews/98ce8ae.md
    git show task/coordination:docs/prompts/CURSOR_U01_REVIEW_FIXES.md

Own web/ and docs/ui/, plus your existing branch handoff. Leave backend source, HTTP/domain contracts, migrations, Python dependencies and central STATUS/TASK_QUEUE to their owners. No main merge. C02 66214bb still has R11/R12 changes requested (R13 corrected); do not consume it or start U02 until Codex explicitly accepts corrected C02 and U01. U03 keeps its model-contract gate.

Fix these on your existing branch:

1. R14: align action parameter types with accepted C01's discriminated variants. A hold has amount; an escalation has transaction_id and reason_code without amount. Fix current proposal, historical proposal and executed-result rendering. Display exact server-built values without fabricated/zero amounts. Use an actual valid escalation payload in regression tests. Codex reproduced a blank workbench by investigating a large synthetic transaction with no prior velocity; the server correctly returned escalate/unusual_amount and awaiting_approval revision 3. Keep the hold path working. A fallback boundary is useful only after fixing the rendering/type defect.
2. R15: fence async results to the current selected case and current queue/filter/cursor request. Detail and audit must stay paired. Test select A then B with B resolving first and A last; B must stay visible with B's audit. Prevent duplicate Next transitions while pending and stale responses from changing newer state. Test double Next followed by Previous, reversed filter responses, and correct loading/busy completion. A single global boolean without stale-response ownership is insufficient.
3. R16: historical approval_expired audit events must not permanently instruct re-investigation. Show the current recovery instruction only when it applies to the current state/revision; keep the historical event visible. Test a genuinely reopened case and recovered awaiting-approval, fresh approval and closed states with the old event still present.
4. R17: queue amount text inherits color:white from generic buttons over pale row backgrounds. Give rows readable foregrounds; verify selected/unselected rows, score labels, keyboard focus and hover. Do a browser check; avoid unrelated redesign.

Write the meaningful regression checks first and show they fail on 98ce8ae for the intended reason, then implement. Preserve in-memory tokens, inert model text, 409 refetch, explicit approve/reject/execute separation and stable execution idempotency keys after ambiguous failures. Ordinary tests remain deterministic and must make no subscription/API model calls.

Run frontend tests, typecheck/build and the normal strict backend/helper/schema checks against your final clean commit. Do not claim strict PASS from an unfinished running report. If using a matching existing environment, record the lock match and source import path; otherwise follow the locked setup. Do not change the checker just to obtain a green report. Do not force-upgrade packages merely to silence an audit summary. Codex's fresh npm audit was blocked by automatic approval review for metadata egress; that check remains unverified, not passed.

Update your handoff and docs/ui/workflow.md as needed. Stage explicit owned files, inspect the diff, commit, and run final checks after the final commit. Return the exact SHA, dependency/base, changed paths, failing-first evidence, actual checks/browser results and gaps. U02's full real-browser/database suite remains a separate gated task; this correction must not be reported as completing U02.
