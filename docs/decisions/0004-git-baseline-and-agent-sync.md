# 0004: Git baseline and how Claude Code and Codex stay in sync

- Status: accepted
- Date: 2026-10-23
- Decided by: project owner (chose "shared docs + Git")

## Context

The project folder had no Git repository. Codex built the contracts increment and Claude Code was asked to continue. Both tools must see the same history and know who owns what.

## Decision

- `git init -b main` (matching the source project's `main`). The previously uncommitted Codex-led working tree is the baseline commit `507538e` on `main`.
- Each task gets a branch (`task/<slug>`) and a branch handoff note at the path printed by `python scripts/agent_status.py --note-path`. The note carries the tested commit, changed paths, results, gaps and one next action.
- Parallel work uses separate worktrees (`git worktree add ../sentinel-<slug> -b task/<slug>`), never two tools in one checkout at once.
- One integrator merges into `main`, reruns the checks on the merged commit and is the only editor of central STATUS.md rows. Integration ownership moves with the agent that holds it, recorded in STATUS.md.
- `.gitattributes` forces LF so file hashes and schema exports match across Windows, WSL and CI.

No remote is configured. Sharing with another machine or a cloud agent requires adding one deliberately.

## Consequences

Uncommitted files are visible only in this checkout. Codex in another worktree sees only committed work. Handoff notes and STATUS are coordination aids, not a shared memory system.
