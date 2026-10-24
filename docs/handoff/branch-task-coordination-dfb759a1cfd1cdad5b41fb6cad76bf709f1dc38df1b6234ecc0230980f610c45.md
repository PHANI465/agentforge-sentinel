# Handoff: task/coordination

- Task and acceptance criteria: independently re-review c6d369f; run focused and normal checks; publish a shared Claude implementation batch and required Cursor assignment.
- Tool and worktree: Codex, E:\PHANI\agentforge-sentinel.
- Updated: October 23, 2026, America/Phoenix.
- State: review and coordination ready; implementation packages not yet executed.
- Code reference tested before this note: c6d369f6043a8c9ec86d8f56cf05670e81fba81d, clean task/thin-path.
- Final check evidence: run strict helper after the final documentation commit; see final chat / ignored .agent/last-check.json for that commit. No self-referential SHA is claimed here.
- Owned/changed paths: AGENTS.md, README.md, docs/STATUS.md, docs/VERIFICATION.md, docs/TASK_QUEUE.md, docs/prompts/CLAUDE_BATCH.md, docs/prompts/CURSOR_UI.md, docs/reviews/c6d369f.md and this note. No application source changed.

## Implemented

- Accepted R1-R8 corrections within the local thin-path scope after independent review.
- Explicitly assigned Claude backend/data/ML/reliability/CI work and Cursor UI/browser implementation.
- Defined dependency commits, separate worktrees, acceptance gates and useful independent work while awaiting review.
- Preserved the existing owner-designation gate for main integration. Main was not merged or advanced.

## Verified

- Focused tests/test_review_regressions.py: 13 passed on c6d369f.
- Strict helper: passed on clean c6d369f; full pytest 106 passed / 1 intentional live-Claude skip, 21 helper tests, 15 schemas, Ruff and Node passed.
- Read-only parallel review found no new blocking transaction/recovery defect.
- Full results and limitations are in docs/reviews/c6d369f.md.

## Not verified / gaps

- No new live-Claude call, CI, Linux/macOS, browser UI, external database path or staging test.
- Global personal Claude memory isolation and exact subscription allowance remain unverified.
- Approval-creation clock capture under contention is an explicitly assigned nonblocking C01 follow-up.
- Tool prompts are prepared; no Claude/Cursor implementation run is claimed.

## Next action

Claude starts C01 from committed task/coordination, hands off the exact HTTP contract commit, then C02. Cursor starts U01 after accepted C01. Claude can work independent ready packages in its own worktree while review proceeds.

## Coordination and provenance

- Shared coordination only; no contracts, migrations, provider adapters or source attribution changed.
- Central queue/STATUS are Codex-owned; implementers update task-specific notes and artifacts.

## Four-package delivery follow-up

Owner supplied C01/C03/C06/C08 delivery hashes; Git branch tips verified. C01 0a6fb0e received an independent read-only review, 40 focused tests, strict checks (146 passed / 1 live skip), and real HTTP probes. R9/R10 remain open, so U01/C02 are not unblocked. C03/C06/C08 measurements/checks remain Claude-reported pending review.

This coordination update publishes the review, the immediate Claude correction prompt, the Cursor non-JSON error requirement, and accurate queue/status gates. No application source, task branch or main was changed. Previously tested coordination commit: fcc04c5eebdb353ce290b99c288990c51a0d4dcf. Final after-commit evidence belongs in the local ignored report/final chat, not a self-referential note hash.

Next action: Claude fixes R9/R10 on its existing C01 branch and returns the corrected commit for Codex re-review. Environment provisioning is outside this prompt update.

## Corrected C01 accepted

C01 2e6c2329aafe28b2e7c31ef5078d554cb66ca529 passed independent re-review/checks; R9/R10 are resolved. Evidence is in docs/reviews/2e6c232.md. This unlocks Cursor U01 and Claude C02. C05 follows the C02 implementation handoff, and the overview consistency note stays assigned there.

The existing Cursor worktree has uncommitted planning notes. Its owner preserves/commits only intended owned notes and merges the accepted C01 dependency without resetting; Codex did not edit that worktree. New backend task branches start from accepted C01. Read latest shared docs via task/coordination, whose application source still remains c6. C03/C06/C08 and main integration are unchanged and pending.

Previously tested coordination reference: 9e49a87b2a7d50c0fdcc3823cd87a07e49a856ae. Final checks after this documentation commit belong in the ignored report/final chat.

## C02 review: changes requested

Reviewed c3fd83df78f2d8e90598508f3779c33a3fdad0a5 read-only. Focused real-socket fixture suite: 13 passed; independent safe lifecycle probes still show R11 unowned-directory deletion and R12 recovery-state deletion on shutdown failure. R13 corrects fixture expectations/audit prose. See docs/reviews/c3fd83d.md. Additional baseline checks, if run, are recorded externally; green checks do not clear these findings.

Cursor U01 continues untouched on accepted C01. U02 stays gated on accepted corrected C02. Claude receives docs/prompts/CLAUDE_C02_REVIEW_FIXES.md; C05 may follow its correction handoff in a separate worktree from accepted C01. C06's independent checker edits and C02's 900-second timeout require an explicit future merge.

This update changes coordination documents only. Previously checked coordination reference: f6236672685fe9508a645f62fac7d9fdb4e21fd6. Final check evidence after this doc commit belongs in the ignored report/final chat. No source worktree or main was modified.

## U01 review: changes requested

Reviewed exact Cursor U01 98ce8aef4a3cc7b1cab4b685ff671ee4acc88e6a against accepted C01 2e6c232. Frontend tests/build pass; a real browser/API/disposable-Postgres hold path works. A valid escalation response blanks the UI (R14); independent deferred-response rendering reproduces lost current selection (R15). Review also requests current-state expiry instructions (R16) and readable queue amounts (R17). Full findings/evidence are in docs/reviews/98ce8ae.md; Cursor receives docs/prompts/CURSOR_U01_REVIEW_FIXES.md.

No application source or task checkout was edited by Codex. All owned review servers/ports and the disposable directory were cleaned up. The interrupted strict-check report is not a pass; fresh completed checks, if run, are recorded externally against their exact commit. npm audit metadata egress was rejected by automatic approval review; no bypass/retry or independent audit success is claimed.

C02 R11-R13 and other backend review gates remain unchanged. Main was not merged. Previously verified coordination reference: a0b4c0afc723b9f0a954be553392ee80e8100dcc. Final checks after this coordination commit belong in the ignored report/final chat, not this tracked note.

## Corrected C02 re-review: remaining R11/R12 failures

Reviewed exact 66214bb466fe9810df5a306f12137606ba2c0251 without implementation edits. Safe intercepted probes confirm nested pg and pg/data junctions are accepted before a foreign-resolving PostgreSQL stop command. Actual Windows locked-file probes confirm partial removal loses the marker and prevents the documented retry. A separate intercepted status-error probe reports success/removes state when shutdown fails and status is unknown. R13 response/description corrections match accepted API semantics. See docs/reviews/66214bb.md and docs/prompts/CLAUDE_C02_FOLLOWUP.md.

Ruff, HTTP and domain exports, Node transport and 21 helper regressions passed independently on clean 66214bb. Automatic approval review rejected the focused process-suite command for the known nested-path risk; it did not run and was not bypassed/retried. Claude's 23/198-test and strict evidence remains attributed to Claude. Review probes were isolated and cleaned; no foreign process was touched.

C02 and U01 remain changes-requested; U02 waits for both accepted corrected packages. C05 is already authorized in its own worktree from accepted C01 without C02 code. Main and implementation source remain unchanged. Previously checked coordination reference: 46ecd6f513432c010c2562a41a7310c6600c02c7. Final checks on this documentation commit belong in the ignored report/final chat.

## U01 5055321 re-review: one R15 query race remains

Reviewed exact 5055321cfa810a2108d184e5542785cf44977edc, accepted C01 ancestor retained. R14/R16/R17 corrections are accepted within scope. A signed-in real Chrome/API/Postgres escalation now renders, approves, executes once and displays closed history/audit. Independent frontend 23-test run and build pass. A separate controlled React/JSDOM probe still shows delayed mutation refresh replacing Closed rows with all-state results while the selector remains Closed; see docs/reviews/5055321.md.

Cursor receives docs/prompts/CURSOR_U01_R15_FOLLOWUP.md, preserving completed corrections and fixing only this query-context failure. Fresh strict results, if completed in parallel, are recorded externally. Reviewer loopback resources/ports and the verified disposable directory were cleaned; no model calls or implementation edits. C02 retains its separate review gate; U02 waits for accepted U01 and C02. Main remains unchanged.

Previously checked coordination reference: 8924b73c9af18437b8da1149871a017ed89a584b. Final checks after this documentation commit belong in the ignored report/final chat.

## C02 accepted; C05 reviewed with changes requested

C02 0e72b0bd599ff1707ca5b2507d65a0927894cbe0 passes independent process-free17 and combined40 focused tests (367.59s), Ruff,21 helper tests,15 schemas,HTTP frozen exports and Node. R11/R12/R13 resolved within Windows local scope. Final empty-directory rmdir failure is an explicit nonblocking/manual-cleanup caveat; no active resource or secret is left. Full215 strict record belongs to Claude; no independent full repeat is claimed.

C05 0119ca73e6ae3b4df9f9eeffcea8b15911f716e6 passes independent36 focused tests and ordinary compatibility/helper checks but has concrete R18 unsafe existing roles, R19 timeout parsing and R20 unbounded HTTP-method metric labels. See docs/reviews/0119ca7.md and docs/prompts/CLAUDE_C05_REVIEW_FIXES.md. Optional X-Request-ID remains diagnostic; C01 bodies/status/OpenAPI stay frozen and no UI dependency or new endpoint is added.

Cursor finishes U01 R15, then after acceptance consumes accepted C02 for U02; C05 remains unaccepted. Implementation worktrees and main were not changed. Reviewer probes/stacks were owned and cleaned; no models or unrelated databases were touched. Previously checked coordination reference: b4e9438c169bf73671eabfba84075d3030ecd649. Final checks after this documentation commit belong in the ignored report/final chat.

## U01 deb1037 accepted; Cursor U02 dispatched

Reviewed exact deb10370352dc62b0abfa2a5776c185494fcb04e, C01 ancestry retained. The unchanged independent delayed-refresh probe now keeps Closed rows and requests all->closed->closed. R14-R17 are resolved. Independent24 frontend tests/build and Ruff,21 helper tests,15 schemas,HTTP exports and Node passed. Backend/dependencies are unchanged from independently checked5055321; the owner's strict175+1 report is attributed separately rather than repeated.

U02 is now ready with U01 deb1037 plus accepted C02 0e72b0b. docs/prompts/CURSOR_U02.md assigns a dedicated task worktree, real browser/API/Postgres flows, committed-response loss/idempotency assertions, isolation/restart cases and token-safe artifacts/cleanup. C05 remains changes-requested; main was not merged. No implementation source was edited by Codex.

Previously checked coordination reference: f721cfed9db1a2f20b5b516f69f5335ed68800c1. Final checks after this documentation commit belong in the ignored report/final chat.


## C05 b3b34ac re-review: R19/R20 resolved, R18 remains

Reviewed clean b3b34acfc79fbca3856877594e8b030dc14a66e0 independently. Focused64 tests passed (202.09s); Ruff,21 helpers,15 schemas,HTTP exports/examples and Node passed. Frozen contracts/web unchanged and owner strict metadata matches the candidate. Full239+1 counts remain owner-attributed.

Fresh owned probes confirmed an effective PUBLIC column UPDATE on api_sessions survives refresh and changed one synthetic session's capabilities. Same-name unmanaged relation grants and effective PUBLIC schema CREATE also bypass the current validation. R18 remains changes-requested; R19/R20, OFF behavior and operator scope notes are resolved. See docs/reviews/b3b34ac.md and docs/prompts/CLAUDE_C05_R18_FOLLOWUP.md. Initial direct-column-grant persistence hypothesis was disproved and is not a finding.

Implementation worktrees and main were not edited. Probe clusters stopped/state removed; no models/external databases/installations. Cursor U02 keeps accepted U01/C02 and continues independently. C03/C06/C08 and model gates are unchanged. Previously checked coordination reference: 35c2acb03228e67156bc58cb58bbb924d3331916. Final checks after this documentation commit belong in the ignored report/final chat.
