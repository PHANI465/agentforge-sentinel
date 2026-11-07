# AN01 proposal revision: R50–R52 before report-query measurement

Recommended coding assistant: **Claude Opus5.5 / High**. Local/UTC boundary conversions,
deadline scopes and a pre-registered measurement schedule need precise reasoning. No max
effort blanket setting and no change to Sentinel's investigator/model configuration.

Read current `task/coordination:AGENTS.md`, STATUS, TASK_QUEUE and
`docs/reviews/AN01-r3-b436c5e.md` with git show. Continue only the existing
task/claude-an01-decisions worktree from exactb436c5e7dc369680a3b15605b96046e1a2913b4d.
Preserve that commit; no reset/amend/rebase, new implementation worktree or edits to main,
accepted checkouts, original probes or Cursor's seven saved changes.

Own the existing AN01 proposal/table/doc-checker paths, their r2 pointer lines and your
branch handoff. This is still documentation/stdlib checker work. Do not edit src, scripts,
public contracts, migrations, grants, dependencies/locks, UI, CI, skip rules, timeouts or
central STATUS/TASK_QUEUE. No SQL measurement or AN01-M1 implementation is assigned yet.

Address the review as one coherent revision:

1. R50: distinguish the allowed UTC request domain from the padded local-midnight lookup
   range. Cover containing days and next-midnight sentinels for all five zones at both
   UTC edges, including NY1999-12-31 and Kolkata/Tokyo2038-01-02 sentinel needs. State
   validation after date-mode conversion; no silent extrapolation, clamping or negative
   lookup index. Update the table/digest, derivation and checker. Add meaningful boundary
   checks that expose the old coverage gap, preserving r2 known answers and daily bounds.
2. R51: enumerate complete report operations and all their SQL/control statements, hashes,
   repetitions and EXPLAIN accounting. Base cap decisions on full report work under one
   budget, not individual statements. Reconcile setup/measurement/cleanup with unchanged
   command caps, or spell out bounded staged commands and owned recovery. Pre-register
   one cross-platform index choice and its staged schedule. Missing mandatory evidence
   means not demonstrated. Replace the id-only JSON attribution with a justified matched
   comparison or an explicitly non-causal diagnostic, at the correct selected size.
3. R52: reconcile connection acquisition with the existing synchronous open_connection
   and the SQL-only bounded-call path. Narrow the budget claim or specify a genuinely
   separate bounded-connect design; no production implementation is required. Specify
   report phase/reserve, finite admission/quarantine and cleanup ownership. The short
   refusal controls and submitted cancellation/lock/withheld-reply controls must be
   separate and feasible under the helpers'2 s connection and100 ms statement minimums.

Apply the supported policy decisions: opt-in v1.3 with explicit strict-legacy-client
incompatibility for new-capability sessions; separate selectable capability values from
the unchanged four default grants; unsigned256-character cursor with coherent strict
counts; five-minute **receipt-age** nudge labelled Received, with server read_at separate.
The cutoff is for ingestion timestamps, not commit availability. These are proposals
being refined, not permission to change the frozen API or implement Reports.

The independent probe source/results are in canonical ignored `.agent/an01-r3-review/`.
Read/copy evidence; do not modify it. Demonstrate new coverage checks against the old
table/source without counting import failures as useful failures. Preserve old evidence.
Run r2/r3-or-current doc checkers, manual Windows/native table re-derivation and Ruff.
Validate links/anchors and scope. Full backend/browser gates and actual load runs are
unnecessary for this documentation-only revision; do not start them.

Commit explicit owned paths as PHANI465 <pgavara1@asu.edu>, sole author and committer,
no trailers or history rewriting. Hand off exact SHA, actual checker/probe results,
policy changes and remaining provisional values. No provider/auth/account calls, final
cases, new spending, remote/push, hosting or deployment. Codex reviews before AN01-M1
gets a separate concrete assignment.
