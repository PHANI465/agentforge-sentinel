# Handoff: task/claude-an01-m1-prototype

- **Task and acceptance criteria:**
  - current: `task/coordination:docs/prompts/CLAUDE_AN01_M1_FINAL_CLOSE.md`, the residual R56 interrupt inside close, under the binding review `docs/reviews/AN01-M1-b54de1a.md`;
  - earlier: `CLAUDE_AN01_M1_R2_FOLLOWUP.md` (R54/R56), `CLAUDE_AN01_M1_REVIEW_FIXES.md` (R53–R57) and `CLAUDE_AN01_M1_IMPLEMENTATION.md`.

  Prototype code and tiny proofs only. DOC01 is not started here.
- **Tool and worktree:** Claude Code, `E:/PHANI/sentinel-wt/claude-an01-m1-prototype`, from accepted main `a07ec12710c86b15f111d13e3384c4cf0c6c8f6e`. Native clone: WSL `~/an01-m1-native`, fast-forwarded from git bundles of this branch.
- **Updated:** 2026-11-10 (America/Phoenix).
- **State:** the final-close correction is delivered for Codex re-review. Not accepted and not merged.
  - `b54de1a4ebb4401b2149035abaeac6678e95d64c`, `5e0a578`, `93583a7` and their ancestors are preserved: no reset, amend or rebase.
- **Code reference tested before this note:** `a82494c07d0e655ad04f74f7ebfbb6090e094b2e`.
  - The probes and both focused suites ran at that commit, on Windows and native.
  - This note's commit changes documentation only.
- **Final check evidence:** the six-command gates and the JUnit, HTTP, package and ML checks run on the final commit, Windows then native. Results are reported in chat.
- **Owned/changed paths:**
  - `scripts/report_benchmark_support.py` (`ReportQuarantine`, `ReportConnection` only)
  - `tests/test_report_benchmark_review.py`
  - `docs/benchmarks/AN01-M1.md`
  - this note

## Implemented (see [AN01-M1.md §5d](../benchmarks/AN01-M1.md))

- **R56, interrupt inside close:**
  - the owner is registered in the report quarantine when the state becomes `"closing"`, before `conn.close()` is called;
  - `_do_close` treats any exception from close, interrupts included, as `close_failed` (class name only), keeps the owner and the reservation, then re-raises the interrupt unchanged;
  - a confirmed close sets `"closed"`, releases the reservation once, then removes the entry;
  - `ReportQuarantine.owner(conn)` reaches the owner for an explicit `retry_close()`, because an interrupted request returns no `Outcome`.

## Verified

- **Failing first, on unchanged `b54de1a` (Windows):** 8 failed and 84 passed.
  - 6 are intended AssertionErrors: KeyboardInterrupt and SystemExit for close, retry and final close.
  - 2 are AttributeErrors for the new `owner()` entry point; they are not counted.
  - Codex's unmasked probe on that checkout gave 10/2/0.
- **At `a82494c`:**
  - Codex unmasked 12: 12/0/0 on both platforms;
  - Codex adapted 14: 14/0/0 on both;
  - focused tests (66 + 92): 158 passed on Windows and 158 passed on native, real PostgreSQL.
- **Probe sources unchanged:** unmasked `1109eb69…`, adapted `7efd534f…`. Codex's canonical `.agent/an01-m1-r3-review/` was only read.
- **Cleanup:** no PostgreSQL process of mine remained on either platform; the native clone is clean.

## Not verified / gaps

- **No new tiny smoke or benchmark** ran on this correction, by assignment. The `af6292f` records stay bound to the old source hash and are historical.
- **Bytecode-level interrupt windows** (untested):
  - an interrupt just after `close()` returns but before `"closed"` keeps the owner and the reservation until process exit;
  - an interrupt between the reservation release and the entry removal leaves a stale entry for a connection that is closed.
- **Still failed and preserved:** the `af6292f` Windows C2:400 miss (S9 not demonstrated), the `f00df8c` native C2:1250 miss, and the unexplained Windows focused stall failure.
- **Unchanged and still open:** R-M1-1 (margin), R-M1-2 (production clock) and R-M1-3 (4 GB and backing-space refusals).
- **Not run:** the full grid, production S1 code and HTTP, and DOC01.

## Next action

Codex re-reviews the exact final SHA reported in chat.

## Coordination and provenance

- **Reused unchanged:**
  - `scripts/benchmark_reports.py`, `scripts/local_stack.py` and the R54 evidence code;
  - production `src`, contracts, migrations and grants;
  - Codex's probe sources in `.agent/an01-m1-r3-review/` (canonical copy in the main checkout), run unmodified through `AN01_REVIEW_ROOT`.
- **Not touched:** src, contracts, migrations, locks, CI, timeouts, skips and central STATUS/TASK_QUEUE.
- **Preserved:** Cursor's edits and every other checkout.
- **Evidence** is in the ignored `.agent/an01-m1-r4/`:
  - `failing-first-windows/` (the test file as run, sha256 `1164f8af…`);
  - `probes-unchanged-windows/`, `probes-windows/` and `focused-windows/`;
  - `native/`, with its script and bundle.

  Earlier evidence is kept in `.agent/an01-m1/`, `.agent/an01-m1-r2/`, `.agent/an01-m1-r3/` and `.agent/gate-*`, and natively in `~/an01-m1-native/.agent/`.
- **Run data:** synthetic only; no credentials in public records.
