# Shared implementation queue

Planning date: October 23, 2026. The owner asked to use Claude heavily today and explicitly requires Cursor to contribute. This is the next executable queue, not a promise that every package fits before a subscription reset.

## Current accepted evidence and coordination

- Code reviewed: c6d369f6043a8c9ec86d8f56cf05670e81fba81d, task/thin-path. R1-R8 fixes accepted for the local thin-path scope; independent focused tests and normal checks passed. See reviews/c6d369f.md.
- Main is still the original baseline unless a later integration record says otherwise. This coordination branch includes the reviewed code. New tasks must start from the committed task/coordination reference, or a later explicitly accepted integration commit; do not accidentally start the UI/backend from the old main.
- Codex is the review and coordination lead. The existing owner-designation gate for merging into main remains; this queue does not silently authorize a merge.
- Claude owns backend, data/ML, backend verification and backend CI work. Cursor MUST own the analyst UI and browser tests. Claude must not absorb Cursor's UI assignment merely to use quota.
- No automatic cross-tool messaging or shared runtime memory is assumed. Shared Git commits, this queue, acceptance artifacts and task handoffs are the synchronization mechanism.
- Central queue and STATUS changes belong to Codex. Implementers update their own task handoff, technical documentation and task evidence. Bring the commit/summary back for review.

## Delivery and review snapshot

Latest owner-provided handoff, with branch commits verified by Codex:

| Package | Delivered commit | Review state |
| --- | --- | --- |
| C01 HTTP contract | 0a6fb0ec8e63fd686ac7e4cf6bbfb7bd22a105b0 | CHANGES REQUESTED: R9 malformed cursor; R10 error-contract accuracy |
| C03 synthetic data | a8e716cdec38fad1c316c6ffa2b722601b50b41d | DELIVERED, CODEX REVIEW PENDING |
| C06 backend CI | e7fc868b52a1d3cc8876d8d993907398663c2d57 | DELIVERED, CODEX REVIEW PENDING; no GitHub/Linux run |
| C08 local operations | 9ab183e836751a75e7a1a350afc51af7663f9a63 | DELIVERED, CODEX REVIEW PENDING |

C01's existing tests pass (40 focused, 146 full / 1 live skip), but independent HTTP probes reproduce R9/R10. Read [the review](reviews/0a6fb0e.md) and [the immediate Claude follow-up](prompts/CLAUDE_REVIEW_FOLLOWUP.md). C03/C06/C08 checks and runtime measurements remain attributed to Claude until independently reviewed. Delivery is not acceptance; the four task branches have not been integrated.

C02 and Cursor U01 wait for accepted corrected C01. C05 is parked until accepted C01 because it overlaps backend paths. C04 waits for accepted C03; C07 waits for accepted C04. WSL changes and GitHub provisioning are undecided and do not block the C01 corrections.

## How to make progress today

1. Claude fixes C01 R9/R10 first on its existing branch and immediately hands off the new tested commit. Do not repeat the delivered packages.
2. Codex re-reviews corrected C01 and separately reviews delivered C03/C06/C08. Those three packages are not implicitly accepted by this queue.
3. After C01 acceptance, Cursor U01 and Claude C02 can proceed independently in separate worktrees. C05 starts from accepted C01 and coordinates any API/migration edits. C04 starts only after accepted C03.
4. Cursor U02 follows accepted C02 plus U01; C07/U03 follow their model gates. Implementers do not merge main.
5. Use remaining allowance for ready work and concrete review corrections. If every dependency is blocked, provide an honest handoff rather than bypassing a gate, buying API capacity or repeatedly rebuilding completed work.

Do not try to spend quota for its own sake. The objective is reviewed working increments before the reset. Browser tests and ordinary CI use the deterministic investigator; real subscription calls are opt-in, targeted and recorded separately.

## Packages and acceptance

### C01 - HTTP boundary for a real analyst queue - Claude - CHANGES REQUESTED

Branch: task/claude-api-contracts. Own backend API/service/contracts, contract exports, backend tests and docs/api/.
Dependency: reviewed coordination base. Preserve existing endpoints and the corrected approval/idempotency behavior.

Deliver:
- Explicit response DTOs/examples for ingest/scoring, case detail, paginated case summaries, audit and safe errors. Export a versioned OpenAPI/HTTP snapshot with useful response models.
- Session-scoped GET /v1/cases with bounded pagination, deterministic ordering and filters needed by the first UI.
- A safe authenticated session/capabilities view and a minimal session-scoped overview. Never return bearer tokens, credentials or Claude account details.
- An API contract note with endpoint methods, auth, pagination, error/status semantics, score labels and a frozen example set.
- Review remaining timestamp capture in record_approval: a lock wait must not return an already-expired newly issued approval. Add a contention regression if changing it.

Acceptance: own-session records only, same-tenant foreign-session isolation, stable bounded pagination with ties, DTO/fixture/OpenAPI compatibility, safe errors and existing regressions pass. Record the exact contract commit for Cursor. No UI files.

### C02 - Real browser test support - Claude - BLOCKED ON ACCEPTED C01

Branch: task/claude-browser-fixtures. Own tests/support/, backend seed/startup scripts and docs/api/browser-fixtures.md. Leave web/ to Cursor.

Deliver reproducible deterministic fixtures and a local test-server lifecycle for approve/reject/expired/stale/duplicate/cross-session cases and provider failure. Supply a deterministic failing-investigator fixture that verifies a failed run and reopened case; it must make no model call. Return IDs and ephemeral test tokens through private test-process fixtures, not committed secrets or URL parameters. A clean Postgres database can be migrated, seeded, started and stopped automatically.

Acceptance: real server readiness/cleanup, synthetic-only data, fixture repeatability, real restart persistence, and no public endpoint that grants capabilities, changes time, bypasses authentication or seeds a database. Test-only clock/policy setup stays outside normal application routes. Document commands and the C02 commit for U02.

### U01 - Analyst workbench - CURSOR REQUIRED - BLOCKED ON ACCEPTED C01

Branch: task/cursor-analyst-ui. Own web/ and docs/ui/. Use React/TypeScript/Vite; reuse suitable original AgentForge UI pieces only with source/license provenance.

Deliver:
- Session-token entry held only in memory, connection/mode state and sign-out.
- Case queue with pagination, loading/empty/error states and a small overview backed by real endpoints. Provide a synthetic transaction entry/demo path through the authorized ingest API or clearly documented seeded cases.
- Case detail: transaction, exact currency amount, recorded score/semantics/artifact, evidence, investigator finding, exact server-built proposed action and audit timeline.
- Human approve/reject and a separate explicit execute step. Generate one idempotency key per intended execution and reuse it after an ambiguous network failure. Re-read authoritative state after changes and on 409.
- Clear states for expired approval/reopened case, insufficient permission, provider failure and replayed action.
- Render model text as inert text. No raw HTML, invented risk probabilities, fabricated metrics or owner-key fallback.
- A development proxy/base-URL setup matching C01. No broad backend CORS/auth edits.

Acceptance: build, type checks, useful component/client tests, keyboard navigation and accessible labels; all displayed values trace to frozen fixtures or actual API responses. Do not invent missing endpoints. Backend change requests go to Claude through a handoff.

### U02 - Browser-to-database acceptance - CURSOR REQUIRED - BLOCKED ON U01 + ACCEPTED C02

Own web/e2e/, browser fixtures/adapters and UI corrections. Coordinate browser-test commands with the integrator.

Use a real browser, real API process and real disposable Postgres with the deterministic investigator. Cover:
- ingest/open case -> investigate -> approve -> execute -> persisted audit;
- rejection, expiration/reopening/fresh approval, stale revision and provider failure;
- duplicate click/network retry, including a lost response after execution, returns the original action with one database effect;
- foreign-session access denied;
- browser reload/session loss does not silently recover a token from storage.
Include a process restart scenario where practical; distinguish it from reconstructing objects.

Acceptance: reproducible fresh-environment run with teardown, traces/screenshots sanitized, no live-model calls, real response/audit assertions and failing regressions for meaningful UI mistakes. Record actual commands and limitations.

### C03 - Reproducible synthetic financial data and historical features - Claude - DELIVERED, REVIEW PENDING

Branch: task/claude-fraud-data. Own data_pipeline/, tests/data/, small reviewed fixtures, data manifests and docs/ml/data-card.md. Start from the accepted coordination base; this task does not edit API/contracts or web/.

Build an independently implemented synthetic generator with fraud scenarios AND legitimate lookalikes, account history, explicit timestamps/currency units, imbalance, delayed labels and deterministic seeds. Separate hidden truth/labels from decision-time transaction projections. Start with a bounded laptop-sized dataset and a CLI row limit.

Define and test historical-only features, same-timestamp ordering, availability cutoffs and chronological train/validation/test split policy. Keep large generated data ignored; track code, small fixtures, manifests/hashes and summaries. Respect dataset/source licenses; do not copy GPL simulator code into an incompatible project.

Acceptance: repeatable manifests, schema/quality checks, per-currency counts/totals reconciliation, future-row and future-label invariance tests, no train/test preprocessing leakage, and measured generation runtime/memory. Document simulator assumptions and realistic limits.

### C04 - Classical fraud model experiments - Claude - BLOCKED ON ACCEPTED C03

Branch: task/claude-fraud-baselines. Own ml/, evals/ml/, tests/ml/, model/data cards and small reproducible reports. Claude owns Python dependency/lock changes; coordinate them with other backend branches.

Compare explicit rules, logistic regression and one CPU tree baseline. Fit preprocessing on training data only. Define delayed-label eligibility, chronological validation, review-capacity ranking/ties and threshold selection before final test evaluation. Preserve natural test prevalence and losing baselines.

Report average precision, precision/recall at stated review capacity, false positives, calibration, timing and assumptions. Keep average precision distinct from trapezoidal PR-AUC. Evaluate the frozen test only after design choices are fixed; do not repeatedly tune to it.

Acceptance: actual saved trusted local artifact, reproducible small seeded run, pinned code/data/feature/model/threshold manifests, model card, error slices and a documented comparison with uncertainty. Never claim real-bank effectiveness or guaranteed savings from synthetic results. No GPU/cloud purchase.

### C05 - Backend reliability, observability and secret safety - Claude - PARKED ON ACCEPTED C01

Branch: task/claude-backend-reliability. Own backend logging/diagnostics, security/failure tests, local role/migration setup and docs/security/. Coordinate any overlapping service.py or migration changes with C01 rather than writing both branches concurrently.

Deliver bounded safe request/trace IDs, latency/outcome metrics and code-only unexpected-error handling with synthetic canary tests. No bearer keys, provider credentials, raw request bodies, model context or credential-bearing DSNs in logs/errors/traces.
Add focused contention/rollback/recovery and same-account ingestion tests, explicit timeout/cancellation behavior and safe approval-expiry observation.
Provide a least-privilege local database role design and tests: runtime cannot alter schema/drop audit protections. Migration/operator privileges remain separate.

Acceptance: injected DB/provider faults produce honest states and safe errors; canaries absent from captured outputs; existing approval/replay/scoping tests pass; privileges and audit guarantees are accurately documented. Do not claim universal injection prevention or tamper-proof storage.

### C06 - Reproducible checks and backend CI - Claude - DELIVERED, REVIEW PENDING

Branch: task/claude-backend-ci. Own backend CI workflows, Python test/setup tooling, package-build verification and docs/ci/. Coordinate pyproject/uv.lock ownership with C04; no frontend source edits.

Create clean-environment backend checks with disposable Postgres, locked Python dependencies, lint, tests, schema compatibility and Node transport. Verify the built package contains migrations. Live Claude stays disabled.
Add the small seeded generation/training/evaluation job only once C03/C04 are accepted; do not manufacture green skips for a supposedly completed ML gate. Cursor owns a separate frontend/browser workflow or provides commands for integration.

Acceptance: each command reproduced locally; workflow syntax reviewed; real CI results distinguished from unexecuted configuration. An absent remote/runner is recorded as unverified, not green. Do not configure an external repository, purchase compute or expose secrets merely to obtain a badge.

### C07 - Controlled trained-scorer integration - Claude - BLOCKED ON C04 + REVIEW

Branch: task/claude-model-serving. Own the scorer interface, explicit rule/model configuration, model artifact verification, service integration and backend compatibility tests.

Only load trusted locally produced artifacts from the accepted training pipeline; no arbitrary uploaded pickle/joblib. Pin model/feature/threshold versions on every outcome/case. Preserve recorded replay scores and old case provenance. Missing or incompatible artifacts fail clearly.
Freeze any new HTTP fields before Cursor extends the UI.

Acceptance: actual trained inference in the API, parity with offline feature/scoring fixtures, rule baseline retained explicitly, replay/upgrade tests and no label leakage or fabricated probability claims.

### U03 - Model and analysis views - CURSOR REQUIRED - BLOCKED ON C07 HTTP CONTRACT

Own web/ extensions. Show actual scorer/version/score semantics, reproducible experiment results/error slices and clearly labeled synthetic limitations. Charts must match backend/report fixtures; keep currencies separate.
Acceptance: typed build/tests, browser assertions for actual values and correct labeling for rule versus trained-model mode.

### C08 - Deployment and operator preparation - Claude - LOCAL PACKAGE DELIVERED, REVIEW PENDING

Own local container/dev scripts and docs/runbooks/. Produce a reproducible local API/Postgres setup, migration/upgrade/rollback runbook, synthetic smoke commands and restricted staging design using deterministic investigations.
Verify current platform/plan limits from official sources before selecting hosting. Existing subscriptions/free allowances only. Keep owner subscription execution local/private and separate from public BYOK.

Acceptance: actual local startup/teardown and persistence smoke evidence where tooling is available, explicit unverified items, no owner model key in deployment configuration and no unsupported always-on/free-resource promise. Hosted provisioning/public release is a later instructed action, not implied by writing this plan.

## Gates for later increments

After the real browser path and reproducible ML baseline: scoped evidence/investigator/reviewer orchestration with one-agent comparisons; prompt/claim-support evaluations; public BYOK session/key isolation and cost/retention enforcement; drift/champion-challenger; then sequence/graph/RAG/fine-tuning tracks as justified.

Do not add a second personal subscription runtime merely to consume a plan. Cursor's required contribution today is implementation of the UI/browser work. Its runtime adapter can be evaluated later against the same fixture and permissions.

## Task handoff format

Every package records: task ID, owner, accepted dependency commit, task branch/worktree, owned paths, acceptance commands/results, tested revision, gaps and one next action. Use docs/handoff/_TEMPLATE.md and the collision-safe note path. Review/stage explicit files; commit when authorized; run final checks AFTER the final commit. A local report from another worktree is not transferable evidence.

When using separate worktrees, each tool reads the current coordination queue explicitly with git show task/coordination:docs/TASK_QUEUE.md until the integrator publishes a later canonical reference. Do not reset working trees or merge another agent's unreviewed branch to obtain context.
