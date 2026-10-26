# Shared implementation queue

## Current Linux readiness: N3/N4 accepted; N5/N6/N7 assigned

N3/N4 **476abccc52b5228f71e129f8e3d0a8d9f11bef41** is accepted for its bounded changes: independent Windows and native Linux focused runs each passed 24 tests; Windows Ruff passed. Read [the review](reviews/476abcc.md). The owner full Windows six-check record is verified; the native full report matches all 436 collected cases but has **430 passes, five failures and one allowed skip**. The full Linux gate is not green; no merge/push occurred.

Next: [Claude N5/N6/N7](prompts/CLAUDE_N5_LINUX_LIFECYCLE.md) from exact 476abcc in a new dedicated worktree. This explicitly authorizes narrow browser_stack lifecycle edits, zombie detection and install-cache diagnosis. Both process defects reproduced independently with owned/reaped children. The install failure's missing package is still unknown; require cold-cache CI-order proof, not only a warm-cache rerun. Preserve accepted candidates, production code, contracts/frozen assets and the exact skip policy. Codex batches integration after review and final platform checks. Main remains verified a456f51; Cursor's seven saved edits are untouched.

Ubuntu setup is complete and native Linux is available as sentinel UID 1000. No additional environment approval is pending for this scoped task. GitHub Actions/macOS/hosting remain unverified; the existing orphan/PID-race limitations remain. New commits use PHANI465 <pgavara1@asu.edu> alone.

## Earlier setup and N3/N4 assignment record
## Current Linux readiness: setup complete; N3/N4 assigned

The owner approved Ubuntu setup. Native Linux tools and a non-root sentinel user/clone are ready: [actual results](ci/WSL_SETUP_RESULTS.md). At accepted N2 3c860d4, all six N2 startup cases passed natively; the combined focused run was **13 passed, one failed**. The failure is an actual PostgreSQL startup portability defect [N4](reviews/N4-linux-postgres-startup.md), not missing tooling. A controlled TCP-only cluster succeeded and was verified stopped. No Linux CI pass is claimed.

Claude's [N3/N4 assignment](prompts/CLAUDE_N3_PORTABLE_CLEANUP.md) now explicitly owns the narrow devdb startup correction plus the two Windows-only cleanup cases. Use base 3c860d4 in the separate task worktree. Run native Windows and Linux checks after the fixes, sequentially; preserve all skip/ownership/frozen-asset guarantees. Main remains checked a456f51, and accepted branches/source are unchanged.

Windows PostgreSQL was observed Running; no Windows service management was performed. The new Ubuntu packaged cluster and owned diagnostic cluster are stopped. Setup/test evidence is under canonical .agent/wsl-setup/. No provider call, paid service, GitHub remote, push or deployment. All new commits keep PHANI465 <pgavara1@asu.edu> as sole author/committer. H01 and the bounded multi-agent milestone remain later work.

## Earlier N2 review and pending setup record

**N2 3c860d4f1efa55c6d6e0bc28200b701afdfec837 is accepted** for its Windows-native and controlled POSIX-launch compatibility scope. Independent 14 tests passed in 39.23s, Ruff passed and the old launch negative control failed for the original ValueError. Final owner six-check metadata and all 435 JUnit node IDs match; 434+1 remains Claude execution evidence. No native Linux/CI pass is claimed. See [the review](reviews/3c860d4.md).

**Claude N3 is assigned, not started:** [portable cleanup-failure coverage](prompts/CLAUDE_N3_PORTABLE_CLEANUP.md), from accepted 3c860d4 in a new worktree. The two Windows-only cleanup skips would fail the Linux gate; an independent report-level probe confirms that rejection. Preserve actual Windows coverage, execute equivalent portable failure/retry cases, and keep the allowlist unchanged. Codex will batch N2/N3 integration after N3 review; verified main remains a456f51.

Native Linux needs a suitable environment. [The scoped WSL setup proposal](ci/WSL_SETUP_REVIEW.md) is prepared for the owner's decision; no setup has been performed. N3 code/Windows work can proceed independently. Main's passing source/report is unchanged. All new commits keep the owner's sole identity. H01 and the broader multi-agent/analyst/security feature milestone remain separate; Cursor can stay closed.

## Previous N2 assignment (now delivered)

Verified main remains **a456f510d8053ce67b4334564d75225a756d923d**: all six strict checks, 433 backend passes/one intentional skip, 44 frontend tests, 19 real browser tests, HTTP/package/model checks and final clean-state audit passed. See [the exact main verification](releases/MAIN-verification-2026-10-26.md).

**Claude N2 is assigned, not started:** follow [CLAUDE_N2_LINUX_READINESS](prompts/CLAUDE_N2_LINUX_READINESS.md) in a new worktree from exact main. Fix the Windows-only orphan-test launch while preserving real lifecycle coverage and the exact skip policy. Linux evidence requires an actually available environment; Ubuntu is registered in WSL2, but no Linux packages/users/configuration were changed by this dispatch. Missing setup is a separate concrete follow-up, not grounds to skip the code/Windows work.

These are coordination-document updates on task/coordination; main's tested commit/source remain unchanged. Codex reviews/integrates; all new commits use the owner's sole identity. Next sequence: N2, actual Linux/CI when ready, then bounded three-role fraud investigations with a one-agent comparison. H01 stays a separate low hardening task; Cursor can remain closed.

## Earlier main consolidation record: October 26

The owner designated **Codex as main integrator** and requested PHANI465 <pgavara1@asu.edu> as sole author on all future commits. This mainline consolidates accepted I03 4fff776 with coordination cad89cb. The application, contracts, model/data/evaluation files, frontend, locked dependencies, CI/checker and runtime tests are unchanged from I03. Reviewed component worktrees stay preserved.

Main is now the canonical application and instructions base. Read [the main release record](releases/MAIN-local-release.md) and SETUP.md. Final results are recorded after the containing commit in ignored evidence and the handoff chat; this document is not a self-certifying test pass. The strict gate must match the exact clean main HEAD/branch. The coordination reference is fast-forwarded during this consolidation; future tasks use main unless explicitly assigned another reference.

N2's Windows-only orphan-test launch, real Linux/CI, H01, hosted/public BYOK and the broader analyst/multi-agent/security milestones remain open. No push, remote creation, platform installation, paid/model-provider call or deployment is included. Existing October 25 rendered snapshots remain unchanged dated artifacts; today's Markdown checkpoint carries this integration update.

## Earlier I03 acceptance, before owner designation

**I03 is accepted at 4fff776fc4b6d2d400db74dc3ff7d6cfce43217d** for the combined Windows-local release-candidate scope. It includes accepted I02 f38e920, C06 4f06e32 and C08 353ecec without application/model/UI changes. Independent 37 combined tests (97.64s), clean package/installed-scorer verification and HTTP export checks passed. The final full-suite JUnit's 434 cases match independent collection; 433+1 remains Claude's execution evidence. See [the release review](reviews/4fff776.md).

**Next: the owner names the main integrator.** Main is still 507538e and no push or remote exists. Preserve exact 4fff776 and all tested component checkouts. The main-integration task must include current coordination documentation without overwriting the accepted application, then verify its final combined commit. Cursor can remain closed; no new implementation task is assigned by this review.

Linux/CI is not green: N2 identifies unguarded Windows creationflags in the orphan test, which needs adaptation before an Ubuntu CI run. POSIX operator behavior remains unverified. H01 remains non-blocking/unassigned. Yesterday's rendered HTML/Word checkpoint stays a dated snapshot; today's Markdown checkpoint and these live coordination files carry this update.

## Historical overnight checkpoint October 25

The owner asked to stop project development for today and continue next session, planned for October 26. **Do not start another implementation, merge or full runtime test tonight.** Documentation and artifact preparation are the only current work.

C08 R28 correction **353ecec2fadbba43f939a27f5ad2b9227ff6fe87** is delivered on task/claude-operator-prep, directly above 784e101 with no merge/rebase. Codex observed clean HEAD, matching passed five-check strict metadata and the handoff. Claude reports 411 backend tests passed, one opt-in live skip and 15 focused operator passes. **R28 independent re-review and C08 acceptance are pending**, not implied by that report. Accepted C06 4f06e32, I02 f38e920 and main 507538e are unchanged.

Next session starts with docs/prompts/NEXT_SESSION_2026-10-26.md. Preserve all tested worktrees. Cursor remains inactive, H01 remains non-blocking/unassigned, and no new paid runtime usage is assumed. The expanded vision is approximately **85 out of 200 planning points** under the explicit artifact rubric; this is a subjective scope estimate, not measured completion or a time forecast.

Matching HTML, Markdown and Word checkpoint files are in E:/PHANI/agentforge-sentinel/docs/artifacts/AgentForge_Sentinel_Project_Checkpoint_2026-10-25.{html,md,docx}. Their shared content covers the summary, 21 progress steps, the rubric, tomorrow's handoff and proposed improvements. Final document render/QA results are recorded separately; no future pass is claimed here.


## Earlier checkpoint: C06 accepted; C08 startup follow-up assigned

C06 is **accepted at 4f06e32385424613fa0006b5bdbaab81ffea028f** for the refreshed local CI configuration/gate/package scope. R25/R27 are resolved: independent 22 focused tests, four-migration/eight-asset installed-package check and read-only ML reproduction passed; the frozen files are unchanged. No Linux/GitHub runner result is claimed. See reviews/4f06e32.md.

C08 **784e1014044920706a41bd91c61b965a03379999 remains changes-requested for R28 only**. Its original 10 ownership/rollback/backup tests passed independently, and the documented rollback works. Additional intercepted startup probes confirmed a lost recovery record when identity inspection fails after launch, and false startup success after a readiness timeout. See reviews/784e101.md. Accepted I02 f38e920 is unchanged.

**Historical assignment, now delivered at 353ecec: Claude followed docs/prompts/CLAUDE_C08_STARTUP_FOLLOWUP.md** on the existing C08 branch. Preserve accepted C06 and I02; no C06 rework or broad operator rewrite is assigned. H01 is non-blocking and unassigned. Cursor remains inactive. After the focused correction/re-review, define release integration; main is still 507538e. Portable checkpoint files are in E:/PHANI/agentforge-sentinel/docs/artifacts/AgentForge_Sentinel_Project_Checkpoint_2026-10-25.{html,md} and remain dated snapshots.

## Latest checkpoint: combined local model/browser integration accepted

Codex completed the saved I02 Part B implementation at **f38e92023481a55db1ecf8bcdbe917140bd5d7cd**, branch task/codex-i02-completion in E:/PHANI/sentinel-wt/codex-i02-completion. Cursor remains an implementation contributor: its original seven edited files and exact byte snapshot are preserved. No need to purchase more Cursor usage to continue this work.

The combined local browser/model/API/Postgres path passes the 19-scenario browser suite (including the intentional failure used for credential-artifact checks). The last-run metadata reports passed with no unexpected failures; private lifecycle records were removed and the owned stack folder is empty. The scanner and 20 shutdown / 12 entrypoint harness checks preceded it. Frontend product code passed 44 unit tests and build on 4df18f2; that code is unchanged at final f38e920, whose e2e-inclusive typecheck passed. The final clean f38e920 strict check passed: Ruff, 396 pytest tests plus one opt-in live-Claude skip, 21 helper tests, 15 schemas and Node transport.

**I02 Part B is accepted at f38e920 after Claude's independent review**, forwarded by the owner: no blocking findings, independent 44 frontend tests/build/typecheck and 19 real browser tests (exit 0), plus a negative session-binding probe and seven error-hygiene probes. See [the acceptance record](reviews/f38e920.md). Two low test-hardening suggestions are tracked as non-blocking H01; the accepted commit stays unchanged. C06 is now accepted; C08 has the focused R28 follow-up before release integration. Cursor can remain closed. Main remains baseline 507538e; Linux/CI, hosting/public BYOK and production claims remain unverified. Earlier pending statements below are dated history.

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
| C01 HTTP contract | 2e6c2329aafe28b2e7c31ef5078d554cb66ca529 | ACCEPTED: R9/R10 resolved |
| C02 browser fixtures | 0e72b0bd599ff1707ca5b2507d65a0927894cbe0 | ACCEPTED: Windows local fixtures; R11/R12/R13 resolved; U02 separately accepted |
| U01 analyst UI | deb10370352dc62b0abfa2a5776c185494fcb04e | ACCEPTED: R14-R17 resolved; U02 separately accepted |
| U02 browser acceptance | 5f2855553ac0a445d96914730a89fc3722682830 | ACCEPTED: R21/R22 resolved; independent 14 real browser tests and cleanup passed on Windows |
| C05 backend reliability | a8294f6a98a3a5f2c093dc6b97d1da8a594c9fdd | ACCEPTED: R18-R20 and operator notes resolved within local backend scope; local browser integration now accepted at f38e920 |
| C03 synthetic data | a8e716cdec38fad1c316c6ffa2b722601b50b41d | ACCEPTED: synthetic-data/historical-feature scope; C04 separately accepted |
| C04 trained baselines | 09b5378150faed06caa73b0384b9ff095c095eb8 | ACCEPTED: offline synthetic evaluation/artifact; 29 ML tests and frozen result independently reproduced; C07 separately reviewed |
| C07 model serving | 275509af655a81a62bba28e74e9d8ab6c8d9cf5f | ACCEPTED: local backend; R23 resolved; v1.1 unchanged; local browser integration accepted at f38e920 |
| U03 model/analysis UI | a5716e252af2077a507767a3f819ddf44ea41c12 | ACCEPTED current-p1 frontend; real model-browser integration accepted at f38e920 |
| I01 model-browser fixtures | 7dd9428c70a7741af1c4781d22fd6b184f957444 | ACCEPTED: Windows local fixture/lifecycle dependency; ten independent real-process tests passed |
| I02 Part A | 50856be3da54ffdadd6cda7a0fcd5e59a9b21733 | ACCEPTED: N1 resolved; included in accepted Part B f38e920 |
| I02 Part B continuation | f38e92023481a55db1ecf8bcdbe917140bd5d7cd | ACCEPTED: independent Claude review; Windows local model/browser integration; two non-blocking H01 suggestions |
| C06 backend CI | 4f06e32385424613fa0006b5bdbaab81ffea028f | ACCEPTED: R25/R27 resolved, current local package/CI configuration scope; no GitHub/Linux run |
| C08 local operations | 353ecec2fadbba43f939a27f5ad2b9227ff6fe87 | ACCEPTED: R28 resolved; independent 15 focused tests / six probes; Windows-local scope |
| I03 release integration | 4fff776fc4b6d2d400db74dc3ff7d6cfce43217d | ACCEPTED: combined Windows-local candidate; main integrator decision pending; N2 Linux-test portability open |

C01 acceptance and independent verification are recorded in [the re-review](reviews/2e6c232.md). The original [0a6fb0e review](reviews/0a6fb0e.md) remains history. C03 is separately accepted; see [the review](reviews/a8e716c.md). C06, C08 and I03 4fff776 are accepted for their tested local scopes. Main remains unchanged pending the owner's integrator designation.

Use [the Cursor assignment](prompts/CURSOR_UI.md) for U01 and [the Claude C02 prompt](prompts/CLAUDE_C02.md) for backend browser fixtures. Start from/include accepted C01 2e6c232. The coordination branch is the current instructions reference, not the application base for these tasks.

U01/U02/U03 and the C01-C05/C07 components are preserved accepted contributions. Accepted I02 f38e920 establishes the combined Windows-local rule/model browser workflow; C06 4f06e32 and C08 353ecec are separately accepted. I03 4fff776 now combines these into an accepted Windows-local release candidate. Linux/real CI, main integration and hosted testing remain open. Older component assignments below are retained as history, not new dispatches.

## Current execution order

1. Claude follows prompts/CLAUDE_N2_LINUX_READINESS.md from exact main a456f51 in its own worktree. Preserve tested main and accepted components.
2. Codex reviews the concrete N2 commit and actual Windows/Linux/simulated evidence; source setup and skip-gate boundaries remain enforced.
3. Obtain actual Linux/CI evidence after needed environment/remote setup. No unexpected skip or unsupported POSIX claim.
4. Then select the bounded three-role fraud-investigation increment. H01 and hosting/public mode are separate; Cursor can remain closed and every new commit uses the owner alone.

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

### U02 - Browser-to-database acceptance - CURSOR REQUIRED - ACCEPTED AT 5f28555

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

### C06 - Reproducible checks and backend CI - Claude - ACCEPTED AT 4f06e32

Branch: task/claude-backend-ci. Own backend CI workflows, Python test/setup tooling, package-build verification and docs/ci/. Coordinate pyproject/uv.lock ownership with C04; no frontend source edits.

Create clean-environment backend checks with disposable Postgres, locked Python dependencies, lint, tests, schema compatibility and Node transport. Verify the built package contains migrations. Live Claude stays disabled.
Add the small seeded generation/training/evaluation job only once C03/C04 are accepted; do not manufacture green skips for a supposedly completed ML gate. Cursor owns a separate frontend/browser workflow or provides commands for integration.

Acceptance: each command reproduced locally; workflow syntax reviewed; real CI results distinguished from unexecuted configuration. An absent remote/runner is recorded as unverified, not green. Do not configure an external repository, purchase compute or expose secrets merely to obtain a badge.

### C07 - Controlled trained-scorer integration - Claude - ACCEPTED AT 275509a

Branch: task/claude-model-serving. Own the scorer interface, explicit rule/model configuration, model artifact verification, service integration and backend compatibility tests.

Only load trusted locally produced artifacts from the accepted training pipeline; no arbitrary uploaded pickle/joblib. Pin model/feature/threshold versions on every outcome/case. Preserve recorded replay scores and old case provenance. Missing or incompatible artifacts fail clearly.
R23 is resolved and the local backend is accepted at 275509a; see reviews/275509a.md. The v1.1 schema/examples at 62def10 are unchanged. Preserve the tested branch for later assigned combined-stack integration.

Acceptance: actual trained inference in the API, parity with offline feature/scoring fixtures, rule baseline retained explicitly, replay/upgrade tests and no label leakage or fabricated probability claims.

### U03 - Model and analysis views - CURSOR REQUIRED - CURRENT P1 FRONTEND ACCEPTED AT a5716e2

The initial contract/UI increment is delivered at a5716e2 from accepted U02 5f28555 and frozen v1.1 artifacts at 62def10. It is accepted for the current-p1 frontend scope; preserve it. I01/I02 now cover combined-stack work. C07 is now separately accepted at 275509a, but is not in this branch. New-feature real-stack acceptance requires a later explicit integration assignment. See prompts/CURSOR_UI.md for current instructions; prompts/CURSOR_U03.md records the implementation scope. Own web/ extensions. Show actual scorer/version/score semantics, reproducible experiment results/error slices and clearly labeled synthetic limitations. Charts must match backend/report fixtures; keep currencies separate.
Acceptance: typed build/tests, browser assertions for actual values and correct labeling for rule versus trained-model mode.

### C08 - Deployment and operator preparation - Claude - CHANGES REQUESTED R28

Own local container/dev scripts and docs/runbooks/. Produce a reproducible local API/Postgres setup, migration/upgrade/rollback runbook, synthetic smoke commands and restricted staging design using deterministic investigations.
Verify current platform/plan limits from official sources before selecting hosting. Existing subscriptions/free allowances only. Keep owner subscription execution local/private and separate from public BYOK.

Acceptance: actual local startup/teardown and persistence smoke evidence where tooling is available, explicit unverified items, no owner model key in deployment configuration and no unsupported always-on/free-resource promise. Hosted provisioning/public release is a later instructed action, not implied by writing this plan.

## Gates for later increments

After the real browser path and reproducible ML baseline: scoped evidence/investigator/reviewer orchestration with one-agent comparisons; prompt/claim-support evaluations; public BYOK session/key isolation and cost/retention enforcement; drift/champion-challenger; then sequence/graph/RAG/fine-tuning tracks as justified.

Do not add a second personal subscription runtime merely to consume a plan. Cursor's required contribution today is implementation of the UI/browser work. Its runtime adapter can be evaluated later against the same fixture and permissions.

## Task handoff format

Every package records: task ID, owner, accepted dependency commit, task branch/worktree, owned paths, acceptance commands/results, tested revision, gaps and one next action. Use docs/handoff/_TEMPLATE.md and the collision-safe note path. Review/stage explicit files; commit when authorized; run final checks AFTER the final commit. A local report from another worktree is not transferable evidence.

When using separate worktrees, each tool reads the current coordination queue explicitly with git show task/coordination:docs/TASK_QUEUE.md until the integrator publishes a later canonical reference. Do not reset working trees or merge another agent's unreviewed branch to obtain context.

## Integration assignments after U03 review

U03 a5716e2 passed independent37 frontend tests/typecheck/build and nine exact fixture-copy comparisons. Current-p1 increment accepted; legal nullable calibration fields and an omitted optional split field need N1 compatibility correction during I02. No full model-browser or new backend acceptance is claimed by those UI checks. Claude follows prompts/CLAUDE_I01.md; Cursor follows prompts/CURSOR_I02.md. These are task-branch integration assignments, not a main merge. C06/C08 remain review-pending.

## I02 Part A accepted while I01 checks continue

50856be passed independent 16 focused tests/typecheck/build and the original parser/fixture-copy probe. N1 is resolved; full 44 and strict 215+1 remain Cursor-attributed. Claude's I01 candidate is still work in progress; an active backend test process was observed and no final I01 acceptance is recorded. See reviews/50856be.md. Preserve accepted checkouts and avoid duplicate background jobs.

## I01 acceptance and I02 Part B dependency

I01 7dd9428 passed independent 10 real-process tests in 160.73s, Ruff, 21 helpers, 15 schemas, HTTP exports and Node. Exact accepted parents/protected-source equality and owner clean strict metadata were verified. Full 396+1, 40 C02 tests and 14 old rule-browser tests remain Claude-attributed. Final status compatibility and 1800-second checker bound are accepted; model-mode browser acceptance is I02's remaining work. Read reviews/7dd9428.md and prompts/CURSOR_I02_PART_B.md. Earlier candidate/waiting observations are historical.

## Historical I02 ownership handoff before final acceptance

Cursor is unavailable under its existing allowance. Its contribution is preserved at E:/PHANI/sentinel-wt/cursor-model-integration (e0e1b05 plus seven saved edits), with an exact byte snapshot. Codex continues in the isolated task/codex-i02-completion worktree from the same base; initial candidate 4df18f2. No new spending, production backend change or main merge is assigned. Final browser/backend checks are pending; this is an ownership checkpoint, not completion acceptance. Current active owner and provenance: prompts/I02_CODEX_TAKEOVER.md. Earlier Cursor execution instructions are superseded while quota is exhausted.

## H01: optional browser-test hardening after I02 acceptance

Non-blocking; unassigned, not implemented. Preserve accepted f38e920. In a later explicitly owned browser-maintenance increment, enforce a read-only transaction/session before any query in both inspect_case.py connection paths (or choose an appropriate SELECT-only role), and assert zero action_count and approval_count in the fresh model case immediately before Approve. Verify actual read-only rejection of a write and retain the real browser proof. Report the new commit and relevant checks separately. The startup-PID secondary check and serial-mode dependency remain informational observations; no cleanup or false-pass gap was found. See reviews/f38e920.md.
