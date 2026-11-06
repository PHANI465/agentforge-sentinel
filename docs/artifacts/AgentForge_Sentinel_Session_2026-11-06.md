# Sentinel checkpoint: November 6, 2026

**G3D-P2 is independently accepted and locally integrated at tested 5a1776be20a85124705a893c81b142384e31d67b.**
The candidate 61cc4b4 adds populated-workflow backup tests and runbook documentation;
production code is unchanged. [Review](../reviews/G3D-P2-61cc4b4.md) and
[complete integration evidence](../releases/G3D-P2-main-integration-2026-11-06.md).

- Independent candidate review: 92 focused tests plus four authority/baseline/corruption controls.
- Independent Windows then native Ubuntu full gates: 649 passed + one allowed skip each,
  six commands, 650-case same-run JUnit, frozen HTTP, packaged install and read-only ML.
- Seven workflows, 20 runs and 128 steps survive dump/restore with every row of all
  16 tables equal, original-token scoped traces, runtime authority, read-only overdue
  GETs, explicit recovery and one human-approved simulated action across retry.
- Browser/frontend checks were not rerun for tests/docs alone. P1's UI133 and browser19+10
  remain dated prior evidence, not a new G3D-P2 result.

Main carries the tested integration plus documentation publication; no extra full strict
run is claimed on the documentation-only publication HEAD. Full evidence belongs to
the exact clean integration worktrees. The approved 2700-second command cap and all
individual deadlines/skips are unchanged. Previous failures remain preserved.

## Next task

G3D-P3 is now assigned through [the three-role operator prompt](../prompts/CLAUDE_G3D_THREE_ROLE_OPERATOR.md),
using Claude Opus 5.5 / High in a new isolated task/worktree. Add explicit mode/adapter
selection, deterministic defaults and recorded restart settings; prove the real
runtime-role workflow and approval/replay path. Implementation has not started.
This dispatch changes documents only; no new application certification is claimed.
Codex reviews before integration. Measured agent/security evaluation, deeper analyst
capabilities and public operations follow; no live/final-case evaluation is assigned.

All financial data is synthetic and actions simulated. No provider call, final cases,
new spending, remote/push or deployment. Accepted worktrees and Cursor's exact seven
saved edits remain preserved. No test-owned database/API process remains on Windows or Ubuntu.
Fresh-cluster role provisioning, Linux browser, macOS, real CI, hosting and capacity
remain unverified. [Prior P1 checkpoint](AgentForge_Sentinel_Session_2026-11-05.md).

## Study the project

The [complete Markdown guide](AgentForge_Sentinel_Complete_Project_Study_Guide_2026-11-02.md)
and [Word guide](AgentForge_Sentinel_Complete_Project_Study_Guide_2026-11-02.docx) remain
dated study references. This checkpoint supersedes their pending integration/backup
status. [Current overview](AgentForge_Sentinel_Overview_and_Remaining_Work.md).
