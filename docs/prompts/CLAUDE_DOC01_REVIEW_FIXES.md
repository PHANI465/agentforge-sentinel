# DOC01 Part A: R58/R59 correction

Recommended coding assistant: **Claude Opus 5.5 / High**. These fixes cross
process identity, cleanup and the untrusted child-result boundary. Sentinel's
test investigators stay deterministic; no live model call is needed.

Read current `task/coordination:AGENTS.md`, STATUS, TASK_QUEUE and
`docs/reviews/DOC01-cecccad.md` with `git show`. Continue the existing
`task/claude-doc01-extractor` worktree from preserved exact
`cecccadfaad6f2cde0cd42543517685fa0235ea8`. Do not reset, rebase or
amend its commits. One editor only; preserve AN01-M1 and Cursor worktrees.

## Required corrections

1. **R58, POSIX recovery:** write a failing-first real-process test in which a
   recorded parser leader exits and a member of its process group survives.
   Call `recover()` from a newly loaded supervisor. It must keep the recovery
   record and owned run directory and must not report success or signal a
   process it cannot prove is owned. After the test itself stops its verified
   member, a retry should complete cleanup. Keep Windows job behaviour and
   reused-PID refusal intact. Investigate the related case where the leader
   is still alive and `kill_pid` stops it while a member survives. Reuse the
   accepted process-identity and cleanup conventions; do not kill by name.
2. **R59, child output:** write failing-first tests for a child that emits a
   syntactically valid `complete` JSON and exits nonzero, and one that emits a
   minimal `complete` JSON with required result fields missing. The
   supervisor must return an error rather than a successful extraction.
   Validate enough of the frozen v0.1 result shape and status relationships
   to make later consumers safe, while allowing valid partial, unsupported
   and protocol-error documents. Keep source bytes and driver errors out of
   returned details and logs. Test the genuine worker child as a positive
   control.

Keep changes within `tools/document_worker/**`, the worker protocol document
if its wording needs clarification, and the branch handoff. Do not edit app
source, contracts, migrations, dependency locks outside the worker, UI, CI,
central STATUS/TASK_QUEUE or frozen AN01/ML assets. Do not begin DOC01 API/UI
upload, OCR, LLM narrative, model training or full-size AN01 measurement.

Run the worker's locked tests and bounded smoke on Windows and native Ubuntu,
serially; verify the original 15 supervisor tests and the new regressions.
Recheck worker and app identities and the application strict/HTTP/ML gates
needed for this correction. Preserve failed-first logs, exact final-commit
results and cleanup evidence; do not report an interrupted or skipped run as a
pass. Keep the explicit OS-isolation gaps. Commit only explicit owned paths as
PHANI465 <pgavara1@asu.edu> sole author and committer, with no trailers and no
history rewriting. Hand off the final SHA for Codex re-review; do not merge or
push the task branch.
