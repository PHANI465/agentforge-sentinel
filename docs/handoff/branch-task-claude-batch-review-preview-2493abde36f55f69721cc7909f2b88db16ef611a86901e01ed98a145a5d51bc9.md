# Handoff: task/claude-batch-review-preview-r2

- Task and acceptance criteria: task-only combined preview for the November 6 review-correction
  batch (`task/coordination:docs/prompts/CLAUDE_BATCH_REVIEW_CORRECTIONS_2026-11-06.md`): corrected
  P4a (R46/R47/R49) and DEMO01 (R48) merged onto exact delivered preview
  830f01864aec3ff94679cf068b598157c7ee4263, then one exact-head Windows and native certification.
- Tool and worktree: Claude Code (batch coordinator), `E:/PHANI/sentinel-wt/claude-batch-review-preview-r2`.
- Updated: 2026-11-07 (America/Phoenix).
- State: ready for Codex re-review. Not accepted, not merged to main, not pushed.
- Code reference tested before this note: 1b71364e2da9701af0e280715f63d456dee5026e (combined
  merges, clean tree). This note's commit only adds this file.
- Final check evidence: the full Windows and native gates run after this note's commit, on its
  exact SHA. Results are in the coordinator's final chat report and the ignored local reports
  (`.agent/last-check.json`, `.agent/r2/`). This note does not record them.
- Owned/changed paths: this note only. Merged content comes from the two worker branches.

## Implemented

- Merge 42ff1b0dd71d04fcdb7eb0fa943313f987c2a545 has parents 830f018 and
  b32f45c495ae9f352c59b1e2173b23dc37fe9914, which is P4a corrected from 96293da by 4b9118d and
  the note commit b32f45c.
- Merge 1b71364e2da9701af0e280715f63d456dee5026e has parents 42ff1b0 and
  1289b42df8f0b9b7fc0b208959fb8b3474c7804d, which is DEMO01 corrected from 47b7cf1 by 2bcc03d,
  af4890a, ed4afe1 and 1289b42.
- Both merges were clean, with no conflicts and no shared paths. The diff against 830f018
  covers 25 files, all under P4a evaluator scripts/tests/docs, DEMO01 demo/script/test/docs or
  branch notes. Nothing under src, contracts, web, CI, lockfiles, the frozen protocol/cases,
  STATUS or TASK_QUEUE changed.
- Unlike the preserved preview 830f018, this preview includes P4a, by design.

## Verified (focused evidence on 1b71364, before full certification)

- **Combined focused pytest:** the six agent_eval modules, local capacity and recorded demo
  ran together, including real disposable Postgres. Result: 167 passed, 0 skipped, 233 s
  (`.agent/r2/focused.xml`).
- **R46 review probe** (`review_p4a_accounting.py`, ROOT retargeted):
  - The control is unchanged: C1 has wrong hold D03, acceptable 2/3.
  - The relabelled-refused mutation and the censored-suffix complete record are both refused.
  - The first attempt was mistargeted: the ROOT substitution had not applied, so it ran the
    reviewer's 96293da checkout and reproduced the old defects. That output is kept as
    `probe-accounting-MISTARGETED-96293da-review-checkout.jsonl`.
- **R47:**
  - The reviewer's unbound key is now refused as having no sheet binding.
  - Coordinator variant `review_p4a_sheets_bound_r2.py`, run with the new binding:
    - blank answers stay unanswered and the review is reported partial;
    - a correction-only answer is counted as a correction, 1/1;
    - `banana` is refused;
    - supported + not_checkable gives 1/2;
    - duplicate items are refused;
    - a blank template is not scored.
- **R49:** the reviewer's real-DB export probe, run as a temporary untracked test and then
  removed, passes 1/1. Escalate→hold now raises ExportError.
- **R48:** the reviewer's probe targets the removed skipping test, so an adapted probe ran
  with all Git access faulted:
  - the tracked capture verifies with no problems;
  - a copied checkout verifies;
  - a changed src byte is detected;
  - the structured gate validator with no skips allowed finds nothing in the focused JUnit.
- **Demo:** `build_recorded_demo.py validate` is ok, with 10 frames and fixture sha256 663a27d1….
  The standalone Chromium QA, using the existing web/node_modules Playwright on loopback,
  passed 31/31 with its server closed.
- **AN01:** `docs/analytics/check_an01.py` reports 34 PASS and 0 failures.
- **Authorship:** every introduced commit and merge has PHANI465 <pgavara1@asu.edu> as
  author and committer, with no trailers.

## Not verified / gaps

- The product frontend and browser suites were not rerun, because no product UI or
  application source changed.
- There was no GitHub Actions, macOS or real shallow-clone CI run; missing history was
  simulated.
- The DEMO01 content identity covers only the generator and src/. A change to
  `scripts/local_stack.py`, contracts or the lockfile does not mark the capture stale.
- The P4a checks detect inconsistent unsigned files; they are not tamper-proofing.
  Unblinding keys made before this change are refused, so packets must be regenerated.
- No live provider, auth/account call, final cases or model-quality evaluation.
- AN01 remains a draft with open decisions.

## Next action

Codex independently re-reviews this preview SHA and the worker SHAs b32f45c and 1289b42
before any application integration.

## Coordination and provenance

- Preserved unchanged:
  - preview 830f018;
  - AN01 dd6518d and a8c164a;
  - PERF01 59b0b54;
  - P4a 96293da and DEMO01 47b7cf1, both in history;
  - accepted branches and main;
  - Cursor's checkouts and its seven saved edits;
  - the canonical `.agent/batch-review-2026-11-06/` probes, which were only copied.
- Heavy-slot use (database, browser and gates) was serialized by a coordinator lock with a
  private queue log.
