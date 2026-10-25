# Handoff: task/claude-model-browser-fixtures

- **Task and acceptance criteria:** I01 (docs/prompts/CLAUDE_I01.md on task/coordination 14477db). Combined model-backend and browser fixtures for Cursor's I02 real-model browser tests.
- **Tool and worktree:** Claude Code, E:\PHANI\sentinel-wt\claude-model-browser-fixtures.
- **Updated:** 2026-10-25 (local time).
- **State:** ready for review.
- **Dependencies and integration:**
  - base: accepted C07 275509af655a81a62bba28e74e9d8ab6c8d9cf5f;
  - merged: accepted U03 a5716e252af2077a507767a3f819ddf44ea41c12;
  - integration commit: **5488a61d6869cc326a661f02dd3548e1398349c8**, with parents 275509a (first) and a5716e2 (second), and merge base C02 0e72b0b.

  The merge was a clean automatic merge with no conflicts and no hand-resolved content. U03 brought `web/`, `docs/ui/`, Cursor handoffs and its own coordination-doc history unchanged. Main, the old coordination application source and C06/C08 were not merged.
- **Contract candidate published early:** e0ff81f (`docs/api/model-browser-fixtures.md` plus the fixture code). One correction followed in this commit: `status` output was restored to C02's exact shape (see Verified).
- **Code reference tested before this note:** the final working tree of this commit. Strict checks run after the commit and are reported in chat.
- **Owned/changed paths:**
  - `tests/support/browser_stack.py`, `tests/support/scenarios.py`, `tests/support/fixture_app.py`;
  - `tests/test_model_browser_fixtures.py`;
  - `docs/api/model-browser-fixtures.md`, `docs/api/browser-fixtures.md` (I01 note);
  - this note.

  Not modified: `web/` (including its lock and the browser runner), `docs/ui/`, the public HTTP contracts and examples, the p1 report and artifact, production `src/`, STATUS and TASK_QUEUE.

## Implemented

- **Model mode in the C02 stack** (same lifecycle, ownership, cleanup and token rules):
  - `start --scorer rule|model [--model-fixtures]` and `restart-api --scorer rule|model`;
  - the value maps only to production `SENTINEL_SCORER` values `rule` or `model:hgb_balanced@p1`, which the production `scorers.from_environment()` validates, so no artifact path can be supplied;
  - there is no HTTP route for mode, seed, clock or capability.
- **Runtime role:** the API process connects as `sentinel_browser_runtime` in every mode. This is the C05 role created by `roles.grant_runtime`; trust auth on loopback means no password. Setup and seeding keep the owner connection (`database_url`), so `inspect_case.py` is unaffected.
- **Model scenarios** (opt-in), seeded with the accepted registered scorer through `provision_accounts` / `record_disclosures`:
  - `model_alert`: a recorded model case with exact stored inputs and provenance;
  - `model_missing_profile`: an unprovisioned account and request body;
  - `model_live_alert`: a provisioned fresh account, plus `expected_scoring` computed at seeding by C03 `compute` and the loaded pipeline.

  An `ingest_only` token covers the 403 checks. Profiles open exactly 400 days before `occurred_at`, so every input and score is wall-clock independent. A model fixture that does not alert fails seeding (fail closed).
- **Default stacks:** without the flags they are seeded exactly as in C02. `status` output is byte-for-byte the C02 shape, and the current mode is the manifest's `api.scorer`.

## Verified

Windows 11, `uv sync --locked --extra dev --extra ml`, PostgreSQL 14.17 disposable clusters, `SENTINEL_LIVE_CLAUDE=0`, no external DB, no LLM calls.

**New real-process tests:** `tests/test_model_browser_fixtures.py`, 10 passed.

| Area | What was verified |
| --- | --- |
| Runtime role | The API connects as the runtime role: setting the role `NOLOGIN` makes requests fail (5xx), and restoring it recovers. The runtime role can read profiles but cannot update them. |
| Routes and permissions | `/v1/scoring` returns model, `uncalibrated_score`, threshold 4.0295386895426815e-06, artifact sha 6c2982d1… and `results_id` p1. `/v1/model-results/p1` equals the frozen report as the `ModelResults` DTO serializes it (label and synthetic flag included). `ingest_only` gets 403 on both routes, no token gets 401, and an unknown ID gets 404. |
| Recorded model case | The case detail's stored scoring equals the seed record: score 0.61962960122, exact f1 values, GBP currency, 0 history rows, 1 disclosure used, USD profile, pins `hgb_balanced`. The C02 `open_case` stays rule (no `model` or `inputs`), and case summaries distinguish the two kinds. |
| Cross-session | `other_session` gets 404 on the case, its audit and investigation, and does not see it listed. |
| Missing profile | 422 `account_profile_missing`; no transaction or outcome stored; transaction and case counts unchanged. |
| Live ingestion | For the seeded record and an on-demand ordinal, the live API returns exactly `expected_scoring`: score 0.802130558706, alerted, model provenance, values. The stored outcome equals the response. |
| CLI | `start --scorer model` through the CLI prints no tokens or DSN. Model-scenario IDs and expected scores repeat across fresh stacks. `status` is the C02 shape, and stop is clean. |
| Default stack | Rule mode, no model scenarios, no `ingest_only`. A model seed is refused. `restart-api` into an unregistered scorer fails closed (port closed), a rule restart recovers, and stop is clean. |
| Failed model start | A start with an unbindable scorer cleans up completely (no directory, port closed). |
| Scorer switch | A CLI `restart-api --scorer rule` brings a new PID and `/v1/scoring` returns rule. The model case is byte-identical; its replay returns the stored model scoring; a new rule ingestion has no `model` or `inputs`. Then `restart-db` and `restart-api --scorer model`: the model case and audit are unchanged, and the rule record replays as rule. |

**Old suites, rerun on the combined tree:**
- C02 browser fixtures: 40 passed, now with the runtime-role API.
- Full backend suite (working tree before the status-shape correction): 396 passed and 1 skipped (opt-in live Claude), 969 s. It ran concurrently with frontend commands for part of that time.
- 21 helper tests, 15 domain schema exports, HTTP v1/v1.1 export check (all contracts and examples byte-identical) and Node transport passed.
- After the status-shape correction, the 50 fixture tests (I01 plus C02) passed again in 450 s.

**Frontend compatibility** (combined tree, Cursor's commands unmodified, `npm ci --offline`):
- `npm run typecheck` passed; `npm test`: 37 passed; `npm run build` passed.
- `npm run test:e2e`:
  - **First run:** 11 passed, 1 failed. Cursor's restart test asserts `stackStatus()` equals exactly `{api, database}`, and my candidate had added a `scorer` key; I restored the C02 shape. The harness then failed closed, recording `controlled_failure_artifact_missing` and keeping its recovery record.
  - **Before the rerun:** I verified the recorded API and Vite PIDs were gone, the three ports were closed and no worktree Postgres was running. Only then did I delete that run's four preserved `.runtime` files, all in this I01 worktree.
  - **Rerun:** **14 passed** (1.6 min), exit 0.

**Resources:** stacks from the tests stopped cleanly. The only leftovers are `web/e2e/.runtime/browser.txt` (the Chromium version string) and an empty `stacks/` directory, both ignored, as in Cursor's documented teardown. `node_modules/` and `dist/` are ignored.

## Not verified / gaps

- **Platforms:** Windows 11 only; the POSIX lifecycle path is still untested; no CI.
- **Browser coverage:** no real-model browser test exists yet; that is Cursor's I02. N1 (nullable `ReliabilityBin` fields / optional `labels_observable_by_horizon` in `web/src/api/analysis.ts`) is Cursor's and is not addressed here.
- **Unhandled 500:** the response body is plain text, not JSON. This is pre-existing and documented in C05 as a proposed contract change.
- **ml extra:** model fixtures need it. Rule-only stacks still work without it; this was not separately re-run in a dev-only environment.
- **Strict-check time:** the full suite now takes about 13–16 minutes, close to the 900 s per-check limit in `agent_check.py`. The strict result after commit is reported in chat.

## Next action

Codex: review I01 (integration 5488a61, contract e0ff81f and this commit). If accepted, Cursor's I02 consumes the accepted I01 SHA with `docs/api/model-browser-fixtures.md`.

## Coordination and provenance

- **Changed:** only test support and docs. No production code, public contract, migration, dependency or lock changed; the frontend lock was unchanged by `npm ci`.
- **Reused:** C02's owned lifecycle (extended, not copied) and the C05/C07 operator methods, all in-repo.
- **Secrets:** no secrets committed. Tokens exist only in private manifests, and no bearer values or credential-bearing URLs appear in output or this note.
