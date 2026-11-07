# Handoff: task/claude-g3d-p4a-tooling

- **Task and acceptance criteria:** P4a review corrections R46, R47 and R49 ([CLAUDE_P4A_REVIEW_FIXES.md](../prompts/CLAUDE_P4A_REVIEW_FIXES.md), findings in docs/reviews/G3D-P4a-96293da.md on task/coordination), under the batch dispatch CLAUDE_BATCH_REVIEW_CORRECTIONS_2026-11-06.md. The original P4a delivery (A–E, 96293da) is described below this section.
- **Tool and worktree:** Claude Code (Opus 5.5 / High), Worker A, the only editor of E:/PHANI/sentinel-wt/claude-g3d-p4a-tooling.
- **Base:** 96293da1a3403bb1d9bf9eb7c669354b2089c5be (no reset, amend or rebase; earlier commits kept).
- **Updated:** 2026-11-07, local time (-07:00).
- **State:** ready for Codex re-review. Not accepted or integrated.
- **Code reference tested before this note:** the fix commit 4b9118d647d5215d7ff593395e5f49be1899b172, and the identical working tree before it. The final exact-HEAD focused run (after this note's commit) is reported in chat; a note cannot name its own commit.
- **Owned and changed paths:** scripts/agent_eval_support/artifact.py, scripts/agent_eval_score.py, scripts/agent_eval_report.py, tests/test_agent_eval_corrections.py (new), tests/test_agent_eval_scoring.py, tests/test_agent_eval_reporting.py, tests/test_agent_eval_pilot.py (make_run test data only), docs/evals/agents/p4a-tooling.md, this note. No production src, frozen protocol/cases, contracts, UI, locks, CI or timeouts changed.

## Implemented (corrections)

- **R46** (`artifact.validate_run`):
  - Each row's outcome, code, case state, disposition and telemetry status must agree (refused: code `agent_capacity_exhausted`, no state or disposition, 0 role attempts; pending: a pending code; error: a non-typed code and no disposition; inconclusive: no disposition, not awaiting_approval; disposition: no code, a disposition unless telemetry was unavailable). Disposition kind and source must fit the comparator.
  - `status` must be complete/incomplete. A complete record may have nothing not attempted. An incomplete record's `stopped` must match the boundary (last comparator that ran and its first not-attempted case, or the first comparator not started). Comparators must be in planned order.
  - Scoring keeps unknown recommendations (telemetry unavailable) apart (`recommendation_unknown`, excluded from the acceptable denominator, with a note), and lists pending attempts with a stored hold as `wrong_holds.pending_with_stored_hold` without inferring a disposition. First outcomes, wrong-hold 0/1 and the R41/R42 attempt rules are unchanged.
- **R47** (`agent_eval_score.read_sheet`/`human_metrics`, `agent_eval_report.review_packets`):
  - The unblinding key now binds every generated sheet row (item, kind, text SHA-256 as a CSV reader reads it back). A sheet is refused for: wrong columns, an unknown packet or item, a duplicate item, a missing generated item, changed text or kind, an invalid choice (`banana`), an answer in a column that does not apply, a correction without `would_correct = yes`, or a key without binding.
  - Blank is unanswered, never "no". Every metric reports its answered and unanswered counts, and `review_status` is complete, partial or not scored. The rubric-supported denominator is supported + unsupported + not_checkable (protocol-v1 §3), so 1 supported + 1 not_checkable = 1/2. The earlier maintained test that expected 1/2 for supported/unsupported/not_checkable now expects 1/3.
- **R49** (`agent_eval_report`):
  - The export rebuilds the adopted disposition from storage (the runner's rule) and refuses any disagreement in source, kind, operation, reason_code, basis_run_id, workflow_id or claim counts. It also refuses a basis that is not a finding run of the adopted workflow, and a stored adoption contradicting a recorded inconclusive/refused outcome. Exported fields come from storage, labelled `verification`. For a disposition whose telemetry was unavailable, the export is stored-only and labelled; the recorded outcome is unchanged.
  - Owner/admin/switched export logins are refused before any read. `review_packets` re-validates each bundle's run digest and its adopted-vs-run agreement before building any packet.
  - Two aggregate cross-checks that I tried briefly (latency list, inconclusive_by_code) were dropped: the scorer recomputes both from rows. The two parametrized cases for them failed on 96293da in the first failing-first file, but they are not in the final tests.

## Verified (corrections)

- **Failing-first on unchanged 96293da source** (new tests written before any source edit). Evidence is private and ignored, under `.agent/p4a-fix/`:
  - `failing-first-unit-96293da.xml`: 38 failed / 0 passed. That covers every R46/R47 unit test and the bundle check, including both review mutations, banana, duplicate, partial, correction-only and supported+not_checkable.
  - `failing-first-db-96293da.xml`: 5/5 R49 real-DB tests failed. The escalate→simulated_hold/hold export was accepted, revision basis and owner identity were not refused, and telemetry-unavailable gave adopted None.
  - `failing-first-db-fields-96293da.xml`: the reordered field test failed at its first mutation ("C0 reason" accepted).
- **After the fix** (working tree = 4b9118d content, plus the one-line test fix below):
  - `focused-fixed-worktree.xml` / `.log`: 93 passed, 1 failed, 209.8 s, across six modules (corrections, reporting, scoring, pilot including the real deterministic end-to-end, privileges, failures).
  - The failure was a test bug. The "C2 operation" mutation set `simulated_hold`, which is already C2-det's stored D01 operation, so nothing changed. It was diagnosed, fixed to always change the value, and passed: `focused-r49-fields-fixed.xml`, 1 passed, 19.1 s.
  - One intermediate rerun used unchanged code (the edit had not applied) and failed identically; that is recorded honestly. Ruff is clean.
- **Test databases:** a disposable initdb cluster owned by the pytest session (conftest `pg_cluster`), stopped and removed by pytest; there is no external database. Every DB run held the shared heavy-slot lock (log entries "A acquire/release").

## Not verified / gaps (corrections)

- No full six-command Windows/native gate. Per the batch, the coordinator certifies once on the combined preview, and this branch SHA does not inherit that result. No browser, frontend, live, auth or provider work.
- These are consistency checks of unsigned, editable files, not tamper-proofing. A fully coherent rewrite of a run file is detectable only by the storage-backed export, and an edited bundle with both copies changed coherently is not detectable offline.
- Keys generated before this change have no sheet binding and are refused; the packets must be regenerated. Workflow elapsed remains not measured.

## Next action

Codex independently re-reviews R46/R47/R49 at the final corrected SHA reported in chat.

---

# Original P4a delivery (96293da), kept as history

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
