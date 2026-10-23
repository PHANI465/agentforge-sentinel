# Project status

## Goal and delivery

Build AgentForge Sentinel, a fraud-risk investigation workbench demonstrating data analysis, classical ML, bounded multi-agent execution and enforceable AI security. Existing laptop/subscriptions and free resources remain the budget; no additional spending is assumed. No fixed deadline, per the user's October 23, 2026 instruction. Delivery is milestone-based; see PROJECT_PLAN.md.

This folder now contains the adopted coordination kit plus draft domain contracts, pure precondition guards, schema exports, a synthetic transport fixture and a locked Python development environment. No API/database/UI, live inference or deployment is claimed yet. G0 is partially complete.

## Next: proposed priority order

1. [ ] Baseline and contracts (partial): measure hardware/local inference, inspect the source repository at a pinned commit, reproduce relevant checks, confirm hosting/subscription capabilities, agree transaction/alert/evidence/case/approval schemas and evaluation split policy.
2. [ ] Thin integrated path: one synthetic transaction -> actual rule score -> alert -> one bounded investigation -> approval -> simulated action -> audit, exercised locally and in an early hosted staging deployment. Label initial scoring honestly.
3. [ ] Data/ML and analyst depth: delayed-label simulation, historical-only features, chronological evaluation, calibrated thresholds, analyst queries and reconciliation.
4. [ ] Multi-agent/security: bounded evidence, investigator and reviewer roles; compare against one-agent and deterministic baselines; adversarial and failure tests.
5. [ ] Public BYOK/reliability gate: scoped sessions, key isolation, durable/recoverable actions, expiry enforcement, quotas, cost visibility and independent hosted end-to-end checks.
6. [ ] Expansion: choose the next module from measured weaknesses. No model or service is added solely to lengthen the stack.

## Done

2026-10-23: implemented and verified the first domain-contract increment: 51 contract/schema tests and 21 helper regressions passed; lint, 11 schema exports and the Node transport check passed. See CONTRACTS.md, BASELINE.md and VERIFICATION.md for scope, evidence and remaining G0 checks. Contracts remain draft pending storage/API integration; no complete application milestone is claimed.

## File ownership

Initial implementation: Codex leads contracts and integration. Other agents provide read-only review until contracts and the first full path exist. Afterward assign a named task owner and worktree per row; these are proposed boundaries, not current assignments.

| Area | Proposed paths | Coordination |
| --- | --- | --- |
| Contracts, migrations, integration | contracts/, migrations/, shared API | Single integrator |
| Data/ML and offline evaluation | ml/, data_pipeline/, evals/ml/ | One branch owner |
| Agent runtime and AI security | agents/, evals/agents/, evals/security/ | One branch owner |
| Analyst interface | web/, contract-generated client | One branch owner |

## Open questions to resolve by measurement

- Laptop RAM/GPU/model speed and available disk; do not assume 16 GB or a GPU.
- Actual Vercel plan, runtime/worker/storage constraints and idle cost; do not assume Hobby.
- Installed CLI versions and which documented personal subscription integrations are permitted. No assumption that subscriptions include public model API calls.
- Which supported local live integration is available: Ollama, a documented personal-subscription SDK/CLI, or an existing provider API allowance. Separately, which tester-supplied provider key can verify hosted BYOK without new owner spending. Never copy key values into planning files.
- Final source/dataset licenses and verified provenance. Claims in the imported research catalog must be reproduced before becoming project claims.

## Immediate implementation target

Add Postgres migrations and a small FastAPI boundary using these contracts, then make the synthetic transaction -> rule score -> alert -> deterministic investigation -> human approval -> simulated action -> audit path survive a restart. Use an independently authenticated server context, full evidence verification, compare-and-set revisions and atomic approval/idempotency handling. Run a real local-model smoke test separately; a deterministic fixture is not live AI.
