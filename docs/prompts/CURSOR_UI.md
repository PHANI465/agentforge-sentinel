# Cursor: current UI and browser assignment

U01 is ACCEPTED at deb10370352dc62b0abfa2a5776c185494fcb04e. R14-R17 are resolved; do not repeat those corrections. See docs/reviews/deb1037.md.

C02 is ACCEPTED at 0e72b0bd599ff1707ca5b2507d65a0927894cbe0 for Windows local fixtures. C01 remains frozen at 2e6c2329aafe28b2e7c31ef5078d554cb66ca529.

Your current task is U02. Read and follow:
    git show task/coordination:docs/prompts/CURSOR_U02.md
    git show task/coordination:docs/TASK_QUEUE.md

Use the dedicated U02 branch/worktree and exact accepted dependencies in that prompt. Preserve the U01 checkout and existing work. Do not use task/coordination or old main as the application base. Do not import unaccepted C05. No main merge.

Cursor owns the actual analyst UI, browser tests, frontend lock/workflow and docs/ui/. Claude owns backend/data/ML; Codex owns review and central coordination. No concurrent edits in another tool's checkout. Tokens stay in private test memory/manifests and necessary live authorization headers, never saved artifacts. Ordinary tests use the deterministic investigator and disposable local database, not subscriptions or provider calls.

U03 remains gated on accepted C07/model-results contracts. Its charts/counts must match real reports and retain synthetic-data limitations.
