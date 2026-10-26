# Claude N3: portable cleanup-failure coverage

Read current main:AGENTS.md and latest task/coordination:docs/STATUS.md, docs/TASK_QUEUE.md, docs/reviews/3c860d4.md and this prompt using git show. N2 3c860d4 is accepted for its bounded scope; no I03/N2 rewrite is assigned. Codex remains the owner-designated main integrator.

## Exact dependency and ownership

Create task/claude-linux-cleanup-tests in E:/PHANI/sentinel-wt/claude-linux-cleanup-tests from **3c860d4f1efa55c6d6e0bc28200b701afdfec837**. Inspect existing branches/paths before creating; refuse unexpected state instead of adopting/resetting it. Preserve main a456f51, accepted N2 and other accepted worktrees, and Cursor's saved edits. Coordination is the instructions reference, not this task's code dependency.

Own tests/test_browser_fixtures_followup.py, narrowly needed test-only helpers, docs/ci/LINUX.md and your handoff. Keep production src/, scripts/, tests/support/browser_stack.py, contracts, model/data/evaluation artifacts, UI, lockfiles, skip-gate allowlist and main untouched. Report a concrete failing example if crossing that ownership boundary becomes necessary.

## Known defect and target behavior

test_r12_locked_file_keeps_state_loadable_and_retry_completes has a skipif(os.name != "nt") marker and two paths: api.log and pg/data/locked.bin. Both skip on Linux; the exact-one-live-skip gate rejects them. Do not delete this recovery coverage, add xfails/skips/exclusions or widen the allowlist.

Retain the actual Windows sharing-violation check. On POSIX, exercise an equivalent deletion refusal, with the same failure/retry assertions, using real owned filesystem permissions under a non-root user or a narrowly injected filesystem error if native execution is unavailable. Prefer native failure evidence once a suitable Linux environment exists. Clearly label injected evidence. POSIX opening a file alone does not stop unlinking it; do not simply remove the marker and keep the Windows stimulus unchanged.

Both path cases must prove: first stop fails and state_removed is false; marker and credential-bearing manifest remain owned and loadable; the retry succeeds once the fault is released; the exact owned directory is removed; canaries and unrelated directories survive; credentials are not printed. Restore every lock/permission/patch in finally. Preserve the procs fixture's interception of subprocess calls and health probes, so these cases do not touch a real server/service.

The neighbouring injected-partial-removal and marker-only tests cover different recovery phases: retain them. Test real recovery behavior and negative controls; a source-string assertion or a helper returning platform flags is insufficient. Keep baseline claims honest: existing Windows recovery already passes, and no native Linux baseline is available yet. Demonstrate the current two-skip gate failure, then show the replacement cases actually execute rather than being hidden.

## Environment and checks

- Locked dev+ml in this worktree; deterministic investigator, SENTINEL_LIVE_CLAUDE=0, no external test DB or another worktree's VIRTUAL_ENV. No provider call or new spending.
- Read-only inspect/use existing Linux resources if suitable. System/user/package setup remains a separate owner decision; do not install tools, create users or change WSL/Docker settings under this prompt. Complete Windows/test-code work even if Linux is not ready. Coordinate with Codex before any full Linux run; never run two full backend suites concurrently on the laptop.
- Run the entire changed follow-up file, relevant retained browser fixture tests as justified, N2 startup variants and Ruff. Prove failure/retry is exercised at both paths, and confirm no unexpected skips in the applicable report.
- On the final clean commit run the six-command strict gate. Capture JUnit from its same full pytest run (use a forward-slash absolute path in PYTEST_ADDOPTS), validate the exact skip policy and record collection/coverage. No duplicate full run solely for report format. Unchanged frontend/browser/model bytes do not require another frontend/evaluation run in this test-only task.
- Report native Windows, native Linux and injected/simulated evidence separately. A passing simulated branch or a removed marker does not establish actual Linux CI success. Record process/temporary-permission cleanup and any unconfirmed recovery state.

All new commits must be solely authored and committed by PHANI465 <pgavara1@asu.edu>, without Co-Authored-By or AI session trailers. Verify inherited project settings and actual commit metadata. Commit explicit owned paths and update the task handoff. Return exact base/final SHA, commands/exits/counts, evidence classes and remaining gaps. Do not merge main, push, alter accepted N2 or regenerate frozen results. Codex will review and integrate N2+N3 together. Cursor can remain closed.
