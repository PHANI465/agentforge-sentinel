# Handoff: task/claude-g3d-evaluator-prep

## R41/R42 continuation (latest)

- **Task:** [CLAUDE_G3DP1_REVIEW_FIXES.md](../prompts/CLAUDE_G3DP1_REVIEW_FIXES.md), following review [G3D-P1-5811a29](../reviews/G3D-P1-5811a29.md). Continued on this branch from exact 5811a29fef9ccc5678ca6aa2f5efe0f2a6a6df78. The authority split, read-only checks and existing tests are unchanged.
- **State:** ready for Codex re-review. Tested before this note: the working tree on 5811a29. Exact-commit gates are reported in chat.
- **Changed paths:**
  - scripts/agent_eval.py
  - tests/test_agent_eval_failures.py (new)
  - docs/evals/agents/evaluator-runbook.md
  - this note
- **R41 fix:**
  - Preflight catalog reads and connection close now raise typed refusals, `runtime_check_failed` or `operator_check_failed`.
  - Setup (provision, authenticate, ingest) raising `SetupFailed` is not an attempt: no row, no latency. The run stops, earlier attempts are kept, and the record shows `status`, `stopped` and `comparators_not_started`, plus per-comparator `cases_not_attempted`. Exit is 3.
  - An investigate failure is still a counted attempt with its latency.
  - A failed usage read keeps the committed outcome and gives `usage_sources: ["unavailable"]` plus `usage_error`.
  - Codes are only service codes or exception class names. KeyboardInterrupt and SystemExit are not caught. The policy is in runbook §4.
- **R42 fix:** `tokens` is `adapter_reported` only if every attempt's `usage_sources` is exactly that. Errored requests get `["not_read"]`.
- **Duplicate names:** `--comparators C0,C0` is refused before any work (`duplicate_comparator`).
- **JSON shape:** additive only. New fields are `record.status`, `record.stopped`, `record.comparators_not_started`, per-comparator `cases_not_attempted` and per-row `usage_error`. Rows also get `usage_sources` values `not_read` and `unavailable`, and there is the new exit 3. `run()` keeps its return shape; stop state goes to an optional `progress` dict.
- **Failing first on 5811a29** (`.agent/g3d-p1/r41-failing-first-5811a29.log`): the new module gave 8 failed and 4 passed.
  - Failures:
    - both setup-failure cases (traceback printing the canary message, no report);
    - both preflight sides (a raw `OperationalError`);
    - the usage-read failure escaping;
    - provenance with a missing field reported as `adapter_reported`;
    - duplicate names executing twice.
  - The investigate-failure test failed only on the new `record.status` field. The base already counted that request as an attempt; it is a request-boundary control.
  - The other four provenance cases are controls and passed.
- **After the fix:**
  - 31 focused tests pass: the new module, the authority tests and the adapter tests.
  - Codex's seven original probes pass unchanged from a temporary copy, since removed (`.agent/g3d-p1/codex-probes-after-fix.log`).

- **Task and acceptance criteria:** G3D-P1 ([docs/prompts/CLAUDE_G3D_EVALUATOR_PREP.md](../prompts/CLAUDE_G3D_EVALUATOR_PREP.md) on task/coordination). Separate the manual runner's operator and runtime authority, verify on deterministic comparators only, and keep live comparators disabled.
- **Tool and worktree:** Claude Code (Opus 5.5 / High), in E:/PHANI/sentinel-wt/claude-g3d-evaluator-prep.
- **Base:** canonical main 365d32654be0cb7500d94176c87fc374ceb0659b. This is the published G3C release; its application commit is f788698.
- **Updated:** 2026-11-02, local time.
- **State:** ready for Codex review.
- **Code reference tested before this note:** the working tree on 365d326 with the three owned files below. Final checks are rerun on the exact commit and reported in chat; a note cannot name its own commit.
- **Owned and changed paths:**
  - scripts/agent_eval.py
  - tests/test_agent_eval_privileges.py (new)
  - docs/evals/agents/evaluator-runbook.md (new)
  - this note

  No production src, contracts, migrations or grants, frozen protocol, case, model, data or eval outputs, UI, dependency files, lifecycle helpers, CI, skip allowlist or timeouts changed.

## Implemented

- **Two authorities, both read from the environment.**
  - `SENTINEL_EVAL_OPERATOR_URL` does read-only runtime-role checks and issues one session per attempt.
  - `SENTINEL_EVAL_RUNTIME_URL` does authentication, ingestion and scoring, evidence reads, the investigation (real service, coordinator and tools) and the post-attempt usage read.
  - `--database-url` is now provisioning-only. If both it and the variable are set, they must be equal.
  - There is no operator fallback.
- **Checks before any comparator construction or case run.** The live-consent check stays first and unchanged. Then come:
  - comparator and case names, plus unsupported case setup;
  - configuration present and not identical;
  - safe connection failures that never print the driver message;
  - same database: name, OID, postmaster start time and port;
  - a runtime login that is distinct, has not switched role and has no admin attributes;
  - the accepted `roles.unsafe_reasons`, `roles.verify_effective` and `roles.environment_reasons`, read-only.

  Each failure prints `refused: <code>: <reason>` and exits 2.
- **Accounting kept from protocol-v1:** attempts, dispositions, inconclusive, refused, pending and error, plus inconclusive by code and latencies.
- **Accounting added:**
  - per-attempt rows (case, outcome, failure codes, case state, usage sources);
  - `tokens`, reported only when every call is `adapter_reported`, otherwise `unknown`;
  - a run record: git HEAD with `+dirty`, platform, times, authority split, and per-case runtime SHA-256 and `faults_not_applied`.
- **Runbook:** [evaluator-runbook.md](../evals/agents/evaluator-runbook.md). It gives the procedure, the refusal codes and the limits. It states plainly that the runner applies no case faults: D05–D15 run as no-fault baselines.

## Verified

- **Failing first on exact 365d326,** with the new test file only. 10 failed and 2 controls passed. Log: `.agent/g3d-p1/failing-first-365d326.log`, ignored.
  - The key result: with an operator `--database-url` and a runtime variable, base wrote `transactions` as the operator login (`{'sentinel'} != {runtime role}`).
  - An operator URL alone created 2 sessions and ran investigations.
  - The remaining refusal tests failed because base had no runtime configuration at all.
  - The runtime-boundary control and the existing `--allow-live` refusal test passed.
- **With the fix:** `tests/test_agent_eval_privileges.py` and `tests/test_agent_adapters.py` give 19 passed, and ruff is clean.
- **Database evidence:** a test-owned SECURITY DEFINER trigger outside `public` records the inserting login. `api_sessions` is inserted only by the operator. `transactions`, `cases`, `evidence_items`, `agent_runs`, `agent_workflows` and `agent_steps` are inserted only by the runtime role.
- **The runtime role cannot:**
  - create a session (`InsufficientPrivilege`);
  - CREATE TABLE, ALTER TABLE, DROP an audit trigger, or DELETE from cases.

  The same runtime role still ingests and investigates D01 to `awaiting_approval`.
- **Refusal tests:** for mismatched databases, missing operator or runtime configuration, an operator posing as runtime, a superuser, a runtime role with one extra grant, and an unreachable runtime or operator:
  - no session or transaction is written;
  - the canary password, the URL canary, the URLs, an unreachable user name, tracebacks and token-shaped strings never appear in the output.
- **Deterministic smoke (dirty tree before commit).** Two fresh disposable databases ran C0 and C2-det over all 15 dev cases. The cluster was stopped and removed. Both runs gave 15/15 dispositions for each comparator, with identical per-case outcomes. Tokens were `unknown`. Usage sources were `no_role_steps` for C0 and `not_applicable` for C2-det. C0 p50 was about 0.15 s and C2-det about 0.45 s. The smoke is rerun on the exact commit; see the chat report.

## Not verified / gaps

- No live comparator was run. `--allow-live` was never passed, and no provider was called.
- Case faults are not applied by this runner, as the runbook says. Fault behaviour stays evidenced by the pytest suites only.
- Workflow-elapsed percentiles and pin digests are not printed. The operator adds them for protocol-v1 §6.
- No browser rerun: there were no frontend edits. No macOS run, real CI or hosting.

## Next action

Codex reviews this commit before the next G3D step.

## Coordination and provenance

- All code is original to this task. It reuses the accepted `sentinel.db.roles` checks without changing grants. No dependencies, credentials or raw reports are tracked.
- Accepted worktrees and Cursor's seven saved edits are untouched.
