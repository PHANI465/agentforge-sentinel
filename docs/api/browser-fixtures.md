# Browser-test fixtures (C02)

Audience: Cursor (U02 Playwright suite) and reviewers. The backend contract is unchanged: accepted C01 `2e6c232` (`docs/api/README.md`, `contracts/http/`).

## What it gives you

A disposable stack per test run:
- a fresh PostgreSQL cluster (trust auth on 127.0.0.1, random port), migrated;
- the **production API** (`sentinel.api.create_app`) in a **real uvicorn process** (random port), with a deterministic fixture investigator;
- eleven seeded scenarios plus four session tokens.

There is no mock server. The investigator makes no model or network call, and live Claude is forced off. Seeding, backdated clocks and limited-capability sessions are created **inside the fixture process** through the service layer and SQL. The API gains no seed, clock, token or capability route.

`overview.investigator.name` is `deterministic-fixture-investigator` (version `x1`). It behaves like the deterministic investigator, except that a transaction amount of exactly `777777` minor units always fails with `provider_unavailable`.

## Process interface

Run from the backend checkout root (Python 3.11 and uv; PostgreSQL binaries found automatically or via `SENTINEL_PG_BIN`):

```powershell
uv run --locked python tests/support/browser_stack.py start [--state-dir DIR] [--api-port N] [--timeout 60]
uv run --locked python tests/support/browser_stack.py seed --manifest PATH --scenario NAME --ordinal N
uv run --locked python tests/support/browser_stack.py restart-api --manifest PATH
uv run --locked python tests/support/browser_stack.py restart-db --manifest PATH
uv run --locked python tests/support/browser_stack.py status --manifest PATH   # {"api":"up|down","database":"up|down"}
uv run --locked python tests/support/browser_stack.py stop --manifest PATH     # {"api_stopped":..,"database_stopped":..,"state_removed":..}
```

- **`start`** returns once the API answers `/healthz`. It prints `SENTINEL_STACK_MANIFEST=<path>` and a line with `base_url` and scenario names, **never tokens**. Exit code 1 means a startup error.
  - On failure everything it started is stopped, and the manifest is deleted.
  - Without `--state-dir` it uses a new private temp directory (`sentinel-browser-*`), which `stop` removes.
- **`seed`** prints one scenario record as JSON (no tokens). `ordinal` ≥ 1 is single-use per stack and gives stable IDs.
- **`restart-api`** kills only the recorded uvicorn process tree (identity checked by PID **and** process start time) and starts a new process on the same port. **`restart-db`** stops and starts the PostgreSQL server with `pg_ctl`; the API reconnects on its next request.
- **`stop`** stops the API and database, verifies both (process gone, port closed, `pg_ctl status`), then deletes the state directory, including the token file and database files. Nothing is terminated by process name.

Suggested Playwright wiring: `globalSetup` runs `start` and reads the manifest path; `globalTeardown` runs `stop`. Tests that need a fresh, time-sensitive record call `seed` just before use.

## Manifest (`stack.json`, private)

The manifest is restricted to the current user (0600 where supported, inside the user temp directory). Fields:

| Field | Content |
| --- | --- |
| `api.base_url`, `api.port`, `api.pid`, `api.start_time` | where the API listens; the process identity used for targeted shutdown |
| `database.port`, `database_url` | disposable cluster (trust auth, loopback only) |
| **`tokens`** (secret) | `analyst`, `other_session`, `read_only`, `second_actor` bearer tokens. They are ephemeral and differ on every start |
| `sessions` | each token's tenant/session/actor IDs and capabilities (no secrets) |
| `scenarios` | name → record: `case_id`, `transaction_id` and, where relevant, `intent_id`, `approval_id`, `approval_expires_at`, `action_id`, `idempotency_key`, `failed_run_id`; plus `session`, `state`, `revision`, `next` (the expected transitions in prose) |

**Token hygiene (Cursor's side):**
- Read tokens from the manifest only, and type them into the UI's in-memory token field.
- Keep them out of URLs, storage, logs, screenshots and traces: mask the token `fill` step, or disable tracing for it.
- Do not copy the manifest into test artefacts.

## Sessions

| Token | Scope | Capabilities | Use |
| --- | --- | --- | --- |
| `analyst` | tenant T, session A, actor 1 | all four | main path |
| `other_session` | tenant T, session B | all four | owns `foreign_session_case`; cross-session denial |
| `read_only` | tenant T, session A, actor 1 | `read_case` | sees A's cases; approve → 403 `permission_denied`; execute → 403 `action_permission_denied` |
| `second_actor` | tenant T, session A, actor 2 | all four | execute actor 1's approval → 403 `approver_mismatch` |

Sessions expire 8 hours after `start`.

## Scenarios (one instance seeded at start; more on demand)

| Name | Seeded state | Browser path and exact responses |
| --- | --- | --- |
| `open_case` | open, rev 1 | investigate (`expected_revision` 1) → 200, `awaiting_approval` rev 3, escalate/unusual_amount |
| `awaiting_approval` | awaiting_approval, rev 3, pending intent | approve → 201 (case stays rev 3); or reject → 201 and the case closes (rev 4) |
| `approved` | awaiting_approval, rev 3, approved | execute with a new key → 200 `succeeded`, closed rev 4; same key again → 200 `replayed: true`, one action row. **Valid only 5 minutes from seeding**: use `seed` right before the test |
| `executed` | closed, rev 4, with `action_id` + `idempotency_key` | execute with that key → 200 `replayed: true`, same `action_id`; another key → 409 `approval_not_available` |
| `rejected` | closed, rev 4 | execute → 409 `approval_not_available`; approve again → 409 `approval_exists` |
| `approval_expired` | awaiting_approval, rev 3; approval decided 10 min before start | execute → 409 `approval_outside_validity`, then the case is **open rev 4** with an `approval_expired` audit event; investigate (rev 4) → rev 6 with a new intent; approve + execute → 200; the old approval → 409 |
| `stale_revision` | open, rev 1 | load it in the UI, investigate it out of band with the analyst token, then submit with rev 1 → 409 `stale_case_revision`; a re-read shows rev 3 |
| `provider_failure` | open, rev 1, amount 777777 | investigate → **200** with the last run `failed` / `provider_unavailable`, case open rev 3, `action_intents` empty; each retry fails again (+2 revisions) |
| `failed_run_reopened` | open, rev 3, one failed run | investigate (rev 3) → 200 `awaiting_approval` rev 5; the failed run stays in `agent_runs` |
| `foreign_session_case` | open, rev 1, in session B | analyst token: GET/audit/investigate → 404 `not_found`; absent from the analyst's list and overview |
| `limited_capabilities` | awaiting_approval, rev 3, approved | see the Sessions table; each denied execution adds an `action_denied` audit event |

**IDs.** IDs are deterministic. Every fresh stack yields the same scenario and session IDs (UUIDv5 under namespace `5e1e0000-c02f-4000-8000-000000000000`). An on-demand seed's IDs depend on `(scenario, ordinal)`.

**Timestamps.** Timestamps are relative to the wall clock at seeding, so they differ between runs; tests should assert on states, codes and IDs, not times. The only expiry mechanism is the backdated seeding of `approval_expired`. There are no sleeps and no clock control in the API.

**Duplicate execution / lost response.** Use an `approved` seed. Send the same `idempotency_key` twice, concurrently or after dropping the first response. Both return the same `action.id`, exactly one with `replayed: false`, and the database holds one action row (asserted in tests).

**Restart.** `restart-api` replaces the uvicorn process (new PID; the old one is verified gone). `restart-db` restarts the PostgreSQL server. Both preserve case, approval, action and audit state; the tests assert identical audit trails and an idempotent replay afterwards. These are real process restarts, not reconstructed Python objects.

## Verification

`tests/test_browser_fixtures.py` (13 tests, real sockets) covers:
- documented states for all scenarios;
- foreign-session denial; limited capabilities and second actor;
- live provider failure and retry; seeded failed-run recovery;
- the expiry → reopen → fresh approval path; replay and rejection; stale revision;
- concurrent duplicate execution with one row;
- API and DB restart persistence;
- repeatable IDs across two fresh stacks, with tokens absent from CLI output;
- failed start (readiness timeout, crashing app) leaving no running cluster or token file.

## Limits

- Verified on Windows 11 only. The POSIX process path (`killpg`, `/proc` start time) is untested.
- Startup takes about 5–10 s (initdb).
- One stack per Playwright run is recommended; parallel workers should each start their own stack (random ports).
- There is no lost-response simulation inside the stack: drop the response in the browser/network layer, and the backend guarantees the replay.
