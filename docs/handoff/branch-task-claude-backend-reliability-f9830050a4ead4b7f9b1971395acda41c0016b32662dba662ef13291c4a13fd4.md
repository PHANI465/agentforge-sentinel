# Handoff: task/claude-backend-reliability

- Task and acceptance criteria: C05 (docs/TASK_QUEUE.md on task/coordination):
  - safe request/trace IDs, latency/outcome metrics and code-only unexpected-error handling with canary tests;
  - contention, rollback and recovery tests; explicit timeout/cancellation behavior; safe approval-expiry observation;
  - least-privilege runtime role design and tests;
  - the overview read-consistency follow-up from the C01 review.
- Owner: Claude Code. Accepted dependency: C01 at 2e6c2329aafe28b2e7c31ef5078d554cb66ca529. No C02 code imported.
- Tool and worktree: Claude Code, E:\PHANI\sentinel-wt\claude-backend-reliability (branch task/claude-backend-reliability)
- Updated: 2026-10-23
- State: R18–R20 corrections ready for Codex re-review. 0119ca7 was CHANGES REQUESTED (docs/reviews/0119ca7.md on task/coordination).
- Code reference tested before this note: working tree on top of 0119ca73e6ae3b4df9f9eeffcea8b15911f716e6 (strict checks rerun after the correction commit; reported in chat)
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

## Next action

Codex: re-review the R18–R20 correction commit. `X-Request-ID` stays an optional, undeclared diagnostic header (no UI reliance) until an accepted HTTP revision declares it.

## Coordination and provenance

- C02 (task/claude-browser-fixtures) is separate and was not imported. Both branches touch neither migrations nor contracts. C05 changes service.py/api.py, which the C02 helpers use unchanged; the integrator must rerun the C02 suites after merging.
- No dependencies added. No credentials committed; all canaries are synthetic.
