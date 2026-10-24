# Handoff: task/claude-backend-reliability

- Task and acceptance criteria: C05 (docs/TASK_QUEUE.md on task/coordination):
  - safe request/trace IDs, latency/outcome metrics and code-only unexpected-error handling with canary tests;
  - contention, rollback and recovery tests; explicit timeout/cancellation behavior; safe approval-expiry observation;
  - least-privilege runtime role design and tests;
  - the overview read-consistency follow-up from the C01 review.
- Owner: Claude Code. Accepted dependency: C01 at 2e6c2329aafe28b2e7c31ef5078d554cb66ca529. No C02 code imported.
- Tool and worktree: Claude Code, E:\PHANI\sentinel-wt\claude-backend-reliability (branch task/claude-backend-reliability)
- Updated: 2026-10-23
- State: ready for Codex review
- Code reference tested before this note: working tree on top of 2e6c232 (strict checks rerun after the commit; reported in chat)
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
- `X-Request-ID` is not yet declared in OpenAPI (byte-frozen). JSON 500 bodies and a metrics endpoint are proposed only.
- An investigator worker past its deadline keeps running until it returns, since threads can't be killed. The Claude adapter's own subprocess timeout bounds that case.

## Next action

Codex: review C05 (error containment versus the frozen contract, role grants, investigator deadline semantics). Decide whether to declare `X-Request-ID` in the next contract revision before Cursor relies on it.

## Coordination and provenance

- C02 (task/claude-browser-fixtures) is separate and was not imported. Both branches touch neither migrations nor contracts. C05 changes service.py/api.py, which the C02 helpers use unchanged; the integrator must rerun the C02 suites after merging.
- No dependencies added. No credentials committed; all canaries are synthetic.
