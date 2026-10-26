# Handoff: task/claude-browser-fixtures

- Task and acceptance criteria: C02 (docs/TASK_QUEUE.md, docs/prompts/CLAUDE_C02.md on task/coordination). Deterministic browser fixtures and a real test-server lifecycle on disposable PostgreSQL. Scenarios: approve/execute, rejection, expiry/reopen/fresh approval, stale revision, duplicate execution, cross-session denial, limited capabilities, deterministic provider failure, and a real restart. Tokens are delivered privately. No public seed/clock/token routes. Interface documented for Cursor.
- Owner: Claude Code. Accepted dependency: C01 at 2e6c2329aafe28b2e7c31ef5078d554cb66ca529.
- Tool and worktree: Claude Code, E:\PHANI\sentinel-wt\claude-browser-fixtures (branch task/claude-browser-fixtures)
- Updated: 2026-10-23
- State: R11/R12 follow-up ready for Codex re-review. 66214bb was CHANGES REQUESTED (docs/reviews/66214bb.md on task/coordination; R13 accepted). U02 stays gated until C02 is accepted.
- Code reference tested before this note: working tree on top of 66214bb466fe9810df5a306f12137606ba2c0251 (strict checks rerun after the follow-up commit; reported in chat)
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

- Junction/redirect rejection and locked-file recovery were verified on Windows only. The POSIX symlink path is written but unexecuted. The path guard does not defend against a concurrent adversary racing the filesystem.

- POSIX process handling is untested (`killpg`, `/proc` start time); no CI/Linux.
- No Playwright run. Cursor's U02 is the browser-side consumer, and Playwright trace masking of the token field is Cursor's responsibility (documented).
- A lost response is simulated at the browser/network layer, not inside the stack.

## Review correction: R11–R13 (on top of c3fd83d)

Changed paths: tests/support/browser_stack.py, tests/support/scenarios.py (prose only), tests/test_browser_fixtures.py (interface updates), tests/test_browser_fixtures_review.py (new), docs/api/browser-fixtures.md, this note. Production API and contracts are unchanged.

- **R11 (ownership):**
  - `start` always creates a fresh private `sentinel-browser-*` directory, under `--parent-dir` if given (replaces `--state-dir`). It never takes over an existing directory.
  - It writes a `.sentinel-browser-stack` marker holding a random owner value and the canonical path. The manifest (version 2) records both.
  - `load` rejects: a link/junction manifest or directory, a manifest outside the directory it records, a wrong directory name, and a missing or mismatched marker. All of this happens before any process or file action.
  - Deletion re-verifies ownership and refuses unexpected top-level entries or any link/junction in the tree. Python 3.11 `rmtree` can follow Windows junctions, which is why that check exists.
- **R12 (failure-safe cleanup):** `stop` returns `{ok, api_stopped, database_stopped, state_removed, errors}`, and the CLI exits 1 unless `ok`.
  - The directory (manifest with tokens, process identity, database files) is deleted only when both API and database are verified stopped and ownership still holds. Otherwise the recovery manifest is saved and kept.
  - A failed start follows the same rule: either fully cleaned and the original error re-raised, or `StackError(... recovery manifest kept at <path>)`.
  - An identity mismatch never kills a process: if the recorded PID's start time differs, nothing is terminated, and an API still serving on the port is reported as a failure.
- **R13:** the rejected scenario now says re-approval gives 409 `stale_case_revision`, asserted over real HTTP. The limited-capabilities wording says only denied executions are audited; a denied approval writes no audit event, also asserted.

Test-first evidence:
- On c3fd83d, `tests/test_browser_fixtures_review.py` gave 10 failed:
  - an existing directory was reused;
  - copied, forged and junction manifests were accepted (DID NOT RAISE);
  - an unexpected file was deleted;
  - the injected API-stop failure propagated after the state directory was deleted;
  - there was no `ok` result;
  - a failed start erased its manifest;
  - the prose said approval_exists / "all audited".
- The live re-approval already returned 409 `stale_case_revision`, confirming only the fixture text was wrong.
- That run used only pytest `tmp_path` subtrees. One expected orphan cluster from the injected-DB-failure case was stopped afterwards by its exact data directory. A `pytest-86` cluster belonging to another session was left untouched.
- After the fix: 23 passed (13 existing + 10 new), all real-process. Then: 0 stack postgres processes, 0 fixture API processes, 0 `sentinel-browser-*` directories in the user temp directory.

## Review follow-up: remaining R11/R12 (on top of 66214bb)

Changed paths: tests/support/browser_stack.py, tests/test_browser_fixtures_followup.py (new), docs/api/browser-fixtures.md, this note. R13 is unchanged; production src/, contracts/ and web/ are unchanged.

- **R11 (nested paths):** a `guard()` (ownership plus every existing critical child, i.e. `stack.json`, marker, `api.log`, `pg`, `pg/data`, must be a real entry resolving inside the owned directory) now runs:
  - in `load`;
  - inside `_cluster()`, so before every `pg_ctl` stop/start/status/restart;
  - before opening `api.log`, before each manifest rewrite, and before and during deletion.
  Loaded objects are re-checked at each boundary. Not-yet-created children are allowed at startup. This is stated as accidental-redirection protection, not race-proofing.
- **R12 (partial removal):** contents (`pg/`, `api.log`) are deleted first, each re-checked. Then the manifest, then the marker, then the empty directory. A failure in the first step keeps the marker and manifest (loadable; a plain retry finishes). A failure deleting the marker leaves a token-free marker-only directory, which `stop --manifest <same path>` finishes via `finish_marker_only`. That path accepts only a `sentinel-browser-*` directory containing exactly a marker recording that very directory. Ownership is never re-created.
- **R12 (database status):** `db_state()` returns running (status 0), stopped (status 3), absent, uninitialized (no PG_VERSION/postmaster.pid), or unknown (status 4, other codes, OSError, timeout). Unknown is never treated as stopped: `stop` keeps the state and reports `database: state unknown, not verified stopped`. `status` reports `database: unknown`. `restart_db` requires verified stopped/running.

Test-first evidence (all process calls intercepted; no real pg_ctl/API was started, stopped or queried):
- On 66214bb, `tests/test_browser_fixtures_followup.py` gave 14 failed, 3 passed:
  - `pg` and `pg/data` junctions accepted by `load` (DID NOT RAISE);
  - no boundary re-check;
  - a redirected `api.log` was opened without a guard (PermissionError);
  - locked `api.log`, locked pg file and injected partial removal each lost the marker (`ownership marker is missing` on retry);
  - marker-only leftover not handled;
  - status 1 and 4 treated as stopped (ok true), and OSError/timeout escaped;
  - uninitialized data still called pg_ctl.
- One test bug was fixed before counting: junction creation used `subprocess`, which the interception blocked; it now uses `_winapi.CreateJunction`.
- After the fix: 17/17 pass, and every junction case shows zero recorded process calls with the outside canary intact. The locked-file cases use real Windows sharing-violation handles in process-free owned trees.
- Real-process C02 suites (followup + review + fixtures): 40 passed. Afterwards: 0 stack postgres, 0 fixture API processes, 0 `sentinel-browser-*` temp directories.

## Next action

Codex: re-review the follow-up commit. On acceptance (with accepted U01), Cursor U02 consumes it. C05 proceeds separately from accepted C01.

## Coordination and provenance

- scripts/agent_check.py: only CHECK_TIMEOUT_SECONDS changed. C06 (task/claude-backend-ci) edits the CHECKS list in the same file; the hunks are separate, but the integrator should merge both.

- Production code is not imported from or changed by these fixtures; `fixture_app` is test-only, under tests/support/.
- No dependencies added; no credentials committed. Tokens exist only in the private manifest and are deleted on stop or failed start.
