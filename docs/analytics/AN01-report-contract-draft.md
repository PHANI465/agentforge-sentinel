# AN01 report contract draft (S1)

Audience: Codex and the backend and frontend implementers. **Draft requiring review.** Nothing below exists in the API today, and frozen contracts v1, v1.1 and v1.2 are not changed by it. Accepted routes would go in a new HTTP contract version with exported OpenAPI and examples, following the existing `scripts/export_http_contract.py` process. Semantics come from [AN01-workspace-design.md](AN01-workspace-design.md).

## 1. Route and permission (draft)

```
GET /v1/reports/{report_id}?from=&to=&date_from=&date_to=&tz=&as_of=&currency=&direction=&limit=&cursor=
GET /v1/reports/{report_id}/export.csv?<same filters>
```

**Capabilities:**
- **Reading a report needs the existing `read_case`.** It reveals nothing beyond what the case list and overview already scope to the session.
- **Export needs a new draft capability `export_report`.** It is not granted to any existing session by default; that decision is part of review.

**Errors** (existing envelope `{"error": code}`):

| Status | Code | When |
| --- | --- | --- |
| 401 | `unauthenticated` | no or unknown token |
| 403 | `permission_denied` | no `read_case`; or export without `export_report` |
| 404 | `not_found` | unknown `report_id` |
| 413 | `report_too_large` (new, draft) | export over the row cap |
| 422 | `invalid_request` | any invalid or missing filter, range over 92 days, `as_of` in the future, unknown tz, or a cursor from another report or filter set |

There is no tenant or session parameter. Scope always comes from the token.

## 2. Filters (validated server-side; the client validates for usability only)

| Filter | Type and rule |
| --- | --- |
| `from`, `to` | RFC 3339 instants with an offset; half-open `[from, to)`; `from < to`; at most 92 days |
| `date_from`, `date_to` | local dates (`YYYY-MM-DD`), inclusive start and exclusive end, interpreted in `tz`. Mutually exclusive with `from`/`to` |
| `tz` | an IANA zone accepted by both zoneinfo and PostgreSQL; default `UTC`; used for date mapping and day buckets only |
| `as_of` | an RFC 3339 instant ≤ server now; default server now; only rows with `ingested_at <= as_of` |
| `currency` | repeatable; a subset of `USD`, `INR`, `GBP`, `JPY` |
| `direction` | optional; `debit` or `credit` |
| `limit` | drilldown only; 1–100, default 25 (the existing `MAX_PAGE_SIZE` and `DEFAULT_PAGE_SIZE`) |
| `cursor` | drilldown only; opaque. It encodes the report ID, a filter digest, `as_of` and the last `(occurred_at, id)`. It is refused (422) if any of these disagree with the request |

## 3. Reports (S1)

All reports are read-only, run in one `REPEATABLE READ, READ ONLY` transaction, and are scoped to the session's `tenant_id`/`session_id`.

| ID | Rows | Columns (types, units) |
| --- | --- | --- |
| `transactions.currency_totals` | one per currency present (and direction, if `direction` is given) | `currency`, `currency_exponent` (int), `debit_count`, `credit_count` (int), `debit_minor`, `credit_minor`, `gross_minor`, `net_outflow_minor` (decimal **strings** of integers; net is signed) |
| `transactions.daily` | one per (local day in `tz`, currency) with activity | `day` (local date), `day_hours` (23, 24 or 25), `currency`, `transactions`, `alerted`, `score_unknown` (int), `debit_minor`, `credit_minor` (strings) |
| `cases.workload` | one row | `cases_by_state` (current state, all 5 states, zeros included), `created_in_window` (int), `open_age_buckets` (`<1h`, `1–24h`, `>24h`: counts of open, investigating or awaiting_approval cases by `as_of − created_at`), `simulated_actions_in_window` (int), `state_basis: "current"` |
| `data_quality.checks` | one per check | `check`, `count`, `denominator`, `status` (`ok`/`attention`), `note`. Checks: transactions without a scoring outcome; alerts without a case; cases without an alert; ingestion lag p50/p95/max in seconds (nearest rank: the ceil(p·n)-th smallest, with n); events ingested after the window end |
| `labels.availability` | per `is_fraud` value, plus `unlabelled` | counts of window transactions with a disclosure where `recorded_at <= as_of` and `disclosed_at <= as_of`. No rates |
| `rows.transactions` (drilldown) | the transactions themselves, ordered by `(occurred_at, id)` | `transaction_id`, `external_id` (inert text), `occurred_at`, `ingested_at`, `currency`, `minor_units` (string), `currency_exponent`, `direction`, `alerted` (bool or null), `score` (number or null), `scoring_kind`, `case_id` (or null), `case_state` (or null) |

**Score fields** carry the existing `score_semantics` (`heuristic` for rule; `uncalibrated_score` for model). They are not probabilities. A missing scoring outcome is `null`, never `false` or `0`.

## 4. Response DTO (draft)

```json
{
  "report_id": "transactions.currency_totals",
  "report_version": "an01-s1",
  "provenance": {
    "data": "synthetic",
    "scope": "current session",
    "window": {"from": "2026-10-01T00:00:00Z", "to": "2026-10-02T00:00:00Z"},
    "tz": "UTC",
    "as_of": "2026-10-02T06:00:00Z",
    "generated_at": "2026-11-06T18:00:00Z",
    "snapshot": "one REPEATABLE READ, READ ONLY transaction"
  },
  "columns": [{"name": "debit_minor", "type": "integer-string", "unit": "minor units of currency"}],
  "rows": [{"currency": "USD", "currency_exponent": 2, "debit_count": 3, "credit_count": 1,
            "debit_minor": "265500", "credit_minor": "5000", "gross_minor": "270500",
            "net_outflow_minor": "260500"}],
  "next_cursor": null,
  "notes": ["money is never summed across currencies", "replays are not stored rows"]
}
```

**CSV export:**
- The same columns, preceded by a provenance block of `# key: value` comment lines. They are clearly labelled; the header row follows.
- Text cells beginning with `=`, `+`, `-`, `@`, a tab or a carriage return are prefixed with `'`. Integer strings and numbers are written as-is.
- UTF-8, with no BOM by default.

## 5. Calculation rules (normative for implementers)

1. Integers only. Sums use PostgreSQL `numeric` or `bigint` on minor units and are returned as strings. Floats never touch money.
2. Group by currency first. There is never a total across currencies, not even "for display".
3. Each stored transaction counts once. Replay and conflict requests are not rows.
4. The window filter applies to `occurred_at`; availability applies `ingested_at <= as_of`. Both apply to every report, including drilldown pages and exports.
5. Scope: `tenant_id = :t AND session_id = :s` on every table, and on both sides of every join.
6. Day buckets use `(occurred_at AT TIME ZONE :tz)::date`, with `day_hours` derived from the zone's offsets at that day's boundaries.
7. Labels: a disclosure counts only with both `recorded_at <= as_of` and `disclosed_at <= as_of`. Unlabelled is never negative.

## 6. Open questions for review

1. The `export_report` capability and how a local or demo session would get it.
2. Export auditing: `audit_events.case_id` is required today. The options are a draft `report_exports` table, or making the case link optional.
3. The index migration `(tenant_id, session_id, occurred_at, id)` on `transactions`, versus generated amount columns.
4. Whether `labels.availability` belongs in S1 or waits for the labelled evaluation-set specification.
5. The default `as_of` age at which the UI flags a report as stale.
