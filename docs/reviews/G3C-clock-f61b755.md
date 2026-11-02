# G3C clock fix review: f61b755, R40 changes requested

## R40 closed at accepted child, November 2

Both callers are corrected at 0c17bc8. Independent checks pass Windows 34+six and native
17+six, and exact full component reports show 609+one skip each. See
[the acceptance](G3C-R40-0c17bc8.md). Earlier f61b755 findings/evidence below are history.

November 2, 2026, America/Phoenix. Exact candidate
**f61b7554da532a0f8149f7ac02d0ab7e4cd84337**, direct child of 7bc0027, is clean and has
PHANI465 <pgavara1@asu.edu> as sole author and committer, no trailers/history rewriting.
Main application remains G3B a7c71f5. No main application merge or push occurred.

## Validated change and diagnosis

The SQL-wait replacement uses monotonic remaining time and short sleeps, without changing
budgets, cancel lead/reply window, result classification, socket ownership or retirement.
Shared state remains protected by the lease lock. The advisory-lock fixture preserves
delayed server-side COMMIT, cancellation and backend termination under the current serial
tests. Its three-second gate is measured monotonically rather than by pg_sleep. Test
bodies/assertions/timeouts are unchanged; this is an acceptable test-mechanism correction.

An isolated exact-commit Windows review passes 24 cases: new clock regressions, existing
bounded-call tests and both real PostgreSQL slow-COMMIT tests. A separate native Ubuntu
review passes seven cases (new clock module and those two real COMMIT cases). Review
checkouts use their own locked dev/ml environments, remain clean, and no provider ran.

Saved full evidence is verified on exact f61b755: both six-command strict records pass,
clean before/after, each same-run JUnit has 600 cases, 599 passed and only the allowed
live-Claude skip. Native head/status notes show sync/strict/JUnit/HTTP/ML all exit 0;
HTTP ends with frozen v1/v1.1/current v1.2 verification, ML reproduces true. Owner Windows
logs record 133 frontend tests and browser suites 19+10 passed. These full runs were
inspected, not independently duplicated during review. Platform sequencing is reported
by the author; wall-clock stamps alone are not a reliable proof on a stepping host.

Saved clock observations contain seven backward steps and corresponding timed-lock
overshoots over 240 seconds; the pg_sleep observation spans a backward step and takes
5599 ms. The native review interpreter independently reports HAVE_SEM_CLOCKWAIT=0.
The observed first-failure mechanism is supported by those data and the implementation.
The exact cause of the ORIGINAL recovery failure remains a qualified inference, not a
retroactively captured event; later reproduction demonstrates the possible typed path.

Primary source checks support the clock distinction: [CPython 3.11.14 pthread locks](https://github.com/python/cpython/blob/v3.11.14/Python/thread_pthread.h)
use the system-clock fallback without sem_clockwait;
[CPython Future.result](https://github.com/python/cpython/blob/v3.11.14/Lib/concurrent/futures/_base.py)
uses a timed condition wait; [time.sleep](https://github.com/python/cpython/blob/v3.11.14/Modules/timemodule.c)
uses CLOCK_MONOTONIC clock_nanosleep on the observed Linux build. PostgreSQL 16
[pg_sleep](https://github.com/postgres/postgres/blob/REL_16_STABLE/src/backend/utils/adt/misc.c)
recomputes against GetCurrentTimestamp. This is about the observed build/host, not every
Python interpreter or a new guarantee on server-side timeout behavior.

## R40 (medium, blocking): two production callers retain the defective wait

- src/sentinel/agents/coordinator.py:414: the submitted role call uses Future.result(timeout).
- src/sentinel/service.py:559: the single-investigator call uses the same mechanism.

Both inherit timed-condition sensitivity on the observed interpreter. This is a known
active path, not a hypothetical future feature. A forward step causes an otherwise
successful in-budget worker to be recorded as timeout; a backward step stretches the
wait beyond its budget. The SQL correction does not guard these caller waits.

Independent probes execute the actual production service/coordinator with real disposable
Postgres and synthetic workers. Only Future's condition is skewed; system time, workers,
database budgets and the ordinary threading implementation remain real. For each caller:
normal control passes; a shortened timed wait produces a false timeout; extending the
timed wait one second stretches the one-second worker budget plus two-second grace.

Results on BOTH platforms: six cases, **four intended assertion failures / two controls**.
Windows backward paths take 4.266 and 4.250 s against a three-second wait budget; native
4.061 and 4.094 s. Forward paths reopen the case with timeout rather than finishing the
valid synthetic recommendation. No model provider, fake authentication or new HTTP route
is used. These are added coverage, not failures in the author's 599 passing tests.

**Required:** extend monotonic waiting to both callers; preserve late-worker/call-slot
ownership, exception classification, failed-run/reopening behavior and existing budgets.
Make future result collection nonblocking after readiness rather than entering another
positive timed condition wait. Add maintained forward/backward/normal controls and real
service/coordinator coverage. Do not change host clocks/interpreter or weaken assertions
to avoid the defect. A helper shared by the two paths is reasonable; no framework needed.

## Nonblocking documentation clarifications

Describe the polling interval as up to 5 ms, not a guaranteed response latency under OS
scheduling. On the checked Linux implementation time.sleep uses an absolute monotonic
deadline; remove the inaccurate word relative. Narrow portable-interpreter statements
to the observed build, and retain the original recovery-failure causal qualification.
The fixture is appropriate for the current serial tests; its gate does not establish a
general per-COMMIT scheduling policy for arbitrarily overlapping waiters.

## Handoff and evidence

[Focused Claude continuation](../prompts/CLAUDE_G3C_CLOCK_WAIT_FOLLOWUP.md), Opus 5.5 / High,
on the existing f61b755 task branch. Explicit scope includes the service caller. Preserve
the SQL correction/fixture and earlier failures, add new sole-owner commits and certify
the corrected candidate. No new full f61b755 run, application merge, push or provider call.

Ignored canonical evidence: .agent/g3c-clock-review/f61b755/ contains Windows/native
independent XML/JSON/logs, safe probe source and owner full/clock observations. Temporary
probe test files were removed from both review trees. Component API/UI, original
integration, candidate and Cursor's seven saved edits remain unchanged. Native browser,
macOS, real CI, hosting, public BYOK, capacity and live agent quality remain unverified.
