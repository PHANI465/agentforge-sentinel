# 0006: Controlled trained-model serving (C07)

- Status: proposed (C07, for Codex review; revised for review R23 on 62def10); amends 0002 (scoring) and 0005 (scoring outcomes)
- Date: 2026-10-24
- Decided by: project owner via docs/prompts/CLAUDE_C07.md; implemented by Claude Code

## Context

C04 froze one trained candidate: `hgb_balanced@p1`, with its artifact, a validation-frozen threshold and offline test results. C07 must serve it in the API without breaking the accepted v1 contract, the rule default, replay guarantees or the least-privilege runtime role. The f1 features need account attributes and disclosed outcomes that the thin path never stored.

## Decision

- **Scorer selection:**
  - The rule stays the default.
  - The operator sets `SENTINEL_SCORER=model:hgb_balanced@p1` explicitly. Any other value, a missing ml extra or a failed identity binding stops startup.
  - There is no runtime fallback in either direction.
- **Fixed registry; identity bound before deserialization:**
  - `sentinel.scorers.REGISTRY` names the only loadable model.
  - Before C04's `load_trusted` runs, the server compares the packaged protocol, selection and manifest against the registry. The fields compared are: protocol digest and version, selection digest, candidate, artifact hash, threshold, review policy, feature version and models-code hash.
  - Artifacts come only from the installed `ml/artifacts/p1/`. Visitor-supplied, remote or arbitrary pickles are never loaded.
- **Threshold:** model mode alerts when `score >= 4.0295386895426815e-06`, C04's validation-frozen pointwise threshold. The offline daily top-15 policy is not used online.
- **Decision-time features:**
  - The service computes f1 with C03's own `data_pipeline.features.compute` at the decision key `(now, external_id)`, where `now` is read after the per-account lock (decision 0005).
  - History is limited to the scope's rows with `occurred_at` in `[t-30d, t)` that were ingested strictly before the key.
  - `prior_known_fraud` counts the account's fraud disclosures with `disclosed_at <= now` **and** `recorded_at <= now`, excluding the transaction itself. A backdated `disclosed_at` alone is not availability.
- **Shared decision boundary (R23):**
  - **Shared lock:** operator writers and model ingestion take the same transaction-scoped advisory lock per (tenant, session, account). The key is `hashtextextended("tenant:session:account", 0)`, the same key the thin path already used for ingestion.
  - **Times after locks:** ingestion reads its decision time only after its lock. Writers read the time they stamp (`provisioned_at`, `recorded_at`) only after **all** their accounts' locks are held. Every lock is held until commit.
  - **Consequences:**
    - A write that waits behind an in-flight decision never enters it. That decision keeps the profile it read: profiles are not filtered by timestamp, so a valid earlier profile is never lost.
    - The write commits afterwards with a stamp no earlier than that decision's time. A decision that waits behind an in-flight write sees it once committed.
    - A writer transaction cannot become visible between a decision's time capture and its queries, because it cannot commit without the lock that decision holds.
  - **Batch locks:** each batch takes its locks deduplicated and in ascending key order, a single global order, so overlapping batches cannot deadlock.
  - **Batch size:** a batch may lock at most 256 distinct accounts (`batch_too_large`). The CLI loads files in 256-row chunks, one transaction each.
  - **Scope:** a different session or tenant uses a different key, so its writes never wait on this scope's decisions.
  - **Recorded-at filter:** this filter on disclosures also covers an operator clock running ahead of the API's: a disclosure stamped later than the decision is unavailable to it.
- **Authoritative inputs (migration 0004):**
  - `account_profiles` (home currency, opened-at) and `fraud_disclosures`, both scoped by tenant and session.
  - The operator loads them with `sentinel.cli provision-accounts` and `record-disclosures`. No HTTP route exists, and the runtime role has SELECT only.
  - A disclosure stores its `account_id` directly. `prior_known_fraud` therefore matches f1 even when the disclosed transaction was never ingested in this scope, and a disclosure cannot be attributed to a different account by joining on transactions.
- **Missing profile:** the request returns `422 account_profile_missing` before anything is stored. Dummy defaults are never used, and there is no rule fallback.
- **Persisted outcome:**
  - A model `ScoringOutcome` records `model` provenance and `inputs`: the exact f1 values, currency, history rows used, disclosures used, and the profile's home currency and opened-at.
  - Replays return that record unchanged, after restarts and after the scorer is switched or upgraded.
  - Cases pin the scorer that alerted.
- **Results:** `GET /v1/model-results/p1` serves packaged byte copies of the frozen C04 report, verified against registry digests. It is labeled as an offline synthetic benchmark.
- **Packaging:** the wheel ships `sentinel`, `ml`, `data_pipeline`, the migrations and only the accepted p1 identity, artifact and results files. A test installs the wheel in a fresh venv outside the checkout and runs inference in isolated mode.

## Alternatives considered

- **R23: a `recorded_at`/`provisioned_at` predicate without locks.** A mutable profile updated after T would hide the earlier valid profile. A writer that stamped its time before waiting could commit after a decision with a stamp earlier than it. Versioned profiles would also work, but they need a history table and a contract-visible version. The shared lock is smaller and reuses the existing boundary.

- **Derive profiles from first-seen transactions.** This invents `opened_at` and the home currency, which is exactly the dummy-default failure the prompt forbids.
- **Join disclosures to ingested transactions.** Disclosures of fraud that was never ingested would be lost, and offline/online parity with f1 would break.
- **Fall back to the rule when the model or a profile is unavailable.** Rejected because it silently changes semantics and thresholds. The operator must choose.
- **Use the daily top-k policy online.** It is a batch policy that needs a full day of scores. The frozen pointwise threshold is the accepted online policy.
- **A provisioning HTTP route.** Rejected because it would let the analyst API write authoritative model inputs.

## Consequences

- **Alert volume:** the frozen threshold is very low (recall-oriented; see the C04 model card), so model mode can alert on many more transactions than the rule (both smoke transactions alerted). That is a property of the accepted policy, not a serving bug, and alert volume was not measured.
- **Operator data:** profiles and disclosures must be provisioned per scope before model-mode ingestion. Stale or missing operator data is an operational responsibility. Profiles can be updated (upsert); disclosures are append-only, and a duplicate `external_id` is refused.
- **Upgrades:** a new model needs a new registry entry, packaged identity files and a new `results_id`. Old outcomes and cases keep their own pins.
- **Footprint:** model mode needs the `ml` extra (numpy, scikit-learn, joblib). Rule mode never imports numpy.
- **Synchronization:** relies on all writers using `Sentinel.provision_accounts` / `record_disclosures` (the CLI does). A direct SQL write by the schema owner bypasses the boundary; the runtime role cannot write these tables at all. Stamps assume the API and operator clocks are synchronized. If the operator clock runs behind, a write that waited behind a decision still cannot enter it (the lock), but its stamp understates its availability by the skew.
- **Contention:** a large batch briefly serializes model decisions for its accounts. Contention was not measured.
- **Not covered:** serving latency under load, profile staleness or retraction policies, and any real data. This decision makes no staleness or retraction guarantee.
