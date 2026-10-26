# N3/N4 review: 476abcc

**Accepted for the scoped N3/N4 fixes. Native Linux release acceptance remains blocked.** Candidate 476abccc52b5228f71e129f8e3d0a8d9f11bef41 on task/claude-linux-cleanup-tests, exact base accepted N2 3c860d4. No merge or push; main remains a456f51. The two new commits have only PHANI465 <pgavara1@asu.edu> as author and committer, with no attribution trailers.

## Code and independent evidence

The diff has five owned files. The only production change is Cluster.start's explicit empty unix_socket_directories, keeping loopback TCP, port selection and the existing stop/wait behavior. The regression actually initializes, starts, connects, checks socket configuration and stops a disposable cluster. R12 retains Windows sharing refusal and uses actual non-root directory permissions on Linux, restored in finally. Both refusal paths retain recovery ownership/credentials and protect outside canaries. Other source, contracts, model/data/evaluation bytes, UI, dependencies and scripts are unchanged from 3c860d4.

Independent final-candidate checks:
- Windows: 24 focused tests passed in 37.03s (devdb startup, R12 follow-up file and N2 startup); Ruff passed.
- Native Ubuntu as sentinel UID 1000: the corresponding 24 passed in 19.38s, without skips.
- Owner Windows .agent/last-check.json names the exact clean candidate, before/after snapshot matches, and all six commands passed. The full 435+1 count remains owner execution evidence; the independent run is 24, not another full suite.
- Owner native JUnit has exactly 436 cases, matching independent collection node for node: 430 passes, five failures, one allowed live-Claude skip. Its SHA256 is 9882f02b273d943cfe8cbc81960ed565be2c9f0afa61819baf6a55c16f773290. No Linux full pass is claimed.

The first independent Linux invocation had an incorrectly quoted PATH, making the external kill command unavailable. Its resulting failures/teardown errors are review-invocation errors. Four stand-ins were verified by UID, exact command and port, stopped individually, and the corrected 24-case run passed. This does not amend the candidate or count as an application defect.

## Remaining native failures: N5/N6/N7

Four failures concern lifecycle behavior in unchanged tests/support/browser_stack.py: never-ready startup cleanup, API-stop recovery/retry, failed-start recovery, and model scorer restart/replay. The actual low-level defects are independently reproducible:
- **N5:** terminate_tree sends only SIGTERM on POSIX. A verified test-owned child with a TERM handler survived the actual helper; it required explicit kill/reap by its own handle. The helper needs bounded, identity-verified escalation, preserving refusal/recovery behavior.
- **N6:** process_start_time reads the start stamp of a real exited, unreaped child in /proc state Z and reports the old identity as alive. The probe confirmed Z before reaping. A stopped zombie must not block restart, while a running, reused or unverifiable process must retain safe handling.

**N7:** the installed-wheel test's offline dependency installation failed during the full run and passed after the online package check. The saved failure is truncated and does not establish the missing package. Cache incompleteness is a hypothesis, not an accepted diagnosis. A warm-cache rerun cannot prove a fresh runner works. Require isolated-cache reproduction after the documented locked install, capture complete subprocess stderr, and make any necessary dependency preparation explicit without weakening the offline install/isolation test or changing pins.

These are separate follow-ups, not regressions introduced by the five-file N3/N4 diff. Assignment: [N5/N6/N7](../prompts/CLAUDE_N5_LINUX_LIFECYCLE.md). Batch integration after review and platform validation; keep the tested candidate intact.

## Records and limits

Independent XML: E:/PHANI/Interview/tmp/n3-codex-windows-focused.xml and /home/sentinel/n3-reports/codex-native-focused.xml. Native probes: codex-lifecycle-probes.json in that Linux report directory. Consolidated independent evidence: E:/PHANI/Interview/tmp/n3-independent-evidence-20261026.json. Owner original full report/logs are /home/sentinel/n3-reports/final-full-junit.xml and final-gate.log. No raw credential-bearing output belongs in tracked docs.

No full suite was independently repeated solely for review. No GitHub Actions, macOS or hosting evidence. The disclosed non-listening orphan limitation and PID check-to-signal race remain. Windows main, accepted N2/N3/N4 candidates and Cursor's seven saved changes remain preserved. Git-ref instructions are handoffs; no message was sent to another assistant.
