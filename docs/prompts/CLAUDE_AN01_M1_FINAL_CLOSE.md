# AN01-M1: finish residual R56 interruption inside close

Recommended coding assistant: **Claude Opus 5.5 / High**. The change is small, but
interruption, ownership and exactly-once release need careful reasoning. No live provider.

Read current task/coordination:AGENTS.md, docs/STATUS.md, docs/TASK_QUEUE.md and
docs/reviews/AN01-M1-b54de1a.md with git show. Continue the existing
task/claude-an01-m1-prototype worktree from exact
b54de1a4ebb4401b2149035abaeac6678e95d64c. Preserve it, 5e0a578, 93583a and every failure.
No reset/amend/rebase and no restart of the previous implementation assignment.

R54 now closes; R53/R55/R57 remain closed. Nested post-rollback cleanup passes. The only
remaining correction is ReportConnection._do_close when conn.close itself raises
KeyboardInterrupt/SystemExit. Currently it bypasses except Exception and leaves one
held reservation but no registered connection/finalization owner.

1. Add maintained tests first on unchanged b54de1a. The independent unmasked probe
   has 10 passes and two intended assertion failures on each platform, no setup errors.
   Its source/results are canonical .agent/an01-m1-r3-review/; preserve them unchanged.
2. Retain an accountable owner and failed/unconfirmed close state before propagating
   either interruption class. Do not swallow interruptions, free an unconfirmed resource,
   close under a busy SQL user, touch workflow quarantine or release twice. A logical
   closed flag is insufficient if the physical close was interrupted. Safe retention
   until process exit is allowed; a retry must establish close before one release.
3. Keep controls: ordinary successful close, ordinary close failure, answered-rollback
   interruption, busy lease, and any safe explicit retry/release. Preserve error privacy.
4. Run focused maintained tests and the independent probes on Windows/native. Certify
   the final exact clean commit with the existing six-command Windows then native gates,
   same-run JUnit/exact one allowed skip, frozen HTTP/package and read-only ML checks.
   Keep resource-heavy work under the shared slot and sequential; no unrelated browsers.

This follow-up assigns **no new tiny timing pass or benchmark**. af6292f's registered
pair remains historical, including the Windows C2:400 miss; f00df8c's native miss and
the unexplained focused stall failure remain preserved. New script hashes must never
be applied to old records as if they were newly measured. State clearly that no new
smoke ran on the final-close correction. Full-size measurements and numerical limits
remain unqualified and unassigned.

Own scripts/report_benchmark_support.py, focused tests/test_report_benchmark_review.py,
docs/benchmarks/AN01-M1.md and your branch handoff. R54 evidence/SQL/controller code,
production src, process helpers, contracts/migrations/grants, data/model/evals, locks,
UI, CI/skips/checker limits and central coordination remain protected. Request a specific
scope change only if actually needed; do not refactor unrelated code.

All commits: PHANI465 <pgavara1@asu.edu> sole author/committer, no trailers/history rewrite.
Hand off exact SHA, actual tests/cleanup and remaining gaps. No main merge/push/deployment,
full grid, production clock change, auth/account/provider/final-case calls, new spending
or DOC01 edits. Codex reviews before integration.
