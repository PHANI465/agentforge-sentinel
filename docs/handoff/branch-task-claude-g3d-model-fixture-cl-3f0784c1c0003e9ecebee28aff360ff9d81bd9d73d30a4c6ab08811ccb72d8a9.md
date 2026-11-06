# Handoff: task/claude-g3d-model-fixture-clock

- **Task and acceptance criteria:** R43, [CLAUDE_G3D_MODEL_FIXTURE_CLOCK.md](../prompts/CLAUDE_G3D_MODEL_FIXTURE_CLOCK.md) on task/coordination, following [G3D-P1-integration-8b4e4eb](../reviews/G3D-P1-integration-8b4e4eb.md). Model browser fixtures must reach their intended checks under a small, documented clock mismatch, with no change to production time semantics.
- **Tool and worktree:** Claude Code (Opus 5.5 / High), in E:/PHANI/sentinel-wt/claude-g3d-model-fixture-clock.
- **Base:** exact integration candidate 8b4e4ebea6cd317812a36f9f7a667452eee0de3a. This is not main, which still carries the G3C application.
- **Updated:** 2026-11-02, local time.
- **State:** ready for Codex review.
- **Code reference tested before this note:** the working tree on 8b4e4eb with the paths below. Exact-commit gates and browser results are reported in chat; a note cannot name its own commit.
- **Owned and changed paths:**
  - tests/support/scenarios.py
  - tests/test_model_fixture_clock.py (new)
  - docs/api/model-browser-fixtures.md
  - this note

  No production src, agent_eval.py, test_reliability.py, browser_stack.py, browser runner, contracts, migrations, grants, model, data, evals, lockfiles, CI, skip policy or timeouts changed. tests/test_model_browser_fixtures.py is unchanged.

## Implemented

- **`EVENT_MARGIN = 5 minutes`** in scenarios.py. Every model transaction (`_model_body`) occurs that long before the seeding clock reading. `_provision` opens the paired profile exactly 400 days before that same `occurred_at`. This is a deterministic past-event margin set at construction: no sleeps, retries or alternative accepted error.
- **All three model scenarios are covered:**
  - `model_alert`: recorded at seeding, then replayed through the API;
  - `model_missing_profile`;
  - `model_live_alert`, both as seeded and as an on-demand `seed_one`.
- **Unchanged:**
  - decision times, the one-hour operator lead and disclosure times, so causal availability holds;
  - stable IDs, all f1 inputs, model pins and the threshold;
  - stored and live scores (0.61962960122 / 0.802130558706).
- **Tolerance:** the margin is shorter than the operator lead, so operator data stays loaded before the event as well as the decision. The tolerance is documented in docs/api/model-browser-fixtures.md, "Clock tolerance (R43)".

## Verified

- **Failing first on 8b4e4eb** (`.agent/g3d-r43/failing-first-8b4e4eb.log`): with the original fixture and the new test file, 8 failed and 5 passed.
  - Every failure is the production `future_event_time` guard. Missing-profile asserts `account_profile_missing` and gets `future_event_time`; the live, on-demand and replay cases raise `future_event_time`. Each fails at both 3 s and 5 min behind.
  - The 5 passes are the four same-clock controls and the finite-limit check.
- **With the fix:** 13/13 pass.
- **Mutation** (profile not paired, i.e. opened 400 days before seeding rather than before the event): 9 fail on `account_age_days` 399 != 400 (`.agent/g3d-r43/mutation-unpaired-profile.log`).
- **Focused suites:** model fixture clock, model browser fixtures (real stack), model serving, browser fixtures, reliability, the future and budget clocks, and the C07 R23 decision boundary. 93 passed (`.agent/g3d-r43/focused-suites.log`). Ruff is clean.
- **Clock labels:** the new tests use CONTROLLED relative clocks, not host observations. The seeder and the API service each get a fixed clock, the API service runs as a granted runtime role on disposable Postgres, and the host clock is untouched.

## Not verified / gaps

- A finite margin does not handle an API clock more than 5 minutes behind the seeder or arbitrary jumps. The limit test pins that the guard then applies unchanged.
- The original native failure did not capture a paired clock observation, so this fix addresses the demonstrated relative-skew path. It does not claim that a specific jump occurred in that run.
- The rule (C02) fixtures are seeded by the seeder service and never POST seed-time bodies through the API. Browser rule bodies are already in the past. They were not changed.
- No macOS, Linux browser, CI or hosting run.

## Next action

Codex reviews R43 on this commit before resuming the G3D application integration.

## Coordination and provenance

- The relative-clock regression ports Codex's probe (E:/PHANI/Interview/tmp/test_codex_model_fixture_clock.py) into maintained tests. All other code is original to this task. No dependencies, credentials or raw reports are tracked.
- The evaluator worktree (dddd0b4), its preserved failed-gate evidence, Codex's release checkout, other accepted branches and Cursor's seven saved edits are untouched.
