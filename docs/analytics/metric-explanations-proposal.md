# Interpretable measures for reports and document feedback

November 8, 2026. Proposed metric vocabulary/UI explanations, not new measured results.
Keep datasets, units, time windows, labels, source/version and sample sizes next to values.

| Measure | Plain-language question | Definition / presentation rule |
| --- | --- | --- |
| Precision | Of the flagged labelled transactions, how many were fraud? | TP/(TP+FP); show counts and threshold/policy. |
| Recall | Of the known frauds, how many were flagged? | TP/(TP+FN); distinguish fully known benchmark truth from matured labels. |
| False-positive burden | How much legitimate review work was created? | FP count and FP/(FP+TN), preferably per 1000 legitimate transactions. |
| Alert rate | How much of the stream reaches an analyst? | Flagged/all scored; do not confuse it with precision. |
| Average precision | How useful is the score ranking across thresholds? | AP with defined positive class/split; not identical to trapezoidal PR-AUC. |
| Label coverage | How much data can support a quality claim yet? | Eligible known labels/all relevant rows; unknown is never silently legitimate. |
| Report consistency | Do the displayed measures match their source set? | Matching rows, rows with outcomes, discrepancies and per-request snapshot/cutoff. |
| Extraction coverage | What part of the file was parsed? | Pages/sheets/rows attempted/read/failed; never invent a calibrated confidence percentage. |
| Reconciliation difference | Do signed amounts explain the balances? | Opening + credits − debits − closing, per currency and stated sign convention. |
| Claim support | Which statements are supported by the evidence? | Atomic supported/contradicted/not-checkable counts; machine and judge/human results separate. |
| Investigation completion | How much attempted work reached a disposition? | Dispositions/attempts, next to refused/inconclusive/pending/error counts. |
| Safety | Did anything violate the action/scope boundary? | Actual violations/opportunities; one violation cannot be averaged away by high usefulness. |
| Latency | How long did the user wait? | Request p50/p95/max with n; database/workflow budgets are different measures. |
| Usage | What did the adapter actually report? | Input/output/cached tokens with provenance, missing attempts and unknowns; never billing inferred from tokens. |

Illustration only: 1000 transactions contain 25 labelled frauds. Flag 100, of which 20 are
fraud. Then TP 20, FP 80, FN 5, TN 895: precision 20%, recall 80%, false-positive rate 80/975
≈8.21%, alert rate 10%. Accuracy 91.5% looks high, while flagging nothing gives 97.5%
accuracy and zero recall. These are invented arithmetic examples, not Sentinel results.

The frozen p1 scores are uncalibrated rankings. Its existing reported test policy yields
102 true positives and 340 false positives at the frozen threshold; daily top 15 is a
different policy with 101 and 409. Do not mix those policies, turn scores into fraud
probabilities, or compare p1's synthetic AP directly with an untrained ULB benchmark.

Every zero denominator displays n/a (0/0). Every count keeps its population/scope. Display
null as unknown and zero as zero. Currency totals use integer strings/minor units with
an exponent. An extraction warning and a suspicious-activity indicator are not verdicts.

Use a small known-answer fixture for each explanation. Initially display separate
data-quality, ML, workflow and runtime groups; do not invent a weighted master confidence
score. Probability calibration or expected financial-loss savings needs a separate
validated model/cost policy, not better copywriting.

Reference: [scikit-learn AP definition](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.average_precision_score.html),
the existing [ML protocol](../../ml/protocol.json) and [agent protocol](../evals/agents/protocol-v1.md).
