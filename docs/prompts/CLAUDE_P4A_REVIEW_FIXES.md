# P4a review corrections: R46, R47, R49

Completed and accepted under [the November7 re-review](../reviews/Batch-r2-10a65ee.md).
This is a historical assignment; do not restart it or rerun delivered work automatically.

Recommended coding assistant: **Claude Opus 5.5 / High**. These changes affect evidence,
human-review denominators and stored-versus-reported recommendations; careful invariant
and real-database testing matters. Sentinel investigators remain deterministic.

Read current `task/coordination:AGENTS.md`, STATUS, TASK_QUEUE and
`docs/reviews/G3D-P4a-96293da.md` using `git show`. Work on the existing
`task/claude-g3d-p4a-tooling` checkout at exact 96293da1a3403bb1d9bf9eb7c669354b2089c5be.
Preserve the original commits: no reset, amend, rebase or edits to another checkout.
The original P4a assignment's ownership still applies. This correction owns its artifact,
scoring/export helpers, associated tests, P4a documentation and branch handoff. It does
not own production source, frozen protocol/cases, contracts, UI, locks, CI or timeouts.

Implement all three findings in one owned branch:

1. **R46:** write failing-first tests for a wrong D03 hold relabelled as refused with
   consistent counts, and a complete record with a censored suffix moved to not-attempted.
   Reject contradictory version-1 status/outcome/accounting. Add valid incomplete/unknown/
   unavailable-telemetry controls; do not infer a request's outcome from later state alone.
   Preserve the first actual outcome, wrong-hold 0/1, and R41/R42 attempt rules.
2. **R47:** validate review-sheet choices, unique item identities and binding to the
   generated packet material. Test partially answered recommendation fields, correction
   only, invalid/duplicate rows and supported + not-checkable. Use the frozen protocol's
   common rubric denominator; blank must never become no. Either refuse incomplete input
   explicitly or expose honest partial/per-metric answered and missing counts. Keep blank
   templates unscored and CSV/model text inert. Do not rewrite the protocol.
3. **R49:** use real deterministic database records to prove the exported disposition
   agrees with the adopted stored single-run or workflow result, including basis, operation,
   reason and claim counts where recorded. A known `escalate` changed to `hold` in JSON
   must refuse before producing a packet. Cover revision/abstention and missing telemetry;
   do not silently rewrite outcomes or use the owner identity for export.

The independent probe sources are in canonical ignored
`.agent/batch-review-2026-11-06/`; copy/read them, never change that evidence. Keep the
maintained tests meaningful and demonstrate their relevant failures on original source.
Do not add crypto/tamper-proof claims for editable unsigned artifacts. Unknown remains
unknown and workflow elapsed remains not measured.

Run focused evaluator/pilot/export/scoring and authority/failure regressions in your own
locked environment. Use only test-owned databases. No real Claude executable, auth/account
call, `--allow-live`, final cases, provider work, paid overage or automatic retries.
Keep evidence private and sanitized. Preserve cleanup/recovery and stopped pilot data.

Commit explicit owned paths as PHANI465 <pgavara1@asu.edu>, sole author and committer,
no trailers. Hand exact corrected SHA, failing-first/fixed evidence, cleanup and gaps to
the batch coordinator. Under the parent correction batch, full Windows/native certification
is consolidated on one new combined preview after both workers finish; do not claim that
an individual branch SHA inherited that preview's exact-head full gate.
