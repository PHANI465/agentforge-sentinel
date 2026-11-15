# Resume Sentinel from committed context

Updated November 15, 2026. This is the durable entry point for a new Codex or Claude chat.
Files supply context; they do not automatically synchronize sessions, authorize extra
work or preserve a killed process. Inspect actual Git and job/recovery state before acting.

## Read in this order

1. Current user instruction and AGENTS.md from the named coordination reference.
2. [STATUS](STATUS.md) and [TASK_QUEUE](TASK_QUEUE.md): current acceptance and task ownership.
3. [Decision ledger](decisions/PROJECT_DECISION_LEDGER.md): confirmed choices, sources,
   alternatives, implementation state and supersession. Add new decisions here.
4. [Current checkpoint](artifacts/AgentForge_Sentinel_Session_2026-11-10.md) and the
   relevant branch handoff/review at its named SHA. Never treat author tests as acceptance.
5. [Complete project guide](artifacts/AgentForge_Sentinel_Complete_Project_Study_Guide_2026-11-08.md)
   or [HTML](artifacts/AgentForge_Sentinel_Complete_Project_Study_Guide_2026-11-08.html)
   for pipeline, implementation, examples and completed/remaining stages.

## Current position

- The browser document-insights source is ready for GitHub at verified implementation
  commit `a56f104`. The production site still uses the preceding deployment.
  [Release verification](releases/DOCUMENT-INSIGHTS-GITHUB.md) and
  [user guide](ui/PUBLIC-DOCUMENT-INSIGHTS.md).

- The public site offers browser PDF explanations, a synthetic p1 dataset download and the recorded fraud case. The same deterministic workbench is live on Vercel for scoped synthetic cases. [Public deployment and checks](releases/PUBLIC-SITE-VERCEL-2026-11-15.md)
- DOC01 Part C is integrated locally at verified source commit `3dfbc00`. Sessions with the document grant can upload local public or synthetic files and review extraction results in the workbench. [Part C release](releases/DOC01-Part-C-main-integration-2026-11-14.md)
- DOC01 Part B integrated the HTTP v1.3 API in `e51f47a`. [Part B release](releases/DOC01-Part-B-main-integration-2026-11-13.md)
- The casework and scoring paths retain their tested 871e31d baseline. Main also includes the accepted DOC01 Part A worker through source merge `662572e`; its integration checks are recorded separately.
- DOC01 Part A [local worker is accepted](reviews/DOC01-8f7bd87.md) at `8f7bd87` and integrated in source merge `662572e`; [release evidence](releases/DOC01-Part-A-main-integration-2026-11-12.md). The [Part B backend assignment](prompts/CLAUDE_DOC01_PART_B_BACKEND.md) is delivered history.
- AN01-M1 is integrated at verified merge `1427b2c`. The full-size grid and provisional limits remain open. [Integration evidence](releases/AN01-M1-main-integration-2026-11-14.md)
- DOC01 Part A was delivered at `cecccad`; its [first review](reviews/DOC01-cecccad.md) requested R58/R59. The original [two-finding correction](prompts/CLAUDE_DOC01_REVIEW_FIXES.md) is delivered history.
- DOC01 re-review at `69b51fe` [closes R59](reviews/DOC01-69b51fe.md); its [unreadable-member correction](prompts/CLAUDE_DOC01_R58_FOLLOWUP.md) is delivered history.
- DOC01 `7ec46ae` [required one R58 group-race fix](reviews/DOC01-7ec46ae.md). Its [correction prompt](prompts/CLAUDE_DOC01_R58_RACE_FOLLOWUP.md) is delivered history.
- Private GitHub repo: https://github.com/PHANI465/agentforge-sentinel. Only accepted main
  is published; Actions disabled. No force/mirror/all-branch push or private data upload.
- ULB dataset is acquired privately, not trained. p1 and protected final cases unchanged.
- Small Claude Pro and Codex/ChatGPT connectivity smokes passed. No live quality study,
  Cursor inference or app provider configuration change is implied.
- [Original DOC01 handoff](prompts/CLAUDE_EXPANSION_AFTER_M1.md) is delivered
  history; use the current review and correction dispatch above.

## Safe new-chat prompt

Read task/coordination:AGENTS.md, docs/START_HERE.md, docs/STATUS.md,
docs/TASK_QUEUE.md and docs/decisions/PROJECT_DECISION_LEDGER.md using git show.
Inspect main and the named task worktree read-only, resolve exact HEAD/status and read
the current review/branch handoff. Summarize completed, changes-requested and unassigned
work. Continue only the current concrete assignment; do not restart an older prompt.

Future commits use PHANI465 <pgavara1@asu.edu> as sole author and committer. Preserve
Cursor's seven edits, accepted worktrees, failed reports, frozen p1/contracts and source
credit. Keep heavy jobs sequential. An interruption requires ownership/cleanup checks,
not blind lock deletion or an assumed pass.
