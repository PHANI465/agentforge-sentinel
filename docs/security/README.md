# Backend reliability, diagnostics and least privilege (C05)

For the current cross-project assessment, read the
[November 15 security/readiness review](PROJECT-REVIEW-2026-11-15.md).
The C05 implementation history below describes its original baseline; newer agent,
document and hosting controls are covered separately in the current review.

Audience: reviewers, operators and the UI owner. Base: accepted C01 `2e6c232`. The HTTP response bodies, status codes and OpenAPI snapshot are **unchanged**. The only externally visible addition is an `X-Request-ID` response header; see "Contract notes".

## Request IDs, events and metrics

- **Request ID.** Every HTTP response carries `X-Request-ID`. A client-supplied `X-Request-ID` is echoed only if it matches `^[A-Za-z0-9][A-Za-z0-9._-]{7,63}$`. Anything else (short, long, spaces, line breaks, markup) is replaced by a random 32-hex ID from `secrets`, which is independent of domain UUIDs.
- **One event per request.** The logger is `sentinel.http`, writing JSON lines to stderr via `configure_logging`. `SENTINEL_LOG_LEVEL` defaults to INFO. `off` removes the sentinel stderr handler, stops propagation to any root handler and disables sentinel loggers; a later non-off configuration re-enables them. Tests cover first-use off with a root handler, and INFO → off → INFO.

  ```json
  {"event":"http_request","request_id":"…","method":"GET","route":"/v1/cases/{case_id}","status":200,"duration_ms":4.2,"outcome":"ok"}
  ```

  `outcome` is `ok`, `handled_error` (4xx), `server_error`, or `unexpected_error` (which adds `error_type`, the exception **class name** only). `route` is the template, never the raw path or query string. `method` is one of GET/HEAD/POST/PUT/PATCH/DELETE/OPTIONS, or `OTHER`: methods are client-controlled, so unsupported ones share one label (review R20).
- **Service events** (logger `sentinel.service`), each also counted in metrics:
  - `approval_expired` (`case_id`, `revision`);
  - `investigation_failed` (`run_id`, `failure_code`, and `error_type` for unexpected exceptions);
  - `investigation_timeout` (`run_id`, `seconds`).
- **Allowlist.** `observability.emit` rejects any field outside the allowlist and any non-scalar value. Tokens, header values, query strings, bodies, exception messages, model context and DSNs cannot be logged through it.
- **Metrics.** `app.state.metrics.snapshot()` gives request counts by `METHOD route status` (bounded: fixed method vocabulary plus `OTHER`, route templates plus `unmatched`, and real status codes), latency buckets (≤5 … ≤5000 ms, >5000) by `METHOD route`, and event counts. They are in-process only; there is no HTTP endpoint (see "Contract notes").

## Unexpected failures

- **Containment.** A plain-ASGI middleware catches any exception that escapes the application, including storage outages and FastAPI `ResponseValidationError`, and does not re-raise it. If the failure happens **before response headers start**, which covers every current endpoint (none streams), it answers with the **same plain-text `500 Internal Server Error` body as C01** (the frozen R10 behavior) plus `X-Request-ID`. A failure after headers have started cannot be replaced: the client sees an incomplete response, and the event records the already-started status. The server therefore never logs the exception traceback or message. This was verified on a real uvicorn process: a canary in the exception message, a bearer token and a DSN host were all absent from uvicorn's stdout/stderr, and no traceback was printed.
- **Clients.** They still need the C01 fallback (`docs/api/README.md`) for non-JSON 5xx, proxies and network failures.
- **Connection timeout.** `db.connect` bounds attempts with `connect_timeout=10` s unless the connection string sets its own. Options are parsed with psycopg's `conninfo_to_dict` (libpq rules, keyword and URI forms), so text such as `application_name=connect_timeout_probe` or a password containing those characters does not disable the default (review R19). Before this, an unreachable database took about 130 s to fail.
- **Access logs.** uvicorn's **default access log prints the query string** (verified). Tokens are never in queries, but cursors and filters are. Run uvicorn with `--no-access-log` (as `scripts/local_stack.py` and the browser stack do) or rely on the `sentinel.http` events instead.

## Investigations: faults, timeouts, cancellation

- The investigator runs under a wall-clock deadline of its budget `timeout_seconds` plus 2 s grace. The grace lets an adapter's own typed timeout, such as the Claude CLI's, win first.
  - **On timeout:** the run is `failed` with `failure_code: timeout` and the case returns to `open`. The worker thread cannot be killed; if it finishes later, its result is discarded (tested: no intent, no revision change).
  - **On an unexpected investigator exception:** the run is `failed` with `provider_unavailable` and the case reopens. It no longer stays stuck in `investigating` until crash recovery. Only the exception class is logged.
- **No process-wide work cap.** Each request runs at most one investigator worker, but nothing bounds the total number of late workers across concurrent requests. That is a limitation for later public/load acceptance, not a claimed guarantee.
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
| Runtime API role (`python -m sentinel.cli grant-runtime --role sentinel_runtime`) | SELECT/INSERT on the domain tables; UPDATE on `cases`, `agent_runs`, `approvals`; SELECT on `api_sessions`, `schema_migrations`, `account_profiles` and `fraud_disclosures` (C07 model inputs; written only by the operator CLI); USAGE on the audit sequence | ALTER/DROP the managed tables, drop or disable the audit triggers, CREATE in any non-system schema, DELETE/TRUNCATE on managed tables, UPDATE/DELETE `audit_events`, issue or modify sessions (no INSERT/UPDATE on `api_sessions`, including column-level and via PUBLIC), record migrations, effectively GRANT anything. Holds within the scope below; verified after granting |

- **Existing roles are verified, never trusted or silently demoted** (review R18). Before any password or privilege change, `grant_runtime` checks an existing role for:
  - attributes: it must be exactly LOGIN + NOINHERIT, with no SUPERUSER, CREATEDB, CREATEROLE, REPLICATION or BYPASSRLS;
  - role memberships (`SET ROLE` reach);
  - ownership anywhere (`pg_shdepend`, database owner);
  - CREATE on any database;
  - direct schema privileges other than USAGE on `public`;
  - privileges (table- or column-level) on unmanaged relations, matched by exact OID;
  - grant options, function grants and default privileges;
  - whether it is the connecting operator.

  Any finding raises `UnsafeRoleError` listing the reasons, with no credentials, and leaves attributes, password, memberships, grants and the PUBLIC schema setting unchanged (tested by snapshot). A verified runtime role is refreshed idempotently: stale table grants are revoked and the password can be rotated.
- **The environment is verified too** (review R18 follow-up), for new and existing roles alike, because a runtime role also receives whatever PUBLIC holds. Refused before any change:
  - PUBLIC table or column privileges on a managed object beyond its grant map. For example, `GRANT UPDATE (capabilities) ON public.api_sessions TO PUBLIC` would let any runtime role rewrite session capabilities.
  - Any PUBLIC privilege on an unmanaged non-system relation.
  - PUBLIC `CREATE` on a non-system schema other than `public` (this tool revokes PUBLIC's `CREATE` on `public`).
  - PUBLIC `CREATE` on a database.

  The tool never rewrites shared PUBLIC grants to make a candidate pass; the operator must fix the environment deliberately. A PUBLIC privilege that is already inside the map (for example SELECT on a managed table) is accepted.
- **Exact object identity.** Managed objects are `public.<name>`, resolved by OID; grants are applied to schema-qualified names. A same-name table in another schema is unmanaged, and a candidate grant on it is refused.
- **Atomic and verified.** Role creation, password change, the PUBLIC `CREATE` revoke on `public`, and all grants run in one transaction. Before commit, effective privileges (direct and via PUBLIC: `has_table_privilege` and `has_any_column_privilege` for every table privilege kind, plus `has_schema_privilege` CREATE on every non-system schema) must match the map exactly. Otherwise everything rolls back.
- **Scope of these guarantees:**
  - covered: the current database's relations, columns and schemas, and the cluster's databases (CREATE);
  - accepted as PostgreSQL defaults: PUBLIC's default EXECUTE on functions and TEMP on the database;
  - not scanned: objects in other databases of the cluster, large objects, and privileges a superuser or owner grants after `grant-runtime` ran (rerun it to re-verify);
  - nothing here is a general PostgreSQL security audit.
- `grant_runtime` refuses to run if any table lacks an explicit entry in `RUNTIME_PRIVILEGES`, and a test pins the table set, so every new migration must decide its grants.
- It also revokes `CREATE` on schema `public` from PUBLIC (PostgreSQL 14 allows it by default).
- A runtime password, if used, comes from `SENTINEL_RUNTIME_PASSWORD`, never the command line.
- Tests: the full thin path runs as the runtime role (sessions issued by the operator), 11 forbidden statements are rejected, a non-owner GRANT has no effect, and migration as the runtime role fails.
- **Limit:** the owner or a superuser can still alter anything, including dropping the triggers. These roles limit a leaked runtime credential; they do not make storage tamper-proof, and they do not prevent injection in general. Queries are parameterized, and identifiers in SQL come from constants or validated names.

## Trained model serving (C07)

- **Only the registered artifact is loaded.** `SENTINEL_SCORER=model:hgb_balanced@p1` is the only model value. The packaged protocol, selection and manifest identities must match `sentinel.scorers.REGISTRY` before C04's `load_trusted` deserializes the installed `ml/artifacts/p1/model.joblib`, whose hash is checked again there. No path, URL or file from a request, visitor or environment variable selects an artifact. Any mismatch stops startup, and the rule is never substituted.
- **Model inputs are operator data.** Account profiles and fraud disclosures are loaded with `sentinel.cli provision-accounts` / `record-disclosures` as the schema owner. The runtime role can only read them (tested: UPDATE/DELETE/INSERT refused). No HTTP route writes them, and a model cannot change them.
- **Decision-time availability (R23):** operator loads take the same scoped per-account lock as model ingestion, and stamp `provisioned_at` / `recorded_at` only after holding it. A load can therefore neither enter a decision whose time was already captured nor be missed by a later one. A disclosure also needs `recorded_at <= decision time`. Direct owner SQL bypasses this boundary, so use the CLI.
- **The score is not an authorization.** A model score only opens a case. Investigation, approval and simulated execution keep every existing server-side guard, and a model never approves.
- **Results are server-owned files.** `GET /v1/model-results/{id}` maps only the registry id `p1` to packaged files verified by digest. The id never becomes a path.

## Contract notes (for Codex and Cursor)

- **Added, non-breaking:** an optional diagnostic `X-Request-ID` response header. It is not declared in `contracts/http/openapi.v1.json`, which is byte-unchanged. Per the C05 review decision, the UI must not rely on it (and must tolerate its absence) until an accepted HTTP revision declares it. It is never authorization.
- **Proposed, not implemented** (each would change the frozen contract): a JSON `500 {"error":"internal_error"}` body, and an authenticated metrics endpoint.

## Not verified

- Linux/macOS, CI and hosted logging pipelines. Log shipping and retention are not designed here.
- Metrics persistence across restarts (in-process only).
- Behavior under real provider latency distributions; only the deterministic and slow-test investigators were used.
