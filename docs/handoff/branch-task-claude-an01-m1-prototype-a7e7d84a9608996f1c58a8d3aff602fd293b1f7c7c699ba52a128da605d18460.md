# Handoff: task/claude-an01-m1-prototype

- **Task and acceptance criteria:**
  - current: `task/coordination:docs/prompts/CLAUDE_AN01_M1_REVIEW_FIXES.md` (R53–R57), under the binding review `docs/reviews/AN01-M1-93583a.md`;
  - original: `docs/prompts/CLAUDE_AN01_M1_IMPLEMENTATION.md`.

  Prototype code and tiny proofs only. The full-size benchmark is not run.
- **Tool and worktree:** Claude Code, `E:/PHANI/sentinel-wt/claude-an01-m1-prototype`, from accepted main `a07ec12710c86b15f111d13e3384c4cf0c6c8f6e`. Native clone: WSL `~/an01-m1-native`, fast-forwarded from git bundles of this branch.
- **Updated:** 2026-11-08 (America/Phoenix).
- **State:** R53–R57 corrections delivered for Codex review. Not accepted and not merged.
  - Delivered candidate `93583a7570ae78f254a2d69e9857b701b0e444ad` and its ancestors are preserved: no reset, amend or rebase.
- **Code reference tested before this note:** `73984b902e4e05baed7a3b54394664682fea970b`.
  - The tiny smoke, the probes and the focused tests on both platforms ran at that commit.
  - The note's own commit changes documentation only, so the source and statement identities are unchanged.
- **Final check evidence:** the six-command gates and the JUnit, HTTP, package and ML checks run on the final commit, Windows then native. Results are reported in chat.
- **Owned/changed paths:**
  - `scripts/benchmark_reports.py`
  - `scripts/report_benchmark_support.py`
  - `tests/test_report_benchmark.py`
  - `tests/test_report_benchmark_review.py` (new)
  - `docs/benchmarks/AN01-M1.md`
  - this note

## Implemented

See [docs/benchmarks/AN01-M1.md §5b](../benchmarks/AN01-M1.md).

- **R53:**
  - an OS-released run slot, held by every stage, recover and cleanup invocation;
  - an invocation-bound run lock (identity and token), removed only by its owner;
  - recovery refuses a live or unverifiable holder;
  - a recorded hand-off after unconfirmed cleanup;
  - a lock release that the interrupted controller performs only when no worker was ever recorded.
- **R54:**
  - schema-2 typed records, bound to the code identities, the profile and the windows/linux pair;
  - duplicates and conflicts are refused;
  - registered counts and finite metrics are required;
  - the ROLLBACK > 50% of R trigger, with measured `rollback_ms`;
  - bound, digested selections, consumed only when demonstrated.
- **R55:**
  - a budget recheck after arming;
  - `BudgetExpired` before any thread for a non-positive wait;
  - `late_reply` by arrival;
  - the armed deadline counted from submission.

  B, R, `work_end` and the 30 ms margin are unchanged.
- **R56:**
  - ownership from acquisition, hooks included;
  - `close_failed` keeps its reservation and owner, with `retry_close`;
  - an interrupt hands a busy connection to its lease;
  - unique lease users.
- **R57:**
  - one snapshot-bound `read_at` in the SQL and the DTO;
  - an explicit `as_of` is kept, and a default one is bound;
  - cursors repeat the resolved `as_of`;
  - a `rollback_unanswered` report keeps its body.
- **Also fixed:** a Windows sharing-violation retry for the state and lock files. It had crashed a live controller under a concurrent reader.

## Verified

- **Failing first, on unchanged `93583a` (Windows):**
  - 42 failed and 15 passed. Of the failures, 41 are defect evidence (39 assertions and 2 rule crashes) and 1 is a new-API test;
  - Codex's probes gave 11/3/0.
- **Codex probes on `73984b9`, both platforms:**
  - unchanged: 13/1/0. The one failure is a mocked-outcome interface difference, explained in §5b;
  - one-line adapted copy: 14/0/0;
  - the adapted copy on exported `93583a`: 11/3/0.
- **Focused tests** (66 + 57): Windows 123 passed; native 123 passed on real PostgreSQL.
- **Tiny smoke at `73984b9`:**
  - Windows then native, every platform stage complete;
  - S3 picks A, S7 gives N\* = 80, S9 says "mandatory evidence present";
  - rule 3 is demonstrated with no triggers;
  - all 14 records carry identical identities;
  - cleanup was verified on both platforms.

## Not verified / gaps

- **R-M1-1:** the policy is unchanged and the margin is not qualified. The smallest Windows slack was 4.7 ms, and the `f00df8c` native C2:1250 failure stays recorded.
- **R-M1-2:** production `budget.py` clock coarseness was not changed (not assigned).
- **R-M1-3:** the 4 GB and backing-space preflight refusals are kept. A full grid needs its own storage and scheduling plan.
- **Not run:**
  - my maintained tests, natively against `93583a`. Codex's native probes are the native failing-first evidence;
  - the full grid;
  - production S1 code and HTTP.
- **Recovery refuses old `93583a`-format locks**, which have no invocation identity; they need manual inspection.

## Next action

Codex reviews the exact corrected SHA reported in chat before integration or any further assignment.

## Coordination and provenance

- **Reused unchanged:**
  - `scripts/local_stack.py` (identity, classify, cluster ownership);
  - `sentinel.db.roles.grant_runtime`;
  - `sentinel.db.migrate`;
  - the v1 contract models;
  - the scoring artifacts;
  - Codex's probe source. Its original is unchanged; the one-line adapted copy and its diff are under `.agent/an01-m1-r2/probes/`.
- **Not touched:** src, contracts, migrations, locks, CI, checker limits and central STATUS/TASK_QUEUE.
- **Preserved:** Cursor's edits and every other checkout.
- **Evidence** is in the ignored `.agent/an01-m1-r2/`:
  - failing-first runs;
  - probes;
  - focused runs;
  - smoke run directories, records and logs;
  - cleanup output.

  The `f00df8c` and `93583a` evidence in `.agent/an01-m1/` and `.agent/gate-*` is kept, along with the native `~/an01-m1-native/.agent/`.
- **Run data:** synthetic only; no credentials in public records.
