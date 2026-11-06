# Handoff: task/claude-g3d-workflow-backup

- **Task and acceptance criteria:** G3D-P2, [CLAUDE_G3D_WORKFLOW_BACKUP.md](../prompts/CLAUDE_G3D_WORKFLOW_BACKUP.md). Prove backup and restore with populated multi-agent workflows, using content comparison, runtime authority, read-only traces and the human boundary.
- **Tool and worktree:** Claude Code (Opus 5.5 / High), in E:/PHANI/sentinel-wt/claude-g3d-workflow-backup.
- **Base:** published main d3b6affadad895ace3c03126dda13b864af767b1. It contains the accepted G3D-P1 integration aa5ee1e124c4163c124d33a9cb036fadf510b397.
- **Updated:** 2026-11-05, local time.
- **State:** ready for Codex review.
- **Code reference tested before this note:** the working tree on d3b6aff with the paths below. Exact-commit gates are reported in chat; a note cannot name its own commit.
- **Owned and changed paths:**
  - tests/test_workflow_backup_restore.py (new)
  - docs/runbooks/local-operations.md
  - this note

  tests/test_backup_restore.py is unchanged; the new module imports its `TABLES` and `counts`. No production src, scripts, contracts, migrations, grants, models, data, evals, UI, lockfiles, CI, skip policy, timeouts or fixtures changed.

## Baseline (what was missing)

- The existing C08 round trip stores **0 `agent_workflows` and 0 `agent_steps`**, because it uses the legacy single investigator. A temporary probe, not committed, asserting non-empty workflow tables fails with `0 > 0` (`.agent/g3d-p2/baseline-probe.log`).
- Its 16-table count check therefore could not show a faithful restored investigation. The new tests are a **new guard**, not a regression fix: the production code already supported the round trip.

## Implemented

- **`populate`.**
  - The operator issues sessions, one profile and one disclosure.
  - The production service and coordinator, as a runtime role (`ac.runtime_url`), seed and investigate six cases with deterministic adapters and FaultyRole faults: a completed recommendation (D01), challenge then abstain (D05), a provider failure then a repeat (D07), a crash then explicit recovery then a retry (D14, two workflows), a crash left `running` (D14), and another tenant's completed D01.
  - Exact counts: 7 workflows, 20 runs, 128 steps, 6 cases, 5 intents, 0 approvals, 0 actions.
- **Round-trip test.**
  - Every table's full row content (`to_jsonb`) on the restore equals the source.
  - Each source trace equals its restored trace, read over real uvicorn HTTP as the runtime role with the same token. Each case's default trace and every workflow by ID is compared, and `read_at` is checked separately.
  - `assert_matches_store` checks each restored projection against the restored rows.
  - Scope: other sessions, other tenants and other cases' workflow IDs get 404; no token gets 401.
  - The restored `running` workflow stays read-only at `recovery_due` across repeated GETs, with rows unchanged.
  - After restore, one real approval plus one key and a retry give exactly one simulated action, and recovery needs an explicit investigate.
  - Also covered: migrations, append-only triggers, the runtime role's least privilege after re-grant, and the source left untouched.
- **Negative-control test,** on isolated restored copies:
  - one step deleted (only in that copy's session, with `session_replication_role = replica`);
  - one workflow body altered, with all counts equal;
  - the archive restored without `agent_steps` TABLE DATA (via `--use-list`).

  Each is detected exactly. The damaged copy's trace also differs.
- **Runbook:** a "Populated workflow history (G3D-P2)" section with the verified procedure, scope and limits.

## Verified

- New module: 2 passed (`.agent/g3d-p2/focused-new.log`).
- **Mutation of the main test** (temporary probe, not committed): with restore replaced by a steps-absent restore, it fails at the counts check (`agent_steps` 0 != 128). With a restore that alters one workflow's `config`, it fails at the content check with counts equal (`.agent/g3d-p2/mutation-main-test.log`).
- Focused suites: workflow backup, C08 backup, trace API, agent workflow, db roles, local rollback drill and thin path. 92 passed (`.agent/g3d-p2/focused-suites.log`). Ruff is clean.
- Earlier drafts failed on my own errors, kept in `.agent/g3d-p2/first-draft.log` and `second-draft.log`. The first was a duplicate seed `external_id` (idempotency_conflict); the second was SQL `min(uuid)`. Both were fixed in the test, not by weakening a check.

## Not verified / gaps

- No live provider.
- `local_stack.py backup` and `restore` are not run as processes here; the rollback drill covers them.
- No browser rerun: the change is tests and docs only.
- No macOS, CI or hosting run.
- The restore keeps grants because the runtime role is cluster-global and is re-granted. A restore into a different cluster would need that role created first, and that is not tested.

## Next action

Codex reviews G3D-P2 on this commit before integration.

## Coordination and provenance

- The test reuses accepted helpers: tests/support/agent_cases.py, plus `LiveServer`, `assert_matches_store` and `wrong_count` from test_trace_api.py, and `TABLES` and `counts` from test_backup_restore.py. None of them was edited. All other code is original to this task. No credentials or raw reports are tracked, and the session token is never printed or written to a file.
- Accepted worktrees, the preserved P1 and R43 checkouts and evidence, and Cursor's seven saved edits are untouched.
