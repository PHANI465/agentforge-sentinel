# External fraud dataset register

November 8, 2026. Research acquisition, not training or product integration. Raw files
are excluded from Git by data/private/. Keep dataset licenses distinct from software licenses.

## Downloaded: ULB / Worldline, OpenML1597 v1

- [Original listing](https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud),
  [OpenML metadata](https://www.openml.org/api/v1/json/data/1597),
  [download](https://openml.org/data/v1/download/1673544/creditcard.arff).
- Original listing metadata reports Database: Open Database, Contents: Database Contents;
  OpenML calls its license Public. Retain [ODbL](https://opendatacommons.org/licenses/odbl/1-0/)
  and [DbCL](https://opendatacommons.org/licenses/dbcl/1-0/) references/attribution. No raw
  redistribution or claim that this is CC0. Provider citation is recorded by OpenML.
- Downloaded locally at data/private/external/ulb-creditcard-1597/creditcard.arff.
  Bytes: 150,829,308. Source MD5 verified: 178bcf9bb1f31a3dfe12d0e577884add.
  SHA-256: fdaf12730dc1fc426f318b71349f24f5c5fd00aa1152940be7e7509ae3d89d2a.
- Streaming validation: 284,807 rows, 492 fraud,
  284,315 legitimate, 30 features plus target. Relative time spans
  0–172792 seconds. No pandas/dataframe load or pickle execution was needed.
- Use: a separate real anonymized transaction-classification benchmark. It does not
  provide account identity/history, merchant identity or p1's 12 decision-time features.
  Do not feed PCA columns to p1, infer account IDs, combine its AP with p1's synthetic AP,
  or describe two observed days as realistic long-term bank behavior.

The [machine-readable acquisition manifest](ulb-1597-acquisition.json) records identity,
license observations and checksums without data rows. Download took about 46 seconds;
it is not a training or inference benchmark. No p1 bytes changed.

## Other primary sources to consider

| Source | What it provides | Verified access/terms observation | Decision |
| --- | --- | --- | --- |
| [PaySim](https://www.kaggle.com/datasets/ealaxi/paysim1), [original simulator](https://github.com/EdgarLopezPhD/PaySim) | Synthetic mobile-money entities, typed transactions, time steps and fraud labels. | Original listing API reports CC BY-SA 4.0 and 493,534,783 uncompressed bytes. | Good candidate for entity-based replay; not downloaded/trained today. Document synthetic origin, field timing and label leakage. |
| [Bank Account Fraud suite](https://github.com/feedzai/bank-account-fraud), [listing](https://www.kaggle.com/datasets/sgpjesus/bank-account-fraud-dataset-neurips-2022) | Generated account-opening fraud data, not a transaction history. | Listing API reports CC BY-NC-SA 4.0; [provider datasheet](https://raw.githubusercontent.com/feedzai/bank-account-fraud/main/documents/datasheet.pdf) says CC BY-NC-ND 4.0. About 1.36 GB listed. | No bulk download until terms/version are resolved. Code repository license does not settle data terms. |
| [Fraud Detection Handbook](https://fraud-detection-handbook.github.io/fraud-detection-handbook/Foreword.html) | Reproducible simulator and temporal fraud research methods. | Original site separates synthetic simulation and real-world benchmark discussion. | Useful independent synthetic world/method reference; do not copy simulator code without its applicable license. |
| [Federal Reserve CardSim](https://www.federalreserve.gov/econres/feds/cardsim-a-bayesian-simulator-for-payment-card-fraud-detection-research.htm) | Bayesian card-transaction simulation and research software. | Official research page links the paper and Python ZIP. | Future candidate; verify package/data terms and resource demand before downloading/running. |

Listing metadata was retrieved directly from public provider APIs. Private evidence keeps
the full metadata; the rendered Kaggle pages did not expose readable license text to the
browser reader. Do not substitute an unlicensed random mirror.

## Before a new experiment

Freeze task, source/version/checksums, label semantics, feature availability, split policy
and metrics. Inspect missingness/schema/duplicates without fitting. Use appropriate time
splits where time exists; never claim account-disjoint splits when account IDs are absent.
With only two days, drift/generalization and uncertainty estimates are limited. Preserve
p1 and fit a separate artifact/schema/manifest only under a new assignment. Counts seen
in this acquisition are not held-out performance results.
