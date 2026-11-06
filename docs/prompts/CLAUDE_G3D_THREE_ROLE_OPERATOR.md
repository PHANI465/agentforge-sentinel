# G3D-P3: explicit three-role selection in the local operator helper

Delivered at2cdb3b7, independently accepted and integrated at tested495c7d3.
[Acceptance](../reviews/G3D-P3-2cdb3b7.md); [release](../releases/G3D-P3-main-integration-2026-11-06.md).
The original assignment below is historical; do not start another implementation.

Recommended coding assistant: **Claude Opus 5.5 / High**. This small configuration slice
crosses subprocess environment, persisted restart settings, case pins and process ownership.
These settings select the coding assistant; all Sentinel verification stays deterministic.

## Base, ownership and existing evidence

Read current task/coordination:AGENTS.md, STATUS and TASK_QUEUE with git show. G3D-P2 is
accepted at 61cc4b4 and integrated at tested 5a1776be20a85124705a893c81b142384e31d67b,
then published at bd91ca51aeefd42d268bcc462de7434c9e32e834. The current documentation
publication dispatches this task; it is not another application change or strict pass.

Create task/claude-g3d-three-role-operator in
E:/PHANI/sentinel-wt/claude-g3d-three-role-operator from current published main. Record
the exact base and confirm it contains 5a1776b and bd91ca5. One editor in this new worktree.
Leave accepted worktrees and Cursor's seven saved edits untouched. Codex owns review,
coordination and integration. Do not repeat accepted P1/P2 or R41-R43 corrections.

Read scripts/local_stack.py, scripts/smoke_thin_path.py, investigators.from_environment,
the workflow config/pins, existing local-stack/startup/rollback tests, the G3D-P2 review
and release record, and docs/runbooks/local-operations.md. No new orchestrator is needed.

## Deliver the missing launch option

The production API already accepts SENTINEL_INVESTIGATOR=three-role, with
SENTINEL_AGENT_ADAPTER=deterministic|claude-cli. local_stack.py currently permits only
deterministic|claude-cli for --investigator. Extend the helper, not the agent engine.

- Add `up --investigator three-role` and an explicit
  `--agent-adapter deterministic|claude-cli` option for three-role mode. Effective
  defaults remain the single deterministic investigator and rule scorer. In three-role
  mode the effective default adapter is deterministic, regardless of an inherited
  SENTINEL_AGENT_ADAPTER=claude-cli. Reject an explicitly supplied adapter for either
  single-investigator mode before creating state or starting a database/API.
- Pass the effective mode and adapter explicitly to the child, using the existing
  runtime URL, local-only mode, checkout import path, no-access-log and credential
  protections. Keep existing single claude-cli behaviour and auth isolation. Configuring
  claude-cli must require explicit operator selection; no quota exhaustion or error may
  trigger a paid/provider fallback. Do not run it during this task.
- Persist enough nonsecret effective configuration to reproduce the same investigator
  pins across smoke's API restart. Do not reread ambient adapter settings during restart.
  If an existing setting such as the model name affects a live config, either preserve
  that effective setting or refuse an inconsistent restart; do not change global CLI
  settings or introduce a new model-selection feature just for this task.
- Keep old single-mode state records readable. A missing new adapter field in a legacy
  single-mode record must not prevent status/down/restore. For an ambiguous three-role
  restart record, refuse rather than silently choose another configuration. Recovery
  must not require new configuration metadata merely to stop an owned process.
- Repeating up against an already-running owned API must not imply an investigator,
  adapter, scorer, database or port change took effect when it did not. Equal effective
  config may be idempotent; a mismatch must be clearly refused with the existing process
  left alone and its record intact. Require explicit down/up to change modes.
- Show effective investigator and, when relevant, adapter in safe launch/status text.
  No token, password, connection URL, provider credential or raw driver error is output.

Do not redesign state ownership, process discovery, SIGTERM/SIGKILL policy or recovery.
Keep pending-launch-before-inspection, healthy-owned readiness, identity checks, refused
foreign/reused/unresolved PIDs, database-stop ordering and recovery preservation intact.
Existing POSIX orphan and PID-check-to-signal limits remain disclosed, not solved here.

## Prove the operator path works

Use a fresh task-owned stack and random free ports, the real production API and
PostgreSQL. Operator provisions/migrates/grants; the API does case work as the restricted
runtime role. Use existing native lifecycle helpers without changing their implementation.

1. Baseline default and legacy single-investigator startup/smoke/restart remain valid.
2. New rule + three-role + deterministic path ingests synthetic transactions, completes
   a real persisted workflow and returns its trace. Assert actual completed roles,
   ordered persisted steps, config pins, server-built intent and trace state; a healthy
   port or parser-only test is not end-to-end proof.
3. Separate investigate and execute phases: zero approvals/actions before the approval
   phase; an explicit synthetic approval plus one execution key produces exactly one
   simulated action across a retry. This is an automated operator smoke, not a claim
   that a human clicked the UI. Preserve the real app's human authorization boundary.
4. Restart between investigation and approval/execution through the helper's existing
   smoke --restart-api path. The effective adapter and case pins survive; the original
   workflow/trace stays readable and execution/replay succeeds without reinvestigation.
5. Prove an inherited live adapter cannot activate a provider in either default mode
   or implicit-adapter three-role mode. Cover explicit invalid combinations, old state
   compatibility and running-config mismatch refusal. Stub provider submission/auth as
   needed for config-only tests; no real account or provider is contacted.

Keep `smoke` rule-only; model-mode ingestion/profile provisioning and model benchmark
results are separate existing features. The start option must not break scorer selection.
Make only narrow smoke output/parsing changes if the three-role response needs them;
do not assume the last role's run is the investigator, or freeze legacy run/audit counts
as the expected three-role counts. Use real persisted/HTTP data for new assertions.

Write meaningful failing-first regressions, explaining whether each baseline failure
is a missing CLI option or a reproduced configuration bug. Keep existing controls and
assertions. One deliberately broken adapter/restart propagation must be caught by the
new tests; do not count import/setup errors as proof of the intended regression.

## Owned files and verification

Own scripts/local_stack.py, a new tests/test_local_stack_three_role.py, narrow compatible
updates to existing test_local_stack/startup/rollback tests if genuinely needed,
docs/runbooks/local-operations.md and your branch handoff. Optional narrow paths:
scripts/smoke_thin_path.py and SETUP.md only for the supported helper path/documentation.
Central STATUS/TASK_QUEUE/checkpoints remain Codex-owned.

Do not edit production src/, contracts, migrations/grants, agent/model/evaluation
protocols or fixtures, data_pipeline/ml/evals assets, UI/browser harnesses, dependencies,
locks, CI, skip allowlist or checker timeouts. Escalate a concrete unsupported behaviour
with code/evidence instead of broadening those paths. No fresh-cluster restore expansion.

Run focused helper/startup/rollback and new integration tests, then commit explicit owned
paths. On the final clean commit run complete Windows then native Ubuntu gates sequentially:
six strict commands with the approved 2700-second per-command cap, JUnit from that same
pytest run, exact structured skip validation, frozen HTTP export, packaged install and
read-only ML reproduce. No new skip or reduced assertions; preserve and diagnose failures.
No frontend/browser rerun solely for helper/tests/docs changes unless evidence justifies
one. State clearly what was not run. Verify task-owned cleanup; leave unrelated services.

All new commits: PHANI465 <pgavara1@asu.edu> as sole author AND committer, no trailers,
history rewriting or global Git changes. Return exact base/SHA, actual mode/restart
proof, failing-first/negative-control evidence, checks, safe output and cleanup limits.
No merge into main, remote/push, deployment, live provider, final-case evaluation or
new spending. Codex reviews before integration. After this small helper milestone,
measured agent/security evaluation is the next substantive workstream.
