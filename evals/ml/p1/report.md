# C04 frozen test report (p1)

Generated from test_report.json. Synthetic data; offline benchmark only.

- Protocol sha256: `bed52b8108bd855f4fa467c2e992e5e33c9a37871dec7664129d58b0dba561e9`
- Selected on validation AP: **hgb_balanced**; artifact sha256 `6c2982d1df12184f704bc45dbc5882d8f85dba16c50bd9829dda9e674602575b`
- Test rows 18597, fraud 109 (synthetic truth; 2219 labels observable by the horizon end)

| Candidate | Val AP | Test AP | Test PR-AUC (trapezoid) | Top-k precision | Top-k recall | Top-k FP |
| --- | --- | --- | --- | --- | --- | --- |
| rule_r1 | 0.487795 | 0.455044 | 0.578945 | 0.164706 | 0.770642 | 426 |
| logreg_balanced | 0.532282 | 0.399565 | 0.395465 | 0.176471 | 0.825688 | 420 |
| logreg_unweighted | 0.63633 | 0.621507 | 0.620437 | 0.170588 | 0.798165 | 423 |
| hgb_unweighted | 0.272991 | 0.208093 | 0.329024 | 0.101961 | 0.477064 | 458 |
| hgb_balanced | 0.829965 | 0.81738 | 0.816827 | 0.198039 | 0.926606 | 409 |

Daily top-15 (selected): {'flagged': 510, 'tp': 101, 'fp': 409, 'fn': 8, 'tn': 18079, 'precision': 0.198039, 'recall': 0.926606, 'false_positive_rate': 0.022122}

Frozen threshold 4.0295386895426815e-06 (from validation): {'flagged': 442, 'tp': 102, 'fp': 340, 'fn': 7, 'tn': 18148, 'precision': 0.230769, 'recall': 0.93578, 'false_positive_rate': 0.01839}

Account bootstrap (200 reps, 600 accounts, 0 skipped): AP [0.696785, 0.913767], recall@capacity [0.870098, 0.985942], precision@capacity [0.128279, 0.286932]

Brier 0.002558 (scores are not calibrated probabilities).
