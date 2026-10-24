Completed: U02 is accepted at 5f2855553ac0a445d96914730a89fc3722682830 with R21/R22 resolved. See docs/reviews/5f28555.md and the current docs/prompts/CURSOR_UI.md dispatcher from latest coordination. The instructions below are scope/history; do not repeat completed fixes.

# Cursor U02: remaining R21 entry-point wiring

Continue task/cursor-browser-e2e in E:/PHANI/sentinel-wt/cursor-browser-e2e. Reviewed bb318a1d283b1802e6f87e484393b50bf4a7673b still has R21 changes requested. Preserve all newer work, the U01+C02 dependency base, duplicate-activation guard, R22 scanner/failure-artifact fixes and existing real flows. Do not restart U01/U02 or merge C05/main.

Read from current coordination:
    git show task/coordination:AGENTS.md
    git show task/coordination:docs/reviews/bb318a1.md
    git show task/coordination:docs/prompts/CURSOR_U02_R21_FOLLOWUP.md
    git show task/coordination:docs/TASK_QUEUE.md

The 20 helper checks pass, but the entry-point wiring differs:
- serve.mjs:106 directly terminates when viteIdentity is missing, bypassing positive verification; the startup-failure path reaches it. Do not kill on absent/unavailable identity. Preserve raw child PID, manifest/stack/run details and the reason as recovery metadata without making that metadata permission to terminate.
- playwright.config.ts:chosenRun adopts a leftover current-run.json ID. Use an invocation-owned identity shared deliberately with its workers, or fail startup when previous state needs recovery. A stale file cannot make an old runtime authoritative for a new invocation. Preserve previous/recovery state safely rather than blindly overwriting or stopping it.

Write failing-first, fully intercepted tests of the actual wrapper and config entry points. Prove missing identity sends no taskkill and retains recovery; a new invocation with stale state never adopts authority to kill/stop the old run; verified owned identity still permits exact cleanup; already-exited/reused/foreign processes remain untouched. The existing planning-helper tests alone are insufficient. Reviewer probe: E:/PHANI/Interview/tmp/u02_bb318_entrypoint_probe.cjs (read as evidence). All its process/filesystem operations were intercepted.

Keep R22 retained secrets until scanning completes, exact private-state exclusions, fail-closed errors and the genuine expected post-login failure artifact. After safe regressions pass, run the real browser/API/disposable-Postgres suite and inspect actual owned-process/resource cleanup and failure recovery. No live provider, unrelated process stop or external test database. Use this worktree's environment and accepted C02's 900-second checker timeout.

Own web/, docs/ui/ and the task handoff; no backend/contracts/migration/Python-dependency/accepted tests/support edits. Update the handoff/docs, stage explicit owned paths, commit, then run final checks after that commit. Report exact SHA/counts, actual entry-point regressions, browser/artifact cleanup and limits. Codex keeps central STATUS/TASK_QUEUE.

Claude independently starts C07 from accepted C04 using its separate backend worktree. Leave that work alone; U03 waits for an explicitly accepted C07 HTTP dependency. Main remains unchanged.
