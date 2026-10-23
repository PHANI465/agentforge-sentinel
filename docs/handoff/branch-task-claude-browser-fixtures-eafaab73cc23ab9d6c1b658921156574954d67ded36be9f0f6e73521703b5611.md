# Handoff: task/claude-browser-fixtures

- Task and acceptance criteria: C02 (docs/TASK_QUEUE.md, docs/prompts/CLAUDE_C02.md on task/coordination). Deterministic browser fixtures and a real test-server lifecycle on disposable PostgreSQL. Scenarios: approve/execute, rejection, expiry/reopen/fresh approval, stale revision, duplicate execution, cross-session denial, limited capabilities, deterministic provider failure, and a real restart. Tokens are delivered privately. No public seed/clock/token routes. Interface documented for Cursor.
- Owner: Claude Code. Accepted dependency: C01 at 2e6c2329aafe28b2e7c31ef5078d554cb66ca529.
- Tool and worktree: Claude Code, E:\PHANI\sentinel-wt\claude-browser-fixtures (branch task/claude-browser-fixtures)
- Updated: 2026-10-23
- State: ready for Codex review; on acceptance it is the backend dependency for Cursor U02 (with U01)
- Code reference tested before this note: working tree on top of 2e6c232 (strict checks rerun after the commit; reported in chat)
- Owned/changed paths: new tests/support/browser_stack.py, tests/support/scenarios.py, tests/support/fixture_app.py, tests/test_browser_fixtures.py, docs/api/browser-fixtures.md, this note; modified scripts/agent_check.py (per-command timeout 300 -> 900 s: the full pytest run now takes about 301 s). No changes to src/sentinel/, contracts/, migrations, web/ or docs/ui/. The HTTP contract is untouched.

## Implemented

- **`browser_stack.py` (CLI + `Stack` library):** `start`, `seed`, `restart-api`, `restart-db`, `status`, `stop`.
  - Fresh initdb cluster and migration; seeding; the production API in a real uvicorn child (random loopback ports); readiness polling with a timeout.
  - Failure-path cleanup: everything started is stopped and the token manifest deleted.
  - Targeted termination only: the recorded PID tree, after checking PID + process start time; Postgres via `pg_ctl -D`. Stops are verified (process gone, port closed, `pg_ctl status`), and the private state directory is removed.
- **`scenarios.py`:** 11 scenarios and 4 sessions, seeded through the real service methods (plus SQL rows for the two same-scope limited/second-actor sessions).
  - Deterministic UUIDv5 IDs per label and ordinal.
  - Expiry comes from seeding with a service whose clock is 10 minutes behind, so there are no sleeps and no clock in the API.
- **`fixture_app.py`:** the production `create_app` with a deterministic fixture investigator, which fails `provider_unavailable` for amount 777777 only. No model or network call.
- **docs/api/browser-fixtures.md:** commands, manifest fields (tokens marked secret), sessions table, per-scenario exact responses and transitions, restart semantics, token-hygiene requirements for Playwright, limits.

## Verified (working tree before the commit, Windows 11, PostgreSQL 14.17, `SENTINEL_LIVE_CLAUDE=0`)

- `tests/test_browser_fixtures.py`: 13 passed (real sockets to a real uvicorn process). Coverage:
  - documented states; foreign-session 404s; read_only/second_actor 403s audited;
  - live provider failure (failed run, open rev 3, no intent; the retry fails again) and seeded failed-run recovery (rev 5);
  - expiry: 409, then open rev 4, re-investigate rev 6, fresh approval executes, the old approval gives 409;
  - replay and rejection; stale revision 409;
  - concurrent duplicate execution: two 200s, one `replayed:false`, one database row;
  - `restart-api` (new PID, old PID verified gone, replay identical) and `restart-db` (state and audit identical);
  - repeatability: a second fresh stack via the CLI had identical scenario/session IDs and different tokens, and no token appeared in CLI stdout/stderr;
  - failed starts (never-ready app, missing factory) left no running cluster and no token file.
- **Cleanup mutation check:** with failure-path cleanup disabled, both failed-start tests failed. The orphaned clusters and API processes from that run were stopped by exact data directory and command line, and the code restored.
- **Process check after the runs:** 0 fixture postgres processes, 0 fixture API processes, 0 leftover `sentinel-browser-*` directories.
- CLI smoke: `start`, then `status` from a separate process (up/up), 11 scenario states as documented, `stop` (all true; directory removed).

## Not verified / gaps

- POSIX process handling is untested (`killpg`, `/proc` start time); no CI/Linux.
- No Playwright run. Cursor's U02 is the browser-side consumer, and Playwright trace masking of the token field is Cursor's responsibility (documented).
- A lost response is simulated at the browser/network layer, not inside the stack.

## Next action

Codex: review C02. On acceptance, Cursor U02 consumes this commit (after U01). Claude then starts C05 from accepted C01 in its own branch, per CLAUDE_C02.md sequencing.

## Coordination and provenance

- scripts/agent_check.py: only CHECK_TIMEOUT_SECONDS changed. C06 (task/claude-backend-ci) edits the CHECKS list in the same file; the hunks are separate, but the integrator should merge both.

- Production code is not imported from or changed by these fixtures; `fixture_app` is test-only, under tests/support/.
- No dependencies added; no credentials committed. Tokens exist only in the private manifest and are deleted on stop or failed start.
