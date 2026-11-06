# Handoff: task/claude-g3d-p4-eval-plan

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
