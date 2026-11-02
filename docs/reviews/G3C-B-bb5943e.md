# G3C-B review: bb5943e — R38/R39 changes requested

## Follow-up received; re-review pending

Corrected candidate 6014680b5713105b5c29b8857561af650bec2b9c is saved as a direct child
of bb5943e. Claude reports both fixes and all final gates passing. Codex inspected the
clean commit and local passing strict/JUnit/frontend records, but has not performed the
correction re-review. R38/R39 are not yet closed. Work is paused at the owner's request;
tomorrow review the correction and focused probes before any API/UI integration.
The original findings and bb5943e evidence below remain unchanged.

November 1, 2026 (America/Phoenix). Candidate
**bb5943e681708d8fbf3db031f06f5d37a57389c9**, task/claude-g3c-trace-ui, based on accepted
G3C-A 16b67fd. **Not accepted or merged.** G3C-A and its frozen HTTP v1.2 contract remain
accepted unchanged. This review identifies two reproducible frontend corrections.

## Independent evidence and scope

A separate task/codex-g3cb-review checkout with its own locked environment ran **115
frontend tests successfully** (13 files, 12.81s). The new parser, hook/trace panel, workbench
integration and suite/runtime changes were inspected using the React review checklist.
Six additional targeted probes give **4 failures and 2 passing controls**: one Unicode
failure, three committed-context failures, original ASCII accepted and over-limit Unicode
rejected. They fail their intended assertions, not imports or setup. Probe files were
removed from the review tree after evidence capture; candidate/review stay clean at bb5943e.

The owner Windows six-command strict record was observed passed at exact clean bb5943e
while review continued. Owner native/final frontend/browser results have not been received
or certified here. Pre-commit 115/19/10/14 claims are attributed to the owner. No duplicate
full backend, independent browser, fixture/Postgres or visual-layout run was started;
known frontend findings need correction first. Passing ordinary gates do not close them.

## R38 — legal Unicode note rejects the whole trace (medium)

web/src/api/trace.ts, note(), uses value.length > 400. JavaScript length counts UTF-16 code
units; the frozen Python/JSON-schema maxLength 400 counts Unicode code points. A note with
400 U+1F642 characters is legal for the accepted DTO (400 code points) but has 800 JS units.
acceptTrace returns null, so a legitimate multilingual workflow is shown as unconfirmed.

**Proof:** the original accepted fixture's analyst note was replaced with 400 code points;
its role-completed output hashes were recomputed, and the frozen Python InvestigationTrace
model validated the full response. The actual client parser rejects that response. The
ordinary frozen ASCII fixture passes; a 401-code-point note stays rejected as it should.
The existing short Unicode example does not test this boundary.

**Fix:** honor the frozen code-point length bounds, retaining the minimum, maximum, null
handling and inert original text. Add schema-valid boundary tests (including supplementary
characters), and ensure401 code points still fails. Do not loosen/change backend schemas,
normalize away text or edit accepted fixture bytes to accommodate the client.

## R39 — old ready data is committed under a changed context (medium)

web/src/ui/TracePanel.tsx, useTrace(), stores ready data without a render-owner identity and
returns it unchanged. token/case/canRead changes are handled by a passive useEffect that
later clears state and advances request generation. Before that effect, a render using
new props still returns the previous ready trace and TracePanel commits its content.

**Proof:** a controlled consumer of the actual hook/panel first loads the accepted trace,
then re-renders with a new case, a new token or canRead=false. A useLayoutEffect observes
the committed DOM before passive effects: in each case it contains the old note under the
changed context. All three zero-stale-commit assertions fail. After effects finish, the
panel clears; tests that only wait for that final state do not catch this ordering.

**Limits of this evidence:** this is a hook/panel consumer probe, not an end-to-end session
exploit. App's normal sign-out unmounts Workbench, which mitigates that path. A committed
DOM observation is also not proof that a browser painted it. No server authentication or
scope bypass was demonstrated. The explicit immediate context-isolation requirement is
nevertheless unmet, including the hook's own canRead=false state.

**Fix:** make renderable state/choice/history belong to their actual context, so a ready
payload cannot be rendered when its owner token/case/selection/permission differs. Clear
or mask it during render rather than relying only on a subsequent effect. Preserve abort
and generation guards for late completions. Keep permitted same-session/case history
while a new workflow loads; preserve explicit history selection on same-context refresh.
Reset session/case-owned selection appropriately. Do not key/reset the whole Workbench
and lose its ambiguous-execution idempotency state merely to remount the trace hook.

Add layout/commit-boundary regressions as well as existing deferred-response tests. Do not
replace the assertion with waitFor-until-effect or dismiss it solely because sign-out
currently unmounts. No new feature or backend change is needed for this correction.

## Retained work and verification limits

Keep the read-only actions, inert notes/citations, unknown-versus-zero semantics, stored
attempt ordering and prior-workflow behavior. Preserve all frozen API bytes and provenance,
source/dependencies, the default 19 and new 10 browser suites and their identity/secret/error-
artifact checks. The startup wait is a reasonable bounded current-run readiness guard;
this review has not independently forced its original race or certified its elimination.
Keep the diagnosed missing-artifact/startup failures as evidence.

Finish any already-running check through its normal cleanup before editing. Do not start
more expensive checks on this known changes-requested candidate just to obtain a green
report; retain completed results. Correct R38/R39 on the existing task branch with new
sole-owner commits, no amend/rebase/reset, then certify the new clean SHA under the original
gates. No timeout/skip/assertion weakening. No API/UI main merge or G3D/live evaluation.

[Claude correction](../prompts/CLAUDE_G3CB_REVIEW_FIXES.md), **Opus 5.5 / High**. Raw independent
unit/probe and Python DTO validation evidence is ignored under .agent/g3cb-review/bb5943e/.
Original Cursor seven-file state, accepted API 16b67fd and other task worktrees are preserved.
