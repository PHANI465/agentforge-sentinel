# DEMO01 correction: R48, history-independent freshness

Completed and accepted under [the November7 re-review](../reviews/Batch-r2-10a65ee.md).
This is a historical assignment; do not restart it or rerun delivered work automatically.

Recommended coding assistant: **Claude Opus 5.5 / High**. Preserve provenance and
privacy checks while making freshness reliable in a clean/shallow checkout.

Read current `task/coordination:AGENTS.md`, STATUS, TASK_QUEUE and
`docs/reviews/Parallel-batch-830f018.md` using `git show`. Continue the existing
`task/claude-demo01-recorded-replay` branch at exact
47b7cf150b2faf01e8ac3030b520d0cdb5c30e71. Preserve all prior commits and author captures.
Do not edit the delivered preview, PERF01, P4a or Cursor's checkout.

Own only the existing DEMO01 script/test/demo/docs paths and branch handoff.
R48 requires capture freshness to remain checked when the recorded commit is absent
from local history. Record and verify reproducible content identity of the generator
and relevant application inputs, or an equally concrete history-independent mechanism.
Check the actual checkout bytes, not just hashes copied between two metadata fields.
Retain commit provenance as provenance rather than making its local presence a skip.

Write failing-first coverage for missing Git history, changed generator/application
content, missing/malformed provenance, and unchanged content. The normal structured gate
must still allow exactly one live-Claude skip; do not edit CI or the allowlist, substitute
an unconditional pass, fetch history over a network, or weaken the freshness check.
Keep the native account-name privacy fix and hostile-text/action-boundary assertions.

If the capture/provenance bytes need regeneration, use one owned deterministic recapture
in the coordinator's heavy slot; keep old failed reports/capture evidence. Run validator,
focused tests and the standalone Chromium QA (existing install, no download) on the new
capture. Preserve label honesty, simulated actions, secret scanning and owned cleanup.

Commit explicit owned paths with PHANI465 <pgavara1@asu.edu> as sole author and committer,
no trailers and no history rewriting. Return exact SHA and honest checks/gaps. The parent
batch consolidates full strict Windows/native gates on a new combined preview; individual
branch commits do not inherit its exact-head certification. No live provider, auth/account,
final cases, paid overage, external remote/push, hosting or deployment.
