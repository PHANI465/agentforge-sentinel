# Handoff: task/claude-an01-m1-prototype

- **Task and acceptance criteria:** `task/coordination:docs/prompts/CLAUDE_AN01_M1_IMPLEMENTATION.md`. Prototype code and tiny proof fixtures only. The full-size benchmark is not run.
- **Tool and worktree:** Claude Code, `E:/PHANI/sentinel-wt/claude-an01-m1-prototype`, from accepted main `a07ec12710c86b15f111d13e3384c4cf0c6c8f6e`. Native clone: WSL `~/an01-m1-native`, built from git bundles of this branch.
- **Updated:** 2026-11-07 (America/Phoenix).
- **State:** ready for Codex review of the controller and resource evidence. Not accepted and not merged.
- **Code reference tested before this note:**
  - The tiny smoke ran at `f00df8c960ad6e277c4d7d48be9c9d625119389e` on both platforms.
  - Later commits change `cleanup_command` and record reply arrival time for latency (`error_at_ms`). They also correct the C2/C3 gate tests after Windows gate run 2 at `cd3517d` failed (AN01-M1.md §5a). The registry and statement digests are unchanged.
- **Final check evidence:** the six-command gates and the JUnit, HTTP, package and ML checks were rerun on the final commit, Windows then native. Results are reported in chat.
- **Owned/changed paths:**
  - `scripts/benchmark_reports.py`
  - `scripts/report_benchmark_support.py`
  - `tests/test_report_benchmark.py`
  - `docs/benchmarks/AN01-M1.md`
  - this note

## Implemented

See [docs/benchmarks/AN01-M1.md](../benchmarks/AN01-M1.md).

- **The tagged statement registry:**
  - 7 operations, 22 SQL statements and 3 controls;
  - registry digest `2bf8b166…1f46`;
  - every statement scoped by tenant and session;
  - integer-string money and genuine unknowns.
- **Request rules:** zone, request and cursor rules with strict lookups and the r2 reference vectors.
- **A measurement-only budget/lease adapter:**
  - copied from `budget.py` at `a07ec12`, with recorded provenance;
  - a separate report registry;
  - reservations taken before connecting;
  - a ROLLBACK reserve measured to `B`.
- **The grid and rules:** the full pre-registered grid and rules 1–7 (the full profile refuses without authorization).
- **The supervisor:** owned run directories, checkpoint digest refusal, the independent whole-stage supervisor, `recover`, `cleanup` and the WSL-aware preflight.

## Verified

- **Focused tests:** `tests/test_report_benchmark.py`.
  - Windows: 64 passed at `f00df8c` (before the cleanup test).
  - Native: 64 passed at `f00df8c`. An earlier native run of 62 at `27acb84` also passed.
  - An owner-interrupted native run has an unknown result and is not counted.
- **Tiny smoke, both platforms at `f00df8c`:**
  - every platform stage is complete except native S6, where `C2:1250` failed: 1 of 5 server cancels missed the 30 ms reply margin;
  - S9 says "not demonstrated";
  - cleanup was verified on both platforms.
- **Failing-first evidence is preserved:** quantized Windows timings, the `BG:drill_cursor` InvalidCursor failure, the phase E index mismatch and the repeat-cleanup traceback.
- **Two Windows gate runs at `cd3517d` did not certify,** with evidence in `.agent/gate-failed-1/` and `-2/`:
  - run 1 was my backslash JUnit path (six checks passed, 875 + 1 allowed skip);
  - run 2 failed `test_c2...[400]`: a reply was noticed 1.27 ms after the work end, with its arrival time not recorded.

## Not verified / gaps

- **R-M1-1, reply margin.** It needs a design decision.
- **R-M1-2, Windows clock.** `time.monotonic` is coarse in accepted `budget.py`; noted only.
- **R-M1-3, disk bound.** The full grid exceeds the 4 GB cluster bound from S4, by estimate.
- **Not run:** the full-size grid, production S1 code and HTTP.

## Next action

Codex reviews the controller and resource evidence, including R-M1-1 and R-M1-3, before any separate full-size measurement assignment.

## Coordination and provenance

- **Reused unchanged:**
  - `scripts/local_stack.py` (identity and cluster ownership);
  - `sentinel.db.roles.grant_runtime`;
  - `sentinel.db.migrate`;
  - the v1 contract models;
  - the scoring artifacts.
- **Not touched:** src, contracts, migrations, locks, CI and central STATUS/TASK_QUEUE.
- **Preserved:** Cursor's edits and every other checkout.
- **Smoke records** live in the ignored `.agent/an01-m1/` (Windows) and `~/an01-m1-native/.agent/an01-m1/` (native).
- **Run data:** synthetic only; no credentials in public records.
