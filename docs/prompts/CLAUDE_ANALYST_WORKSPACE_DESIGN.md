# AN01: financial analyst workspace design, independent of P4a

Recommended assistant: **Claude Opus5.5 / High**. The work is documentation-only, but
needs precise financial units, scope, temporal semantics and known-answer examples.
This is the analyst-depth portion of the existing roadmap, not a renaming of its G4
public-operations milestone. Do not change milestone numbering in the project plan.

Read current task/coordination:AGENTS.md/STATUS/TASK_QUEUE and accepted application
contracts/docs from current main. Create task/claude-analyst-workspace-design at
E:/PHANI/sentinel-wt/claude-analyst-workspace-design from the current published main
that contains tested495c7d3 and accepted P4 plan cee83f9. Record the exact base. Do not
merge P4a or build on its unaccepted code; this design does not depend on it.

Own new docs/analytics/AN01-workspace-design.md, docs/analytics/AN01-report-contract-draft.md,
docs/analytics/AN01-acceptance-cases.md and your branch handoff only. Keep central docs,
production source, API contracts, tests, schemas, models/data/evals, UI and locks unchanged.
No provider/auth call, deployment, service signup, final-case generation/inspection or
real financial/customer data. Existing development data can inform examples, but do
not touch protected agent-final or ML holdout assets to design new analytics.

Deliver one implementable analyst slice, with a ranked backlog rather than all of
finance at once. Default product remains synthetic fraud review and simulated actions.

1. Explain the target analyst questions: transaction/alert trends, per-currency money
   reconciliation, queue/disposition workload, data-quality checks and model/error slices.
   Distinguish actually available transaction/score/case tables from an imagined warehouse.
   Specify the smallest useful first release and defer unsupported dashboards.
2. Propose curated read-only query/report IDs with validated filters, max date range,
   row/pagination limits, timezone/as-of semantics, tenant/session scope and snapshot
   consistency. No arbitrary LLM SQL, owner-role queries, write tools or invented
   existing endpoints. Mark every new route/permission/DTO as a draft requiring review.
3. Define integer minor-unit money calculations per currency/exponent. Never sum USD,
   INR/GBP/JPY into one money total. Gross/net/debit/credit/reversal meanings must be
   explicit and supported by stored fields. No FX conversion without separately
   specified dated rates; do not fetch prices/rates or introduce a financial data vendor.
   Replay requests do not create new transactions or inflate aggregate counts.
4. Separate labels/truth from observable outcomes. Case approval, alert or model score
   is not confirmed fraud. Error analysis requires a labelled dataset with eligibility
   and cutoff provenance; preserve delayed-label rules and uncalibrated-score wording.
   Private agent evaluation packets are not a public dashboard data source.
5. Write a small, explicit synthetic known-answer example (about12-20 rows) with at
   least two currencies, boundary timestamps, missing values, a replay and foreign scope.
   Show hand-checkable expected counts/totals/filter results, not invented benchmark
   performance. Use a tiny no-I/O calculation if helpful and report it honestly.
6. Describe the existing UI's extension flow: filter -> report -> underlying scoped
   rows/case -> export, with empty/loading/error/stale/denied states, accessibility and
   clear provenance. Sketch in Markdown/Mermaid only; no new app/mock UI as finished work.
   Exports need safe text/CSV formulas, private scoping and audit/retention proposals.
7. Map accepted tables/contracts to required backend/frontend work. List missing API
   semantics and a dependency order so Claude/Cursor can later implement disjoint owned
   slices after contract acceptance. Reuse PostgreSQL/FastAPI/React/TypeScript first;
   no new warehouse/agent framework/dependency simply to expand the stack.
8. List acceptance cases: reconciliation, pagination/time/currency boundaries, replay,
   two sessions/tenants, denied exports, malicious formula/text, snapshot consistency
   and label leakage. State proposed checks separately from tests actually run.

Check local links, code references and example arithmetic. No full backend/browser gate
for docs only. New commit(s): PHANI465 <pgavara1@asu.edu> sole author AND committer,
no trailers/rewrite, explicit owned paths. Return exact SHA, draft contracts/questions,
arithmetic/link results and gaps. Do not merge main or start implementation. This can
be completed while P4a waits for Codex review, without editing P4a's branch again.
