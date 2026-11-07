# Handoff: task/claude-demo01-recorded-replay

- Task and acceptance criteria: DEMO01 portable key-free recorded synthetic replay
  (docs/prompts/CLAUDE_DEMO01_RECORDED_REPLAY.md), the native-gate scan fix (preview 82316a5),
  and now R48 (docs/prompts/CLAUDE_DEMO01_PROVENANCE_FIX.md; docs/reviews/Parallel-batch-830f018.md),
  dispatched as Worker B of docs/prompts/CLAUDE_BATCH_REVIEW_CORRECTIONS_2026-11-06.md.
- Tool and worktree: Claude Code (Opus 5.5 / High), E:/PHANI/sentinel-wt/claude-demo01-recorded-replay
- Updated: 2026-11-07 UTC
- State: ready for review (task branch only; not accepted, not merged)
- Code reference tested before this note: af4890afb3b6f0af9e85d3841428b10d4ddb25b6 (generator and
  tests; recapture, validate, focused pytest including a real capture, Chromium QA) with the
  fixture commit ed4afe177aedb36fecfdb6f5bbbb1b1f0598acfa.
- Final check evidence: reported in the final chat handoff after the final commit; no
  self-referential SHA here.
- Owned/changed paths: demo/ (index.html, replay.css, replay.js, README.md, data/recorded-case.json,
  data/manifest.json, tests/browser_qa.mjs), scripts/build_recorded_demo.py,
  tests/test_recorded_demo.py, docs/demo/DEMO01.md, this note. Nothing outside these paths.

## Implemented

- Static replay, capture generator and validator as before (see docs/demo/DEMO01.md).
- Native fix (26f73e0): the account name is a scan needle only in path form. Kept unchanged.
- R48 (2bcc03d, af4890a): history-independent freshness. The capture records
  `provenance.content_identity`:
  - `inputs`: scripts/build_recorded_demo.py and src/, excluding __pycache__/, *.egg-info/ and
    *.pyc/*.pyo;
  - one SHA-256 per file, computed with CRLF read as LF;
  - an aggregate over the file digests.

  `freshness_problems()` compares this record with the checkout's actual bytes and makes no
  Git call. The validator CLI and the test use it. Missing or malformed identity fails with
  a re-capture message. The skipping Git-history test was removed, and `generator_commit`
  stays as provenance only. The page and QA show the identity.
- Fixture recaptured once (ed4afe1): SHA-256 663a27d1b7f6177b9a6f90381041b2c63e2628fe9b11a5b46ef060aba2575625,
  49,327 bytes, 33 identity files, aggregate c7b2a5897b75371bc026caa5fce47ef4a5e4e6678c083e534f8734463099bfd1.
  It supersedes fa47192e... (521148d) and f24da3ca... (2044060), which stay in history. A copy
  of the 521148d fixture and manifest is in .agent/r48/old-capture-521148d/.

## Verified

- Failing first:
  - unmodified 47b7cf1: the reviewer's missing-history probe skips, and the gate validator
    reports `unexpected skip` (.agent/r48/original-47b7cf1-missing-history-probe.txt);
  - the new tests on the 47b7cf1 generator: 17 failed, 19 passed
    (.agent/r48/failing-first-on-47b7cf1-generator.{txt,xml});
  - the allowlist regression test on 2bcc03d: 1 failed (.agent/r48/failing-first-scope-key-on-2bcc03d.txt).
- Recapture 1 on 2bcc03d failed safely: forbidden projection key `scope` in the new identity;
  nothing public was written; cluster stopped and removed (.agent/r48/recapture1-FAILED-*.txt).
- Recapture 2 on af4890a: pass. 10 frames valid; 8 public files x 18 forbidden values clean
  (real 43-character token); cluster stopped (verified) and removed (.agent/r48/recapture2-*.txt;
  stamp 20261107T152954Z under .agent/demo01/).
- `build_recorded_demo.py validate`: ok.
- `pytest -q tests/test_recorded_demo.py`: 38 passed, 0 skipped, including the real capture
  (.agent/r48/focused-after-recapture2.{txt,xml}). The structured gate validator found nothing
  with no skips allowed (.agent/r48/focused-gate-validation.txt).
- No-Git check: a `git archive` export without .git ran the pure tests (37 passed, real capture
  deselected) and `validate` (ok) (.agent/r48/nohistory-export.{txt,xml}).
- `node demo/tests/browser_qa.mjs` (existing Playwright, loopback): 31/31 (out .agent/demo01/qa-r3,
  log .agent/r48/browser-qa-r3.txt).
- All DB and browser work ran inside the shared heavy-slot lock. Afterwards no QA, Playwright
  or capture PostgreSQL process remained.

## Not verified / gaps

- The full six-command gate was not run on this branch. The coordinator certifies the
  combined preview; the native Ubuntu rerun of this file belongs to the coordinator.
- Not tested in a real shallow GitHub Actions checkout. Missing history was simulated by
  faulting Git and by a `git archive` export.
- The identity covers the generator and src/ only, the same scope as the old check. A
  change in scripts/local_stack.py, contracts or the lockfile does not mark the capture stale.
- Browser QA ran only in Windows headless Chromium.

## Next action

The coordinator includes this branch head in the new combined preview and runs the
Windows and then native gates. If the generator or src/ changes, recapture once in the heavy
slot.

## Coordination and provenance

- No contract, migration, grant, production src, web/, CI, skip allowlist, dependency or lock
  change. Reused unchanged by import: scripts/local_stack.py, sentinel.*.
- Playwright was used read-only from E:/PHANI/agentforge-sentinel/web/node_modules; nothing was downloaded.
- Raw captures, logs, QA reports and evidence are private under the ignored .agent/.
