# Project status

## Goal and delivery

Build AgentForge Sentinel, a fraud-risk investigation workbench demonstrating data analysis, classical ML, bounded multi-agent execution and enforceable AI security. Existing laptop/subscriptions and free resources remain the budget; no additional spending is assumed. No fixed deadline, per the owner's October 23, 2026 instruction. Delivery is milestone-based; see PROJECT_PLAN.md.

## Accepted code and current branch

- Main still holds baseline 507538e (adopted kit and draft contracts); the thin path has not been merged.
- Reviewed implementation: task/thin-path at c6d369f6043a8c9ec86d8f56cf05670e81fba81d, following ed08de0. It implements Postgres + FastAPI, rule scoring, recorded scoring outcomes, deterministic or opt-in local Claude investigation, human approval, idempotent simulated actions and audit.
- Codex independently re-reviewed R1-R8 and found no new blocking defect in those corrections. Focused regressions: 13 passed. Strict clean-commit check: passed; full pytest 106 passed / 1 intentional live-Claude skip, 21 handoff tests, 15 schema exports, Ruff and Node checks.
- Review scope and limitations: [c6d369f review](reviews/c6d369f.md). Claude's live-call, real-server restart and isolation-canary evidence was not independently repeated by Codex.
- task/coordination adds this shared task queue and tool prompts on top of the reviewed implementation. New work starts from that committed reference or a later explicitly accepted integration commit, not the old main.
- G0 and G1 remain partial. There is no analyst UI, real browser-to-database acceptance, trained model, hosted staging or public BYOK yet.

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

## Immediate executable queue

Use [TASK_QUEUE.md](TASK_QUEUE.md) for exact branches, dependencies, ownership and acceptance. This is a substantial queue, not a promise that all tasks fit today.

1. Claude applies C01 review corrections R9/R10 and returns the new commit; see prompts/CLAUDE_REVIEW_FOLLOWUP.md.
2. Codex re-reviews C01 and reviews the separately delivered C03/C06/C08 packages.
3. Cursor U01 and Claude C02 wait for accepted corrected C01. C05 starts from the same accepted backend base with coordinated contract ownership.
4. C04 waits for accepted C03, including an explicit delayed-label eligibility and mature-label count policy. C07/U03 follow accepted training/API gates.
5. No WSL installation, GitHub provisioning, main merge or hosted release is authorized by this prompt update.

## Evidence history

- 2026-10-23, Codex-led baseline: domain contracts, 51 contract/schema tests and 21 helper regressions passed.
- 2026-10-23, Claude ed08de0: thin local path and manual live-Claude/server/database restart evidence; Codex review requested R1-R8 changes.
- 2026-10-23, Claude c6d369f: test-first R1-R8 corrections, migration 0002 and harness/line-ending follow-ups; 107 pytest tests with live Claude, 106 + 1 skipped by default. See VERIFICATION.md for attribution and limits.
- 2026-10-23, Codex c6d369f re-review: accepted local corrections; independent focused and ordinary checks passed on the clean reviewed commit. See reviews/c6d369f.md. Final coordination-commit checks are recorded externally in the final chat/local ignored report, not invented inside this commit.

## File ownership and integration

Codex is review/coordination lead and owns central STATUS/TASK_QUEUE. Claude owns backend, data/ML and backend reliability/CI. Cursor is a required implementation contributor and owns the analyst interface and browser tests. Each task uses a branch/handoff and a dedicated worktree for parallel work. No two tools edit a checkout concurrently.

The existing owner-designation gate for the integrator remains: the owner has not explicitly named the main-branch integrator, so this review/queue does not merge into main. Implementation can continue from the reviewed coordination reference.

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
