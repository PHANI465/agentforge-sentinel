# Cursor I02 Part B real model browser acceptance

Start Part B now. Codex has accepted I01 at exact 7dd9428c70a7741af1c4781d22fd6b184f957444 (task/claude-model-browser-fixtures). Review: latest task/coordination:docs/reviews/7dd9428.md. Your Part A 50856be3da54ffdadd6cda7a0fcd5e59a9b21733 is already accepted and N1 is resolved.

## Include the accepted dependency

Reuse task/cursor-model-integration in E:/PHANI/sentinel-wt/cursor-model-integration. Read current coordination AGENTS/STATUS/TASK_QUEUE, this prompt and docs/prompts/CURSOR_I02.md. Inspect HEAD/status and preserve your Part A changes. Include exact 7dd9428 on this task branch, record the parents/resulting integration SHA and any conflict resolution. This is the assigned task-dependency merge, not a main merge. Leave accepted U03/U02, Claude's I01 and C07 checkouts unchanged. Do not replace your branch with I01 or lose the Part A fix.

Read docs/api/model-browser-fixtures.md and docs/api/browser-fixtures.md from the final I01 SHA. The older e0ff81f contract candidate is superseded: status remains exactly {api,database}; get mode from GET /v1/scoring or private manifest.api.scorer. Preserve I01's 1800-second checker timeout; pending C06 edits join separately later.

Install/sync this worktree's locked environment with both dev and ml extras: uv sync --locked --extra dev --extra ml. Verify Python/Sentinel imports resolve to this worktree. Keep SENTINEL_LIVE_CLAUDE=0 and the external test-database override unset. Ensure subprocesses use this environment; a green run in the old coordination environment is not evidence for this integration.

## Ownership and runner

Own web/ (frontend, Playwright tests, runner/adapters/lock), docs/ui/ and your task handoff. Read-only browser assertion helpers under web/e2e/support/, including inspect_case.py, are yours to extend narrowly for synthetic scoring/row assertions. Preserve existing helper outputs consumed by old tests; add a bounded read operation where necessary. Keep database URLs/tokens private. Do not edit src/sentinel/, contracts/, migrations, tests/support/ backend lifecycle, p1 reports/artifacts or central STATUS/TASK_QUEUE. Send any backend request as a precise reproduction to Codex/Claude.

Preserve the accepted rule-mode browser suite and add real model-mode cases, using isolated owned stacks/runs or clearly serialized mode changes with restoration. Keep R21/R22 lifecycle safeguards, exact process identity/no fallback kill, invocation ownership, recoverable cleanup, private secrets until scanning finishes and fail-closed artifact checks. Continue the genuine controlled failure artifact scan. Include all tokens from the private manifest, including ingest_only, in hygiene checks. No raw auth traces, browser token storage or public seed/clock/mode-selection route.

I01 lifecycle: start --scorer model implies model fixtures; start --scorer rule --model-fixtures prepares both histories with a rule-configured API; restart-api --scorer rule|model changes mode through a real process restart. Normal start without new flags keeps the old C02 scenarios. Seed fresh scenario ordinals as needed, especially before using five-minute approvals. These are local test-helper commands, never public API controls.

## Verify actual browser API database behavior

1. Read current scoring from the real API: model name/version/semantics, threshold 4.0295386895426815e-06, artifact identity and investigator label. The UI shows uncalibrated ranking, not probability. Compare rendered labels/values with authoritative API data; verify hashes in the API/persisted outcome where the UI only shows name/version.
2. Read the real /v1/model-results/p1 response. Assert rendered baseline AP, uncertainty, policies (442 frozen-threshold flags versus 510 daily-top15), calibration/slices and PR points agree with it and the frozen report. Labels remain offline synthetic benchmark; currencies stay separate and scenario slices are offline hidden truth.
3. Submit model_missing_profile through the UI. Assert 422 account_profile_missing and no persisted transaction/outcome/alert/case for that external ID. A case-only not_found assertion alone does not prove no transaction was stored; extend the read-only assertion adapter if needed.
4. Submit a fresh model_live_alert through the UI. Assert actual score 0.802130558706, feature values, USD profile/currency, no prior disclosure, stored model provenance and a new case. Complete investigate -> human approval -> separate simulated execute and compare the persisted action/audit. Seed fresh ordinal/account data for independent tests.
5. Observe recorded model_alert (score 0.61962960122, GBP transaction, USD home profile, one disclosed fraud) and C02 open_case (rule score 0.6). Their stored identities/thresholds/inputs stay distinct from current server configuration.
6. Use real API and Postgres restarts, including restart-api --scorer rule then model. Re-read configuration, keep historical identity, and verify replay returns the original saved scoring. Assert process restarts rather than only recreating JS objects. Restore modes for subsequent cases.
7. Retain rejection, expiry/reopen/fresh approval, stale revision, provider failure, ambiguous execution retry with one persisted effect, session isolation and sign-out/late-response handling. Rerun the original rule-mode browser coverage against the combined runtime-role backend. Add ingest_only403 and foreign-session model-case denial. Keep fixtures out of failed live responses.

Happy-path model requests must use the actual backend/artifact/Postgres. Fault injection may deliberately delay/drop a real committed response to test ambiguity, with one real persisted action. Ordinary browser tests call no LLM/subscription/provider.

## Final handoff

Run frontend tests/typecheck/build, the reproducible full rule/model browser command (including scanner/harnesses), relevant schema/HTTP/Node checks and strict checks with dev/ml extras on the final clean committed tree. Use actual exit codes, not a final tail/grep result. Commit explicit owned paths and record merged dependencies, new versus old coverage, real mode/role/score assertions, cleanup and gaps. Preserve private recovery information if stop fails; never delete it to manufacture a clean rerun. No main merge, push, remote setup, WSL change or hosting is assigned. Return the final SHA and real test results for Codex review.
