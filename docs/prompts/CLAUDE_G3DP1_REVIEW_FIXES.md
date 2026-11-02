# G3D-P1 R41/R42: safe failures and truthful evaluator reporting

Recommended coding assistant: **Claude Opus 5.5 / High**. Exception/transaction boundaries
and partial-result provenance require care; this is a focused runner correction, not a
database-role redesign. Sentinel comparators stay deterministic, no --allow-live.

## Exact continuation

Read current task/coordination:AGENTS.md, STATUS/TASK_QUEUE and
docs/reviews/G3D-P1-5811a29.md with git show. Continue the EXISTING
E:/PHANI/sentinel-wt/claude-g3d-evaluator-prep, task/claude-g3d-evaluator-prep, from exact
**5811a29fef9ccc5678ca6aa2f5efe0f2a6a6df78**. Keep the current passing authority split,
read-only checks and all existing tests. No new worktree, reset/rebase/amend or repeated
original implementation. Main's runner is older; the named candidate is the task base.

## R41: account safely for failures at the actual boundaries

Protect connection-established preflight catalog queries as well as initial connect;
expected driver errors become safe typed refusal before comparator/case construction.
Protect session provisioning, authentication, ingestion, investigate and diagnostic usage
reads without dropping previously completed work or exposing a raw exception/traceback.

A real subprocess probe installs a test-owned trigger that fails the SECOND session
insert. The first request already completed, but 5811a29 prints a canary-bearing server
traceback and loses its report. Another probe makes post-result usage reading fail after
a genuine disposition; it escapes instead of retaining the known outcome. A third injects
an OperationalError into preflight execute and it escapes the typed refusal boundary.

Preserve protocol-v1: an attempt is one investigate request. Keep failed setup separate
from requests that never started; no invented attempt/completion or zero request latency.
Retain prior completed results and mark an incomplete/failed run and phases honestly if
processing stops. A failed telemetry lookup must leave the committed outcome intact,
with explicitly unavailable/unknown provenance. Do not retry silently or switch authority.
Use code-only/safe errors; no raw driver/provider text, URLs, credentials or tokens.
Do not swallow KeyboardInterrupt/SystemExit or replace the issue with a blanket catch
that hides all partial data. Choose/document a clear CLI exit and partial-output policy
within the existing development JSON/report contract; no frozen protocol edits.

## R42: unknown stays unknown

The union of row.get(usage_sources, ()) drops rows with missing provenance. One reported
row plus an error row with no provenance yields adapter_reported for the whole run today.
Treat missing/unavailable provenance explicitly as unknown. Keep complete reported usage
and explicitly unknown usage controls. No numeric token or money field is requested.

Also address the small duplicate-name input guard: --comparators C0,C0 currently executes
twice but overwrites report[C0], reporting one attempt. Prefer refusing duplicates before
any comparator/provider construction; alternatively preserve every executed row honestly.
This does not require a report redesign or a new feature.

## Ownership and tests

Own scripts/agent_eval.py, tests/test_agent_eval_privileges.py (or one focused new evaluator
failure test module), docs/evals/agents/evaluator-runbook.md and your branch handoff. No
production src/API/roles/grants/schema, UI, dependencies, locks, frozen case/protocol/model/
evaluation data, lifecycle helper, CI/skip policy, timeouts or central coordination edits.
Cursor's seven saved changes and all accepted/review worktrees remain untouched.

Write maintained failing-first cases against 5811a29 for each real boundary and report
semantics; use actual disposable Postgres/real service, test-owned triggers or narrow
query faults where appropriate. Do not feed evaluator expectations into runtime inputs.
Cover retained earlier successes, setup-not-request accounting, no driver/canary leak,
post-result telemetry failure, missing/unknown/fully reported provenance and duplicate
names refused without sessions/cases. Existing operator/runtime writer proof must pass.

Original seven independent probes and reports are in canonical ignored
.agent/g3d-p1-review/5811a29/ and E:/PHANI/Interview/tmp/test_codex_g3d_eval_review.py.
On both platforms five assertion failures/two controls are reproduced; these are not
import failures. Port their useful meaning into maintained tests and document any JSON
shape changes; do not weaken assertions merely to accommodate the implementation.

No new full run on unchanged 5811a29 is needed; both old full records already verify
620+one allowed skip. After focused tests pass, commit new changes as PHANI465
<pgavara1@asu.edu>, sole author AND committer, no trailers/history rewriting. Run required
exact-clean-commit Windows/native gates sequentially, same-run JUnit/exact skip validation,
frozen exports and read-only ML reproduction, and repeat the deterministic development
smoke on fresh databases. No browser rerun is needed for unchanged production/UI; report
that scope rather than claiming a pass. Preserve/diagnose any failure and normal cleanup.

Return exact new SHA/base, failing-first proof, actual results including limits, the safe
partial-failure policy and evidence paths. No merge to main, remote/push/deployment, live
provider, final cases or new paid usage. Codex re-reviews before the next G3D step. Ask a
specific clarification if the frozen protocol genuinely leaves a required decision open;
do not invent a new metric denominator or broaden this task into a full evaluator.
