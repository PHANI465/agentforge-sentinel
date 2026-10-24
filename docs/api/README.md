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

Every **handled** error (the codes below, plus unknown routes/methods and request validation) returns `ErrorResponse`: `{"error": "<code>"}`, plus `details: [{"code": ...}]` for invalid JSON bodies. No field names, values or input are echoed. This is not a guarantee for every failure; see the next section.

| Status | Codes |
| --- | --- |
| 400 | `invalid_content_length` |
| 401 | `unauthenticated` (missing, unknown or expired token) |
| 403 | `permission_denied`, `action_permission_denied`, `approver_mismatch` |
| 404 | `not_found` (missing, foreign-session or unknown route) |
| 405 | `method_not_allowed` |
| 409 | `stale_case_revision`, `case_not_investigable`, `investigation_in_progress`, `investigation_recovered`, `investigation_superseded`, `approval_expired`, `approval_exists`, `approval_not_available`, `approval_outside_validity`, `case_not_executable`, `stale_agent_config`, `stale_evidence_snapshot`, `stale_policy`, `stale_action_intent`, `inactive_policy`, `idempotency_conflict`, `conflict`, evidence-verification codes (`evidence_*`, `incomplete_evidence_snapshot`, `duplicate_evidence`) |
| 413 | `body_too_large` |
| 422 | `invalid_request` (body or query/path validation), `invalid_cursor`, `future_event_time`, `account_profile_missing` (v1.1, model mode only) |

For a 409, re-read authoritative state before offering the next step. Codes are stable within v1; new codes may be added, so the UI should show a generic message for an unknown code.

## Failures outside the error contract (client fallback is required)

The API does not guarantee a JSON body for every failure:
- An unexpected server exception, such as a storage outage or a response that fails its own model validation, returns **HTTP 500 with a non-JSON body** (currently `text/plain` "Internal Server Error"). Internals are not echoed (tested).
- A proxy, gateway, timeout or runtime in front of the API can return other non-JSON 5xx pages, an empty body or a truncated or invalid body.
- A network failure can produce no response at all.

Client requirements:
1. Parse an error body as `ErrorResponse` only if the status is 4xx/5xx, the content type is JSON and the body validates. Otherwise show a safe generic message and never render the raw body.
2. Treat any non-JSON 5xx, empty or invalid body, timeout or network failure as **outcome unknown**. Re-read authoritative state (`GET /v1/cases/{id}`) before offering the next step.
3. **Execution:** after an ambiguous `POST /v1/actions` failure (network failure, timeout, any 5xx, or an unparseable body), retry with the same `idempotency_key`; never generate a new one. An ambiguous failure does not establish that no action occurred. The retry either returns the original action (`replayed: true`) or a handled error. Only a handled 4xx/409 response is a definite outcome.
4. Ingestion retries reuse the same `external_id` and body for the same reason.

Safe logging and observability for unexpected errors are tracked separately (C05).

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

## HTTP v1.1 revision (C07 contract candidate)

Status: **candidate for Codex review; not accepted.** U03 must not consume it until Codex accepts it by commit. The C07 inference increment adds model-mode examples and one error code without changing the reviewed shapes. The revision is explicit and additive:

- **Active snapshot:** `contracts/http/openapi.v1.1.json`, with `info.version` 1.1.0.
- **Legacy snapshot:** `contracts/http/openapi.v1.json` is **frozen**. It is checked by SHA-256 (`scripts/export_http_contract.py`, `LEGACY_V1_SHA256`) and never regenerated.
- **v1 bodies are unchanged:** the 21 v1 examples in `contracts/http/examples/` are still regenerated by the deterministic rule-mode run and are byte-identical to the accepted C01 set.
- **Compatibility, tested in `tests/test_http_contract_v11.py`:**
  - every v1 path, method, request body, response and security entry is identical in v1.1;
  - v1 component schemas gain only optional properties and wider enums, with no new required fields;
  - all v1 examples still validate.
- **New examples:** `contracts/http/examples-v1.1/`, recorded from real rule-mode and model-mode servers.

### What changed

| Change | Detail |
| --- | --- |
| `score_semantics` | Adds `uncalibrated_score`, a trained model's ranking score in [0, 1] and **not a probability**. A rule is always `heuristic`; a model is never `heuristic`. |
| `ScoringOutcome.model` (optional) | `ModelProvenance`: `protocol_version`, `protocol_sha256`, `selection_sha256`, `candidate`, `artifact_sha256`, `feature_version`, `threshold_source` (`validation_frozen_threshold`), `results_id`. Present exactly when `scoring_kind` is `model`. |
| `ScoringOutcome.inputs` (optional) | `ScoringInputs`: the exact f1 feature values scored, plus currency, the number of history rows and fraud disclosures used, and the account profile's home currency and `opened_at`. Present exactly for model outcomes. Absent keys are **omitted, not null**, so rule outcomes serialize exactly as in v1. |
| `GET /v1/scoring` | `ScorerInfo` for the server's configured scorer: mode, kind, semantics, scorer/features/threshold-policy `ArtifactRef`s, threshold, `alert_rule: "score >= threshold"`, `model` provenance (null for the rule) and `results_id`. Requires `read_case`. |
| `GET /v1/model-results/{results_id}` | `ModelResults`: the frozen C04 offline results, served from packaged server-owned byte copies of `evals/ml/p1`. Only the registry id `p1` exists; any other value returns `404 not_found` (no filesystem path is ever derived from it). Requires `read_case`. |

### Semantics U03 must preserve

- **Which threshold applies:**
  - **Rule mode** (the default) alerts at the rule threshold 0.5, as in v1.
  - **Model mode** alerts when `score >= threshold`, using the **frozen validation threshold** (4.0295e-06 for `hgb_balanced@p1`). It does not use the rule cutoff or the offline daily top-15 batch policy; daily top-k results are offline evidence only.
- **Model results labels:** model results are labeled `"offline synthetic benchmark"` with `synthetic: true` and carry a `limitations` list. Display them as such. Charts and counts must come from these fields, which match the frozen C04 report (tested).
- **Scenario:** `scenario` appears only in offline `slices`, as hidden synthetic truth. It is never a model input or a live field.
- **Coexisting scorers:** a case or outcome keeps the scorer that produced it. Switching the server's scorer never rescores old records. The UI should show each record's own `scoring_kind`, `score_semantics` and `scorer`, not assume the current `/v1/scoring` applies to history.

### New error code

- `422 account_profile_missing`: model mode cannot score a transaction whose account has no provisioned profile (home currency and opened-at) in the caller's scope. Nothing is stored, and nothing falls back to the rule (example `examples-v1.1/error_account_profile_missing.json`).
- A server configured with a model that fails its identity binding does not start; there is no runtime fallback.

### Model-mode examples

`ingest_model_alert`, `ingest_model_replay` and `case_detail_model` in `examples-v1.1/` come from a real model-mode server. They show `scoring.model`, `scoring.inputs`, the frozen threshold and case pins naming `hgb_balanced`. The replay is byte-identical apart from `replayed: true`.

### Operator notes (model mode)

1. Install with the ml extra: `uv sync --locked --extra ml`, or install the wheel plus the lock's ml pins. Rule mode does not need it.
2. Run `sentinel.cli migrate` (applies `0004_scoring_profiles.sql`), then `grant-runtime` (adds SELECT on `account_profiles` and `fraud_disclosures`).
3. Run `create-session`, then load inputs for that tenant and session as the schema owner:
   - `python -m sentinel.cli provision-accounts --tenant T --session S --file profiles.jsonl`, with one `{"account_id", "home_currency", "opened_at"}` object per line;
   - `python -m sentinel.cli record-disclosures --tenant T --session S --file disclosures.jsonl`, with `{"external_id", "account_id", "is_fraud", "disclosed_at"}` per line. Only disclosures with `disclosed_at <= decision time` count.
4. Start the API with `SENTINEL_SCORER=model:hgb_balanced@p1` and the runtime-role URL. Leaving it unset, or setting `rule`, keeps the default rule.
5. Switching scorers never rescores stored outcomes or cases.
