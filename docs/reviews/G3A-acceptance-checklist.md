# G3A acceptance checklist

## Final status: accepted 43d9e8a, R31-R33 closed

[Independent final acceptance](G3A-43d9e8a.md) closes all design gates. Revision3 passes
the positive reserve case, no zero/negative rounding, single-host connection/granularity,
shared transaction budgets and honest uncertain outcomes. Mutations fail (15/8/3/14),
120 extra budget combinations pass, and all 15 schemas / 35 valid / 50 invalid / 15 dev
cases and earlier semantic controls remain green. Schema/example/catalog bytes match
revision2. Runtime proof, real COMMIT behavior and platform gates belong to G3B.
The original checklist and review chronology below are historical, not open blockers.

## Revision 2 independent review — October 31

Exact feb80d1 reviewed: **R32/R33 closed; R31 admission/late-worker portion closed**.
**R31 full elapsed budget remains open** for the terminal-reserve formula and contradictory
protocol definition. See [the review](G3A-feb80d1.md) and
[current narrow follow-up](../prompts/CLAUDE_G3A_DEADLINE_FOLLOWUP.md).

Actual checks: 15 schemas / 35 valid / 50 invalid examples, 15 dev cases, Ruff, links/anchors,
14 baseline/regression pairs, 3 actor variants, 54 usage combinations, 8 role subsets and
6 lifecycle negative controls pass. The old formula independently returns 0/-1/-5 for
5/4/0 seconds remaining. Scope/parent/sole-owner metadata pass. No corrected deadline
candidate exists yet; no interface freeze or G3B dispatch. The original checklist below
is retained as the resumption record, not a list of still-open R32/R33 issues.

## Original resumption checklist (historical status column)

Prepared by Codex on October 31, 2026, on the owner's resumption. This is the review plan
for the documentation-only correction of 06a7c0c. **No item below is satisfied merely by
being listed. No corrected candidate has been delivered or accepted yet.**

Read [the original findings](G3A-06a7c0c.md) and
[the active assignment](../prompts/CLAUDE_G3A_REVIEW_FOLLOWUP.md).

| Gate | Evidence required from the corrected package | Status at resumption |
| --- | --- | --- |
| Exact task ancestry and scope | Existing task branch descends from 06a7c0c; only owned design/eval docs and branch note; sole-owner metadata and no trailers | Awaiting revision |
| R31 admission and worker lifetime | Explicit lease owner/release table; finite outstanding calls including late workers; no repeat overlap beyond that bound; unresolved work remains capacity-accounted | Awaiting revision |
| R31 full elapsed budget | Deadline covers gathering/tools/coordinator, including bounded connection, lock and statement waits; examples distinguish HTTP completion from late-worker completion | Awaiting revision |
| R31 refusal/release examples | Timeout, attempted second admission, late result discard, actual worker completion, and eventual safe release; no provider cancellation/billing promise | Awaiting revision |
| R32 terminal transaction | Scoped case/workflow revision guards, terminal state/code/time and audit principal without requiring a running AgentRun | Awaiting revision |
| R32 no-role and between-role examples | Zero-role exhaustion and crash/recovery between completed roles reopen without intent; preserve completed statuses; report honest CaseDetail | Awaiting revision |
| R32 abstention basis | Identify an eligible completed investigator in the same workflow; if none, inconclusive/no intent; human approval still separate | Awaiting revision |
| R33 exact required roles | Empty or incomplete role maps rejected; exactly analyst, investigator and reviewer required | Four baseline probes still accept invalid states |
| R33 usage invariants | Unknown/not-applicable usage cannot carry measured counts; adapter-reported counts have a coherent measured/source representation | Awaiting revision |
| R33 lifecycle and time | Terminal states require coherent finish/disposition; running states reject terminal combinations; timestamp order checked; zero-role terminal example valid | Awaiting revision |
| Schema boundary | Cross-record scope, basis membership, policy, counts and pins explicitly assigned to coordinator checks rather than implied by JSON shape | Awaiting revision |
| Evaluation interpretation | C1/C2 labelled end-to-end with unequal evidence access; no causal role claim; common rubric, zero-denominator handling, completion/failure counts | Awaiting revision |
| Four resolved design decisions | New capacity409; provisional 45s/150s; inconclusive reopens open/no intent; usage unknown unless observed | Must remain consistent |
| Actual scoped checks | New regression examples accepted on original candidate then rejected by corrected draft; generated schemas, valid/invalid examples, 12 development cases, Ruff, links and protected bytes | Baseline rechecked October 31; correction pending |

The four original semantic probes were re-run on unchanged 06a7c0c on October 31 and still
accept: empty roles, unknown usage with token counts, completed without disposition/finish,
and deadline before start. Supplied checks still pass (13 schemas, 24 valid / 25 invalid,
12 dev cases, Ruff, five-document links). These are baseline evidence, not new fixes.

Codex independently re-runs the corrected examples and additional negative controls after
handoff, reads the resolved lifecycle examples and reviews all changed paths. A full backend
or browser suite is unnecessary for this documentation-only gate. Freeze the accepted
schema/protocol only after the findings close, then dispatch G3B at an exact accepted SHA.
Runtime resource, concurrency, transaction and platform tests are G3B acceptance work.
Do not create or inspect final held-out cases during this correction.
