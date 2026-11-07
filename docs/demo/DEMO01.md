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

Capture run: stamp 20261107T010104Z, from generator commit
`8675b5c191c3280755bc36406d7b0b74acd40c3c` on a clean tree.

- `src/` was identical to the tested application `495c7d33424054d27d68d08004191d4be37adaf9`
  (G3D-P3). The generator checks this with git and records it.
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

- SHA-256 `f24da3ca46fab8d0dc15b0ae7be98f60f2d4d5f8f9b1a9ae19125cc87c42ee2c`;
- 45,531 bytes, LF, canonical JSON (`sort_keys`, indent 1).

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
- the manifest hash and size.

A capture whose fixture fails validation writes nothing public and never falls back to fixture
data.

## Secret-safe scan

During the capture, with the real token still in memory (43 characters), the generator
scanned every public file: 7 files under `demo/` at that time, including the new fixture and
manifest. It checked against 15 forbidden values:

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

## Verification run (single heavy slot granted by the batch coordinator)

| Check | Result |
| --- | --- |
| `scripts/build_recorded_demo.py capture` on 8675b5c | pass: 10 frames valid, scan clean, cluster stopped and removed |
| `scripts/build_recorded_demo.py validate` | pass |
| `pytest -q tests/test_recorded_demo.py` | 15 passed, including one more real capture on a pytest-owned cluster |
| `node demo/tests/browser_qa.mjs` (headless Chromium 1248, existing install) | 30/30 on the second run (see below) |

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
- the token scan (positive control, plus refusal of an empty source).

Static checks cover CSP, no external URL, no form or input, no HTML sinks
(`innerHTML`/`eval`/...), fetch only of the two data constants, and in-page links only.

Browser QA served `demo/` from its own Node server on loopback, closed by its handle. It
covered:

- persistent labels, and the manifest hash computed in the browser and matching;
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
Screenshots are private under `.agent/demo01/qa/`. No token existed on disk, and none was in
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
