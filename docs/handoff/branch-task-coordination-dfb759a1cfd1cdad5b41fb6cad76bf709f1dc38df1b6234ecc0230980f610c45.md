# Handoff: task/coordination

- Updated: November 5 2026 America/Phoenix.
- State: G3D-P1 integrated and verified; R41-R43 closed; owner budget decision implemented.
- Code reference tested before this note: aa5ee1e124c4163c124d33a9cb036fadf510b397.
- Evidence:647+one allowed skip on Windows/native, six commands each, same-run JUnit,
  HTTP/package/ML; Windows UI 133, typecheck/build and real browser 19+10 pass.
- Publication changes documents only beyond the tested commit, not another full-head pass.

## Next action

Claude starts docs/prompts/CLAUDE_G3D_WORKFLOW_BACKUP.md in a new isolated worktree from
current main containing aa5ee1e124c4163c124d33a9cb036fadf510b397; Opus 5.5 / High. Codex reviews before integration.

## Preserved and limits

2700s verification-command cap was explicitly approved; individual/application deadlines,
assertions and skip rules unchanged. Earlier timeouts remain failed and archived; cause
unproven. No owned test databases/APIs or browser secrets/recovery remain. Accepted
worktrees, unrelated services and Cursor's seven changes are preserved. No live provider,
final cases, paid usage, remote/push/deployment, Linux browser, macOS, real CI or hosting.
Current checkpoint and study guide are in docs/artifacts/.
