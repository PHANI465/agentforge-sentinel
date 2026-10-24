Current dispatch: C04 09b5378 is accepted; start C07 using docs/prompts/CLAUDE_C07.md from latest task/coordination. C03/C05 remain accepted. Cursor owns remaining U02 R21 wiring; U03 waits for an accepted C07 HTTP dependency. Earlier dispatches below are history, not permission to repeat completed tasks.

Current dispatch: C03 a8e716c is accepted and C04 is ready using docs/prompts/CLAUDE_C04.md from latest task/coordination. C01/C02/C05 are accepted and stay intact. C06/C08 await review; Cursor owns U02 R21/R22. The batch below is the broader backlog; do not repeat completed packages.

# Claude implementation batch

Current next step: C01 is accepted at 2e6c232. Read CLAUDE_C02.md from the latest task/coordination reference. The C01 correction prompt below is historical; C03/C06/C08 still await review. This current phase supersedes the initial execution order below.

Open a dedicated Claude worktree. Read this entire prompt and the shared queue first. This prompt is the owner's requested substantial work queue; execute ready packages in order and use independent packages while waiting for reviews.

You are Claude Code continuing AgentForge Sentinel. The owner also has Codex AND Cursor, and explicitly requires that Cursor implement the analyst UI and browser tests.

Read AGENTS.md, docs/STATUS.md, docs/TASK_QUEUE.md, docs/reviews/c6d369f.md, relevant decisions and the task handoff. Confirm the actual Git branch/HEAD, clean state and dependency commit. The reviewed thin path is c6d369f; main may still be the original baseline. Start from committed task/coordination or a later explicitly accepted base.

Your assignments:
1. C01: typed HTTP responses and frozen fixtures/OpenAPI; scoped case list, minimal overview and safe session/capability metadata. This is the immediate priority that unblocks Cursor.
2. C02: deterministic backend/browser fixture and real test-server lifecycle. Cursor owns the UI and browser test implementation.
3. C03 then C04: independent synthetic fraud data, historical features and reproducible CPU rule/logistic/tree baselines.
4. C05: backend reliability/observability/secret-safety work.
5. C06: backend/package CI and later the small seeded ML reproducibility job.
6. C07 only after its model/API gates pass; C08 local deployment/operator preparation where ready.

Use docs/TASK_QUEUE.md for exact ownership, dependencies and acceptance. Each package is its own bounded branch and tested commit, not one enormous change. You may use your subagents for read-only research/review or explicitly disjoint paths. You remain responsible for integration; do not run two writers in one checkout.

Immediately after C01, emit its exact contract commit and handoff for Codex review/Cursor. C02 waits for accepted C01, then supplies its own fixture commit. While waiting for review, continue C03, C05 or C06 in a separate worktree; C04 waits for accepted C03. Do not silently integrate an unreviewed dependency. Keep dependencies immutable by commit.

Cursor owns web/, docs/ui/ and web/e2e/. Do not implement its UI yourself or change its package lock. If a backend change affects Cursor, write a concrete contract change request with response examples, stop dependent edits, and notify the owner through the handoff. Shared Python dependencies/migrations have one writer at a time.

Use the owner's existing subscriptions/free resources only. Ordinary checks and CI must not call a live model. Targeted personal live tests are opt-in and separately reported; do not use API-key fallback, buy resources or loop on quota failures. Spend allowance on useful implementations and verification, not repeated self-reviews without new evidence.

Keep central STATUS/TASK_QUEUE ownership with Codex. Update your branch handoff, task-specific technical docs and evidence instead. Preserve licenses/provenance and unrelated files. Stage explicit paths, inspect the diff for secrets, commit the task, then run final checks. Do not merge into main or rewrite published history.

Before a limit or context boundary, finish an atomic increment or hand off dirty work honestly. Report completed task IDs, commit hashes, tested revisions/commands/results, unresolved failures, Cursor-ready artifacts and the next ready task. Every completed package needs code/artifacts and evidence; a plan alone does not complete it.
