# G3C-A preliminary review: 16b67fd

November 1, 2026 (America/Phoenix). Candidate **16b67fd0cd09cdd08bbfa64a159035a7a188bf5b**
is a clean direct child of accepted main b69b8bc. Owner-only author/committer metadata and
no trailers are verified. **Not accepted or frozen; final gates and independent database
review remain pending. G3C-B must wait.** Main's application remains accepted G3B a7c71f5.

## Scope checked so far

Read the complete projection and response types, route integration, contract revision,
selection/recovery semantics and focused-test coverage. The read uses one REPEATABLE READ
READ ONLY transaction, scope predicates and typed projection; workflow ordering uses the
monotonic case revision and prior workflows remain selectable. Analyst checks and provider
submission are not invented. Running counters are null; terminal counts are stored values.
Legacy workflows, role repeats/revisions and incomplete recovery have distinct projections.
The different HTTP read DTO is justified without modifying frozen agents-1.0 types.

No blocking implementation finding has emerged from this limited review. This is not a
completed independent database review or permission to merge. In an isolated checkout with
its own locked dev/ml environment, **23 contract tests pass**, Ruff passes, and four
no-database HTTP validation-order scenarios produce the results below. Current full test
collection is **581 cases**; this is a collection count, not a passing-gate claim.

Independent Git comparisons show no changes to legacy v1/v1.1 snapshots/examples,
agents-1.0, migrations/grants/G3B machinery, model/data/evals, UI, dependencies/lockfiles,
CI/skip policy or checker timeout. The two live-schema assertions now target v1.2 while
v1.1 is frozen by hash; this is a versioning change, not removed compatibility coverage.
Claude reports 79 pre-commit focused passes; those are not independent final-commit results.

## Low: the documented error-check order differs from framework validation

The table in docs/api/investigation-trace-v1.2.md puts read_case permission before UUID
validation. With a successfully authenticated read-less session, malformed case_id or
workflow_id returns **422 invalid_request** before the endpoint checks capabilities. A
valid UUID returns **403 permission_denied**. Missing authentication still returns **401**,
even with a malformed path. These four cases were exercised through the production app's
TestClient with a controlled authentication stand-in and no database access.

This does not expose a case or bypass authorization. Correct the documentation ordering
when the contract is finalized; no backend permission change is needed. Do not edit the
candidate during its running checks just for this documentation detail. Codex can include
the correction in the integration documentation. SETUP's active-v1.1 sentence likewise
needs changing when v1.2 is accepted; it is still correct for current main today.

## Verification-harness note, before native execution

The candidate's ignored .agent/g3c/linux_gate.sh records individual statuses but uses only
set -u. Setup failure can fall through, and the final echo normally makes the wrapper exit
0 even if a check failed. This is not a product-source finding and does not invalidate a
valid individual report, but **wrapper exit 0 alone is not a green gate**.

Before using it, fail setup immediately on wrong directory/clone/fetch/checkout, unexpected
HEAD or a dirty tree; verify native tools and the unprivileged user. Aggregate the actual
check statuses (including pipelines) into the final exit. Independently require strict.json
passed at exact candidate/clean before+after with six successful checks, the matching JUnit
allowlist, HTTP/model results and final cleanliness. An ignored runner can be corrected
without changing the tracked candidate. Never rerun a finished suite solely to make XML.

## Still required

Finish the already-running Windows strict gate, then validate its own JUnit with
ci_test_gate.py --validate-only PATH, run HTTP export and read-only ML reproduction. Run
native Ubuntu sequentially in the separate owned g3c-trace-contract clone, preserving the
accepted a7c71f5 checkout. Finish frontend/typecheck/build and the existing 19-browser
compatibility suite; they do not verify a trace UI. Keep source at 16b67fd unless a real
failure needs a new owner-authored commit; preserve failed evidence and diagnose it.

Codex has deliberately not started a duplicate full backend run, another database suite
while the owner run is active, a merge, a trace UI or a model call. After the final handoff,
complete independent trace/real-Postgres checks and inspect all exact-commit reports
before accepting/freezing v1.2. Current continuation:
[Claude gate completion](../prompts/CLAUDE_G3C_GATE_COMPLETION.md).
