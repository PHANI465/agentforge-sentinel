# DOC01 Part A: re-review of 7ec46ae

**November 12, 2026 — changes requested for one remaining R58 race.**
Reviewed exact `7ec46aea258501389c0ce39b6315e0eed88f26f0`, descended from
preserved `cecccad` and `69b51fe` on `task/claude-doc01-extractor`.
The unreadable-`/proc` correction works, R59 stays closed, and the reused-PID
test now covers both layouts. Part A is not yet accepted or merged.

## R58 — a PID-list snapshot can miss a newly forked group member (blocking)

`tools/document_worker/src/docworker/supervisor.py` `group_members()` lists
`/proc` PIDs once and reads each listed entry. After the recorded leader has
exited, a surviving group member can fork another member **after that list is
taken** and then exit. The old member is gone or a zombie when read; the new
member is absent from the list. `_group_empty()` returns true, so `recover()`
deletes the recovery record while the group is still populated.

Independent native Ubuntu probe used a real session leader, member and forked
descendant. A test seam paused immediately after the real `/proc` listing,
then let the member fork and exit before recovery consumed the list. Result:

```json
{"result":"recovered","record_exists":false,"grandchild_alive":true}
```

The descendant was verified in the recorded process group and stopped by its
exact PID in probe cleanup. This is a feasible scheduling order, not a forged
group entry. A `/proc` snapshot alone does not prove the group empty. After
the scan, make an independent kernel group-existence check (for example a
non-signalling `killpg(pgid, 0)`), and retain the record on a live or unknown
group. Handle a reused group ID by keeping the record, not signalling it. The
test should make the fork-after-list order deterministic and fail before the
fix, then pass after it. Keep the unreadable-member and leader-alive guards.

## What closed in this revision

- The independent permission-fault probe now returns
  `group_state_unknown_kept` with the member alive and record retained. The
  original exit-7 child probe still returns `status: error`.
- Independent focused worker suites: **60 passed, 12 expected POSIX skips on
  Windows** and **72 passed, 0 skipped on native Ubuntu**. The revised
  reused-PID test passes under this native process-group layout.
- The author reports full worker tests **173 passed/12 skips on Windows** and
  **185 passed/0 skips on native**, smoke fidelity 259/259 and 101/101 on
  both, Windows app strict gate 810+one allowed skip, and HTTP/ML checks on
  both. The first Windows full worker run at code commit `b3c37d3` had a
  `test_crashed_supervisor_is_recoverable` startup-time failure under load;
  its cause is unproven and the author kept the failed log. Later author runs
  passed. No full app gate was rerun independently for this review.

Two new commits have PHANI465 as sole author and committer with no trailers;
changes stay in the worker, protocol and handoff. The candidate worktree is
clean, and no app source, contract, app lock or UI path changed. No DOC01
source was merged or pushed; no provider, upload or AN01 full grid ran.

Continue the existing branch under the [focused R58 race follow-up](../prompts/CLAUDE_DOC01_R58_RACE_FOLLOWUP.md).
Preserve all previous candidate commits and failure evidence, and return a
new exact tested SHA for Codex re-review.
