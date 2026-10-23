# Handoff: task/claude-operator-prep

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
