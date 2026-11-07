# Claude parallel work batch: November6,2026

The owner explicitly requested remaining Claude work with simultaneous agents where
useful. Use the existing Claude Code subagent/team capability **if available on the
current subscription**, without installing an agent framework, enabling paid overage
or changing global settings. If unavailable, execute the same scoped tasks sequentially.

Coordinator and agents: **Opus5.5 / High**. Use at most three worker agents plus the
coordinator, and fewer if memory/context pressure requires it. Do not split into more
agents merely to spend quota. Coding-assistant usage is authorized; Sentinel's actual
providers/auth/final-case evaluations remain disabled.

## First read and preserve delivered work

Read current task/coordination:AGENTS.md, STATUS/TASK_QUEUE and
[delivery intake](../handoff/P4a-AN01-delivery-intake-2026-11-06.md).
P4a 96293da1a3403bb1d9bf9eb7c669354b2089c5be and AN01 dd6518d85a864a4742f75b29b66beaa656dca085 are **review-pending**, not accepted.
Do not repeat those completed assignments, merge P4a into main, or modify their clean
author worktrees. Record each worker's exact base and owned paths before starting.
Current main's application is still tested G3D-P3 at495c7d3 plus docs publications.

## Three disjoint worker assignments

| Worker | Task | Base and ownership |
| --- | --- | --- |
| A | [AN01-r2 contract refinement](CLAUDE_AN01_DESIGN_REFINEMENT.md) | exact dd6518d, new design-r2 worktree; docs/analytics only |
| B | [PERF01 local capacity tool](CLAUDE_PERF01_LOCAL_CAPACITY.md) | current accepted main; new benchmark script/tests/docs |
| C | [DEMO01 recorded replay](CLAUDE_DEMO01_RECORDED_REPLAY.md) | current accepted main; new demo/ generator/tests/docs |

They may read/specify/code in parallel. Each has a named branch/worktree and its own
locked dev+ml environment; clear inherited VIRTUAL_ENV where necessary and verify
sentinel.__file__ belongs to that checkout before a real run. Pass workers their scoped
assignment and Git references, not the entire old chat transcript. No agent
edits another's checkout or central STATUS/TASK_QUEUE. No analytics backend/UI is
assigned until Codex accepts the refined contract. Do not invent APIs to unblock it.
P4a review and live P4b are not dependencies of PERF01 or DEMO01.

## One heavy-execution slot for the whole laptop

The coordinator schedules **only one** real DB/load/browser/full-gate job at a time,
including Windows and WSL. Workers must request the slot and wait for the coordinator
to release it; do not run memory-heavy tests in parallel. Pure docs/arithmetic/unit
work may continue in other worktrees. Use existing RAM history to choose fewer jobs,
not higher limits or skipped checks. Keep a private ignored queue/evidence record,
never tokens or command-line credentials. Never stop a peer's processes by name.

Suggested execution order after coding: PERF01 focused/real run, then DEMO01 capture/
browser QA, then final combined certification. Keep failures, diagnose them and record
justified reruns; do not loop until green. Stop affected work when subscription quota
ends, without paid fallback; leave a clean handoff and continue only truly independent
work that the available tools can perform.

## Combined preview for one final certification

Workers commit explicit owned paths, run meaningful focused checks and hand off exact
SHAs/gaps. They do **not** each run the entire six-command gate. The coordinator alone
creates task/claude-parallel-batch-preview at
E:/PHANI/sentinel-wt/claude-parallel-batch-preview from the current dispatch main SHA,
then explicitly merges only this batch's clean AN01-r2, PERF01 and DEMO01 commits.
This authorizes a **task-branch preview only**, not main integration or acceptance.
Do not include P4a96293da, other unreviewed branches, modified frozen assets or shared
files outside the worker ownership lists. If conflicts/scope changes are material,
hand off concrete evidence rather than guessing a new API or weakening a check.

On the final clean preview commit run full Windows then native Ubuntu backend gates
sequentially: all six commands, same-run JUnit/exact skip validation, frozen HTTP,
packaged install and read-only ML reproduce. Keep2700s per command, individual waits,
assertions and skip rules unchanged. Run the new benchmark/demo focused checks against
that combined source too. The existing web app/harness is unchanged; do not rerun its
full browser suites without a concrete reason. DEMO01's own browser QA is separate.
Clearly attribute full gates to the preview SHA, not the worker branch heads. No
full-gate pass is invented if a worker or environment remains blocked.

If a worker hits an out-of-scope/environment blocker, preserve it and finish the others;
do not abandon productive independent work. An incomplete preview must stay explicitly
incomplete; do not drop a failed task/result silently just to certify the batch.

## Final handoff and stop boundary

Return a table of original P4a/AN01 candidates, new worker branches/base/SHAs, preview
parents/SHA, actual focused/full/QA results, accepted-versus-draft status, failure logs,
resource cleanup and remaining gaps. Original candidates and Cursor's seven edits stay
unchanged. All new commits and merges use PHANI465 <pgavara1@asu.edu> as sole author
AND committer, no trailers, history rewriting or global Git changes. Main and central
coordination remain Codex-owned; no external remote/push, deployment, live/auth call,
final-case generation/inspection, new dependency/model download or paid usage.

Remaining later work is explicit: Codex reviews P4a and this batch; report backend/UI
waits for accepted analytics contracts; live comparisons wait for P4a acceptance and
owner go-ahead; real CI/hosting/BYOK require a separate authorized deployment task.
Optional Ollama/deep-learning/RAG/graph tracks are not added merely to fill the queue.
