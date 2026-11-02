# G3C integration: diagnose native COMMIT timing and recovery failures

**Follow-up:** diagnosis/SQL-clock correction is delivered at f61b755 and passes scoped
review. Do not repeat the original investigation. Current task is
[R40 caller waits](CLAUDE_G3C_CLOCK_WAIT_FOLLOWUP.md) on the same branch, with explicit
service.py ownership. Main integration still waits for that correction.

Recommended coding assistant: **Claude Opus 5.5 / High**. This requires careful Postgres
transaction/cancellation, thread/connection lifetime and monotonic-budget analysis. No
new feature or framework is requested; Sentinel providers remain deterministic/off.

## Exact base and ownership

Read current task/coordination:AGENTS.md, STATUS, TASK_QUEUE and
docs/reviews/G3C-integration-7bc0027.md with git show. UI 6014680 is accepted, R38/R39 closed.
API 16b67fd is frozen. Main is still G3B; do NOT start from its older runtime.

Create task/claude-g3c-native-diagnosis at E:/PHANI/sentinel-wt/claude-g3c-native-diagnosis
from exact **7bc00272e083bb30d673eb4b11311623b992f942** and record that dependency. This
named diagnostic base overrides the generic main-base rule. Preserve original integration,
accepted API/UI, review checkouts and Cursor's seven edits. One editor only.

Inspect tests/test_agent_bounds.py, tests/test_agent_workflow.py, coordinator/budget
implementation, the retained logs and previous G3B R34-R37 review. Windows full integration
passes all six commands (594+1), frontend 133 and browsers 19+10. Native full integration
has 592 pass, two fail, one allowed skip; other five strict commands pass. HTTP/ML pass
separately. Native JUnit validation correctly rejects the failed report.

## Evidence to explain, not rerun until green

1. test_withheld_terminal_commit_reply_is_unknown_within_the_budget: correct unknown
   outcome, but 2.953205276 seconds against unchanged <2.5 assertion (two-second budget).
2. test_uncertain_commit_reports_outcome_unknown: unknown and investigating checks pass;
   recovery after clock advance gives conflict instead of investigation_recovered. The
   full test took 2.652 seconds; do not assume an expensive recovery COMMIT was reached.

One external-instrumented focused run of these plus the known-rollback control passes
3/3. It observes a ~1137 ms withheld COMMIT and ~3009 ms recovery COMMIT. This is NOT a fix
or diagnosis. Earlier exact component native gates passed too. Retain all contradictory
evidence; do not label it fixed, merely load, or merely a flaky test without proof.

Native originals: /home/sentinel/g3c-integration-reports/ and
/home/sentinel/g3c-integration-diagnostics/. Canonical ignored copies:
E:/PHANI/agentforge-sentinel/.agent/g3c-integration/native-first-failure/ and windows/.
External timing fixture/runner are in E:/PHANI/Interview/tmp/g3c_timing_probe.py and
run_g3c_focused_diagnosis.py; read before reuse. No credentials should be displayed.

## Work and stop conditions

First diagnose with narrow, hypothesis-driven runs. Capture actual phase budgets and
waiter/cancel/retirement/close timings, quarantine counts, relevant preceding test state,
and recovery's exact typed failure path. Observe only test-owned connections/processes;
parameterized safe queries, no secrets/raw exceptions in shared logs. Do not stop WSL,
unrelated processes or remove shared caches to obtain a green run. Document environment
and instrument overhead. Preserve production behavior while observing it.

If a code defect is proven, add a meaningful deterministic regression that fails for
that defect on 7bc0027, then make the smallest fix. Own src/sentinel/agents/budget.py,
src/sentinel/agents/coordinator.py, tests/test_agent_bounds.py, tests/test_agent_workflow.py,
a focused new test module if needed, a new diagnostic note under docs/agents/ and the
branch handoff. If the fault is outside this scope, hand off exact evidence before any
unrelated change. No new dependency, contract, migration, model/eval/data, UI or lifecycle
helper changes. Do not edit central coordination or original worktrees.

Do not increase deadlines/assertion tolerances/checker timeouts, add sleeps to mask it,
weaken tests, change the skip allowlist, skip cases, alter frozen claims or silently map
every failure to a convenient error code. Preserve unknown COMMIT versus known rollback
and safe connection retirement. If the evidence indicates an OS-scheduling/testing-contract
limit rather than a code fix, report the evidence and a concrete proposal for Codex review
instead of changing the guarantee yourself.

If no cause is established, submit a bounded diagnostic handoff and next reproducible
experiment; do not run full suites repeatedly hoping for green. If a fix is established,
verify focused cases first, then commit with PHANI465 <pgavara1@asu.edu> as sole author and
committer, no trailers and no history rewriting. Run exact-clean-commit Windows/native
full gates sequentially, same-run JUnit/structured skip validation, frozen HTTP/domain
exports/package/ML checks and both Windows browser suites if backend behavior changed.
Keep failures and cleanup evidence. No live model calls, paid fallback, final quality
evaluation, main merge, push, remote or deployment. Codex re-reviews before main advances.

Return exact SHA/base, diagnosis and negative controls, actual results (including failures),
safe evidence paths and cleanup. A passing focused rerun alone does not close this task.
