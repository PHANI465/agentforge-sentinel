# Runbook: local API + Postgres operations (C08)

Audience: the owner or an operator running Sentinel on a laptop. Everything here is local and synthetic. No paid service is involved, and the deterministic investigator and rule scorer are the defaults. Refreshed for the accepted f38e920 release and review 9ab183e (R24, R26).

## Prerequisites

- `uv sync --locked --extra dev --extra ml`. The ml extra is needed for `--scorer model` and the packaged model; rule mode does not import it.
- Local PostgreSQL binaries (`initdb`, `pg_ctl`, `pg_dump`, `pg_restore`; tested with 14.17). Set `SENTINEL_PG_BIN` if they are not on PATH or in a standard install location.
- Docker is **not** required; the stack uses native binaries.

## Start, check, stop

```powershell
uv run --locked python scripts/local_stack.py up [--scorer rule|model] [--database NAME]
    [--investigator deterministic|claude-cli|three-role] [--agent-adapter deterministic|claude-cli]
uv run --locked python scripts/local_stack.py status   # exit 0 only if our DB and our API are both up
uv run --locked python scripts/local_stack.py down     # stop our API, then our DB; data is kept
```

Global options go before the subcommand: `--port` (default 8000), `--db-port` (default 55433) and `--state-dir` (default `.agent/stack/`).

- **State.** Everything lives in one owned directory, git-ignored by default:
  - an ownership marker (`.sentinel-local-stack`, with a random owner value);
  - `state.json`, holding the recorded process identities, ports, scorer, database name and the effective investigator configuration (investigator, three-role adapter, and the Claude model name for a live configuration), but no secrets or connection strings;
  - `pg/data`, `api.log`, and `session.json` (an 8-hour dev bearer token, never printed, restricted to the user where the OS supports it).

  A directory without a matching marker is never adopted; `down` and `status` refuse it. Delete the directory to start from scratch, which destroys local data.
- **Authority.** `up` runs as the cluster owner to migrate, grant the C05 least-privilege runtime role `sentinel_local_runtime` (verified by `sentinel.db.roles.grant_runtime`) and issue the dev session. The API process connects **as the runtime role**, which cannot alter schema, issue sessions or write profiles or disclosures. Backup and restore use the owner.
- **Capabilities.** The dev session has `ingest_transaction`, `read_case`, `approve_action` and `execute_simulated_action`. `read_case` also covers `GET /v1/scoring` and `GET /v1/model-results/p1`. There is no admin capability.
- **Scorer.** It is explicit: `rule` by default; `--scorer model` serves the registered `hgb_balanced@p1`. Model mode needs account profiles (`python -m sentinel.cli provision-accounts`, as the owner); otherwise ingestion returns 422 `account_profile_missing`. `smoke` runs only in rule mode.
- **Code served.** The API process runs this checkout's code (`PYTHONPATH` = this checkout's `src` and root), not some other installed copy.
- **Auth.** The local cluster uses trust authentication on loopback. It is a development convenience and never a deployment configuration.
- **Investigator.** The deterministic single investigator is the default.
  - `up --investigator claude-cli` uses the owner's local Claude login (decision 0005 preflight). Never use it for staging or shared environments.
  - `up --investigator three-role` runs the G3B coordinator: evidence analyst, then investigator, then reviewer.
    - Its role adapter is **deterministic** unless you pass `--agent-adapter claude-cli` (the local subscription; never paid, no fallback).
    - An inherited `SENTINEL_AGENT_ADAPTER`, `SENTINEL_INVESTIGATOR` or `SENTINEL_CLAUDE_MODEL` is never used: the helper passes each one explicitly to the API.
    - `--agent-adapter` with a single investigator is refused before any state, database or API is created.
  - Launch and `status` output name the effective investigator, adapter and live model.
- **Restart consistency (G3D-P3).**
  - `smoke --restart-api` restarts with the **recorded** configuration, never the environment, so new cases pin the same agent and tool config as earlier ones.
  - A record that does not state its configuration is refused for restart before any work. That covers a three-role record without an adapter, and a pre-P3 claude-cli record without its model.
  - A pre-P3 deterministic record is still accepted. `status` and `down` never need the new fields to show or stop an owned process.
- **Repeating `up`.** Against our running API, an identical request is idempotent ("already running"). A different investigator, adapter, scorer, database or port is refused with the process and its record untouched. Change modes with `down`, then `up`.

## Ownership and failure behavior (R24)

- **Recorded identity.** A process is acted on only when its recorded identity still matches: PID, creation time and executable image. The venv `python.exe` is a launcher on Windows, so the API's port must be served only by the recorded process or its descendants. The postmaster must run from our PostgreSQL binary, for our data directory and port.
- **Refusals.** Each of these is refused **without any kill**, keeping the record, with exit code 1:
  - a reused PID whose port is still served;
  - a record without identity;
  - a foreign process on the API or database port (including a healthy foreign API);
  - an unknown state.

  A reused PID whose port is free means our process already exited; `down` then clears the record without touching the new owner of that PID.
- **Confirmed stop.** `down` reports success only after the API process tree is gone and its port is closed, then after `pg_ctl status` reports the database stopped and its port free. If a stop cannot be confirmed, it exits 1 and keeps the identity for a retry; it never erases identity just to claim it stopped. The database is not stopped under an API it could not account for.
- **Startup (R28).**
  - *Launch record first.* A pending launch record (port, scorer, database) is saved **before** the API is launched, and its raw PID right after. Only then is its identity inspected.
  - *Unverifiable launch.* If the identity cannot be established (the inspection fails, or the launcher is already gone), `up` exits 1 and keeps an **unresolved launch** record, killing nothing. While it is unresolved, `down` and `restore` refuse and the database is not stopped. It resolves only when that PID is gone, no descendant survives (Windows keeps an orphan's parent PID) and its port is free. Stop a surviving process yourself, then rerun `down`.
  - *Readiness.* Success requires an actual healthy `/healthz` response, within 60 s, from our own process tree serving the port. A bound port alone is not readiness. On timeout or early exit, `up` stops only the verified API it started, confirms that, clears the record and exits 1. If that cleanup cannot be confirmed, it keeps the recovery record and asks for `down`.
  - *Launcher exited.* A verified launcher that exited while a descendant survives is reported as `gone-but-child-alive`, and `down` refuses.
- **Platforms.** Windows is implemented and tested. The POSIX path (`/proc`, `killpg`) is implemented to fail closed but **untested**.

## Smoke test (synthetic data, rule mode)

```powershell
uv run --locked python scripts/local_stack.py smoke                 # ingest -> investigate -> approve -> execute -> replay -> audit
uv run --locked python scripts/local_stack.py smoke --restart-api   # verified stop and restart of our API mid-path
```

Expected: `simulated_hold` or `escalate`, case `awaiting_approval` (revision 3); then action `succeeded`, mode `simulated`, `retry_replayed=True`, `same_action=True`, six audit events, case `closed` (revision 4).

The smoke output lists every role run (`runs=role:status,...`), names the run that produced the finding (not simply the last run), and summarizes the trace (`trace workflows=... legacy_runs=... status=... disposition=...`). Before approving, it prints the case's run, approval and action counts (`before approval runs=N approvals=0 actions=0`).

With `up --investigator three-role`, a deterministic run shows:
- `runs=evidence_analyst:completed,investigator:completed,reviewer:completed`;
- `trace workflows=1 legacy_runs=0 status=completed disposition=recommend`;
- `before approval runs=3 approvals=0 actions=0`.

The approval and execution are an automated operator smoke through the real API's human-authorization routes, not a person clicking the UI.

`tests/test_local_stack_three_role.py` proves this with real stacks on free ports. The inherited environment selects claude-cli and another model on purpose, and the Claude executable points at a nonexistent path, so no provider can be reached. The test checks:
- the persisted workflow, roles, ordered steps and pins;
- that the intent is server-built;
- that the trace is unchanged across `smoke --restart-api`;
- that the first case executes once without reinvestigation;
- that a case created after the restart pins the same config;
- that `up` is idempotent, or refused on a mismatch.

## Upgrade (new migrations)

Migrations are forward-only numbered SQL files. `db.migrate` applies each once, in order, under an advisory lock, and records it in `schema_migrations`. There are **no down-migrations**; rollback means restoring a backup into a new database.

1. `local_stack.py backup --out pre-upgrade.dump` (`pg_dump --format=custom --no-owner` of the served database).
2. `local_stack.py down`, update the code, then `uv sync --locked --extra dev --extra ml`.
3. `local_stack.py up`. It prints the migrations it applied. Running it again prints `none pending`.
4. `local_stack.py smoke`, then `status`.

## Rollback (R26; drilled)

If step 3 or 4 fails:

1. `local_stack.py down` stops the API (verified) and the database. Restore refuses while an API is running.
2. `local_stack.py restore pre-upgrade.dump --database sentinel_rollback` (still on the new code, or on the previous code; either works).
   - It starts and verifies **only our** cluster, creates the **new** database (refusing an existing name or the live `sentinel`) and runs `pg_restore --exit-on-error`.
   - It reports the table count and the restored `schema_migrations` list.
   - It does **not** migrate and does **not** start an API, so nothing moves the rollback target forward. The database is left running.
3. Check out the previous code revision, then `uv sync --locked --extra dev --extra ml`.
4. `local_stack.py up --database sentinel_rollback`. The **previous** code migrates (it must print `none pending`, because the dump came from that version), grants its runtime role, reuses the stored dev token (the restored database contains its session) and starts the API against the restored database. `up --database` never creates a missing non-default database.

The upgraded live `sentinel` database is never overwritten. Inspect or drop it later.

`tests/test_local_rollback_drill.py` runs exactly this sequence with real processes:

1. Two code versions are used: this tree, and the same tree plus an upgrade migration `0005`.
2. Previous code: `up`, `smoke`, `backup`, `down`.
3. New code: `up` (applies 0005).
4. `restore` is refused while the API is up.
5. New code: `down` and `restore` (restored migrations end at 0004; no `0005` table; no API started).
6. Previous code: `up --database sentinel_rollback` (none pending).

It asserts that every table's row count, the case (closed, revision 4), its simulated action, its audit event IDs and the session rows equal the pre-upgrade backup. It checks the case is served to the original token, that the live database still has the 0005 table, and that no token or `postgresql://` string appears in any command output or `api.log`.

## Backup and restore

```powershell
uv run --locked python scripts/local_stack.py backup [--out FILE]
uv run --locked python scripts/local_stack.py restore FILE --database NAME   # API stopped; NAME must be new
```

`tests/test_backup_restore.py` round-trips a populated database, including C07's `account_profiles` and `fraud_disclosures`, and checks:
- equal row counts in **all 16 current tables** (including the G3B `agent_workflows` and `agent_steps`), checked against the live schema inventory;
- no pending migrations;
- audit `DELETE` rejected;
- the restored case is served to the same token.

That scenario uses the legacy single investigator, so its `agent_workflows` and `agent_steps` are empty.

### Populated workflow history (G3D-P2)

`tests/test_workflow_backup_restore.py` proves that stored three-role investigations survive the same `pg_dump --format=custom --no-owner` / `pg_restore --no-owner --exit-on-error` round trip into a new database.

**Authority.**
- The operator (the schema owner) issues the sessions and loads one profile and one disclosure.
- Everything else is written by the production service and coordinator, connected as a least-privilege runtime role, with deterministic adapters and the G3B fault harness.
- After restore, the procedure re-grants **the same runtime role** on the restored database, as `local_stack.py up --database NAME` does. That role still cannot delete steps or cases, or issue sessions.

**What is stored.** 7 workflows, 20 role runs and 128 steps across six cases and two scopes:
- a completed recommendation;
- a reviewer challenge, a revision and then abstain;
- a provider failure followed by a repeat attempt;
- a crash, an explicit recovery (inconclusive, `terminal_by: recovery`) and a retry, which gives two workflows on one case;
- a crashed workflow still `running`;
- another tenant's completed case.

No approval or action exists yet.

**What it checks.**
- Equal counts in all 16 tables, and **every row of every table equal field for field**: IDs, revisions, pins, ordered step `seq`, dispositions, failures and usage provenance.
- No pending migrations.
- Append-only `audit_events` and `agent_steps` reject `DELETE` and `UPDATE`, even for the owner.
- Each restored trace, read over real HTTP by the production app as the runtime role with the **original session token**, equals the trace read from the source, field for field. `read_at` is compared separately: it is the reading server's clock, not a stored field.
- Selecting each workflow by `workflow_id` works. Another session of the same tenant, another tenant, and another case's workflow ID all get `404 not_found`. No token gets `401`.
- Repeated trace reads of the restored `running` workflow at `recovery_due` change no row. Recovery happens only on an explicit investigate request (`investigation_recovered`).
- The human boundary still holds after restore: one real approval and one idempotency key give exactly one simulated action, and a retry replays it.

**Negative controls,** each on an isolated restored copy; the source is never modified. Each one is detected by the content comparison:
- one step removed (in that copy's session only, with `session_replication_role = replica`), which changes `agent_steps`;
- one workflow body altered with every row count unchanged, which changes `agent_workflows`;
- an archive restored without `agent_steps` data.

The trace of the copy with the missing step also differs.

**Not covered:** a live provider, `local_stack.py backup` and `restore` as processes (the rollback drill covers those), or Linux/macOS clusters other than the native Ubuntu gate.

Backups contain session token **hashes**, operator-provisioned profiles and disclosures, and synthetic data. Treat them as private; `.agent/` is git-ignored.

## Logs

`api.log` receives uvicorn warnings and errors (access log disabled), startup failures, and the API's structured JSON events. Those events are one line per request (`http_request`: request ID, method, route template, status, duration, outcome), plus `investigation_timeout`, `investigation_failed` and `approval_expired` events (IDs, codes and counts only, from an allowlist of scalar fields). They contain no request or response bodies, no bearer tokens and no connection strings; the drill asserts the token and `postgresql://` are absent. `local_stack.py` itself prints no tokens or DSNs, only ports, database names, file paths and migration names.

## Troubleshooting

- `API failed to start`: read the owned `api.log`.
- **Port in use / foreign process:** choose `--port`/`--db-port`, or stop the other process yourself. `status` shows what is ours.
- **Stop not confirmed:** rerun `down`. The recorded identity is kept until the stop is verified.
- On Windows, `pg_ctl` must not be given pipes; `sentinel.devdb` runs it with no inherited handles (otherwise the call never returns).
- **Stale `investigating` case after a crash:** the next investigate request after timeout + 30 s recovers it (`investigation_recovered`); re-read and retry.
- **Lapsed approval:** reopened lazily on the next execute/investigate request (`approval_outside_validity` / `approval_expired`); re-investigate.
