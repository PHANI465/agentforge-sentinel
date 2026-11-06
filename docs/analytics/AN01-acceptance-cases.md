# AN01 acceptance cases and known-answer example

Audience: the implementers and reviewers of AN01-S1. These are **proposed** checks for a future implementation. Only the arithmetic in §2 was actually checked: by hand, and by a tiny no-I/O Python calculation that was run once and not committed (results in §2). No database, API or UI test was run for AN01. All data is synthetic.

## 1. Known-answer example (15 requests)

**Scopes:**
- **S1** is the analyst's session (tenant T1).
- **S2** is another session of T1.
- **T2** is another tenant.

**Report parameters:** window `[2026-10-01T00:00:00Z, 2026-10-02T00:00:00Z)`, `tz=UTC`, `as_of=2026-10-02T06:00:00Z`.

The **alerted** values are stated stored outcomes for this example. They are not derived from the rule's thresholds.

| Row | Scope | external_id | Currency (exp) | Direction | minor_units | occurred_at (UTC) | ingested_at (UTC) | Stored? | Outcome | Alerted | Case |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R01 | S1 | an-01 | USD (2) | debit | 12500 | 10-01 00:00:00 | 10-01 00:00:05 | yes | yes | no | — |
| R02 | S1 | an-02 | USD (2) | credit | 5000 | 10-01 08:15:00 | 10-01 08:15:01 | yes | yes | no | — |
| R03 | S1 | an-03 | USD (2) | debit | 250000 | 10-01 23:59:59.999 | 10-02 00:00:01 | yes | yes | yes | awaiting_approval |
| R04 | S1 | an-04 | USD (2) | debit | 999 | 10-02 00:00:00 | 10-02 00:00:02 | yes | yes | no | — |
| R05 | S1 | an-05 | INR (2) | debit | 1000000 | 10-01 05:30:00 | 10-01 05:30:02 | yes | yes | yes | closed (one simulated hold) |
| R06 | S1 | an-06 | INR (2) | credit | 250050 | 10-01 18:31:00 | 10-01 18:31:01 | yes | yes | no | — |
| R07 | S1 | an-07 | JPY (0) | debit | 15000 | 10-01 12:00:00 | 10-01 12:00:01 | yes | yes | yes | open |
| R08 | S1 | an-08 | GBP (2) | debit | 7525 | 10-01 09:00:00 | **10-02 07:00:00** | yes | yes | no | — |
| R09 | S1 | an-01 | USD (2) | debit | 12500 | 10-01 00:00:00 | — | **no** (replay of R01 → 201 `replayed: true`) | — | — | — |
| R10 | S1 | an-01 | USD (2) | debit | 13000 | 10-01 00:00:00 | — | **no** (409 `idempotency_conflict`) | — | — | — |
| R11 | **S2** | an-11 | USD (2) | debit | 777777 | 10-01 10:00:00 | 10-01 10:00:01 | yes | yes | yes | open |
| R12 | **T2** | an-12 | USD (2) | debit | 500000 | 10-01 11:00:00 | 10-01 11:00:01 | yes | yes | yes | open |
| R13 | S1 | an-13 | USD (2) | debit | 0 | 10-01 13:00:00 | — | **no** (422: `minor_units` must be > 0) | — | — | — |
| R14 | S1 | an-14 | USD (2) | debit | 3000 | 10-01 10:00:00 | 10-01 10:00:03 | yes | **missing** (pre-0002 style) | unknown | — |
| R15 | S1 | an-15 | GBP (2) | credit | 10000 | 10-01 14:00:00 | 10-01 14:00:02 | yes | yes | no | — |

**Labels** (`fraud_disclosures` in S1):
- R05 has `is_fraud=true`, with `disclosed_at` and `recorded_at` both 10-03 (after `as_of`).
- R07 has `is_fraud=false`, `disclosed_at` 10-01 20:00 and `recorded_at` 10-01 20:05.

## 2. Expected answers

**Rows in the window, as of `as_of`, in S1:** R01, R02, R03, R05, R06, R07, R14 and R15, which is **8**.
- R04 is at the exclusive end of the window.
- R08 was ingested after `as_of`.
- R09, R10 and R13 were never stored.
- R11 and R12 are in foreign scopes.

**`transactions.currency_totals` (UTC):**

| Currency | debit n | debit_minor | credit n | credit_minor | gross_minor | net_outflow_minor | Display |
| --- | --- | --- | --- | --- | --- | --- | --- |
| GBP | 0 | "0" | 1 | "10000" | "10000" | "-10000" | net −100.00 GBP |
| INR | 1 | "1000000" | 1 | "250050" | "1250050" | "749950" | net 7,499.50 INR |
| JPY | 1 | "15000" | 0 | "0" | "15000" | "15000" | net ¥15,000 (exponent 0) |
| USD | 3 | "265500" | 1 | "5000" | "270500" | "260500" | net 2,605.00 USD |

There is no total across currencies. The transaction count across currencies is 8 (USD 4, INR 2, JPY 1, GBP 1).

**Same window as local dates in `tz=Asia/Kolkata`** (`date_from=2026-10-01`, `date_to=2026-10-02`, which is `[09-30T18:30Z, 10-01T18:30Z)`):
- Rows: R01, R02, R05, R07, R14 and R15, which is **6**.
- R03 falls outside: 23:59:59.999Z is after 18:30Z.
- R06 falls outside: 18:31Z is just after 18:30Z.
- Totals: USD debit 2 / "15500", credit 1 / "5000", net "10500"; INR debit 1 / "1000000", net "1000000"; JPY "15000"; GBP credit "10000", net "-10000".

**Alerts (UTC window):** R03, R05 and R07 alerted, so 3 of 8. R14's score is unknown: 1 of 8 is reported as `score_unknown`, not as "not alerted".
- Per currency: USD 1 alerted of 4 (one unknown); INR 1/2; JPY 1/1; GBP 0/1.

**`cases.workload`** (current state, cases created in the window, S1):
- awaiting_approval 1 (R03), closed 1 (R05), open 1 (R07), investigating 0, inconclusive 0.
- Simulated actions: 1.
- R11 and R12 are never counted.

**`data_quality.checks`:**
- Transactions without a scoring outcome: 1 of 8 (R14).
- Alerts without a case: 0. Cases without an alert: 0.
- Events ingested after the window end: 1 (R03).
- Ingestion lag in seconds, sorted: [1.0, 1.0, 1.0, 1.001, 2.0, 2.0, 3.0, 5.0]. By nearest rank: p50 is the 4th value = **1.001**, p95 is the 8th = **5.0**, max **5.0**, n = 8.

**`labels.availability` (as of 10-02T06:00Z):**
- Labelled not-fraud: 1 (R07). Labelled fraud: 0, because R05's label is not yet recorded at `as_of`. Unlabelled: 7.
- No rates. R07 being alerted and labelled not-fraud is one observation, not a false-positive rate.

**`rows.transactions` drilldown,** ordered by `(occurred_at, id)` with `limit=3`:

| Page | Rows |
| --- | --- |
| 1 | R01 (00:00), R05 (05:30), R02 (08:15) |
| 2 | R14 (10:00), R07 (12:00), R15 (14:00) |
| 3 | R06 (18:31), R03 (23:59:59.999), then `next_cursor: null` |

**No-I/O calculation, run once and not committed.** It reproduced every UTC and Kolkata total, the row sets, the page split and the lag quantiles above. It also showed that 1,001 rows at the maximum `minor_units` sum to 9,009,000,000,000,000, which is above JavaScript's safe-integer limit (9,007,199,254,740,991). That is why sums are strings.

## 3. Proposed acceptance cases for the implementation (not run)

| ID | Case | Expected |
| --- | --- | --- |
| A1 | Reconciliation | Loading §1's rows through the real `POST /v1/transactions` as the runtime role gives exactly §2's totals, as strings, per currency. Summing across currencies is impossible in the DTO |
| A2 | Window boundaries | R01 (at `from`) is included and R04 (at `to`) excluded. A row 1 ms before `to` (R03) is included |
| A3 | Timezone | The Kolkata local-date window gives the 6-row result. A DST zone (for example `America/New_York` around the November change) gives `day_hours` 25 on that day |
| A4 | as_of | R08 is absent at `as_of = 10-02T06:00Z` and present at `as_of ≥ 10-02T07:00Z`. A future `as_of` gets 422 |
| A5 | Replay and conflict | Replaying R01 and sending the conflicting R10 change no count or total |
| A6 | Pagination stability | While page 1 → 2 → 3 is being read, a new transaction ingested in the window (with `ingested_at > as_of`) does not appear, shift or duplicate rows. A cursor reused with changed filters gets 422 |
| A7 | Scope | S2 and T2 rows never appear, in any report, drilldown, export or count. A foreign case ID behind a drilldown link gets 404 from the existing case route |
| A8 | Denied export | A session without `export_report` gets 403 on `export.csv`. Without `read_case`, 403 on reports |
| A9 | Malicious text | An `external_id` like `=HYPERLINK(...)` (if the Name pattern admits it) or role-like text appears inert in JSON and is `'`-prefixed in CSV. Typed integer strings such as `-10000` are not prefixed |
| A10 | Snapshot consistency | Totals and the drilldown's row count agree for the same filters and `as_of`, even with concurrent ingestion (each report is one read-only transaction) |
| A11 | Label leakage | No report exposes `is_fraud` for an unavailable label (R05 before `recorded_at`). Alerts and approvals are never labelled "fraud". Agent-evaluation packets and the ML holdout are not readable through any report |
| A12 | Limits | A range over 92 days, an unknown tz or an unknown currency gets 422. An export over the row cap gets 413. Limits are enforced on the server, not only in the UI |
| A13 | Missing values | R14's null score is reported as `score_unknown` and `null` in the drilldown, never as `false` or `0` |
| A14 | UI states | Loading, empty, error, stale and denied states render the texts in the design doc §7, and are keyboard and screen-reader accessible |

**Note on A9:** the current `Name` pattern for `external_id` (`^[A-Za-z0-9][A-Za-z0-9._:-]*$`) does not admit a leading `=`. Formula escaping therefore mainly protects any later free-text fields and the provenance block. It must still be tested on the escaping function directly.
