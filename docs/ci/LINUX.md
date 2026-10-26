# Linux readiness (N2, N3, N4)

Audience: whoever runs the backend checks on Linux (the `ubuntu-24.04` workflow or the local WSL2 Ubuntu). Local WSL runs are native Linux, but they are **not** a GitHub Actions run. The final candidate's Linux and Windows results are reported with its SHA in the handoff chat. This file records the fixes and the evidence gathered before that final commit.

## Evidence classes

| Class | Meaning |
| --- | --- |
| Windows native | Real processes and files on Windows 11 (CPython 3.11.3, PostgreSQL 14.17) |
| Native Linux | Ubuntu 24.04.3 on WSL2, unprivileged `sentinel` (UID 1000), managed CPython 3.11.14, PostgreSQL 16.15 |
| Simulated non-Windows launch (N2 only) | Real processes on Windows, with CPython's POSIX `Popen` argument checks applied inside one stand-in process |
| Injected | A patched failure, used only by the neighbouring R12 tests listed below. N3 and N4 use **no** injection |

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

## Running in the local WSL clone

The clone is `/home/sentinel/agentforge-sentinel`, a verification checkout only.
- **Transfer a committed candidate.** Use a checksum-verified `git bundle`, then `git fetch <bundle> <branch>:refs/heads/<name>`. Check out detached only when the tree is clean and no pytest or postgres process is running. Do not change the global `safe.directory`.
- **Environment:**
  - `export PATH=$HOME/.local/bin:$PATH SENTINEL_PG_BIN=/usr/lib/postgresql/16/bin SENTINEL_LIVE_CLAUDE=0 SENTINEL_INVESTIGATOR=deterministic`;
  - unset `VIRTUAL_ENV` and `SENTINEL_TEST_DATABASE_URL`;
  - the existing Linux `.venv` is locked dev+ml. Never copy Windows `.venv` or `node_modules`.
- **Run order:** the focused tests, then the CI-equivalent sequence in `docs/ci/README.md`. Never run two full backend suites at once, including one on Windows and one on Linux.
