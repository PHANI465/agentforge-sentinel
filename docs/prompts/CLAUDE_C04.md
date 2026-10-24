Completed: C04 is accepted at 09b5378150faed06caa73b0384b9ff095c095eb8 for offline synthetic training/evaluation. Preserve its frozen p1 artifacts/results. See docs/reviews/09b5378.md; the next task is docs/prompts/CLAUDE_C07.md from latest coordination. Do not repeat the historical C04 assignment below.

# Claude C04: trained fraud baselines and reproducible evaluation

C03 is ACCEPTED at a8e716cdec38fad1c316c6ffa2b722601b50b41d. C05 a8294f6 is separately accepted and stays intact. Cursor corrects U02 R21/R22 in its own worktree. Your next substantive task is C04; implement models, artifacts and evidence, not only a plan.

Read current instructions without merging task/coordination:
    git show task/coordination:AGENTS.md
    git show task/coordination:docs/TASK_QUEUE.md
    git show task/coordination:docs/reviews/a8e716c.md
    git show task/coordination:docs/prompts/CLAUDE_C04.md

Use branch task/claude-fraud-baselines and worktree E:/PHANI/sentinel-wt/claude-fraud-baselines starting from exact accepted C03 a8e716c. If either exists, inspect ownership/HEAD/changes and preserve/reuse safely; never reset unfamiliar work. Record the dependency/base. Do not use old main or task/coordination as application code, combine unreviewed packages, edit Cursor's checkout or merge main.

Own ml/, evals/ml/, tests/ml/, new model/experiment docs under docs/ml/, small reproducible reports, the task handoff and necessary Python dependency/lock changes. Preserve accepted data_pipeline behavior and fixtures; request a specific change if an actual data bug blocks you. No backend/API/contracts/migration/web changes. Coordinate Python dependency ownership with C07 later.

## 1. Freeze a workable data and evaluation protocol first

- Default C03 train eligibility is 20 fraud / 0 legitimate rows. Do not fit a classifier on it or relabel unknowns as legitimate. Choose a bounded longer history and label-maturity strategy on the laptop; validate both class counts and every split before fitting. max_rows limits exported rows after generation, not generation memory. Bound accounts/days up front; report actual runtime/memory and reject silent truncation.
- Freeze config/seed, training-label cutoff, chronological windows, embargo/maturity gaps, allowed feature schema and review capacity/tie policy before accessing final test performance. Commit/save the protocol and its digest. Do not search seeds or windows for attractive test scores.
- State when labels are observable for training and validation selection, and ensure any claimed historical deployment timeline is possible. A full synthetic-truth offline benchmark may be reported if explicitly labeled; it is not proof that those labels were available for a historical selection decision. Never use final test labels to tune models, thresholds, calibration or features. Unknown/never-disclosed labels must stay distinguishable.
- Preserve natural validation/test prevalence. Historical overlap in 30-day feature windows is allowed only as declared stream context; a one-day embargo is not a 30-day independence guarantee.
- Validate dataset/file/feature hashes, actual account/transaction/label/class counts and currency summaries. C03 verify has partial derived-summary checks; add the validation your ML snapshot actually needs under owned ml/tests paths. A passing hash check does not establish that every manifest summary is correct.

## 2. Build CPU baselines and a real saved artifact

- Use NumPy/pandas as useful and scikit-learn for an explicit rule baseline, logistic regression and one seeded CPU tree baseline (for example HistGradientBoosting). Add only needed dependencies and lock them; use an optional training extra if it keeps the API runtime small. Document the exact uv sync command and ensure final checks have the declared extras. No GPU, API key, cloud purchase or subscription/model call.
- Consume the declared C03 decision-time feature set. Exclude external/account identifiers, scenario, fraud truth and label-availability metadata from model inputs. Any additional decision-time feature such as currency must have explicit version/provenance. Fit imputers/scalers/encoders only on training data; reuse the fitted pipeline unchanged on validation/test.
- Keep a small fixed candidate/search budget. Record every compared baseline, including losing ones. Choose the candidate and thresholds on the declared validation view only. Preserve a single reproducible final evaluation for the frozen test; do not iterate on test results.
- Save the fitted pipeline plus JSON manifests: code/data/feature versions and hashes, dependency versions, seeds, label-view/cutoff, split IDs or digests, threshold/capacity policy, hyperparameters, metrics, timing and artifact hash. Keep large generated datasets ignored; retain a small real trusted artifact/report fixture sufficient to demonstrate loading/prediction and reproducibility.
- Pickle/joblib loading is allowed only for your trusted locally generated artifact. Never deserialize a visitor-supplied model, remote arbitrary path or untrusted blob. Confirm round-trip predictions and schema/version mismatch refusal.

## 3. Evaluation and analyst evidence

- Report average precision distinctly from trapezoidal PR-AUC, and don't use accuracy as the headline for imbalanced fraud. Include precision/recall at a stated review capacity, false-positive counts/rates, a confusion matrix at the chosen threshold and calibration/Brier evidence when probabilistic interpretation is used.
- Define capacity units, windowing and ties exactly (daily batch ranking versus a streaming threshold are different policies). Never present a rule score or uncalibrated margin as a fraud probability.
- Add declared error slices for available dimensions such as currency, scenario/lookalikes, account activity and time. Synthetic hidden scenario may be used only for offline evaluation slices, never input features.
- Report uncertainty with a method appropriate to correlated account/episode rows (for example account/block resampling), sample counts and one-class/small-sample limits. No invented real-bank savings, production efficacy or causal claims.
- Produce reviewable small tables/charts from actual frozen results and a concise model card. Plots need reproducible source data and synthetic labels, not fabricated dashboard metrics. Preserve machine-readable outputs for C07/U03 without inventing serving endpoints now.

## 4. Tests, checks and handoff

Write meaningful tests for as-of training eligibility, preprocessing fit isolation, feature/label separation, deterministic split/capacity ties, metric definitions, threshold freezing, trusted artifact round-trip and fail-closed schema/version handling. Use independently specified small examples; avoid assertions that only mirror implementation internals. Record a regression failure first for any actual bug corrected.

Run a bounded training/evaluation command end to end and all required checks in the dedicated environment with live Claude off. Preserve contract/schema/Node checks and existing regressions. Coordinate later C06 CI installation of training extras and C02's longer checker timeout; local success is not a CI/Linux result. No WSL setup, GitHub provisioning or added spending is implied.

Update new experiment/model docs and your task handoff with exact protocol/data/artifact hashes, actual commands/counts/results, memory/runtime and limits. Stage explicit owned paths, inspect for secrets/unrelated artifacts, commit, then run final strict checks after the final commit. Return the exact SHA and dependency, all baselines, selected policy, saved-artifact evidence and gaps. Stop C07 serving work until Codex accepts C04. Keep central STATUS/TASK_QUEUE with Codex.
