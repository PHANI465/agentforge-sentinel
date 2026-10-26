# Claude N2: remove the known Linux test blocker

Read current main:AGENTS.md, then the latest task/coordination:docs/STATUS.md, docs/TASK_QUEUE.md, docs/reviews/4fff776.md (N2) and this assignment using git show. Main is consolidated and verified; this is the next small compatibility task, not another I03 rewrite.

## Base, branch and ownership

Code base: exact main a456f510d8053ce67b4334564d75225a756d923d. Create task/claude-linux-readiness in E:/PHANI/sentinel-wt/claude-linux-readiness from that commit. Inspect existing branches/worktrees first; do not reset or adopt an unexpected directory. If main has moved, report the exact difference before choosing a new dependency. Preserve main, all accepted component worktrees and Cursor's original saved changes.

Own tests/test_local_stack_startup.py, narrowly related test support, docs/ci/Linux notes and your branch handoff. Do not edit production src/, scripts/local_stack.py, contracts, model/data/evaluation files, UI, lockfiles or central coordination. If a real production POSIX defect prevents progress, provide the failing example and proposed narrow scope before crossing this boundary.

## Concrete defect and required behavior

ORPHANING in tests/test_local_stack_startup.py unconditionally passes nonzero Windows creationflags to the child Popen. Its test is unguarded, while backend CI targets Ubuntu. CPython rejects those flags on non-Windows platforms before the orphan PID is printed. Keep the Windows detached-child behavior; use a supported POSIX launch when running there. Do not fake the PID/port/process evidence that the regression is meant to test.

Before the fix, add/run a regression that fails for that unsupported-launch reason, not a missing import/symbol. Preserve the real owned-process tests. Where Linux execution is unavailable, a controlled non-Windows launch boundary can test argument compatibility without globally monkeypatching os.name; label that evidence as simulated. A helper returning a flags dictionary by itself is not sufficient evidence that the real launch and cleanup work.

Keep all R28 guarantees: unresolved launch is recorded, down/restore refuse to stop the database, unverified/reused/foreign processes are not killed, timeout is not readiness, owned cleanup is confirmed or recovery retained. Use test-owned handles/identities only; never kill by name or delete an unverified directory.

## Linux environment and scope

Ubuntu is registered in WSL2 and was stopped when Codex listed it. Installed Linux tools/user state were not rechecked. Read-only inspect existing Ubuntu tools and identity first. Use an existing suitable non-root/tool environment if available. This assignment does not install packages, create users, change the default WSL user, alter Docker/OS settings, create a remote or deploy anything. If setup is missing, finish the code/Windows regression work and return the exact missing prerequisites plus a concrete setup plan. Do not call the Linux path verified merely because a mock or Windows test passed.

Even a passing Linux launch test does not establish full POSIX operator safety: orphan reparenting/non-listening children remains a disclosed limitation. Do not expand into a lifecycle redesign in this task.

## Checks and delivery

- Locked dev+ml from this worktree, deterministic investigator, SENTINEL_LIVE_CLAUDE=0; external test DB and another VIRTUAL_ENV unset. No live provider call, subscription usage or additional spending.
- Run the changed startup/lifecycle tests on Windows. Run the relevant real Linux tests if the already available environment permits; record exact OS/user/interpreter/results and cleanup.
- Keep the structured gate's sole allowed live-Claude skip. Do not add skips, xfails, test exclusions or weaken ownership assertions to make CI pass.
- After the final commit, run the required six-command strict check on the exact clean candidate. Obtain JUnit from the same full pytest run and validate it. In PYTEST_ADDOPTS, use a forward-slash absolute report path (or correct quoting): raw Windows backslashes are consumed as escapes. Keep reports ignored. Do not run two full backend suites concurrently or rerun unchanged frontend/browser tests without a concrete reason.
- Document what is native Linux, Windows and simulated evidence. Keep frozen application/model/UI/dependency bytes unchanged and return exact base/final SHA, commands/exits/counts, cleanup and gaps.
- All new commits: sole author and committer PHANI465 <pgavara1@asu.edu>; no Co-Authored-By or AI session trailers. Read inherited .claude/settings.json/AGENTS.md and verify actual commit metadata before handoff. Do not rewrite historical accepted commits.

Commit explicit owned paths. Do not merge main or push; Codex remains the owner-designated main integrator/reviewer. Return a concrete tested N2 candidate. The following stage is an actual Linux/CI run after the needed environment/remote decisions, then a bounded three-role fraud investigation feature (evidence analyst, investigator, reviewer). Cursor can stay closed.
