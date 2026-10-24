# Cursor: U03 contract/UI increment is ready

U02 remains accepted at 5f2855553ac0a445d96914730a89fc3722682830; preserve its tested branch/worktree. R21/R22 are resolved.

The HTTP v1.1 schema and nine examples at 62def106af74821040ac54535b8efe87341ca10b are now accepted as a UI development dependency only. The complete C07 backend is changes-requested for R23 and must not be merged or treated as accepted. See docs/reviews/62def10.md.

Start the dedicated U03 frontend increment using docs/prompts/CURSOR_U03.md, read from latest task/coordination together with AGENTS.md, STATUS and TASK_QUEUE. Base task/cursor-model-analysis on accepted U02 5f28555; consume the named contract artifacts without merging the unaccepted backend. Implement actual frontend types/client/components and fixture-based checks now; real new-feature browser/API/Postgres acceptance follows an explicitly accepted corrected backend. Never substitute fixtures for failed live calls or label this first increment complete U03.

Cursor owns web/ and docs/ui/, Claude owns the R23 backend correction, Codex owns reviews and central coordination. Keep exact SHA handoffs; there is no automatic cross-tool messaging. No main merge, provider usage, CI/WSL provisioning or hosting is assigned.
