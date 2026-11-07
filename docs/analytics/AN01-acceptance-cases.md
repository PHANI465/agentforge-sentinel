# AN01 acceptance cases and known-answer fixture (revision r2)

Audience: the implementers and reviewers of AN01-S1.
- **What was run.** The arithmetic in §2 and §3 is recomputed by [check_an01.py](check_an01.py), a stdlib-only script with no network, database, files or time-zone database. Run it with `uv run --locked python docs/analytics/check_an01.py`.
- **What was not run.** The database, API and browser cases in §4 are **proposed and unrun**: no report route exists. The fixture construction in §1 is also unrun; it is a plan derived from reading the code at `dd6518d`.
- All data is synthetic. Nothing here reads the ML holdout, agent-final cases or evaluation packets.

## 1. Fixture

**Scopes:**
- **S1** is the analyst's session in tenant T1. It is issued with the five capabilities `ingest_transaction`, `read_case`, `approve_action`, `execute_simulated_action` and `read_report`. Reports are session-scoped, so the session that loads the data is the one that reads it.
- **S2** is another session of T1. It is created in the test harness with `Sentinel.create_session(tenant_id=T1)`, because the CLI has no tenant flag.
- **T2** is another tenant.

**Harness (proposed; unrun):**
- The service runs in rule mode r1 with the deterministic investigator i1 and a `FakeClock` (`tests/conftest.py`), injected as `Sentinel(clock=…)` and set before each call.
- Each S1 row uses its own `account_id`, so `prior_count_1h = 0` for every decision. The r1 score is then 0.6 (alert) if `minor_units >= large_amount_minor[currency]`, and 0.0 otherwise. The cutoffs are USD/GBP 100,000, INR 8,000,000 and JPY 150,000.
- The **Alerted** column below is what r1 computes for these inputs, and the checker asserts that. It is not a value injected into the database.

**Report parameters:** window `[2026-10-01T00:00:00Z, 2026-10-02T00:00:00Z)`, `tz=UTC`, `as_of=2026-10-02T06:00:00Z`, and all reads at `read_at=2026-10-02T08:00:00Z`, after every fixture write committed.

| Row | Scope | How created | external_id | id ends | Currency (exp) | Direction | minor_units | occurred_at (UTC) | ingested_at (UTC) | Response | Alerted (r1) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R01 | S1 | POST | an-01 | a001 | USD (2) | debit | 12500 | 10-01 00:00:00 | 10-01 00:00:05 | 201 | no |
| R02 | S1 | POST | an-02 | a002 | USD (2) | credit | 5000 | 10-01 08:15:00 | 10-01 08:15:01 | 201 | no |
| R03 | S1 | POST | an-03 | a003 | USD (2) | debit | 250000 | 10-01 23:59:59.999 | 10-02 00:00:01 | 201 | **yes** |
| R04 | S1 | POST | an-04 | a004 | USD (2) | debit | 999 | 10-02 00:00:00 | 10-02 00:00:02 | 201 | no |
| R05 | S1 | POST | an-05 | a005 | INR (2) | debit | 8000000 | 10-01 05:30:00 | 10-01 05:30:02 | 201 | **yes** (exactly at the INR cutoff) |
| R06 | S1 | POST | an-06 | a006 | INR (2) | credit | 250050 | 10-01 18:31:00 | 10-01 18:31:01 | 201 | no |
| R07 | S1 | POST | an-07 | a007 | JPY (0) | debit | 200000 | 10-01 12:00:00 | 10-01 12:00:01 | 201 | **yes** |
| R08 | S1 | POST | an-08 | a008 | GBP (2) | debit | 7525 | 10-01 09:00:00 | **10-02 07:00:00** | 201 | no |
| R09 | S1 | POST | an-01 | — | USD (2) | debit | 12500 | 10-01 00:00:00 | — | 201 `replayed: true` (R01's body) | — |
| R10 | S1 | POST | an-01 | — | USD (2) | debit | 13000 | 10-01 00:00:00 | — | 409 `idempotency_conflict` | — |
| R11 | **S2** | POST | an-11 | a011 | USD (2) | debit | 777777 | 10-01 10:00:00 | 10-01 10:00:01 | 201 | yes |
| R12 | **T2** | POST | an-12 | a012 | USD (2) | debit | 500000 | 10-01 11:00:00 | 10-01 11:00:01 | 201 | yes |
| R13 | S1 | POST | an-13 | — | USD (2) | debit | 0 | 10-01 13:00:00 | — | 422 (`minor_units` must be > 0) | — |
| R14 | S1 | **operator fixture** | an-14 | e014 | USD (2) | debit | 3000 | 10-01 10:00:00 | 10-01 10:00:03 | none (no request) | **unknown** (no outcome row) |
| R15 | S1 | POST | an-15 | a015 | GBP (2) | credit | 10000 | 10-01 14:00:00 | 10-01 14:00:02 | 201 | no |
| R16 | S1 | POST | an-16 | a016 | USD (2) | credit | 2000 | 10-01 10:00:00 | 10-01 10:00:04 | 201 | no |

- **Transaction IDs.** They are fixed in the fixture, so the order is deterministic. Each is `00000000-0000-4000-8000-00000000` followed by the four characters shown. R16 (`…a016`) and R14 (`…e014`) share `occurred_at`, and R16 sorts first.
- **R14 is not producible through today's API.** Modern ingestion inserts the `scoring_outcomes` row in the same transaction as the transaction (`_ingest`).
  - R14 is therefore an **explicitly labelled operator/migration fixture**: the schema owner inserts one `transactions` row with a valid v1 `Transaction` body and *no* outcome. That is the state migration 0002 says rows ingested before it have.
  - It must be inserted by the owner role, never through the runtime API, and the test must name it as such.
- **Cases** (created by ingestion at `ingested_at`), then the workflow through the API under the FakeClock. This is expected from reading the code, and unrun:

  | Case of | `created_at` | Later steps | Current state |
  | --- | --- | --- | --- |
  | R03 | 10-02 00:00:01 | investigation at 10-02 00:20:00. i1 finds a large amount with no priors, so `escalate` / `unusual_amount` → awaiting_approval. No approval | awaiting_approval |
  | R05 | 10-01 05:30:02 | investigation 05:40:00 → awaiting_approval (`escalate`); approval 05:45:00 (expires 05:50:00, 300 s TTL); `POST /v1/actions` 05:46:00 → simulated action succeeded, `completed_at` 05:46:00 → closed | closed |
  | R07 | 10-01 12:00:01 | none | open |

- **Disclosures,** loaded by the operator `record-disclosures` under the FakeClock:
  - R05: `is_fraud=true`, `disclosed_at` 10-02 07:30, `recorded_at` 10-02 07:31.
  - R07: `is_fraud=false`, disclosed 10-01 20:00, recorded 10-01 20:05.

  Labels are deferred from S1. These rows exist only so that test A11 can prove no S1 output exposes them.

## 2. Expected answers

All values below are asserted by `check_an01.py`.

**Requests versus stored rows** (kept separate):

| Count | Value |
| --- | --- |
| API requests, all scopes (R01–R13, R15, R16) | 15 |
| Operator fixture rows (R14) | 1 |
| S1 API requests | 13: **201 new 10**, 201 replayed 1 (R09), 409 1 (R10), 422 1 (R13) |
| Stored transactions, all scopes | 13 |
| Stored transactions in S1 | 11 (R01–R08, R14, R15, R16) |
| S1 `scoring_outcomes` rows | 10 (all except R14) |
| S1 alerts / cases | 3 / 3 (R03, R05, R07) |

**Rows in the window, as of `as_of`, in S1:** R01, R02, R03, R05, R06, R07, R14, R15 and R16, which is **9**.
- R04 is at the exclusive end of the window.
- R08 was ingested after `as_of`.
- R09, R10 and R13 were never stored.
- R11 and R12 are in foreign scopes.

**`transactions.currency_totals` (UTC):**

| Currency | debit n | debit_minor | credit n | credit_minor | gross_minor | net_outflow_minor | Display of net |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GBP | 0 | "0" | 1 | "10000" | "10000" | "-10000" | -100.00 GBP |
| INR | 1 | "8000000" | 1 | "250050" | "8250050" | "7749950" | 77,499.50 INR |
| JPY | 1 | "200000" | 0 | "0" | "200000" | "200000" | 200,000 JPY (exponent 0) |
| USD | 3 | "265500" | 2 | "7000" | "272500" | "258500" | 2,585.00 USD |

There is no total across currencies. The count across currencies is 9 (USD 5, INR 2, JPY 1, GBP 1).

**Local dates in `tz=Asia/Kolkata`** (`date_from=2026-10-01`, `date_to=2026-10-02`, which is `[09-30T18:30Z, 10-01T18:30Z)`):
- Rows: R01, R02, R05, R07, R14, R15 and R16, which is **7**. R03 (23:59:59.999Z) and R06 (18:31Z) fall after 18:30Z.
- Totals: USD debit 2 / "15500", credit 2 / "7000", gross "22500", net "8500"; INR debit 1 / "8000000", net "8000000"; JPY "200000"; GBP credit "10000", net "-10000".

**`transactions.daily`, `tz=UTC`:** one bucket, 2026-10-01 (`day_seconds` 86,400, `covered_seconds` 86,400).

| Currency | transactions | alerted | score_unknown | debit_minor | credit_minor |
| --- | --- | --- | --- | --- | --- |
| GBP | 1 | 0 | 0 | "0" | "10000" |
| INR | 2 | 1 | 0 | "8000000" | "250050" |
| JPY | 1 | 1 | 0 | "200000" | "0" |
| USD | 5 | 1 | 1 | "265500" | "7000" |

Alerts across currencies: 3 of 9, with R14 as `score_unknown` (1 of 9), never "not alerted".

**`transactions.daily`, the same UTC *instant* window with `tz=Asia/Kolkata`:** the window cuts two local days.

| Bucket | start → end (clipped) | day_seconds | covered_seconds | Rows (currency: n, alerted, unknown, debit, credit) |
| --- | --- | --- | --- | --- |
| 2026-10-01 | 10-01T00:00Z → 10-01T18:30Z | 86,400 | 66,600 | GBP 1,0,0,"0","10000"; INR 1,1,0,"8000000","0"; JPY 1,1,0,"200000","0"; USD 4,0,1,"15500","7000" |
| 2026-10-02 | 10-01T18:30Z → 10-02T00:00Z | 86,400 | 19,800 | INR 1,0,0,"0","250050"; USD 1,1,0,"250000","0" |

**`cases.workload`** (S1; window and `as_of` as above; `read_at` 10-02T08:00Z):
- **Created in window** (`cases.created_at`): R05 and R07, so **2**. By current state: open 1, closed 1, investigating 0, awaiting_approval 0, inconclusive 0.
  - R03 is **not** counted: its case was created at 10-02T00:00:01Z, after `to`, although its transaction's event time is inside the window.
- **Actions completed in window** (`completed_at`): **1** (R05, at 05:46:00).
- **Open now** (`read_at − created_at`, no window, no `as_of`): R03 (awaiting_approval, 28,799 s, so `1h_8h`, one second under 8 h) and R07 (open, 71,999 s, so `8h_24h`). Buckets: `lt_1h` 0, `1h_8h` 1, `8h_24h` 1, `ge_24h` 0.
- R11 and R12 are never counted.

**`data_quality.checks`:**

| Check | Value | Denominator |
| --- | --- | --- |
| transactions_without_outcome | 1 (R14) | 9 |
| alerted_outcome_without_alert | 0 | 3 |
| alert_without_case | 0 | 3 |
| ingested_after_window_end | 1 (R03) | 9 |
| ingestion_lag_p50_us | 2,000,000 (the 5th of 9) | n = 9 |
| ingestion_lag_p95_us | 5,000,000 (the 9th of 9; ceil(0.95 × 9) = 9) | n = 9 |
| ingestion_lag_max_us | 5,000,000 | n = 9 |

The sorted lags in µs are [1,000,000, 1,000,000, 1,000,000, 1,001,000, 2,000,000, 2,000,000, 3,000,000, 4,000,000, 5,000,000]. R03's lag is 1.001 s.

**`rows.transactions` drilldown** with `limit=4`, ordered by `(occurred_at, id)`: see contract §6.
- Page 1 is R01, R05, R02, R16.
- Page 2 is R14, R07, R15, R06.
- Page 3 is R03, with `next_cursor: null`.

Every page reports `matching_transactions` 9 and `with_outcome` 8, and `row_set_changed` false. The page-1 cursor is 215 characters, under the draft 400.

**Money bounds** (verified constants: `MAX_MINOR_UNITS = 9,000,000,000,000`):
- 1,000 maximum rows sum to 9,000,000,000,000,000, which is JavaScript-safe.
- 1,001 rows sum to 9,009,000,000,000,000, which is not safe (the limit is 9,007,199,254,740,991). That is why sums are strings.
- The draft cap of 200,000 rows gives at most 1,800,000,000,000,000,000, which is under the `bigint` maximum.

**Local day lengths** (seconds; offsets from tzdata 2026e, checked once with `zoneinfo`; the checker re-does only the arithmetic):
- In the S1 allow-list: New York 2026-03-08 82,800 and 2026-11-01 90,000; London 2026-03-29 82,800 and 2026-10-25 90,000.
- Outside it: Lord Howe 2026-10-04 84,600 and 2026-04-05 88,200; Troll 2026-03-29 79,200 and 2026-10-25 93,600.

## 3. Thought experiments with known answers

**T1, late commit.** The setup:
- The drilldown uses `limit=4` with the default `as_of` = `read_at` = 10-02T08:00:00Z, so R08 is now included and page 1 has 10 matching rows.
- An ingest of L1 (S1, USD debit 4000, `occurred_at` 10-01T07:00Z, id `…b017`) reads its clock at 07:59:59.900 but commits at 08:00:00.200, after page 1's snapshot. Pages 2 and 3 are read at 08:00:10 and 08:00:20 with `as_of` 08:00:00 carried.

| Page | Rows | Consistency | row_set_changed |
| --- | --- | --- | --- |
| 1 | R01, R05, R02, R08 | 10 / 9 | false |
| 2 | R16, R14, R07, R15 | 11 / 10 | **true** |
| 3 | R06, R03 | 11 / 10 | **true** |

- L1 sorts before page 1's cursor (09:00, R08), so it never appears in this page sequence. It is *missed*, and the flag says so.
- `currency_totals` with the same filters gives USD `debit_minor` "265500" at 08:00:00 and "269500" at 08:00:10. The same `as_of` gives a different answer, which is why `as_of` is not a snapshot.

**T2, a slow clock.** A second API process runs 3 s behind.
- It ingests L2 (S1, USD debit 1500, `occurred_at` 10-01T11:00Z, id `…b018`) at real 08:00:02, stamps it 07:59:59 (`<= as_of`) and commits at 08:00:02.050.
- L2 sorts after the cursor, so it *shifts* page 2: page 2 is R16, R14, L2, R07, and page 3 is R15, R06, R03. Pages 2 and 3 are flagged `row_set_changed`.

**T3, tied timestamps.**
- **An `occurred_at` tie across a page boundary.** R16 and R14 share 10:00:00Z. The keyset `(occurred_at, id) > (10:00:00Z, …a016)` puts R14 first on page 2. Ordering by `id` alone decides it, never by insertion order or `external_id`.
- **An `ingested_at` tie at `as_of`.** R08 (stamped exactly 10-02T07:00:00Z) is included at `as_of` = 07:00:00 (`<=`) and excluded at 06:59:59.999999.
- Two rows with the same stamp are both included or both excluded. No ordering uses `ingested_at`.

**T4, a past `as_of` is not history.** With `as_of` = 10-01T05:43:00Z (same window, `read_at` 08:00):
- Only R05's case was created by then, so created in window is 1.
- It is shown as **closed** (its current state), although at 05:43 it was awaiting_approval (investigated at 05:40, closed at 05:46).
- Actions completed in window is 0, because 05:46 > 05:43.

The workload section says `state_basis: "current_at_read"`.

**T5, cursors.**
- A page-1 cursor replayed with `as_of` 07:00 instead of 06:00 gets `invalid_cursor`, because the digest differs.
- So do these malformed inputs: `!!` (not base64), `W10` (decodes to `[]`), a truncated cursor, a 401-character string, and an array with a negative count.

## 4. Proposed acceptance tests for the implementation (not run)

| ID | Case | Expected |
| --- | --- | --- |
| A1 | Reconciliation | Loading §1 by its stated method (API rows through `POST /v1/transactions` under the FakeClock; R14 by the owner) gives exactly §2's totals, as strings, per currency, and the request/row counts of §2 |
| A2 | Window boundaries | R01 (at `from`) is included and R04 (at `to`) is excluded. R03, 1 ms before `to`, is included |
| A3 | Timezone | The Kolkata local-date window gives the 7-row result, and the Kolkata instant window gives the two clipped buckets. `America/New_York` with `date_from=2026-11-01` returns one bucket with `day_seconds` 90,000. `Australia/Lord_Howe` and any zone outside the allow-list get 422 |
| A4 | as_of | R08 is absent at `as_of` 06:00 and present at exactly 07:00. `as_of > read_at` gets 422 |
| A5 | Replay and conflict | R09 and R10 change no count or total, and no report can count them |
| A6 | Time bases | Workload matches §2: R03 is in "open now" but not "created in window", and T4 holds with a past `as_of` |
| A7 | Change detection | Reproduce T1 and T2 with two connections. The flags and page rows match §3, and nothing claims stability |
| A8 | Scope | S2 and T2 rows never appear in any report, page or count. A foreign case ID behind a drilldown link gets 404 from the existing case route |
| A9 | Permissions | Without `read_report`, or without `read_case`, the route gets 403. A plain `sentinel create-session` (default set) lacks `read_report`. A session issued before the change never gains it |
| A10 | Missing values | R14 is `score_unknown` in daily, `null` in the drilldown and counted in `transactions_without_outcome`, never `false` or `0` |
| A11 | Label leakage | No S1 response contains `is_fraud` or any disclosure-derived count, even though R05 and R07 have disclosures. Agent tools gain no report access. The ML holdout and agent-final data are unreadable through any report |
| A12 | Limits | A range over the limit, an unknown currency, or currency or direction on `cases.workload` get 422. More than 200,000 matching rows get 413. A forced statement timeout gets 503 `report_timeout`. All are enforced on the server |
| A13 | Cursor | T5 holds. A cursor from another report gets 422 `invalid_cursor` |
| A14 | Large sums | 1,001 synthetic rows at `MAX_MINOR_UNITS` in one currency return `debit_minor` "9009000000000000" exactly, and the UI renders it with `BigInt` |
| A15 | UI states | Loading, empty, error, changed, old-as_of and denied states render the design §10 texts, and are keyboard and screen-reader accessible |

The S2 export cases (formula escaping, buffered errors, the `report_exports` audit row) are deferred with export. The escaping rule's known answers are already in `check_an01.py`.
