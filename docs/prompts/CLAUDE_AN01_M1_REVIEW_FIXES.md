# AN01-M1 corrections: R53–R57 on the existing prototype branch

Delivered correction5e0a578 has been re-reviewed. **Continue [the R54/R56 follow-up](CLAUDE_AN01_M1_R2_FOLLOWUP.md)**; R53/R55/R57 are closed for that scope. The original assignment below is preserved history.

Recommended coding assistant: **Claude Opus 5.5 / High**. Process ownership, faulted
connection lifetimes and timing/evidence invariants need careful reasoning. Use existing
allowance; no paid overage. Sentinel providers stay deterministic and no auth/account call.

Read current task/coordination:AGENTS.md, docs/STATUS.md, docs/TASK_QUEUE.md and
docs/reviews/AN01-M1-93583a.md using git show. The review is binding for this correction;
the original r3.2 design applies where not clarified. Do not reimplement or make a new
branch/worktree that discards the delivered work.

Existing branch/worktree: task/claude-an01-m1-prototype at
E:/PHANI/sentinel-wt/claude-an01-m1-prototype. Preserve exact candidate
93583a7570ae78f254a2d69e9857b701b0e444ad and its ancestors, with no reset/amend/rebase.
Inspect actual HEAD/status and preserve unfamiliar changes. One editor owns this checkout.

## Complete all five corrections

Own the existing scripts/benchmark_reports.py, scripts/report_benchmark_support.py,
tests/test_report_benchmark.py, docs/benchmarks/AN01-M1.md and your branch handoff.
Optional focused test additions under tests/test_report_benchmark_review.py are allowed.
Production src (including budget.py and clock.py), accepted process helpers, contracts,
grants/migrations, data/model/eval assets, deps/locks, UI, CI/skip policy, checker limits,
central STATUS/TASK_QUEUE and the original Cursor checkout remain protected.

1. **R53:** controller identity plus invocation-bound exclusive recovery. Refuse a live
   or uninspectable controller, including the acquire-lock/pre-worker gap. Recovery must
   not kill its worker or remove its lock. Test actual stage/recover entry points; use
   intercepted negative signals and only verified owned processes for positive cleanup.
   Demonstrate a truly dead controller can recover, stale/reused identity does not grant
   authority, and a racing second recovery/stage cannot steal the slot.
2. **R54:** typed complete evidence/provenance validation, immutable first outcomes and
   source/profile-bound selections. Require expected outcome counts and finite values;
   empty BG timed lists do not qualify a cap. Reject mixed source/SQL/setup/zone/profile
   records, incompatible platform pairs, conflicting duplicate cells and invalid or
   unqualified selection consumption. Instrument rollback duration and implement the
   pre-registered reserve trigger. Unknown required metrics mean not demonstrated.
3. **R55:** recheck the actual remaining budget after arming and immediately before SQL.
   Never launch report work with expired/subminimum budgets; zero wait must not start a
   worker. Classify actual late arrival honestly despite delayed waiter wake-up. Force
   both answered and no-reply branches with deterministic tests, retain real controls
   and strict benchmark cells. Keep B/R/work_end and 30 ms provisional margin unchanged;
   no reserve borrowing or margin increase is assigned. A strict timing miss can remain
   not demonstrated; never rerun it into a pass or label a late reply on time.
4. **R56:** acquired connection ownership must cover on_connect/hook failures. A failed
   close must not free its reservation or masquerade as a successful final close. Keep
   an accountable owner/recovery state until actual close/process exit; release once.
   Test close exceptions and hook exceptions plus healthy, late-return and retry paths.
   Preserve interruption semantics and the separate workflow quarantine.
5. **R57:** a fully answered report survives an unanswered readonly rollback; an incomplete
   read never fabricates data. Use the actual snapshot-bound read_at consistently in SQL
   and DTO, keep explicit as_of separate, and handle default cutoff/cursor binding. Test
   the real adapter/report path with delayed acquisition and bounded rollback failure,
   not only a mocked already-shaped body.

Codex's independent probe source and initial/final platform results are preserved privately
under E:/PHANI/agentforge-sentinel/.agent/an01-m1-review/. Reuse them unchanged where their
interfaces still apply; disclose any adaptation and its purpose. The final probe set has
14 cases: 11 intended assertion failures and 3 passing controls on both platforms. Add
maintained regression tests first, demonstrate meaningful failing-first results on 93583a,
then fix the code. A setup/import error is not defect evidence.

## Scope and verification

No production clock fix is assigned for R-M1-2. Keep the 4 GB and backing-space preflight
refusals for R-M1-3; no automatic deletion, installs, WSL changes or grid reduction. The
full-size experiment still needs a separate reviewed storage/scheduling plan.

Run focused maintained tests and the independent probes; preserve negative results.
Run bounded tiny smoke only on Windows then native, with all stage/selection records
bound to the same corrected source/statement identities. Do not combine old f00df8c
records with new code. If a required control misses, keep the failed cell and its full
record; do not retry that cell or issue a third unregistered pass. Tiny evidence may
honestly remain not demonstrated. No full grid or --authorized-full-size.

Commit explicit owned paths as PHANI465 <pgavara1@asu.edu>, sole author and committer,
no trailers, no history rewriting. Certify the final clean commit with the existing
six-command Windows then native gates, same-run JUnit/exact one allowed skip, frozen
HTTP, package and read-only ML checks. Keep 2700 s cap and every existing app/test/skip
boundary. All DB/relay/browser/load/full-gate work holds the one heavy slot sequentially;
after interruption verify processes/recovery before clearing an owned stale lock.

Update the write-up/handoff with exact fixes, timing policy, statement/source digests,
actual final-code tiny results, failure evidence, cleanup and gaps. Do not promise a
numerical limit or claim full-gate success validates incomplete measurements. No main
merge, push/remote, deployment, provider/auth/account/final-case work or new spending.
Codex reviews the exact corrected SHA before integration or another assignment.
