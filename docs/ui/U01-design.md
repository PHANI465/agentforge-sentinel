# U01 analyst workbench — design note

Status: blocked. No `web/` application is implemented in this commit.

## Base and the missing contract

- Task branch: `task/cursor-analyst-ui`.
- Worktree: `E:\PHANI\sentinel-wt\cursor-analyst-ui`.
- Base commit: `9e49a87b2a7d50c0fdcc3823cd87a07e49a856ae` on `task/coordination` (`docs: dispatch C01 review corrections and record delivered packages`).
- Queue read with `git show task/coordination:docs/TASK_QUEUE.md` at that commit. U01 is **BLOCKED ON ACCEPTED C01**. U02 additionally waits for accepted C02. U03 waits for the accepted C07 model-results contract.
- Accepted C01 dependency commit: **none**.

Codex reviewed `0a6fb0ec8e63fd686ac7e4cf6bbfb7bd22a105b0` and requested changes (R9 malformed cursor, R10 error-contract accuracy). See `docs/reviews/0a6fb0e.md`. A passing strict check on that commit is not acceptance.

`git log task/claude-api-contracts` shows a later candidate, `2e6c2329aafe28b2e7c31ef5078d554cb66ca529` (`C01 review R9/R10: strict cursor validation, scoped error contract`), parent `0a6fb0e`. Its message says cursor members must be strings and that `ErrorResponse` covers handled errors only. Codex has not accepted that commit. This branch does not merge it, does not copy its OpenAPI snapshot, and does not treat it as the UI contract.

Exact missing contract: a Codex acceptance record that names one C01 commit and thereby freezes, for the analyst client:

- `contracts/http/openapi.v1.json`
- `contracts/http/examples/*.json`
- the pagination, score-label and error semantics in that commit’s `docs/api/README.md`, including `422 invalid_cursor` for a malformed cursor and a client fallback for non-JSON 5xx, empty bodies, invalid bodies and network failures
- the response models that commit exports (`SessionView`, `Overview`, `CasePage`, `CaseDetail`, `IngestResponse`, `ExecuteResponse`, `ErrorResponse`, and the domain records they embed)

The typed client is generated from that accepted snapshot. If review moves the tip past `2e6c232`, implementation waits for the accepted SHA and reads that tree with `git show`, not another worktree’s working copy.

## Surfaces described by the unaccepted candidate

These routes are quoted from `git show 2e6c232:docs/api/README.md`. They are the intended binding if Codex accepts `2e6c232` unchanged. They are not implemented here.

| Method and path | Success | Client use |
| --- | --- | --- |
| GET `/healthz` | 200 `Health` | Connection probe. `investigator` is a server string. |
| GET `/v1/session` | 200 `SessionView` | Tenant, session, actor, sorted capabilities, expiry. The body has no bearer token. |
| GET `/v1/overview` | 200 `Overview` | Counts and `investigator.name` / `investigator.version`. |
| POST `/v1/transactions` | 201 `IngestResponse` | Synthetic entry when the session has `ingest_transaction`. Replay keeps `external_id` and the same body. |
| GET `/v1/cases` | 200 `CasePage` | Queue. `limit` 1–100, default 25. Optional `state`. Opaque `next_cursor` is sent back unchanged. |
| GET `/v1/cases/{case_id}` | 200 `CaseDetail` | Detail, evidence, runs, server-built intents. |
| GET `/v1/cases/{case_id}/audit` | 200 audit list | Oldest first. |
| POST `/v1/cases/{case_id}/investigations` | 200 `CaseDetail` | Body is `expected_revision` only. |
| POST `/v1/approvals` | 201 `Approval` | `action_intent_id` plus `approved` or `rejected`. |
| POST `/v1/actions` | 200 `ExecuteResponse` | `approval_id` plus one `idempotency_key`. |

Every `/v1/*` call sends `Authorization: Bearer` from memory. Tokens are issued outside HTTP (`python -m sentinel.cli create-session`, later C02 fixtures). There is no login or capability-granting route to invent.

Handled errors use `{"error": "<code>"}` and, for invalid JSON bodies, `details: [{"code": ...}]`. Stable codes are listed in that same API note (400, 401, 403, 404, 405, 409, 413, 422). An unknown code gets a generic message that includes the code when the body validated, and omits the raw body.

## Client behavior to implement against the accepted fixtures

React, TypeScript and Vite, in `web/`. Same-origin dev server: proxy `/healthz` and `/v1` to the local API. The existing smoke helper defaults to `http://127.0.0.1:8000` (`scripts/smoke_thin_path.py`). Override with an environment variable for another local origin. The browser talks only to the Vite origin. No backend CORS or auth edit.

Session. A labeled token field submits into component memory. Sign-out drops that memory and returns to the signed-out screen. Reload starts signed out. The token is absent from the URL, `localStorage`, `sessionStorage` and document cookies. Connection state is disconnected, checking, connected, unauthenticated (401) or unavailable. Connected state shows actor, session expiry and capabilities from `GET /v1/session`, plus investigator name and version from `GET /v1/overview`.

Queue and overview. Overview counts render from `cases_by_state`, `transactions`, `alerts` and `simulated_actions`. The queue shows loading, empty and error states. Each row shows state, revision, external id, direction and the exact amount. Pagination controls use the returned cursor only. A `422 invalid_cursor` response resets to the first page and shows the safe error. State filter values are the contract states: `open`, `investigating`, `awaiting_approval`, `closed`, `inconclusive`.

Amounts. Display `minor_units` with `currency_exponent` by placing a decimal point in the integer digits (USD/INR/GBP exponent 2, JPY exponent 0). Totals stay in integer minor units per currency. Currencies are never added together.

Scores and modes. A recorded score shows `scoring_kind`, `score_semantics`, numeric score, threshold, and scorer / features / threshold artifact name and version. `rule` + `heuristic` is labeled as a rule score, not a probability. A null legacy score is labeled unknown. `model` + `estimated_probability` is shown with the server’s semantics label when a response contains it. Charts and experiment counts wait for U03 and the accepted C07 fixtures. Investigator mode comes from `overview.investigator`: `deterministic-investigator` is the deterministic investigator, `claude-cli-investigator` is the local Claude investigator, and any other name is shown as returned. The client does not switch `SENTINEL_INVESTIGATOR` and does not call a model.

Case detail. Show the transaction, evidence facts, investigator finding and the audit timeline. `finding.rationale` is inert text (a text node). HTML and Markdown are not interpreted. The proposed action is the server-built `action_intents` entry whose `intent.case_revision` equals `case.revision`. Older intents stay in history. Parameters, evidence snapshot and policy artifact are rendered from that intent.

Decisions. Approve and reject are separate from execute. Buttons follow `SessionView.capabilities` (`approve_action`, `execute_simulated_action`) and `actor_kind: human`. The server remains the authority: 403 `permission_denied`, `action_permission_denied` and `approver_mismatch` stay visible as permission failures. Execute creates one UUID idempotency key for that approval and keeps it in memory for that attempt.

Idempotency. An ambiguous `POST /v1/actions` result is a network failure, timeout, any 5xx, or a body that is empty, non-JSON or invalid `ErrorResponse`. The client keeps the original key, shows a generic message that the outcome is unknown, refetches the case, and retries with that same key. A later `replayed: true` shows the original action. A handled 4xx is a definite outcome. A new key is created only when the analyst starts a new execution on a newly read approval. Component tests cover key retention for a lost or unreadable response. One persisted database row for that lost response is a U02 assertion and needs the accepted C02 fixture.

Conflicts and lifecycle. Any 409 refetches the case before the next step. `stale_case_revision` asks the analyst to continue from the new revision. `approval_expired` and `approval_outside_validity` show the reopened case (`open`, new revision, `approval_expired` audit). The lapsed approval is not offered again. The next step is a new investigation, then a new approval. A failed run shows `failure_code` (`provider_unavailable`, `timeout`, `invalid_output`, `budget_exhausted`) and the reopened case. `investigation_recovered` also refetches. Rejection closes the case when the server says so.

Failure parsing. Parse `ErrorResponse` only when the status is 4xx or 5xx, the content type is JSON, and the body validates. Otherwise show one safe generic message and do not render the raw body. Ingestion retries reuse the same `external_id` and body after an ambiguous `POST /v1/transactions`.

Accessibility. The token field, sign-out, queue rows, pagination, approve, reject and execute are named controls. Status text is in a live region. Loading, empty and error states include text. Keyboard users can reach every action without a pointer.

Tests once unblocked. Typecheck and production build. Client tests against the accepted example JSON for queue, detail, inert rationale, 409 refetch, permission flags, replayed execution, and ambiguous execution retaining one key. Browser coverage of Postgres persistence, restart, cross-session denial and a lost response with one stored action is U02, after accepted C02, using the deterministic investigator.

## Out of scope until later gates

- U02 browser → API → disposable Postgres. C02’s accepted fixture is still missing. The C01 review already notes that investigator failure, rejected approval and permission-denied sessions are not in the frozen C01 example set.
- U03 charts. Counts must match accepted report fixtures. Synthetic limits stay labeled as synthetic.
- Edits to `src/sentinel/`, `contracts/`, Python dependencies, migrations, `docs/STATUS.md` and `docs/TASK_QUEUE.md`.
- Reused AgentForge UI source. None is copied in this note. A later reuse records repository, path, commit and required notices.

## Next action

Codex accepts a C01 commit, or requests further changes. On acceptance of commit `S`, implement this note in `web/` bound to `S` and its fixtures. If `S` is not `2e6c232`, re-read `S` before generating types.
