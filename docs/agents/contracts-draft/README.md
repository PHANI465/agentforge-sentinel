# G3A draft contracts (`g3a-draft-1`)

These are proposed shapes for the three-role workflow, kept outside the frozen `contracts/` tree. They become frozen only when Codex accepts G3A. G3B then moves them into `src/sentinel/contracts/agents.py` and exports them beside the v1 schemas.

| File | Purpose |
| --- | --- |
| `g3a_models.py` | Pydantic draft models, reusing the frozen v1 primitives (`Id`, `Digest`, `Timestamp`, `ArtifactRef`, `Revision`). It is also the checker |
| `schemas/*.schema.json` | Generated JSON Schemas (13) |
| `examples/valid/*.json` | Payloads that must validate. The D01 worked case and the main variants |
| `examples/invalid/*.json` | Payloads that must be rejected, each for one stated reason |

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
| `WorkflowConfig`, `WorkflowLimits` | server (pinned) | Role config refs, tool profile, claim schema and hard limits. The limit fields have upper bounds, so an unbounded configuration cannot validate |
| `StepRecord`, `Usage` | server | One append-only coordinator event. `Usage` states whether tokens were measured; unknown is never zero |
| `Disposition` | server | `recommend` (an operation, all adopted claims supported), `abstain` (always escalate/`insufficient_evidence`) or `inconclusive` (a typed code, no operation) |
| `WorkflowRecord` | server | One coordinator attempt: pins, deadline, counters, disposition |
| `TraceSummary`, `TraceRole` | server read model | Proposed v1.2 additive response (G3C UI). Not needed for G3B |

## Compatibility and error semantics

- **Frozen contracts are unchanged.** v1 domain contracts (`contracts/v1`) and the HTTP v1 and v1.1 documents are not modified. `AgentRun`, `Case`, `CasePins`, `InvestigationFinding`, `ActionIntent` and `AuditEvent` keep their v1 shapes:
  - the composite workflow is pinned through the existing `CasePins.agent_config`/`tool_config` (`ArtifactRef`s);
  - per-role runs reuse `AgentRun.role`, including `evidence_analyst`/`reviewer`, and status `inconclusive`, which v1 already allows.
- **The v1.1 `CaseDetail` stays valid.** `agent_runs[*].finding` is filled only for the adopted investigator run, with a server-rendered `InvestigationFinding`. Analyst, reviewer and superseded runs return `finding: null`.
- **A role output failing validation** is the typed failure `invalid_output`, recorded as a `role_failed` step. It consumes the workflow's single repeat, and is otherwise inconclusive. A forged identifier is rejected by `extra="forbid"`, not by sanitizing. **An excess or not-in-profile tool request** is not a role failure: it becomes `ToolResult(status="denied")`.
- **New HTTP error code:** 409 `agent_capacity_exhausted` (live adapter busy, no state change). It is additive. Existing codes keep their meanings; see G3A-design §8.
- **Version strings:** the draft schemas carry `schema_version: "g3a-draft-1"`. G3B may rename it to `"1.0"` under a new `sentinel.agents` namespace at freeze. The canonicalization namespace for digests will be `sentinel.agent-step.v1` and `sentinel.tool-result.v1`.
- **Is an HTTP revision needed?** No, not for the G3B backend slice. A v1.2 additive read route (`GET /v1/cases/{id}/investigation-trace` → `TraceSummary`) is needed only when the UI shows the role trace (G3C). It needs its own export, frozen examples and UI work.
