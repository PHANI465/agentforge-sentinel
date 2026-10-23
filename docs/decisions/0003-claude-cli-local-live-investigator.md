# 0003: Claude Code CLI as the opt-in local live investigator

- Status: accepted for local use only
- Date: 2026-10-23
- Decided by: project owner (chose "use my Claude account as the app's live AI"); implemented by Claude Code

## Context

G1 needs one explicitly authorized local live-model test without new spending. The owner has a logged-in Claude subscription and Claude Code 2.1.224. Per PROJECT_PLAN.md, headless `claude -p` can use subscription limits for ordinary individual use. That entitlement does not cover routing public visitors through the owner's account.

## Decision

`ClaudeCliInvestigator` runs `claude -p --output-format json --json-schema <InvestigationFinding> --tools "" --strict-mcp-config --setting-sources "" --no-session-persistence --system-prompt <fixed>` with:

- a fresh empty temporary working directory, so no project files or CLAUDE.md are visible;
- `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, Bedrock/Vertex switches and `ANTHROPIC_BASE_URL` removed from the child environment, so it cannot silently bill an API key;
- input limited to typed synthetic facts and the rule score;
- output parsed into `InvestigationFinding` (`extra="forbid"`, enumerated operation/reason, 600-character rationale). Anything else becomes a typed failure (`invalid_output`, `provider_unavailable`, `timeout`) and the case reopens;
- a timeout matching the run budget. stdout is never logged.

Selection: `SENTINEL_INVESTIGATOR=claude-cli` (default `deterministic`). It refuses to start unless `SENTINEL_MODE` is `local`. On Windows the npm `.cmd` shim is never executed, because cmd.exe would re-parse the JSON arguments. The package's native `claude.exe` is resolved instead, or `SENTINEL_CLAUDE_EXECUTABLE` is used.

`--bare` is not used: it skips keychain/OAuth reads and therefore subscription login.

## Alternatives considered

- Claude Agent SDK (Python): same entitlement, but a new dependency. The CLI is already installed and verified.
- Anthropic API key: separate billing. Out of budget unless an existing allowance is confirmed.
- Ollama: not found on PATH.

## Consequences

- The investigator's config (model alias, prompt, schema) is content-addressed and pinned on each case. Switching investigators makes open cases fail with `stale_agent_config` instead of silently mixing configurations.
- The model alias (`sonnet`) can resolve to different model versions over time. The pin records the alias, not the resolved model.
- Subscription quota exhaustion surfaces as `provider_unavailable`. The deterministic investigator remains available.
- Hosted/public BYOK needs a separate provider-key adapter and is still unverified.
