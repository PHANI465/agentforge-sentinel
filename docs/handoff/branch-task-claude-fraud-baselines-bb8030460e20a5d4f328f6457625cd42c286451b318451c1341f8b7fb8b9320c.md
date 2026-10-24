# Handoff: task/claude-fraud-baselines

- Task and acceptance criteria: C04 (docs/TASK_QUEUE.md, docs/prompts/CLAUDE_C04.md on task/coordination):
  - a rule baseline, logistic regression and a CPU tree baseline;
  - a frozen protocol with delayed-label eligibility and chronological windows;
  - review capacity, tie and threshold policy;
  - a single test evaluation with AP vs trapezoidal PR-AUC, capacity metrics, false positives, calibration and uncertainty;
  - error slices, a trusted saved artifact with manifests, and a model card.
- Owner: Claude Code. Accepted dependency: C03 at a8e716cdec38fad1c316c6ffa2b722601b50b41d (data_pipeline unchanged).
- Tool and worktree: Claude Code, E:\PHANI\sentinel-wt\claude-fraud-baselines (branch task/claude-fraud-baselines)
- Updated: 2026-10-24
- State: ready for Codex review. C07 waits for acceptance.
- Commits: 0ecd476 froze the protocol and pipeline **before** any selection or test score. The results commit follows. Final strict checks run after the final commit; reported in chat.
- Owned/changed paths: ml/ (new package, protocol.json, runs/p1/, artifacts/p1/), tests/ml/ (new), evals/ml/p1/ (new), docs/ml/experiment-protocol.md and docs/ml/model-card.md (new), pyproject.toml and uv.lock (new optional `ml` extra; numpy/narwhals age limits), this note. No data_pipeline/, src/, contracts/, migrations or web/ changes.

## Implemented

- **Protocol p1** (sha256 bed52b8108bd855f4fa467c2e992e5e33c9a37871dec7664129d58b0dba561e9):
  - data: 600 accounts × 150 days, seed 7;
  - windows: train [10,55) with labels known by day 85; validation [56,85) with labels by day 115; test [116,150) under synthetic truth;
  - f1 features + currency; 5 fixed candidates;
  - review: daily top-15 with external_id ties, plus a frozen validation threshold;
  - account bootstrap (200, seed 11); single test access.
- **`ml` package:**
  - validated snapshot (re-derived summaries, hashes, peak working set);
  - as-of splits that never relabel unknowns and build only the requested splits;
  - rule (production-parity) / logistic / HGB pipelines fitted on train only;
  - metric and policy definitions; trusted artifact with fail-closed loading;
  - `select` / `test` / `test --reproduce` with protocol, provenance and selection guards;
  - CSV, SVG and markdown reports generated from the stored JSON.

## Results (actual, synthetic)

| Candidate | Validation AP | Test AP | Test top-15 recall / FP |
| --- | --- | --- | --- |
| rule_r1 | 0.488 | 0.455 | 0.771 / 426 |
| logreg_balanced | 0.532 | 0.400 | 0.826 / 420 |
| logreg_unweighted | 0.636 | 0.622 | 0.798 / 423 |
| hgb_unweighted | 0.273 | 0.208 | 0.477 / 458 |
| **hgb_balanced** (selected on validation AP) | **0.830** | **0.817** | 0.927 / 409 |

- Selected, daily top-15 on test: precision 0.198, false-positive rate 2.21%.
- Selected, frozen threshold 4.0295e-06: precision 0.231, recall 0.936, 340 false positives.
- Bootstrap: AP [0.697, 0.914], recall at capacity [0.870, 0.986].
- Artifact `ml/artifacts/p1/model.joblib`, sha256 6c2982d1df12184f704bc45dbc5882d8f85dba16c50bd9829dda9e674602575b; round trip verified against a deterministic refit.
- Slices: lookalikes (micro-payments 47/76 flagged) and INR (181 of 201 flagged are false positives) drive the false positives.

## Verified (Windows 11, `uv sync --locked --extra dev --extra ml`, `SENTINEL_LIVE_CLAUDE=0`)

- `tests/ml`: 28 passed. They cover:
  - hand-computed AP vs trapezoid; ties and per-day reset; the frozen threshold;
  - as-of eligibility with unknowns excluded; single-class refusal;
  - feature/label separation; preprocessing fit isolation; rule parity with `sentinel.scoring.rule_score`;
  - snapshot summary tampering detected (where `verify` alone misses it);
  - artifact round trip and refusal for tampered bytes, schema/version/code/library mismatch and an untrusted root;
  - tiny end-to-end: select without test labels, a single test, `--reproduce`, and refusal after a protocol change.
- **Real bug found and fixed test-first:** `select` originally built all splits, computing test labels before discarding them. The spy test failed on that version (it saw the train/validation/test set) and passes now.
- **Injected leak:** relabeling unknown labels as legitimate failed the eligibility test (reverted).
- **Real run:**
  - `python -m ml select`: 32.6 s, peak working set 483 MiB;
  - `python -m ml test`: 40.0 s, 481 MiB;
  - `python -m ml test --reproduce`: `{"reproduced": true}`;
  - a plain rerun of `test` is refused.
- An apparent coincidence (identical top-k counts for rule_r1 and logreg_balanced on validation) was checked: the flagged sets overlap on only 243 of 435 rows, so it is not a bug.
- Protocol-validation disclosure: before freezing, I inspected class counts (only) of every split, including test, as the prompt requires. No model scores existed then.

## Not verified / gaps

- One seed, one synthetic world; no fairness, drift or adversarial analysis.
- Scores are uncalibrated. Currency-normalized amounts are a clear next feature (new feature version and protocol).
- Linux/macOS/CI not run. C06 CI must install `--extra ml`, or tests/ml fails at import; that is intentional, not a green skip.
- The run happened under heavy machine memory pressure from other processes (about 0.3 GiB free), so runtimes are indicative.
- The tracked `*_stats.json` files are non-deterministic measurements.

## Next action

Codex: review C04 (protocol chronology and label views, the select/test separation, metrics/policy definitions, artifact trust boundary). On acceptance, C07 integrates the trusted artifact behind an explicit rule/model configuration.

## Coordination and provenance

- Python dependency change: optional `ml` extra (scikit-learn 1.9.1, numpy 2.4.6, scipy 1.17.1, joblib 1.6.0, narwhals 2.26.0, threadpoolctl, cloudpickle), with numpy/narwhals held to releases at least two weeks old. Coordinate with C06 (CI extras) and C07 (serving import of ml/models.py; data_pipeline/ml are source packages, not in the src-only wheel).
- The C02 900 s checker timeout lives on another branch; this branch's full suite fits the existing timeout locally.
- No third-party data or model code; no GPU, cloud, API key or live model call.
