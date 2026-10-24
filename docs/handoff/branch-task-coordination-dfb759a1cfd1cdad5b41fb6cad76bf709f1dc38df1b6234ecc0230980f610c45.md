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
