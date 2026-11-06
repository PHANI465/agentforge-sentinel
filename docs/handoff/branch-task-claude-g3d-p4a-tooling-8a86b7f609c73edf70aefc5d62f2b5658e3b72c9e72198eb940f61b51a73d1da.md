# Handoff: task/claude-g3d-p4a-tooling

- **Task and acceptance criteria:** G3D-P4a evaluation tooling, milestones A–E ([CLAUDE_G3D_P4A_EVALUATION_TOOLING.md](../prompts/CLAUDE_G3D_P4A_EVALUATION_TOOLING.md), batch [CLAUDE_TODAY_BATCH_2026-11-06.md](../prompts/CLAUDE_TODAY_BATCH_2026-11-06.md)).
- **Tool and worktree:** Claude Code (Opus 5.5 / High), in E:/PHANI/sentinel-wt/claude-g3d-p4a-tooling.
- **Base:** published main d8443a199200157afa2131ddf8f22c1d20b89a26, which contains accepted plan cee83f9 and tested G3D-P3 integration 495c7d3.
- **Updated:** 2026-11-06, local time.
- **State:** ready for Codex review.
- **Code reference tested before this note:** the working tree on the D commit (5e38877) plus the E paths. Final exact-commit gates are reported in chat; a note cannot name its own commit.
- **Commits:**

  | Milestone | Commit | Content |
  | --- | --- | --- |
  | A | 158d86b | artifacts and measurements |
  | B | e002192 | pilot supervisor |
  | C | 7378283 | export and packets |
  | D | 5e38877 | scoring |
  | E | this commit | end-to-end test, runbook, this note |
- **Owned and changed paths:**
  - scripts/agent_eval.py (additive);
  - scripts/agent_eval_support/ (`__init__`, artifact, measure, catalog);
  - scripts/agent_eval_pilot.py, scripts/agent_eval_report.py, scripts/agent_eval_score.py;
  - tests/test_agent_eval_reporting.py, tests/test_agent_eval_pilot.py, tests/test_agent_eval_scoring.py;
  - tests/fixtures/agent_eval_p4a/run-fixture.json;
  - docs/evals/agents/p4a-tooling.md, and a narrow docs/evals/agents/evaluator-runbook.md update;
  - this note.

  No production src, local_stack.py, browser lifecycle, accepted plan, frozen protocol or cases, contracts, migrations, grants, model, data or evals assets, UI, dependencies, locks, CI, skip policy, checker timeouts or central coordination changed. Existing evaluator tests are unchanged.

## Implemented

- **A. Versioned run artifact `sentinel.agent-eval.run/1`** (additive to the P1 report; `run()` keeps its shape and the R41/R42 semantics are unchanged).
  - Fields: attempt ID and index, scoped tenant/session/case IDs, wall-clock labels, request latency, `workflow_elapsed_ms` null (`not_measured`), the case's pins, workflows, and the adopted disposition by `basis_run_id`.
  - Measurements: recorded role intervals (paired cumulative markers; missing ends unknown; pre-submission budget refusals labelled), the attempt's own `capacity.snapshot()` with its scope, and late-return events observed up to the `run()` cutoff (unknown after).
  - Accounting: reserved, recorded, pre-submission, submission (`not_observed`) and reach (`unknown`) are kept apart. The comparator pin and alias are recorded, model version stays `unknown`, and `--annotations` requires a source and time.
  - Telemetry is read after the outcome and never changes it. `validate_run` refuses old, censored, recounted or relabelled artifacts.
- **B. `agent_eval_pilot.py`.**
  - A new root (never adopted), with a seeded schedule: P00-det, then 10 live pairs.
  - A database-only cluster owned through `local_stack.Stack` and `start_database`/`stop_database`, with one fresh database per pair. The operator provisions; the runtime role does the case work. DSNs go only through the environment.
  - Live pairs need `--allow-live`, the preflight and the full reservation (1 or 5 of 30), reserved before start. Pairs run in order with no rerun.
  - Setup, refusal, typed-failure, short-preflight and wrong-hold stops keep the run file, mark the pass incomplete and list the pairs not attempted.
  - The cluster is stopped after each run. `cleanup --drop` drops only this pilot's recorded, prefixed databases.
- **C. `agent_eval_report.py`.**
  - The export runs as the runtime role in one `REPEATABLE READ, READ ONLY` transaction, selecting by the artifact's IDs plus scope. Every row is re-checked, foreign or tampered mappings and workflow mismatches are refused, and a before/after content-digest proof of no mutation is recorded.
  - Review packets have a seeded order, opaque IDs and a separate key. Comparator, config and role names, pins, case IDs and expected answers are removed; blinding is partial and disclosed.
  - In CSV, formula cells are escaped and typed numbers left unchanged.
- **D. `agent_eval_score.py`.**
  - Catalog membership and digest are checked first, and duplicates or missing pilot artifacts are refused.
  - Metrics: acceptable recommendation, retained wrong holds (0/1), workflow-only abstention (unobservable for C0/C1), machine-supported claims, calls, and nearest-rank latency p50/p95/max with n (refusals apart).
  - Unknowns stay unknown, `n/a (0/0)` is printed for zero denominators, and the hard gates are "not demonstrated" or "not exercised". The human rubric is computed only from completed sheets with a matching key. `summary.md` holds counts and labels only.

## Verified

- **Focused, final working tree:** 75 passed (`.agent/p4a/E-focused.log`). That covers the 4 P4a test modules (31 tests), the evaluator privileges, failures and adapters tests, and the local_stack and startup tests. Ruff is clean.
- **Real deterministic pilot (CLI)** over D01–D04 and D11, P00-det (`.agent/p4a/smoke/`; private).
  - C0 5/5 and C2-det 5/5 dispositions, with acceptable recommendations 5/5 and 5/5 and 0 wrong holds. These are tooling evidence only, not quality.
  - Request latency p50/p95/max: C0 0.187/0.391/0.391 s, C2-det 0.344/0.36/0.36 s (n=5 each).
  - Export: mutation proof unchanged, 0 approvals, 0 actions. 10 blank packets were built and the human rubric is "not scored". No `postgresql://` string appears in any pilot file.
  - Cleanup dropped `p4a_5ad84f61_p00_det`; the cluster is stopped and the port free.
- **Negative controls:**
  - A broken scope filter (`_scope_clause` emptied), with a tampered mapping, is refused by row re-validation.
  - A censored wrong hold (row deleted and renumbered), and one relabelled as a refusal, are refused by integrity and count checks.
  - A pilot artifact that vanished is refused.
  - **Code mutation:** `catalog.wrong_hold` forced to False fails 3 tests (`.agent/p4a/mutation-wrong-hold-censored.log`).
- **A real regression found and fixed during A** (`.agent/p4a/A-existing-evaluator-tests.log`): describing a stub comparator raised and stopped the run. Comparator description is now non-fatal telemetry, and all 31 existing evaluator tests pass.
- **A bug found during C:** evidence facts were exported as `null`. It was fixed, and the strengthened test would fail on it.

## Not verified / gaps

- No live pair (P4b), auth call or provider call was made. Live-pair behaviour is covered by intercepted tests only.
- **Unobservable:**
  - exact workflow elapsed;
  - adapter submission and provider reach;
  - provider-wide capacity;
  - late returns after the cutoff;
  - role inputs (so propagation and cross-scope in inputs);
  - model version and quota without a manual annotation.
- The C0/C1 abstention metric is unobservable. The human rubric needs a real reviewer: the sheets are blank.
- Blinding is partial: C2's rendered rationale ("Reviewer: accept.") and its tool values reveal the system.
- The pilot leaves its root directory on disk after cleanup (manual removal). POSIX lifecycle is the existing local_stack path.
- No browser or frontend run: evaluator, test and doc changes only.

## Next action

Codex reviews P4a on this commit. P4b stays unassigned until the owner gives a written go-ahead.

## Coordination and provenance

- All code is original to this task. It reuses accepted runner, local_stack, agent_cases and trace-test helpers without editing them. No credentials or raw reports are tracked.
- Accepted worktrees and Cursor's seven saved edits are untouched.
