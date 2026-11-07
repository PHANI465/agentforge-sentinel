# AN01-M1: report-query prototype, safe stage controller and tiny proofs

Recommended coding assistant: **Claude Opus 5.5 / High**. Exact SQL semantics, bounded
supervision and late-connection ownership require careful tests. Sentinel investigators
stay deterministic; no live provider, auth/account call, final cases or spending.

## Accepted design and base

Read current `task/coordination:AGENTS.md`, STATUS/TASK_QUEUE and
`docs/reviews/AN01-r31-2db42ee.md` with git show. The accepted design is the **Codex-corrected
r3.2** in docs/analytics/AN01-decisions-r3.md, not unchanged2db42ee. In particular it has
pre-connect resource reservations, C4/C5 separated controls, and a whole-stage supervisor.
Read the r2 report/known-answer documents and padded table as well.

Create one task/claude-an01-m1-prototype worktree from current accepted main, record its
exact resolved SHA and source references, and keep all accepted/proposal/Cursor checkouts
untouched. One editor owns it. Read-only advisor agents may help review SQL or ownership;
do not have concurrent writers in another agent's checkout.

## Deliver code and actual tiny-fixture evidence

Own new scripts/benchmark_reports.py, optional new scripts/report_benchmark_support.py,
tests/test_report_benchmark.py, optional tests/support/report_benchmark_worker.py,
docs/benchmarks/AN01-M1.md and a branch handoff. Production src, public contracts,
migrations/grants, locks/dependencies, UI, CI/skip policy, checker timeouts, existing
lifecycle/benchmark helpers and central STATUS/TASK_QUEUE are protected.

1. Implement the seven complete report operations as a tagged SQL registry against the
   existing schema. Include guard/consistency/result and actual driver/control templates,
   ordered operation digests and parameters. Respect tenant/session on every relation
   and join, distinct time bases, ingestion cutoff, currencies/exponents, integer-string
   money, genuine zero versus unknown outcomes, daily boundaries and stable keyset order.
   Verify r2 known answers and foreign scopes on real disposable PostgreSQL. Include tiny
   23/25-hour day cases: the July-to-October timing distribution does not itself cross DST.
2. Create deterministic contract-valid operator fixtures and explicit owned stage/run
   records/checkpoints. The owner only provisions data/schema/index variants/sessions;
   report SELECT/EXPLAIN work uses the restricted runtime identity and read-only snapshots.
   Do not issue read_report or add a route: capabilities/HTTP S1 are not implemented yet.
   Prototype intended HTTP outcomes must be labelled as prototype classifications.
3. Implement a measurement-only budget/lease adapter with recorded provenance to the
   accepted code. Do not patch the live production module/global registry. Report B starts
   after acquisition; rollback has its own reserve; resource admission atomically reserves
   before connecting, and retired leases retain the reservation until final close. Prove
   healthy/error/pending-close/late-return interleavings, no double close/release, and
   isolation from workflow quarantine. Unknown stays unknown. No COMMIT or report mutation.
4. Implement complete-operation measurement and separately labelled EXPLAIN diagnostics,
   common cross-platform index selection, mandatory-evidence checks and matched-design
   comparison at selected N*. Code the full pre-registered grid, but do not execute it.
   Keep first results, refusals, failures, unknowns and unstarted cells; no silent reruns,
   post-hoc limits or statements changing after their measured digest is recorded.
5. Implement the independent whole-stage monotonic supervisor and owned lifecycle. The
   work/wait deadline covers blocked connect, COPY/index setup and EXPLAIN, not just SQL
   reply waits. Reuse accepted process/cluster identity mechanisms; record pending launch
   before inspection and refuse foreign/stale/missing identity. No kill-by-name or broad
   deletion. Stop only verified owned workers/clusters; if unconfirmed, keep recovery and
   block new stages. Do not call a bounded wait proof that a process stopped.
6. Prove C1 refusal before submission separately from C2 server cancellation, C3 lock wait
   and C4 withheld-reply retirement using real owned Postgres/relay where applicable. C5
   is an explicitly injected final-close delay: hold 2 leases, refuse the third admission
   before connect, release once, drain and allow a fresh request. Do not disable socket
   shutdown, fabricate counters or wait forever to force a result. Use barriers/events,
   intercepted negative signals and finally cleanup, with no assertion/timeout weakening.
7. Add stage/checkpoint/source-digest/recovery tests, including a deliberately stalled
   connector/worker and incomplete mandatory cells. Include resource preflight for the
   actual target volume (and relevant WSL backing-space limits); no automatic deletion,
   installing, resizing or changing settings to make space. Public reports/logs must not
   contain tokens, DSNs, local usernames/paths, raw driver exceptions or model data.

The supervisor's production-size constants remain as accepted: no new work after 2300 s,
whole-stage work/wait deadline 2350 s, cleanup reserve 300 s, controller deadline 2650 s,
outer safety cap 2700 s. Tests/smoke may use explicitly labelled **smaller** budgets and
tiny synthetic sizes; do not change any application's or existing verification's limits.

## Verification boundary: implementation and tiny smoke only

Do not run D1/D2 large datasets, 200k/800k/1.36m grids, a full staged benchmark or any
multi-hour measurement. This assignment cannot accept 200,000 rows / 5,000 ms ms or freeze v1.3.
Run focused tests and one bounded tiny end-to-end smoke on Windows, then native Ubuntu,
using the same code/statement identities. All real DB/relay/browser/load/full-gate jobs
share one heavy slot. Record actual elapsed time and volume; tiny figures are plumbing
evidence only. Diagnose failures and preserve them rather than rerunning until green.

Commit explicit owned paths as PHANI465 <pgavara1@asu.edu>, sole author and committer,
no trailers or history rewriting. Certify the final clean SHA with the existing six-command
Windows/native gates sequentially, same-run JUnit/exact one-skip validation, frozen HTTP,
package and read-only ML checks. No product browser rerun is needed without UI changes.
Hand off exact SHA, statement registry/digests, failing-first/fixed proof, actual tiny-run
results, cleanup and gaps. Codex reviews the controller and resource evidence before a
separate full-size measurement assignment. No main merge, remote/push or deployment.
