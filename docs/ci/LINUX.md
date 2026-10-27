# Linux readiness (N2 to N7)

Audience: whoever runs the backend checks on Linux (the `ubuntu-24.04` workflow or the local WSL2 Ubuntu). Local WSL runs are native Linux, but they are **not** a GitHub Actions run. The final candidate's Linux and Windows results are reported with its SHA in the handoff chat. This file records the fixes and the evidence gathered before that final commit.

## Evidence classes

| Class | Meaning |
| --- | --- |
| Windows native | Real processes and files on Windows 11 (CPython 3.11.3, PostgreSQL 14.17) |
| Native Linux | Ubuntu 24.04.3 on WSL2, unprivileged `sentinel` (UID 1000), managed CPython 3.11.14, PostgreSQL 16.15 |
| Simulated non-Windows launch (N2 only) | Real processes on Windows, with CPython's POSIX `Popen` argument checks applied inside one stand-in process |
| Injected | A patched failure or identity. Used by the neighbouring R12 tests listed below, and by N5's identity-change, missing-identity and group-refusal cases, which inject a stamp change or intercept destructive signals around a real stand-in. N3, N4, N6 and N7 use **no** injection |

## N2: the orphan test's Windows-only launch (accepted at 3c860d4)

The `ORPHANING` stand-in in `tests/test_local_stack_startup.py` now detaches with Windows flags on Windows and with `start_new_session=True` on POSIX. The gone-launcher R28A test runs as two variants:
- **`[native]`:** the host platform's real launch.
- **`[posix-launch]`:** the simulated boundary above.

**Results.** On Windows, the simulated variant failed before the fix with CPython's `creationflags is only supported on Windows platforms`. All six startup cases later passed natively on Linux (see `WSL_SETUP_RESULTS` on the coordination branch).

**Limitation.** On POSIX an orphan is reparented, so it is detected only while it holds the port. A non-listening orphan is undetected. This is disclosed and unchanged.

## N3: R12 deletion-refusal recovery runs on every platform

`test_r12_locked_file_keeps_state_loadable_and_retry_completes[api.log | pg/data/locked.bin]` used to be `skipif(os.name != "nt")`. On Linux both cases skipped, and the structured gate rejected them.

**The stimulus is now a real refusal on each platform.** The `deletion_refused` helper provides it:

| Platform | Stimulus |
| --- | --- |
| Windows (unchanged) | An open handle without `FILE_SHARE_DELETE`, which causes a sharing violation |
| POSIX | The owner removes write permission from the file's parent directory (`0o500`), restored in `finally` |

On POSIX an open file does not stop `unlink`. Directory permission is what controls it. Root ignores directory permissions, so the POSIX case asserts it is running unprivileged instead of passing vacuously.

**Assertions in both cases:**
- the first `stop` fails with `state_removed` false, naming the refused entry;
- the marker, the refused file and the manifest's owner, state directory and credentials are unchanged, and the stack still loads;
- the result contains no credential;
- once the fault is released, a plain retry succeeds and the exact owned directory is gone;
- an outside fake cluster's canary and an unrelated sibling directory survive;
- no process command runs: the `procs` fixture still intercepts subprocess calls and health probes;
- nothing credential-bearing is printed.

**Other R12 tests, kept unchanged.** Injected partial removal and marker-only leftover cover different recovery phases, with injected `rmtree` or `unlink` errors. The unowned-directory refusal is unchanged too.

**Evidence before the final commit:**
- *Native Linux at 3c860d4:* the R12 file plus `test_investigators.py` gave 36 passed and 3 skipped. `ci_test_gate.py --validate-only` exited **3**, naming exactly the two R12 skips as unexpected.
- *Native Linux with the new tests:* 38 passed and 1 skipped (the live-Claude test only). The gate exited 0, and both R12 cases ran and passed through real permission refusal.
- *Windows native:* both cases passed before and after, as the existing Windows coverage already did.

## N4: disposable PostgreSQL startup on Ubuntu

**The defect.** `sentinel.devdb.Cluster.start` set a port and `listen_addresses=127.0.0.1`, but inherited the server's Unix-socket default. Ubuntu's build uses `/var/run/postgresql`, which an unprivileged test user cannot write. So the server bound its TCP port and then exited with a permission-denied socket-lock error.

**The fix.** `Cluster.start` also passes `-c unix_socket_directories=`. An empty value disables Unix sockets ([PostgreSQL 16 connection settings](https://www.postgresql.org/docs/16/runtime-config-connection.html)), so the cluster is TCP-only on loopback. Every project client already connects through `Cluster.url()` or TCP URLs, including `pg_dump` and `pg_restore`.

Everything else is unchanged: port selection, loopback binding, trust authentication, the `-w` wait and `stop`. The fix makes no permission, group or root changes.

**The regression,** `tests/test_devdb_startup.py`, uses the real `Cluster.init`, `start` and `stop` and a loopback connection:
1. The cluster's own `postgresql.conf` sets `unix_socket_directories` to a test-owned unusable location:
   - on POSIX, a directory with mode `0o500`, restored in `finally`, with an asserted non-root user;
   - on Windows, a missing directory, which is real but whose path also exceeds PostgreSQL's 107-byte socket limit.
2. After `start`, a query must return `current_user = sentinel`, server address `127.0.0.1` and an empty `unix_socket_directories`.
3. No socket file may be created.
4. After `stop`, `pg_ctl status` must return 3 (no server running).

**Baseline before the fix, native on both platforms:**
- **Linux:** `FATAL: could not create lock file ".../socket-default/.s.PGSQL.<port>.lock": Permission denied`, the same failure class as `/var/run/postgresql`.
- **Windows:** `FATAL: could not create any Unix-domain sockets`.
- In both cases the server shut itself down; no process remained.

**After the fix:** the Windows focused set passed, 57 tests: devdb startup, the follow-up file, N2 startup, lifecycle, backup, rollback drill and browser fixtures. The Linux results are reported with the final SHA.

## The first full native Linux gate (476abcc) and what happened to each failure

The structured gate on accepted N3/N4 476abcc gave 430 passed, 5 failed and the one allowed live-Claude skip. The original report is kept, unedited, in the WSL clone at `/home/sentinel/n3-reports/final-full-junit.xml` (with `final-gate.log`).

| Original failure | Cause | Disposition |
| --- | --- | --- |
| `test_browser_fixtures::test_failed_start_cleans_up_processes_and_tokens[never_ready]` | N5: the POSIX stop sent only SIGTERM. The never-ready factory blocks after uvicorn's TERM handler is installed, so it never exits. Cleanup then hung in an unhandled 15 s `wait` | Fixed: verified SIGTERM, then SIGKILL to the same group |
| `test_browser_fixtures_review::test_r12_failed_start_keeps_recovery_manifest_when_cleanup_fails` | N5, as above | Fixed |
| `test_browser_fixtures_review::test_r12_api_stop_failure_keeps_recovery_state_and_retry_completes` | N6: the retry stops an API that pytest launched. The killed API stays a zombie until pytest reaps it, and its unchanged start stamp read as running ("did not stop") | Fixed: `/proc` state `Z`/`X` counts as exited |
| `test_model_browser_fixtures::test_scorer_switch_restarts_preserve_identity_and_replay` | N6: the `restart-api` CLI kills a pytest-launched API, the same zombie case | Fixed. The real CLI restart, model/rule identity and replay assertions are unchanged |
| `test_installed_wheel::test_wheel_installed_outside_the_checkout_binds_and_infers` | N7: offline `uv pip install -r requirements.txt` resolves `name==version` through registry index pages. A locked `uv sync` caches artifacts but never fetches those pages | Fixed: install the lock-exact `pylock.toml` (artifact URLs plus hashes) offline |

## N5: bounded, identity-verified API termination (`tests/support/browser_stack.py`)

**POSIX sequence.** `terminate_tree(pid, stamp)` first verifies that:
- the recorded start stamp still matches;
- the PID leads its own process group;
- that group is not the helper's own.

It then sends SIGTERM to the group and waits up to `TERM_GRACE_SECONDS` (10, using a monotonic clock). If the leader is still running, it re-verifies the same identity and group, then sends SIGKILL and waits up to `KILL_WAIT_SECONDS` (10).

**Refusals.** Each of these raises `StackError` with nothing (further) signalled, so `stop` reports failure and keeps the recovery manifest:
- a changed, missing or unknown identity at either boundary;
- a different group;
- a signal or permission error;
- a leader that exited while live members of its group remain.

**Windows.** Behaviour is unchanged (`taskkill /T /F`), but it now sits behind the same pre-signal identity check. The helper never kills by name.

**Regressions.** `tests/test_browser_stack_lifecycle.py` uses real stand-ins that print `ready` once their handlers are installed and `term` on the request, so the path taken is shown by what the process saw and by its exit status:

| Case | What it proves |
| --- | --- |
| Cooperative | Exits on SIGTERM (`-15`), with no escalation |
| TERM-resistant | Received `term`, survived, then was killed (`-9`) |
| Identity changed after the unanswered graceful wait | Refused with recovery kept; only SIGTERM was sent, and the stand-in is untouched |
| Missing identity, or a stand-in in the test's own group | Refused with no signal at all, even with a live launch handle |
| Leader exits but a TERM-ignoring member survives | Unresolved. Not escalated; the member is untouched |

**Same tests on Windows.** They exercise the forced-kill and pre-signal identity paths. The member case there asserts that the tree kill also stops the member.

**Results:**
- *Native Linux baseline on the test-only commit:* the lifecycle file gave 6 failed, 1 passed, for the intended reasons ("did not stop", "DID NOT RAISE", `TimeoutExpired` after signalling without identity, and a zombie start stamp). The four original lifecycle failures reproduced.
- *Windows baseline:* 3 failed (signalled despite a changed or missing identity), 4 passed.
- *After the fix:* the 73-test focused set (lifecycle, browser fixtures, review, follow-up, model fixtures, devdb startup, N2 startup, operator lifecycle) passed on both platforms, with no skips and no leftover processes.

## N6: exited zombies are not a running API

`process_start_time` parses the `/proc/<pid>/stat` state as well as the start stamp, after the last `)` so that a `comm` containing spaces or parentheses is safe. State `Z` or `X` returns None (exited).

**Unchanged cases:**
- A running process keeps its stamp.
- A missing process returns None.
- A process whose `/proc` cannot be read returns `0`, which never matches a recorded stamp. So it is never treated as a verified identity or killed.

**The regression** creates a real child that exits. It observes `Z` from `/proc` before reaping, without calling `poll` or `wait`, checks the helper returns None, and then always reaps the child. On Windows, the same test observes an exited process whose handle is still open.

## N7: the installed-wheel test no longer depends on an earlier online install

**Cold-cache reproduction.** This used a new task-owned `UV_CACHE_DIR` and project environment under `/home/sentinel/n7`; the shared cache and `.venv` were untouched. Steps on Ubuntu, in CI order:
1. `uv sync --locked --extra dev --extra ml` exited 0, leaving a 276 MB cache with **one** simple-index entry (`setuptools`, from the build).
2. The test's own steps:
   - `uv build` exited 0;
   - the pins export gave 26 pins;
   - `uv venv` exited 0;
   - `uv pip install --offline --no-deps -r requirements.txt <wheel>` exited **1**: `annotated-doc was not found in the cache and you require annotated-doc==0.0.5 … registry packages may only be read from the cache`.
3. The unchanged test then failed.

**Cause.** The `annotated-doc` wheel **was** cached (`wheels-v5/pypi/annotated-doc`). What was missing is the registry index metadata that a `name==version` resolution needs. A locked sync installs by the lock's URLs and hashes and never fetches it. `annotated-doc` is just the first pin alphabetically. The earlier full-run pass came only after `scripts/check_package.py`'s online install had written those index pages.

**Fix.** The test exports the lock as `pylock.toml` (each artifact's URL and sha256) and installs it with `--offline` into the same fresh venv, then installs the project wheel with `--offline --no-deps`. The `python -I` probe and every assertion are unchanged. There is no pin change, no network in the install or inference phase, and no workflow change.

**Proof:**
- On the same cold cache, the `pylock.toml` install exited 0. The installed set equals the marker-evaluated export pins (23 packages on Linux), and the isolated probe bound `hgb_balanced@p1`.
- On a **second** fresh cache, with only the locked sync before it, the committed test passed (1 passed, 6.2 s). The cache still held only the `setuptools` index entry afterwards.
- On Windows, the test passed on the existing warm cache. A cold cache was not tried there because of the limited C: space.

**Evidence and cleanup.** The full stderr and logs are in the WSL clone at `/home/sentinel/n5-reports/n7-evidence/` (`cold/` for the failing reproduction, `cold2/` for the passing proof). The task-owned caches and environments (625 MB) were removed after their ownership marker was verified and no process referenced them.

## Running in the local WSL clone

The clone is `/home/sentinel/agentforge-sentinel`, a verification checkout only.
- **Transfer a committed candidate.** Use a checksum-verified `git bundle`, then `git fetch <bundle> <branch>:refs/heads/<name>`. Check out detached only when the tree is clean and no pytest or postgres process is running. Do not change the global `safe.directory`.
- **Environment:**
  - `export PATH=$HOME/.local/bin:$PATH SENTINEL_PG_BIN=/usr/lib/postgresql/16/bin SENTINEL_LIVE_CLAUDE=0 SENTINEL_INVESTIGATOR=deterministic`;
  - unset `VIRTUAL_ENV` and `SENTINEL_TEST_DATABASE_URL`;
  - the existing Linux `.venv` is locked dev+ml. Never copy Windows `.venv` or `node_modules`.
- **Run order:** the focused tests, then the CI-equivalent sequence in `docs/ci/README.md`. Never run two full backend suites at once, including one on Windows and one on Linux.
