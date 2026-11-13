# DOC01 Part A: close the remaining R58 group race

Recommended coding assistant: **Claude Opus 5.5 / High**.

Read current `task/coordination:AGENTS.md`, STATUS, TASK_QUEUE and
`docs/reviews/DOC01-7ec46ae.md` with `git show`. Continue the existing
`task/claude-doc01-extractor` worktree from exact
`7ec46aea258501389c0ce39b6315e0eed88f26f0`. Preserve `cecccad`,
`69b51fe` and `7ec46ae` as ancestors; no reset, rebase, amend, second editor
or task-branch push. R59 and the unreadable-entry R58 fix are closed; keep them.

Write a failing-first native test with a real owned session leader and group
member. After the leader exits, let recovery list the real `/proc` PIDs, then
make the member fork a descendant and exit before recovery consumes the list.
The descendant must remain in the recorded group. Recovery must not return
`recovered` or delete the record while that descendant lives, and must never
signal a group whose ownership is unproved. After the test stops its own
verified descendant, a fresh retry should complete cleanup. Avoid sleeps as
the deciding condition; gate the fork and check exact PIDs/group identities.

Make recovery confirm group emptiness at the kernel boundary **after** its
`/proc` scan. A non-signalling group-existence query such as
`os.killpg(pgid, 0)` can conservatively catch members created after the
snapshot. A live, inaccessible or reused group means keep the record. Do not
assume a failed `/proc` read means an entry vanished. Prove the positive case
where the group really has emptied, and the earlier unreadable-member,
leader-alive, reused-PID, Windows job and R59 behaviours still hold.

Own only `tools/document_worker/**`, its protocol note if clarification is
needed, and the branch handoff. No app code/contracts/dependency changes,
DOC01 upload/UI, LLM/OCR, AN01 full grid or live provider work. Run the
worker's locked focused and full tests and bounded smoke on Windows then
native, serially. Recheck the app identities/gates needed for this change,
retain failed-first and any intermittent-failure evidence, and report exact
clean-commit results. Commit as PHANI465 <pgavara1@asu.edu> sole author and
committer, no trailers or history rewrite. Hand off a final SHA for review;
do not merge or push the task branch.
