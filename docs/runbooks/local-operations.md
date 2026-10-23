# Runbook: local API + Postgres operations (C08)

Audience: the owner or an operator running Sentinel on a laptop. Everything here is local and synthetic. No paid service is involved, and the deterministic investigator is the default.

## Prerequisites

- `uv sync --locked --extra dev`.
- Local PostgreSQL binaries (`initdb`, `pg_ctl`, `pg_dump`, `pg_restore`; tested with 14.17). Set `SENTINEL_PG_BIN` if they are not on PATH or in a standard install location.
- Docker is **not** required: the Docker daemon was not running on the reference laptop, so the stack uses native binaries.

## Start, check, stop

```powershell
uv run --locked python scripts/local_stack.py up       # first run: initdb; then start, migrate, session, API
uv run --locked python scripts/local_stack.py status   # exit 0 only if DB and API are both up
uv run --locked python scripts/local_stack.py down     # stop API and DB; data is kept
```

- **State.** Everything lives under `.agent/stack/` (git-ignored): `pg/data`, `api.log`, `state.json` and `session.json`. `session.json` holds an 8-hour dev bearer token, is never printed, and is restricted to the user where the OS supports it. Delete `.agent/stack/` to start from scratch; this destroys local data.
- **Ports.** API 8000, Postgres 55433, both on 127.0.0.1 only. Override with `--port` / `--db-port` before the subcommand.
- **Auth.** The local cluster uses trust authentication on loopback. It is a development convenience and never a deployment configuration.
- **Investigator.** `up --investigator claude-cli` uses the owner's local Claude login (decision 0005 preflight). Never use it for staging or shared environments.

## Smoke test (synthetic data)

```powershell
uv run --locked python scripts/local_stack.py smoke                 # ingest -> investigate -> approve -> execute -> replay -> audit
uv run --locked python scripts/local_stack.py smoke --restart-api   # kills and restarts the API process mid-path
```

Expected (verified 2026-10-23):
- alert score 1.0;
- `simulated_hold`, case `awaiting_approval` (revision 3);
- after the API restart: action `succeeded`, mode `simulated`, `retry_replayed=True`, `same_action=True`;
- six audit events; case `closed` (revision 4).

## Upgrade (new migrations)

Migrations are forward-only numbered SQL files. `db.migrate` applies each once, in order, under an advisory lock, and records it in `schema_migrations`. There are **no down-migrations**: rollback means restoring a backup.

1. `local_stack.py backup`. This writes `.agent/backups/sentinel-<UTC>.dump` (`pg_dump --format=custom --no-owner`).
2. Stop the API (`down`), update the code, `uv sync --locked --extra dev`.
3. `local_stack.py up`. It prints the migrations it applied. Running `up` again must print `none pending`.
4. `local_stack.py smoke`, then check `status`.

If step 3 or 4 fails, roll back:

1. `down`.
2. Check out the previous code revision.
3. Restore the pre-upgrade dump into a fresh database: `local_stack.py restore <dump> --database sentinel_rollback`.
4. Point the API at it. Either rename databases with `psql`, or start uvicorn manually with `SENTINEL_DATABASE_URL=.../sentinel_rollback`.

Never restore over the live database in place.

## Backup and restore

```powershell
uv run --locked python scripts/local_stack.py backup [--out FILE]
uv run --locked python scripts/local_stack.py restore FILE --database NAME   # NAME must not exist
```

Verified:
- Manually on 2026-10-23: the restored database had row counts equal to the source in all 11 tables, and the audit append-only trigger was still enforced.
- Automatically by `tests/test_backup_restore.py`: equal counts, no pending migrations, audit `DELETE` rejected, and the restored database serves the closed case to the same session token.

Backups contain session token **hashes** and synthetic data only. Treat them as private anyway; `.agent/` is git-ignored.

## Troubleshooting

- `API did not become healthy`: read `.agent/stack/api.log` (it contains no request bodies; startup errors only).
- Port in use: choose `--port`/`--db-port`, or stop the other process. `status` shows what is up.
- On Windows, `pg_ctl` must not be given pipes; `sentinel.devdb` runs it with no inherited handles (otherwise the call never returns).
- Stale `investigating` case after a crash: the next investigate request after timeout + 30 s recovers it (`investigation_recovered`); re-read and retry.
- Lapsed approval: reopened lazily on the next execute/investigate request (`approval_outside_validity` / `approval_expired`); re-investigate.
