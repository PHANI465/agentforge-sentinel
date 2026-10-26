# Handoff: task/claude-linux-cleanup-tests

- **Task:** combined N3/N4, per docs/prompts/CLAUDE_N3_PORTABLE_CLEANUP.md on task/coordination cafe6ea (reviews 3c860d4 and N4-linux-postgres-startup; WSL_SETUP_RESULTS):
  - N3: R12 deletion-refusal recovery runs on every platform;
  - N4: disposable PostgreSQL starts on Ubuntu without the system socket directory.
- **Tool and worktree:** Claude Code, E:\PHANI\sentinel-wt\claude-linux-cleanup-tests (new; the branch and path did not exist before).
- **Updated:** 2026-10-26.
- **State:** ready for Codex review.
- **Base:** exact accepted N2 3c860d4f1efa55c6d6e0bc28200b701afdfec837. No merge or rebase. N2, main a456f51 and the other accepted worktrees are untouched.
- **Commits:**
  - b06b6a1 holds the failing-first tests;
  - the commit containing this note holds the fix and the docs.
- **Code reference tested before this note:** b06b6a1 plus the `devdb.py` fix (working tree). The final Windows strict and native Linux CI-equivalent results are for the final commit and are reported in chat.
- **Changed paths:**
  - `src/sentinel/devdb.py`, `Cluster.start` only;
  - `tests/test_devdb_startup.py` (new);
  - `tests/test_browser_fixtures_followup.py`, the R12 locked-file test and its helper only;
  - `docs/ci/LINUX.md`;
  - this note.

  Not changed: `scripts/local_stack.py`, `tests/support/browser_stack.py`, the gate allowlist, contracts, model/data/evaluation files, `web/`, lockfiles and central coordination.

## Implemented

- **N4.** `Cluster.start` adds `-c unix_socket_directories=`, which makes the cluster TCP-only on loopback. Port, binding, wait and stop are unchanged.
- **N4 regression** (`test_devdb_startup.py`):
  - the cluster's own config names an unusable socket default: a test-owned `0o500` directory on POSIX, restored in `finally`, or a missing path on Windows;
  - the real `start`, connection (user, `127.0.0.1`, empty socket setting), `stop` and `pg_ctl status` 3 must all succeed.
- **N3.** The R12 locked-file test has no platform skip. `deletion_refused` keeps the Windows sharing-violation handle; on POSIX it removes the parent directory's write permission, restored in `finally`, with an asserted non-root user.
- **N3 assertions:**
  - first-stop failure, with `state_removed` false and the refused entry named;
  - marker, refused file, owner, state directory and credentials preserved; the stack still loads;
  - no credential in the result or the output;
  - the retry succeeds once the fault is released, and the exact directory is removed;
  - the outside canary and an unrelated sibling survive;
  - no process calls are made.
- **Kept unchanged:** the injected partial-removal and marker-only tests.

## Verified before the final commit

- **Windows 11, CPython 3.11.3, PostgreSQL 14.17, locked dev+ml.** Settings: `SENTINEL_LIVE_CLAUDE=0`, deterministic investigator, no external test DB, `VIRTUAL_ENV` unset.
  - Baseline at b06b6a1: `test_devdb_startup` **failed** with `FATAL: could not create any Unix-domain sockets`. The new R12 cases passed, as Windows recovery already did.
  - After the fix: 57 passed across the focused set (devdb startup, follow-up, N2 startup, lifecycle, backup, rollback drill, browser fixtures and review). Ruff passed.
- **Native Linux:** Ubuntu 24.04.3 WSL2, `sentinel` UID 1000, CPython 3.11.14, PostgreSQL 16.15. The clone was checked out from a checksum-verified bundle, with a clean tree and no active run.
  - *At 3c860d4:* the R12 file plus the live-skip module gave 36 passed and 3 skipped. `ci_test_gate.py --validate-only` exited **3**, naming exactly the two R12 skips.
  - *At b06b6a1:* 38 passed and 1 skipped (live Claude only), and the gate exited 0. Both R12 cases **passed through real permission refusal**.
  - *N4 baseline at b06b6a1:* `test_devdb_startup` failed with `could not create lock file ".../socket-default/.s.PGSQL.<port>.lock": Permission denied`. No postgres process remained.

## Not verified / gaps

- **Not run:** GitHub Actions and macOS. The local WSL run is native Linux, not CI.
- **POSIX operator limits** are unchanged: non-listening orphan detection and the PID check-to-kill window.
- **Root:** the N3 and N4 POSIX cases need an unprivileged user and fail clearly under root, as intended.

## Next action

Codex: review N2 together with N3/N4, then integrate.

## Coordination and provenance

The PostgreSQL socket setting semantics come from the PostgreSQL 16 documentation, which is linked in `docs/ci/LINUX.md`. There are no credentials or raw logs.
