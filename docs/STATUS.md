# Project status

## Goal and delivery

Build AgentForge Sentinel, a fraud-risk investigation workbench demonstrating data analysis, classical ML, bounded multi-agent execution and enforceable AI security. Existing laptop/subscriptions and free resources remain the budget; no additional spending is assumed. No fixed deadline, per the owner's October 23, 2026 instruction. Delivery is milestone-based; see PROJECT_PLAN.md.

## Accepted code and current branch

- Main still holds baseline 507538e (adopted kit and draft contracts); the thin path has not been merged.
- Reviewed implementation: task/thin-path at c6d369f6043a8c9ec86d8f56cf05670e81fba81d, following ed08de0. It implements Postgres + FastAPI, rule scoring, recorded scoring outcomes, deterministic or opt-in local Claude investigation, human approval, idempotent simulated actions and audit.
- Codex independently re-reviewed R1-R8 and found no new blocking defect in those corrections. Focused regressions: 13 passed. Strict clean-commit check: passed; full pytest 106 passed / 1 intentional live-Claude skip, 21 handoff tests, 15 schema exports, Ruff and Node checks.
- Review scope and limitations: [c6d369f review](reviews/c6d369f.md). Claude's live-call, real-server restart and isolation-canary evidence was not independently repeated by Codex.
- C01 is separately accepted at 2e6c2329aafe28b2e7c31ef5078d554cb66ca529. See reviews/2e6c232.md. U01/C02/C05 include that application dependency. task/coordination carries current instructions on the older c6 source; do not use its tip or old main as their application base.
- G0 and G1 remain partial. U01 5055321 resolves R14/R16/R17 but retains one R15 delayed-refresh query race. Bounded real-browser hold and escalation paths work; full U02 browser-to-database acceptance, a trained model, hosted staging and public BYOK remain incomplete.

## Delivery and review snapshot

| Package | Delivered commit | Review state |
| --- | --- | --- |
| C01 HTTP contract | 2e6c2329aafe28b2e7c31ef5078d554cb66ca529 | ACCEPTED: R9/R10 resolved; U01 continues |
| C02 browser fixtures | 0e72b0bd599ff1707ca5b2507d65a0927894cbe0 | ACCEPTED: Windows local fixtures; R11/R12/R13 resolved; full U02 still pending |
| U01 analyst UI | 5055321cfa810a2108d184e5542785cf44977edc | R14/R16/R17 resolved; CHANGES REQUESTED: remaining R15 delayed-refresh query race |
| C05 backend reliability | 0119ca73e6ae3b4df9f9eeffcea8b15911f716e6 | CHANGES REQUESTED: R18 existing-role privileges, R19 timeout parsing, R20 metric labels |
| C03 synthetic data | a8e716cdec38fad1c316c6ffa2b722601b50b41d | DELIVERED, CODEX REVIEW PENDING |
| C06 backend CI | e7fc868b52a1d3cc8876d8d993907398663c2d57 | DELIVERED, CODEX REVIEW PENDING; no GitHub/Linux run |
| C08 local operations | 9ab183e836751a75e7a1a350afc51af7663f9a63 | DELIVERED, CODEX REVIEW PENDING |

C01 acceptance and independent verification are recorded in [the re-review](reviews/2e6c232.md). The original [0a6fb0e review](reviews/0a6fb0e.md) remains history. C03/C06/C08 evidence remains Claude-reported until independently reviewed; those branches have not been integrated.

Use [the Cursor assignment](prompts/CURSOR_UI.md) for U01 and [the Claude C02 prompt](prompts/CLAUDE_C02.md) for backend browser fixtures. Start from/include accepted C01 2e6c232. The coordination branch is the current instructions reference, not the application base for these tasks.

Cursor finishes the remaining R15 delayed-refresh race using [the follow-up prompt](prompts/CURSOR_U01_R15_FOLLOWUP.md); see [the U01 re-review](reviews/5055321.md). R14/R16/R17 are resolved. Codex left its source checkout unchanged. C02 0e72b0b is accepted; see [the acceptance](reviews/0e72b0b.md). U02 waits for accepted corrected U01. Claude corrects C05 R18-R20 using [the review](reviews/0119ca7.md) and [prompt](prompts/CLAUDE_C05_REVIEW_FIXES.md) on its existing C01-based worktree. C04 still waits for accepted C03. WSL changes, GitHub provisioning and main integration remain pending.

## Immediate executable queue

1. Cursor finishes U01 R15 query ownership on its existing branch, adds the delayed mutation-refresh regression and hands off a new tested commit.
2. Claude corrects C05 R18-R20 using prompts/CLAUDE_C05_REVIEW_FIXES.md and returns a new tested commit.
3. After accepted U01, Cursor includes accepted C02 0e72b0b and implements U02. C05 remains separate until its corrections are reviewed; keep C01 frozen.
4. Codex reviews corrected C05 and delivered C03/C06/C08. C04 still awaits accepted C03; U02 awaits accepted U01 plus the accepted C02 dependency.
5. Main, WSL/GitHub provisioning, hosted release and model expansion remain outside this acceptance.

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
