# Data card: Sentinel synthetic transactions (generator g1, features f1, split s1)

Audience: whoever trains or evaluates models on this data (C04), and reviewers.

## What it is

Fully synthetic card/account transactions for developing and testing the Sentinel workbench. It contains no real customer, bank or merchant data. It is independently implemented in `data_pipeline/` (standard-library Python, no third-party simulator code or data, so no dataset or GPL licence obligations). Results on it say nothing about real-bank fraud rates or model effectiveness.

## How to produce it

```powershell
uv run --locked python -m data_pipeline generate --out data/generated/ref   # defaults below
uv run --locked python -m data_pipeline verify data/generated/ref
uv run --locked python -m data_pipeline features data/generated/ref         # features.f1.jsonl
uv run --locked python -m data_pipeline refresh-fixtures                    # tracked fixtures
```

Options: `--seed`, `--accounts`, `--days`, `--max-rows`. Generated data goes under `data/generated/`, which is git-ignored.

Tracked:
- `data_pipeline/manifests/reference-g1-seed7.json`: the reference dataset's manifest, with hashes, counts and totals.
- `tests/data/fixtures/tiny/`: 24 accounts, 6 days, 315 rows, every scenario present.

Tests regenerate both and require byte equality.

**Determinism.** The same config gives identical bytes. This relies on `random.Random` and IEEE arithmetic and was verified on CPython 3.11 / Windows. Another Python version or platform should reproduce the same output, but that has not been run. The manifest hashes would expose any drift.

## Reference dataset (default config: seed 7, 1,000 accounts, 30 days from 2026-09-01Z)

| Measure | Value |
| --- | --- |
| Transactions | 50,768 (not truncated; `max_rows` 100,000) |
| Fraud rows | 335 (0.66%); 38 never disclosed |
| Scenario rows | normal 49,931; account_takeover 48; card_testing 179; mule_cashout 108; lookalikes: payday_burst 225, micro_payments 239, large_legit_purchase 38 |
| Currencies (rows) | GBP 7,847, INR 10,945, JPY 3,175, USD 28,801; debit/credit minor-unit totals per currency are in the manifest |
| Generate | 9.2 s, Python peak 79.2 MiB (tracemalloc, which also slows the run; not process RSS), Windows laptop, CPython 3.11.3 |
| Features (batch) | 6.5 s for 50,768 rows |

The per-currency totals in the manifest are recomputed by `verify`, and must match exactly. Currencies are never summed together.

## Files and fields

- `accounts.jsonl`: `account_id`, `home_currency`, `opened_at`, `segment`. Generation-only parameters (daily rate, typical spend) are not exported.
- `transactions.jsonl`: the **decision-time projection**: `external_id`, `account_id`, `amount {currency, minor_units, currency_exponent}`, `direction`, `occurred_at`, `ingested_at`. Every row validates against the API's `TransactionInput` contract (with `ingested_at` removed). Timestamps are fixed-width RFC 3339 with microseconds, UTC.
- `labels.jsonl`: **hidden truth**: `is_fraud`, `scenario`, `label_available_at`. Joined only by `external_id`, and never present in a transaction row (checked).

## Generative assumptions (simplifications, stated plainly)

- **Accounts.** Home currency USD 60% / INR 20% / GBP 15% / JPY 5%. Account age is up to 3 years. Each account has a Poisson daily rate between 0.3 and 3 and a log-normal typical spend around 35 USD-equivalent.
- **Baseline activity.** About 8% credits (8× typical size) and 2% foreign-currency rows. Amounts are converted with fixed rates (1 USD = 0.8 GBP = 83 INR = 150 JPY) and rounded to the currency's minor unit.
- **Fraud.** One episode per fraud account (5% of accounts):
  - account takeover: a burst of 3–8 large debits within 90 minutes, about half in a foreign currency;
  - card testing: 4–10 tiny probes, then one large debit;
  - mule cash-out: 2–4 large inbound credits, then 2–5 outbound debits about 2 hours later.
- **Legitimate lookalikes.** One episode per lookalike account (10% of accounts), so velocity or amount alone is not a fraud signal:
  - payday burst: salary credit, then several purchases;
  - large legitimate purchase;
  - micro-payments: many tiny taps.
- **Ingestion delay.** 0–120 s normally. 1% of rows arrive 1–12 h late, which exercises availability cutoffs.
- **Delayed labels.**
  - Fraud is disclosed 1–45 days after the event.
  - 10% of fraud is never disclosed within the horizon (`label_available_at: null`).
  - A legitimate label is known only after a 30-day maturity window with no dispute.

Not modelled: merchants/categories, devices/IPs/geography, seasonality, coordinated rings across accounts, adversarial adaptation, chargeback reversals and label noise beyond non-disclosure. Rates and shapes are illustrative, not calibrated to any real portfolio.

## Historical features (f1, `data_pipeline/features.py`)

**Decision time** is the row's arrival, ordered by the key `(ingested_at, external_id)`. A prior row is usable only if it is from the same account, arrived strictly before (by that key), and occurred in `[t − 30 d, t)`. Events at exactly `t` are excluded regardless of arrival order, matching the API's velocity rule. A label is usable only if `label_available_at ≤ ingested_at` of the row being decided.

Features:
- `amount_minor`, `is_credit`, `is_foreign_currency`, `account_age_days`;
- `count_1h`, `count_24h`, `small_count_1h` (below 5 USD-equivalent);
- `same_currency_sum_24h`, `credit_sum_24h` (same currency only);
- `seconds_since_prev` (−1 if none);
- `amount_to_median_bps` (integer basis points versus the 30-day same-currency median; −1 if no history);
- `prior_known_fraud` (disclosed fraud labels on the account).

Guarantees tested in `tests/data/`:
- batch computation equals an online replay that only ever sees the past;
- dropping all rows that arrive after a decision never changes it (future-row invariance);
- rewriting any label not yet disclosed at a decision never changes it (future-label invariance);
- a late-arriving older event is excluded until it arrives;
- same-timestamp exclusion.

Injected leaks (removing the availability filter, or the label cutoff) make these tests fail; this was checked by mutation, and the code was reverted.

## Split policy (s1, `data_pipeline/splits.py`)

The split is chronological by decision time and never shuffled. The default is 60/20/20 of the time span, with a 1-day embargo after each cutoff; rows in the gap are dropped.

A model trained at `train_end` may use only labels disclosed by then. Training rows with undisclosed labels are reported as `train_ineligible`, not assumed legitimate. With a 30-day legitimate maturity and an 18-day training window, most training rows are ineligible. That is a real property of delayed labels: C04 must pick a longer horizon or a label-maturity strategy, and state the choice.

Validation and test keep natural prevalence. Evaluating on synthetic truth (`is_fraud`) includes never-disclosed fraud; report which label view is used.

Fitted preprocessing (scaling, encoders, thresholds) does not exist in C03. C04 must fit it on training rows only.

## Known limits

- **Small positive class.** 335 fraud rows (fewer in each split) gives wide uncertainty; report intervals.
- Scenario signals are deliberately learnable; lookalikes limit trivial rules but do not make the task realistic.
- Fixed FX rates; no cross-currency aggregation by design.
- Pure-Python feature computation is O(rows × 30-day account history). That is fine at laptop scale but not optimized beyond about 10⁶ rows.
