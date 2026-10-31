# G3A draft contracts (`g3a-draft-1`)

These are proposed shapes for the three-role workflow, kept outside the frozen `contracts/` tree. They become frozen only when Codex accepts G3A. G3B then moves them into `src/sentinel/contracts/agents.py` and exports them beside the v1 schemas.

| File | Purpose |
| --- | --- |
| `g3a_models.py` | Pydantic draft models, reusing the frozen v1 primitives (`Id`, `Digest`, `Timestamp`, `ArtifactRef`, `Revision`). It is also the checker |
| `schemas/*.schema.json` | Generated JSON Schemas (15) |
| `examples/valid/*.json` | Payloads that must validate. The D01 worked case, the main variants and the R31/R32 terminal and lease examples |
| `examples/invalid/*.json` | Payloads that must be rejected, each for one stated reason. `*.r33-*.json` are the review regressions (below) |

The example file prefix names the model it is checked against.

**Check:** `uv run --locked python docs/agents/contracts-draft/g3a_models.py --check`. This regenerates the schemas in memory, fails on stale or extra schema files, and validates every example against its label. Use `--write` to refresh the schemas after an intended model change.

## Models

| Model | Trust | Notes |
| --- | --- | --- |
| `ToolRequest` (discriminated by `tool`) | untrusted (role) | `case_evidence`, `scoring_outcome`, `account_history{window: 24h\|7d\|30d}`, `account_profile`. No other fields: there are no IDs, SQL, paths or URLs |
| `ToolResult` | server | `status` is `ok`, `unavailable` or `denied`. A denial carries its code; only `ok` carries values. `window` is used only by history. It is content-digested and computed as of the decision time |
| `Claim` = `FactClaim` \| `MissingEvidenceClaim` | untrusted (role) | A fact claim is a fact key, a relation (`eq`/`gte`/`lte`), an integer or boolean value, and a citation (evidence or tool-result ID). There are no floats and no free-text facts |
| `AnalystOutput`, `InvestigatorOutput`, `ReviewerOutput`, `RoleOutput` | untrusted (role) | Bounded lists. `note` is ≤400 characters, display-only and never forwarded. The investigator selects an operation and reason only (no parameters). The reviewer verdict is `accept`, `challenge` or `abstain`; there is no approve |
| `ClaimCheck` | server | Per-claim result: `supported`, `unsupported` or `uncheckable` (reserved), with a reason code |
| `WorkflowConfig`, `WorkflowLimits` | server (pinned) | Exactly the three role config refs (no fewer, no others), tool profile, claim schema and hard limits. Every limit has an upper bound. The deadline must fit one full role call + grace + terminal reserve, and outstanding call slots must be ≥ admitted workflows. Limits also bound database waits and the terminal reserve |
| `StepRecord`, `Usage` | server | One append-only coordinator event. `role_failed` (only) carries a failure code, and only a timed-out call may set `worker_unresolved`. `Usage`: `unknown`/`not_applicable` are unmeasured with no counts; `adapter_reported` is measured with both counts |
| `Disposition` | server | `recommend` (an operation, all adopted claims supported), `abstain` (always escalate/`insufficient_evidence`) or `inconclusive` (a typed code, no operation, no basis). Codes add `call_capacity_exhausted`, `coordinator_error` and `interrupted` (recovery) |
| `WorkflowRecord` | server | One coordinator attempt. **Lifecycle:** `running` has no finish, disposition or terminal actor. `completed` has a finish, a recommend/abstain disposition by the coordinator, and ≥3 role invocations. `inconclusive` has a finish, an inconclusive disposition, and `terminal_by` coordinator, or recovery (only with `interrupted`). **Time:** deadline > start; finish ≥ start. Zero role invocations is valid for an inconclusive record |
| `TraceSummary`, `TraceRole` | server read model | Proposed v1.2 additive response (G3C UI). Not needed for G3B |

## Compatibility and error semantics

- **Frozen contracts are unchanged.** v1 domain contracts (`contracts/v1`) and the HTTP v1 and v1.1 documents are not modified. `AgentRun`, `Case`, `CasePins`, `InvestigationFinding`, `ActionIntent` and `AuditEvent` keep their v1 shapes:
  - the composite workflow is pinned through the existing `CasePins.agent_config`/`tool_config` (`ArtifactRef`s);
  - per-role runs reuse `AgentRun.role`, including `evidence_analyst`/`reviewer`, and status `inconclusive`, which v1 already allows.
- **The v1.1 `CaseDetail` stays valid.** `agent_runs[*].finding` is filled only for the adopted investigator run, with a server-rendered `InvestigationFinding`. Analyst, reviewer and superseded runs return `finding: null`. Exhaustion before the first role returns `agent_runs: []` (G3A-design §6.1).
- **A role output failing validation** is the typed failure `invalid_output`, recorded as a `role_failed` step. It may use the workflow's single repeat (the worker returned), and is otherwise inconclusive. A forged identifier is rejected by `extra="forbid"`, not by sanitizing. **An excess or not-in-profile tool request** is not a role failure: it becomes `ToolResult(status="denied")`.
- **New HTTP error code:** 409 `agent_capacity_exhausted` (process capacity held, possibly by another case; no state change or disclosure). It is additive, and documented in the handled-code list in G3B. Existing codes keep their meanings; see G3A-design §8.
- **Version strings:** the draft schemas carry `schema_version: "g3a-draft-1"`. G3B may rename it to `"1.0"` under a new `sentinel.agents` namespace at freeze. The canonicalization namespace for digests will be `sentinel.agent-step.v1` and `sentinel.tool-result.v1`.
- **Is an HTTP revision needed?** No, not for the G3B backend slice. A v1.2 additive read route (`GET /v1/cases/{id}/investigation-trace` → `TraceSummary`) is needed only when the UI shows the role trace (G3C). It needs its own export, frozen examples and UI work.

## Coordinator checks (cross-record)

JSON shape alone cannot prove these. G3B must enforce each one in coordinator or service code, with its own tests:

1. **Citation scope.** An evidence citation is in this case's `evidence_ids`. A tool-result citation is an `ok` result recorded in **this workflow**. The cited record holds the fact.
2. **Claim truth.** The relation holds against the stored value. A `missing` claim is checked against every result and evidence item in the workflow.
3. **Basis membership.** `Disposition.basis_run_id` is an `agent_runs` row of the same workflow, with role `investigator`, status `completed` and the latest attempt (G3A-design §6.1).
4. **Reviewer indices.** `challenged_claims` index the claims of the investigator output under review.
5. **Policy consistency.** Operation and reason against supported claims (G3A-design §5); `simulated_hold` needs reviewer `accept`.
6. **Counters against records.** `role_invocations` and `tool_calls` equal the recorded `role_started` and `tool_executed` steps. They stay within the pinned `WorkflowLimits`. Step `seq` values are contiguous.
7. **Pins.** `WorkflowRecord.config` and `tool_profile` equal the case's `pins.agent_config` and `tool_config`. `input_snapshot_sha256` equals the case pin. `deadline_at - started_at` equals the pinned `workflow_deadline_seconds`.
8. **Scope and revision.** Every write is filtered by the context's tenant and session, and guarded by the case being `investigating` at `case_revision` and the workflow being `running`.
9. **Tool results.** `as_of` equals the alert decision time, and values come only from rows available by then.
10. **Terminal actor.** The audit actor matches `terminal_by` (the coordinator principal, or `SYSTEM_ACTOR`).
11. **Leases.** A live role call holds a call slot from submission until its worker returns. A repeat requires that the failed call's worker returned. These are process-local runtime checks, not record fields (G3A-design §3.1).

## Review regressions (R33) and baseline demonstration

`examples/invalid/*.r33-*.json` hold 14 payloads that use only 06a7c0c vocabulary:
- the four contradictions Codex reproduced: empty roles, unknown usage with counts, completed without disposition or finish, deadline before start;
- ten further combinations of the same classes: a missing reviewer, three more incoherent usages, running with a disposition or finish, inconclusive with recommend, completed with inconclusive, finish before start, completed without roles.

**Accepted then, rejected now.** The 06a7c0c models (`git show 06a7c0c:docs/agents/contracts-draft/g3a_models.py`, loaded outside the repository) **accept all 14**. The revised models reject all 14.

**Variants.** Three of them (completed with an inconclusive disposition, completed without roles, inconclusive with a recommend disposition) are now rejected first by the new terminal-actor requirement. The `*_actor.json` variants add `terminal_by` and are rejected by their own specific contradiction.
