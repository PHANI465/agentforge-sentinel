# Handoff: task/claude-g3b-workflow

- **Task:** G3B, the bounded three-role investigation backend (docs/prompts/CLAUDE_G3B_WORKFLOW.md on task/coordination a3198bc; accepted design G3A 43d9e8a, review G3A-43d9e8a.md).
- **Tool and worktree:** Claude Code, E:\PHANI\sentinel-wt\claude-g3b-workflow (new; the branch and path did not exist; the G3A checkout is untouched).
- **Updated:** 2026-10-31.
- **State:** the R37 correction is ready for Codex re-review (review docs/reviews/G3B-b74473e.md, prompt CLAUDE_G3B_OWNERSHIP_FIX.md). R34-R36 are closed. G3C, final and live evaluation are not started.
- **Base:** exact 2919f76a5cad729ea078d5bfb35c226a3d2bff3f (it contains no G3B runtime code). The corrections continue on the same branch, from reviewed candidates 391effe and then b74473e (no reset, rebase or amend).
- **Code reference tested before this note:** the R37 working tree on b74473e. The final Windows strict gate, native Linux gate and browser results are for the final commit and are reported in chat.

## R37 correction (ADR 0007, item 10)

- **Lifetime owner:** `budget._Lease` owns the connection's users during a bounded call (the SQL worker and the COMMIT cancel helper).
  - A reply is handed back only after the helpers have left.
  - A helper outliving the response budget retires the connection: quarantined, never reused, and closed exactly once by the last user, before its quarantine entry is released.
- **Shutdown:** `budget._OwnSocket` duplicates the socket before the operation starts, so a shutdown can never reach a closed and reused descriptor.
- **Changed paths:** `src/sentinel/agents/budget.py`, new `tests/test_agent_ownership.py` (4 cases), ADR 0007 and this note.
- **Failing-first on b74473e:** the same 3 of the 4 new cases failed on Windows and on native Ubuntu, each for its lifetime behaviour:
  - the confirmed COMMIT's connection was not retired while its canceller ran;
  - the connection was closed while a cancel request was still active;
  - a shutdown was built on the closed descriptor (Windows, intercepted); on Ubuntu, the reused foreign socket's peer received EOF.

  The positive reuse case passed, as expected.
- **Codex's ownership probes:**
  - Probe B (a real reused descriptor) passes natively after the correction.
  - Probe A still fails by construction: its canceller is released only after the call returns, so the connection is (correctly) retired, and the probe then marks a next statement on it itself. The maintained case asserts the same scenario under the production reuse rule (`usable()`).
- **Mutation controls:** 5 of 5 caught on Windows; the descriptor mutation was also caught on native Ubuntu.

## R34-R36 corrections (ADR 0007, items 6-9)

- **R34, finite client waits:**
  - `budget.bounded_call` runs every statement, COMMIT and rollback on an operation thread, and the caller waits at most the remaining transaction budget;
  - COMMIT's cancel request goes 1 s (at most half the budget) before that end, with at most 150 ms more for the reply once the request completes; an unanswered COMMIT is `CommitUncertain`;
  - **quarantine:** an abandoned connection is never reused; its operation thread closes it, its socket is shut down, and admission is refused while the quarantine is at the limit;
  - **recovery owns its transaction:** `owned=False` is gone, and `begin_investigation` defers to `recover_workflow_bounded`.
- **R35:** the full call budget is rechecked after the start record, before submission. If it no longer fits, the unused slot is released and the run fails `budget_exhausted` with no usage. The wait is capped by the working time left.
- **R36:** persisted `transition` steps, checked against the pinned `max_transitions` before each one; `done` is the terminal step and is never refused.
- **Changed paths:**
  - `src/sentinel/agents/{budget,coordinator}.py`;
  - `src/sentinel/service.py` (`begin_investigation` recovery hand-off);
  - new `tests/test_agent_bounds.py` (16 cases);
  - `tests/test_agent_workflow.py` (the D08 step list now includes its `transition` step);
  - ADR 0007, `docs/api/README.md` (the capacity cause) and this note.
- **Failing-first on 391effe source** (scratch export, scratch release timer): 15 of 16 new cases failed. Stalled waits lasted 30 s, withheld replies blocked until released, the recovery waited out an 8 s COMMIT, a live call was made with 45 s of 47 s left, and no transitions were recorded or limited. The quarantine-admission case failed with an AttributeError, because the mechanism did not exist. The "still fits" control passed.
- **Codex's four independent probes** pass on the corrections (3 runs).
- **Tests use a test-owned TCP relay** that withholds server replies to give real-PostgreSQL no-reply coverage, both for a terminal COMMIT (unknown within 2 s; the client re-read shows the commit) and for a working statement (connection quarantined and replaced, inconclusive `budget_exhausted`).

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
