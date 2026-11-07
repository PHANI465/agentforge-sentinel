# Handoff: task/claude-demo01-recorded-replay

- Task and acceptance criteria: DEMO01 portable key-free recorded synthetic replay
  (docs/prompts/CLAUDE_DEMO01_RECORDED_REPLAY.md; batch Worker C under
  docs/prompts/CLAUDE_PARALLEL_BATCH_2026-11-06.md)
- Tool and worktree: Claude Code (Opus 5.5 / High), E:/PHANI/sentinel-wt/claude-demo01-recorded-replay
- Updated: 2026-11-07 UTC
- State: ready for review (task-branch only; not accepted, not merged)
- Code reference tested before this note: 8675b5c191c3280755bc36406d7b0b74acd40c3c (capture,
  validate, focused pytest). The browser QA script fix in the following commit was tested as a
  working-tree change, then committed together with the fixture and docs.
- Final check evidence: reported in the final chat handoff after the final commit (validate
  plus the pure focused tests rerun on the committed tree); no self-referential SHA here.
- Owned/changed paths: demo/ (index.html, replay.css, replay.js, README.md, data/recorded-case.json,
  data/manifest.json, tests/browser_qa.mjs), scripts/build_recorded_demo.py,
  tests/test_recorded_demo.py, docs/demo/DEMO01.md, this note. Nothing outside these paths was
  touched.

## Implemented

- Static replay (10 frames) with persistent labels, a per-frame observed ledger, safe DOM
  text only, in-page record links only, CSP, and a SHA-256 check against the manifest in the
  browser. No backend, provider or approval controls.
- Generator `capture`: an owned disposable cluster (local_stack machinery), operator-only
  setup, then the runtime role through the production HTTP app (TestClient); rule scorer plus
  deterministic three-role workflow; scripted approval, one execution and an idempotent retry;
  allowlisted projection, validation and a real-token scan before any public write.
- Generator `validate`: pure re-check of the tracked fixture and manifest.
- Fixture data SHA-256 f24da3ca46fab8d0dc15b0ae7be98f60f2d4d5f8f9b1a9ae19125cc87c42ee2c (45,531 bytes).

## Verified

- Capture on 8675b5c (clean tree; src identical to 495c7d3): `build_recorded_demo.py capture`
  -> 10 frames valid; 7 public files x 15 forbidden values (real 43-character token included)
  clean; private raw capture and log clean; cluster stopped (verified) and its directory
  removed.
- `build_recorded_demo.py validate` -> ok.
- `pytest -q tests/test_recorded_demo.py` -> 15 passed (includes a second real capture on a
  pytest-owned cluster and the negative controls).
- `node demo/tests/browser_qa.mjs --node-modules <canonical web/node_modules>` -> run 1: 28/30
  (two QA-script bugs, diagnosed); run 2 after the fix: 30/30.
- After the slot: no postgres, Chromium or QA node process from this task remained.

## Not verified / gaps

- Full six-command gate not run on this branch (the coordinator runs it on the combined
  preview).
- Browser QA only in Windows headless Chromium; no Linux, WebKit/Firefox or screen-reader run.
- Model scorer, live adapters, uvicorn, browser auth and the product web UI were not exercised
  by the capture.
- Once, before the slot, PostgreSQL was started for about 10 s: a pytest `-k` filter
  unintentionally selected the DB test. The test errored at once and conftest teardown stopped
  the cluster; no process was left behind.

## Next action

Codex reviews DEMO01 together with the combined batch preview. If the generator or `src/`
changes, rerun `capture` (one heavy slot) and commit the regenerated fixture.

## Coordination and provenance

- No contract, migration, grant, production src, web/, CI, dependency or lock changes. Reused
  unchanged by import: scripts/local_stack.py, sentinel.devdb/db/roles/api/service/coordinator.
- Playwright is used read-only from an existing install; no download.
- Raw capture, logs, the QA report and screenshots are private under the ignored .agent/demo01/.
