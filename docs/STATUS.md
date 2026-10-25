# Project status

## Goal and delivery

Build AgentForge Sentinel, a fraud-risk investigation workbench demonstrating data analysis, classical ML, bounded multi-agent execution and enforceable AI security. Existing laptop/subscriptions and free resources remain the budget; no additional spending is assumed. No fixed deadline, per the owner's October 23, 2026 instruction. Delivery is milestone-based; see PROJECT_PLAN.md.

## Accepted code and current branch

- Main still holds baseline 507538e (adopted kit and draft contracts); the thin path has not been merged.
- Reviewed implementation: task/thin-path at c6d369f6043a8c9ec86d8f56cf05670e81fba81d, following ed08de0. It implements Postgres + FastAPI, rule scoring, recorded scoring outcomes, deterministic or opt-in local Claude investigation, human approval, idempotent simulated actions and audit.
- Codex independently re-reviewed R1-R8 and found no new blocking defect in those corrections. Focused regressions: 13 passed. Strict clean-commit check: passed; full pytest 106 passed / 1 intentional live-Claude skip, 21 handoff tests, 15 schema exports, Ruff and Node checks.
- Review scope and limitations: [c6d369f review](reviews/c6d369f.md). Claude's live-call, real-server restart and isolation-canary evidence was not independently repeated by Codex.
- C01 is separately accepted at 2e6c2329aafe28b2e7c31ef5078d554cb66ca529. See reviews/2e6c232.md. U01/C02/C05 include that application dependency. task/coordination carries current instructions on the older c6 source; do not use its tip or old main as their application base.
- G0 and G1 remain partial. U01 deb1037 is accepted with R14-R17 resolved. Bounded real-browser hold and escalation paths work; C04's offline trained model is accepted; U02 browser acceptance is complete on Windows for U01+C02; the trained API is separately accepted; combined-stack browser/model acceptance, hosted staging and public BYOK remain incomplete.

## Delivery and review snapshot

| Package | Delivered commit | Review state |
| --- | --- | --- |
| C01 HTTP contract | 2e6c2329aafe28b2e7c31ef5078d554cb66ca529 | ACCEPTED: R9/R10 resolved |
| C02 browser fixtures | 0e72b0bd599ff1707ca5b2507d65a0927894cbe0 | ACCEPTED: Windows local fixtures; R11/R12/R13 resolved; U02 separately accepted |
| U01 analyst UI | deb10370352dc62b0abfa2a5776c185494fcb04e | ACCEPTED: R14-R17 resolved; U02 separately accepted |
| U02 browser acceptance | 5f2855553ac0a445d96914730a89fc3722682830 | ACCEPTED: R21/R22 resolved; independent 14 real browser tests and cleanup passed on Windows |
| C05 backend reliability | a8294f6a98a3a5f2c093dc6b97d1da8a594c9fdd | ACCEPTED: R18-R20 and operator notes resolved within local backend scope; combined stack pending |
| C03 synthetic data | a8e716cdec38fad1c316c6ffa2b722601b50b41d | ACCEPTED: synthetic-data/historical-feature scope; C04 separately accepted |
| C04 trained baselines | 09b5378150faed06caa73b0384b9ff095c095eb8 | ACCEPTED: offline synthetic evaluation/artifact; 29 ML tests and frozen result independently reproduced; C07 separately reviewed |
| C07 model serving | 275509af655a81a62bba28e74e9d8ab6c8d9cf5f | ACCEPTED: local backend; R23 resolved; v1.1 unchanged; combined-stack acceptance pending |
| U03 model/analysis UI | a5716e252af2077a507767a3f819ddf44ea41c12 | ACCEPTED current-p1 frontend increment; full model-browser acceptance pending; I01/I02 assigned |
| C06 backend CI | e7fc868b52a1d3cc8876d8d993907398663c2d57 | DELIVERED, CODEX REVIEW PENDING; no GitHub/Linux run |
| C08 local operations | 9ab183e836751a75e7a1a350afc51af7663f9a63 | DELIVERED, CODEX REVIEW PENDING |

C01 acceptance and independent verification are recorded in [the re-review](reviews/2e6c232.md). The original [0a6fb0e review](reviews/0a6fb0e.md) remains history. C03 is separately accepted; see [the review](reviews/a8e716c.md). C06/C08 remain pending review; none of these branches has been integrated into main.

Use [the Cursor assignment](prompts/CURSOR_UI.md) for U01 and [the Claude C02 prompt](prompts/CLAUDE_C02.md) for backend browser fixtures. Start from/include accepted C01 2e6c232. The coordination branch is the current instructions reference, not the application base for these tasks.

U01 deb1037 and U02 5f28555 are accepted on their preserved U01+C02 browser base. C03 a8e716c, C04 09b5378 and C05 a8294f6 remain separately accepted. C07 is now accepted at 275509af655a81a62bba28e74e9d8ab6c8d9cf5f with R23 resolved; see [the re-review](reviews/275509a.md). The v1.1 snapshot at 62def10 is unchanged. Cursor completed the U03 contract/UI increment at a5716e252af2077a507767a3f819ddf44ea41c12; its clean branch and passed local strict metadata were found after shutdown. The current-p1 frontend increment is now accepted; new real-model browser acceptance is still pending. Claude I01 and Cursor I02 are assigned disjoint integration work. Preserve every accepted task checkout. C06/C08, combined-stack acceptance, WSL/GitHub provisioning, hosting and main integration remain pending.

## Immediate executable queue

1. Claude starts I01 using prompts/CLAUDE_I01.md: a dedicated task branch from accepted C07 275509a, include accepted U03 a5716e2, and deliver real deterministic model-browser fixture/lifecycle support. Preserve accepted checkouts.
2. Cursor starts I02 Part A now using prompts/CURSOR_I02.md: nullable/optional report-field compatibility on a dedicated branch from accepted U03. Part B waits for the explicitly accepted I01 SHA, then verifies actual browser/API/Postgres model flows and old regressions.
3. Codex reviews I01/I02 handoffs and pending C06/C08. No new model/features are needed before the integrated path is proved. Current-p1 U03 review: reviews/a5716e2.md.
4. Main still holds baseline 507538e. Main-integrator designation and remote provisioning remain separate; no merge or push is implied.
5. Preserve the laptop/subscriptions/free-resource budget. Live LLMs stay off in integration tests; Linux/CI, hosting/public-BYOK and measured performance remain later gates.

## Evidence history

- 2026-10-23, Codex-led baseline: domain contracts, 51 contract/schema tests and 21 helper regressions passed.
- 2026-10-23, Claude ed08de0: thin local path and manual live-Claude/server/database restart evidence; Codex review requested R1-R8 changes.
- 2026-10-23, Claude c6d369f: test-first R1-R8 corrections, migration 0002 and harness/line-ending follow-ups; 107 pytest tests with live Claude, 106 + 1 skipped by default. See VERIFICATION.md for attribution and limits.
- 2026-10-23, Codex c6d369f re-review: accepted local corrections; independent focused and ordinary checks passed on the clean reviewed commit. See reviews/c6d369f.md. Final coordination-commit checks are recorded externally in the final chat/local ignored report, not invented inside this commit.

## File ownership and integration

Codex is review/coordination lead and owns central STATUS/TASK_QUEUE. Claude owns backend, data/ML and backend reliability/CI. Cursor is a required implementation contributor and owns the analyst interface and browser tests. Each task uses a branch/handoff and a dedicated worktree for parallel work. No two tools edit a checkout concurrently.

The existing owner-designation gate for the integrator remains: the owner has not explicitly named the main-branch integrator, so this review/queue does not merge into main. Implementation starts from each package's accepted application dependency; task/coordination supplies current instructions.

| Area | Owner | Paths |
| --- | --- | --- |
| Central coordination/review | Codex | AGENTS.md, docs/STATUS.md, docs/TASK_QUEUE.md, review and dispatch docs |
| API/contracts/database | Claude, one writer at a time | src/sentinel/, contracts/, backend tests, docs/api/ |
| Data/ML/evaluation | Claude | data_pipeline/, ml/, evals/ml/, tests/data/, tests/ml/, docs/ml/ |
| Backend reliability/CI/operator tooling | Claude | backend workflows, backend scripts/tests, docs/security/, docs/ci/, docs/runbooks/ |
| Analyst UI/browser acceptance | Cursor REQUIRED | web/, docs/ui/, frontend workflow |

## Open measurements and limitations

- Laptop RAM/GPU/model speed and available disk; do not assume a GPU.
- Source-project tests/provenance, dataset licenses and historical-only evaluation policy still need task evidence.
- Actual Vercel plan, runtime/storage/worker constraints and persistent staging database. Verify current official limits before choosing hosting.
- Exact Claude allowance behavior and global-memory isolation remain unverified; local login is not a public API entitlement.
- Public tester-supplied key, expiry, retention and cost controls need a separate hosted acceptance gate. Never copy key values into planning files.
- Under-threshold scoring is recorded but has no case-bound audit event in v1. Legacy transactions before migration 0002 may have unknown scoring outcomes.
- Approval expiry is observed lazily on execute/investigate. Decide on an active sweeper only with a measured need.
- No CI, Linux/macOS, external test-database path or hosted staging has been independently verified here.

## C07 review on October 24

See [62def10 review](reviews/62def10.md): 37 focused model/contract/installed-wheel tests and ordinary compatibility checks passed independently; two real-Postgres interleavings confirmed post-cutoff operator data enters a captured model decision. R23 blocks backend acceptance. HTTP v1.1 artifact acceptance is explicitly limited to Cursor development. Claude full 372+1 strict evidence is attributed separately; no independent full repeat, main integration, live provider call or hosting occurred.

## Owner checkpoint on October 25

Start with [the project checkpoint](PROJECT_CHECKPOINT.md): summary first, step-by-step completed process, exact saved Cursor state, package register, ML evidence, skills, remaining milestones and restart commands. A standalone readable HTML copy is saved in E:/PHANI/Interview/output/AgentForge_Sentinel_Project_Checkpoint_2026-10-25.html. It is a dated snapshot, not a live dashboard.

C07 275509a passed independent 50 focused tests (142.83 s), Ruff, 21 helpers, 15 schemas, HTTP exports and Node. R23 is resolved. Claude's full386+1 count is attributed. U03 a5716e2 is observed delivered/clean with matching local strict metadata; new UI review remains pending. No new provider call, deployment, install, remote or main merge occurred.

## Integration assignments after U03 review

U03 a5716e2 passed independent37 frontend tests/typecheck/build and nine exact fixture-copy comparisons. Current-p1 increment accepted; legal nullable calibration fields and an omitted optional split field need N1 compatibility correction during I02. No full model-browser or new backend acceptance is claimed by those UI checks. Claude follows prompts/CLAUDE_I01.md; Cursor follows prompts/CURSOR_I02.md. These are task-branch integration assignments, not a main merge. C06/C08 remain review-pending.
