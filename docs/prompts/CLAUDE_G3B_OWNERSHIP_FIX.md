# Claude G3B R37: connection and helper lifetime ownership

Completed at accepted e23a7cd; R37 is closed under [the re-review](../reviews/G3B-e23a7cd.md).
The assignment below is historical. Do not repeat it or start G3C before its new dispatch.

Recommended coding assistant: **Claude Opus5.5 / High**. This focused resource-lifetime
correction needs event ordering, transaction semantics and concurrency reasoning.

Read current main:AGENTS.md, current task/coordination:docs/reviews/G3B-b74473e.md and
STATUS/TASK_QUEUE. Resume the existing `task/claude-g3b-workflow` worktree at exact
**b74473e820ae95effbd165eaad4e5faf974115d0**. Preserve commits/history, no reset/rebase/amend.
R34-R36 original probes now pass; keep those corrections. G3A remains accepted.

Fix R37 in the current budget/connection ownership implementation:
1. bounded_call must not return a connection for reuse while an older cancel worker can
   still cancel its next operation. Track cancel/shutdown owners as well as the SQL worker.
   If a helper cannot finish inside the response budget, retire the connection with finite
   resource accounting; do not wait indefinitely or silently reuse it.
2. The late SQL worker must not close its native descriptor while _shutdown_socket can
   still use a borrowed reference. Prevent close/reuse between descriptor acquisition and
   shutdown, or safely acquire an independent owned socket reference before close can occur.
   Never act on an unrelated socket that reused the descriptor.
3. Close exactly once and release accounting only after every helper relinquishes ownership.
   Keep abandoned resources bounded, preserve confirmed vs unknown COMMIT meanings and
   recovery truth, and keep provider-call slots independent and correctly held.

Independent repro source: E:/PHANI/Interview/tmp/test_g3b_b744_ownership.py (also copied to
canonical ignored .agent/g3b-review/b74473e/). The late-cancel case fails on Windows and
Linux; the descriptor case uses real probe-owned sockets and os.dup2 on Linux. Add maintained
regressions under owned tests/test_agent_* using event gates, including positive safe reuse,
helper completion, exactly-once close and zero final resource counts. Use a Windows
intercepted counterpart for the POSIX-specific primitive; no new pytest skips/allowlist edits.

Keep all85 independent passing agent/original-probe tests green. Budget/code policy,
public contracts, schema/examples, role transitions, provider isolation and human approval
stay unchanged. Own agents/budget.py and any strictly necessary agents/coordinator.py or
service integration changes, new agent tests, ADR0007 and branch handoff. Existing approved
packaging/inventory exceptions stay preserved. No UI/dependency/lockfile/legacy migration/
CI/timeout/skip-policy changes, no live provider or final-case evaluation. Codex owns central
STATUS/TASK_QUEUE; no accepted worktree/Cursor edits.

Write failing-first regressions onb74473e and demonstrate they reach both actual lifetime
behaviors, not just import errors. Record simulation vs real socket/PG evidence honestly.
Preserve the earlier unexplained failures/reports; do not increase thresholds, weaken
assertions or claim R37 caused them without evidence. If they recur after correction,
capture safe request/workflow diagnostics and diagnose the actual cause.

Final clean-commit checks remain the original Windows/native Ubuntu gates sequentially,
structured JUnit allowlist, domain+HTTP/package/ML checks, frontend and unchanged browser
suite. Only the existing live-Claude skip is allowed. All new commits: sole author and
committer PHANI465 <pgavara1@asu.edu>, no coauthor/AI/session trailers. Return exact SHA,
per-case failure-first and final results, cleanup and remaining limits. Do not merge main
or start G3C. Codex re-reviews before integration.
