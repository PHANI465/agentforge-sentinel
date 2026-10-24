# Cursor analyst UI assignment

The owner explicitly requires Cursor to contribute. You own the analyst interface and browser tests; Claude owns backend/data/ML and Codex owns review/coordination.

C01 is ACCEPTED at 2e6c2329aafe28b2e7c31ef5078d554cb66ca529. U01 5055321cfa810a2108d184e5542785cf44977edc resolves R14/R16/R17; one R15 delayed-refresh query race remains CHANGES REQUESTED. Follow docs/prompts/CURSOR_U01_R15_FOLLOWUP.md and read docs/reviews/5055321.md from the current task/coordination reference. Preserve completed corrections. The assignment below remains the intended scope; it is not U01 acceptance. C02 66214bb still has R11/R12 changes requested (R13 corrected); do not merge that fixture candidate or begin U02 until corrected C02 and U01 are explicitly accepted. U03 retains its model dependency.

Use the existing Cursor worktree E:/PHANI/sentinel-wt/cursor-analyst-ui, branch task/cursor-analyst-ui. U01 is already in progress: continue it and preserve existing planning/implementation commits and uncommitted work. Inspect actual HEAD/status. Accepted C01 must be an ancestor; bring it in only if it is missing, after preserving your work. Do not reset, discard files, repeat a completed merge or restart U01 because older worktree documents describe the preparation phase. Report any material dependency conflict.

Read current instructions with:
    git show task/coordination:AGENTS.md
    git show task/coordination:docs/TASK_QUEUE.md
    git show task/coordination:docs/prompts/CURSOR_UI.md
    git show task/coordination:docs/reviews/2e6c232.md

Inherited STATUS/queue copies in this worktree may describe older pending gates. The current coordination reference and accepted C01 commit above govern this task; do not merge the coordination branch merely to copy documents.

Record the exact accepted C01 dependency and actual working HEAD. Read the accepted contracts/http/openapi.v1.json, contracts/http/examples/ and docs/api/README.md before implementation.

Implement U01 in web/ and docs/ui/:
- React/TypeScript/Vite, a typed client from the accepted response contracts, and a same-origin development proxy.
- Session-token entry in memory only; connection/mode state, sign-out, scoped case queue/overview, case detail/evidence and audit.
- Recorded score and artifact/semantics labels; distinguish rule baseline, deterministic investigator and local Claude mode.
- Exact server-built action details, human approve/reject and separate execute, clear permissions, expired/reopened cases, provider failures and idempotent replay. Keep one execution idempotency key across an ambiguous network retry; test a lost response with one persisted action.
- Safe loading/error/empty states; refresh server truth on 409; keyboard/accessibility support. Handle non-JSON 5xx, empty/invalid response bodies and network failures with a safe generic message; do not assume every failure parses as ErrorResponse. An ambiguous execution response retains its original idempotency key.
- Model rationale is inert text. Do not enable raw HTML or store tokens in URLs/localStorage/sessionStorage.

For U02, token-hygiene evidence must cover request headers and all saved artifacts; masking the token field alone does not prove trace redaction. Keep authenticated-context tracing disabled unless complete artifact redaction is verified.

Then implement U02 after C02's accepted backend fixture: real browser -> API -> disposable Postgres tests for successful execution, rejection, expiration/reopening, stale revision, duplicate retry, cross-session denial and persistence/restart. Ordinary browser tests use the deterministic investigator, not a subscription/model call.

Only start U03 after C07's accepted model-results contract. All charts/counts must match actual data/report fixtures and synthetic limitations.

Do not edit src/sentinel/, Python dependencies, contracts/ or database migrations. Request backend changes through a specific example/status-code handoff. Own web/package lock and frontend workflow; coordinate integration commands with Codex. Reuse source UI code only with recorded repository/file/commit and required notices.

One task branch/worktree; no concurrent edits in Claude's checkout. Keep central STATUS/TASK_QUEUE edits with Codex. Commit explicit owned paths, run build/type/test/browser checks and hand off exact commit, actual results and gaps. Do not merge into main yourself. This is a substantive Cursor assignment, not an extra approval hop between Claude and Codex.
