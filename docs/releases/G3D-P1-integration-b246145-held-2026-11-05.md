# G3D-P1 integration verification: held November 5

## November 5: resumed; integration held by Windows verification command budget

Prepared candidate **b246145410229ce6192f969b100bfec93a628503** merges current coordination and accepted 6e461c0.
Application, scripts, tests, fixtures, contracts, model/data and lock bytes match the
accepted candidate exactly. R41-R43 remain closed. One documentation conflict only.

**Native Ubuntu is fully green:** 647 passed + one allowed live-Claude skip, six strict
commands, same-run648-case JUnit validation, frozen HTTP export, packaged install and
read-only ML reproduction. **Windows UI is green:** 133 tests, typecheck/build and real
browser 19 legacy +10 trace cases, with secret scanning and verified cleanup.

**The required Windows full strict gate is not green.** The first run hit its unchanged
1800-second pytest-command cap after 506/648 progress markers. After the owner reported
closing unused apps and connecting power, one controlled rerun reached 637/648 and hit
the same cap. Neither reported an assertion failure before cutoff, but neither has a
complete JUnit report. The other five strict commands passed on both attempts. The 11
unreached cases pass separately; this does not replace the required full run. Both
failures are preserved. A broad runtime slowdown is observed; its cause is not proven.

**Awaiting the owner's decision:** [one-line proposal](../proposals/G3D-verification-command-budget.md)
to change only the verification-command cap 1800 ->2700 seconds (45 minutes), keeping
individual tests, assertions, agent/database/HTTP deadlines and skip policy unchanged.
The saved resume plan protects timeout changes. The proposal is unapplied; no third
unchanged full Windows run is authorized by this checkpoint. Alternative: keep 1800 and
perform focused Windows runtime diagnosis.

Main APPLICATION stays released G3C; this publication changes documents only. The
prepared evaluator integration is not promoted. Populated-workflow backup remains the
next feature task after release. Accepted worktrees, Cursor's seven saved edits and old
failure evidence are preserved. No test-owned database/API remains on either platform;
the unrelated PostgreSQL service and idle Ubuntu shell were left alone. No provider,
final-case evaluation, paid use, remote/push or deployment. Older entries are history.

## Evidence and what it does not prove

Both full Windows attempts ended before native or another full Windows run began. The
first post-timeout process snapshot contains no surviving pytest interpreter. Each
orphan cluster was stopped through pg_ctl only after rechecking its PID, creation time
and exact test-owned data directory; files remain for investigation. The current native
clone is clean and the browser runtime directory contains no recovery/secrets state.

The same first506 cases took 861 seconds in the accepted author's older Windows report,
versus reaching the 1800-second cutoff here. Other helper/package commands slowed too.
Initially the laptop reported 1.7 GiB free memory. The owner closed apps and confirmed
taskbar charging; programmatic power readings disagreed. These observations do not prove
a hardware cause or a production-code defect. No assertion or individual deadline was
weakened to obtain a green result. The two full Windows attempts remain failed.

The proposed 2700s value is a maximum lifetime for each verification command, not an
application latency target or a change to the agent 150s workflow/45s role limits.
If approved, it requires a new clean owner-authored commit and complete required gates;
the old timeouts cannot be relabeled as passes. If not approved, retain1800 and diagnose.

All data is synthetic and actions simulated. No live quality, production capacity,
Linux-browser, macOS, real CI or hosting result. Main application bytes are unchanged.
Local evidence: `.agent/g3d-final-integration/b246145-held/`, including both failures,
native full pass,11-case focus, frontend/browser logs, process recovery and proposal.
