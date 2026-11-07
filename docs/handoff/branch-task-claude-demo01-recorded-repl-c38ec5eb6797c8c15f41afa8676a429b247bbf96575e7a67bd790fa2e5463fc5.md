# Handoff: task/claude-demo01-recorded-replay

- Task and acceptance criteria: DEMO01 portable key-free recorded synthetic replay
  (docs/prompts/CLAUDE_DEMO01_RECORDED_REPLAY.md; batch Worker C under
  docs/prompts/CLAUDE_PARALLEL_BATCH_2026-11-06.md), plus the coordinator's native-gate fix
  (preview 82316a5).
- Tool and worktree: Claude Code (Opus 5.5 / High), E:/PHANI/sentinel-wt/claude-demo01-recorded-replay
- Updated: 2026-11-07 UTC
- State: ready for review (task branch only; not accepted, not merged)
- Code reference tested before this note: 26f73e0ff2cd4101ec65e7b51009338ba55fcbfb (capture,
  validate, focused pytest, browser QA on the new fixture)
- Final check evidence: reported in the final chat handoff after the final commit (validate
  plus the pure focused tests rerun on the committed tree); no self-referential SHA here.
- Owned/changed paths: demo/ (index.html, replay.css, replay.js, README.md, data/recorded-case.json,
  data/manifest.json, tests/browser_qa.mjs), scripts/build_recorded_demo.py,
  tests/test_recorded_demo.py, docs/demo/DEMO01.md, this note. Nothing outside these paths was
  touched.

## Implemented

- Static replay (10 frames) with persistent labels, a per-frame observed ledger, safe DOM text
  only, in-page record links only, CSP, and a SHA-256 check against the manifest in the
  browser. No backend, provider or approval controls.
- Generator `capture`: an owned disposable cluster (local_stack machinery), operator-only
  setup, then the runtime role through the production HTTP app (TestClient); rule scorer plus
  deterministic three-role workflow; scripted approval, one execution and an idempotent retry;
  allowlisted projection, validation and a real-token scan before any public write.
- Generator `validate`: pure re-check of the tracked fixture and manifest.
- Native fix (26f73e0): the account name is a scan needle only in path form (`/home/<u>`,
  `Users/<u>`, `Users\<u>`, JSON-escaped). Home and checkout paths are matched in every
  separator form. Regression tests cover product-word account names and planted paths.
- Fixture data SHA-256 fa47192ede8d9ed2c4ab5bd7e69d3e589542377a131d21709aba34696d92bcea (45,529
  bytes), captured from 26f73e0. It supersedes f24da3ca46fab8d0dc15b0ae7be98f60f2d4d5f8f9b1a9ae19125cc87c42ee2c
  (captured from 8675b5c).

## Verified

- Capture on 26f73e0 (clean tree; src identical to 495c7d3): 10 frames valid; 8 public files x
  18 forbidden values (real 43-character token included) clean; private raw capture and log
  clean; cluster stopped (verified) and its directory removed.
- `build_recorded_demo.py validate` -> ok.
- `pytest -q tests/test_recorded_demo.py` -> 21 passed (includes a second real capture on a
  pytest-owned cluster, the negative controls and the new scan regression tests).
- `node demo/tests/browser_qa.mjs` on the new fixture (out .agent/demo01/qa-r2) -> 30/30.
- After the slot: no postgres, Chromium or QA node process from this task remained.
- Earlier run on 8675b5c (superseded): capture, validate and pytest (15) passed; QA 28/30, then
  30/30 after two QA-script fixes.

## Not verified / gaps

- Full six-command gate not run on this branch (the coordinator runs it on the combined
  preview). The native rerun of this test file is the coordinator's.
- Browser QA only in Windows headless Chromium; no Linux, WebKit/Firefox or screen-reader run.
- Model scorer, live adapters, uvicorn, browser auth and the product web UI were not exercised
  by the capture.
- Once, before the first slot, PostgreSQL ran for about 10 s through an unintended pytest `-k`
  match. The test errored at once and fixture teardown stopped the cluster; nothing was left
  running.

## Next action

The coordinator reruns the combined preview gates with this branch head. If the generator or
`src/` changes again, recapture (one heavy slot).

## Coordination and provenance

- No contract, migration, grant, production src, web/, CI, dependency or lock changes. Reused
  unchanged by import: scripts/local_stack.py, sentinel.devdb/db/roles/api/service/coordinator.
- Playwright is used read-only from an existing install; no download.
- Raw captures, logs, QA reports and screenshots are private under the ignored .agent/demo01/.
