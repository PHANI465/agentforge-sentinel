# DOC01 Part A: final R58 recovery follow-up

Recommended coding assistant: **Claude Opus 5.5 / High**.

Read current `task/coordination:AGENTS.md`, STATUS, TASK_QUEUE and
`docs/reviews/DOC01-69b51fe.md` with `git show`. Continue the existing
`task/claude-doc01-extractor` branch from exact
`69b51fe5dfaea68275e0c9463edceb5f2525bf15`. Preserve `cecccad` and
`69b51fe` as ancestors. No reset, rebase, amend, second editor or task branch.
R59 is closed for its reviewed scope; leave that correction intact.

Write a failing-first native regression with a real owned session leader and
live group member. After the leader exits, inject a permission error when
reading only that member's `/proc/<pid>/stat`. `recover()` must return an
unknown/kept result, retain the record and run folder, send no signal, and
succeed only after the test stops its own verified member and the read fault
is removed. Also cover a non-ENOENT I/O error and malformed stat data; a
genuinely disappeared entry may be skipped. Keep the safety property under
repeated fresh-supervisor retries. Document any platform limitation honestly.

Correct the existing reused-PID test so it proves no unrelated process is
signalled under both process-group layouts. If pytest itself is group leader,
`group_members_alive_kept` is the safe result; make the setup or expectations
explicit and deterministic. Preserve Windows job behaviour, leader-alive
group stopping, fail-closed unknowns and the original R59 tests.

Own only `tools/document_worker/**`, its protocol note if needed, and the
branch handoff. Do not edit app source, contracts, dependencies outside the
worker, central coordination, AN01, ML or UI; do not start upload/feedback,
OCR, LLM work or the AN01 full grid. Run the worker's locked focused and full
tests and bounded smoke on Windows then native, serially. Recheck the app
strict/HTTP/ML identities as needed; preserve failed-first logs and exact
clean-commit outcomes. New commits: PHANI465 <pgavara1@asu.edu> as sole
author and committer, no trailers and no history rewriting. Hand off the
final SHA for Codex review; do not merge or push this task branch.
