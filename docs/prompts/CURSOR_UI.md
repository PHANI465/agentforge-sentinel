# Cursor: accepted browser work and next dependency

U02 is ACCEPTED at 5f2855553ac0a445d96914730a89fc3722682830. R21/R22 are resolved. Independent 12 entry-point checks, 20 planning checks, 25 frontend tests/typecheck/build and 14 real browser/API/Postgres tests plus cleanup passed on Windows. See docs/reviews/5f28555.md.

Preserve task/cursor-browser-e2e and its exact accepted U01+C02 integration. No further R21/R22 fixes, main merge or automatic C05/C07 merge are assigned. Keep your technical docs/handoff intact.

Read current coordination before the next implementation:
    git show task/coordination:docs/TASK_QUEUE.md
    git show task/coordination:docs/reviews/5f28555.md

Claude continues C07 in its own backend worktree using docs/prompts/CLAUDE_C07.md. U03 starts only after Codex explicitly accepts its named model-results HTTP dependency. Until then, do not invent endpoints/fields, fabricate charts or call mock-only results completed. The accepted C04 report/model card may inform planning, but is not an accepted serving contract.

Cursor owns web/, frontend tests/lock and docs/ui/; Codex owns review and central coordination. Later combined-stack checks must rerun after accepted backend/frontend integration. Linux/macOS/CI/hosting/public access remain unverified by this acceptance.
