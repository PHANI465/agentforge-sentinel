# P4a and AN01 delivery intake: November6,2026

The owner delivered two clean candidates and explicitly requested further parallel Claude
work while Codex review remains pending. This is intake and task dispatch, **not acceptance**.

| Candidate | Exact tip | Base | Delivered scope |
| --- | --- | --- | --- |
| P4a | 96293da1a3403bb1d9bf9eb7c669354b2089c5be | d8443a1 | evaluator scripts/support, tests and docs |
| AN01 | dd6518d85a864a4742f75b29b66beaa656dca085 | d8443a1 | three analyst design documents and handoff |

The branch tips, clean author checkouts and owner author/committer identity were inspected.
Claude reports passing exact Windows/native P4a gates, deterministic smoke and negative
controls. Those results are author-provided and have not been independently certified here.
AN01 proposes contracts; no route/capability/migration is accepted by receiving its report.
Both original branches/worktrees stay frozen at these tips. Do not merge them into main
or import P4a into independent tasks. Application main remains tested495c7d3 plus docs.

## Intake observations for AN01 refinement, not a full contract review

- A fixed ingested_at cutoff is not a shared MVCC snapshot across requests. A transaction
  timestamped before the cutoff can commit later, and tied/backward clocks can admit a
  later write beneath it. Each READ ONLY/REPEATABLE READ request is internally consistent,
  but different requests may see different committed rows. Current case state is mutable.
- R03's event time is before the window end but its ingestion/case creation is after it.
  Workload and action expectations need explicit case/action timestamps and their own
  window rules. The ledger example also needs to separate API-created modern rows from
  deliberately provisioned pre-0002 missing-score fixtures. Current ingestion atomically
  records an outcome, so a normal current POST cannot produce a missing-outcome row.
- Row-count bounds on aggregate output do not bound scanned data. Day lengths for all
  IANA zones must not be hard-coded as only23/24/25 hours. Label availability is called
  both S1 and deferred; capability provisioning and export auditing are still undecided.

The refinement agent gets concrete decisions/proposals without permission to implement
unaccepted backend/UI or change frozen contracts. PERF01 and DEMO01 use accepted runtime
only. Generic D09-D11 agent security tests already exist; duplicating them just to use
quota is not assigned. Linux browser/CI/public-BYOK and live P4b remain future gates.

## Authorized next batch

[Three-agent coordinator prompt](../prompts/CLAUDE_PARALLEL_BATCH_2026-11-06.md):
AN01-r2 design refinement, bounded deterministic local capacity measurement, and a
portable key-free recorded demo. Parallel editing is allowed in separate worktrees;
one heavy execution slot serializes DB/load/browser/full-gate jobs across all agents.
No provider/auth, final cases, paid overage, external push or deployment. Codex retains
sole main integration authority; any Claude combined preview remains a task branch.
