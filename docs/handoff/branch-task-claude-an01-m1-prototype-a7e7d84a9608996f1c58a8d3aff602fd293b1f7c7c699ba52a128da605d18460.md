# Handoff: task/claude-an01-m1-prototype

- **Task and acceptance criteria:**
  - current: `task/coordination:docs/prompts/CLAUDE_AN01_M1_R2_FOLLOWUP.md`, the residual R54 and R56, under the binding review `docs/reviews/AN01-M1-5e0a578.md`;
  - earlier: `CLAUDE_AN01_M1_REVIEW_FIXES.md` (R53–R57) and `CLAUDE_AN01_M1_IMPLEMENTATION.md`.

  Prototype code and tiny proofs only. DOC01 is not started here.
- **Tool and worktree:** Claude Code, `E:/PHANI/sentinel-wt/claude-an01-m1-prototype`, from accepted main `a07ec12710c86b15f111d13e3384c4cf0c6c8f6e`. Native clone: WSL `~/an01-m1-native`, fast-forwarded from git bundles of this branch.
- **Updated:** 2026-11-08 (America/Phoenix).
- **State:** the R54/R56 follow-up is delivered for Codex re-review. Not accepted and not merged.
  - `93583a7570ae78f254a2d69e9857b701b0e444ad` and `5e0a578be91b7739e5d08fc315dc37504f0df188` are preserved with their ancestors: no reset, amend or rebase.
- **Code reference tested before this note:** `af6292f5466b3d99d23796b00fac3e53ff362b77`.
  - The registered tiny validation pair, the probes and the focused tests ran at that commit.
  - This note's commit changes documentation only, so the source and statement identities are unchanged.
- **Final check evidence:** the six-command gates and the JUnit, HTTP, package and ML checks run on the final commit, Windows then native. Results are reported in chat.
- **Owned/changed paths:**
  - `scripts/benchmark_reports.py`
  - `scripts/report_benchmark_support.py`
  - `tests/test_report_benchmark.py`
  - `tests/test_report_benchmark_review.py`
  - `docs/benchmarks/AN01-M1.md`
  - this note

## Implemented (see [AN01-M1.md §5c](../benchmarks/AN01-M1.md))

- **R54:**
  - stored medians and maxima are reconciled with the timed outcomes (0.001 ms rounding rule), and the rules use derived values;
  - EXPLAIN evidence must name the operation's statements, in order, each answered;
  - per-control diagnostics are validated (C1–C4 `control_run_problem`; C5's exact event sequence);
  - rules check their own inputs (`valid_cell`), and an invalid mandatory cell is missing;
  - the loader is strict, while `rule_n_star` tolerates absent (never contradictory) summaries on raw input.
- **R56:** nested finalization. An interrupt after ROLLBACK's reply, or raised by it, closes the idle connection once. A busy connection still goes to its lease, and a failed close keeps its owner.

## Verified

- **Failing first, on unchanged `5e0a578` (Windows):** 22 failed (all AssertionError, 0 setup errors; R54 17, R56 5) and 61 passed. Codex's additional probes gave 6/2/0.
- **At `af6292f`:**
  - Codex original 14: 13/1/0 on both platforms (the disclosed `read_at` fake);
  - Codex adapted 14: 14/0/0 on both;
  - Codex additional 8, on the new records: 7/1/0 on both. The failing baseline control reflects the genuine C2:400 failure;
  - focused tests: native 150 passed; Windows 149 passed and 1 failed (the stall test, kept and not rerun).
- **Tiny validation pair at `af6292f`** (14 records, identical identities):
  - every stage complete except Windows S6 (C2:400 failed: run 1 got no reply by `work_end`);
  - S3 picks A and S7 gives N\* = 80;
  - S9 says **not demonstrated**;
  - cleanup was verified on both platforms.

## Not verified / gaps

- **R-M1-1:** the margin is not qualified. Windows C2:400 failed in the r3 pair, and native C2:1250 failed at `f00df8c`; both stay failed.
- **The Windows stall test (unchanged path):** a setup server start stalled about 10 s, so the 15 s deadline stopped the worker before the injected stall. Cleanup was correct and nothing leaked; the cause of the stall is not established.
- **D's derived maximum:** through the loader, an invalid D cell is missing (not demonstrated), but its derived over-budget trigger shows only on raw rule input.
- **Unchanged and still open:** R-M1-2 (production clock) and R-M1-3 (4 GB and backing-space refusals kept).
- **Not run:** the full grid, production S1 code and HTTP, and DOC01.

## Next action

Codex re-reviews the exact final SHA reported in chat.

## Coordination and provenance

- **Reused unchanged:**
  - `scripts/local_stack.py`;
  - `sentinel.db.roles.grant_runtime`;
  - `sentinel.db.migrate`;
  - the v1 contract models;
  - the scoring artifacts;
  - Codex's probe sources in `.agent/an01-m1-r2-review/`, run unmodified. The additional set's records folder was given through its own `AN01_RECORDS_ROOT` variable.
- **Not touched:** src, contracts, migrations, locks, CI, timeouts, skips and central STATUS/TASK_QUEUE.
- **Preserved:** Cursor's edits and every other checkout.
- **Evidence** is in the ignored `.agent/an01-m1-r3/`:
  - failing-first runs;
  - probes;
  - focused runs and the stall-test failure;
  - validation run directories, records and logs;
  - cleanup output.

  Earlier evidence is kept in `.agent/an01-m1/`, `.agent/an01-m1-r2/` and `.agent/gate-*`, and natively in `~/an01-m1-native/.agent/`.
- **Run data:** synthetic only; no credentials in public records.
