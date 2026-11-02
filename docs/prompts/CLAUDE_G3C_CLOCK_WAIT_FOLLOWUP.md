# G3C R40: finish monotonic waits for investigator and role callers

**November 2:** clock/caller correction 0c17bc8 is accepted and R40 closed under
[the independent review](../reviews/G3C-R40-0c17bc8.md). This assignment is complete;
do not restart it. Codex owns final combined release verification. Older pending/pause
banners and original assignments below are historical.

Recommended coding assistant: **Claude Opus 5.5 / High**. This is a focused completion of
the proven clock fix across two asynchronous callers, preserving deadlines and late-worker
leases. It selects the coding assistant; all Sentinel test providers remain synthetic.

Read current task/coordination AGENTS/STATUS/TASK_QUEUE and docs/reviews/G3C-clock-f61b755.md
with git show. Continue the EXISTING task/claude-g3c-native-diagnosis worktree from exact
**f61b7554da532a0f8149f7ac02d0ab7e4cd84337**. Do not redo the original diagnosis, recreate
its worktree, amend/reset/rebase or rewrite the preserved commit. The SQL polling fix and
monotonic slow-COMMIT fixture pass scoped review and should stay intact.

## Required correction

Both coordinator.py's live-role result(timeout) and service.py's single-investigator
result(timeout) still use the realtime-sensitive condition wait. Independent real-service
probes on Windows AND native Ubuntu produce four assertion failures and two controls
passing: forward skew falsely times out a 150 ms successful worker; backward skew adds
one second to a three-second budget. No model or system-clock modification is involved.

Use a shared monotonic deadline/readiness wait, then obtain an already-ready result without
a positive timed Future wait (for example result(timeout=0)). Keep the existing timeout
plus grace and coordinator working-phase cap. Do not start a second full budget after
submission, poll past the working deadline, or reintroduce the same condition wait in a
helper. Preserve completed-result errors, provider failures, honest timeout/reopen and
discarded late results; a worker's call slot stays held until its real return. Do not
cancel/release the slot merely because the coordinator stops waiting, repeat after a
timeout, or make an unbounded executor shutdown. No usage/billing inference.

## Ownership (explicit extension)

Own src/sentinel/agents/budget.py, src/sentinel/agents/coordinator.py and specifically
src/sentinel/service.py's investigator-deadline helper and necessary imports. A small
shared timing module under src/sentinel/ is allowed if it avoids duplication; no package
dependency or architecture migration. Own a new tests/test_future_clock.py or equivalent,
focused additions to relevant agent/reliability tests, docs/agents/G3C-native-clock-diagnosis.md
and your branch handoff. Preserve unrelated service/approval/scoring logic. Do not edit
contracts, migrations/grants, model/data/evals/protocol, UI, dependency files, lifecycle
helpers, CI/skip policy, checker timeouts or central coordination. Keep Cursor and other
accepted worktrees untouched. This scope already authorizes the service helper change.

## Regressions and documentation

Write meaningful maintained tests first on f61b755: normal/forward/backward for BOTH
callers, true timeouts, worker completion/errors and late-result/lease preservation. Use
real service/coordinator and disposable Postgres where appropriate. Isolate simulated
skew to Future's wait implementation, not a global system clock or wall-time monkeypatch
that makes the test pass trivially. Test workers must actually return or be released in
finally; no provider call. Keep a supported result under forward skew and a monotonic
timeout bound under backward skew. Measure the intended wait carefully; don't hide the
bug by broadening response-time assertions or adding sleeps.

Original independent probe source and runner are archived in canonical ignored
.agent/g3c-clock-review/f61b755/ and E:/PHANI/Interview/tmp/test_codex_future_clock.py.
The probes have four assertion failures/two controls on f61b755, not setup failures.
Port useful cases into maintained tests, preserving their meaning. Run the original six
probes as an independent sanity check; temporary files must be removed afterward.

Small documentation clarifications: time.sleep uses monotonic waiting (absolute
clock_nanosleep on the observed Linux build), not a relative-clock guarantee; <=5 ms is
the poll interval rather than guaranteed observed latency. Narrow build claims to the
observed uv CPython 3.11.14. Keep failure 2's original-run cause qualified; later reproduction
does not retrospectively prove it. Leave server-side timeout limitations explicit.

## Final verification and handoff

No need to rerun full f61b755 checks: both complete gates are already verified at 599+one
allowed skip. First prove your new regressions fail for the right reasons then pass.
Commit new changes with PHANI465 <pgavara1@asu.edu> as sole author AND committer, no
trailers/history rewriting. Certify the NEW exact clean SHA with full Windows/native
gates sequentially, same-run JUnit and exact structured skip validation, frozen exports,
package/install/ML reproduction and Windows frontend/legacy19/trace10 browser coverage.
No weakened tests, sleeps to obtain green, new skips or increased timeouts. Preserve and
diagnose failures; repeat runs are new evidence, not automatic fixes.

Return the exact tested SHA/base, meaningful failing-first results, actual platform
results and cleanup/gaps. Keep the R34-R39 and SQL clock regressions intact. No main merge,
push, remote, deployment, paid fallback, live provider or final evaluation. Codex re-reviews
R40 before the combined application advances. No additional unrelated feature is assigned.
