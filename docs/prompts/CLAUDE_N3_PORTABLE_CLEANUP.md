# Claude N3/N4: Linux cleanup coverage and disposable PostgreSQL startup

Read current main:AGENTS.md and latest task/coordination:docs/STATUS.md, docs/TASK_QUEUE.md, docs/reviews/3c860d4.md, docs/reviews/N4-linux-postgres-startup.md, docs/ci/WSL_SETUP_RESULTS.md and this prompt using git show. N2 3c860d4 is accepted for its bounded scope; no I03/N2 rewrite is assigned. Codex remains the owner-designated main integrator.

## Exact dependency and ownership

Create task/claude-linux-cleanup-tests in E:/PHANI/sentinel-wt/claude-linux-cleanup-tests from **3c860d4f1efa55c6d6e0bc28200b701afdfec837**. Inspect existing branches/paths before creating; refuse unexpected state instead of adopting/resetting it. Preserve main a456f51, accepted N2 and other accepted worktrees, and Cursor's saved edits. Coordination is the instructions reference, not this task's code dependency.

Own tests/test_browser_fixtures_followup.py, the narrow Cluster.start portability change in src/sentinel/devdb.py for N4, focused new/updated tests, docs/ci/LINUX.md and your handoff. Preserve other production source, scripts/local_stack.py, tests/support/browser_stack.py, contracts, model/data/evaluation artifacts, UI, lockfiles, skip-gate allowlist and main. This is an explicit ownership extension after a real Linux failure, not permission for a lifecycle redesign.

## Known defect and target behavior

test_r12_locked_file_keeps_state_loadable_and_retry_completes has a skipif(os.name != "nt") marker and two paths: api.log and pg/data/locked.bin. Both skip on Linux; the exact-one-live-skip gate rejects them. Do not delete this recovery coverage, add xfails/skips/exclusions or widen the allowlist.

Retain the actual Windows sharing-violation check. On POSIX, exercise an equivalent deletion refusal, with the same failure/retry assertions, using real owned filesystem permissions under a non-root user or a narrowly injected filesystem error if native execution is unavailable. Prefer native failure evidence once a suitable Linux environment exists. Clearly label injected evidence. POSIX opening a file alone does not stop unlinking it; do not simply remove the marker and keep the Windows stimulus unchanged.

Both path cases must prove: first stop fails and state_removed is false; marker and credential-bearing manifest remain owned and loadable; the retry succeeds once the fault is released; the exact owned directory is removed; canaries and unrelated directories survive; credentials are not printed. Restore every lock/permission/patch in finally. Preserve the procs fixture's interception of subprocess calls and health probes, so these cases do not touch a real server/service.

The neighbouring injected-partial-removal and marker-only tests cover different recovery phases: retain them. Test real recovery behavior and negative controls; a source-string assertion or a helper returning platform flags is insufficient. Keep baseline claims honest: existing Windows recovery already passes; N3 baseline evidence is the demonstrated two-skip gate failure. The separate native N4 startup baseline is now available. Demonstrate the current two-skip gate failure, then show the replacement cases actually execute rather than being hidden.

## N4: startup fails on actual Ubuntu (new finding)

The approved WSL setup is complete. At clean 3c860d4 as UID 1000, the six N2 startup cases passed, but the lifecycle suite's missing-factory case failed first at PostgreSQL startup. Cluster.start inherits Ubuntu's unwritable /var/run/postgresql Unix-socket default. A fresh owned diagnostic reproduced the failure; the same cluster started and accepted TCP connections when Unix sockets were explicitly disabled, then stopped cleanly. Read the N4 review and actual evidence before coding.

Fix only this disposable-cluster configuration boundary: choose an owned socket directory or disable Unix sockets for the established TCP-only cluster profile. Preserve Windows behavior, loopback-only binding, port selection and owned shutdown. No chmod/chown of system socket directories, root execution, extra privileges, database skips or model/contract changes. Add real failure-first startup/connect/stop coverage; on POSIX force the problematic default using a test-owned unwritable location and restore permissions. Retain meaningful Windows execution without a platform skip. A command-string-only test is not enough.

Implement N3 and N4 together on the assigned branch from 3c860d4, preserving any existing task edits. Do not change accepted N2. If a tested N3 candidate is already delivered, report its SHA rather than silently rewriting it.

## Environment and checks

- Locked dev+ml in this worktree; deterministic investigator, SENTINEL_LIVE_CLAUDE=0, no external test DB or another worktree's VIRTUAL_ENV. No provider call or new spending.
- Existing Ubuntu is now ready: user sentinel UID 1000, uv 0.9.26, Python 3.11.14, Node 22.23.4 and PostgreSQL 16.15. The clean verification clone is /home/sentinel/agentforge-sentinel at detached 3c860d4. Use it as a verification clone only after transferring your committed candidate and confirming no active run. Direct clone/fetch from the Windows mount triggered ownership checks; use a checksum-verified local Git bundle as recorded in WSL_SETUP_RESULTS, without global safe.directory changes. Leave Windows .venv/node_modules out of Linux. No new tool installation, user/default-user or global service/permission changes are assigned. Do not run two full backend suites concurrently.
- Run the entire changed follow-up file, relevant retained browser fixture tests as justified, N2 startup variants and Ruff. Prove failure/retry is exercised at both paths, and confirm no unexpected skips in the applicable report.
- On the final clean commit run the six-command strict gate. Capture JUnit from its same full pytest run (use a forward-slash absolute path in PYTEST_ADDOPTS), validate the exact skip policy and record collection/coverage. No duplicate full run solely for report format. Unchanged frontend/browser bytes do not require another frontend run for this narrow startup/test task. Use read-only ML reproduction as specified below; do not regenerate results.
- Run actual native Linux focused tests after N4, then the CI-equivalent structured full backend gate, helper/schema/HTTP/Node/package and read-only ML reproduction on the final candidate. Fix or report failures honestly; no frozen-result tuning, unexpected skips or root workarounds. Run final Windows strict validation too, sequentially with Linux. Report actual counts/platforms, native versus injected evidence and cleanup. A local Linux run is not a GitHub Actions run.

All new commits must be solely authored and committed by PHANI465 <pgavara1@asu.edu>, without Co-Authored-By or AI session trailers. Verify inherited project settings and actual commit metadata. Commit explicit owned paths and update the task handoff. Return exact base/final SHA, commands/exits/counts, evidence classes and remaining gaps. Do not merge main, push, alter accepted N2 or regenerate frozen results. Codex will review and integrate N2 plus N3/N4 together. Cursor can remain closed.
