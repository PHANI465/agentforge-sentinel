# G3A revision 2 review: feb80d1

October 31, 2026. Reviewed exact **feb80d19cac6c91844d8c7490a7e04e1b1b246d1** on
`task/claude-g3a-design`, direct parent 06a7c0c; application base f091a34.
**Decision: one remaining R31 deadline correction; not frozen or merged.** No production
bug is claimed here: the workflow is still a documentation-only proposal.

## Closed findings

- **R32 closed.** The workflow terminal transaction is independent of an active role;
  zero-role and between-role examples preserve true completed statuses, reopen without
  intent and distinguish coordinator/system audit actors. An intent requires an eligible
  completed investigator from the same workflow. The abstain example now cites that run.
- **R33 closed for the reviewed invariants.** Exact role membership, measured usage,
  lifecycle/actor/time and step failure invariants reject the reproduced contradictions.
  Cross-record constraints are explicitly assigned to the coordinator. The evaluation
  clarification and zero-denominator/failure-count reporting are incorporated.
- **R31 capacity portion closed.** Two distinct leases bound admitted workflows and
  outstanding provider-call workers; unresolved workers retain their slots, no timed-out
  call is repeated, and late outputs are discarded. These are accepted design rules,
  not implemented or measured runtime guarantees.

## Remaining R31 blocker: the terminal reserve disables its own bound

Candidate `docs/agents/G3A-design.md:117-124` says **every coordinator/tool transaction**
uses `min(db_wait_seconds, remaining - terminal_reserve)` for lock/statement timeout,
while the terminal write must run inside that reserve. With the pinned defaults:

| Remaining seconds | Reserve | Derived timeout seconds |
| --- | --- | --- |
| 6 | 5 | 1 |
| 5 | 5 | 0 |
| 4 | 5 | -1 |
| 0 | 5 | -5 |

Those last three are not finite positive waiting budgets. PostgreSQL explicitly defines
zero `statement_timeout` and zero `lock_timeout` as disabling the timeout, rather than
refusing to wait. The statement limit applies to each statement; the lock limit applies
per lock acquisition. See the primary
[PostgreSQL 16 timeout documentation](https://www.postgresql.org/docs/16/runtime-config-client.html#GUC-STATEMENT-TIMEOUT).

The fixed five-second `connect_timeout` also cannot fit a terminal attempt with only four
seconds left. A connection limit followed by several independently bounded statements is
not a bound on their combined duration. libpq applies the connection limit separately to
each host, and a value of one second is interpreted as two; see
[libpq connection timeout semantics](https://www.postgresql.org/docs/16/libpq-connect.html#LIBPQ-CONNECT-CONNECT-TIMEOUT).
No live database/provider call is needed to expose the arithmetic contradiction.

**Required narrow correction:** define separate working and terminal operation budgets,
using a common absolute/monotonic deadline with persisted wall-clock metadata. The terminal
phase must not subtract its own reserve. Refuse operations when no positive budget remains;
never convert exhausted time to PostgreSQL's disabling zero, a negative value or an unsafe
round-up. Specify units explicitly. Recompute the remaining budget across connection,
locks, statements and commit; account for the connection driver's actual granularity and
per-host behavior, or require an already-open bounded connection/another explicit policy.

If the terminal write cannot safely start or its outcome is uncertain, do not claim a
committed terminal state or report a successful completion. Preserve the durable running
workflow for the already-designed recovery path and specify the request outcome honestly.
Preserve the call-lease lifetime even when terminal persistence fails.

Add a small executable *design-budget* check under docs (not a runtime implementation):
inside/at/outside the reserve, sub-second rounding and exhausted budgets, sequential waits,
and the no-safe-terminal/recovery path. Verify a genuinely valid positive terminal budget
inside the reserve; rejecting all terminal operations would not fix it.

Finally reconcile the two protocol statements: the latency table currently allows
`150 s + terminal reserve`, while security gate 5 requires the reserve **inside 150 s**.
Use one explicit definition consistently and distinguish an elapsed-wait policy from an
unproven wall-clock/commit guarantee. No limit increase, dependency or runtime work is needed.

## Implementation notes, not additional blockers

- Existing v1.1 CaseDetail returns **all historical runs for a case**. The draft's empty
  and three-to-five-run examples describe a fresh case/this workflow; G3B must not hide
  earlier runs after retries just to match those illustrative counts.
- Local subprocess timeout/worker-lifetime claims still need the adapter evidence listed
  for G3B. No provider-side cancellation, exactly-once billing or measured quota claim is
  accepted. Process-local call caps do not claim a cross-process provider concurrency cap.

## Independent checks on the clean candidate

| Check | Actual result |
| --- | --- |
| Draft export/examples | 15 current schemas; 35 valid / 50 invalid as labelled |
| Development catalog | 15 cases consistent with real sentinel.scoring; runtime three-role implemented in 0 |
| Ruff, both new Python doc trees | Passed |
| Five Markdown documents: relative links and heading anchors | No broken links/anchors |
| Original R33 regressions | All 14 accepted by unchanged 06a7c0c models, rejected by revision 2 |
| Actor-specific variants | All 3 rejected by their specific lifecycle contradictions |
| Independent usage combinations | 54 checked, all coherent with the stated policy |
| Independent role subsets | All 8 checked; only the complete role map accepted |
| Additional lifecycle negative controls | 6 rejected; valid zero-role terminal remains accepted |
| Exact parent/scope/identity | Direct 06a7c0c child, 54 owned doc paths, owner-only author/committer, no trailers |
| Deadline counterexamples | Remaining 5/4/0 produces 0/-1/-5, as above |

One reviewer-harness setup assertion initially included the three actor variants in the
14 baseline files. Corrected the selection before recording the passing results; no
candidate file was edited. No full backend, browser, database or provider run was needed.
Evidence is saved locally under canonical `.agent/g3a-review/feb80d1/` after publication.
Candidate and Cursor's original seven edits remain preserved. Main application remains
f091a34; prior full backend results remain c8b9477 and are not relabelled as current runs.

## Next action

Use [the narrow R31 follow-up](../prompts/CLAUDE_G3A_DEADLINE_FOLLOWUP.md),
**Claude Opus 5.5 / High**, for the remaining deadline/lifecycle reasoning. Preserve R32,
R33, all lease rules and existing schema bytes unless a justified change is required.
Do not implement G3B or start final evaluation until the corrected design is accepted.
