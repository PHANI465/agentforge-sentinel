# Handoff: task/cursor-analyst-ui

- Task and acceptance criteria: U01 analyst workbench in `web/` and `docs/ui/`, then U02 after accepted C02 and U03 after accepted C07. U01 waits for Codex acceptance of the C01 HTTP contract. Without that acceptance, the deliverable is a UI design note that names the missing contract.
- Tool and worktree: Cursor, `E:\PHANI\sentinel-wt\cursor-analyst-ui`.
- Updated: October 23, 2026, UTC-7.
- State: blocked. No accepted C01 contract commit.
- Code reference tested before this note: base `9e49a87b2a7d50c0fdcc3823cd87a07e49a856ae` (`task/coordination`). This note and `docs/ui/U01-design.md` are the task changes. No application code.
- Final check evidence: run the strict helper after the documentation commit; record the result in the final chat / ignored local report. This note does not claim its own commit SHA.
- Owned/changed paths: `docs/ui/U01-design.md` and this handoff note. `docs/STATUS.md` and `docs/TASK_QUEUE.md` were not edited.

## Implemented

- Opened `task/cursor-analyst-ui` from coordination commit `9e49a87b2a7d50c0fdcc3823cd87a07e49a856ae`.
- Read `git show task/coordination:docs/TASK_QUEUE.md`, `docs/STATUS.md`, `docs/reviews/0a6fb0e.md`, decisions 0002, 0003 and 0005, and `docs/CONTRACTS.md`.
- Recorded the missing contract in `docs/ui/U01-design.md`: Codex has not accepted a C01 commit. Reviewed `0a6fb0ec8e63fd686ac7e4cf6bbfb7bd22a105b0` is changes-requested. Candidate `2e6c2329aafe28b2e7c31ef5078d554cb66ca529` was observed with `git log` / `git show` and is not accepted.
- Described the client behavior that will bind to the accepted OpenAPI snapshot, examples and error semantics, including in-memory tokens, inert rationale, 409 refetch, and one execution idempotency key after an ambiguous response.

## Verified

- Queue gate -> `git show task/coordination:docs/TASK_QUEUE.md` -> U01 blocked on accepted C01; C01 row is still `0a6fb0e` / changes requested.
- C01 branch tip -> `git log -1 task/claude-api-contracts` -> `2e6c2329aafe28b2e7c31ef5078d554cb66ca529`, parent `0a6fb0e`. No Codex acceptance record for that SHA.
- Worktree -> `git worktree list` -> this checkout is `task/cursor-analyst-ui` at the coordination base. Claude worktrees were not edited.
- UI build, typecheck, component tests and browser tests -> not run. There is no `web/` app.

## Not verified / gaps

- No accepted HTTP contract, so no typed client, proxy, screens or fixture-backed tests.
- U02 and U03 are not started. C02 and C07 remain unaccepted.
- Candidate `2e6c232` was not retested here. Claude’s reported R9/R10 results are not Cursor or Codex acceptance.
- Strict project checks for this documentation commit are reported after the commit, outside this note.

## Next action

When Codex accepts a C01 commit, implement U01 in `web/` against that exact commit and `docs/ui/U01-design.md`. If the accepted SHA differs from `2e6c232`, re-read its OpenAPI snapshot and examples before generating types.

## Coordination and provenance

- Dependency commit for implementation: none. Base for this branch: `9e49a87b2a7d50c0fdcc3823cd87a07e49a856ae`.
- No edits to `src/sentinel/`, `contracts/`, migrations, Python dependencies, STATUS or TASK_QUEUE.
- No AgentForge UI source was copied. No tokens, credentials or raw traces are in these notes.
