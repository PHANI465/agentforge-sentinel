Completed update October 26: I03 4fff776 is accepted for Windows-local release-candidate scope; see task/coordination:docs/reviews/4fff776.md. Preserve the tested branch. The owner has not named the main integrator; no main merge or I03 rewrite is assigned. The original task below is history.

# Claude I03: consolidate the accepted local release

Read the latest task/coordination:AGENTS.md, docs/STATUS.md, docs/TASK_QUEUE.md and docs/reviews/353ecec.md plus reviews/4f06e32.md and reviews/f38e920.md. The owner resumed work on October 26. C08 R28 is accepted; do not repeat the old implementation assignment. You are the integrator for this task branch only. Codex reviews the resulting candidate; main integration still requires the owner's designation.

## Exact dependencies and workspace

- Accepted application/I02: f38e92023481a55db1ecf8bcdbe917140bd5d7cd.
- Accepted C08: 353ecec2fadbba43f939a27f5ad2b9227ff6fe87.
- Accepted C06: 4f06e32385424613fa0006b5bdbaab81ffea028f.
- C06 and C08 already include the accepted application, and their observed common ancestor is f38e920.

Inspect existing branches/worktrees first. Create a new task/claude-release-integration branch/worktree at E:/PHANI/sentinel-wt/claude-release-integration from exact 353ecec, then merge exact 4f06e32 there. Record merge parents and any conflict resolutions. Refuse mismatched existing paths rather than adopting or resetting them. Do not switch branches in, rewrite, rebase or edit any accepted checkout. Read coordination files from their named Git reference; do not merge the coordination branch's older application code into this release.

## Scope and preserved behavior

Combine the accepted CI/operator/app changes. Retain all six strict-check commands, C06's package check, the 1800-second per-command bound, locked dev+ml setup, structured CI skip gate, pinned workflow actions/read-only permissions, current HTTP v1/v1.1 examples, trusted p1 assets and four migrations. Record source/contract/model/UI/lockfile byte comparisons against f38e920. No model threshold, training, evaluation or fixture changes.

Own integration-only fixes in scripts/, backend CI/tests and docs/ci or docs/runbooks, plus your handoff/release note. Preserve web/ as accepted; no H01 changes or UI feature work is assigned. If a real incompatibility requires production, shared-contract, dependency or frontend changes, hand Codex the exact failing command/example and proposed narrow change before crossing that ownership boundary. Do not edit central STATUS/TASK_QUEUE/AGENTS or owner-facing dated artifacts.

## Verification

1. Use this worktree's locked dev+ml environment. Set SENTINEL_LIVE_CLAUDE=0 and SENTINEL_INVESTIGATOR=deterministic; unset external test database URLs and another checkout's VIRTUAL_ENV. No model-provider calls or paid fallback. Do not run two full backend suites concurrently on this laptop.
2. During integration, use focused checks for actual conflicts/failures. No need to rerun every component full suite before the final combined check.
3. On the final clean committed candidate, run scripts/agent_check.py with all six commands. Obtain JUnit from that same full pytest run where practical, then run scripts/ci_test_gate.py --validate-only on it: exactly the opt-in live-Claude skip, no unexpected skips/xfails, no missing required coverage and no failures. A per-run PYTEST_ADDOPTS JUnit option is acceptable if compatible with nested test invocations; verify that the retained report is the final full-suite report. Record your method. Do not weaken checks or silently substitute a nested fixture report, and avoid a second full backend run merely to obtain another report format.
4. Verify scripts/export_http_contract.py --check and read-only python -m ml test --reproduce on the final candidate. Frozen p1/source data files must remain unchanged. The sixth strict command must verify clean wheel/sdist, all four migrations/eight accepted assets and isolated installed inference.
5. From web/, run npm ci with the existing lock (use offline cache if available), npm run typecheck, npm test, npm run build and npm run test:e2e unmodified. This must exercise the real browser/API/disposable Postgres stack with rule and registered model, expected failure-artifact scan, all token retention/secret scanning and identity-verified cleanup. Do not sum overlapping branch test counts or claim a fake-client test proves persistence.
6. Exercise a narrowly scoped local_stack model-mode up/status/down smoke on test-owned resources, if supported without changing the accepted fixtures. No Claude call. The existing focused tests already cover the rule rollback/backup path. Check cleanup and keep recovery when unconfirmed; never kill by process name or delete an unverified directory.
7. Record actual commands, exits, counts, time and platform. Any final edit invalidates final-commit checks; rerun only what that edit actually invalidates, including the required clean-commit strict gate. Do not claim Linux/GitHub CI/hosting or production fraud performance.

## Delivery

Create docs/releases/I03-local-release.md with dependency/final-code references, how to start the integrated app, verified paths, limitations and remaining gates. Update your own branch handoff with actual results. Commit explicit owned paths, then return exact merge/final SHA, clean state, check results and any unresolved recovery state. Do not try to put a commit's own SHA inside that same commit; use the final chat/ignored report for the containing SHA.

Keep accepted checkouts and Cursor's original saved work untouched. Cursor can remain closed. No main merge, push, remote creation, WSL installation, deployment or new spending is assigned. Return the concrete candidate for Codex review before any broader feature track starts.
