# G3A revision 2: narrow R31 deadline follow-up

**Completed and superseded: G3A 43d9e8a accepted; R31-R33 closed. Do not rerun this task. Read current coordination for G3B.**

Recommended coding assistant: **Claude Opus 5.5, High effort**. This is one bounded
absolute-deadline and transaction-budget correction, not another architecture redesign.

Read current main:AGENTS.md, task/coordination:docs/reviews/G3A-feb80d1.md and current
STATUS/TASK_QUEUE through the named Git reference. Resume the existing
`task/claude-g3a-design` worktree at exact **feb80d19cac6c91844d8c7490a7e04e1b1b246d1**.
Do not reset/rebase/amend or edit another checkout. Codex remains integrator.

R32/R33 and R31's capacity rules are closed. Preserve those. Correct only the remaining
R31 terminal-budget issue in design section 3.1 and the conflicting protocol deadline:

1. Separate working-phase and terminal-phase budgets. The terminal phase must not subtract
   its own reserve. Use an absolute monotonic deadline for elapsed checks and explicit
   units/rounding. Exhaustion must never become a disabling zero or negative database timeout.
2. Account for the *combined* connection/lock/statement/commit time and libpq's minimum and
   per-host behavior. Define what happens if the remaining terminal budget cannot safely
   accommodate a new connection or operation. Bound waiting without claiming cancellation
   of provider work, an impossible commit guarantee or exactly-once outcome knowledge.
3. If no safe terminal write is possible or the commit outcome is uncertain, preserve the
   durable running workflow for the existing recovery path, describe the honest HTTP/state
   result, and keep unresolved worker leases accounted for. Never silently mark completion.
4. Make latency metrics and hard gates use the same reserve/deadline definition. Keep
   45s/150s provisional defaults; no extra timeout allowance or checker increase.
5. Add a small executable budget specification/check under docs/agents/, using existing
   dependencies. Demonstrate the old formula's 5/4/0 remaining -> 0/-1/-5, then validate
   working vs terminal budgets at/inside the reserve, sub-second boundaries, zero/expired,
   sequential wait consumption and pending-terminal recovery. Include a valid terminal
   operation inside the reserve, so an always-refuse helper cannot pass.

This is **docs only**: docs/agents/, docs/evals/agents/ and your branch handoff. A pure budget
spec under docs is allowed; no src/, tests/, scripts/, migrations, UI, public contracts,
lockfiles, model/data artifacts, central coordination, new dependency, install or provider
call. No need to rerun the full backend/browser suite. Check draft exports/examples, the
15 dev cases, budget checks, Ruff, links/anchors and all protected bytes. Preserve the
15 current schema shapes unless the correction truly requires a reviewed shape change.

CaseDetail must continue to include all historical case runs: the draft's fresh-case
counts are not a filter to implement. Record this clarification without changing v1.1.

Commit explicit owned paths; sole author and committer PHANI465 <pgavara1@asu.edu>, no
coauthor/AI/session trailers. Return the exact tested SHA, actual checks and remaining
limits. Nothing is merged/frozen and G3B is not dispatched until Codex accepts the design.
