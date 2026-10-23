# Cursor analyst UI assignment

The owner explicitly requires Cursor to contribute. You own the analyst interface and browser tests; Claude owns backend/data/ML and Codex owns review/coordination.

Open a dedicated Cursor worktree. Read AGENTS.md, docs/STATUS.md, docs/TASK_QUEUE.md, relevant decisions and the accepted C01 HTTP contract/fixtures. Read the current coordination queue from its named Git reference; files in another worktree are not your working copy.

Before coding, record your base/dependency commit. U01 waits for Codex's acceptance of the C01 contract commit. If it is not available yet, produce a short UI task/design note and identify the exact missing contract; do not invent endpoints or implement a mock-only app as completed functionality.

Implement U01 in web/ and docs/ui/:
- React/TypeScript/Vite, a typed client from the accepted response contracts, and a same-origin development proxy.
- Session-token entry in memory only; connection/mode state, sign-out, scoped case queue/overview, case detail/evidence and audit.
- Recorded score and artifact/semantics labels; distinguish rule baseline, deterministic investigator and local Claude mode.
- Exact server-built action details, human approve/reject and separate execute, clear permissions, expired/reopened cases, provider failures and idempotent replay. Keep one execution idempotency key across an ambiguous network retry; test a lost response with one persisted action.
- Safe loading/error/empty states; refresh server truth on 409; keyboard/accessibility support.
- Model rationale is inert text. Do not enable raw HTML or store tokens in URLs/localStorage/sessionStorage.

Then implement U02 after C02's accepted backend fixture: real browser -> API -> disposable Postgres tests for successful execution, rejection, expiration/reopening, stale revision, duplicate retry, cross-session denial and persistence/restart. Ordinary browser tests use the deterministic investigator, not a subscription/model call.

Only start U03 after C07's accepted model-results contract. All charts/counts must match actual data/report fixtures and synthetic limitations.

Do not edit src/sentinel/, Python dependencies, contracts/ or database migrations. Request backend changes through a specific example/status-code handoff. Own web/package lock and frontend workflow; coordinate integration commands with Codex. Reuse source UI code only with recorded repository/file/commit and required notices.

One task branch/worktree; no concurrent edits in Claude's checkout. Keep central STATUS/TASK_QUEUE edits with Codex. Commit explicit owned paths, run build/type/test/browser checks and hand off exact commit, actual results and gaps. Do not merge into main yourself. This is a substantive Cursor assignment, not an extra approval hop between Claude and Codex.
