# Project status

## Goal and delivery

Build AgentForge Sentinel, a fraud-risk investigation workbench demonstrating data analysis, classical ML, bounded multi-agent execution and enforceable AI security. Existing laptop/subscriptions and free resources remain the budget; no additional spending is assumed. No fixed deadline, per the user's October 23, 2026 instruction. Delivery is milestone-based; see PROJECT_PLAN.md.

The folder is now a Git repository. `main` holds the baseline (adopted kit + draft contracts, commit 507538e). Branch `task/thin-path` (ed08de0 plus the review-fix commit) adds the local API path: Postgres migrations, a FastAPI boundary, a rule scorer, a deterministic investigator, an opt-in local Claude investigator, human approval, a simulated action and audit, with restart/race/isolation tests. G0 is partially complete. G1 is partially complete locally: no UI, browser end-to-end or hosted staging yet.

## Next: proposed priority order

1. [ ] Baseline and contracts (partial): hardware/RAM/GPU and a local-model benchmark are still unmeasured. Source-project tests are not reproduced. Hosting plan is unconfirmed. Evaluation split policy is not agreed. Done: contracts, migration from an empty database, Postgres/Claude CLI availability.
2. [ ] Thin integrated path (partial): local API path done and tested, including a live Claude investigation and a real server + database restart. Missing: analyst UI and browser-to-database end-to-end test, hosted staging with persistent DB, secret-safe trace inspection beyond error bodies.
3. [ ] Data/ML and analyst depth: delayed-label simulation, historical-only features, chronological evaluation, calibrated thresholds, analyst queries and reconciliation.
4. [ ] Multi-agent/security: bounded evidence, investigator and reviewer roles; compare against one-agent and deterministic baselines; adversarial and failure tests.
5. [ ] Public BYOK/reliability gate: scoped sessions, key isolation, durable/recoverable actions, expiry enforcement, quotas, cost visibility and independent hosted end-to-end checks.
6. [ ] Expansion: choose the next module from measured weaknesses. No model or service is added solely to lengthen the stack.

## Done

- 2026-10-23 (Codex-led): first domain-contract increment. 51 contract/schema tests and 21 helper regressions passed. See VERIFICATION.md history.
- 2026-10-23 (Claude Code, branch task/thin-path, ed08de0): Git baseline; Postgres + FastAPI thin path (decisions 0002-0004). 86 pytest tests passed (with SENTINEL_LIVE_CLAUDE=1), 21 helper regressions, 14 schema exports; manual two-process smoke with a live Claude investigation and restarts.
- 2026-10-23 (Codex review of ed08de0): request changes, findings R1-R8 plus harness follow-ups (E:\PHANI\Interview\output\Sentinel_Review_ed08de0.md).
- 2026-10-23 (Claude Code, branch task/thin-path, review fixes): R1-R8 fixed test-first, with regressions that failed on ed08de0 (decision 0005, migration 0002). Harness follow-ups were done too. 107 pytest tests passed with live Claude (106 + 1 skipped by default), 21 helper regressions, 15 schema exports. See VERIFICATION.md. Not merged to `main`.

## File ownership

Contracts/integration were Codex-led. At the owner's request, Claude Code implemented the thin path on `task/thin-path`. Codex reviewed ed08de0 (request changes) and recommended itself as integrator, subject to the owner's explicit designation. Next: Codex re-reviews the fix commit. The owner then names the integrator; until then nothing merges to `main`. Cursor is suggested for the analyst UI in its own branch/worktree after the API settles. After merge, assign one named owner and worktree per row.

| Area | Proposed paths | Coordination |
| --- | --- | --- |
| Contracts, migrations, integration | contracts/, src/sentinel/contracts/, src/sentinel/db/, src/sentinel/service.py, src/sentinel/api.py | Single integrator |
| Data/ML and offline evaluation | ml/, data_pipeline/, evals/ml/, src/sentinel/scoring.py | One branch owner |
| Agent runtime and AI security | src/sentinel/investigators.py, agents/, evals/agents/, evals/security/ | One branch owner |
| Analyst interface | web/, contract-generated client | One branch owner |

## Open questions to resolve by measurement

- Laptop RAM/GPU/model speed and available disk; do not assume 16 GB or a GPU.
- Actual Vercel plan, runtime/worker/storage constraints and idle cost; do not assume Hobby. Hosted Postgres choice for staging.
- Exact Claude plan and quota behavior under repeated investigations. Whether Codex/Cursor local adapters are worth adding against the same fixture.
- Which tester-supplied provider key can verify hosted BYOK without new owner spending. Never copy key values into planning files.
- Final source/dataset licenses and verified provenance. Claims in the imported research catalog must be reproduced before becoming project claims.
- Whether under-threshold transactions need their own audit event (AuditEvent.case_id is required in v1). Their scoring outcome is now recorded, but no audit event is.
- Whether lapsed approvals need an active sweeper (currently expiry is detected lazily on the next execute/investigate request).

## Immediate implementation target

Codex re-reviews the review-fix commit on `task/thin-path` (targeted R1-R8 regressions plus the ordinary checks). The named integrator then merges it and reruns checks on the merged commit. Then build the analyst UI (reuse the Vite/React frontend) over the existing endpoints and add a browser-to-database end-to-end test covering approve, reject, expired and duplicate cases. Then stand up restricted hosted staging with persistent Postgres using the deterministic investigator only. The Claude CLI investigator stays local.
