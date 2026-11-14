# Handoff: task/claude-doc01-ui

- **Task and acceptance criteria:** DOC01 Part C, the local document analysis UI and a
  real browser proof, under `docs/prompts/CLAUDE_DOC01_PART_C_UI.md` (task/coordination
  c7d566b). Scope is `web/`, `docs/ui/`, one browser fixture helper under `tests/support/`
  and this note.
- **Tool and worktree:** Claude Code, `E:/PHANI/sentinel-wt/claude-doc01-ui`. It was created
  from exact main `813b0db3f5e5b289428ea03dc249518f589bf0c2` (DOC01 Part B accepted at
  `d6d509e`, integrated in source merge `e51f47a`).
- **Updated:** 2026-11-13 (local time).
- **State:** ready for Codex review. Not merged and not pushed. Claude's Part B branch, the
  accepted Part A worktree, AN01-M1 and Cursor's seven edits are untouched.
- **Code reference tested before this note:** `ae86cf8` (clean). Exact final-commit checks
  are reported in chat; this note cannot name its own commit.
- **Owned/changed paths:**
  - `web/src/api/{documents.ts, documents.test.ts, types.ts}`
  - `web/src/ui/{DocumentReview.tsx, DocumentReview.test.tsx, Workbench.tsx}`
  - `web/src/App.tsx`, `web/src/styles.css`
  - `web/src/fixtures/http-v1.3/` (29 byte-identical copies plus `PROVENANCE.md`)
  - `web/e2e/{documents.pw.ts, support/documents.ts}`
  - `web/e2e/support/{launch.mjs, suite.mjs, suite-harness.mjs}`
  - `web/package.json` (a script only; no dependency)
  - `tests/support/doc01_browser.py`, `docs/ui/DOC01-document-review.md` and this note

  No production `src/`, `contracts/`, migration, worker, model/data/evals, lockfile, CI or
  skip policy, or central STATUS/TASK_QUEUE changed. The browser stack's
  ownership/recovery code (`browser_stack.py`, `serve.mjs`, `global-teardown.ts`,
  `process-identity.mjs`) is unchanged.

## Dependency and example provenance

- `contracts/http/openapi.v1.3.json` SHA-256
  `d4306c651f8a555fca6e309a27c7bd5b2c133f07d4cfc2f07f1fcde772eae4dc`. This is checked in
  `web/src/api/documents.test.ts`.
- `contracts/http/examples-v1.3/` holds **29** files at `813b0db`, not the 31 the dispatch
  mentions. That matches the Part B exporter's sequence: 14 analyses, 3 uploads, 1 records
  page, 1 delete and 10 errors. All 29 are copied byte-for-byte, with per-file SHA-256 and
  sizes in `web/src/fixtures/http-v1.3/PROVENANCE.md`. A test checks the hashes, byte
  equality with the frozen files and the count. No accepted example was modified.

## Implemented

See `docs/ui/DOC01-document-review.md`.

- A separate **Document review** section, shown only with `analyze_document`.
- **Upload:** raw bytes with the v1.3 media type, without multipart or a filename. The
  10 MiB cap is shown and enforced client-side; the server's 413 is authoritative.
- **Analysis:** an explicit request, with confirmation before a re-analysis replaces the
  stored result.
- **Strict DTO parsing:** contradictions become *unconfirmed*, never an empty report.
- **Rendering:** exact n-of-d ratios, with 0/0 shown as not applicable; separate currencies
  with plain-language reconciliation; table typing or PDF structure (no OCR); provenance
  details; inert text throughout; evidence buttons only for records on the current page.
- **Paging** by the returned `next_offset`.
- **Delete** uses the accepted DELETE route.
- **Failures:** 404 clears stale content; worker 5xx is never shown as a result and offers a
  retry; malformed, non-JSON and network failures are handled.
- **Fencing:** each request carries a generation counter and an AbortController, and the
  section is keyed by session. The token and handle stay in memory only.

## Verified (before this note)

- **Frontend:** typecheck (app and e2e) passes; 228 unit and component tests (133 existing
  plus 59 API plus 36 component); build OK.
- **Browser suites on Windows:**
  - documents: 12 passed, including the expected controlled-failure probe (run 9);
  - legacy 19/19, with the shutdown and entrypoint harnesses;
  - trace 10/10;
  - suite-harness passes.
- **Earlier documents runs failed, and each was diagnosed before the next.** Evidence is in
  `.agent/doc01-c/run{1..7}-evidence/` (runtime and recovery records, test-results; no
  secrets file).
  - **Runs 1–2:** Chromium evicted the upload response body, so the test could not learn
    the handle. The handle is now observed from the run's own worker store.
  - **Run 3:** wrong keyboard expectation (Tab moves forward from the alert; Shift+Tab
    returns to Upload). The shared scanner also reported **1 token hit**. Its file could not
    be identified afterwards: the scanner reports counts only, and no text artifact held a
    token-shaped string. The suite's own token scan now reports the matching file names,
    and every later run reports 0 leaks.
  - **Runs 4–5:** the test's direct API helper sent no JSON body to `/analysis`, and the API
    answered 422 before resolving the handle. Run 5 repeated run 4 because a patch had not
    applied.
  - **Runs 6–7:** sign-out aborts the in-flight analysis by design, so no response event
    came. The test now waits for request finished or failed. Run 7 repeated run 6 because
    an edit had not applied.
  - **Cleanup each time:** the store was kept as evidence and later launches refused to
    start over it. Before clearing the stale runtime by hand, I verified that the recorded
    API and Vite PIDs had exited and that the stack directory had been removed.
- **QA screenshots:** desktop and narrow layouts inspected (private copies in
  `.agent/doc01-c/qa/`). They show no token, file name or path.

## Not verified / gaps

- Linux browser execution; the browser suites ran on Windows only.
- An analysis abandoned by sign-out still completes on the server and replaces the stored
  result. The departed session never sees it.
- Expired handles are reported only as the shared 404; the UI does not schedule
  expiry-aware refreshes.

## Next action

Codex reviews the UI and the documents browser suite at the final SHA before combined
integration.

## Coordination and provenance

- Contract use is read-only. If a backend change were needed it would be requested
  separately; none was.
- The opt-in sessions in the browser suite are issued by `tests/support/doc01_browser.py`
  as the operator, against the ownership-checked stack manifest. The tokens are printed to
  the test process only and scanned for in every artifact.
