# Handoff: task/claude-an01-decisions

- Task and acceptance criteria: the owner's request of November 7.
  - Propose concrete resolutions for AN01's six open contract decisions, and a bounded
    report-query measurement plan.
  - Keep unmeasured limits provisional.
  - No production endpoint and no frozen-contract change.
- Tool and worktree: Claude Code, `E:/PHANI/sentinel-wt/claude-an01-decisions`, from main
  c2140ce19e080244830e4ffe799a35f8b6ec50f1.
- Updated: 2026-11-07 (America/Phoenix).
- State: ready for Codex review. This is a documentation proposal; nothing is accepted.
- Code reference tested before this note: the working tree on top of c2140ce, whose only
  changes are this branch's documentation files, before commit.
- Final check evidence: the documentation checkers and ruff are rerun after the final
  commit and reported in chat. No full strict gate was run, because nothing under src,
  tests, contracts or web changes.
- Owned/changed paths:
  - `docs/analytics/AN01-decisions-r3.md` (new)
  - `docs/analytics/AN01-zone-table.json` (new)
  - `docs/analytics/derive_an01_zones.py` (new)
  - `docs/analytics/check_an01_r3.py` (new)
  - one pointer line each in `docs/analytics/AN01-workspace-design.md` §13 and
    `AN01-report-contract-draft.md` §7
  - this note

## Implemented

The six resolutions are in `AN01-decisions-r3.md`:
1. **Time zones.** A committed five-zone midnight table (IANA 2026e, sha256 dd1b19c9…) is
   used at runtime instead of host zoneinfo, with no lockfile change.
2. **Capability and version.** An additive HTTP v1.3 adds `read_report` and freezes v1.2.
   Clients must ignore unknown capabilities, and the server keeps closed validation.
3. **Cursor.** Unsigned, with strict members and a derived 256-character limit (worst case
   228). The UI never takes a cursor from navigation.
4. **Limits.** The database budget reuses `BoundedTransaction` and ends with ROLLBACK; it is
   explicitly not a response deadline. The 200,000-row cap and the 5,000 ms budget stay
   provisional.
5. **Indexes.** `transactions (tenant_id, session_id, occurred_at, id)`, plus a
   measurement-gated `simulated_actions (tenant_id, session_id)`. No generated columns.
6. **Staleness wording.** An earlier `as_of` is labelled a chosen cutoff, result age is
   measured on the browser's monotonic clock, and a 5-minute nudge is policy.

AN01-M1 is a bounded measurement plan with phases, caps and pre-registered decision rules.
It is not run.

## Verified

- `uv run --locked python docs/analytics/check_an01_r3.py`: 23 PASS, 0 failures. This covers
  the cursor bound, the zone-table digest and invariants, the r2 known answers, and the
  bound of 94 local dates and 376 daily rows, checked exhaustively over 2000–2037.
- `uv run --locked python docs/analytics/derive_an01_zones.py --check`: matches the committed
  table on Windows (tzdata wheel 2026e, Python 3.11.3) and on native Ubuntu WSL (system
  zoneinfo 2026e, Python 3.11.14, no tzdata module).
- The existing `check_an01.py` still reports 0 failures. `ruff check docs/analytics` is clean.

## Not verified / gaps

- No report SQL exists, and nothing was measured; AN01-M1 is a plan only.
- The cap and budget remain provisional.
- No contract export, product test, browser or full strict gate was run, because this
  branch changes documentation and docs-only checkers.

## Next action

Codex reviews the six resolutions and the AN01-M1 plan. If they are accepted, assign AN01-M1
(or a corrected plan) before freezing the S1 contract.

## Coordination and provenance

- All facts were read from main c2140ce source. The zone data comes from IANA tzdata 2026e
  (public domain), derived locally; no network was used.
- Preserved: AN01 r1 dd6518d, r2 a8c164a, accepted branches, Cursor's seven edits and the
  canonical checkout on main.
