# Resume Sentinel from committed context

Updated November 12, 2026. This is the durable entry point for a new Codex or Claude chat.
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

- Accepted application/tooling remains exact tested 871e31d plus later documentation.
- AN01-M1 measurement prototype is independently accepted at exact `28dfcef` for its reviewed behavior; R56 is closed. [Review](reviews/AN01-M1-28dfcef.md). It remains unmerged, and the tiny timing controls are not demonstrated. The prior b54de1a review is preserved as history.
- DOC01 Part A was delivered at `cecccad` and is [changes-requested](reviews/DOC01-cecccad.md) for R58/R59. The [current Claude correction](prompts/CLAUDE_DOC01_REVIEW_FIXES.md) continues its existing branch. No document upload/API/UI has been accepted or merged.
- Private GitHub repo: https://github.com/PHANI465/agentforge-sentinel. Only accepted main
  is published; Actions disabled. No force/mirror/all-branch push or private data upload.
- ULB dataset is acquired privately, not trained. p1 and protected final cases unchanged.
- Small Claude Pro and Codex/ChatGPT connectivity smokes passed. No live quality study,
  Cursor inference or app provider configuration change is implied.
- New local document feedback, automated dev review and readable metrics are approved
  directions with research/proposals. No new production feature is implemented here.
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
