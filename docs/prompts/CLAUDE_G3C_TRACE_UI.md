# G3C-B: analyst investigation trace UI and real browser integration

**November 2:** clock/caller correction 0c17bc8 is accepted and R40 closed under
[the independent review](../reviews/G3C-R40-0c17bc8.md). This assignment is complete;
do not restart it. Codex owns final combined release verification. Older pending/pause
banners and original assignments below are historical.

**November 2:** UI 6014680 is accepted and R38/R39 closed under
[the independent review](../reviews/G3C-B-6014680.md). Do not rerun this completed task.
The current follow-up is [native integration diagnosis](CLAUDE_G3C_NATIVE_INTEGRATION_DIAGNOSIS.md).
Older pending/pause banners and assignments below are historical.

**Checkpoint:** Claude has delivered the R38/R39 correction at 6014680b5713105b5c29b8857561af650bec2b9c.
The owner paused work for today. Do not rerun this completed implementation assignment.
Codex re-reviews that exact candidate tomorrow; acceptance and integration remain pending.
The original assignment below is retained as implementation/review history.

Delivered at bb5943e; [review R38/R39](../reviews/G3C-B-bb5943e.md) requests focused fixes.
The current task is [the correction prompt](CLAUDE_G3CB_REVIEW_FIXES.md) on the existing
UI branch, not another fresh implementation worktree. The original assignment follows.

Recommended coding assistant: **Claude Opus 5.5 / High**. Typed nullable data, asynchronous
case/session switching and real browser/fixture lifecycle boundaries need careful review.
This selects the coding assistant; Sentinel's test investigators stay deterministic.

## Exact dependency and one editor

G3C-A is accepted at **16b67fd0cd09cdd08bbfa64a159035a7a188bf5b**. Read current
`task/coordination:AGENTS.md`, STATUS, TASK_QUEUE and docs/reviews/G3C-A-16b67fd.md with
`git show`. That acceptance supersedes the candidate/pending labels in the dependency's
documents. Main's application remains G3B until API/UI integration; do not start from its
older runtime accidentally. The named accepted dependency overrides the generic main-base
rule for this task.

Create task/claude-g3c-trace-ui in E:/PHANI/sentinel-wt/claude-g3c-trace-ui **from exact
16b67fd**, record base/dependency, and leave reviewed worktrees intact. One editor only.
Cursor has already delivered its required contribution; Claude can own this isolated UI
slice while Cursor is unavailable. If the owner chooses Cursor, use a separate named
Cursor task worktree and the same accepted dependency, never concurrent edits here.

Read the dependency's docs/api/investigation-trace-v1.2.md, decision 0008, existing
web/ client/CaseFile/Workbench/analysis code, docs/ui/workflow.md and browser fixture docs.
API reference: contracts/http/openapi.v1.2.json, SHA-256
b52f8fd4d323f59565b3e1148557cb85221b76c793377e021c32f9c877e5b053;
16 frozen examples under contracts/http/examples-v1.2/. Record their exact hashes and
source commit in UI provenance. Do not edit these files or the server to make the UI pass.

## Deliver the trace panel in the existing case workbench

Extend the existing typed client and safe parsing patterns for the accepted DTO. Validate
required fields and nullable values; an unusable response is unconfirmed, not fabricated
empty data. Keep normal safe handling for JSON errors, non-JSON/empty 5xx and network
failures. No new framework/dependency is expected.

- A clear read-only trace panel, with loading/error/retry/empty states, selected workflow,
  read_at and case revision. No workflow is distinct from old single-investigator runs;
  keep their existing case history. Zero-role running/inconclusive workflows are real
  workflows; avoid the contradictory blanket 'no investigation recorded' message.
- Workflow history in server order, newest by case revision. Show '25 of N' when capped;
  do not invent a cursor endpoint or claim every workflow is listed. Use workflow_id for
  selection, retaining the latest option and handling missing/foreign selection safely.
- Recorded role attempts in their stored order, keyed by agent_run_id. A revision can
  have another attempt 1; role+attempt is not a unique key. Show role, status, failure,
  checked claims/citations, tools/results, reviewer verdict and final disposition.
- Separate untrusted role claims from server claim checks and the server disposition.
  Analyst claim_checks null is 'not recorded', not 'verified' or 'unsupported'. A reviewer
  accept verdict never means human approval. Proposals and actions stay in the current
  CaseDetail human-approval flow; an old selected trace must not authorize an old action.
- Null counts/usage/elapsed/limits stay unknown; genuine zero stays zero. Label recorded
  attempts as attempts, not provider calls. Token sums cover reported attempts only;
  show unknown/not-applicable attempts, and never present token counts as billing.
  elapsed_ms is coordinator time including persistence, not provider latency.
- Use server deadline_status as of read_at. 'recovery_due' is overdue and not recovered;
  terminal_by recovery confirms recovery. A recorded worker_unresolved flag does not
  establish that the worker is still running now. Do not infer remote/provider state.
- Order steps by seq, allowing gaps. The terminal step's elapsed_ms 0 is a stored marker,
  not a zero-duration workflow or an earlier event; do not sort a timeline by that field.
  Limits are the recorded-config limits known to this server; unknown is not unlimited,
  and *_per_process is not an account-wide or provider-wide quota.
- Keep primary labels understandable. Put identifiers/hashes and technical provenance
  in an expandable detail view where useful. Use the existing UI design, accessible
  headings/tables/controls, keyboard focus, visible error text and sufficient contrast.

Render all model notes/rationales as inert text. No raw HTML, Markdown links from model
text, eval or executable content. Citation links may navigate only to the actual stored
case evidence/tool result with that ID; do not invent a URL from a claim or note.
Session tokens remain in memory; no token in a URL, browser storage, logs or screenshots.

## Request lifecycle and unchanged actions

Fence every response by current session, case, selected workflow and request generation.
Cover reversed case/history responses, rapid selection and sign-out/session changes.
Clear old private content on context changes. Error responses must not restore an old
session's trace. Abort where helpful; generation checks still decide whether to apply it.

Refresh trace uses GET only, never POST investigations. Refresh after actual case mutations
and 409 re-reads without clobbering an explicit historical selection. A latest selection
can follow the new latest workflow. Separate snapshots can have different case revisions;
label an older snapshot/offer refresh rather than combining it into a false current view.
Keep approval/reject/execute separate and preserve one execution idempotency key across an
ambiguous retry. No auto-approval, auto-execution or investigation just to populate a panel.

## Real fixtures and tests

Unit/component tests may use exact accepted examples and documented DTO-valid variants, including Unicode notes.
Include mixed reported/unknown usage and reported 0/0, null limits, tool-followup versus
retry, repeated attempt 1, zero-role state, old single-investigator state, overdue/recovered,
malformed/non-JSON responses, literal hostile notes and deferred-response races. Keep the
accepted fixture bytes unchanged; record source/hash for copied UI fixtures.

Add real browser -> production API -> disposable Postgres coverage for this panel.
Existing 19 browser cases remain the baseline and must still pass; they do not cover trace
UI. New cases must show at least recommend/abstain or challenge/revision, failure/repeat,
zero-role, running/overdue/recovered, legacy/empty, prior-workflow selection and auth/session
switching. Include actual refresh with no workflow/action mutation, inert hostile text,
restart persistence, stale-response suppression and the unchanged human action boundary.
Verify no simulated action exists before approval/execute, and exactly one after execution.

Use the accepted Stack ownership/process/cleanup and secret-scanning machinery. The
existing start --app hook can choose a **test-only** factory around the unchanged production
app with deterministic three-role adapters. Prefer a separate trace stack/run so original
19 cases keep their single-investigator fixture semantics. New trace seed helpers must
use real service/coordinator code and the runtime role for investigations, operator access
only for provisioning. Do not fake completed functionality with intercepted fixture JSON
or add seed/clock/token routes to production. Reuse existing sessions/tokens where possible.

New local support helpers may live in tests/support/g3c_trace_browser.py and a focused
new fixture test module; document the scenario IDs and lifecycle. A helper may read its
owned private manifest but must emit only safe scenario IDs/codes, never credentials or
raw exception messages. Keep every fixture token in owned-secret scanning until it ends,
including expected browser error artifacts. Do not place unexpected files in a Stack-owned
folder or change its manifest behind its ownership checks. Preserve recovery on failed
stop, identity checks, no stale-run adoption and no kill-by-name. Do not weaken the 20/12
lifecycle harnesses, secret scanner or failed-start assertions for a new fixture.

## Ownership, verification and handoff

Own web/, docs/ui/, the two new test-helper/test paths if needed, and a branch handoff.
Frontend runner/config/package scripts may be extended for trace cases with regression
coverage; preserve the default legacy run and underlying process ownership behavior.
Do not edit production src/, contracts/, migrations/grants, agents-1.0, model/data/evals,
Python dependencies/lockfiles, existing browser_stack lifecycle code, CI/skip policy,
checker timeouts or central STATUS/TASK_QUEUE. Request a concrete backend change with an
example/status code only if the frozen contract really cannot support the feature.
The local_stack.py three-role flag and manual-evaluator/backup follow-ups are separate tasks.

Run typecheck, unit/component tests, build, unchanged legacy browser cases and new trace
browser cases; inspect desktop/narrow layouts and keyboard use, storing QA screenshots
privately/ignored without tokens. Run meaningful focused support tests if Python helpers
are added. Final clean-commit verification follows existing strict Windows/native backend
gates sequentially, exact structured skip gate, frozen exports/package/ML checks. Keep all
assertions/timeouts/skips; preserve failures and diagnose instead of rerunning until green.

New commits: PHANI465 <pgavara1@asu.edu> as sole author and committer, no trailers, no
history rewriting. Commit explicit owned paths and hand off exact SHA, source fixture
hashes, actual results, screenshots/QA location, cleanup and gaps. No main merge, remote,
push, deployment, paid usage, live provider or final-case evaluation. Codex reviews the UI
before combined API/UI integration. Do not edit the original Cursor checkout or its seven saved changes; owned copies of
those files in the new task worktree may change as needed.
