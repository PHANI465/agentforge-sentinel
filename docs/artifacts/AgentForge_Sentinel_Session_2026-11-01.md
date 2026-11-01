# AgentForge Sentinel November 1 checkpoint

## Latest checkpoint: trace API accepted; trace UI is next

**G3C-A 16b67fd0cd09cdd08bbfa64a159035a7a188bf5b is accepted and HTTP v1.2 frozen**.
The independent final review passed 95 Windows tests and three native tests for real HTTP
authorization, repeatable read during recovery and database read-only enforcement. Three
additional Postgres probes passed on each platform: partial usage reporting with unknown
attempts, reported 0/0 remaining zero, and tool-followup as another attempt 1 rather than
a provider retry. No live provider was used. Both supplied full gates were verified at
clean exact 16b67fd: 580 passes, one allowed skip, 581 cases and all six commands passed.
The native non-login PATH failure is retained as setup evidence, not counted as success.

The accepted dependency remains on its task branch. **No G3C application code has been
merged into main**; its current runtime is still accepted G3B a7c71f5. G3C-B uses exact
16b67fd so it has the real trace API. Contract SHA-256:
b52f8fd4d323f59565b3e1148557cb85221b76c793377e021c32f9c877e5b053.
The sixteen examples and all earlier frozen assets stay unchanged.

Next: [G3C-B trace UI](../prompts/CLAUDE_G3C_TRACE_UI.md), Claude Opus 5.5 / High, in a
new isolated worktree. Show the stored roles/tools/claims, partial data, history and
unconfirmed recovery honestly; preserve human approval and request/session isolation.
New real browser tests are required; the old 19 cover only existing UI. Codex reviews
before combined API/UI integration. Two small doc corrections are queued for that merge:
UUID-validation/permission-check ordering and SETUP's active HTTP version. No backend
contract change is requested. [Final API acceptance](../reviews/G3C-A-16b67fd.md).

G3C-B has not started; no trace UI or live agent-quality result is complete. The broader
[overview and remaining work](AgentForge_Sentinel_Overview_and_Remaining_Work.md) stays
current. Manual-evaluator least privilege, populated workflow backup and a three-role
convenience CLI remain follow-ups. Original Cursor files and accepted branches are
preserved. New commits use only the owner identity. No push, hosting or new spend.
Earlier entries below are historical checkpoints, not the current assignment.

## Previous checkpoint: G3C-A candidate delivered, gates in progress

Candidate 16b67fd0cd09cdd08bbfa64a159035a7a188bf5b implements the read-only trace route
and a new HTTP v1.2 response. It is not yet accepted or integrated. The Windows owner
gate was running at this checkpoint; native Ubuntu and frontend/browser final results
remain pending. Codex independently passed 23 pure contract tests and Ruff and checked
four HTTP validation-order scenarios. No independent new Postgres suite or duplicate
full gate was run while Claude's full run was active.

The read model distinguishes missing data, running/overdue/recovered workflows and role
attempts versus provider calls. Legacy v1/v1.1 bytes, agents-1.0, G3B, UI, migrations,
model/data and dependency files remain preserved. A small permission/validation-order
documentation correction is queued for integration. The ignored native runner needs
fail-closed setup and real status aggregation before its wrapper can be trusted as a gate.

Next: finish [the existing Claude gates](../prompts/CLAUDE_G3C_GATE_COMPLETION.md), using
Opus 5.5 / High, preserving the tracked candidate. Return its complete exact-commit report;
Codex then finishes independent DB review and freezes the contract before the trace UI.
See [preliminary review](../reviews/G3C-A-16b67fd.md). Main's tested application remains
G3B a7c71f5; no G3C UI, live comparison, push or hosting is complete. The earlier entries
below describe the accepted G3B release and its original G3C dispatch, not a new dispatch.

## Summary first

The local three-role backend is **accepted and integrated**. R34-R37 are closed.
Tested application commit: **a7c71f553328b5872df53039daf572ad3b8fda81**, combining current
coordination with accepted candidate e23a7cd automatically. Both native Ubuntu and canonical
Windows pass their full gates: **539 tests passed, one allowed skip, 540 cases**. Windows
also passes 44 frontend tests/typecheck/build and all 19 real browser/API/Postgres tests.
The final documentation publication has identical application/test/dependency assets.
No live model was called and G3C has not started.

## What happened today, in order

1. Read Claude's exact R37 handoff and four-file correction; preserved its clean worktree.
2. Inspected connection/SQL/cancel/socket lifetime ownership and confirmed the coordinator
   replaces retired connections. Confirmed a known COMMIT keeps its known outcome.
3. Corrected independent probe A to honor retirement before reuse, as the accepted remedy
   allows. It still fails on b74473e for the original missing retirement. Probe B exercises
   actual native socket reuse. All six native probes and 90 focused Windows cases pass.
4. Verified the candidate owner strict metadata and exact native 540-case full report;
   checked frozen contracts, metadata, unchanged assets and Cursor preservation.
5. Accepted R37 and automatically merged exact e23a7cd as a7c71f5 with sole-owner identity.
6. Ran integrated gates sequentially. The initial Windows runner mistakenly disabled all
   logging and caused eight logging-sensitive tests to fail. Reproduced that setup error and corrected
   only the external runner; retained the first report, then ran the full standard gate.
7. Verified canonical Windows strict/JUnit/HTTP/ML/frontend/browser and native Ubuntu full
   backend/JUnit/HTTP/package/ML checks on the same clean integration. No new skip/timeout
   or application change was used to obtain the pass.
8. Published [the release record](../releases/G3B-main-integration-2026-11-01.md), current
   overview/queue and [next Claude trace API assignment](../prompts/CLAUDE_G3C_TRACE_API.md).

## Next actions

Use **Claude Opus 5.5 / High** for G3C-A in a new worktree from current published main.
Deliver only the additive trace contract/read API and reproducible fixtures; Codex reviews
before the UI consumes them. No trace UI or new live evaluation is implemented yet.
The earlier evaluator least-privilege split and populated workflow backup remain preparation
for measured agent evaluation/operations. After G3C, run explicitly authorized quality
comparisons, deepen the analyst workspace, and plan public demo/CI/hosting separately.

The [current overview](AgentForge_Sentinel_Overview_and_Remaining_Work.md) explains the
project with a fraud-review example. Four major product workstreams remain after this
backend gate: trace API/UI, measured agents, analyst depth and public operational release.
Optional G5 research extensions are additional, not a fixed completion percentage.

Existing unexplained b74473e timing/retry failures are still disclosed; no root cause is
claimed. Provisional per-process budgets do not prove production scale or live quality.
All current data/actions are synthetic/simulated. Sole-owner commit metadata and original
Cursor seven edits remain preserved. No paid usage, provider call, remote, push or hosting.
