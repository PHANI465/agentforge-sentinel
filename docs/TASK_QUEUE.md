# Shared implementation queue

Planning date: October 23, 2026. The owner asked to use Claude heavily today and explicitly requires Cursor to contribute. This is the next executable queue, not a promise that every package fits before a subscription reset.

## Current accepted evidence and coordination

- Code reviewed: c6d369f6043a8c9ec86d8f56cf05670e81fba81d, task/thin-path. R1-R8 fixes accepted for the local thin-path scope; independent focused tests and normal checks passed. See reviews/c6d369f.md.
- Main remains the original baseline. This coordination checkout contains the accepted c6 thin path plus current instructions. C01 is separately accepted at 2e6c2329aafe28b2e7c31ef5078d554cb66ca529; U01/C02/C05 must start from or include that exact application dependency. Read task/coordination for current instructions, not as their application base.
- Codex is the review and coordination lead. The existing owner-designation gate for merging into main remains; this queue does not silently authorize a merge.
- Claude owns backend, data/ML, backend verification and backend CI work. Cursor MUST own the analyst UI and browser tests. Claude must not absorb Cursor's UI assignment merely to use quota.
- No automatic cross-tool messaging or shared runtime memory is assumed. Shared Git commits, this queue, acceptance artifacts and task handoffs are the synchronization mechanism.
- Central queue and STATUS changes belong to Codex. Implementers update their own task handoff, technical documentation and task evidence. Bring the commit/summary back for review.

## Delivery and review snapshot

| Package | Delivered commit | Review state |
| --- | --- | --- |
| C01 HTTP contract | 2e6c2329aafe28b2e7c31ef5078d554cb66ca529 | ACCEPTED: R9/R10 resolved; U01 continues |
| C02 browser fixtures | 0e72b0bd599ff1707ca5b2507d65a0927894cbe0 | ACCEPTED: Windows local fixtures; R11/R12/R13 resolved; full U02 still pending |
| U01 analyst UI | deb10370352dc62b0abfa2a5776c185494fcb04e | ACCEPTED: R14-R17 resolved; U02 ready with accepted C02 |
| U02 browser acceptance | bb318a1d283b1802e6f87e484393b50bf4a7673b | CHANGES REQUESTED: remaining R21 wrapper/config wiring; R22 corrections verified in reviewed scope |
| C05 backend reliability | a8294f6a98a3a5f2c093dc6b97d1da8a594c9fdd | ACCEPTED: R18-R20 and operator notes resolved within local backend scope; combined stack pending |
| C03 synthetic data | a8e716cdec38fad1c316c6ffa2b722601b50b41d | ACCEPTED: synthetic-data/historical-feature scope; C04 separately accepted |
| C04 trained baselines | 09b5378150faed06caa73b0384b9ff095c095eb8 | ACCEPTED: offline synthetic evaluation/artifact; 29 ML tests and frozen result independently reproduced; C07 ready |
| C06 backend CI | e7fc868b52a1d3cc8876d8d993907398663c2d57 | DELIVERED, CODEX REVIEW PENDING; no GitHub/Linux run |
| C08 local operations | 9ab183e836751a75e7a1a350afc51af7663f9a63 | DELIVERED, CODEX REVIEW PENDING |

C01 acceptance and independent verification are recorded in [the re-review](reviews/2e6c232.md). The original [0a6fb0e review](reviews/0a6fb0e.md) remains history. C03 is separately accepted; see [the review](reviews/a8e716c.md). C06/C08 remain pending review; none of these branches has been integrated into main.

Use [the Cursor assignment](prompts/CURSOR_UI.md) for U01 and [the Claude C02 prompt](prompts/CLAUDE_C02.md) for backend browser fixtures. Start from/include accepted C01 2e6c232. The coordination branch is the current instructions reference, not the application base for these tasks.

U01 deb1037 is accepted; see [the acceptance](reviews/deb1037.md). Cursor now implements [U02](prompts/CURSOR_U02.md) using accepted U01 plus C02. Codex left its implementation checkout unchanged. C02 0e72b0b is accepted; see [the acceptance](reviews/0e72b0b.md). U02 bb318a1 retains R21 entry-point gaps; see [the re-review](reviews/bb318a1.md) and [Cursor follow-up](prompts/CURSOR_U02_R21_FOLLOWUP.md). Preserve resolved R22 corrections. C05 a8294f6 is separately accepted; see [the acceptance](reviews/a8294f6.md). R18-R20 and operator notes are resolved. Preserve its tested C01-based branch for later combined-stack verification; do not interrupt Cursor's current U02 dependency snapshot. C04 09b5378 is accepted; see [the acceptance](reviews/09b5378.md). Claude starts [C07](prompts/CLAUDE_C07.md) in a dedicated integration worktree; U03 still waits for its accepted HTTP dependency. WSL changes, GitHub provisioning and main integration remain pending.

## Current execution order

1. Cursor corrects remaining U02 R21 wrapper/config wiring on bb318a1 using prompts/CURSOR_U02_R21_FOLLOWUP.md; preserve R22 and accepted U01/C02 dependencies.
2. C04 09b5378 is accepted. Claude starts C07 using prompts/CLAUDE_C07.md, including named accepted C05/C02 dependencies in its dedicated worktree; publish the HTTP candidate early.
3. U03 waits for explicit Codex acceptance of the C07 model-results HTTP dependency. No UI model-field invention or premature serving acceptance.
4. Codex reviews corrected U02, C07 deliveries and pending C06/C08. Main/hosting/public-BYOK gates remain separate; all combined-stack checks must run after integration.
5. Existing laptop/subscriptions/free resources only. No live-model ordinary tests, extra spending, WSL changes or GitHub provisioning is implied.

## Packages and acceptance

### C01 - HTTP boundary for a real analyst queue - Claude - ACCEPTED AT 2e6c232

Branch: task/claude-api-contracts. Own backend API/service/contracts, contract exports, backend tests and docs/api/.
Dependency: reviewed coordination base. Preserve existing endpoints and the corrected approval/idempotency behavior.

Deliver:
- Explicit response DTOs/examples for ingest/scoring, case detail, paginated case summaries, audit and safe errors. Export a versioned OpenAPI/HTTP snapshot with useful response models.
- Session-scoped GET /v1/cases with bounded pagination, deterministic ordering and filters needed by the first UI.
- A safe authenticated session/capabilities view and a minimal session-scoped overview. Never return bearer tokens, credentials or Claude account details.
- An API contract note with endpoint methods, auth, pagination, error/status semantics, score labels and a frozen example set.
- Review remaining timestamp capture in record_approval: a lock wait must not return an already-expired newly issued approval. Add a contention regression if changing it.

Acceptance: own-session records only, same-tenant foreign-session isolation, stable bounded pagination with ties, DTO/fixture/OpenAPI compatibility, safe errors and existing regressions pass. Record the exact contract commit for Cursor. No UI files.

### C02 - Real browser test support - Claude - ACCEPTED AT 0e72b0b

Branch: task/claude-browser-fixtures. Own tests/support/, backend seed/startup scripts and docs/api/browser-fixtures.md. Leave web/ to Cursor.

Deliver reproducible deterministic fixtures and a local test-server lifecycle for approve/reject/expired/stale/duplicate/cross-session cases and provider failure. Supply a deterministic failing-investigator fixture that verifies a failed run and reopened case; it must make no model call. Return IDs and ephemeral test tokens through private test-process fixtures, not committed secrets or URL parameters. A clean Postgres database can be migrated, seeded, started and stopped automatically.

Acceptance: real server readiness/cleanup, synthetic-only data, fixture repeatability, real restart persistence, and no public endpoint that grants capabilities, changes time, bypasses authentication or seeds a database. Test-only clock/policy setup stays outside normal application routes. Document commands and the C02 commit for U02.

### U01 - Analyst workbench - CURSOR REQUIRED - ACCEPTED AT deb1037

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

### U02 - Browser-to-database acceptance - CURSOR REQUIRED - R21 ENTRY-POINT CHANGES REQUESTED AT bb318a1

Own web/e2e/, browser fixtures/adapters and UI corrections. Coordinate browser-test commands with the integrator.

Use a real browser, real API process and real disposable Postgres with the deterministic investigator. Cover:
- ingest/open case -> investigate -> approve -> execute -> persisted audit;
- rejection, expiration/reopening/fresh approval, stale revision and provider failure;
- duplicate click/network retry, including a lost response after execution, returns the original action with one database effect;
- foreign-session access denied;
- browser reload/session loss does not silently recover a token from storage.
Include a process restart scenario where practical; distinguish it from reconstructing objects.

Acceptance: reproducible fresh-environment run with teardown, traces/screenshots sanitized, no live-model calls, real response/audit assertions and failing regressions for meaningful UI mistakes. Record actual commands and limitations.

### C03 - Reproducible synthetic financial data and historical features - Claude - ACCEPTED AT a8e716c

Branch: task/claude-fraud-data. Own data_pipeline/, tests/data/, small reviewed fixtures, data manifests and docs/ml/data-card.md. Start from the accepted coordination base; this task does not edit API/contracts or web/.

Build an independently implemented synthetic generator with fraud scenarios AND legitimate lookalikes, account history, explicit timestamps/currency units, imbalance, delayed labels and deterministic seeds. Separate hidden truth/labels from decision-time transaction projections. Start with a bounded laptop-sized dataset and a CLI row limit.

Define and test historical-only features, same-timestamp ordering, availability cutoffs and chronological train/validation/test split policy. Keep large generated data ignored; track code, small fixtures, manifests/hashes and summaries. Respect dataset/source licenses; do not copy GPL simulator code into an incompatible project.

Acceptance: repeatable manifests, schema/quality checks, per-currency counts/totals reconciliation, future-row and future-label invariance tests, no train/test preprocessing leakage, and measured generation runtime/memory. Document simulator assumptions and realistic limits.

### C04 - Classical fraud model experiments - Claude - ACCEPTED AT09b5378

Branch: task/claude-fraud-baselines. Own ml/, evals/ml/, tests/ml/, model/data cards and small reproducible reports. Claude owns Python dependency/lock changes; coordinate them with other backend branches.

Compare explicit rules, logistic regression and one CPU tree baseline. Fit preprocessing on training data only. Define delayed-label eligibility, chronological validation, review-capacity ranking/ties and threshold selection before final test evaluation. Preserve natural test prevalence and losing baselines.

Report average precision, precision/recall at stated review capacity, false positives, calibration, timing and assumptions. Keep average precision distinct from trapezoidal PR-AUC. Evaluate the frozen test only after design choices are fixed; do not repeatedly tune to it.

Acceptance: actual saved trusted local artifact, reproducible small seeded run, pinned code/data/feature/model/threshold manifests, model card, error slices and a documented comparison with uncertainty. Never claim real-bank effectiveness or guaranteed savings from synthetic results. No GPU/cloud purchase.

### C05 - Backend reliability, observability and secret safety - Claude - ACCEPTED AT a8294f6

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

### C07 - Controlled trained-scorer integration - Claude - READY; CONTRACT REVIEW BEFORE U03

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
