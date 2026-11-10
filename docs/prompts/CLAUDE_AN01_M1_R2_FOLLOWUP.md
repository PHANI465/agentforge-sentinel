# AN01-M1 final focused follow-up: remaining R54 and R56

Delivered at b54de1a; [re-review](../reviews/AN01-M1-b54de1a.md) closes R54 and post-rollback cleanup. Continue only [the final-close dispatch](CLAUDE_AN01_M1_FINAL_CLOSE.md). The original assignment below is history.

Recommended coding assistant: **Claude Opus 5.5 / High**. Evidence qualification and
interrupt-safe connection ownership need careful reasoning; no live model/provider usage
is needed. Use existing allowance; no paid overage.

Read current task/coordination:AGENTS.md, STATUS, TASK_QUEUE and
docs/reviews/AN01-M1-5e0a578.md with git show. Exact delivered candidate is
5e0a578be91b7739e5d08fc315dc37504f0df188 on existing task/claude-an01-m1-prototype,
E:/PHANI/sentinel-wt/claude-an01-m1-prototype. Preserve it and 93583a; no reset/amend/rebase.
Do not restart implementation. R53/R55/R57 are closed for that review scope; retain them.

## Complete the two residual corrections

1. **R54:** make the four review counterexamples fail safely through the public evidence
   loader/rule path. Derive or reconcile median/max summaries against the registered timed
   measurements. Validate control-specific evidence rather than trusting proved/status or
   a nonempty C5 list. Preserve correct C1-C5 evidence, expected run counts, finite values,
   statement/EXPLAIN identities and per-stage/source/profile/platform/selection bindings.
   An incomplete or contradictory record cannot qualify a selection or a mandatory cell.
   Do not edit old captured records or replace a failure with a later success.
2. **R56:** close or transfer every acquired connection even if ROLLBACK's wait is
   interrupted after its worker replied. Both KeyboardInterrupt and SystemExit must
   propagate; an idle connection cannot be left with reservation 1, close_calls 0 and no
   owner. Retain busy-lease behavior, failed-close reservation/retry, one final release, and
   separation from the workflow quarantine. Use nested finalization or another explicit
   ownership scheme; do not swallow interruption or close under a running SQL thread.

Independent originals are canonical .agent/an01-m1-r2-review/. The eight new probes
give six assertion failures/two controls, zero errors, on Windows and native; original 14
pass with the disclosed one-field read_at fake adaptation. Preserve originals. Add
maintained regressions first on unchanged 5e0a578; distinguish assertion failures from
setup errors. Keep source/candidate/failure evidence and document any probe adaptation.

## Scope and verification

Own the two prototype scripts, the two benchmark test modules, docs/benchmarks/AN01-M1.md
and your branch handoff only. Production src, accepted process helpers, contracts, migrations,
grants, model/data/evals, deps/locks, UI, CI/skips, timeouts and central coordination are protected.
No full-size grid, production clock fix, margin/reserve borrowing, disk-limit change, provider/
auth/account/final-case calls, push/deployment or new spending. DOC01 remains a later
isolated assignment; do not mix it into these fixes.

Run maintained focused tests and the independent probes. This follow-up explicitly
registers **one new tiny validation pair after the code correction**, Windows then native,
all stages once with one source/statement identity set, no cell retries. It validates the
changed evidence/cleanup implementation; it does not replace the earlier timing failure
or qualify a limit. Preserve every new miss as failed/not demonstrated; do not issue an
extra pass. Keep B/R/work_end and provisional 30 ms policy unchanged. Old smoke records
remain historical and cannot be rebound to changed script hashes.

Certify a final clean commit with the existing six-command Windows then native gates,
same-run JUnit/exact one allowed skip, frozen HTTP/package and read-only ML checks. All
DB/relay/browser/load/gate work holds the shared heavy slot and stays sequential. Keep
all assertions/timeouts; don't rerun unexplained failures until green. Record actual
counts, SHA, source identities, tiny outcomes, cleanup and gaps. No unrelated browser rerun.

All commits: PHANI465 <pgavara1@asu.edu> sole author and committer, no trailers or history
rewriting. Hand back exact SHA for Codex re-review; no main code integration or acceptance.
