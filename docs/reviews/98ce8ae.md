# Codex U01 review: 98ce8ae

Exact commit: 98ce8aef4a3cc7b1cab4b685ff671ee4acc88e6a.
Branch/worktree: task/cursor-analyst-ui, E:\PHANI\sentinel-wt\cursor-analyst-ui.
Accepted C01 dependency: 2e6c2329aafe28b2e7c31ef5078d554cb66ca529 (verified ancestor).
Date: October 23, 2026, America/Phoenix.

**Outcome: changes requested. Preserve the working hold path and fix R14-R17 before U01 acceptance.** No backend or HTTP contract change is required for these findings.

## R14 [P1]: render escalation parameters according to the accepted contract

Locations: [types.ts:139](E:/PHANI/sentinel-wt/cursor-analyst-ui/web/src/api/types.ts:139), [CaseFile.tsx:202](E:/PHANI/sentinel-wt/cursor-analyst-ui/web/src/ui/CaseFile.tsx:202), [history:172](E:/PHANI/sentinel-wt/cursor-analyst-ui/web/src/ui/CaseFile.tsx:172), [format.ts:59](E:/PHANI/sentinel-wt/cursor-analyst-ui/web/src/api/format.ts:59).

The shared ActionParameters type requires amount for both operations. Accepted EscalateParameters instead contains operation=escalate, transaction_id and reason_code; it has no amount. Proposal, executed-result and history rendering all format the missing amount unconditionally.

Independent real-browser reproduction used the unchanged U01 API source, real Uvicorn, a fresh local Postgres database and the deterministic investigator: a 250000-minor-unit USD transaction with no previous account transactions scores 0.6 and opens a case. Clicking Investigate returns an escalation with reason_code=unusual_amount. The API correctly persists awaiting_approval at revision 3, but the UI becomes completely blank. Independent exact-source rendering also reproduced TypeError while reading minor_units from undefined. This is a normal supported operation, not malformed server output.

Correction: represent the accepted operation variants as a discriminated union and render the exact appropriate fields in current, executed and historical views. Show escalation reason_code and transaction identity. Never invent an amount or substitute zero to suppress the crash. Add meaningful regressions using an actual accepted escalation shape and preserve hold rendering. An error boundary can improve fallback behavior but does not replace the contract correction.

## R15 [P2]: keep case and queue responses tied to the current request

Locations: [Workbench.tsx:82](E:/PHANI/sentinel-wt/cursor-analyst-ui/web/src/ui/Workbench.tsx:82), [pagination:209](E:/PHANI/sentinel-wt/cursor-analyst-ui/web/src/ui/Workbench.tsx:209), [Queue.tsx:55](E:/PHANI/sentinel-wt/cursor-analyst-ui/web/src/ui/Queue.tsx:55).

loadCase unconditionally publishes detail/audit responses. Select case A, then B; return B first and the older A response last. The selected row remains B, but detail becomes A, so the case pane disappears into the Select a case placeholder. Independently reproduced against the exact Workbench source with deferred responses in JSDOM. A simple busy boolean does not solve this: queue rows remain selectable and an old completion can clear a newer request's busy state.

The same request ownership issue affects queue navigation/filtering. Next updates cursor history and starts loadQueue without setting pending/loading. Two clicks before the first response append the same cursor twice; Previous then reloads the same page. Responses also are not checked against the current filter/cursor request. An independent deferred-response probe confirmed calls [null, cursor1, cursor1, cursor1]: after double Next, Previous requested cursor1 again rather than the first page.

Correction: give case-detail/audit and queue requests clear current-request ownership or cancellation with stale-result guards. Keep detail and audit paired with the selected case. Make pagination transitions atomic and prevent duplicate navigation while its result is pending; old completions must not override newer request/loading/filter state. Add deferred-response regressions for reversed A/B responses, filter changes and double Next followed by Previous.

## R16 [P2]: distinguish historical expiry from a current recovery requirement

Locations: [case.ts:20](E:/PHANI/sentinel-wt/cursor-analyst-ui/web/src/api/case.ts:20), [CaseFile.tsx:119](E:/PHANI/sentinel-wt/cursor-analyst-ui/web/src/ui/CaseFile.tsx:119).

approvalExpired returns true if any historical audit event is approval_expired. The screen therefore says Investigate this revision before making a new decision even after successful re-investigation produces a fresh current intent, and even after closure. The expiry remains part of the audit history; it must not permanently drive current workflow instructions. An exact-source component probe confirmed that the stale instruction appeared beside Approve, while Investigate was absent, after recovery to a new current intent.

Correction: scope the recovery instruction to the current open/reopened state and revision, or describe historical expiry as history. Cover recovered awaiting-approval, freshly approved and closed states with the old expiry event still present. Preserve the useful instruction for a genuinely reopened case.

## R17 [P2]: make queue amounts readable

Locations: [styles.css:134](E:/PHANI/sentinel-wt/cursor-analyst-ui/web/src/styles.css:134), [styles.css:217](E:/PHANI/sentinel-wt/cursor-analyst-ui/web/src/styles.css:217), [Queue.tsx:63](E:/PHANI/sentinel-wt/cursor-analyst-ui/web/src/ui/Queue.tsx:63).

The generic button rule sets color:white. The row class changes the background but not the text color, so its primary amount is white on the pale desk background and also on the selected sheet background. Confirmed in the real browser: the main financial amount is barely readable. Relative-luminance contrast is about 1.19:1 against #e4eee8 and 1.04:1 against #f7fbf8.

Correction: give row text an explicit readable foreground, preserve intended score/metadata colors, and check selected/unselected, keyboard focus and hover states in the browser. This is financial-data readability and accessibility, not a request for a visual redesign.

## Independent evidence and limits

- Clean exact HEAD and accepted C01 ancestry verified; no source modifications by reviewers.
- npm test: 16 tests passed across 5 files; npm run build: TypeScript and production build passed. These existing tests miss the escalation and response-order counterexamples.
- Real browser -> Vite same-origin proxy -> unchanged API -> disposable Postgres: sign-in, hold investigation, explicit approval, separate simulated execution, closed revision 4 and Action succeeded audit verified. A later API read confirms exactly one persisted action. No live model call was made.
- Escalation reaches valid persisted awaiting_approval revision 3, then fails at response -> UI rendering as described above. Browser reload returns to an empty sign-in form.
- Reviewer stack used a private, newly created temporary directory and the original devdb primitive, not unaccepted C02 browser_stack.py. The exact review API/Vite/Postgres processes were confirmed stopped and all three ports closed; only the verified owned temporary directory was removed.
- Independent temporary React/JSDOM probes reproduced duplicate pagination history, the stale recovery instruction and computed white queue amount text. Probe: E:/PHANI/Interview/tmp/u01_behavior_probe.cjs, using existing Node/esbuild dependencies; no package install or checkout edit.
- The interrupted strict-check attempt left an unfinished running report and is not a pass. Fresh final strict-check evidence, if completed, is reported externally against this exact commit. The existing C01 virtual environment may be used only because its uv.lock is byte-identical; PYTHONPATH/import location must point explicitly to U01 source. No claim of a fresh dependency install is made.
- A fresh npm audit was blocked by automatic approval review because it would transmit dependency metadata to npm's registry. No bypass/retry was attempted. Cursor's audit/advisory summary remains reported evidence, not independently revalidated here; do not force-upgrade dependencies without reviewing the actual advisory and compatibility.
- This bounded browser review does not complete U02. The full lost-response/database, rejection, expiry/recovery, stale revision, foreign-session and restart browser suite still needs accepted corrected C02. Linux/macOS, CI and hosted staging remain unverified.

## Next handoff

Cursor corrects R14-R17 on its existing task branch, writes meaningful failing-first regressions, updates its handoff and returns the final tested commit for re-review. Read the current dispatch at docs/prompts/CURSOR_U01_REVIEW_FIXES.md from task/coordination. Do not merge main or unaccepted C02. Claude continues its separate C02 R11-R13 corrections; C05 may follow that correction handoff as already assigned.
