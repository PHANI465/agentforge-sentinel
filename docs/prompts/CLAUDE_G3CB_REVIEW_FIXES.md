# Claude G3C-B R38/R39 review corrections

**Checkpoint:** Claude has delivered the R38/R39 correction at 6014680b5713105b5c29b8857561af650bec2b9c.
The owner paused work for today. Do not rerun this completed implementation assignment.
Codex re-reviews that exact candidate tomorrow; acceptance and integration remain pending.
The original assignment below is retained as implementation/review history.

Recommended coding assistant: **Claude Opus 5.5 / High**. This is a focused Unicode-contract
and React render-ownership correction, with event/commit ordering and regression evidence.
No architecture redesign or live provider call is requested.

Read current task/coordination:docs/reviews/G3C-B-bb5943e.md with git show, current AGENTS,
STATUS/TASK_QUEUE and the accepted G3C-A review. Resume the existing
E:/PHANI/sentinel-wt/claude-g3c-trace-ui, task/claude-g3c-trace-ui, from exact
bb5943e681708d8fbf3db031f06f5d37a57389c9. Preserve 16b67fd API and all delivered UI work.

If an old candidate check is still running, let it reach normal cleanup and retain its
reports before tracked edits. Do not launch another full old-candidate run. This source
has two demonstrated UI defects even if its backend gate passes. Preserve failure logs
from the missing-artifact and runtime-record startup race; do not claim repeated green
runs prove the race impossible.

1. R38: note() must use Unicode code-point bounds matching the accepted maxLength 400,
   not UTF-16 code-unit length. Keep min 1/max 400, null/type handling and original inert
   text. Add proper BMP/ASCII and supplementary-character boundary cases, including
   a valid 400-code-point note and invalid 401. Do not change frozen schema/example bytes.
2. R39: render-visible state, history and selection must be owned by their current
   session/case/workflow/permission context. Returning a previous ready payload until a
   passive effect clears it is insufficient. Immediately mask/clear stale content when
   context differs or canRead=false, and retain request-generation/abort guards for late
   results. Reset context-owned selection on session/case changes; preserve the explicit
   prior workflow and allowed same-context history across refresh/loading.
3. Add regressions that inspect committed content before passive effects as well as the
   existing deferred-response cases. Cover case, token/session and read-permission changes;
   cover workflow selection too. Keep positive same-context refresh/history behavior.
   App sign-out currently unmounts: retain that control, but do not use it to avoid fixing
   the hook's ownership contract. Do not reset the whole Workbench and lose the preserved
   execution idempotency key or other existing action state.

Independent probe source: E:/PHANI/Interview/tmp/Codex.g3cb.probes.test.tsx.
Python-validated response: E:/PHANI/Interview/tmp/g3cb-schema-valid-emoji.json; generated
with the frozen InvestigationTrace model and matching updated role-output hashes.
Original scripts/results also live in canonical ignored .agent/g3cb-review/bb5943e/.
The expanded probe gives 4 real assertion failures and 2 passing controls on bb5943e. The
context probe observes committed DOM with useLayoutEffect; it does not claim a browser
paint or a server-auth bypass. Port meaningful tests into the maintained test suite;
remove hard-coded local review paths. Do not turn a commit-boundary assertion into a
waitFor-final-state assertion, or weaken cases to fit current behavior.

Use the same owned web/, docs/ui/ and task handoff paths. No production src/, contracts,
migrations/grants, agents-1.0, model/data/evals, dependencies/lockfiles, browser_stack
lifecycle implementation, CI/skip/checker timeout or central coordination edits. Preserve
all frozen inputs, copied fixture bytes and provenance. Keep startup waiting, suite
selection, original 19/new 10 browser checks, 20/12 harnesses and secret scanning intact.
No unrelated refactor, new framework or activation of another editor in this checkout.

Demonstrate maintained regressions fail on exact bb5943e for these behaviors, then pass
with the focused fix. Final clean owner-authored commit: frontend typecheck/unit/build,
original browser suite and trace browser suite, focused helpers if changed, then the
original sequential Windows/native full backend/JUnit/export/package/ML checks. Record
actual ordering/results and safe cleanup; no duplicate full suite just to get XML. Use
ci_test_gate.py --validate-only PATH on the strict run's own report. Keep normal logging
and native login/native-tool preflight. Only the existing live-Claude skip is allowed.
If another failure appears, preserve and diagnose it; do not rerun until green or increase
limits. All new commits: PHANI465 <pgavara1@asu.edu> author and committer alone, no trailers,
no amend/rebase/reset. Return exact tested SHA, failing-first and final results, remaining
limits and one handoff. No main merge/push/remote, provider, new spend or G3D evaluation.
