# G3C native integration failures: realtime-clock steps (diagnosis)

Base: integration candidate 7bc00272e083bb30d673eb4b11311623b992f942. Branch:
task/claude-g3c-native-diagnosis. The failures are in docs/reviews/G3C-integration-7bc0027.md.
Investigated November 2, 2026 on the native Ubuntu (WSL2) host used for the gates.

## Summary

- **Cause, proven for failure 1.** `budget.bounded_call` bounded its waits with timed
  `threading` waits (`Event.wait`, `Condition.wait`). On the interpreter the gates use, those
  waits expire on `CLOCK_REALTIME`, not on the monotonic clock that budget.py measures with.
- **Host behaviour.** On this WSL2 host, `CLOCK_REALTIME` steps by about 2.5 s roughly every
  32 s, mostly backwards and sometimes forwards.
- **Effect of a step.** A backward step mid-wait overruns the bound by the step. A forward
  step ends a wait early.
- **Failure 2.** Its mechanism is a forward step ending the COMMIT's pre-cancel wait early.
  This is strongly supported: the timing is consistent, forward steps occur, and the same
  typed path was reproduced. It was not observed inside the original failed run.
- **Fix.** The three waits in `bounded_call` now measure on the monotonic clock (`_await`).
  The `slow_commit` test fixture now delays COMMIT for 3 s of monotonic time instead of
  `pg_sleep(3)`, whose server-side duration also follows `CLOCK_REALTIME`.

## Environment facts (read-only observations)

| Fact | Value |
| --- | --- |
| Kernel | 5.15.167.4-microsoft-standard-WSL2, clocksource `tsc` |
| Time sync | systemd-timesyncd active (and the Hyper-V host time sync) |
| Interpreter | uv-managed CPython 3.11.14 (portable build), `sysconfig HAVE_SEM_CLOCKWAIT = 0` |
| System glibc | 2.39, which provides `sem_clockwait`, but the interpreter was not built with it |
| psycopg / libpq | 3.3.6 binary, libpq 18 on both platforms. `cancel_safe` uses the non-blocking cancel API, which rules out the legacy blocking-cancel hypothesis |
| Windows | CPython 3.11.3. Windows timed lock waits are monotonic, and all six commands pass there |

Without `sem_clockwait`, CPython's `PyThread_acquire_lock_timed` computes an absolute
`CLOCK_REALTIME` deadline once and calls `sem_timedwait`. `threading.py:331` is
`waiter.acquire(True, timeout)`. On this build `time.sleep` waits on the monotonic clock
(an absolute `CLOCK_MONOTONIC` `clock_nanosleep` deadline) and is not affected. These
statements describe the observed build and host, not every Python interpreter.

## Evidence

All of it is under `.agent/g3c-native/` in this worktree and `~/g3c-native-diagnosis-reports/`
natively. It holds identifiers, counts, typed classes and `file:line` frames only, with no
messages or credentials.

1. **Standalone clock probe, idle, 240 s** (`clock/idle-240s.json`). There were seven
   realtime steps of Ã¢Ë†â€™2.52 to Ã¢Ë†â€™2.66 s, about 33 s apart. Each was followed by a 500 ms timed
   lock wait taking **3.17Ã¢â‚¬â€œ3.41 s** (measured by monotonic time). There were no other
   overshoots.
2. **pg_sleep probe** (`clock/pgsleep.json`, a disposable cluster that was then stopped).
   - A **+2601.5 ms** (forward) step occurred, and a Ã¢Ë†â€™2595.4 ms step 15 s later.
   - The `pg_sleep(3)` spanning the backward step took **5599 ms**.
   - No `pg_sleep(3)` finished under 3003 ms. A forward step does not shorten it, because it
     first waits its full interval on a relative latch.
3. **Failing-order prefix** (the data, ML and all `test_agent_*` modules, 135 tests, in the
   full-run order), with an observation-only plugin. Over 9 unpatched runs:
   - A **third, database-free failure** appeared:
     `test_statement_without_a_reply_is_budget_exhausted_and_quarantined` took 3.61 s
     against 1.2 s, using the in-process `Silent` fake.
   - Failure 1 recurred twice. In the run with the realtime monitor (`prefix-clock/run2`),
     a **Ã¢Ë†â€™2490 ms step landed during that test**, and its COMMIT bound took **3461 ms against
     1939 ms**.
   - A passing test, `test_withheld_statement_reply_replaces_the_quarantined_connection`
     (whose bound allows 15 s), overran **7628 ms against 4999 ms**. All 1288 main-thread
     samples were at `threading.py:331 < budget.py:290`.
   - **Negative controls:** gen-2 GC pauses were at most 88 ms (about 165k tracked objects),
     and a 5 ms `time.sleep` watchdog thread recorded no scheduling gap of 100 ms or more.
     The process was not frozen; only the realtime-timed wait was late.
4. **Failure 2.**
   - Every passing native run of `test_uncertain_commit_reports_outcome_unknown` takes
     4.18Ã¢â‚¬â€œ7.40 s, because the recovery COMMIT always includes the 3 s delay. The failed run
     took **2.65 s**, so its recovery COMMIT ended early.
   - The only typed path to `conflict` there is a COMMIT error. A cancel sent at about
     `3.97 Ã¢Ë†â€™ step` s (the forward step shortening `done.wait`) while the server still sleeps
     3 s fits that duration.
   - The client fix alone was then run 20 times. One run failed with the reverse mechanism,
     captured in full: a backward step stretched the server's `pg_sleep(3)`, and the now
     correctly monotonic client cancelled at exactly **3972 ms**. The path was
     `QueryCanceled` (57014), then `BudgetExhausted` at `budget.py:480`, then `conflict` at
     `coordinator.py:159`.
   - So the `slow_commit` fixture is itself realtime-sensitive, and the old code passed with
     a backward step only because the client and server stretched together.

## Changes

- **`src/sentinel/agents/budget.py`.** `_await(ready, left_s)` waits by sleeping on the
  monotonic clock: 0.2 ms, doubling to 5 ms, until the operation answers or the limit passes.
  The 5 ms is the polling interval, not a guaranteed observed latency under OS scheduling.
  (The helper is now `sentinel.clock.wait_until`; see R40 below. The f61b755 commit message
  called `time.sleep` "relative"; it waits on an absolute monotonic deadline on this build.)
  `bounded_call` uses it in place of `done.wait(cancel_after)`, the reply-wait
  `Condition.wait` and the helper-wait `Condition.wait`. Shared state is still read under
  the lease lock. These are unchanged:
  - budgets, `COMMIT_CANCEL_LEAD_MS` and `COMMIT_CANCEL_REPLY_MS`;
  - unknown COMMIT versus known rollback;
  - retirement, quarantine and socket shutdown (R34Ã¢â‚¬â€œR37).
- **`tests/test_agent_workflow.py`, fixture `slow_commit` only.**
  - The deferred trigger now waits on an advisory lock instead of calling `pg_sleep(3)`,
    and the function runs with `lock_timeout = 0`.
  - A fixture thread releases the lock **3.0 s of monotonic time** after a COMMIT starts
    waiting.
  - The client cancel and backend termination still end the wait.
  - Test bodies, assertions, timeouts and durations are unchanged. This is a test-mechanism
    change for Codex review: the intended 3 s server-side COMMIT is kept, and only its clock
    changes.
- **`tests/test_budget_clock.py`, new.** It replaces only budget.py's view of `threading`
  with timed waits skewed as a stepping realtime clock would skew them (Ã‚Â±1.5 s), and does not
  touch the system clock.

## Regression and verification

**Failing first on exact 7bc0027 source, Windows**
(`regression/failing-first-7bc0027-windows.log`):

- These fail:
  - a backward step on a COMMIT and on a statement (3.0 s and 2.5 s against 1.2 s);
  - a forward step cancelling a COMMIT early (`CommitUncertain` for a COMMIT answered at
    0.6 s inside a 2 s budget).
- These controls pass:
  - a forward step on the main reply wait, which already re-checked monotonic time;
  - quick-reply latency.

**With the fix:** the new module and all of `test_agent_bounds.py` pass on Windows (22).

**Native, with the full patch applied to the diagnostic clone (restored afterwards):**

- `test_uncertain_commitÃ¢â‚¬Â¦` passed **20/20**, with **9 steps (6 backward, 3 forward) during
  the runs** and no bounded-wait overrun. Recovery COMMITs took 3016Ã¢â‚¬â€œ3048 ms, and the first
  COMMIT ended `AdminShutdown` then unknown each time.
- The known-rollback control passed **10/10**, cancelled at 975Ã¢â‚¬â€œ993 ms.
- The failing-order prefix passed **3/3**. Steps landed during
  `test_statement_without_a_replyÃ¢â‚¬Â¦` (Ã¢Ë†â€™2491 ms, which had failed before) and
  `test_withheld_statement_replyÃ¢â‚¬Â¦`, with no overrun.

The final exact-commit gates are reported in the task handoff chat.

## Not changed, and remaining exposure (for Codex)

- **Same-class waits outside `bounded_call`. Resolved by R40 below; the original note follows.**
  - `coordinator.py:414` uses `future.result(timeout)` for live role calls.
  - `service.py:559` is the single-investigator deadline. That file is outside this task's
    ownership.

  Both are `concurrent.futures` condition waits, so they are realtime-timed on this
  interpreter. A forward step can end a live call as a false `timeout`; a backward step lets
  it run about one step longer. Neither appeared in these failures: the gates use
  deterministic roles, and the live-role tests do not assert durations.

  Proposal: wait for `future.done` with `_await` and then call `future.result(timeout=0)`,
  with a skewed-`concurrent.futures` regression. This is a separate, reviewed change.
- **PostgreSQL server timeouts** (`statement_timeout`, `lock_timeout`) and `pg_sleep` use the
  server's realtime clock. On such a host they can fire early or late by about one step. A
  client cannot correct this. budget.py already states that it does not prove timely server
  behaviour.
- **Test-side timed waits.** Examples are the 0.7 s killer `Event.wait` and `until()`
  polling. They are realtime-timed too. They were harmless in every observed run.
- **Environment option, not adopted.** An interpreter built with `sem_clockwait` (or a host
  without realtime steps) would also remove the client-side symptom. Changing the locked
  interpreter or the host time sync is an environment decision for the owner and Codex.
- **Not established.** Failure 2's forward-step mechanism was not observed inside the
  original failed run itself. No full native suite was rerun before the fix; the final
  exact-commit gates follow the commit.

## R40 follow-up: the two caller waits (review G3C-clock-f61b755)

- **Defect.** Two waits had the same weakness:
  - `coordinator.py`: the live-role `Future.result(timeout)`;
  - `service.py` `_run_investigator`: the single-investigator `Future.result(timeout)`.

  Both are timed condition waits on the observed build. A forward step recorded a successful
  150 ms worker as `timeout`. A backward step stretched the 1 s + 2 s grace deadline by about
  a second.
- **Fix.** A shared `sentinel/clock.py` holds `wait_until`, moved unchanged from budget.py,
  and `wait_future(future, timeout_s)`, which waits for `future.done()` on the monotonic
  clock. Each caller then collects the finished future with `future.result(timeout=0)`,
  which performs no timed wait on a finished future. These are unchanged:
  - the deadlines: timeout plus grace, and the coordinator's working-phase cap;
  - result and exception classification;
  - honest timeout and reopen;
  - discarded late results;
  - the late-worker call slot, released only when the worker really returns
    (`capacity.Slot.start`'s done-callback);
  - `pool.shutdown(wait=False)`, and no repeat after a timeout.
- **Regressions.** `tests/test_future_clock.py` skews only `Future`'s condition: forward
  ends a positive timed wait at once, and backward adds 1 s. It runs the real service over
  HTTP and the real coordinator with a live synthetic role, on disposable PostgreSQL.
  - **Failing first on exact f61b755, on Windows and native alike:** 6 fail on their
    intended assertions and 4 normal controls pass. The six are: forward skew turning a
    150 ms success into `timeout` (both callers); forward skew turning a 150 ms provider
    failure into `timeout` (both callers); and backward skew stretching the 3 s deadline to
    4.06â€“4.39 s (both callers).
  - **With the fix:** all pass, including the late-result discard and the call slot staying
    held after the timeout until the worker returns. Codex's six original probes pass
    (4 failed before); they ran as a temporary file that was then removed.
- **Fixture scope.** The advisory-lock `slow_commit` gate suits the current serial tests. It
  is not a general per-COMMIT scheduling policy for arbitrarily overlapping waiters.
- **Server side.** PostgreSQL `statement_timeout`, `lock_timeout` and `pg_sleep` still follow
  the server's realtime clock. That limitation is unchanged and not addressed here.
