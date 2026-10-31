# 0007: Bounded three-role investigation workflow (G3B)

- Status: implemented for review (G3B); the design was accepted at G3A 43d9e8a and integrated at 2919f76
- Date: 2026-10-31
- Decided by: the project owner and Codex (G3A acceptance); implemented by Claude Code

## Context

G3 needs evidence analyst, investigator and reviewer roles behind a deterministic coordinator, without weakening the existing human approval path. The accepted design lives in [G3A-design](../agents/G3A-design.md), with its evaluation in [protocol-v1](../evals/agents/protocol-v1.md).

## Decision

- **An explicit operator mode.** `SENTINEL_INVESTIGATOR=three-role` is an operator choice, and `SENTINEL_AGENT_ADAPTER` is `deterministic` (default) or `claude-cli` (local only). The single deterministic investigator remains the default, and single-Claude mode is unchanged.
- **Pins without contract changes.** The composite `three-role-workflow` w1 (role configs, the `agent-read-tools` t1 tool profile, claim schema `agents-1.0`, limits) is pinned through the existing `CasePins.agent_config` and `tool_config`. Switching modes makes open cases `stale_agent_config`.
- **Contracts.** The accepted draft is promoted mechanically into `sentinel.contracts.agents`: `schema_version` "1.0", claim schema "agents-1.0", 15 schemas exported under `contracts/agents/`, and 85 ported examples. Legacy v1/v1.1 domain and HTTP bytes are unchanged.
- **Migration 0005:**
  - `agent_workflows`, with one running workflow per case;
  - `agent_steps`, append-only for application roles, as audit events are;
  - `agent_runs.workflow_id`, `attempt` and `seq`.

  The runtime grants are SELECT/INSERT/UPDATE on workflows, SELECT/INSERT on steps, and USAGE on the two new sequences.
- **Server-owned decisions.** The coordinator (`sentinel.agents`) owns the transitions, the four read-only tools, claim verification, the disposition and the intent. Roles return untrusted output only.

## Implementation decisions beyond the design text (for review)

1. **COMMIT watchdog.** Real PostgreSQL disables `statement_timeout` before commit processing: a 3 s deferred trigger was not cancelled by a roughly 1.9 s `statement_timeout` (observed in the `test_commit_refused_by_its_timeout_is_a_known_rollback` baseline). COMMIT is therefore bounded by a client-side cancel request when the remaining budget runs out.
   - If the server answers with an error, it is a known rollback (409 `investigation_in_progress`).
   - If there is no definitive reply, the outcome is uncertain (409 `investigation_outcome_unknown`).
2. **`agent_runs.seq`.** CaseDetail ordered runs by `started_at` only. Sequential role runs can share a clock reading, so `seq` (insertion order) breaks ties. Every historical run is still returned.
3. **The packaging list.** `pyproject.toml` lists packages explicitly, so `sentinel.agents` was added to the wheel/sdist package list. This was owner-approved; no dependency or lockfile changed.
4. **Admission.** Every workflow takes the per-process workflow slot, as design §3 requires. Only live adapters also need, and take, call slots.
5. **Sessions.** The runtime role cannot issue sessions; tests issue them as the operator, as production does.

## Consequences

- **Capacity.** One workflow per API process is admitted at a time. A second request gets 409 `agent_capacity_exhausted` with no state change.
- **What the clock bounds.** Elapsed waiting is bounded on the coordinator's monotonic clock. Durable-commit timing, server-side detection latency and response transport are not claimed.
- **Late workers.** They keep their call slot until the thread returns. The Claude CLI adapter's subprocess timeout ends the local child process (tested with a real test-owned subprocess). Provider-side cancellation and billing are not claimed.
- **No quality claim.** Deterministic roles prove plumbing and safety, not agent quality. Live comparisons follow protocol-v1 and are run manually (`scripts/agent_eval.py`), never by the gates.
