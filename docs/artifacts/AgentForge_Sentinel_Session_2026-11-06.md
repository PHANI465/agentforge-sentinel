# Sentinel checkpoint: November 6, 2026

**G3D-P3 accepted and locally integrated at tested 495c7d33424054d27d68d08004191d4be37adaf9.**
The operator helper now offers explicit three-role/adapter selection and consistent
restart settings, while keeping deterministic single/rule defaults. [Review](../reviews/G3D-P3-2cdb3b7.md)
and [release evidence](../releases/G3D-P3-main-integration-2026-11-06.md).

- Independent review:32 helper/startup/rollback tests plus nine configuration probes pass.
- Independent Windows then native full backend gates:666 passed + one allowed skip
  each; all six commands, same-run667-case JUnit, frozen HTTP, package and read-only ML.
- Real stacks prove roles/steps/pins/trace survive API restart and exactly one simulated
  action follows explicit approval/execution and retry. Implicit settings cannot turn
  on a live adapter. Live helper modes are configuration-tested only.
- Main includes this tested integration plus documentation publication. No extra full
  strict pass is claimed on the documentation-only publication HEAD. Browser/frontend
  were not rerun; P1's UI133 and19+10 browser results remain dated prior evidence.

G3D-P2 remains accepted at5a1776b: seven workflows,20 runs and128 steps survive real
backup/restore with all16 tables' content equal, scope/audit/approval/replay checks.
[P2 release](../releases/G3D-P2-main-integration-2026-11-06.md). G3D-P1's restricted-role
evaluator and error/usage accounting are integrated. R41-R43 remain closed.

## Next substantive work

Plan measured agent/security comparisons under the frozen protocol: deterministic,
one-live and three-role systems; evidence quality, errors/failures, latency and honestly
reported usage. Development pilots and a protected final evaluation are distinct.
No live provider or final-case generation/inspection is assigned by this integration.
Then deepen financial analytics and prepare public demonstration/operations.

The2700-second verification-command cap and individual deadlines/skips are unchanged.
Original failures, accepted worktrees and Cursor's seven edits are preserved. No test-owned
PG/API remains. Ordinary Ubuntu operator startup/restart/shutdown is now tested; orphan
and PID-check-to-signal limits remain. Fresh-cluster role provisioning, Linux browsers,
macOS, real CI, hosting and capacity remain unverified. No new spending, remote/push
or deployment. All financial data is synthetic and all actions simulated.

## Study the project

[Complete Markdown guide](AgentForge_Sentinel_Complete_Project_Study_Guide_2026-11-02.md)
and [Word guide](AgentForge_Sentinel_Complete_Project_Study_Guide_2026-11-02.docx) remain
dated study references. This checkpoint supersedes their pending evaluator/backup/trace
status. [Current overview and remaining work](AgentForge_Sentinel_Overview_and_Remaining_Work.md).
