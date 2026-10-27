# Handoff: task/claude-g3a-design

- **Task:** G3A three-role investigation contracts, coordinator design, evaluation protocol and the G3B plan (docs/prompts/CLAUDE_G3A_MULTI_AGENT_DESIGN.md on task/coordination 4730010).
- **Tool and worktree:** Claude Code, E:\PHANI\sentinel-wt\claude-g3a-design (new; the branch and path did not exist before).
- **Updated:** 2026-10-27.
- **State:** ready for Codex contract review. **G3B is not started.**
- **Base:** exact accepted H01 f091a34c2ed3f6636625b3141be88d86cd5307dd (includes N2–N7). No merge or rebase.
- **Code reference tested before this note:** f091a34 plus these documentation files (working tree). This is a documentation-only proposal: no `src/`, migration, contract, test, UI, script, model or lockfile change.
- **Changed paths (all new):**
  - `docs/agents/G3A-design.md`;
  - `docs/agents/G3B-implementation-plan.md`;
  - `docs/agents/contracts-draft/` (`README.md`, `g3a_models.py`, 13 generated `schemas/*.json`, 24 valid and 25 invalid `examples/`);
  - `docs/evals/agents/protocol-v1.md`, `dev-cases-v1.json`, `dev-cases-v1.md` and `dev_cases.py`;
  - this note.

## Deliverables and decisions

- **Design** (`G3A-design.md`):
  - the current limits, with exact f091a34 file and line references;
  - roles and the coordinator; the state machine with hard limits (≤5 role calls, ≤1 revision, ≤6 tool executions, ≤1 repeat, 45 s per role, 150 s per workflow, 1 live workflow per process, no delegation);
  - the read-only tool registry with decision-time bounds; typed claims and server verification, with a server-rendered rationale;
  - persistence (migration 0005: `agent_workflows`, append-only `agent_steps`, `agent_runs.workflow_id`/`attempt`); exact service integration points; recovery and repeat semantics;
  - the worked case D01; errors, compatibility and version pins.
- **Key decisions:**
  - It is an operator-selected mode (`SENTINEL_INVESTIGATOR=three-role`), and the default stays deterministic.
  - The composite workflow is pinned through the existing `CasePins.agent_config`/`tool_config`, so no v1 contract changes.
  - An inconclusive workflow reopens the case to `open`. The unused `inconclusive` case state stays unused, because no route reopens it.
  - Abstain is always server-built escalate/`insufficient_evidence`.
  - Usage is recorded only when the adapter reports it; there is no monetary cap.
  - **No HTTP revision for G3B.** v1.1 `CaseDetail` stays valid because only the adopted investigator run carries a `finding`. An additive v1.2 trace route is drafted for G3C. There is one new error code, 409 `agent_capacity_exhausted`.
- **Contracts draft:** Pydantic models on the frozen v1 primitives, generated schemas and labelled examples. Each invalid example was confirmed to be rejected for its intended reason (forged IDs, SQL, unknown tool, free window, approve verdict, unbounded limits, inconsistent disposition, and so on).
- **Protocol** (`protocol-v1.md`):
  - comparators C0 (deterministic), C1 (single live), C2 (three-role live), and C2-det as a plumbing control only;
  - metric numerators and denominators with acceptance conditions; hard security gates; the human rubric;
  - the development/final boundary and its independence limits;
  - no numbers reported.
- **Development cases:** D01–D12, with separate runtime and evaluator sections. The implemented flags show that no three-role path exists yet, and that the notes-reader defence is deferred.
- **G3B plan:** one backend vertical slice, owned files, 9 ordered steps with failing-first tests, acceptance checks (the strict gate on both platforms, an unchanged HTTP export, no new pytest skip) and the G3C/G3D dependencies. Recommended settings: Opus, effort High.

## Verified (this worktree, Windows 11, locked dev+ml)

- `uv run --locked python docs/agents/contracts-draft/g3a_models.py --check` → "13 draft schemas current; 24 valid and 25 invalid examples behave as labelled", exit 0. A per-example error listing confirmed each invalid example's intended rejection reason.
- `uv run --locked python docs/evals/agents/dev_cases.py` → "12 development cases consistent with sentinel.scoring; three-role implemented in 0", exit 0. **Negative control:** in-memory changes to a score, a fact and an abstention label were each reported, and an evaluator field placed inside `runtime` was rejected.
- **Ruff:** `uv run --locked python -m ruff check .` passed.
- **Links:** every relative link in the 5 new Markdown files resolves.
- **Protected bytes:** `git diff --stat f091a34` shows only new files under `docs/agents/`, `docs/evals/` and this note.
- **Not run:** the full backend and browser suites. That is intentional for a documentation-only change, per the assignment.

## Not verified / open

- **Not implemented or measured:** no runtime, migration, tool or adapter exists, and no live provider call was made. All numbers in the design are limits, not measurements.
- **Unverified CLI detail:** whether the Claude CLI JSON envelope reports usage is left for G3B to check.
- **Decisions for Codex:**
  1. Accept 409 `agent_capacity_exhausted`, or reuse an existing code.
  2. Confirm the 45 s / 150 s limits for the laptop and subscription.
  3. Confirm that inconclusive reopens to `open`, rather than adding a versioned reopen route.

## Next action

Codex: review and accept, or request changes to, the G3A contracts and protocol. On acceptance, dispatch G3B from the accepted SHA per `docs/agents/G3B-implementation-plan.md`.
