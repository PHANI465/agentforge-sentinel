# Handoff: task/claude-g3c-native-diagnosis

- Task and acceptance criteria: diagnose the native G3C integration failures
  (docs/prompts/CLAUDE_G3C_NATIVE_INTEGRATION_DIAGNOSIS.md on task/coordination a4aedee). If
  a code defect is proven: add a failing-first regression, make the smallest fix and run the
  exact-commit gates.
- Tool and worktree: Claude Code (Opus 5.5) at E:/PHANI/sentinel-wt/claude-g3c-native-diagnosis
- Base: exact 7bc00272e083bb30d673eb4b11311623b992f942 (integration candidate; G3C-A 16b67fd,
  G3C-B 6014680).
- Updated: 2026-11-02 (local time)
- State: the R40 follow-up (review G3C-clock-f61b755) is ready for Codex re-review. Not merged.
- Code reference tested before this note: the uncommitted working tree on f61b755 (R40).
  f61b755 itself has its own full gates.
- Final check evidence: the full gates run after the final commit and are reported in the
  final chat.
- Owned/changed paths:
  - src/sentinel/agents/budget.py
  - tests/test_agent_workflow.py (fixture `slow_commit` only)
  - tests/test_budget_clock.py (new)
  - docs/agents/G3C-native-clock-diagnosis.md (new)
  - this note

## Implemented

- `bounded_call` measures its three waits on the monotonic clock (`_await`) instead of timed
  `threading` waits. On the gates' interpreter (`HAVE_SEM_CLOCKWAIT = 0`), those expire on
  `CLOCK_REALTIME`, and WSL2 steps that clock by about 2.5 s every ~32 s.
- `slow_commit` now delays COMMIT for 3 s of monotonic time (an advisory-lock gate) instead
  of `pg_sleep(3)`, which stretches on a backward step. The assertions are unchanged.

## Verified

- The cause and the evidence chain are in docs/agents/G3C-native-clock-diagnosis.md. In
  particular, an instrumented reproduction of failure 1 recorded a âˆ’2490 ms realtime step
  during the test, with the bound taking 3461 ms against 1939 ms.
- Failing first on exact 7bc0027 (Windows): 3 of the new regressions fail, and the 2
  controls pass.
- With the fix:
  - Windows: the new module plus test_agent_bounds pass (22);
  - native, patch applied to the diagnostic clone: test 2 passed 20/20 (9 steps, no
    overrun, recovery COMMITs 3016â€“3048 ms);
  - native: the known-rollback control passed 10/10 (cancel at 975â€“993 ms);
  - native: the failing-order prefix passed 3/3, including steps that landed inside the
    previously failing tests.

## Not verified / gaps

- Failure 2's forward-step mechanism was not observed inside the original failed run itself.
  It is consistent with its 2.65 s duration and with observed forward steps.
- These remain realtime-timed:
  - live-role `future.result(timeout)` (coordinator.py:414);
  - the single-investigator deadline (service.py:559, not owned);
  - PostgreSQL's own timeouts;
  - test-side waits.

  A proposal is in the diagnostic note.

## Next action

Codex reviews the diagnosis, the budget.py change and the `slow_commit` mechanism change at
the final commit reported in chat.

## Coordination and provenance

- Original work. No dependency, contract, migration, UI or lifecycle-helper change.
- Observation plugin and scripts: .agent/g3c-native/ (ignored). The native reports are in
  ~/g3c-native-diagnosis-reports/. My own clone ~/g3c-native-diagnosis was restored to a
  clean 7bc0027 after each patched run.
- The integration clone, review checkouts and Cursor's seven edits are untouched.

## R40 follow-up (on f61b755)

- **Change.** The new src/sentinel/clock.py holds `wait_until` (moved unchanged from
  budget.py) and `wait_future`. coordinator.py (live role) and service.py
  `_run_investigator` wait for `future.done()` on the monotonic clock, then call
  `result(timeout=0)`.
- **Unchanged:** deadlines, the working-phase cap, classification, reopen, late-result
  discard, the call-slot lease, no repeat after a timeout, and the SQL fix and
  advisory-lock fixture.
- **Tests.** The new tests/test_future_clock.py fails first on f61b755 (Windows and native):
  6 fail on assertions and 4 controls pass. With the fix, they pass. On Windows, a focused
  run of the clock, bounds, workflow, reliability, thin-path and units suites gives 119
  passed. Codex's 6 probes pass, run as a temporary file that was removed.
- **Docs.** The clarifications are in docs/agents/G3C-native-clock-diagnosis.md: monotonic
  `time.sleep`, the poll interval, the narrowed build claims, the fixture scope and the
  server-side limits.
