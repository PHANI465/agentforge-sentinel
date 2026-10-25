# Codex C01 review: 0a6fb0e

Reviewed: October 23, 2026.
Exact commit: 0a6fb0ec8e63fd686ac7e4cf6bbfb7bd22a105b0.
Branch/worktree: task/claude-api-contracts, E:\PHANI\sentinel-wt\claude-api-contracts.
Base: fcc04c5eebdb353ce290b99c288990c51a0d4dcf.

**Outcome: changes requested before C01 acceptance. Cursor U01 and Claude C02 remain gated.** The submitted handoff is the correct C01 handoff. Existing tests pass, and two review probes expose corrections needed at the HTTP boundary.

## R9 [P2]: validate cursor structure and member types before parsing

Location: [service.py:67](E:/PHANI/sentinel-wt/claude-api-contracts/src/sentinel/service.py:67), particularly uuid.UUID(case_id) at line 71.

A caller can base64url-encode JSON such as ["2026-10-23T17:00:00+00:00", 123] and send it as the cursor query parameter. Its size passes the FastAPI query bounds. decode_cursor passes the second JSON member straight into uuid.UUID(), which raises AttributeError for integers, booleans, arrays and objects. The handler catches ValueError/TypeError and decoding errors, so AttributeError escapes and the route returns plain-text HTTP 500 instead of the documented 422 invalid_cursor.

Independently reproduced:
- Actual decoder: numeric, boolean, object and array UUID members raise AttributeError.
- In-process HTTP probe using stub auth/storage and the actual decoder: valid string -> 200, invalid UUID string -> 422 invalid_cursor, numeric/object/array -> 500.
- Real Uvicorn process with a real disposable PostgreSQL database and authenticated session: numeric cursor -> 500, non-JSON body.

Correction: validate that decoded JSON is a two-element list of strings before parsing. Retain timezone-aware timestamp and UUID validation. Reject malformed shape/type values through ServiceError("invalid_cursor", 422); do not hide unrelated exceptions with a blanket catch.

Acceptance: HTTP regressions for integer/boolean/object/array/null UUID members and invalid root/length/member shapes return 422 with the safe error code. Valid pagination and existing invalid-string/time cases continue working. Write the regression first and verify it fails on the submitted implementation.

## R10 [P2]: align the error contract with unexpected server failures

Locations:
- [docs/api/README.md:62](E:/PHANI/sentinel-wt/claude-api-contracts/docs/api/README.md:62).
- [http_v1.py:41](E:/PHANI/sentinel-wt/claude-api-contracts/src/sentinel/contracts/http_v1.py:41).
- [api.py:47](E:/PHANI/sentinel-wt/claude-api-contracts/src/sentinel/api.py:47) and its registered exception handlers.

The docs and ErrorResponse description promise that every non-2xx response has the JSON ErrorResponse shape. Expected service/validation/HTTP errors are handled, but unexpected exceptions are not mapped to that shape. A storage failure or response-validation failure can therefore produce Starlette's plain-text 500. A client generated against the stated guarantee can itself fail while parsing that body.

Independent in-process probe injected a synthetic authentication/storage exception: status 500, content-type text/plain, body "Internal Server Error". The synthetic exception message was not echoed. The issue is contract accuracy and client recovery, not a demonstrated secret disclosure.

Preferred bounded correction for C01: narrow the promise to documented/handled errors and explicitly require the UI client to handle non-JSON 5xx, empty/invalid bodies and network failures with a safe generic message. An ambiguous execution failure must retain the original idempotency key; it is not evidence that no action happened. Adjust the ErrorResponse description and regenerate the OpenAPI snapshot.

Alternatively, implement and test an intentional safe JSON 500 boundary, including response-validation failures. Do not claim universal JSON failures merely from registering one application handler; proxy/runtime/network failures still need client fallback. Broader safe logging/observability can stay in C05.

Acceptance: documentation, DTO description and exported OpenAPI no longer promise a response shape the application cannot guarantee. Add an appropriate failure-boundary/contract regression for the chosen behavior. No new dependency or real provider call is needed.

## Independent verification on the submitted commit

| Check | Result |
| --- | --- |
| tests/test_api_contracts.py + tests/test_http_contract.py | 40 passed, 1 existing TestClient warning; 60.86 seconds |
| Strict scripts/agent_check.py | PASSED, exit 0; 208.841 seconds |
| Full pytest | 146 passed, 1 intentional live-Claude skip, 1 TestClient warning; 164.00 seconds |
| Handoff regressions | 21 passed; 40.734 seconds |
| Domain schema exports | 15 verified |
| Ruff and Node transport | Passed |
| Real process HTTP smoke | Session/list/overview 200; synthetic ingest 201 and correct list/overview changes; missing auth 401; malformed numeric cursor 500 reproduced |

Runs used the existing locked virtual environment on Windows. Live Claude was disabled, the external test-database URL was removed only from the child test environment, and disposable local databases were used. No new model call or source/Git change was made by the reviewers.

## Other review conclusions and limits

- No additional session-scoping, migration 0003 backfill or approval-clock blocker was found.
- The typed envelopes/fixtures otherwise provide the data required for U01. Authority remains server-controlled, legacy unknown scores remain nullable, and rationale is explicitly untrusted.
- C02's missing failure/rejection/permission fixtures remain disclosed dependencies.
- Nonblocking C05 follow-up: overview reads its state/count aggregates in separate READ COMMITTED snapshots. Concurrent ingestion/execution can produce inconsistent totals within one response. Consider a single-statement aggregate or an explicit consistent read snapshot with a targeted regression.
- No CI/Linux/macOS, browser UI or hosted staging verification is claimed.

## Next handoff

Claude makes a focused C01 correction on task/claude-api-contracts, updates its branch handoff, reviews explicit staged paths, commits and runs final checks after that commit. Return the exact new commit and results for Codex re-review. Keep Cursor U01 and C02 pending acceptance; independent ready C03/C06 work can continue in their own worktrees. Main is not merged by this review.
