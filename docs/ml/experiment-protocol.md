# C04 experiment protocol p1

Audience: reviewers and the later serving task (C07). The protocol of record is `ml/protocol.json`, sha256 `bed52b8108bd855f4fa467c2e992e5e33c9a37871dec7664129d58b0dba561e9`. It was committed in `0ecd476` **before** any model was selected or any test score existed; `python -m ml test` refuses to run if the protocol changes after selection.

## Why not the C03 defaults

With the C03 default dataset (30 days), the default split gives 20 eligible training rows, all fraud, because legitimate labels mature only 30 days after the event (C03 review). No binary classifier can be trained on that. Unknown labels are never relabeled legitimate. The fix was a longer horizon with label-mature windows, not relabeling.

## Data (bounded up front)

- **Generation.** Accepted C03 generator g1, seed 7: 600 accounts, 150 days, daily rate 0.3–1.5, fraud-account rate 0.15, lookalike rate 0.2, 1% late ingestion, 10% undisclosed fraud. The size was fixed by accounts/days, not by `max_rows`; truncation is rejected.
- **Result.** 82,819 transactions and 581 fraud rows (62 never disclosed). Scenarios: account takeover 156, card testing 263, mule cash-out 162; lookalikes: micro-payments 387, payday burst 270, large legitimate purchase 31. Peak working set was about 483 MiB; generation took 3.6–5.6 s and features 17.7–23.6 s (two runs on the reference laptop, which was under memory pressure from other processes).
- **Validation.** The snapshot recomputes every count and summary it uses (accounts, transactions, labels, fraud and never-disclosed counts, scenarios, per-currency totals) from the rows, and rejects any disagreement with the manifest. `manifest.verify` alone does not cover these (C03 review). It also records dataset, manifest and feature-file hashes.

## Inputs

The accepted f1 historical features (12) plus **currency** (one-hot over the protocol's fixed list; a decision-time projection field).

Excluded from inputs: `external_id`, `account_id`, timestamps, `is_fraud`, `scenario`, `label_available_at`. Scenario is used only for offline error slices.

## Chronology and label views (days from 2026-09-01Z, by decision time)

| Window | Decisions | Labels used | Rows (fraud / legitimate / unknown excluded) |
| --- | --- | --- | --- |
| burn-in | [0, 10) | none | not used (thin history) |
| train | [10, 55) | known by day 85 | 141 / 24,631 / 34 |
| validation | [56, 85) | known by day 115 | 123 / 15,829 / 30 |
| test | [116, 150) | synthetic truth (`is_fraud`), offline benchmark | 109 / 18,488; 2,219 labels observable by the day-150 horizon |

**Timeline:**
- The model is fitted at day 85 (train labels mature 30 days after the window).
- Validation rows are scored retrospectively with their decision-time features.
- Selection happens at day 115 with validation labels known by then.
- Test decisions start at day 116, after selection, so the deployment timeline is possible.

**Test labels.** The test view is synthetic truth. It includes never-disclosed fraud, labels that would not all be observable in practice; it is labeled as an offline benchmark, not as labels available for any historical decision.

**Gaps.** The day 55–56 and 85–116 gaps are chronological only. Feature windows of up to 30 days still share earlier history across splits (declared stream context, not independence).

**Prevalence.** Natural (about 0.57–0.77%); no resampling.

## Candidates, selection and policies

- **Fixed budget of 5 candidates:**
  - `rule_r1`, the production `velocity-amount-rules r1`, recomputed from features, with parity tested against `sentinel.scoring.rule_score`;
  - logistic regression, C=1, balanced and unweighted;
  - `HistGradientBoostingClassifier` (lr 0.1, 200 iterations, 31 leaves, no early stopping, seed 7), balanced and unweighted.

  All fitted steps (scaler, encoder, model) see training rows only.
- **Selection:** the highest validation average precision; ties go to the earlier candidate.
- **Primary review policy, daily top-15:** per UTC decision day, rank by score descending with ties by `external_id` ascending, and flag the first 15 (about 2.7% of rows).
- **Frozen streaming threshold:** the validation score at rank 15 × 29 validation days = 435, i.e. 4.0295e-06 for the selected model. It is applied unchanged to test, and every row with score ≥ threshold is flagged.
- **Metrics:**
  - average precision (sklearn's step-wise sum) and trapezoidal PR-AUC, reported separately;
  - precision, recall, false positives and false-positive rate at both policies, plus the confusion matrix;
  - Brier score and 10-bin reliability, for information only (scores are uncalibrated);
  - account-level bootstrap, 200 replicates, seed 11, 2.5–97.5% interval;
  - slices by currency, scenario (offline), 24-hour activity and test week.
- **Test access:** exactly once (`python -m ml test`). A rerun requires `--reproduce`, which recomputes, compares and writes nothing.

## Commands

```powershell
uv sync --locked --extra dev --extra ml
uv run --locked python -m ml select             # train + validation only (test labels never computed)
uv run --locked python -m ml test               # the single frozen test evaluation
uv run --locked python -m ml test --reproduce   # recompute and compare: {"reproduced": true}
```

Generated data goes to the git-ignored `data/generated/c04-p1/`. Tracked outputs: `ml/runs/p1/selection.json`, `ml/artifacts/p1/{model.joblib, manifest.json}`, `evals/ml/p1/` (report, CSVs, SVG). `*_stats.json` files hold timing/memory measurements and are not deterministic.
