# Draft only: full-suite command budget

**Completed November 5:** the approved 2700-second verification-command budget and
combined integration pass all required final gates at aa5ee1e. See the
[release record](../releases/G3D-P1-main-integration-2026-11-05.md). Earlier pending/held
instructions below are history. The next separate task is the workflow-backup proof.

**Owner approved November5:** the verification-command cap may change to2700 seconds.
Decision0009 governs this exception. Earlier pending/protected wording below is historical.
Final certification is still required; no old timeout becomes a pass.

This is not applied and is not release acceptance. Both Windows attempts hit the existing limit,
at 506 and 637 of648 progress markers; the 11 unreached cases pass separately. The saved resume plan forbids timeout
relaxation, so changing this plan needs the owner's explicit decision.

Concrete proposed diff in scripts/agent_check.py:

```diff
-CHECK_TIMEOUT_SECONDS = 1800
+CHECK_TIMEOUT_SECONDS = 2700
```

The value is the maximum lifetime of each verification command, not a transaction,
agent, HTTP, database, approval or individual-test deadline. All test bodies/assertions,
skip rules, complete test collection and six check commands remain required. A timeout
or assertion failure still fails. Existing failed reports remain failed and preserved.

Reason: the complete suite now has648 cases; the current Windows full run exceeded
1800s after 506 completed tests, versus861s for the same prefix in the accepted author's
report. The controlled rerun reached 637 of648 before the same cap, without a reported assertion failure. The other five commands passed, and native Ubuntu's complete647+one-skip gate
passed on the exact merge. A broader runtime slowdown is observed; its cause is not
proven. Owner-reported app closure and charging preceded one controlled unchanged rerun.
Do not use this proposal to claim the slowdown has been fixed or capacity improved.

If approved, record the decision and preserve the finite 45-minute bound. Make a new
owner-authored clean commit and run both required full backend gates sequentially,
same-run JUnit/skip validation, HTTP/package/ML and the frontend/browser compatibility
checks. No release is accepted until complete checks pass. No model, dependency, data,
contract, live provider, global power setting, remote or deployment change.

Alternative: retain1800s and keep integration held for focused Windows runtime diagnosis.
