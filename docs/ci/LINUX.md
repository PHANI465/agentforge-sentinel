# Linux readiness (N2)

Audience: whoever runs the backend checks on Linux (the `ubuntu-24.04` workflow or a local WSL2 Ubuntu). The suite has been executed on **Windows 11 only**. Nothing here is a Linux pass.

## Evidence classes

| Class | Meaning | What it covers |
| --- | --- | --- |
| Windows native | Real processes on Windows 11 | The full suite through the strict checker; all R28 startup and lifecycle tests |
| Simulated non-Windows launch | Real processes on Windows, with CPython's POSIX `Popen` argument checks applied inside one stand-in process | The orphan test's launch arguments are accepted by a POSIX `Popen`, and its real PID, port, refusal and cleanup still hold |
| Native Linux | A real Linux interpreter, `/proc` and PostgreSQL | **Not executed.** The environment is missing (see below) |

## Fixed: the orphan test's Windows-only launch

`tests/test_local_stack_startup.py` has an `ORPHANING` stand-in, which starts a detached listener and exits. It used to pass Windows `creationflags` unconditionally. On Linux, CPython raises `ValueError: creationflags is only supported on Windows platforms` before the orphan PID is printed, so the test failed there.

**The fix.** The stand-in now detaches with the same Windows flags on Windows and with `start_new_session=True` on POSIX. The test now runs twice:
- **`native`:** the host platform's real launch.
- **`posix-launch`:** the `POSIX_LAUNCH` boundary is prepended to the stand-in. Within that process only, `Popen` rejects `creationflags` and `startupinfo` exactly as CPython's POSIX branch does (`Lib/subprocess.py`).
  - On Windows it then turns `start_new_session` into the equivalent real detached launch.
  - On Linux it simply passes `start_new_session` through.
  - `os.name` is never patched.

**What both variants assert.** The R28A behavior is unchanged:
- startup exits nonzero and keeps an unresolved launch record;
- the orphan really listens on the port;
- `down` exits 1 without killing anything or stopping the database;
- the orphan is untouched until the test stops it by the PID its parent reported.

**Evidence on Windows 11, CPython 3.11.3:**
- **Before the fix,** committed as the failing-first regression: `posix-launch` failed with exactly `ValueError: creationflags is only supported on Windows platforms`, raised from the stand-in's `Popen` before any orphan PID was produced. The other 5 tests passed.
- **After the fix:** all 6 startup tests and the 8 lifecycle tests passed, 14 in total, with no stand-in left running.

**What this does not establish on POSIX.** On Linux an orphan is reparented, so this test is unresolved only because the orphan still holds the port, not because of its process tree. An orphan that does not listen would go undetected. That is the disclosed POSIX operator limitation, and this task does not change it.

## Open: a second Linux CI blocker (not in N2's file ownership)

`tests/test_browser_fixtures_followup.py:170`, `test_r12_locked_file_keeps_state_loadable_and_retry_completes`, is marked `skipif(os.name != "nt")`.

**Why it blocks CI.** On Linux its two parametrized cases skip. The structured gate permits only the live-Claude skip, so the Ubuntu workflow's Tests step would fail even when every test passes.

**Proposed narrow fix** (needs assignment, because the file is outside N2 ownership):
- give the test a POSIX way to cause a real partial-removal failure, for example a directory made read-only (`chmod 0o500`) under a non-root runner, and restore permissions in `finally`;
- alternatively, replace the Windows lock with an injected `rmtree` failure, as the neighbouring R12 test does, on all platforms.

Either way, no new skip is added and the gate's allowlist stays unchanged. Root ignores directory permissions, so the first option needs a non-root user, which the GitHub runner provides.

A static scan of `tests/` found no other Windows-only skip. The remaining `os.name` branches have POSIX alternatives, but those are unexecuted.

## Local WSL2 Ubuntu: what exists (read-only inspection, 2026-10-26)

Ubuntu was stopped before the inspection. It was started only to run the read-only commands, then returned to Stopped with `wsl --terminate Ubuntu`. Nothing was installed or configured.

| Item | Found |
| --- | --- |
| Distribution | Ubuntu 24.04.3 LTS, WSL2, kernel 5.15.167.4-microsoft-standard-WSL2, systemd enabled |
| Default user | **root** (uid 0). There is no non-root account (uid 1000 or above) |
| Python | System 3.12.3. **Missing:** `python3.11`, the `venv`/`ensurepip` modules (no `python3-venv`) and **uv** |
| PostgreSQL | **Missing:** no `/usr/lib/postgresql/*/bin`, `initdb`, `pg_ctl` or `psql` |
| Node | **Missing natively.** `npm` resolves only to the Windows install through interop |
| Other | `git` and `sudo` are present; `gcc` is missing. The Windows `E:` drive is visible at `/mnt/e` |

**Why it cannot run the suite as is:**
- PostgreSQL `initdb` refuses to run as root, and the tests start their own clusters, so a non-root user is required.
- uv (or at least `venv`) is required to build the locked environment.
- PostgreSQL binaries are required.

## Setup plan (owner action; no paid service)

1. **As root in Ubuntu, install the packages:**
   - `apt-get update && apt-get install -y --no-install-recommends postgresql curl ca-certificates`;
   - tests use only their own disposable clusters, so the packaged service can stay disabled: `systemctl disable --now postgresql`.
2. **Create a non-root user,** for example `adduser sentinel`. Optionally make it the default user in `/etc/wsl.conf` (`[user] default=sentinel`); that changes WSL configuration and is the owner's choice.
3. **As that user, install uv 0.9.26:** `curl -LsSf https://astral.sh/uv/0.9.26/install.sh | sh`. uv provides Python 3.11 itself.
4. **Use a local clone on the Linux filesystem, not `/mnt/e`** (`/mnt/e` gives slow I/O and Windows permission semantics):
   - `git clone /mnt/e/PHANI/agentforge-sentinel ~/sentinel`, then `git checkout <candidate SHA>`.
   - The clone's `origin` points at the local Windows path; no network remote is created.
5. **Run the checks:**
   - `export SENTINEL_PG_BIN=$(ls -d /usr/lib/postgresql/*/bin | sort -V | tail -1) SENTINEL_LIVE_CLAUDE=0 SENTINEL_INVESTIGATOR=deterministic`, then `uv sync --locked --extra dev --extra ml`;
   - first `uv run --locked python -m pytest -v tests/test_local_stack_startup.py tests/test_local_stack.py`, then the full `scripts/ci_test_gate.py --junit pytest-results.xml`.
   - The full gate will fail on the R12 skip above until that test is fixed.
6. **For the workflow's Node transport check,** install Node 22 inside Ubuntu (for example the NodeSource or nvm package). The Windows `npm` reached through interop is not a Linux run.

The GitHub `ubuntu-24.04` runner already provides a non-root user with sudo, and the workflow installs PostgreSQL. Running it needs a Git remote, which is an owner decision.
