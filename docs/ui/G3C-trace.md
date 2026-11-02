# G3C-B: investigation trace panel

Status: candidate for Codex UI review; not integrated. Base and dependency: G3C-A accepted
at 16b67fd0cd09cdd08bbfa64a159035a7a188bf5b (docs/reviews/G3C-A-16b67fd.md on
task/coordination). The server, contracts and fixtures are unchanged.

## Contract inputs (provenance)

- OpenAPI `contracts/http/openapi.v1.2.json`, SHA-256
  `b52f8fd4d323f59565b3e1148557cb85221b76c793377e021c32f9c877e5b053`.
- The 16 examples are copied byte-for-byte from `git show 16b67fd:contracts/http/examples-v1.2/`
  into `web/src/fixtures/http-v1.2/`. Per-file hashes are in its `PROVENANCE.md`. They are
  checked against the copies and the frozen originals in `web/src/api/trace.test.ts`.
- Semantics: `docs/api/investigation-trace-v1.2.md` and decision 0008 at that commit, with
  the accepted review's error-order note: 422 for a malformed UUID can precede 403.

## What the panel shows

The panel is a read-only section, **Investigation trace**, under the case file. Its only
request is `GET /v1/cases/{id}/investigation-trace[?workflow_id=]`. It never investigates,
recovers, approves or executes. The case pane's existing buttons remain the only mutations.

| Stored state | Wording |
| --- | --- |
| No workflow, no legacy runs | "No three-role workflow has been recorded for this case." |
| Single-investigator runs only | "investigated by the single investigator (N runs, listed under Investigation above)". The case history keeps those runs |
| Zero-role workflow | A real workflow: "No role attempt was recorded in this workflow." and "Recorded role attempts: 0." The case pane no longer says "No investigation has been recorded" when the trace shows a workflow |
| Running | Counts are "not yet recorded", with the server `deadline_status` as of `read_at` |
| `recovery_due` | "Overdue and due for recovery when read. It has not been recovered…" |
| `terminal_by: recovery` | "Ended by recovery after the workflow was interrupted." |

- **Attempts.**
  - Listed in stored order and keyed by `agent_run_id`. A revision's second "attempt 1" is a
    separate row.
  - Shown: failure (and whether the coordinator or the terminal transaction recorded it),
    an unresolved worker ("does not say whether it is still running now"), coordinator time
    ("includes persistence; not provider latency") and usage.
  - Usage "not recorded (unknown, not zero)" differs from a reported 0/0.
- **Claims and checks.** Role claims are labelled untrusted, and each shows the server's
  recorded check. Analyst checks are not persisted, so they read "Server check not
  recorded", never verified or unsupported. A citation links only to a stored evidence item
  or tool result present on the page (`#evidence-<id>`, `#tool-result-<id>`); otherwise it
  says "not shown here".
- **Outcome.**
  - The server disposition is stated as "the coordinator's recommendation, not an approval".
  - A reviewer verdict is "not a human approval".
  - An earlier workflow is "history only"; any current proposal is under Proposed action.
- **Usage summary.** "Token counts are not billing, and attempts are not provider calls".
  Token sums cover reported attempts only.
- **Limits.**
  - Unknown limits are shown as "not unlimited".
  - Limits ending in "per process" "apply to one API process, not to an account or
    provider".
- **Steps.** Steps are in an expandable table, in seq order with gaps allowed. The terminal
  step's elapsed value is labelled "stored marker", never a duration. Identifiers and
  hashes are in "Technical identifiers" and "Attempt identifiers" details.
- **Inert text.** Notes, rationales and all other text are React text nodes. There is no
  HTML, Markdown or links from model text.

## Request lifecycle

The `useTrace` hook (`web/src/ui/TracePanel.tsx`) handles requests as follows:

- **Fencing.** It aborts the previous request. A response is applied only if its request
  generation is current, and the body's `case_id` (and the selected workflow, when explicit)
  match. Another case, or a sign-out, unmounts or re-keys the state, so an old session's or
  case's trace never reappears.
- **Loading.** Old content is cleared on every context change. While another workflow of
  the same case and session loads, only that case's workflow list stays visible, so the
  selection can change again.
- **Selection.**
  - `workflow_id` is null by default, which means "follow the newest".
  - An explicit selection survives refreshes, and is reset by another case.
  - A 404 for an explicit selection offers "Show the newest workflow".
  - A capped history reads "Showing the newest 25 of N"; no cursor is invented.
- **Refresh.** The trace re-reads after every case re-read that follows a mutation or 409
  (`Workbench.refresh`), and on "Refresh trace". A snapshot read at another case revision
  says so, and offers refresh.
- **Failures.** Errors, non-JSON or empty 5xx, network failures and unusable bodies (strict
  parser `web/src/api/trace.ts`) show a message and Retry. Nothing is fabricated.
- **Capabilities.** A session without `read_case` never requests a trace.

## Real browser coverage (trace run)

`npm run test:e2e:trace` runs `web/e2e/trace.pw.ts` on a separate stack. The default
`npm run test:e2e` still runs only the original 19 cases with the single-investigator fixture
app. The switch is `web/e2e/support/suite.mjs`, checked by `suite-harness.mjs`. The legacy
start arguments are unchanged; the trace run adds only `--app g3c_trace_browser:create_app`.
Stack ownership, cleanup, recovery, owned-secret scanning, the controlled failure artifact
and teardown are the existing machinery.

Fixtures come from `tests/support/g3c_trace_browser.py`:

- **App.** `create_app` is the unchanged production app with the deterministic three-role
  workflow (test-only).
- **Seeding.** `seed --manifest P --scenario ID --ordinal N` uses the real service and
  coordinator as the stack's runtime role and its existing analyst session. Scenario IDs:
  - `recommend`
  - `abstain_challenge` (a contradiction, challenge, revision and abstain)
  - `repeat_failure` (provider unavailable, then attempt 2)
  - `zero_roles` (transition limit 1: another config, so its limits are unknown)
  - `running`
  - `overdue` (crashed 10 minutes ago, so `recovery_due`)
  - `retry` (recovered, then a new workflow)
  - `hostile_note`
  - `open_three_role`

  Legacy and empty use the stack's own `awaiting_approval` and `open_case`.
- **Inspection.** `inspect` reads counts over a read-only operator connection, as H01 does.
- **Safety.** Output is identifiers, counts and codes only; a failure prints
  `{"error": code}`. The helper never writes the manifest or the Stack directory.
  `tests/test_g3c_trace_browser.py` covers the factory, every scenario over real HTTP,
  scope, the read-only inspection and the absence of secrets in its output.

The 10 trace cases cover:

- recommend with refresh and no mutation, then approve and execute to exactly one action;
- challenge and abstain, failure and repeat;
- zero-role, legacy and empty states;
- running and overdue, unchanged by three refreshes, then recovered by the explicit POST;
- an earlier-workflow selection across refresh and API plus database restarts;
- inert hostile text (no img, script or iframe; anchors only to stored records; no dialog);
- a delayed earlier-case trace suppressed (real responses, only delayed);
- session switching with a held read and other-session 404s;
- investigating from the case pane;
- the controlled failure probe.

Other checks:

- QA screenshots are written to `web/test-results/qa/` (ignored, scanned) and copied
  privately to `.agent/g3c-ui/qa/`.
- At 390 px the page has no horizontal scroll.
- Keyboard focus reaches "Refresh trace", and Enter re-reads.

## Harness finding

`serve.mjs` writes `runtime.json` only after capturing the Vite and API identities, a few
seconds after Vite already answers Playwright's readiness probe. A test that reads the run
record first can therefore find it missing. This happened once in the trace run and once in
the legacy run, on its first test; the evidence is under `.agent/g3c-ui/`. In both cases
teardown or the documented `stop --manifest` recovery cleaned everything up.

`waitForRuntime` (`web/e2e/support/runtime.ts`) now waits for this invocation's record. The
token binding in `session.ts` and the trace suite use it. No assertion, timeout or lifecycle
code changed. `serve.mjs` keeps its order.
