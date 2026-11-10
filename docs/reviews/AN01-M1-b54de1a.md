# AN01-M1 re-review: b54de1a — R54 closed; one residual R56 path

November 10, 2026 (America/Phoenix). Exact candidate
**b54de1a4ebb4401b2149035abaeac6678e95d64c** remains clean, preserved, unaccepted and
unmerged on task/claude-an01-m1-prototype. Its code is af6292f; b54de1a adds docs only.
The two commits preserve earlier candidates and have PHANI465 as sole author/committer,
with no trailers. The diff from 5e0a578 stays within the six assigned paths.

## Independent evidence

- Separate exact-candidate Windows checkout, offline locked dev/ml environment, real
  disposable PostgreSQL: **150/150 focused maintained tests pass**, zero skips. Pytest
  174.29 s; outer command 230.494 s. Same-run JUnit retained. These are different intervals.
- Original adapted 14 probes pass 14/14 on Windows and native. The earlier disclosed
  read_at fake-field adaptation is unchanged; original source/failures stay preserved.
- **12 additional independent probes:10 pass,2 assertion failures,0 setup errors on
  each platform.** A complete synthetic positive evidence fixture qualifies controls
  with no missing/failed C2 cell. Six independent mutations then reject contradictory
  medians, empty C5, submitting C1, false D maximum, unseen C4 and wrong EXPLAIN statement.
  Thus C1/C5/D cannot pass merely because the real tiny records already failed C2.
  Normal close and both post-rollback-reply interruption cases also pass. Only the two
  interruption-inside-close variants fail, described below. These probes use no SQL,
  process signals or benchmark; synthetic fixtures are not measured run records.
- Focused Ruff passes with --no-cache; diff checks and independent checkout cleanliness
  pass. An initial Ruff attempt could not create its sandboxed cache; --no-cache resolved
  that tool setup issue without source changes. It is not a test failure or a code fix.
- I inspected author exact-b54de1a metadata and independently validated both saved JUnit
  reports: **961 cases, 960 passed, one allowed live-Claude skip, 0 failures/errors**,
  validator exit0. Both metadata records show all six commands exit0 and clean trees.
  Saved HTTP/ML results are author evidence; I did not independently rerun full gates.
- No product browser, native real-DB focused/full suite, full-size benchmark, provider,
  auth, training or deployment. Heavy Windows tests ran under the shared slot, released
  on completion. No review-owned PostgreSQL remains. Other checkouts/Cursor edits stay
  untouched. Independent native work is a new owned offline clone.

## Disposition

**R54 closes for the reviewed prototype scope.** Summary reconciliation/derived values,
control-specific diagnostics, EXPLAIN validation and mandatory-cell rejection address
the previous counterexamples. The loader discards invalid D measurements, so its report
can show missing evidence without the raw-input maximum trigger; this is disclosed and
fails qualification safely. It does not make invalid evidence demonstrated.

**The post-rollback-reply part of R56 closes.** Nested finalization now closes the idle
connection after either KeyboardInterrupt or SystemExit, releasing once. R53/R55/R57
remain closed for their prior scopes. One residual final-close interruption below still
blocks closing R56 and accepting the package.

## R56 — P1: interruption inside close loses the retained cleanup owner

Source at b54de1a: scripts/report_benchmark_support.py:894–913, ReportConnection._do_close.
close_normal and retry_close enter that function with close_state=closing. It catches
Exception, marks close_failed, and registers the connection. KeyboardInterrupt/SystemExit
inherit BaseException, so they bypass that branch. Neither the new outer nested finally
nor _do_close registers an owner for this unconfirmed close.

Independent fault injection: after a normal successful read and answered ROLLBACK,
the test-owned connection's close raises KeyboardInterrupt or SystemExit before closure.
The exception correctly propagates, but both platforms observe:
**close_calls=1, closed=false, resources=(0,1), quarantine=0**.
The positive close control reaches(0,0); post-rollback interruption controls now do too.
No SQL user is running. The request exits without returning Outcome, so the reservation
is stranded and the failed/unconfirmed connection has no retained quarantine owner.
These are controlled connection faults, not a claim that a real socket leaked in this probe.

Retain an accountable connection/finalization owner and explicit failed/unconfirmed-close
state before propagating an interruption in close. Preserve KeyboardInterrupt/SystemExit;
do not swallow them or free the reservation just to restore capacity. Confirm actual close
before release, or retain bounded ownership until process exit. A logical closed flag
alone is not proof when close itself was interrupted. Keep ordinary close-error handling,
busy leases, one release and workflow-quarantine separation intact.

Add maintained failing-first regressions for both interruption classes and positive
controls. An explicit retry may release once only after confirmed close; if that cannot
be established, safe retention is acceptable. No timing-policy or measurement change is
needed for this cleanup defect. Use [the final-close dispatch](../prompts/CLAUDE_AN01_M1_FINAL_CLOSE.md).

## Preserved failures and unqualified work

The author's af6292f tiny pair has one Windows C2:400 miss and S9=not demonstrated.
It is not retried. The earlier f00df8c native C2:1250 miss also remains failed. None of
the new review checks qualifies 30 ms,200k rows,5000 ms,250 ms or M/Q 2/2. Original full-grid
4 GB/backing-space refusals and the separate production-clock question remain unchanged.

The author's earlier Windows focused run had 149 passes and one stall-test failure;
the author reports about 10 s of setup startup delay but no established cause. It remains
preserved. It passed in both author gates and this independent 150-test run; those passes
do not explain or replace that failure. Do not label its cause proven or silently retry it.

## Evidence and next step

Private independent records: canonical .agent/an01-m1-r3-review/, review checkout
.agent/codex-review/, native ~/codex-an01-m1-r3-review/.agent/codex-review/.
The unmasked fixture/probe source is retained. Actual author smoke/gate files remain
untouched under .agent/an01-m1-r3/ in the Claude worktree. Candidate code is not merged.
Finish only the residual close guard before Codex re-review; DOC01 stays a separate later
worktree and no new timing smoke/grid is assigned by this review.
