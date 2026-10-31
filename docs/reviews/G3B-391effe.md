# G3B implementation review: 391effe

October 31, 2026. Candidate **391effed084adef34ca5852255687fffa3d99d50**,
branch `task/claude-g3b-workflow`, exact dependency2919f76. Independent review worktree:
`E:/PHANI/sentinel-wt/codex-g3b-review`, clean at the candidate. Claude's checkout and main
are preserved. **Decision: changes requested for R34-R36; do not merge or start G3C.**
G3A acceptance remains valid; these are implementation gaps against the accepted limits.

## Positive evidence and scope

The implementation supplies the three roles, production runtime-role tools, checked claims,
server-built intent, migration0005 and durable role/step records. Deterministic remains the
default, and the legacy contracts/UI/model artifacts/lockfile are byte-preserved. Agent
output does not approve or execute an action. Existing recovery, rejection, expiry and
idempotent-action tests pass in the independent focused suite.

The packaging entry and two-table backup/runbook inventory additions are the explicitly
approved exceptions. The additional migration-count correction in test_check_package.py
and CI README is accepted as a necessary narrow inventory update: it keeps the exact count
assertion and changes 4 to5, without weakening the guard or editing workflow/timeout/skip
policy. No new dependency was added.

## R34 — COMMIT cancellation does not bound the client wait (high)

`src/sentinel/agents/budget.py:174-205` starts a watchdog that calls cancel_safe, but the
request remains synchronously blocked in conn.commit(). A failed cancellation is ignored.
Even an acknowledged cancel request does not supply a missing COMMIT reply. There is no
client-side deadline which makes that blocked wait return, so the workflow admission slot
can remain held indefinitely. The same distinction matters for a stalled statement or
connection operation; a server timeout is not a bound on receipt of a response.

**Independent evidence on Windows and native Ubuntu:** two injected transport stand-ins
use the real BoundedTransaction and a controlled commit that withholds its reply. One
cancel request raises OSError; the other acknowledges but still withholds the commit reply.
In both, the 1000ms watchdog fires, but the caller is still blocked at about1250ms elapsed from start and
returns CommitUncertain **only after the test explicitly releases it**. The tests release
and join every thread in finally. This is fault-injected client-I/O evidence, not a claim
that a real network failure was measured. It demonstrates the blocking path directly.

The existing real-database kill-backend/deferred-trigger tests are useful but do not cover
an unresponsive transport. A cancellation attempt alone is insufficient for the accepted
elapsed-wait contract.

**Required:** implement a finite client-wait strategy consistent with the accepted absolute
budget, including no-answer/cancel-failure paths. Do not turn an unconfirmed COMMIT into a
known rollback or success. Quarantine unresolved connection/operation ownership: do not
reuse a connection while a worker/cancel can still affect it, and do not solve this with
unbounded abandoned SQL threads. Keep provider call leases separate and correctly held.
Cover recovery's transaction owner as well: owned=False currently leaves COMMIT to a
caller that may not use this watchdog. Add meaningful no-reply regressions and real
PostgreSQL/owned transport coverage where practical. No timeout extension or weakened
waiting claim is approved by this review.

## R35 — role budget is stale by the time a live call is submitted (high)

`coordinator.py:323-378` checks that the full role timeout plus grace fits **before** the
before_role hook and bounded role-start persistence. It then submits the worker and waits
for the original full call_ms without checking the budget again. Time spent writing the
start record can consume the admitted budget, letting a call run into the reserve or past
the workflow deadline and consume subscription quota even when it should not start.

**Independent real-PostgreSQL/runtime-role probe on each platform:** use the existing hook
and injected monotonic clock to leave1000ms of working time after the first precheck, then
let production role-start persistence run. A controlled live-marked45s adapter is called
once with only **985ms on Windows / 993ms on Linux** of working budget, against the required
47000ms. It returns immediately to keep the probe bounded; no real provider is called.
The final case reopens, but the forbidden late call has already happened.

**Required:** re-evaluate the absolute remaining budget immediately before actual call
submission, after persistence/setup. Do not submit if the full call/grace does not fit.
Account honestly for a recorded attempt that cannot start; release any reserved unused
call slot, persist typed exhaustion through the terminal path, and create no intent.
The wait itself must never exceed the remaining working budget. Add a gated persistence/
clock regression for this exact gap, not only a pre-call deadline test.

## R36 — the pinned transition limit is never enforced (medium)

WorkflowLimits.max_transitions is in the pinned contract (contracts/agents.py:166), but
no coordinator path reads it and no transition count is enforced. The accepted design's
bounded state machine is therefore not honoring that pinned control.

**Independent real-PostgreSQL/runtime-role probe on both platforms:** construct a valid
workflow with max_transitions=1, pin it normally on ingestion and investigate D01. All
three roles complete, a current intent is created and the case reaches awaiting_approval.
The configuration has been ignored, rather than ending typed budget_exhausted.

**Required:** define/count the accepted state-machine transitions, check the pinned limit
before advancing, and record transitions sufficiently to audit the count. Exhaustion must
still allow safe terminal/recovery bookkeeping, with no extra role/tool/action. Cover a
small limit, an exactly-fitting path and default/revision/repeat paths without weakening
the role/tool/repeat caps or changing frozen legacy schemas.

## Independent verification and supplied reports

| Evidence | Result |
| --- | --- |
| Isolated Windows locked dev+ml environment | Installed offline from existing cache; imports candidate source |
| All five new G3B test files on Windows | **64 passed**,120.72s, no skips (real disposable PG where applicable) |
| Ruff / domain+agents export / HTTP export | Passed;15 legacy schemas,15 agents schemas,85 examples; legacy HTTP unchanged |
| Added review probes on Windows | **4 intended failures**,19.92s: two R34 variants, R35, R36 |
| Same probes on native Ubuntu | **4 intended failures**,9.11s; no skips |
| Owner Windows final strict record | Exact391effe clean before/after;6 checks exit0; pytest step1092.938s |
| Owner Linux final report | **518 passed,1 allowed live-Claude skip**,519 cases,0 failures/errors |
| Independent Linux collection vs report | Exact519-case identity set matches |
| Owner Linux package/HTTP/ML records |5 migrations/8 model-data assets; frozen HTTP check; ML reproduced |
| Cleanup | Probe threads joined; fixture databases/clusters stopped; zero probe-owned processes found on each platform |

The owner disclosed a pre-existing ingestion-timestamp test flake and retained the failing
first/full rerun reports. I did not repeat the30-run experiment or relabel it as an
independently diagnosed G3B regression. The full Windows/Linux suites and browser suite
were not rerun independently after these new blockers; there is no integration to certify.
The owner reports the existing browser suite passed unchanged; this review does not claim
an additional independent browser result.

Review probes are deliberately outside the tracked tree, under allowed temporary storage;
canonical ignored evidence is copied to `.agent/g3b-review/391effe/`. Native originals remain
in `/home/sentinel/g3b-reports/codex-independent-probes.*`. No raw reports/credentials belong
in tracked documentation. A shell quoting error in one read-only report-inspection command
was corrected by using a file script; it changed no project state. A sandbox-denied process
inventory was rerun read-only with appropriate access before recording the zero count.

## Nonblocking notes / later evidence

- Manual scripts/agent_eval.py currently uses its operator database_url for investigations
  too. It is not evidence of runtime-role enforcement. Before a live evaluation, separate
  operator session creation from the restricted runtime connection and make case/fault
  applicability explicit. No live comparison is assigned now.
- The16-table backup inventory remains exact, but the current backup fixture uses the
  single investigator, leaving the new workflow tables empty. A populated workflow/steps
  round-trip would add evidence before claiming their backup contents were exercised.

## Next action

[Claude R34-R36 corrections](../prompts/CLAUDE_G3B_REVIEW_FIXES.md), on the same task branch
from exact391effe, **Opus5.5 / High**. Keep the delivered implementation and approved
inventory/packaging edits. Codex re-reviews the exact corrected SHA before integration.
Main application stays f091a34; G3A stays accepted; G3C remains unstarted.
