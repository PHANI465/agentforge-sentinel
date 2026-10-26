# Handoff: task/claude-operator-prep

- **Task:** C08 review corrections R24 and R26 (docs/prompts/CLAUDE_RELEASE_REVIEW_FIXES.md and docs/reviews/9ab183e.md on task/coordination 6c31516).
- **Tool and worktree:** Claude Code, E:\PHANI\sentinel-wt\claude-operator-prep (branch task/claude-operator-prep).
- **Updated:** 2026-10-25.
- **State:** ready for Codex re-review.
- **Dependency:**
  - previous C08 commit: 9ab183e836751a75e7a1a350afc51af7663f9a63;
  - refreshed with the accepted I02 f38e92023481a55db1ecf8bcdbe917140bd5d7cd as dependency-merge **b5ccb5214cdb304c0395bbbc4adfb43cf30bf692** (parents 9ab183e, f38e920);
  - clean automatic merge, no conflicts.
- **Code reference tested before this note:** the final working tree of this commit. Strict checks run after the commit and are reported in chat.
- **Owned/changed paths:**
  - `scripts/local_stack.py` (rewritten);
  - `tests/test_local_stack.py`, `tests/test_local_rollback_drill.py` (both new);
  - `tests/test_backup_restore.py` (all 14 current tables plus C07 operator data);
  - `docs/runbooks/local-operations.md`, this note.

  Not changed: production `src/`, contracts, migrations, p1 files, the UI, the lockfile and the checker. `docs/runbooks/staging-design.md` was rechecked: it makes no `local_stack`, table-count or log claim, so it is unchanged.

## R24 and R26 corrections (this commit)

- **Owned directory.** All state is in one directory with an ownership marker and a random owner value that must match `state.json`. Directories without it, such as the old 9ab183e layout, are never adopted. A private `--state-dir` is available for drills and tests.
- **Identity before any action.**
  - *API process:* the recorded PID, creation time and executable image must match. The venv `python.exe` is a launcher on Windows (measured: the `Popen` PID differs from the interpreter PID), so the port must be served only by the recorded process or its descendants. Windows uses a toolhelp snapshot and `GetExtendedTcpTable`.
  - *Postmaster:* `pg_ctl status`, then `postmaster.pid`, whose PID must run our `postgres.exe` for our data directory and port, and own the listener.
  - *Refusals:* a reused PID whose port is served, missing identity, a foreign API or database port, and unknown states are refused with no kill; the record is kept and the exit code is 1. A reused PID with a free port proves our process already exited, so its record is cleared without touching anything.
- **Truthful stop.** A stop is reported only after the process is gone and the port is closed, or for the database after `pg_ctl status` 3 and a free port. Otherwise the identity is kept and the exit code is 1. The database is not stopped under an unaccounted-for API. On startup failure, `up` stops only the verified API it started, confirms that and clears the record; if that cannot be confirmed, it keeps the recovery record.
- **Authority refresh.**
  - Owner connection: migrations, `roles.grant_runtime` (the C05 API, role `sentinel_local_runtime`), sessions, backup and restore. The API connects as the runtime role.
  - Capabilities: deliberate local analyst capabilities, where `read_case` covers scoring and results.
  - Scorer: explicit `--scorer rule|model`, with rule the default. Grant refusals are reported as operator errors.
  - Code: the API serves this checkout's code through `PYTHONPATH`.
- **R26 restore and rollback.**
  - `restore` refuses under a live API. It starts and verifies only the owned cluster, restores into a **new** database (refusing an existing name or the live one), and reports the tables and migration list. It neither migrates nor starts an API.
  - `up --database NAME` serves an existing restored database (and never creates a missing non-default one). It reuses the stored token when that token authenticates against the restored sessions.
  - The runbook's rollback and log claims were corrected. `api.log` holds structured per-request events and does not hold "startup errors only"; there are 14 tables, not 11.

## Verified (Windows 11, locked dev+ml, `SENTINEL_LIVE_CLAUDE=0`, deterministic, disposable Postgres)

- **Baseline on the old code** (b5ccb52 = 9ab183e `local_stack.py`, with destructive calls intercepted and no real kill): all four review defects reproduced.
  - A kill was requested for a reused PID.
  - The identity was cleared after a failed kill while health stayed up.
  - A foreign healthy API was adopted without starting ours.
  - `restore` after `down` failed with ConnectionTimeout before `CREATE DATABASE` and never started the database.

  Probe script: scratchpad `c08_baseline_probe.py` (not committed).
- **Process note:** for C08, the new `local_stack.py` was written before its committed regressions, against the requested test-first order. The baseline evidence above comes from the probe against the old interface; the new tests use the new interface.
- **`tests/test_local_stack.py`, 8 passed, through the real `main(argv)`:**
  - foreign directory not adopted;
  - reused PID with a served port refused with no kill; reused PID with a free port cleared with no kill;
  - missing identity refused;
  - foreign healthy API refused before any database work;
  - foreign database-port listener refused with no initdb or start;
  - failed stop: termination intercepted to fail, the real process stays alive, the identity is kept, exit 1; the retry gives a real verified stop of our own process and a free port;
  - startup failure (bad factory): the owned API is cleaned up and the database kept, then a real `down` verifies it stopped.
- **`tests/test_local_rollback_drill.py`, 1 passed (about 35 s), real processes and two code versions:** the previous tree, and the same tree plus `0005` (with its runtime grant).
  1. Previous code: `up`, `smoke` (closed, revision 4), `backup`, `down`.
  2. Next code: `up` applies 0005.
  3. `restore` is refused under the live API.
  4. Next code: `down`; ports free and database stopped.
  5. `restore` into `sentinel_rollback` reports migrations through 0004 only, with no 0005 table and no API started. The live database keeps 0005.
  6. Previous code: `up --database sentinel_rollback` reports none pending.

  All table counts, the case, its action, its audit IDs and the session rows equal the pre-upgrade backup. The original token reads the closed case and its 6 audit events, and the scorer is rule. No token or `postgresql://` appears in any output or `api.log`. A final `down` leaves both ports free.
- **`tests/test_backup_restore.py`, 1 passed:** 14 tables, inventory pinned, including profiles and disclosures.
- **Manual real CLI run** (temporary state directory, ports 8093/55493):
  - `up`: 4 migrations, API up in rule mode;
  - `smoke --restart-api`: alert, then a verified API stop and restart, then the action succeeded with `retry_replayed=True`, 6 audit events and the case closed at revision 4;
  - `status`: both owned, exit 0;
  - `down`: both verified stopped;
  - `status`: exit 1.

  `api.log` contains the token 0 times and `postgresql://` 0 times. The directory was removed afterwards.
- **Cleanup:** no leftover test Postgres or Python processes (checked by command line).

## Not verified / gaps

- **POSIX:** the lifecycle path (`/proc`, `killpg`) is implemented to fail closed but was not run. There is no Linux, CI or hosting.
- **Timing gap:** between an identity check and a kill, an exited process's PID could be reused within the same instant. Creation-time matching makes that unlikely, but the window is not closed atomically.
- **`--investigator claude-cli`:** not exercised (no live calls).
- **Model mode:** `up --scorer model` serving was not separately smoke-run here; C07 and I01 cover model serving.
- **Restore failure:** a partial `pg_restore` leaves the new database for manual drop, and the error says so.

## Next action

Codex: re-review R24/R26 at the final C08 SHA reported in chat.

## Previous evidence (9ab183e, kept as history)

- Task and acceptance criteria: C08 local work (docs/TASK_QUEUE.md). A reproducible local API/Postgres setup; a migration/upgrade/rollback runbook; synthetic smoke commands; a restricted staging design with deterministic investigations; actual local startup/teardown and persistence evidence; explicit unverified items; no owner model key in deployment configuration. Hosting stays gated.
- Owner: Claude Code. Accepted dependency: task/coordination at fcc04c5. The branch name was chosen here because the queue names none.
- Tool and worktree: Claude Code, E:\PHANI\sentinel-wt\claude-operator-prep
- Updated: 2026-10-23
- State: ready for Codex review
- Code reference tested before this note: working tree on top of fcc04c5 (strict checks rerun after the commit; reported in chat)
- Owned/changed paths: scripts/local_stack.py (new), tests/test_backup_restore.py (new), docs/runbooks/local-operations.md (new), docs/runbooks/staging-design.md (new), this note. No changes to service/API/migrations/web/.

## Implemented

- `local_stack.py`: `up`, `status`, `down`, `smoke [--restart-api]`, `backup`, `restore`.
  - Native Postgres (Docker is not required); state under git-ignored `.agent/stack/`; dev token stored in a file and never printed.
  - Deterministic investigator by default; the API is detached with health polling.
- Runbooks: local operations (start/stop, smoke, forward-only upgrade with backup-based rollback, backup/restore, troubleshooting) and a restricted staging design with a hosting-verification list and release checklist.

## Verified (manual, Windows 11, PostgreSQL 14.17, 2026-10-23)

- `up` initialized the cluster, applied 0001 and 0002, issued a session and started the API; `status` returned 0.
- `smoke --restart-api`: alert, investigation (`awaiting_approval` 3), API process killed (health false), new process; then execute succeeded with an identical replay, six audit events, `closed` 4.
- `backup` wrote a custom-format dump. `down` gave `status` 1. `up` again applied nothing pending, and the earlier case read back as `closed` 4 after the full stack restart.
- `restore` into `sentinel_restored`: row counts equal in all 11 tables; an audit UPDATE was rejected.
- Automated: `tests/test_backup_restore.py` passed (equal counts including sessions, no pending migrations, audit DELETE rejected, the restored database serves the case to the same token).

## Not verified / gaps

- Linux/macOS process handling in `local_stack.py` (`killpg` path) is untested.
- No container setup (the Docker daemon was unavailable). No hosted provisioning, hosting limits not checked (listed in the staging design). No least-privilege role yet (C05).

## Next action

Codex: review C08. The owner decides when to verify hosting limits and authorize staging.

## Coordination and provenance

- Uses migrations 0001–0002 from the base. C01's 0003 applies automatically through `up` after integration.
- No dependencies added. No credentials committed; the token file is in ignored `.agent/`.
