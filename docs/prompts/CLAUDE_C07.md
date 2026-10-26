# Claude C07: controlled trained scorer in the API

C04 is ACCEPTED at 09b5378150faed06caa73b0384b9ff095c095eb8 for offline synthetic training/evaluation. Preserve its protocol, selection, artifact and results. C05 a8294f6, C02 0e72b0b and C01 2e6c232 are accepted separately. U02 5f28555 is separately accepted and preserved for later combined-stack verification; keep this C07 task's existing named dependency base stable and do not edit web/. U03 still waits for an explicitly accepted C07 HTTP dependency.

Read current coordination without merging it for application code:
    git show task/coordination:AGENTS.md
    git show task/coordination:docs/TASK_QUEUE.md
    git show task/coordination:docs/reviews/09b5378.md
    git show task/coordination:docs/prompts/CLAUDE_C07.md

Use task/claude-model-serving in E:/PHANI/sentinel-wt/claude-model-serving, starting from exact C04 09b5378. Include accepted C05 a8294f6a98a3a5f2c093dc6b97d1da8a594c9fdd (which includes C01), and accepted C02 0e72b0bd599ff1707ca5b2507d65a0927894cbe0 for integrated backend fixtures/checker timeout. Record each exact dependency and resulting task integration commit. Inspect/reuse existing work safely; no resets or merges into main. Preserve C02's 900-second checker timeout and account for pending C06 checker changes later.

Own backend scorer/feature-provider integration, required database migrations and grants, Python packaging/dependencies, versioned contracts/fixtures, backend tests, technical docs and your handoff. Do not edit Cursor's web/, lock, browser runner or central STATUS/TASK_QUEUE. Keep one backend/contracts writer.

## Contract-first increment

Design a small explicit HTTP/results revision exposing actual scorer identity/version, feature/artifact/protocol/threshold provenance and score semantics, plus the frozen offline model-results data needed by U03. Keep recorded rule scores distinguishable from uncalibrated model scores. Freeze candidate DTOs, examples, error behavior and compatibility tests in an early commit and return its SHA for Codex review before Cursor consumes it. No mock-only functionality may be called finished. Continue independent packaging/feature/inference work while contract review is pending.

Preserve legacy C01 bodies/status behavior and frozen golden files deliberately; a new contract revision must be explicit, with active-version export and legacy compatibility checks. Do not silently rebless old snapshots to hide drift. U03 remains gated until Codex explicitly accepts its named dependency.

## Actual inference and model identity

- Retain explicit rule mode/default and add explicit trained-model mode. No silent fallback when a configured artifact/profile is missing or incompatible; return a documented safe failure. A visitor or model cannot select an arbitrary artifact path or grant scoring permissions.
- Load only the accepted locally produced artifact from a fixed trusted registry/root. Before deserialization, bind expected artifact bytes, manifest, accepted protocol/selection, feature/model code/schema versions, dependency version and threshold/review-policy identity. The current C04 helper checks feature/env/model bytes but does not itself enforce every protocol/selection metadata field; add the runtime binding and refusal tests rather than assuming it does. No uploaded/remote/arbitrary pickle/joblib.
- Package required ml/data_pipeline modules, protocol, artifact and manifests/resources. Prove imports and inference from a clean installed wheel outside the source checkout, with source PYTHONPATH removed, and verify migrations are shipped. Avoid accidentally packaging generated data/node_modules/tests or retraining on API startup. Keep the accepted models.py implementation/hash unchanged where possible.
- The C04 selected score is uncalibrated. Use the accepted frozen pointwise threshold for online alerts with explicit provenance, not the old rule cutoff or the daily top15 batch policy. Daily ranking is an offline/batch result, not a promise of exact online capacity. No probability or real-bank efficacy claims.

## Real decision-time features, not invented metadata

- f1 needs account home currency/opened_at, account transaction history and prior disclosed fraud information. The current transaction input alone does not provide all of it. Define an authoritative scoped profile/disclosure source and actual storage/operator provisioning as needed; no hard-coded dummy account ages, fabricated home currencies or hidden future truth in live scoring.
- Use only history and disclosures actually available at the scoring decision; timestamp/cutoff/tie semantics must match accepted f1. Cover late/out-of-order arrivals, same event/arrival timestamps, currency units and cold-start/missing-profile behavior. If exact f1 cannot be supplied, fail clearly or propose a separately reviewed feature/model revision; never silently change trained semantics.
- Preserve tenant/session boundaries and transaction locking/idempotency. Every scoring outcome persists its exact value, model/artifact/feature/threshold/policy identity and relevant feature/provenance snapshot. Retries return that recorded outcome after restarts or configuration/model upgrades, without rescoring old cases.
- Extend explicit runtime-role grants for any new tables while preserving the accepted least-privilege policy, audit immutability, approval/execute boundaries and human authorization. Account/disclosure provisioning must not become a public capability/clock/seed bypass.

## Results, verification and handoff

Serve only reviewed server-owned synthetic model results and clear offline/scope labels; no arbitrary report-file path API, hidden train labels or fabricated tenant statistics. Charts/counts for U03 must match frozen C04 reports. Keep p1 frozen; currency-normalization is a later new protocol/holdout experiment, not test retuning.

Tests must demonstrate actual trained API inference and offline parity from independent fixtures, artifact/manifest/protocol mismatch refusal, scoped missing/stale profile/disclosure behavior, replay/upgrade persistence, installed-wheel inference and unchanged rule/default compatibility. Run real API/Postgres smoke evidence with deterministic investigations; C02 fixtures and C05 regressions must pass on the combined dependency commit. No live LLM, API-key fallback, extra spend, WSL setup, GitHub provisioning or hosting is implied. Document runtime/package footprint and known concurrency/platform limits honestly.

Use the worktree's locked environment with required dev/ml extras. Publish actual commands, hashes, counts, inference outputs/labels, legacy/new export checks and unverified items. Update technical docs/handoff, stage explicit owned files, commit, then run final strict checks after the final commit. Return the contract-candidate SHA early and the complete tested C07 SHA when ready. Main stays unchanged; C06/C08 and public/hosting acceptance remain separate.

## Current acceptance overrides

C07 is accepted at 275509af655a81a62bba28e74e9d8ab6c8d9cf5f with R23 resolved; see latest task/coordination:docs/reviews/275509a.md and docs/STATUS.md. Preserve the tested backend checkout and p1. Cursor U03 a5716e2 is delivered for review; C07 is not in that branch yet. No new implementation, combined-stack merge or main merge is assigned by the original prompt above. C06/C08 and the integration task retain separate gates.
