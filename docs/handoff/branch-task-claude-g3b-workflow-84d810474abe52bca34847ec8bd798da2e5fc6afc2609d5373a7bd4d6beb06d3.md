# Handoff: task/claude-g3b-workflow

- **Task:** G3B, the bounded three-role investigation backend (docs/prompts/CLAUDE_G3B_WORKFLOW.md on task/coordination a3198bc; accepted design G3A 43d9e8a, review G3A-43d9e8a.md).
- **Tool and worktree:** Claude Code, E:\PHANI\sentinel-wt\claude-g3b-workflow (new; the branch and path did not exist; the G3A checkout is untouched).
- **Updated:** 2026-10-31.
- **State:** ready for Codex review. G3C, final and live evaluation are not started.
- **Base:** exact 2919f76a5cad729ea078d5bfb35c226a3d2bff3f (it contains no G3B runtime code).
- **Code reference tested before this note:** the G3B working tree on 2919f76. The final Windows strict gate, native Linux gate and browser results are for the final commit and are reported in chat.

## Changed paths

- **New:**
  - `src/sentinel/contracts/agents.py`;
  - `src/sentinel/agents/{__init__,budget,capacity,tools,claims,adapters,coordinator}.py`;
  - `src/sentinel/db/migrations/0005_agent_workflows.sql`;
  - `contracts/agents/` (15 schemas, 85 examples);
  - `tests/test_agent_{baseline,units,tools,workflow,adapters}.py`, `tests/support/agent_cases.py`;
  - `scripts/agent_eval.py`;
  - `docs/decisions/0007-three-role-workflow.md`;
  - this note.
- **Narrow edits:**
  - `src/sentinel/service.py`: clock and capacity fields; the `tool_config` pin and its claim check; workflow dispatch; `_case_detail` and `_build_intent` helpers (behaviour unchanged); workflow recovery in `_recover_lost_run`; the run tie-break `ORDER BY started_at, seq`;
  - `src/sentinel/investigators.py`: `from_environment` only;
  - `src/sentinel/db/roles.py`: grants and sequences;
  - `src/sentinel/observability.py`: three fixed fields (`workflow_id`, `role`, `attempt`);
  - `scripts/export_contracts.py`: additive agents export;
  - `docs/api/README.md`: both codes and client guidance;
  - status pointers in `docs/agents/G3A-design.md` and `G3B-implementation-plan.md`.
- **Owner-approved extra paths** (asked during this task):
  - `pyproject.toml`: `sentinel.agents` added to the explicit package list, after a probe wheel showed it missing. No dependency or lockfile change; `uv lock --check` passes.
  - `tests/test_backup_restore.py` and `docs/runbooks/local-operations.md`: the inventory guard now lists the two new tables (14 → 16).
  - `tests/test_check_package.py` (the pinned count 4 → 5, test name and node ID kept) and `docs/ci/README.md` (the current migration description, five, 0001–0005). The first strict gate on the previous commit failed only there; the historical evidence row was left unchanged.
- **Not changed:**
  - `web/` and existing `tests/support/*`;
  - `contracts/{v1,http}` and `src/sentinel/contracts/{v1,http_v1,guards}.py`;
  - existing migrations;
  - model/data/evaluation artifacts and lockfiles;
  - CI, checker timeouts and the skip allowlist.

## Failing-first evidence (Windows 11, real PostgreSQL)

- **Baseline on 2919f76:** `tests/test_agent_baseline.py` **4 failed**, each for a behavioural reason, through interfaces that already existed:
  - `three-role` was rejected by `from_environment` (RuntimeError);
  - `agent_workflows` and `agent_steps` were absent;
  - the HTTP investigate route could not run three roles;
  - the docs lacked both codes.

  None of these is an import error. They pass after the change.
- **Real PostgreSQL finding.** `statement_timeout` does **not** bound COMMIT: a 3 s deferred trigger completed under an approximately 1.9 s budget, so the first version of `test_commit_refused_by_its_timeout_is_a_known_rollback` failed. That led to the client-side COMMIT cancel watchdog (ADR 0007, item 1).
- **Mutation controls.** A scratch plugin, not committed, injected one defect at a time; each made its targeted test(s) fail:
  - slot released when waiting stops: 2 failed;
  - repeat after timeout: 1;
  - terminal phase subtracting its own reserve: 1;
  - no workflow guard: 1;
  - no COMMIT watchdog: 1;
  - uncertain COMMIT treated as success: 1.

  The first guard mutation survived because of the append-only step-sequence uniqueness, a second safety layer. A test with no step collision (`test_a_moved_case_stops_every_further_workflow_write`) was added, and it catches the mutation.

## Coverage (all real processes, PostgreSQL and the runtime role unless noted)

- **All 15 development cases, C2-det.** C0 runs for D01–D04, where the catalog says it applies. D06, D12 and D10's HTTP part also exercise existing paths.
- **Terminal outcomes:**
  - commit inside the reserve;
  - too little time (refused, workflow kept running, then recovery);
  - a bounded lock wait that rolls back;
  - a lost connection in the terminal phase (409 `in_progress`) and in the working phase (reconnect, inconclusive);
  - an uncertain COMMIT (backend killed during a deferred commit: 409 `outcome_unknown`, client re-read, recovery);
  - a COMMIT cancelled by the watchdog (a known rollback).
- **Guards and history:** a superseded workflow cannot alter newer state; a moved case stops every further write; concurrent investigations; the mode switch gives `stale_agent_config`; zero-role and between/during-role crash recovery; complete historical runs after a retry.
- **Leases:** a held worker keeps its call slot until it returns; there is no repeat after a timeout; capacity is refused across admissions; the late result writes nothing.
- **Claude role adapter:** driven through a **real test-owned subprocess** (a fake CLI script; no billable call): flags, preflight, scrubbed environment, envelopes, usage, and an ended child after timeout. The manual evaluator refuses live comparators without `--allow-live`.

## Not verified / gaps

- **No live model or subscription call; no quality claim.** Deterministic roles prove plumbing and safety only. No final or held-out evaluation was run.
- **UI unchanged.** The v1.1 UI shows role runs as plain runs; the trace view is G3C. A zero-role inconclusive workflow shows "No investigation has been recorded", while the audit shows the failure.
- **Bounds are on elapsed waiting only.** The COMMIT watchdog bounds the client wait; a commit that completes before the cancel arrives still succeeds. Durable-commit timing, cancel latency and response transport are not measured. The limits remain provisional.
- **Not claimed:** provider-side cancellation and billing; a cross-process provider cap (leases are process-local); macOS and GitHub Actions; Linux browser execution.

## Next action

Codex: review G3B (`sentinel.agents`, migration 0005, ADR 0007 decisions 1–5) and integrate after its own checks.
