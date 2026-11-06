# Handoff: task/claude-g3d-p4-eval-plan

## R44/R45 revision (latest)

- **Task:** [CLAUDE_G3DP4_PLAN_REVIEW_FIXES.md](../prompts/CLAUDE_G3DP4_PLAN_REVIEW_FIXES.md), following review G3D-P4-3366edf. Both live on main 7ddec82 and are not merged into this branch. This is a new commit on top of preserved 3366edf, with no rewrite.
- **State:** ready for Codex re-review. Documentation only.
- **Changed paths:** the plan document and this note.
- **R44 (timing and measurements):**
  - The runner's monotonic timing is now named **request latency**.
  - The 150 s workflow-elapsed gate is **not measured** in this pilot and not demonstrated. No persisted field and no runner-only exact timing is promised; an exact observer is deferred to a separately reviewed design.
  - `StepRecord.elapsed_ms` is described as cumulative from `t0`, and the terminal `0` as a marker.
  - Paired `role_started` and `role_completed`/`role_failed` markers give a labelled *recorded step interval*, not provider latency. The caveats for missing or failed markers and pre-submission failures are stated.
  - The worst-case pass durations are removed. A time-quantities table now keeps apart:
    - C1's 60 + 2 s caller wait;
    - the CLI auth (15 s) and call (60 s) subprocess lifetimes;
    - C2's 150 s coordinator budget, with 45 + 2 s per role;
    - late worker lifetimes;
    - request latency;
    - end-to-end duration, which is unknown.
  - `capacity.snapshot()` (`calls`, `peak_calls`) is described as existing in memory but missing from reports.
- **R45 (stopping keeps the result):**
  - A hold on D03, D04 or D11 is a completed, **unacceptable** disposition: scored 0/1, retained with its attempt, latency and usage, and never excluded, relabelled or replaced by a rerun.
  - Stopping makes the pass incomplete and lists the remaining pairs as not attempted. Quality failures are distinguished from typed request failures.
  - For D11 the cause is unestablished and the injection-related gate is not demonstrated. D02 is not a matched control. The external_id-only scope and the unobserved role inputs are explicit. No control fixture was added and the catalog is unchanged.
- **Decisions applied:**
  - one pass, with no pre-approved repeat and no live permission;
  - P4a first, under a separate dispatch;
  - the fault-applying runner and production instrumentation deferred.
- **Operational clarifications:**
  - **Allowance:** the "30" is defined as application adapter/CLI-invocation reservations (1 per C1, 5 per C2, reserved before each run). It is not a provider-request or billing cap. Separate accounting categories are listed, with unknowns kept as unknown.
  - **Commands:** they are marked as templates until P4a supplies tested orchestration. They use:
    - a new pilot-owned worktree, refusing a pre-existing `.agent/devdb`;
    - a verified free port;
    - a created output directory;
    - nested JSON validation (`record.status`, `record.authorities.runtime_verified`, `comparators.*.counts.dispositions`);
    - stopping and dropping only verified pilot resources.
  - **Exports and authority:** exports are read-only, scoped and private, run as the runtime role, which has SELECT on all 16 tables. Operator authority is limited to provisioning and the drop. Evaluator data enters offline scoring only.
- **Checked:**
  - Relative links: the three frozen-doc links resolve. The review link resolves on main 7ddec82, not in this branch (stated in the plan).
  - `src`, `scripts`, `tests`, `docs/evals` and `contracts` are byte-identical to fac96b3 (`git diff --quiet`).
  - Code facts were re-read: Deadline after admission, `Run.step`, the terminal step, `INVESTIGATOR_GRACE_SECONDS` = 2, the auth-status timeout of 15 s, `capacity.snapshot`, `role_invocations` increments after the start record, the `devdb` directory, and `RUNTIME_PRIVILEGES`.
- **Not run:** nothing executed. No provider, auth or database command, no gates (documentation only), and no final cases.

## Original proposal (3366edf)

- **Task and acceptance criteria:** prepare the G3D-P4 development evaluation plan (C0/C1/C2 pilot) from current main, for Codex review. Planning only: no provider calls, no final cases, no code changes, no spending, no deployment and no push.
- **Tool and worktree:** Claude Code (Opus 5.5), in E:/PHANI/sentinel-wt/claude-g3d-p4-eval-plan.
- **Base:** main fac96b3fc1f7d3dadd69b25d623b9473a8731b4f.
- **Updated:** 2026-11-06, local time.
- **State:** ready for Codex review.
- **Code reference:** documentation only. No code, protocol, case, runner, test or coordination file changed.
- **Changed paths:**
  - docs/artifacts/AgentForge_Sentinel_G3D-P4_Development_Evaluation_Plan_2026-11-06.md (new)
  - this note

## Implemented

- The plan document. It covers:
  - scope and limits;
  - the pilot shape and call bounds;
  - exact commands, step by step;
  - stop conditions;
  - fault scenarios the runner doesn't apply;
  - missing measurements;
  - the human scoring procedure;
  - the proposed P4a–P4d sequence;
  - the open decisions.

## Verified

- Facts were read from main fac96b3: protocol-v1, the dev case catalog and JSON, the evaluator runbook, `scripts/agent_eval.py`, `sentinel.agents` limits, adapters and coordinator, and `sentinel.investigators`.
- Checks I made in the code:
  - C1 timeout is 60 s, and C2's role timeout is 45 s with a 150 s deadline, ≤5 invocations and ≤2 outstanding calls.
  - The `workflow_terminated` step records `elapsed_ms=0`.
  - Role inputs are not persisted.
  - Late workers are only a log event.
  - The runner's model alias is fixed.

## Not verified / gaps

- Nothing was run. No backend gate was run for this documentation-only commit. No live, final-case or browser activity took place.

## Next action

Codex reviews the plan and decides on §9 before assigning P4a.

## Coordination and provenance

- Central STATUS, TASK_QUEUE and prompts are left to Codex. Accepted worktrees and Cursor's seven edits are untouched.
