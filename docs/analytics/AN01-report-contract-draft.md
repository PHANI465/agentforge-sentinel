# AN01 report contract draft (S1, revision r2)

Audience: Codex and the backend and frontend implementers. **Draft requiring review; not accepted.**
- Nothing below exists in the API today, and frozen contracts v1, v1.1 and v1.2 are not changed by it.
- Accepted routes would go in a new HTTP contract version, with a number assigned at acceptance. It would have exported OpenAPI and examples, following the existing `scripts/export_http_contract.py` process.
- Semantics come from [AN01-workspace-design.md](AN01-workspace-design.md), and the example values come from [AN01-acceptance-cases.md](AN01-acceptance-cases.md) and are recomputed by [check_an01.py](check_an01.py).

## 1. Routes, permissions and errors (draft)

```
GET /v1/reports/{report_id}?from=&to=&date_from=&date_to=&tz=&as_of=&currency=&direction=&limit=&cursor=
```

- **S1 has one route.** It is read-only. There is no export route in S1; CSV is the S2 proposal in design §11.
- **Permission.** The route requires **both** the existing `read_case` and the new draft capability `read_report`.
  - `read_report` is issued only by `sentinel create-session --capability read_report` (operator CLI). It is not in the CLI's default set, and no existing session is backfilled.
  - Widening the closed `Capability` sets is a contract change (§7).
- **Scope.** There is no tenant or session parameter. Scope always comes from the token.

**Errors** (existing envelope `{"error": code}`):

| Status | Code | When |
| --- | --- | --- |
| 401 | `unauthenticated` | no token, or an unknown or expired one |
| 403 | `permission_denied` | missing `read_case` or `read_report` |
| 404 | `not_found` | unknown `report_id` |
| 413 | `report_too_large` (new, draft) | more than 200,000 matching transactions (the guard query, design §8) |
| 422 | `invalid_request` | any invalid, missing or inapplicable filter; a range over the limit; `as_of > read_at`; a `tz` outside the allow-list; a window outside 2000–2037 |
| 422 | `invalid_cursor` (existing code) | a malformed cursor, or one whose report or filter digest differs from the request (§2) |
| 503 | `report_timeout` (new, draft) | the per-request statement or lock budget was exhausted |

Status 503 is not in today's `_ERRORS` map in `api.py`, so it is part of the new contract version.

## 2. Filters and cursor (validated server-side; the client validates for usability only)

| Filter | Applies to | Type and rule |
| --- | --- | --- |
| `from`, `to` | all | RFC 3339 instants with an offset (the existing strict pattern); half-open `[from, to)`; `from < to`; `to − from <= 92 × 86,400 s` |
| `date_from`, `date_to` | all | local dates `YYYY-MM-DD` in `tz`; `date_from` inclusive and `date_to` exclusive; at most 92 local dates. They are mutually exclusive with `from`/`to`, and the server maps them to the instants starting each local date (design §6) |
| `tz` | all | one of `UTC`, `Asia/Kolkata`, `Asia/Tokyo`, `Europe/London` or `America/New_York`; default `UTC` |
| `as_of` | all | an RFC 3339 instant `<= read_at`; default `read_at`; an availability filter, not a snapshot |
| `currency` | transaction reports and quality | repeatable; a subset of `USD`, `INR`, `GBP`, `JPY`. Inapplicable to `cases.workload` (422) |
| `direction` | transaction reports and quality | `debit` or `credit`. Inapplicable to `cases.workload` (422) |
| `limit` | `rows.transactions` only | 1–100, default 25 (the existing `MAX_PAGE_SIZE` and `DEFAULT_PAGE_SIZE` in `src/sentinel/contracts/http_v1.py`) |
| `cursor` | `rows.transactions` only | opaque; see below |

**Normalized filters and digest.**
- **Normalized form.** `from` and `to` are resolved to UTC instants (date mode included). `as_of` is resolved (the default becomes `read_at`). Currencies are sorted, and `direction` is the string or `null`. Timestamps are written as `YYYY-MM-DDTHH:MM:SS.ffffffZ`, always with six fraction digits.
- **`filter_digest`** is the SHA-256 hex of `"sentinel.report-filters.an01-s1\n"` followed by the canonical JSON of `{report_id, from, to, tz, as_of, currency, direction}`, with sorted keys and no spaces. `limit` is not bound.
- **Reference vector.** It is produced by `check_an01.py`'s canonicalization, so it checks a reimplementation, not the rule itself: `rows.transactions`, UTC window 2026-10-01, `tz=UTC`, `as_of` 2026-10-02T06:00Z, no currency or direction filter gives `8c8263345233e1427e5ecada81cfc42c7dc8943163c9058dd9fc83e0e24a04b6`.

**Cursor (drilldown only).**
- **Encoding.** URL-safe base64 without padding of the JSON array `["rows.transactions", filter_digest, last_occurred_at, last_id, first_matching, first_with_outcome]`, at most 400 characters (draft; the fixture's page-1 cursor is 215).
- **Next page.** Rows after `(last_occurred_at, last_id)` in `(occurred_at, id)` order. The last two members are page 1's consistency pair (design §5).
- **Request rules.**
  - **Missing:** the first page.
  - **Present:** the request must repeat the same filters with an explicit `as_of` equal to page 1's `provenance.as_of`. The server recomputes the digest, and a mismatch gets 422 `invalid_cursor`. So does a cursor from another report.
  - **Malformed:** too long, non-ASCII, not base64, not JSON, the wrong shape or member types, or a negative count: 422 `invalid_cursor`. This follows the existing `decode_cursor` style, which checks the shape before any parsing.
- **Tampering.** The cursor carries **no authority**; scope comes only from the token.
  - A tampered position only starts the page elsewhere inside the caller's own scoped, filtered rows.
  - A tampered digest is refused unless it matches the request's own filters, which is then just a legitimate query.
  - Tampered counts can only make the caller's own `row_set_changed` wrong.

  S1 therefore does not sign cursors (design open question 3).
- **Underlying data changed.** Pages are separate snapshots. Each page reports its own consistency pair, and `row_set_changed` is true when it differs from the pair in the cursor. The server never silently "repairs" a page.

## 3. Reports (S1)

All reports are read-only. Each runs in one `REPEATABLE READ, READ ONLY` transaction and is scoped to the session's `tenant_id` and `session_id`.

| ID | Rows | Columns (types and units) |
| --- | --- | --- |
| `transactions.currency_totals` | one per currency present (≤ 4) | `currency`, `currency_exponent` (int), `debit_count`, `credit_count` (int), `debit_minor`, `credit_minor`, `gross_minor`, `net_outflow_minor` (decimal **strings** of integers; net is signed) |
| `transactions.daily` | `buckets`: every local day touched by the window (≤ 94). `rows`: one per (day, currency) with activity (≤ 376) | buckets: `day` (local date), `start`, `end` (instants, clipped to the window), `day_seconds`, `covered_seconds` (int). rows: `day`, `currency`, `transactions`, `alerted`, `score_unknown` (int), `debit_minor`, `credit_minor` (strings) |
| `cases.workload` | one object with three sections | `created_in_window`: `by_current_state` (all 5 states, zeros included) and `time_basis: "cases.created_at"`. `actions_completed_in_window`: an int, `time_basis: "simulated_actions.completed_at"`. `open_now`: `by_state` (the 3 non-terminal states), `age_buckets` (`lt_1h`, `1h_8h`, `8h_24h`, `ge_24h`) and `time_basis: "read_at - cases.created_at"`, `window_applied: false`. Also `state_basis: "current_at_read"` |
| `data_quality.checks` | 7 rows, one per check | `check`, `value` (int), `denominator` (int or null), `unit`, `status` (`ok`, `attention` or `info`). Checks: `transactions_without_outcome`; `alerted_outcome_without_alert`; `alert_without_case`; `ingested_after_window_end` (`ingested_at >= to`); `ingestion_lag_p50_us`, `ingestion_lag_p95_us` and `ingestion_lag_max_us` (nearest rank: the ceil(p·n)-th smallest, which equals PostgreSQL `percentile_disc(p)`; integer microseconds; `status: info`) |
| `rows.transactions` (drilldown) | matching transactions in `(occurred_at, id)` order | `transaction_id`, `external_id` (inert text), `occurred_at`, `ingested_at`, `currency`, `currency_exponent`, `minor_units` (string), `direction`, `alerted` (bool or null), `score` (number or null), `scoring_kind`, `score_semantics` (or null), `case_id` (or null), `case_state` (or null; current at this page's `read_at`) |

- **Scores.** Score fields carry the stored `score_semantics`: `heuristic` for rule r1, `uncalibrated_score` for the trained model. They are never probabilities. A missing scoring outcome is `null` (and counted as `score_unknown`), never `false` or `0`.
- **What S1 never returns:** labels, `is_fraud`, disclosure-derived counts, account profiles or the account ID. Labels are deferred (design §9).

## 4. Response DTO (draft)

Example: `transactions.currency_totals` for the fixture. The values are recomputed by `check_an01.py`.

```json
{
  "report_id": "transactions.currency_totals",
  "report_version": "an01-s1-r2",
  "provenance": {
    "data": "synthetic",
    "scope": "current session",
    "window": {"from": "2026-10-01T00:00:00Z", "to": "2026-10-02T00:00:00Z"},
    "tz": "UTC",
    "tz_data": "zoneinfo tzdata 2026e",
    "as_of": "2026-10-02T06:00:00Z",
    "read_at": "2026-10-02T08:00:00Z",
    "snapshot": "per_request",
    "time_basis": "transactions.occurred_at",
    "notes": ["separate requests may reflect different committed data, even with the same as_of",
              "money is never summed across currencies",
              "replayed and rejected requests are not stored rows"]
  },
  "consistency": {"matching_transactions": 9, "with_outcome": 8},
  "columns": [{"name": "debit_minor", "type": "integer-string", "unit": "minor units of currency"}],
  "rows": [
    {"currency": "GBP", "currency_exponent": 2, "debit_count": 0, "credit_count": 1,
     "debit_minor": "0", "credit_minor": "10000", "gross_minor": "10000", "net_outflow_minor": "-10000"},
    {"currency": "INR", "currency_exponent": 2, "debit_count": 1, "credit_count": 1,
     "debit_minor": "8000000", "credit_minor": "250050", "gross_minor": "8250050", "net_outflow_minor": "7749950"},
    {"currency": "JPY", "currency_exponent": 0, "debit_count": 1, "credit_count": 0,
     "debit_minor": "200000", "credit_minor": "0", "gross_minor": "200000", "net_outflow_minor": "200000"},
    {"currency": "USD", "currency_exponent": 2, "debit_count": 3, "credit_count": 2,
     "debit_minor": "265500", "credit_minor": "7000", "gross_minor": "272500", "net_outflow_minor": "258500"}
  ],
  "next_cursor": null
}
```

**A drilldown page** adds `"page": {"limit": 4, "row_set_changed": false}` and a non-null `next_cursor` while more rows follow. Its `consistency` pair is the one counted in that page's own snapshot.

## 5. Calculation rules (normative for implementers)

1. **Integers only.** Sums are `sum((body->'amount'->>'minor_units')::numeric)`, returned as strings. Floats never touch money; lags are integer microseconds.
2. **Group by currency first.** There is never a total across currencies, not even "for display".
3. **Each stored transaction counts once.** Replay, conflict and invalid requests are not rows.
4. **Event-time reports** apply `from <= occurred_at < to` and `ingested_at <= as_of` to every statement, including each drilldown page. Workload uses its own bases (design §4).
5. **Scope.** `tenant_id = :t AND session_id = :s` on every table and on both sides of every join.
6. **Day buckets.** The server computes local-date start instants in Python `zoneinfo` (the first instant whose local date is D) and passes them as `timestamptz` parameters. SQL buckets compare `occurred_at` with those instants and never call `AT TIME ZONE` on local timestamps. `day_seconds` is the next start minus this start.
7. **One transaction per request.** First `SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY`, then read `read_at`, the guard count, the consistency pair and the report, all in that one transaction.
8. **No labels.** No S1 statement reads `fraud_disclosures`, `account_profiles`, agent-evaluation data or ML assets.

## 6. Example request sequence (drilldown, UTC fixture, `limit=4`)

| Request | Rows | Consistency | `row_set_changed` | `next_cursor` |
| --- | --- | --- | --- | --- |
| page 1 (no cursor) | R01, R05, R02, R16 | 9 / 8 | false | cursor after (10-01T10:00:00Z, R16's id) |
| page 2 | R14, R07, R15, R06 | 9 / 8 | false | cursor after R06 |
| page 3 | R03 | 9 / 8 | false | null |

R16 and R14 share `occurred_at` 10-01T10:00:00Z. Their order is decided by `id` (R16's id sorts before R14's), and the tie falls across the page boundary. The late-commit and slow-clock variants are in acceptance §3.

## 7. Contract impacts and open questions for review

Proposed resolutions are in [AN01-decisions-r3.md](AN01-decisions-r3.md). That is a proposal, not accepted. Among them: contract version v1.3, a derived 256-character cursor limit, and keeping the row cap and budget provisional until AN01-M1.

1. **Capability.** `read_report` needs `TrustedContext.capabilities` (`src/sentinel/contracts/v1.py`) and `Capability` (`src/sentinel/contracts/http_v1.py`) widened in a new contract version, plus a CLI choice outside the default set. The v1.x `SessionView` enum stays frozen. How a v1.x client should treat the new value is design open question 2.
2. **New error codes.** `report_too_large` (413) and `report_timeout` (503) are new. `invalid_cursor` (422) is reused.
3. **Index.** Draft migration `(tenant_id, session_id, occurred_at, id)` on `transactions`.
4. **Draft numbers:** 92 days, 200,000 matching rows, a 5,000 ms budget, a 400-character cursor and the age buckets. They need measurement before acceptance.
5. **`report_version`.** The draft string `an01-s1-r2` is replaced at acceptance.
6. **Export.** S2 only: `export_report` and `report_exports` (design §11).
