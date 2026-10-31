# Active G3A review follow-up — October 31 resumption

**The owner resumed work on October 31, 2026. The October 27 pause is lifted for this task.**
Recommended coding assistant: **Claude Opus 5.5, High effort**. The work concerns resource
leases, durable terminal states and typed contracts; careful reasoning is needed, but this
remains a bounded design correction. Do not change global model settings.

Read current main:AGENTS.md and current
task/coordination:docs/reviews/G3A-06a7c0c.md and
task/coordination:docs/reviews/G3A-acceptance-checklist.md.
Codex remains integrator; Cursor may remain inactive and its saved checkout is protected.

Resume `task/claude-g3a-design` at exact 06a7c0c779eeb60ff4e57ddab70de07277e27501 in
E:/PHANI/sentinel-wt/claude-g3a-design. Inspect state first; preserve existing history and
unfamiliar edits. No reset/rebase/amend. The application base remains accepted f091a34.

Own only docs/agents/, docs/evals/agents/ and your branch handoff. No src/, migrations,
public contracts, tests/, UI, dependencies, scripts, model artifacts, central STATUS/queue,
provider calls, installs, WSL setup, remote/push/deployment or G3B implementation.

Resolve R31-R33 in the review together as one design revision:
- Define admission/late-worker ownership and release, a finite outstanding-call bound,
  repeat behavior with unresolved calls, and deadline coverage for tools and coordinator.
- Define workflow completion/recovery with no active role, including zero-role and
  between-role cases, true run statuses, audit identity, and eligible abstention basis.
- Enforce the exact role set and consistent usage/workflow lifecycle/time combinations;
  add valid/invalid cases for all independently reproduced contradictions and the new
  terminal examples. Keep cross-record coordinator checks explicit.
- Incorporate the four resolved decisions and the evaluation clarification; keep C1/C2
  end-to-end comparison separate from any future role-only causal claim. Define missing
  denominators and failed-attempt reporting. Do not create or inspect final held-out cases.

Validate the draft exports, all examples, development-case checker, Ruff, relative links
and protected-byte preservation. Demonstrate the new invalid payloads accepted on 06a7c0c
before rejecting them in the revision, without changing that preserved commit. No full
backend/browser rerun is needed for a documentation-only proposal. Report actual commands,
exact tested SHA and remaining limits. All new commits: sole author and committer
PHANI465 <pgavara1@asu.edu>, no coauthor/AI/session trailers. Do not merge main or start
G3B until Codex accepts the corrected package. Live usage observation is not part of this
follow-up. Stop after the completed correction handoff and await Codex review. This is a dependency
gate, not a renewed owner-requested pause. G3B needs a separate accepted design SHA and dispatch.
