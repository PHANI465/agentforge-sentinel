# AN01-r2: refine analyst report semantics before implementation

Recommended assistant: **Claude Opus5.5 / High**. Temporal consistency, money units,
export authority and a buildable contract need careful reasoning. This is docs/spec work.

Read current coordination and [delivery intake](../handoff/P4a-AN01-delivery-intake-2026-11-06.md).
The original draft dd6518d85a864a4742f75b29b66beaa656dca085 is not accepted. Preserve its branch/worktree.
Create task/claude-an01-design-r2 at E:/PHANI/sentinel-wt/claude-an01-design-r2
from **exact dd6518d**. This named draft dependency overrides the generic main base only
for this documentation revision. Read newer instructions from task/coordination with
git show; do not merge coordination or P4a into the draft just for context.

Own the three docs/analytics/AN01-*.md files, optional new docs/analytics/check_an01.py
(a tiny no-network/no-database known-answer checker), and your branch handoff only.
Do not implement routes, UI, migration, grants or export code; no production/test/lock/
frozen protocol/model changes. This refinement is not Codex contract acceptance.

## Resolve concrete issues and leave one implementable S1 proposal

1. **Snapshots and clocks.** ingested_at<=as_of alone cannot stabilize pages/exports
   across transactions: late commits, timestamp ties/backward jumps and mutable case
   state remain. A new REPEATABLE READ transaction per request is not the same snapshot.
   Choose a clear S1 proposal: honest per-request snapshots with cross-request changes
   disclosed, or a separately scoped materialized/held report snapshot design with
   authorization, expiry and failure semantics. Do not claim stability from a filter.
   Prefer the smaller truthful first slice; no storage mechanism is implicitly accepted.
   Add thought experiments/known-answer cases for a late commit and tied timestamps.
2. **Time bases.** Define event-time transaction windows separately from case creation,
   action completion and current workload age. R03 is ingested/case-created after the
   sample window; it cannot also be a case created inside that window. Add explicit
   case/action timestamps and correct expected answers. A past as_of is not a historical
   case-state reconstruction. State precisely which workload filters and clock apply.
3. **Real fixtures.** Modern POST ingestion creates scoring_outcomes atomically. A
   pre-0002 missing-score row requires an explicitly labelled operator/migration fixture,
   not a claim that all15 requests can create the sample through today's API. Invalid
   requests/replays/foreign rows must retain distinct request-vs-stored-row counts.
4. **Currency/timezone/query bounds.** Keep integer per-currency sums and JS-safe decimal
   strings. Verify each stored amount bound against code. All IANA local days are not
   restricted to23/24/25 hours (consider half-hour DST); specify actual interval seconds
   or a clearly reviewed narrower zone policy, including skipped/ambiguous local dates.
   Separate maximum result rows from scanned input and finite SQL waits; do not claim
   a92-day output shape bounds total query work or memory.
5. **Scope and permissions.** A report may reveal non-alert transactions absent from
   today's case list; do not justify a permission choice by saying it reveals nothing
   additional. Propose and justify access and an operator-only provisioning path. No
   silent capability backfill. For export auditing, choose one explicit proposal or
   defer export from S1; do not make a case audit entry with a made-up case or relax
   append-only protections. No schema/grant change is implemented here.
6. **Trim contradictions.** Decide whether labels.availability is S1 or deferred and
   make design, DTOs, backlog and acceptance cases agree. Keep delayed-label truth out
   of agents; case outcomes are not fraud labels. Cursors need scope/filter binding,
   malformed/missing/tampered behavior and honest handling when underlying data changes.
   Streaming export cannot promise a clean JSON error after headers; specify a bounded
   fully validated first version or honest partial-download behavior.
7. **Known-answer spec.** Make the source fixture and expected results executable in a
   tiny no-I/O checker if useful: per-currency sums, UTC/local windows, page order, missing
   scores, workload time bases, lag quantiles and unsafe CSV strings. Label proposed DB/
   browser tests as unrun. Do not touch ML holdout or agent-final data. Draft API shapes
   may be refined in docs only and must stay labelled unaccepted.

Check references/links/arithmetic, preserve the original draft and report exact changes,
remaining questions and actual results. No full backend gate for docs only. Sole author
AND committer PHANI465 <pgavara1@asu.edu>, no trailers/history rewriting. No main merge,
provider/auth, final cases, new dependency, external push or deployment. Backend/UI
implementation waits for Codex acceptance of the revised contract. Inform the parent
coordinator when ready; you need no heavy-execution slot for pure arithmetic/link checks.
