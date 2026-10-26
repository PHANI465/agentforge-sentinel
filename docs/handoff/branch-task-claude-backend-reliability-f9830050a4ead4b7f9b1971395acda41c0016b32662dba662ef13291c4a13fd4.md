# Handoff: task/claude-backend-reliability

- Task and acceptance criteria: C05 (docs/TASK_QUEUE.md on task/coordination):
  - safe request/trace IDs, latency/outcome metrics and code-only unexpected-error handling with canary tests;
  - contention, rollback and recovery tests; explicit timeout/cancellation behavior; safe approval-expiry observation;
  - least-privilege runtime role design and tests;
  - the overview read-consistency follow-up from the C01 review.
- Owner: Claude Code. Accepted dependency: C01 at 2e6c2329aafe28b2e7c31ef5078d554cb66ca529. No C02 code imported.
- Tool and worktree: Claude Code, E:\PHANI\sentinel-wt\claude-backend-reliability (branch task/claude-backend-reliability)
- Updated: 2026-10-23
- State: remaining-R18 correction ready for Codex re-review. b3b34ac was CHANGES REQUESTED for R18 only (docs/reviews/b3b34ac.md); R19/R20 and the operator notes were resolved there and are unchanged.
- Code reference tested before this note: working tree on top of b3b34acfc79fbca3856877594e8b030dc14a66e0 (strict checks rerun after the follow-up commit; reported in chat)
- Owned/changed paths: src/sentinel/observability.py (new), src/sentinel/db/roles.py (new), src/sentinel/api.py (middleware, metrics, logging), src/sentinel/service.py (overview single statement, investigator deadline and fault handling, events), src/sentinel/db/__init__.py (connect timeout), src/sentinel/cli.py (`grant-runtime`), tests/test_reliability.py (new), tests/test_db_roles.py (new), docs/security/README.md (new), this note. contracts/ and web/ are unchanged; the HTTP examples and OpenAPI are byte-identical.

## Implemented

- **`X-Request-ID`:** echoed only if it matches a safe pattern, otherwise random.
- **Events:** one JSON `sentinel.http` event per request (route template, status, duration, outcome; `error_type` class name only). The emit helper uses an allowlist.
- **Metrics:** in-process (requests, latency buckets, events).
- **Unexpected exceptions, including ResponseValidationError:** contained by a plain-ASGI middleware with the unchanged plain-text 500 body and not re-raised, so the server never logs the traceback or message.
- **Investigator:** a deadline (budget + 2 s). Timeout means a failed `timeout` run with the late result discarded. An unexpected exception means a failed `provider_unavailable` run, never a stuck case.
- **Events emitted:** `approval_expired`, `investigation_failed`, `investigation_timeout` (logged and counted).
- **Overview:** one SQL statement, so one snapshot.
- **`db.connect`:** 10 s connect timeout by default.
- **`sentinel.db.roles.grant_runtime`** plus `cli grant-runtime`: an explicit per-table grant map (required for every table); no DDL, DELETE or TRUNCATE; audit rows insert/select only; no session issuing or migrations; public-schema CREATE revoked.

## Verified (working tree before the commit, Windows 11, PostgreSQL 14.17, `SENTINEL_LIVE_CLAUDE=0`)

- **Failing first on 2e6c232:** `tests/test_reliability.py` gave 15 failed, 4 passed. The 4 that passed are the labelled guards: ingest rollback, execute rollback, same-account contention, typed errors. `tests/test_db_roles.py` failed at import (no roles module).
  - Notable failures: no request ID, no log line, no metrics; the unexpected RuntimeError escaped the app (it would reach the server's traceback logging); the investigator exception left the case stuck; the 6 s investigator exceeded the 1 s budget; the overview interleaving produced inconsistent totals; expiry was unobserved.
- **Test bugs fixed before counting:**
  - the canary scan included the test client's own `httpx` logs (client-side, not server output);
  - the outage test needed a short `connect_timeout` and the `ConnectionTimeout` subclass name; this also exposed a real ~130 s unbounded connect, now fixed;
  - the interleaving proxy lacked attribute delegation;
  - a non-owner GRANT only warns in PostgreSQL, so that case now asserts nothing was granted.
- **After the fix:** reliability and roles tests 36 passed (reliability 19 + roles 17).
- **Contract drift caught by the HTTP exporter:** minting request IDs with `uuid4` shifted the deterministic example IDs. Request IDs now use `secrets`, and `export_http_contract.py --check` verifies all 21 examples byte-identical.
- **Real-uvicorn probe** (default uvicorn logging, access log on, no database), with a route raising an exception that carries a canary DSN:
  - response: 500 `text/plain`, `Internal Server Error`, `X-Request-ID` present;
  - uvicorn stdout/stderr: no canary, no bearer token, no DSN host, no traceback;
  - the safe `RuntimeError` event was present;
  - observed: uvicorn's access log does print query strings; documented, with `--no-access-log` recommended.
- The full suite and strict checks are reported in chat after the commit.

## Not verified / gaps

- Linux/macOS/CI. Metrics are process-local with no export endpoint. Log shipping and retention are undesigned.
- `X-Request-ID` is not declared in OpenAPI (byte-frozen; no UI reliance). JSON 500 bodies and a metrics endpoint remain proposals only.
- No process-wide cap on late investigator workers. A failure after response headers start cannot become a clean 500 (no current endpoint streams).
- An investigator worker past its deadline keeps running until it returns, since threads can't be killed. The Claude adapter's own subprocess timeout bounds that case.

## Review correction: R18–R20 and operator notes (on top of 0119ca7)

Changed paths: src/sentinel/db/roles.py, src/sentinel/db/__init__.py, src/sentinel/observability.py, src/sentinel/api.py, tests/test_c05_review_regressions.py (new), docs/security/README.md, this note. contracts/ and web/ are unchanged; the OpenAPI and 21 examples are byte-identical; the 500 body and status are unchanged.

- **R18:** an existing role is checked first by `unsafe_reasons`:
  - attributes: exactly LOGIN + NOINHERIT, none of SUPERUSER/CREATEDB/CREATEROLE/REPLICATION/BYPASSRLS;
  - no memberships (SET ROLE reach);
  - owns nothing (`pg_shdepend` owner entries plus database owner);
  - no CREATE on any database;
  - no direct schema privilege beyond USAGE on public;
  - no privileges on unmanaged relations, no grant options, no function grants, no default privileges;
  - not the connecting operator.

  Any reason raises `UnsafeRoleError` before any password, privilege or PUBLIC-schema change. Operators are never demoted. A verified runtime role refreshes idempotently.
- **R19:** `connect_timeout` is detected with `psycopg.conninfo.conninfo_to_dict` (keyword and URI forms). Explicit values, including 0, are preserved.
- **R20:** the metric and log `method` comes from a fixed vocabulary plus `OTHER`; responses are unchanged.
- **Operator notes:**
  - `SENTINEL_LOG_LEVEL=off` now removes the sentinel handler, stops propagation and disables sentinel loggers (first use and INFO→off), and re-enables on a later non-off call;
  - the 500-containment prose is narrowed to failures before headers start;
  - the lack of a process-wide late-worker cap is stated as a limitation.

Test-first evidence: on 0119ca7, `tests/test_c05_review_regressions.py` gave 22 failed, 6 passed.
- R18 (all DID NOT RAISE: the old code accepted the role and changed it):
  - 7 attribute variants (SUPERUSER, CREATEROLE, CREATEDB, BYPASSRLS, REPLICATION, INHERIT, NOLOGIN);
  - an existing superuser;
  - direct schema CREATE and database CREATE;
  - membership, ownership, grant option;
  - the operator identity.
- R19: 4 misleading-value URLs got no timeout.
- R20: 64 `XMETHOD…` labels stored; the injected method was logged verbatim.
- Log off: 2 cases still emitted.
- The 6 that passed: plain/explicit-timeout URLs and the safe refresh, which already worked.
- Two test fixes before counting:
  - the R18 tests resolve `UnsafeRoleError` with a fallback, so the old code's `grant_runtime` actually runs (DID NOT RAISE) instead of failing on a missing class;
  - the ownership case uses an owned sequence, because an unmanaged table trips the existing grant-map check instead.
- After the fix: focused C05 suites (regressions 28 + roles 17 + reliability 19) pass, 64/64.

## Review follow-up: remaining R18 effective privileges (on top of b3b34ac)

Changed paths: src/sentinel/db/roles.py, tests/conftest.py (the shared `make_role` fixture moved here; it was in test_c05_review_regressions.py), tests/test_c05_review_regressions.py (fixture import only), tests/test_c05_r18_followup.py (new), docs/security/README.md, this note. contracts/ and web/ are unchanged; the R19/R20/logging code is untouched.

- **`environment_reasons`** (runs for new and existing roles before any change) refuses:
  - PUBLIC table or column privileges on managed objects beyond the map;
  - any PUBLIC privilege on unmanaged non-system relations;
  - PUBLIC CREATE on non-system schemas other than `public`;
  - PUBLIC CREATE on databases.

  Shared PUBLIC grants are never rewritten to make a candidate pass.
- **Exact identity:** managed objects are resolved by OID (`to_regclass('public.<name>')`). Candidate table and column ACLs are matched by OID, and grants use schema-qualified identifiers. Messages show explicit `schema.relation`.
- **One transaction:** CREATE ROLE, the password change, the public-schema CREATE revoke and the grants commit together. `verify_effective` compares effective privileges (direct and via PUBLIC, table and column level, schema CREATE) with the map before commit and rolls back on any mismatch.
- **Narrowed claims:** docs state the covered scope (current database's relations, columns and schemas; databases' CREATE). PUBLIC's default function EXECUTE and database TEMP are accepted. Other databases' objects are not scanned. The unconditional "no CREATE in any schema" statement is replaced by the scoped, verified one.

Test-first evidence: on b3b34ac, `tests/test_c05_r18_followup.py` gave 4 failed, 2 passed. The failures were DID NOT RAISE for:
- PUBLIC UPDATE(capabilities) on public.api_sessions;
- a candidate DELETE on probe_other.api_sessions (same name, other schema);
- PUBLIC CREATE on schema probe_other;
- PUBLIC SELECT on an unmanaged probe_other.notes.

The 2 that passed are guards: PUBLIC SELECT inside the map is allowed, and effective privileges exactly match the map after a refresh that removes stale direct DELETE/TRUNCATE and column-UPDATE grants (the case the review confirmed already worked).

Each refusal test snapshots role attributes, password hash and all table, column and schema ACLs naming the role or PUBLIC, and compares them after refusal without printing them. It also confirms a brand-new role is refused and not created.

Two fixes before counting: the `make_role` fixture moved into conftest (pytest registers fixtures by attribute name, so an aliased import was not found); and messages now use explicit schema-qualified names (`regclass::text` drops `public.`). After the fix: the 6 follow-up + 28 review regressions + 17 role + 19 reliability tests all pass (70).

## Next action

Codex: re-review the remaining-R18 follow-up commit. `X-Request-ID` stays an optional, undeclared diagnostic header (no UI reliance) until an accepted HTTP revision declares it.

## Coordination and provenance

- C02 (task/claude-browser-fixtures) is separate and was not imported. Both branches touch neither migrations nor contracts. C05 changes service.py/api.py, which the C02 helpers use unchanged; the integrator must rerun the C02 suites after merging.
- No dependencies added. No credentials committed; all canaries are synthetic.
