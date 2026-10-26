# Handoff: task/claude-linux-readiness

- **Task:** N2 Linux readiness: the orphan test's Windows-only launch (docs/prompts/CLAUDE_N2_LINUX_READINESS.md on task/coordination 3f6f208; review docs/reviews/4fff776.md, N2).
- **Tool and worktree:** Claude Code, E:\PHANI\sentinel-wt\claude-linux-readiness (new; the branch and path did not exist before).
- **Updated:** 2026-10-26.
- **State:** ready for Codex review.
- **Base:** exact main a456f510d8053ce67b4334564d75225a756d923d. Main had not moved.
- **Commits:**
  - 5e366d8 is the failing-first regression;
  - the commit containing this note holds the fix, the Linux notes and this handoff.
- **Code reference tested before this note:** the fixed working tree on 5e366d8. The final strict, JUnit-gate results are for the final commit and are reported in chat.
- **Changed paths:**
  - `tests/test_local_stack_startup.py`;
  - `docs/ci/LINUX.md` (new);
  - `docs/ci/README.md`, the Linux evidence row only;
  - this note.

  Not changed: `src/`, `scripts/` (including `local_stack.py`), contracts, model, data and evaluation files, `web/`, lockfiles and central coordination files.

## Implemented

- **`ORPHANING` detaches per platform:**
  - Windows keeps the same flags (`DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`);
  - POSIX uses `start_new_session=True`.
- **`POSIX_LAUNCH` boundary.** A stand-in prelude that applies CPython's POSIX `Popen` argument checks inside that one process. On Windows it maps `start_new_session` to the equivalent real detached launch; on POSIX it passes through. `os.name` is never patched.
- **The gone-launcher R28A test runs as `[native]` and `[posix-launch]`.** Its assertions are unchanged: a real orphan listener, an unresolved record, `down` exit 1, no kill or database stop, and the orphan untouched. The launcher's stderr goes to a file, so a failed launch reports its real error.

## Verified (Windows 11, CPython 3.11.3, locked dev+ml)

Settings: `SENTINEL_LIVE_CLAUDE=0`, `SENTINEL_INVESTIGATOR=deterministic`, `VIRTUAL_ENV` and `SENTINEL_TEST_DATABASE_URL` unset.

- **Baseline on 5e366d8** (regression only, old `ORPHANING`): **1 failed, 5 passed.** The `[posix-launch]` failure was `ValueError: creationflags is only supported on Windows platforms`, raised by the stand-in's `Popen` before any orphan PID existed. There was no import or symbol error.
- **After the fix:** `pytest -v tests/test_local_stack_startup.py tests/test_local_stack.py` gave **14 passed** in 42 s. Ruff passed.
- **Cleanup:** a process query found no stand-in (`sleep(600)` or `serve_forever`) left running.
- **Evidence classes:** `[native]` is Windows-native evidence. `[posix-launch]` on Windows is **simulated** non-Windows launch evidence, with real processes, PID and port. Neither is native Linux.

## Not verified / gaps

- **Native Linux was not run.** The read-only WSL inspection found:
  - Ubuntu 24.04.3 with only a **root** default user and no non-root account;
  - no uv, no `python3-venv`/`ensurepip`, no Python 3.11, no PostgreSQL and no native Node.

  Installing those is outside this task. The exact prerequisites and setup plan are in `docs/ci/LINUX.md`. Ubuntu was restored to Stopped.
- **Second Linux gate blocker, outside N2 ownership:** `tests/test_browser_fixtures_followup.py:170` (`test_r12_locked_file...`) has `skipif(os.name != "nt")`. Its two cases would skip on Linux, and the structured gate rejects them. The proposed narrow fix is in `docs/ci/LINUX.md`.
- **POSIX orphan detection:** detection relies on the port. A non-listening reparented orphan is undetected (disclosed and unchanged).
- **Not run:** GitHub Actions and macOS.

## Next action

Codex: review N2. Then assign the R12 POSIX test fix, and get the owner's decision on the WSL setup or a remote for a real Linux run.

## Coordination and provenance

`POSIX_LAUNCH` mirrors the argument checks in CPython 3.11's `Lib/subprocess.py` POSIX branch (PSF license). It is reimplemented, not copied. There are no credentials or raw logs.
