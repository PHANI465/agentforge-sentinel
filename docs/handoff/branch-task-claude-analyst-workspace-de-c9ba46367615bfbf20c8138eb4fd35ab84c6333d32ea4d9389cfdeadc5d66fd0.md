# Handoff: task/claude-analyst-workspace-design

- **Task and acceptance criteria:** AN01, an independent financial analyst workspace design package ([CLAUDE_ANALYST_WORKSPACE_DESIGN.md](../prompts/CLAUDE_ANALYST_WORKSPACE_DESIGN.md), batch [CLAUDE_TODAY_BATCH_2026-11-06.md](../prompts/CLAUDE_TODAY_BATCH_2026-11-06.md)). Design only.
- **Tool and worktree:** Claude Code (Opus 5.5 / High), in E:/PHANI/sentinel-wt/claude-analyst-workspace-design.
- **Base:** published main d8443a199200157afa2131ddf8f22c1d20b89a26, which contains tested 495c7d3 and accepted plan cee83f9. It does not use or depend on the unaccepted G3D-P4a branch.
- **Updated:** 2026-11-06, local time.
- **State:** ready for Codex review.
- **Changed paths:**
  - docs/analytics/AN01-workspace-design.md (new)
  - docs/analytics/AN01-report-contract-draft.md (new)
  - docs/analytics/AN01-acceptance-cases.md (new)
  - this note

  No production source, API contracts, tests, schemas, models, data or evals, UI, locks or central docs changed.

## Delivered

- **Design.**
  - Analyst questions are mapped to the tables that actually exist. Unsupported items are named: reversals, fees, FX, replay counts, and history of case states.
  - The smallest first release (S1): currency totals, daily activity, workload and data quality, a drilldown, and CSV export.
  - Principles: curated SQL only, server-side scope, a snapshot plus an `as_of` cutoff, integer money per currency, and "observable is not true".
  - Money terms (debit, credit, gross, net outflow), with sums as strings above JavaScript's safe-integer limit. Time semantics: a half-open `occurred_at` window, `ingested_at <= as_of`, tz bucketing and DST.
  - Index and JSONB access, and limits. Labels and model-error rules (deferred, with S1 limited to availability counts).
  - The UI flow (Mermaid) with its states, accessibility and export rules, the implementation split and dependency order, and a ranked backlog.
- **Contract draft.**
  - A draft route `GET /v1/reports/{report_id}`, using `read_case` plus a new draft `export_report` capability.
  - Validated filters, six report IDs with columns and units, a DTO example, CSV rules and normative calculation rules.
  - Five open questions, including export auditing: `audit_events.case_id` is NOT NULL today.
- **Acceptance cases.**
  - A 15-request known-answer example: two sessions and a foreign tenant, four currencies (JPY exponent 0), window and `as_of` boundaries, a replay, a conflicting replay, a rejected zero amount, a missing outcome, and delayed labels.
  - Hand-checkable expected totals, row sets, a Kolkata timezone variant, page splits and lag quantiles.
  - 14 proposed implementation checks (A1–A14), clearly marked as not run.

## Verified (docs only)

- **Arithmetic:** checked by hand, and by one no-I/O Python calculation (scratch, not committed). It reproduced all UTC and Kolkata totals, the row sets, the page split (R01, R05, R02 / R14, R07, R15 / R06, R03) and the lag quantiles (p50 1.001, p95 5.0, max 5.0). It also confirmed that 1,001 maximum-size amounts exceed 2^53 − 1.
- **Code references:** the routes, the `Money` contract, the currency exponents, the max/default page sizes, the tables and indexes (migrations 0001–0004), the `cases.created_at` column (0003), `audit_events.case_id NOT NULL`, the rule thresholds, the UI files and `scripts/export_http_contract.py`.
- **Links:** all relative links resolve.
- **Not run:** no database, API, UI, backend or browser checks. Docs only.

## Gaps / open questions

- The export capability grant and export auditing (table versus nullable case link) both need review.
- The index migration versus generated columns.
- Whether `labels.availability` belongs in S1.
- The default staleness threshold for the UI.
- Exact state history for a past `as_of` is not supported; S1 labels it as current state.

## Next action

Codex reviews the AN01 package and decides the open questions before any S1 implementation is assigned.

## Coordination and provenance

- Original documentation. No dependency on G3D-P4a. Accepted worktrees and Cursor's seven saved edits are untouched.
