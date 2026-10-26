# Model card: hgb_balanced (C04, protocol p1)

Audience: reviewers, the C07 serving task and analysts reading model output. **Synthetic data only.** Nothing here measures effectiveness on real transactions, real fraud rates or savings.

## Identity

| Field | Value |
| --- | --- |
| Model | scikit-learn 1.9.1 `HistGradientBoostingClassifier` (lr 0.1, 200 iterations, 31 leaves, `class_weight=balanced`, no early stopping, seed 7) behind a fixed preprocessing pipeline: signed log1p on numeric features plus one-hot currency |
| Artifact | `ml/artifacts/p1/model.joblib`, sha256 `6c2982d1df12184f704bc45dbc5882d8f85dba16c50bd9829dda9e674602575b` (284 KB); manifest `ml/artifacts/p1/manifest.json` |
| Protocol | `ml/protocol.json` p1, sha256 `bed52b81…a561e9` (full value in the experiment protocol doc) |
| Data | C03 g1 seed 7, 600 accounts × 150 days. The dataset, manifest and feature-file hashes are in `selection.json` under `data` |
| Inputs | f1 features (12) + currency. No identifiers, timestamps, scenario or labels |
| Output | an **uncalibrated** class-weighted score in [0, 1], used for ranking. Not a fraud probability |
| Environment | Python 3.11.3, numpy 2.4.6, joblib 1.6.0, Windows 11 laptop (i5-1240P), CPU only |

**Loading.** Use only `ml.artifact.load_trusted(manifest, trusted_root, protocol)`. It refuses, before deserializing, any of:
- a path outside the trusted root, or a link;
- a hash mismatch;
- a different format, feature schema or feature version;
- a different scikit-learn version;
- different `ml/models.py` code.

Never load a visitor-supplied or remote model.

## Results (frozen test, days 116–150: 18,597 rows, 109 fraud, synthetic truth)

| Candidate | Validation AP | Test AP | Test PR-AUC (trapezoid) | Daily top-15 precision / recall / FP |
| --- | --- | --- | --- | --- |
| rule_r1 (production rule) | 0.488 | 0.455 | 0.579 | 0.165 / 0.771 / 426 |
| logreg_balanced | 0.532 | 0.400 | 0.395 | 0.176 / 0.826 / 420 |
| logreg_unweighted | 0.636 | 0.622 | 0.620 | 0.171 / 0.798 / 423 |
| hgb_unweighted | 0.273 | 0.208 | 0.329 | 0.102 / 0.477 / 458 |
| **hgb_balanced (selected)** | **0.830** | **0.817** | 0.817 | 0.198 / 0.927 / 409 |

**Selected model, in detail:**
- **Daily top-15:** 510 flagged; TP 101, FP 409, FN 8, TN 18,079; false-positive rate 2.21%.
- **Frozen threshold (4.0295e-06, from validation):** 442 flagged; TP 102, FP 340, FN 7; precision 0.231, recall 0.936, false-positive rate 1.84%.
- **Uncertainty** (account bootstrap, 600 accounts, 200 replicates, 0 skipped):
  - AP 0.697–0.914;
  - recall at capacity 0.870–0.986;
  - precision at capacity 0.128–0.287.
- **Calibration:** Brier 0.0026, but 18,496 of 18,597 rows fall in the 0–0.1 score bin, and higher bins hold few rows with uneven fraud rates. Treat scores as ranking signals only.
- **Why both metrics:** the rule's discrete scores show why AP and trapezoidal PR-AUC are reported separately (0.455 vs 0.579). Linear interpolation over tied score levels inflates the trapezoid.

## Error slices (daily top-15, test)

- **Fraud scenarios:** account takeover 31/33, card testing 37/42 and mule cash-out 33/34 caught, with 0 false positives within those scenario rows.
- **Lookalikes cause false positives:** 47 of 76 micro-payment rows and 14 of 21 payday-burst rows are flagged; 344 of the 409 false positives are ordinary rows.
- **Currency:** INR has 181 false positives out of 201 flagged (precision 0.10, versus 0.25–0.30 elsewhere). The `amount_minor` input is not comparable across currencies; INR minor-unit amounts are about 83× USD. A currency-normalized amount feature is the obvious next experiment, and it would need a new feature version and protocol.
- **Cold-start accounts:** recall is lowest with no activity in the last 24 h (5/7) and highest at 3+ prior transactions (68/72).
- **Over time:** recall is 0.81–1.0 by test week; precision varies with how much fraud each week contains.

## Intended use and limits

- **Intended:** a reproducible baseline and fixture for C07 (serving integration) and U03 (results views) on synthetic data, compared explicitly with the production rule.
- **Not intended:** any real-money decision, any claim about real-bank performance, or use as a probability.
- **Synthetic signals are deliberately learnable.** Near-perfect recall on the three fraud scenarios reflects the generator, not real-world difficulty. Lookalikes are the meaningful stress test here.
- **The test view is synthetic truth.** It includes 10% never-disclosed fraud that a real institution would never observe; validation used only labels known by day 115.
- **Small positive counts:** 109 test fraud rows, all from a handful of accounts and episodes; see the bootstrap intervals. Results are one seed on one synthetic world. No seed or window search was done, so they are not tuned.
- **Not covered:** fairness or protected-attribute analysis (the data has no such attributes), drift, adversarial adaptation, and serving latency under load.
