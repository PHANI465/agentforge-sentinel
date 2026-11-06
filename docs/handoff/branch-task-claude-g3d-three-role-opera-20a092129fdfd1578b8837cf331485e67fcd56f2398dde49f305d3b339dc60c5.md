# Handoff: task/claude-g3d-three-role-operator

- **Task and acceptance criteria:** G3D-P3, [CLAUDE_G3D_THREE_ROLE_OPERATOR.md](../prompts/CLAUDE_G3D_THREE_ROLE_OPERATOR.md). Add explicit three-role selection to the local operator helper, with restart consistency and real deterministic end-to-end proof.
- **Tool and worktree:** Claude Code (Opus 5.5 / High), in E:/PHANI/sentinel-wt/claude-g3d-three-role-operator.
- **Base:** published main f45c70347b8969d8bb8579ce95e644928d70611e. It contains integration 5a1776b and publication bd91ca5.
- **Updated:** 2026-11-06, local time.
- **State:** ready for Codex review.
- **Code reference tested before this note:** the working tree on f45c703 with the paths below. Exact-commit gates are reported in chat; a note cannot name its own commit.
- **Owned and changed paths:**
  - scripts/local_stack.py
  - scripts/smoke_thin_path.py (output only)
  - tests/test_local_stack_three_role.py (new)
  - tests/test_local_stack_startup.py (one call updated to the new `start_api` config argument)
  - docs/runbooks/local-operations.md
  - this note

  No production src, contracts, migrations, grants, agent/model/eval protocols or fixtures, data, ml, evals, UI, browser harnesses, dependencies, locks, CI, skip allowlist or timeouts changed.

## Implemented

- **`up --investigator three-role` and `--agent-adapter deterministic|claude-cli`.**
  - In three-role mode the adapter is deterministic unless given explicitly.
  - An adapter with a single investigator is refused before any state, database or API exists.
  - Defaults stay deterministic + rule.
- **`requested_config` / `child_environment`.**
  - The child API gets `SENTINEL_INVESTIGATOR` (plus `SENTINEL_AGENT_ADAPTER` for three-role, and `SENTINEL_CLAUDE_MODEL` only for a live configuration) explicitly.
  - Inherited values of those three variables are stripped.
  - The runtime URL, local mode, checkout `PYTHONPATH` and no-access-log are unchanged. Other environment, including Claude auth isolation, is untouched.
- **The live model** that claude-cli would read (ambient `SENTINEL_CLAUDE_MODEL`, default sonnet) is captured at `up` and recorded. A restart reuses it, so live pins stay the same.
- **The API record** stores `investigator`, `adapter` and `claude_model`. These are nonsecret and also written into the pending launch record.
- **`recorded_config`.**
  - A restart (`smoke --restart-api`) uses only the record.
  - These records refuse restart before any smoke stage, stop or launch: a three-role record without an adapter, a live record without a model, or an adapter without three-role.
  - Pre-P3 deterministic records are accepted.
  - `status` and `down` do not depend on the new fields.
- **`running_matches`.** `up` against an owned running API refuses any difference in investigator, adapter, live model, scorer, database, API port or database port. It refuses before touching the database, and leaves the process and record untouched. An equal request stays idempotent.
- **Launch and `status` text** name the effective investigator, adapter and model. No token, URL, password or driver text is printed.
- **smoke_thin_path.**
  - It lists every role run and reports the run that produced the finding, not the last one.
  - It prints a trace summary and the counts before approval.
  - Model mode and rule-only `smoke` are unchanged.

## Verified

- **Failing first on f45c703** (`.agent/g3d-p3/failing-first-f45c703.log`): the new module on the base scripts gives 17 failed.
  - Missing CLI option (4): the adapter-refusal tests ×2 (argparse exit 2), the adapter-mismatch case, and the three-role E2E (`invalid choice: 'three-role'`).
  - Missing new display or record fields (2): the legacy status text, and the default E2E launch text. The default-mode behaviour itself is a control.
  - **Reproduced configuration bugs (11):**
    - Restart environment ×3: the base passes the ambient `SENTINEL_AGENT_ADAPTER=claude-cli` and `SENTINEL_CLAUDE_MODEL=opus` to the restarted API. A three-role record would restart live, and a claude-cli record would change model.
    - Ambiguous records ×3: the base runs the smoke stage and restart instead of refusing.
    - Running mismatch ×5: the base proceeds into the database ("the database was touched") and would report "already running" for a different investigator, live mode, scorer, database or port.
- **With the fix:** 17 passed (`.agent/g3d-p3/fixed-focused.log`).
- **Mutation** (restart rereads the ambient adapter): 6 tests fail (`.agent/g3d-p3/mutation-restart-rereads-adapter.log`). They are the restart-environment tests, the ambiguous-record tests, and the real-stack three-role E2E, where the restart reported `adapter claude-cli`.
- **Focused suites:** the new module, local_stack, startup, rollback drill, investigators and agent workflow. 87 passed, plus 1 allowed live-Claude skip (`.agent/g3d-p3/focused-suites.log`). Ruff is clean.
- **E2E facts** (real stack, runtime role, random ports, hostile inherited environment, nonexistent Claude executable):
  - The three-role case completes evidence_analyst, investigator and reviewer, with contiguous step seq ending in `workflow_terminated`.
  - Case pins equal the workflow config. The server-built intent operation equals the disposition operation.
  - There are 0 approvals and 0 actions before the approval phase.
  - The trace is unchanged across `smoke --restart-api`, and the first case executes once, with the retry replayed and no new workflow or run.
  - A case created after the restart has identical agent and tool pins.
  - Default mode shows the single investigator, no workflows, and one action.

## Not verified / gaps

- `--agent-adapter claude-cli` and `--investigator claude-cli` were never run against a provider. Their env propagation is covered by intercepted launches only.
- No browser or frontend rerun: helper, test and doc changes only.
- POSIX orphan and PID-check-to-signal limits are unchanged. Native Ubuntu runs the backend gate only.
- When the API is down, a different `--db-port` with a recorded cluster still reuses the recorded port. That behaviour is unchanged.

## Next action

Codex reviews G3D-P3 on this commit before integration.

## Coordination and provenance

- All code is original to this task. It reuses the existing helper lifecycle and the smoke script. No credentials or raw reports are tracked.
- Accepted worktrees, the preserved P1, R43 and P2 checkouts and evidence, and Cursor's seven saved edits are untouched.
