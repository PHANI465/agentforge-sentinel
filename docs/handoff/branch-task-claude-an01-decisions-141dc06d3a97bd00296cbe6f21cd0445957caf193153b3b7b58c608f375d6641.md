# Handoff: task/claude-an01-decisions

- **Task:** revision r3.1 under `task/coordination:docs/prompts/CLAUDE_AN01_R3_REVIEW_FIXES.md`. It answers review `task/coordination:docs/reviews/AN01-r3-b436c5e.md` (R50–R52) and applies its supported policy decisions. Documentation and standard-library checkers only.
- **Tool and worktree:** Claude Code, `E:/PHANI/sentinel-wt/claude-an01-decisions`. It continues from b436c5e7dc369680a3b15605b96046e1a2913b4d, which is preserved: no reset, amend or rebase.
- **Updated:** 2026-11-07 (America/Phoenix).
- **State:** ready for Codex re-review. It is a proposal: not accepted, and AN01-M1 is not run.
- **Code reference tested before this note:** the working tree on top of b436c5e, with documentation and doc-checker changes only. The checks are rerun after commit and reported in chat.
- **Final check evidence:** the doc checkers, the Windows and native table derivation, and Ruff were run after the final commit and are reported in chat. There was no full strict, backend, browser or load run, because nothing under src, tests, contracts, web or scripts changed.
- **Owned/changed paths:**
  - `docs/analytics/AN01-decisions-r3.md`
  - `docs/analytics/AN01-zone-table.json`
  - `docs/analytics/derive_an01_zones.py`
  - `docs/analytics/check_an01_r3.py`
  - this note

  The r2 pointer lines from b436c5e are unchanged.

## Implemented

- **R50, zone coverage.**
  - The public UTC domain `[2000-01-01, 2038-01-01)` is kept separate from the padded lookup dates `[1999-12-31, 2038-01-02]`, which cover New York's 1999-12-31 and the Kolkata/Tokyo 2038-01-02 sentinel.
  - Lookups are strict: no clamping, extrapolation or negative index. Date mode is validated after conversion.
  - The new table digest is 24e41cec….
  - The checker adds edge answers in all five zones, whole-domain coverage, strictness and date-mode cases.
- **R51, measurement plan.**
  - The measured unit is the complete report operation: 7 operations, 22 SQL statements and 3 control texts, all hashed.
  - Each cell gets one warm-up, 5 timed runs and a separate EXPLAIN pass.
  - Staged commands each fit the unchanged 2,700 s cap (2,613 s internal bound). The total job is bounded at about 10.7 h, with owned recovery and no automatic resume.
  - One joint cross-platform index rule. Cap decisions use complete operations.
  - Phase E is a matched JSON-versus-columns comparison at N\*, with no causal percentage. Missing mandatory evidence means "not demonstrated".
- **R52, connection and budget.**
  - Acquisition is outside the budget and disclosed, with no bound claimed.
  - The report budget starts after acquisition, with a report ROLLBACK reserve `R` = 250 ms; the workflow's 5 s is not inherited.
  - Admission `M` and report quarantine `Q` are finite and separate from the workflow `QUARANTINE`.
  - A table gives each outcome's meaning and cleanup owner.
  - Refusal controls are separated from submitted-statement, lock and withheld-reply controls. Their budgets are feasible: the work budget is at least 150 ms, connect is outside the budget, and submission is proved by tag and observer.
- **Policy.**
  - Opt-in v1.3, with conditional compatibility.
  - CLI `SUPPORTED_CAPABILITIES` is separated from the unchanged four-value default.
  - Coherent exact-integer cursor counts.
  - "Received {n} minutes ago", separate from the server's `read_at`.
  - The cutoff applies to ingestion timestamps, not commit time.

## Verified

The evidence is in this checkout's ignored `.agent/an01-r3-fix/`.

- **`check_an01_r3.py` on the new table:** 59 PASS, 0 failures, about 5 s.
- **`--coverage-only --table <b436c5e table>`:** 7 explicit FAILs, no exceptions. They are New York's lower edge (2), the Kolkata and Tokyo upper sentinels (2 each), and whole-domain coverage, with 4,621 uncovered window starts.
- **The b436c5e checker on its own table** still passes 23/23, which shows the gap it missed.
- **`derive_an01_zones.py --check`:** matches the committed table on Windows (tzdata wheel 2026e) and native Ubuntu (system zoneinfo 2026e, no tzdata module), with the same digest.
- **Other checks:** the r2 `check_an01.py` reports 0 failures; links and anchors in `docs/analytics/*.md` show 0 problems; Ruff is clean.

## Not verified / gaps

- No report SQL exists, and AN01-M1 is a plan only.
- Still provisional: the cap of 200,000, `B` 5,000 ms, `R` 250 ms, and `M`/`Q` 2/2.
- Points that need implementation-time review:
  - parameterizing the quarantine registry in `budget.py`;
  - a ROLLBACK measured against the report's end;
  - whether the measurement harness's controls are equivalent to production code.
- The review document exists only on `task/coordination` and is referenced by path, not linked.

## Next action

Codex re-reviews r3.1. If it is accepted, AN01-M1 gets a separate concrete assignment.

## Coordination and provenance

- The review probes in canonical `.agent/an01-r3-review/` were read and copied only, never changed.
- The zone data is IANA tzdata 2026e (public domain), derived locally without network.
- Preserved: b436c5e, the r2 documents, accepted checkouts, main and Cursor's seven edits.
