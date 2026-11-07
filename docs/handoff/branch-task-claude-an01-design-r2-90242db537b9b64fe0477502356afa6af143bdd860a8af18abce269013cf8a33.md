# Handoff: task/claude-an01-design-r2

- **Task and acceptance criteria:** AN01-r2, a refinement of analyst report semantics before implementation (`docs/prompts/CLAUDE_AN01_DESIGN_REFINEMENT.md` on main). It resolves the seven issues of that prompt and of the intake note `docs/handoff/P4a-AN01-delivery-intake-2026-11-06.md` (main). Docs/spec only.
- **Tool and worktree:** Claude Code (Opus 5.5 / High), as Worker A of the coordinated batch, in E:/PHANI/sentinel-wt/claude-an01-design-r2.
- **Base:** exact `dd6518d85a864a4742f75b29b66beaa656dca085` (the original AN01 draft r1). The r1 branch and worktree `task/claude-analyst-workspace-design` were not touched.
- **Updated:** 2026-11-06, local time.
- **State:** ready for Codex review. This is not contract acceptance.
- **Code reference tested before this note:** the docs-only working tree of this commit, on base dd6518d. The checker ran on the final file contents. Post-commit evidence is reported in the coordinator's chat, not here.
- **Owned and changed paths:**
  - docs/analytics/AN01-workspace-design.md (revised)
  - docs/analytics/AN01-report-contract-draft.md (revised)
  - docs/analytics/AN01-acceptance-cases.md (revised)
  - docs/analytics/check_an01.py (new; stdlib only, no I/O beyond stdout)
  - this note

  No production source, tests, schemas, grants, migrations, UI, locks, frozen contracts, models, data or evals changed. The r1 handoff note is preserved unchanged.

## Implemented

- **1. Snapshots.** The S1 proposal is honest per-request `REPEATABLE READ, READ ONLY` snapshots.
  - Cross-request change is disclosed. Drilldown pages detect it with a monotone `(matching_transactions, with_outcome)` pair, which is sound because the runtime role cannot UPDATE or DELETE `transactions` or `scoring_outcomes` (roles.py).
  - The held snapshot is deferred, and late-commit, slow-clock and tie known answers are included.
- **2. Time bases.** Event time, case creation (`cases.created_at`, which is the ingestion time), action completion (`body.completed_at`) and current workload (`read_at − created_at`, no window, no `as_of`) are separate.
  - R03 is no longer a case "created in window".
  - State is always current, and a past `as_of` is shown not to reconstruct history.
- **3. Fixtures.**
  - API requests (15) are separated from one labelled owner-role pre-0002 row (R14), and request counts from stored-row counts.
  - The amounts were changed so that the stated alerts equal rule r1's real outcomes. R05 becomes INR 8,000,000, exactly at the cutoff; R07 becomes JPY 200,000.
  - A tie row (R16) was added.
- **4. Bounds.**
  - Money bounds were re-verified (`MAX_MINOR_UNITS` 9e12, `gt=0`; there is no DB CHECK on the body). Sums use `numeric`.
  - Day length is in seconds. The S1 five-zone allow-list is justified by a zoneinfo scan (Lord Howe, Troll, Apia, Havana and Santiago are documented as excluded).
  - Bucket boundaries are computed in Python and passed to SQL.
  - Result rows, matching rows (a 200,000 guard), time (a statement/lock budget, 503) and memory (not bounded) are stated separately.
- **5. Permissions.**
  - A new draft `read_report` capability, plus `read_case`, issued by the operator CLI only. It is not in the default set and is never backfilled.
  - The frozen v1.x `Capability` and `SessionView` enum impact is called out.
  - Export is deferred to S2, with one explicit `report_exports` append-only audit proposal.
- **6. Trims.**
  - `labels.availability` is deferred everywhere. Case outcomes are not labels, and no agent gains report access.
  - The cursor is bound to the report and a filter digest, with malformed, tampered and changed-data rules.
  - S2 export is fully buffered (no streaming).
- **7. Known answers.** `check_an01.py` recomputes them. The database and browser tests (A1–A15) are labelled unrun.

## Verified

- Known answers -> `uv run --locked python docs/analytics/check_an01.py` -> 34 PASS lines, `OK: 0 failure(s)`, exit 0 (Windows, CPython 3.11.3).
- Lint -> `uv run --locked python -m ruff check docs/analytics/check_an01.py` -> "All checks passed!"
- One-off zoneinfo checks (tzdata 2026e, `tzdata` 2026.5 locked for win32), not in the checker:
  - local day lengths for New York, London, Lord Howe and Troll in 2026;
  - Apia 2011-12-30 skipped;
  - Havana and Santiago local midnight gaps;
  - for the five allowed zones over 2000–2037, only 82,800/86,400/90,000-second days and no midnight gap or ambiguity (15-minute scan);
  - a 92-day window touches at most 93 local dates (UTC, Kolkata, Tokyo) or 94 (London, New York).
- Links -> a scratch script resolved every relative Markdown link and every cited existing source path; the only paths not found are the draft-new `src/sentinel/reports*` and `web/src/ui/Reports*`. The intake note exists on main.
- Code facts were read at dd6518d: `Money`, `MAX_MINOR_UNITS`, `CURRENCY_EXPONENT`, `TrustedContext`, `Capability`/`SessionView` (and the frozen OpenAPI enums), `ingest`/`_ingest`, `list_cases`, `overview`, `decode_cursor`, `MAX_PAGE_SIZE`, `roles.RUNTIME_PRIVILEGES`, migrations 0001–0005, `trace.py`, the CLI `create-session`, `record-disclosures`, r1 `RULE_CONFIG` and the i1 investigator.

## Not verified / gaps

- No database, API, browser or full-gate run: none is needed or allowed for docs.
- The fixture construction (FakeClock harness, case workflow through i1, approval and action) is derived from reading the code, and unrun.
- PostgreSQL's handling of nonexistent and ambiguous local times was cited from its documentation, not run. The design avoids depending on it.
- `width_bucket` or the equivalent SQL bucketing is not specified exactly.
- `scripts/agent_check.py` was not run: it runs project gates beyond this docs scope.

## Next action

Codex reviews the revised contract (design §13, contract §7). Implementation waits for that acceptance.

## Coordination and provenance

- Owned paths only. There is no main merge, push, provider/auth call, final-case or holdout access, or new dependency.
- Proposed future contract changes (all draft): a `read_report` capability, error codes `report_too_large` and `report_timeout`, a transactions index migration, and S2 `export_report` with `report_exports`.
