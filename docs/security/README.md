# Backend reliability, diagnostics and least privilege (C05)

Audience: reviewers, operators and the UI owner. Base: accepted C01 `2e6c232`. The HTTP response bodies, status codes and OpenAPI snapshot are **unchanged**. The only externally visible addition is an `X-Request-ID` response header; see "Contract notes".

## Request IDs, events and metrics

- **Request ID.** Every HTTP response carries `X-Request-ID`. A client-supplied `X-Request-ID` is echoed only if it matches `^[A-Za-z0-9][A-Za-z0-9._-]{7,63}$`. Anything else (short, long, spaces, line breaks, markup) is replaced by a random 32-hex ID from `secrets`, which is independent of domain UUIDs.
- **One event per request.** The logger is `sentinel.http`, writing JSON lines to stderr via `configure_logging`. `SENTINEL_LOG_LEVEL` defaults to INFO; set it to `off` to disable.

  ```json
  {"event":"http_request","request_id":"…","method":"GET","route":"/v1/cases/{case_id}","status":200,"duration_ms":4.2,"outcome":"ok"}
  ```

  `outcome` is `ok`, `handled_error` (4xx), `server_error`, or `unexpected_error` (which adds `error_type`, the exception **class name** only). `route` is the template, never the raw path or query string.
- **Service events** (logger `sentinel.service`), each also counted in metrics:
  - `approval_expired` (`case_id`, `revision`);
  - `investigation_failed` (`run_id`, `failure_code`, and `error_type` for unexpected exceptions);
  - `investigation_timeout` (`run_id`, `seconds`).
- **Allowlist.** `observability.emit` rejects any field outside the allowlist and any non-scalar value. Tokens, header values, query strings, bodies, exception messages, model context and DSNs cannot be logged through it.
- **Metrics.** `app.state.metrics.snapshot()` gives request counts by `METHOD route status`, latency buckets (≤5 … ≤5000 ms, >5000) by `METHOD route`, and event counts. They are in-process only; there is no HTTP endpoint (see "Contract notes").

## Unexpected failures

- **Containment.** A plain-ASGI middleware catches any exception that escapes the application, including storage outages and FastAPI `ResponseValidationError`. It answers with the **same plain-text `500 Internal Server Error` body as C01** (the frozen R10 behavior) plus `X-Request-ID`, and does not re-raise. The server therefore never logs the exception traceback or message. This was verified on a real uvicorn process: a canary in the exception message, a bearer token and a DSN host were all absent from uvicorn's stdout/stderr, and no traceback was printed.
- **Clients.** They still need the C01 fallback (`docs/api/README.md`) for non-JSON 5xx, proxies and network failures.
- **Connection timeout.** `db.connect` bounds attempts with `connect_timeout=10` s unless the URL sets its own. Before this, an unreachable database took about 130 s to fail.
- **Access logs.** uvicorn's **default access log prints the query string** (verified). Tokens are never in queries, but cursors and filters are. Run uvicorn with `--no-access-log` (as `scripts/local_stack.py` and the browser stack do) or rely on the `sentinel.http` events instead.

## Investigations: faults, timeouts, cancellation

- The investigator runs under a wall-clock deadline of its budget `timeout_seconds` plus 2 s grace. The grace lets an adapter's own typed timeout, such as the Claude CLI's, win first.
  - **On timeout:** the run is `failed` with `failure_code: timeout` and the case returns to `open`. The worker thread cannot be killed; if it finishes later, its result is discarded (tested: no intent, no revision change).
  - **On an unexpected investigator exception:** the run is `failed` with `provider_unavailable` and the case reopens. It no longer stays stuck in `investigating` until crash recovery. Only the exception class is logged.
- **Client disconnects** do not cancel server work. Every write path is a single transaction and is idempotent on retry (ingestion by `external_id`; execution by `idempotency_key`), so a client that loses a response retries with the same key.

## Consistency and contention (tests in `tests/test_reliability.py`)

- **Overview.** All counts come from **one SQL statement**, so they share one snapshot even under READ COMMITTED. A deterministic interleaving test commits a new alerting case between the old implementation's statements: the old code returned inconsistent totals, the new code doesn't.
- **Guards** (already true at the base, kept as regressions):
  - an injected database fault mid-ingest leaves no partial rows;
  - a fault after approval consumption rolls back the consumption, the action and the case change;
  - 8 concurrent ingestions for one account each count exactly the prior transactions that were available when they were decided.

## Least-privilege database roles (`sentinel.db.roles`)

| Identity | Can | Cannot |
| --- | --- | --- |
| Schema owner / operator (migrations, `create-session`, `grant-runtime`) | DDL, migrations, issue sessions | (it is trusted; not tamper-proof) |
| Runtime API role (`python -m sentinel.cli grant-runtime --role sentinel_runtime`) | SELECT/INSERT on the domain tables; UPDATE on `cases`, `agent_runs`, `approvals`; SELECT on `api_sessions` and `schema_migrations`; USAGE on the audit sequence | ALTER/DROP tables, drop or disable the audit triggers, CREATE in `public`, DELETE/TRUNCATE anywhere, UPDATE/DELETE `audit_events`, issue or modify sessions, record migrations, effectively GRANT anything |

- `grant_runtime` refuses to run if any table lacks an explicit entry in `RUNTIME_PRIVILEGES`, and a test pins the table set, so every new migration must decide its grants.
- It also revokes `CREATE` on schema `public` from PUBLIC (PostgreSQL 14 allows it by default).
- A runtime password, if used, comes from `SENTINEL_RUNTIME_PASSWORD`, never the command line.
- Tests: the full thin path runs as the runtime role (sessions issued by the operator), 11 forbidden statements are rejected, a non-owner GRANT has no effect, and migration as the runtime role fails.
- **Limit:** the owner or a superuser can still alter anything, including dropping the triggers. These roles limit a leaked runtime credential; they do not make storage tamper-proof, and they do not prevent injection in general. Queries are parameterized, and identifiers in SQL come from constants or validated names.

## Contract notes (for Codex and Cursor)

- **Added, non-breaking:** an `X-Request-ID` response header on every response. It is not yet declared in `contracts/http/openapi.v1.json`, which is byte-unchanged. Proposed: declare it in a future contract revision. UIs may display it for support, but must not rely on it for authorization.
- **Proposed, not implemented** (each would change the frozen contract): a JSON `500 {"error":"internal_error"}` body, and an authenticated metrics endpoint.

## Not verified

- Linux/macOS, CI and hosted logging pipelines. Log shipping and retention are not designed here.
- Metrics persistence across restarts (in-process only).
- Behavior under real provider latency distributions; only the deterministic and slow-test investigators were used.
