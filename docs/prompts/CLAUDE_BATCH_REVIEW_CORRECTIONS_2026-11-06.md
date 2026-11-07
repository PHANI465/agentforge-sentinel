# Continue the delivered batch: focused review corrections

Recommended coding assistant: **Claude Opus 5.5 / High**. This batch needs evidence
integrity and denominator checks, plus portable demo provenance. It does not need max
effort as a blanket setting. Sentinel's investigators stay deterministic.

The earlier repair/recapture follow-up is obsolete: delivery 830f018 already completed
that work. Read the current coordination instructions and both independent reviews:

- `task/coordination:docs/reviews/G3D-P4a-96293da.md` — R46/R47/R49, changes requested.
- `task/coordination:docs/reviews/Parallel-batch-830f018.md` — R48, plus scoped PERF01
  review and AN01's still-open contract decisions.

Use two agents if available and useful, one editor per existing task worktree:

| Worker | Branch/base | Assignment |
| --- | --- | --- |
| A | task/claude-g3d-p4a-tooling at 96293da | docs/prompts/CLAUDE_P4A_REVIEW_FIXES.md |
| B | task/claude-demo01-recorded-replay at 47b7cf1 | docs/prompts/CLAUDE_DEMO01_PROVENANCE_FIX.md |

Read named files with `git show task/coordination:<path>`; another worktree's files are
not your working copy. Keep delivered preview830f018, original AN01dd6518d, AN01-r2a8c164a,
PERF0159b0b54, accepted branches/main and Cursor's seven saved edits intact. No new
analytics backend/UI work is assigned; AN01 remains a draft pending explicit decisions.

The coordinator owns a private queue log. Code/spec/unit work may run in parallel; all
real database, recapture, load, browser and full-gate work uses **one heavy slot**, never
Windows and Ubuntu suites simultaneously. Workers return committed SHAs and focused
evidence rather than each repeating two complete suites.

After both fixes are ready, create a **new** task-only preview branch/worktree
`task/claude-batch-review-preview-r2` from exact
830f01864aec3ff94679cf068b598157c7ee4263. Merge the exact corrected P4a and DEMO01 tips;
record merge parents and any conflicts. This new preview intentionally includes P4a;
the preserved old preview did not. Do not modify protected paths to resolve a conflict.
No main merge, acceptance of a draft contract or remote operation is authorized.

Before expensive verification, run focused combined tests, both review probes, the
AN01 arithmetic checker and the demo validator/Chromium QA. Keep failed evidence and
diagnose a failure rather than rerunning unchanged code until green. Check introduced
commits and merges have PHANI465 <pgavara1@asu.edu> as sole author and committer with
no trailers, no amend/rebase/reset and no global identity changes.

Then certify the new clean combined commit once: full six-command Windows gate with
same-run JUnit and exact skip validation, HTTP export and read-only ML reproduction;
then the same native Ubuntu checks on exactly that SHA, sequentially. Use locked dev/ml,
live off and deterministic roles; preserve the 2700 s command cap and every individual
assertion/deadline/skip. Do not rerun product frontend/browser suites unless a real
change makes them relevant. Component focused evidence and combined exact-head full
evidence must be labelled separately; no transferred clean-head PASS claims.

Hand off exact worker/preview SHAs, source scope, actual results, old failures retained,
cleanup/recovery and limits. No provider/auth/account calls, live flags, final-case access,
new spending, paid fallback, deployment, push or changes to central STATUS/TASK_QUEUE.
Codex re-reviews before application integration.
