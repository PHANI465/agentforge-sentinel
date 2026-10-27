# Claude N5 review follow-up: R29/R30

Read main:AGENTS.md and latest task/coordination:docs/STATUS.md, docs/TASK_QUEUE.md, docs/reviews/8a4b3d7.md and this prompt using git show. Candidate 8a4b3d767772a5cc11fa0d405ae4b8190b974ba3 is changes-requested; a passing full gate did not exercise these two recovery paths. N2/N3/N4 remain accepted. N6/N7 have no blocking scoped findings and must be preserved.

## Branch, scope and invariants

Continue task/claude-linux-lifecycle in E:/PHANI/sentinel-wt/claude-linux-lifecycle from exact 8a4b3d7; add commits, do not rebase/amend/reset the tested history. Inspect state first and preserve unexpected edits. Own tests/support/browser_stack.py, focused regression tests, necessary lifecycle documentation in docs/ci/LINUX.md and docs/api/browser-fixtures.md, and your handoff. Internal recovery metadata may be extended narrowly if needed and documented; preserve the existing public CLI result shapes and previously valid manifests/recovery flows. Do not modify production src, scripts, CI/gate/timeouts/skip allowlist, tests/test_installed_wheel.py or its pylock change, UI/runner, contracts, frozen model/data/evaluation files or dependency pins. Central coordination is Codex-owned.

## R29: unresolved groups survive retries and reloads

Use the review's real SURVIVOR + owned_tree reproduction. First stop refuses when the leader dies but a member remains. Reloading the saved manifest and stopping again currently succeeds and deletes it while the member is alive. Correct this at the real lifecycle boundary: persist or re-establish unresolved group status across retries rather than relying only on whether the old leader still exists. A vanished leader or closed health port is not proof its group is empty.

Write tests first that fail on 8a4b3d7 for the actual lost-recovery behavior. Assert first stop, fresh Stack.load retry and another retry all report failure/state_removed=false, keep a loadable matching ownership marker/manifest and credentials, leave the live survivor untouched, and do not send unverified signals. Then resolve only the test-owned member by its proved identity/handle, and prove an ordinary fresh-load retry succeeds and removes exactly the owned state. Keep outside canaries. Cover applicable no-live-handle/exited-leader paths, including permission/unknown identity where relevant. Do not fix this by killing unknown group members, deleting the original recovery flag, or making all retries fail forever.

## R30: unknown process membership is not positive shutdown evidence

_group_members currently catches every OSError reading /proc/*/stat and continues. Ignore only affirmative disappearance races that really prove the entry went away. PermissionError/EACCES, other I/O failure and malformed/incomplete stat data must remain unknown/unresolved, not an empty group or an uncaught incidental error. Preserve robust comm parsing, zombie exclusions, known reused-PID refusal and current Windows behavior.

Add failing-first regressions with a real live survivor and narrowly injected stat permission/I/O failures. Through Stack.stop, assert safe failure and preserved loadable state on repeated fresh-load retries, no destructive signals or credential leakage, then real success only after inspection and/or process state is safely resolved. Also prove an actually disappeared enumerated process does not strand ordinary cleanup. Label injected versus native process evidence. Keep existing group/identity/TERM/KILL/Windows cases; no new skips, xfails or weaker assertions.

The independent native probe scripts and JSON results are linked in the review; use them as evidence, not as authority to kill PIDs from a previous session. Every test must clean up only its own currently verified children/processes in finally. Never kill by process name, signal the caller's group or assume all members of a reused group are ours. Keep identity checks immediately before destructive operations and bounded monotonic waits. The previously disclosed PID check-to-signal race is not a redesign assignment.

## Verification and handoff

Use locked dev+ml, deterministic investigator, SENTINEL_LIVE_CLAUDE=0, no external test DB or inherited foreign VIRTUAL_ENV. Preserve accepted branches/main and Cursor's original seven changes. Native WSL is ready under sentinel UID 1000; use checksum-verified bundle transfer of the final committed candidate into the clean verification clone with no active test run. No system service/user/permission changes, new spending or provider calls.

Run the new failing-first tests on 8a4b3d7, then the final regressions and all retained lifecycle, browser-fixture/review/follow-up/model-fixture and N2/N3/N4 startup coverage. Verify cleanup and secret hygiene. Retain no unexpected skips and preserve the original full passing/failing reports.

After the final commit, run native Linux's full CI-equivalent structured gate/JUnit and all ancillary lint/helpers/domain+HTTP/Node/package/read-only ML checks, then Windows's six-command strict gate with JUnit from that same pytest run (or reverse order). Full runs must be sequential; no duplicate full suite just to change report formatting. Validate exact allowed skip and counts. No need to repeat the unchanged cold-cache experiment, frontend or training; preserve the N7 evidence and note Windows cold-cache/macOS/Actions limits.

Document R29/R30 and the final semantics before the last commit; do not edit tracked files afterward just to add its own SHA. All commits must be solely authored and committed by PHANI465 <pgavara1@asu.edu>, no Co-Authored-By or AI trailers. Stage explicit owned paths, verify metadata, return exact SHA, native/injected proof, checks/exits/counts, cleanup and gaps. Do not merge main, push or deploy. Codex re-reviews and integrates N2-N7 only after these findings close. Cursor can stay closed.
