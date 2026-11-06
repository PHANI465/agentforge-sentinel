# R43: model browser fixtures must reach their intended checks under modest clock skew

**R43 completed and integrated at aa5ee1e.** Read the final release and current queue.
The [workflow-backup proof](CLAUDE_G3D_WORKFLOW_BACKUP.md) is next; do not repeat this
historical correction or its old pause instructions.

**Completed and accepted at6e461c0; R43 closed. Owner requested a one-day pause.**
Do not repeat this historical assignment or run another unchanged gate. Leave the
candidate clean. Read [the resume plan](RESUME_AFTER_BREAK.md) when the owner returns.

Recommended coding assistant: **Claude Opus 5.5 / High**. Keep fixture-time causality,
exact model features and real browser/runtime behavior aligned without changing the API.
Sentinel investigators stay deterministic; no live provider, paid fallback or --allow-live.

## Exact base and current state

R41/R42 are accepted at dddd0b47e5346beed561a7e6216e641394b75348. Do not reopen that
evaluator task or change its preserved worktree. The integration candidate is exact
**8b4e4ebea6cd317812a36f9f7a667452eee0de3a**, not main. It includes current coordination,
the accepted evaluator and Codex's test-only tied-timestamp reference correction.

Read current task/coordination AGENTS, STATUS/TASK_QUEUE,
docs/reviews/G3D-P1-dddd0b4.md and docs/reviews/G3D-P1-integration-8b4e4eb.md with git show.
Create task/claude-g3d-model-fixture-clock in
E:/PHANI/sentinel-wt/claude-g3d-model-fixture-clock from exact 8b4e4eb. Record that SHA.
The exact dependency overrides the generic main-base rule: main still carries the older
G3C application, and only its coordination documents are updated. One editor; preserve
Codex's release checkout, accepted Claude branches and Cursor's seven saved changes.

## Finding and evidence

Windows integration passes all six commands, 634+one allowed skip, same-run JUnit,
HTTP and ML checks. Native integration has **633 passed, 1 failed, 1 allowed skip**:
tests/test_model_browser_fixtures.py::test_missing_profile_is_refused_and_nothing_is_stored
gets 422 future_event_time instead of the intended account_profile_missing. The other
five strict commands pass. No blind full rerun has been made.

tests/support/scenarios.py stamps _model_body.occurred_at with the fixture's current
time. The production ingest guard checks future event time before the missing profile.
If the API's clock is behind the seeder, the fixture tests the wrong precondition. The
WSL host's clock jumps are independently established in the G3C diagnosis, but no jump
was captured inside THIS failure: qualify that causal claim rather than invent proof.

A controlled relative-clock probe uses real disposable Postgres and the restricted
runtime service, without changing the host clock: no skew passes; a 3-second mismatch
fails with exactly future_event_time. Both leave zero transactions/outcomes/alerts/cases.
Probe source and logs are in canonical ignored .agent/g3d-p1-review/dddd0b4/ after
publication, and E:/PHANI/Interview/tmp/test_codex_model_fixture_clock.py. Native originals
remain in ~/codex-g3d-p1-release-reports/; Windows in Codex's .agent/g3d-p1-release/windows/.

## Required narrow correction

Make model fixture transactions valid historical events for a documented small finite
clock mismatch. Prefer a deterministic past-event margin at construction, not sleeps,
retries, conditionally accepting a different error or disabling future_event_time.
Review all three model scenarios, including replay of a seeded alert and on-demand fresh
ingestion, rather than fixing only the assertion that happened to fail.

If transaction times move, keep paired profile opening times exactly 400 days earlier.
Preserve causal profile/disclosure availability, stable IDs, scoped runtime authority,
all f1 inputs and exact stored/live model scores (0.61962960122 / 0.802130558706), model
pins, threshold, missing-profile rollback and idempotent replay. Expected values must
remain grounded in the actual accepted artifact; no model tuning, manifest edits or
changing the frozen expected results merely to accommodate a bad fixture.

A finite fixture margin does not solve arbitrary clock jumps or change production time
semantics. Document the actual tolerance. No host-clock, time-sync or interpreter changes.

## Ownership and verification

Own tests/support/scenarios.py, a focused new tests/test_model_fixture_clock.py,
docs/api/model-browser-fixtures.md and your branch handoff. Add narrow checks to the
existing test_model_browser_fixtures.py only if required. Do not edit production src,
agent_eval.py, test_reliability.py, browser_stack.py/process lifecycle, browser runner,
contracts/migrations/grants, model/data/evals, lockfiles, CI, skip policy, timeouts or
central STATUS/TASK_QUEUE. Backup proof remains a later task.

Port the meaningful relative-clock regression into maintained tests. Prove that the old
fixture fails for its intended assertion on 8b4e4eb, then the corrected fixture reaches
the documented missing-profile error with nothing stored. Include the ordinary-clock
control and exact model feature/score checks for live/recorded/replayed cases, under a
finite backward mismatch. Use real service/runtime authority; clearly label controlled
relative clocks versus real host observations. No production seed/clock/token routes.

Run focused clock/model-fixture/reliability tests. Because these fixtures also feed the
browser, run the unchanged original19 and trace10 browser suites, their lifecycle/secret
checks, frontend typecheck/unit/build and normal verified cleanup. Do not weaken an
assertion, add a skip, change timeouts or substitute mocked JSON for the real stack.

Commit explicit paths as PHANI465 <pgavara1@asu.edu>, sole author AND committer, no trailers
or history rewriting. Run required final exact-clean-commit Windows then native Ubuntu
backend gates sequentially; capture same-run JUnit, exact skip validation, frozen HTTP
export and read-only ML reproduction. Do not rerun the unchanged failed candidate's full
gate. Preserve original evidence and diagnose any new failure before another run.

Return exact SHA/base, meaningful failing-first/controls, unchanged score/pin proof,
actual gates and browser results, cleanup and limits. No main merge, remote/push,
deployment, live comparator, final-case evaluation or new paid use. Codex reviews R43
before resuming application integration; populated-workflow backup follows afterwards.
