# DEMO01: portable, key-free recorded synthetic replay

Status: delivered on `task/claude-demo01-recorded-replay` for Codex review. Not accepted or
merged. Assignment: `docs/prompts/CLAUDE_DEMO01_RECORDED_REPLAY.md`. Batch:
`docs/prompts/CLAUDE_PARALLEL_BATCH_2026-11-06.md`.

## What it is

`demo/` is a small static page (HTML, CSS and dependency-free JS, all local). It steps
through one synthetic case that was **actually captured** through the unchanged Sentinel
service. A viewer needs no key, login or backend. The page fetches only
`demo/data/recorded-case.json` and `demo/data/manifest.json` from its own folder. It makes no
`/v1` or health request, uses no socket, selects no provider and sends no approval or
execution request. Its controls (Previous, Next, the frame rail, arrow keys and Home/End)
only move between recorded frames.

Every frame shows these labels: recorded, synthetic, rule baseline, deterministic roles,
scripted approval, simulated action. The rule score is a heuristic, not a fraud
probability. The replay is not live inference, and the approval frame has no approve
control.

## What was really captured, and what is fixture

Current capture run: stamp 20261107T152954Z, from generator commit
`af4890afb3b6f0af9e85d3841428b10d4ddb25b6` on a clean tree, after the R48 freshness change
described below. It replaces the capture of stamp 20261107T014928Z (from 26f73e0, fixture in
commit 521148d), which replaced the first capture (stamp 20261107T010104Z, from 8675b5c)
after the scan fix. All runs recorded the same story; only times and IDs differ.

- `src/` was identical to the tested application `495c7d33424054d27d68d08004191d4be37adaf9`
  (G3D-P3). The generator checks this with git at capture time and records it.
- The provenance also records `content_identity`: canonical digests of the generator and of
  all 32 `src/` files (33 files; aggregate
  `c7b2a5897b75371bc026caa5fce47ef4a5e4e6678c083e534f8734463099bfd1`). See "Capture freshness".
- Database: a disposable PostgreSQL 14.17 cluster, created by `scripts/build_recorded_demo.py`
  through the accepted `scripts/local_stack.py` ownership machinery: marker, recorded
  identity and verified stop. The cluster was stopped and its directory removed afterwards.
- Operator (cluster owner) steps, and nothing more: migrate, grant the production
  least-privilege runtime role (`sentinel.db.roles.grant_runtime`), and issue one analyst
  session. The token stayed in memory only.
- Runtime role checks, read through the API's own connection:
  - connected as the runtime role;
  - not superuser, createrole or createdb;
  - issuing a session from it is refused (InsufficientPrivilege).
- Every case step ran as that role through the production HTTP app
  (`sentinel.api.create_app`), driven in process by the FastAPI TestClient with no network
  port:
  1. Five synthetic USD debits for one synthetic account went to `POST /v1/transactions`.
     Event times were 9 days, 2 days, 40 min, 20 min and 2 min before the capture started.
     Rule scores were 0.0, 0.0, 0.0, 0.2 and 1.0. Only the last one alerted.
  2. Alert, case at revision 1, and two evidence items, with the snapshot hash pinned.
  3. `POST /v1/cases/{id}/investigations` ran the deterministic three-role workflow
     (`coordinator.deterministic_workflow()`). It recorded 3 role invocations, 5 tool calls
     and 19 steps. The profile tool came back unavailable because no profile was provisioned.
     The workflow recommended `simulated_hold` for `velocity_pattern`, with 4 claims
     supported and 0 unsupported. The reviewer accepted.
  4. `GET .../investigation-trace` (v1.2) was read twice. The final read returned the same
     workflow and the same number of steps.
  5. Server-built action intent, with the case at revision 3, awaiting approval.
  6. **Scripted** `POST /v1/approvals` with decision `approved`, sent by the capture program.
     It is not a human review.
  7. `POST /v1/actions` once, then a retry with the same idempotency key. The retry got the
     same action back with `replayed: true`. One simulated action; the case closed at
     revision 4.
  8. After each step, the program read `GET /v1/cases/{id}`, `/audit` and `/v1/overview`.
     These readings are the per-frame ledger: zero approvals and actions through frame 6, one
     approval and zero actions at frame 7, one action from frame 8.
  9. Six audit events in this order: transaction_received and alert_raised (system),
     investigation_started (scripted-analyst), investigation_completed
     (three-role-workflow), approval_recorded and action_succeeded (scripted-analyst).

**Fixture**: the only tracked data is `demo/data/recorded-case.json`, an explicit allowlisted
projection of that capture, plus its `manifest.json`:

- SHA-256 `663a27d1b7f6177b9a6f90381041b2c63e2628fe9b11a5b46ef060aba2575625`;
- 49,327 bytes, LF, canonical JSON (`sort_keys`, indent 1).

It supersedes `fa47192ede8d9ed2c4ab5bd7e69d3e589542377a131d21709aba34696d92bcea` (26f73e0) and
the first fixture, `f24da3ca46fab8d0dc15b0ae7be98f60f2d4d5f8f9b1a9ae19125cc87c42ee2c`. Both stay
in branch history.

Nothing in it was edited by hand. The frame titles, notice, provenance text and actor labels
were written by the generator. The narrative text lives in `demo/replay.js`. The raw capture,
capture log and report stay private and ignored under `.agent/demo01/`.

## The allowlisted projection

Only fields named in `scripts/build_recorded_demo.py` (`*_KEYS` and `project()`) are exported.

- Dropped: tenant and session scope, actor and principal IDs, tokens and token hashes,
  connection strings, role names, CLI or auth output, and local paths.
- Actors become fixed labels (`scripted-analyst`, `system`, `three-role-workflow`). An
  unmapped actor fails the projection.
- Kept: synthetic record IDs, artifact pins (name, version, SHA-256), timestamps, amounts,
  role outputs, claim checks, tool results, the server-rendered rationale, and request
  method/path/status.
- A recursive forbidden-key check runs on the projection and again in the validator.
- Usage stays as recorded: `not_applicable` for every attempt, with token totals `null`. It
  is never shown as zero or as billing.

## Validation (`scripts/build_recorded_demo.py validate`; no database)

The validator checks:

- schema and labels;
- clean-tree provenance and the rule, deterministic and restricted-role facts;
- frame order and chronology inside the capture window;
- every event time is before the recording;
- ingest, score and threshold consistency, with exactly the last debit alerting;
- alert, case and evidence links, and evidence `source_ref` targets;
- the evidence snapshot pin on the case, workflow and intent, and the scorer, agent and tool
  pins;
- step order and timing inside the workflow;
- every claim citation and tool-result evidence ID resolves;
- the disposition basis is the investigator attempt, and the reviewer accepts;
- the final trace is unchanged;
- intent, approval and action binding (IDs and intent SHA-256), the approval window and
  consumption, and replay identity;
- per-frame approval and action counts;
- the audit sequence, actors and times, and audit counts per observation time;
- the manifest hash and size;
- the recorded `content_identity` shape, and capture freshness against this checkout's bytes
  (see below).

A capture whose fixture fails validation writes nothing public and never falls back to fixture
data.

## Secret-safe scan

During the capture, with the real token still in memory (43 characters), the generator
scanned every public file: 8 files (all of `demo/` plus this document), including the new
fixture and manifest. It checked against 18 forbidden values:

- the token and its SHA-256;
- both connection strings and the PostgreSQL URL scheme;
- tenant, session and actor IDs;
- local repository and home paths in every separator form, and the account name only in
  path form (`/home/<u>`, `Users/<u>`, `Users\<u>`, JSON-escaped). A bare account name
  is not a needle: it also matches ordinary words (see the native fix below).

Result: clean. The private raw capture and capture log were scanned for the token, its digest
and both connection strings: clean. Report: `.agent/demo01/capture-report-<stamp>.json`
(ignored). An empty forbidden source is refused, not treated as a pass. The tests re-run the
path and user scan over `demo/` and this document.

**Native fix (preview 82316a5).** The coordinator's native Ubuntu gate ran as an account
named `sentinel`. The first generator also used the bare account name as a needle, matched
case-insensitively, so it hit the product name in six public files. That was a false
positive, not a leak: each real path needle alone matched nothing. The account name is now
matched only in path form. Regression tests check two things:

- account names that are product words ("sentinel", "Sentinel", "demo", "replay", "root"),
  with Linux and Windows layouts, produce no bare-name needle and scan clean;
- planted `/home/<u>` paths, checkout paths in every separator form, and `C:\Users\<u>`,
  `c:/users/<u>`, JSON-escaped and `/Users/<u>` strings are still caught.

This changed the generator, so the fixture was recaptured from 26f73e0.

## Capture freshness without Git history (R48)

Review finding R48 (`docs/reviews/Parallel-batch-830f018.md`): the old freshness test ran
`git diff <capture commit> HEAD -- src scripts/build_recorded_demo.py` and **skipped** when Git
or the capture commit was missing, as in a shallow or exported checkout. That added a skip to
a gate whose only allowed skip is the opt-in live-Claude test.

Now freshness reads files only:

- At capture, the generator records `provenance.content_identity`: `inputs`
  (`scripts/build_recorded_demo.py`, `src`), the canonicalization rule, one SHA-256 per file
  and an aggregate SHA-256 over the sorted `digest  path` lines.
- Inputs: the generator file, and every file under `src/` except `__pycache__/`, `*.egg-info/`
  and `*.pyc`/`*.pyo`. Paths are relative and use `/`.
- Canonicalization: CRLF becomes LF before hashing, so Windows (autocrlf) and Ubuntu checkouts
  of the same commit agree. No other bytes change. `.gitattributes` already checks out LF.
- `freshness_problems()` recomputes the digests from the checkout's actual bytes. It reports
  each changed, missing or added file and tells you to re-run the capture. It makes no Git
  call. The validator CLI and `test_capture_content_identity_matches_this_checkout` both use it.
- Missing or malformed identity fails with a re-capture message and does not crash. That
  covers a non-object identity, empty or non-object `files`, a bad digest, a path that is
  escaping, absolute, backslashed or out of scope, a wrong `inputs` or rule, and a missing or
  mismatched aggregate.
- `generator_commit` stays as recorded provenance. Its local presence is never a condition.

Tests that failed first, on the 47b7cf1 generator (17 failed), cover these cases:

- simulated Git absence (`_git` returns 128, any `git` subprocess raises, `which` finds none);
- a changed generator, and a changed, added or removed `src/` file, in a minimal tree and in
  a copy of the real checkout;
- a CRLF copy that passes;
- ignored build output;
- missing and malformed provenance;
- the validator CLI reporting stale content (on 47b7cf1 it printed `ok`).

The first recapture on 2bcc03d failed safely. The identity's own key `scope` is a forbidden
projection key, so the unchanged forbidden-key check refused it and nothing public was
written. The key was renamed `inputs`, and a regression test pins the result (it failed first
on 2bcc03d).

## Verification runs (heavy slots granted by the batch coordinator)

Current run, on af4890a (the fixture is in ed4afe1):

| Check | Result |
| --- | --- |
| `scripts/build_recorded_demo.py capture` | pass: 10 frames valid; 8 public files x 18 forbidden values clean (real 43-character token); cluster stopped and removed |
| `scripts/build_recorded_demo.py validate` | pass |
| `pytest -q tests/test_recorded_demo.py` | 38 passed, 0 skipped, including one more real capture on a pytest-owned cluster; the structured gate validator reports no finding with no allowed skips |
| same pure tests and `validate` in a `git archive` export with no `.git` | 37 passed (real capture deselected), validate ok |
| `node demo/tests/browser_qa.mjs` on the new fixture (headless Chromium, existing install) | 31/31 on the first run, including the new content-identity row |

Earlier runs (superseded): on 26f73e0 capture, validate, pytest 21 passed and QA 30/30; on
8675b5c capture, validate, pytest 15 passed and QA 30/30 on its second run (see below).

The pytest run includes these negative controls, and each is detected:

- an action or approval before the approval frame;
- an action timed before its approval;
- a broken claim citation and a broken tool-result evidence reference;
- a replay returning a second action;
- a future event time;
- reordered frames;
- an injected `session_id`;
- an unlabelled actor;
- a malformed fixture;
- the token scan (positive control, plus refusal of an empty source);
- stale, missing and malformed capture content identity (see R48 above).

Static checks cover CSP, no external URL, no form or input, no HTML sinks
(`innerHTML`/`eval`/...), fetch only of the two data constants, and in-page links only.

Browser QA served `demo/` from its own Node server on loopback, closed by its handle. It
covered:

- persistent labels, and the manifest hash computed in the browser and matching;
- the recorded content-identity aggregate and file count shown in provenance;
- Next/Previous, rail, arrow keys and Home/End in recorded order, with Next keeping focus;
- per-frame ledger counts;
- no approve or execute control;
- all 13 record links opening and focusing an existing record, and a citation jump;
- skip link, rail tab order and a visible focus ring;
- 1280px and 375px layouts with no horizontal page scroll on any of the 10 frames, and dark
  mode;
- hostile `<img onerror>`, `<script>`, `<b>` and `javascript:` strings injected into the data
  staying literal text, with no execution and the integrity banner shown;
- zero console errors, and zero requests outside the six allowlisted GETs.

The first QA run reported 28/30. Both failures were bugs in the QA script, not in the page:

- a rail title containing "executed" matched the approve/execute word check;
- a hash-only `goto` kept the earlier focus.

The script was corrected and rerun once, with 30/30. The failed report is kept privately.
Screenshots are private under `.agent/demo01/qa/` (first fixture), `.agent/demo01/qa-r2/`
(26f73e0 fixture) and `.agent/demo01/qa-r3/` (current fixture). No token existed on disk, and none was in
any page or screenshot.

## Not verified / limitations

- One recorded case only. Rule baseline only; the trained-model path was not exercised.
- The deterministic adapters are a plumbing control, not evidence of LLM investigation
  quality. No provider was called.
- The approval was scripted, and the action is a simulated record.
- HTTP ran in process (TestClient). Uvicorn, browser auth and the product `web/` UI were not
  part of the capture.
- Browser QA ran on Windows Chromium only. No Linux or WebKit/Firefox run, no screen-reader
  test, and no full six-command gate on this branch. The coordinator runs the full gates on
  the combined preview.
- Deployment and hosting are out of scope.

## Provenance and reuse

- All demo code and styles are new for this task. Nothing was copied from `web/`.
- Reused unchanged, by import: `scripts/local_stack.py` (Stack, start_database,
  stop_database, owner_url, database_state), `sentinel.devdb`, `sentinel.db.migrate`,
  `sentinel.db.roles.grant_runtime`, `sentinel.api.create_app` and the service/coordinator.
- Browser QA loads the already-installed Playwright package from a `node_modules` directory
  given on the command line. No package or lock change, and no download.
- System fonts only.
