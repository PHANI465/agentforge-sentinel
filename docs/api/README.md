# HTTP API v1 contract (C01)

Audience: Cursor (analyst UI, browser tests) and reviewers. The contract is frozen as:

- `contracts/http/openapi.v1.json`: OpenAPI 3.1 with typed responses, request bodies and bearer auth.
- `contracts/http/examples/*.json`: one request/response pair per file, produced by a deterministic scripted run (fixed clock from 2026-10-23T17:00:00Z, sequential UUIDs `5e000000-…`, deterministic investigator). Each file is `{request: {method, path, authenticated, body}, status, response}`.
- Python models: `sentinel.contracts.http_v1` (envelopes) and `sentinel.contracts.v1` (domain records); `contracts/v1/*.schema.json` holds the domain schemas.

Regenerate after an intentional change with `uv run --locked python scripts/export_http_contract.py`, then review the diff. Use `--check` to verify. `tests/test_http_contract.py` fails if the code and the committed snapshot or examples diverge. A contract change after acceptance needs a new review before the UI consumes it.

## Authentication and scope

- Every `/v1/*` route needs `Authorization: Bearer <token>`. Tokens are issued out-of-band (`python -m sentinel.cli create-session`, or C02 test fixtures). Only their SHA-256 is stored.
- There is no login, token-issuing or capability-granting HTTP route. A UI should hold the token in memory only.
- All data is scoped to the token's tenant AND session. Another session's records, even in the same tenant, return `404 not_found`, exactly like missing ones.
- `GET /v1/session` returns the session's own `tenant_id`, `session_id`, `actor_id`, `actor_kind`, sorted `capabilities` and `expires_at`. It never returns the token, credentials or investigator account details.

## Endpoints

| Method and path | Capability | Success | Body / query | Response model |
| --- | --- | --- | --- | --- |
| GET `/healthz` | none | 200 | | `Health` |
| GET `/v1/session` | any valid token | 200 | | `SessionView` |
| GET `/v1/overview` | `read_case` | 200 | | `Overview` |
| POST `/v1/transactions` | `ingest_transaction` | 201 (also on replay) | `TransactionInput` | `IngestResponse` |
| GET `/v1/cases` | `read_case` | 200 | `limit` 1–100 (default 25), `state`, `cursor` | `CasePage` |
| GET `/v1/cases/{case_id}` | `read_case` | 200 | | `CaseDetail` |
| GET `/v1/cases/{case_id}/audit` | `read_case` | 200 | | `AuditEvent[]`, oldest first |
| POST `/v1/cases/{case_id}/investigations` | `read_case`, human | 200 | `InvestigationRequestInput` | `CaseDetail` |
| POST `/v1/approvals` | `approve_action`, human | 201 | `ApprovalDecisionInput` | `Approval` |
| POST `/v1/actions` | `execute_simulated_action`, same human approver | 200 | `ExecuteActionInput` | `ExecuteResponse` |

Bodies are JSON, at most 16 KiB, with unknown fields rejected.

## Case list and pagination

- Order: `created_at` descending, then `id` descending. Ties on `created_at` are deterministic.
- `next_cursor` is opaque; pass it back unchanged with the same `state` filter. It is `null` on the last page.
- Keyset pagination: cases created after you started paging do not shift or duplicate later pages.
- The cursor carries no authority. A cursor from another session only positions a query that remains scoped to your session.
- `state` is one of `open`, `investigating`, `awaiting_approval`, `closed`, `inconclusive`.
- `CaseSummary` gives the case id/state/revision/timestamps, alert and transaction ids, `external_id`, exact `amount` (minor units + currency + exponent), `direction` and the alert's `score`, `threshold`, `scoring_kind` and `score_semantics`.

## Scores and model text

- `scoring_kind: "rule"` with `score_semantics: "heuristic"`: the score is a rule heuristic in [0, 1], **not a probability**. Display it as a rule score.
- `IngestResponse.rule_score` / `scoring` are `null` only for legacy transactions ingested before migration 0002: **unknown**, never zero.
- `CaseDetail.agent_runs[].finding.rationale` is untrusted text. Render it inert (no HTML/Markdown execution). The executable action is `action_intents[].intent`, built by the server from stored records.
- Amounts are integers in minor units. Format with `currency_exponent`; never convert through floating point for display totals.

## Workflow semantics the UI must handle

- **Revisions:** pass the `revision` you last read as `expected_revision`. A mismatch gives `409 stale_case_revision`; re-read the case.
- **Current intent:** the last `action_intents` entry is current only if `intent.case_revision == case.revision`. Older entries are history.
- **Expiry:** an approval is valid for 5 minutes. A lapsed approval reopens the case: execute returns `409 approval_outside_validity`, or investigate returns `409 approval_expired`. The case is then `open` at a new revision with an `approval_expired` audit event. Re-investigate to get a new intent and approve again. The old approval never works again.
- **Idempotent execution:** generate one `idempotency_key` (UUID) per intended execution. Reuse it on retry after an ambiguous failure. A repeated key returns `replayed: true` with the original action and no second effect, provided the session still has execution authority. A key reused for a different approval gives `409 idempotency_conflict`.
- **Investigation failure:** the run is recorded `failed` with a `failure_code` (`provider_unavailable`, `timeout`, `invalid_output`, `budget_exhausted`), and the case returns to `open` at a new revision.
- **Ingestion replay:** an identical body with the same `external_id` returns the original outcome with `replayed: true`. A different body gives `409 idempotency_conflict`.

## Errors

Every non-2xx body is `ErrorResponse`: `{"error": "<code>"}`, plus `details: [{"code": ...}]` for invalid JSON bodies. No field names, values or input are echoed.

| Status | Codes |
| --- | --- |
| 400 | `invalid_content_length` |
| 401 | `unauthenticated` (missing, unknown or expired token) |
| 403 | `permission_denied`, `action_permission_denied`, `approver_mismatch` |
| 404 | `not_found` (missing, foreign-session or unknown route) |
| 405 | `method_not_allowed` |
| 409 | `stale_case_revision`, `case_not_investigable`, `investigation_in_progress`, `investigation_recovered`, `investigation_superseded`, `approval_expired`, `approval_exists`, `approval_not_available`, `approval_outside_validity`, `case_not_executable`, `stale_agent_config`, `stale_evidence_snapshot`, `stale_policy`, `stale_action_intent`, `inactive_policy`, `idempotency_conflict`, `conflict`, evidence-verification codes (`evidence_*`, `incomplete_evidence_snapshot`, `duplicate_evidence`) |
| 413 | `body_too_large` |
| 422 | `invalid_request` (body or query/path validation), `invalid_cursor`, `future_event_time` |

For a 409, re-read authoritative state before offering the next step. Codes are stable within v1; new codes may be added, so the UI should show a generic message for an unknown code.

## Example index

| File | Shows |
| --- | --- |
| session, overview | session metadata; per-state counts, totals, investigator name/version |
| ingest_below_threshold, ingest_replay, ingest_alert | non-alert scoring outcome, its replay, alerting ingestion with case |
| cases_page_1, cases_page_2, cases_filtered_open | cursor pagination and state filter |
| investigate, approval, execute, execute_replay | the main path, including idempotent replay |
| case_detail_closed, audit | final case state and audit timeline |
| error_approval_outside_validity, case_detail_reopened | expiry lifecycle |
| error_unauthenticated, error_not_found, error_invalid_request, error_stale_revision, error_idempotency_conflict | safe errors |

Not in the frozen set (C02 will supply fixtures): investigator failure, a rejected approval, and permission-denied sessions.
