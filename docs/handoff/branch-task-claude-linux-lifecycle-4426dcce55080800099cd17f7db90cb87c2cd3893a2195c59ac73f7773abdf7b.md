# Handoff: task/claude-linux-lifecycle

- **Task:** N5/N6/N7 (docs/prompts/CLAUDE_N5_LINUX_LIFECYCLE.md on task/coordination 914cfef; review docs/reviews/476abcc.md):
  - N5: bounded, identity-verified API termination;
  - N6: zombie-aware identity;
  - N7: the installed-wheel test's hidden cache-order dependence.
- **Tool and worktree:** Claude Code, E:\PHANI\sentinel-wt\claude-linux-lifecycle (new; the branch and path did not exist before).
- **Updated:** 2026-10-26.
- **State:** ready for Codex review.
- **Base:** exact accepted N3/N4 476abccc52b5228f71e129f8e3d0a8d9f11bef41. No merge or rebase. Main a456f51, N2 3c860d4 and N3/N4 476abcc are preserved.
- **Commits:**
  - 711fa24: failing-first lifecycle regressions;
  - 88339c9: the N5/N6 fix;
  - 9d60c2c: the N7 fix;
  - the commit containing this note: docs and this handoff.
- **Code reference tested before this note:** 9d60c2c (code), with these docs uncommitted. The final Windows strict and native Linux CI-equivalent results are for the final commit and are reported in chat.
- **Changed paths:**
  - `tests/support/browser_stack.py`: `process_start_time`, `_group_members`, `terminate_tree` and `stop_api`, plus two bound constants;
  - `tests/test_browser_stack_lifecycle.py` (new);
  - `tests/test_browser_fixtures_review.py`: the cleanup helper passes the stamp;
  - `tests/test_installed_wheel.py`;
  - `docs/ci/LINUX.md`, `docs/ci/README.md` and `docs/api/browser-fixtures.md`;
  - this note.

  Not changed: production `src/`, `scripts/` (`local_stack.py`, `check_package.py`), the workflow, the gate allowlist, checker timeouts, contracts, model/data/evaluation files, `web/`, lockfiles and central coordination.

## Original native Linux failures (476abcc full gate: 430 passed, 5 failed, 1 allowed skip)

| Original failure | Group | Disposition |
| --- | --- | --- |
| `test_failed_start_cleans_up_processes_and_tokens[never_ready]` | N5 | Fixed |
| `test_r12_failed_start_keeps_recovery_manifest_when_cleanup_fails` | N5 | Fixed |
| `test_r12_api_stop_failure_keeps_recovery_state_and_retry_completes` | N6 | Fixed |
| `test_scorer_switch_restarts_preserve_identity_and_replay` | N6 | Fixed |
| `test_wheel_installed_outside_the_checkout_binds_and_infers` | N7 | Fixed |

The original report is kept unedited at `/home/sentinel/n3-reports/final-full-junit.xml`. Causes and details are in `docs/ci/LINUX.md`.

## Verified before the final commit

Settings throughout: locked dev+ml, `SENTINEL_LIVE_CLAUDE=0`, deterministic investigator, no external test DB, `VIRTUAL_ENV` unset.

**Native Linux:** Ubuntu 24.04.3 WSL2, `sentinel` UID 1000, CPython 3.11.14, PostgreSQL 16.15. The clone was checked out from checksum-verified bundles, with a clean tree and no active run.
- *Baseline at 711fa24:* the lifecycle file gave 6 failed, 1 passed, for the intended reasons. The 4 original lifecycle failures reproduced (4 failed, 1 passed). The leftover 2 never-ready uvicorn processes and 2 clusters were stopped by exact identity.
- *At 88339c9:* the focused set gave **73 passed**, with no skips and no leftovers.
- *N7 cold cache* (task-owned cache and environment):
  - on the unchanged test, the offline install exited 1 with `annotated-doc was not found in the cache`. The wheel was cached, but only one simple-index entry existed;
  - the `pylock.toml` offline install exited 0, matching the evaluated pins (23 packages);
  - *at 9d60c2c,* on a second fresh cache, the test passed right after the locked sync.
  - Evidence: `/home/sentinel/n5-reports/n7-evidence/`. The 625 MB of task-owned caches was removed.

**Windows 11, CPython 3.11.3, PostgreSQL 14.17:**
- *Baseline at 711fa24:* 3 failed (signalled despite a changed or missing identity), 4 passed.
- *After the fix:* the same focused set gave **73 passed**; ruff passed; no leftovers. `test_installed_wheel` passed on the warm cache (not a cold proof).

## Not verified / gaps

- **Not run:** GitHub Actions and macOS. On non-Linux POSIX the stop refuses because no `/proc` stamp is available.
- **Windows cold cache:** not tried, because C: space is limited (about 5 GB free).
- **Disclosed limits, unchanged:** the PID check-to-signal race; `scripts/local_stack.py`'s own POSIX orphan limits are untouched.
- **`scripts/check_package.py`:** it still installs online (unchanged, outside ownership). Only the test is offline.

## Next action

Codex: review N5/N6/N7 and batch-integrate N2 to N7.

## Coordination and provenance

`pylock.toml` is the PEP 751 lock format exported by uv 0.9.26. There are no credentials, tokens or raw manifests in tracked files.
