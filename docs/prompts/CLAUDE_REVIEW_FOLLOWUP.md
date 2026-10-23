# Claude follow-up after four delivered packages

Historical correction prompt: R9/R10 are completed and C01 is accepted at 2e6c2329aafe28b2e7c31ef5078d554cb66ca529. Use CLAUDE_C02.md from the latest task/coordination reference for the next task. The pending instructions below describe the earlier review stage; do not repeat them.

Use this follow-up for the current next step; CLAUDE_BATCH.md remains the broader backlog. The owner has not sent the earlier C01 correction prompt yet.

## Preserve delivered work and identify the current state

Read AGENTS.md, the latest shared TASK_QUEUE/STATUS, this prompt and the C01 review report. Inspect actual branches/HEAD and worktrees before editing.

Delivered commits:
- C01: task/claude-api-contracts, 0a6fb0ec8e63fd686ac7e4cf6bbfb7bd22a105b0. Codex reviewed it and requested R9/R10 corrections. It is NOT accepted.
- C03: task/claude-fraud-data, a8e716cdec38fad1c316c6ffa2b722601b50b41d. Delivered; Codex review pending.
- C06: task/claude-backend-ci, e7fc868b52a1d3cc8876d8d993907398663c2d57. Delivered; Codex review pending. GitHub/Linux execution is unverified.
- C08: task/claude-operator-prep, 9ab183e836751a75e7a1a350afc51af7663f9a63. Delivered; Codex review pending.

Keep these branches and worktrees. Do not rebuild the delivered packages, squash away their evidence, merge them into each other or main, or describe a strict-check pass as review acceptance.

The current shared instructions and review are available without merging a docs branch:
    git show task/coordination:docs/prompts/CLAUDE_REVIEW_FOLLOWUP.md
    git show task/coordination:docs/reviews/0a6fb0e.md
    git show task/coordination:docs/TASK_QUEUE.md

The original review also exists at E:/PHANI/Interview/output/Sentinel_Review_0a6fb0e.md.

## Immediate task: fix C01 R9 and R10

Use the existing task/claude-api-contracts worktree, E:/PHANI/sentinel-wt/claude-api-contracts. Verify its HEAD and preserve any newer/unfamiliar changes. Do not reset to the old commit if the branch has advanced.

R9:
- decode_cursor currently lets non-string JSON UUID members reach uuid.UUID(), which raises an uncaught AttributeError and produces HTTP 500.
- Validate that decoded JSON is a two-element list of strings before parsing.
- Retain valid timezone-aware timestamp/UUID validation and bounded pagination.
- Invalid shape/type/date/UUID inputs must return 422 {"error":"invalid_cursor"} safely.
- Add HTTP regressions first, including numeric, boolean, object and array UUID members and invalid root/length shapes. Demonstrate the new failure on the submitted implementation; retain tests for valid cursors and existing invalid inputs.

R10:
- docs/api/README.md and ErrorResponse's description promise every non-2xx body is JSON, but unexpected exceptions currently produce plain-text 500.
- Prefer the bounded C01 correction: narrow the guarantee to documented/handled errors. Explicitly require client fallback for non-JSON 5xx, empty/invalid bodies and network failures.
- An ambiguous execution failure must retain the same idempotency key; it does not establish that no action occurred.
- Update the DTO description and regenerate/review affected OpenAPI bytes. Add the appropriate failure-boundary/contract check for the chosen behavior.
- Broader unexpected-error logging/observability remains C05. Do not claim that one handler guarantees JSON from proxies or network failures.

Read the full review for exact evidence, locations and acceptance. No new provider call or dependency is required.

## Verification and handoff

Run focused API/HTTP tests, the HTTP exporter --check and ordinary project checks. Use deterministic investigations with live Claude disabled. Run a bounded real HTTP malformed-cursor probe if practical, with disposable data and clean process teardown.

Update your C01 branch handoff, inspect the diff, stage explicit task paths and commit. Run the strict helper AFTER the final commit. Report:
- new full commit hash, branch/worktree and base;
- what R9/R10 changed;
- test-first evidence and actual commands/results;
- OpenAPI/schema compatibility changes and remaining gaps.

Immediately return that C01 handoff for Codex re-review. Cursor U01 and C02 remain pending until Codex explicitly accepts the corrected commit.

## Work after review, with dependencies respected

- After accepted C01: C02 backend browser fixtures and C05 backend reliability can proceed on separate task branches based on that exact accepted commit. Sequence C05's API/service/migration edits against the frozen contract; coordinate any contract change before Cursor consumes it.
- Cursor MUST own U01, U02 and U03 in its own worktree. You do not edit web/ or docs/ui/ or implement its interface to consume allowance.
- After accepted C03: start C04. First report total and mature-label counts per chronological split. Choose an observation horizon and delayed-label eligibility policy that yields a meaningful evaluation without using labels unavailable at the chosen cutoff. Unknown labels remain unknown, never assumed legitimate; no future-label leakage or test-set tuning.
- C07 waits for accepted C04 and model/API review. Cursor U03 follows the accepted C07 boundary.
- C06/C08 remain awaiting review. Apply only concrete requested corrections; do not repeatedly rebuild delivered work or invent extra packages while waiting.
- While blocked on all dependencies, hand off clearly. Task-specific documentation or a review-preparation note is useful; no dependency is silently accepted merely to keep the agent busy.

## Environment decisions and coordination

This prompt does not authorize installing packages into WSL, creating a Linux user, creating a GitHub repository/remote, pushing branches or provisioning hosting. Leave those two environment decisions pending; they do not block R9/R10. Linux and GitHub Actions remain unverified until actually run.

Keep central STATUS/TASK_QUEUE and shared prompt ownership with Codex. Use task-specific handoffs for your evidence. Preserve source/license attribution, secrets and the existing budget. Ordinary tests make no live model calls. Stop on quota exhaustion without paid API fallback. Do not merge main.
