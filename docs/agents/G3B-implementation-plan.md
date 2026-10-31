# G3B implementation plan: the three-role backend slice

Audience: Codex (dispatches G3B after accepting G3A) and the G3B implementer.

**Recommended development settings:** Claude Opus, effort High. The task changes the investigation transaction boundaries, recovery, a migration with least-privilege grants, and security-relevant claim and tool checks. That needs careful reasoning and verification. Max effort is not needed: the design questions are settled in G3A.

## Goal (one vertical slice)

**What works end to end.** With `SENTINEL_INVESTIGATOR=three-role`, an analyst's existing `POST /v1/cases/{id}/investigations` runs the coordinator: analyst → investigator → reviewer, with read-only tools, claim verification and bounded limits. It ends in one of:
- `awaiting_approval` with one server-built intent (recommend or abstain); or
- `open` after an auditable inconclusive workflow.

The existing human approval and simulated execution path is unchanged.

**Adapters:**
- **Deterministic role adapters:** the default for this mode, tests and C2-det.
- **Claude CLI role adapter:** local-only and opt-in, reusing `ClaudeCliInvestigator`'s subscription and isolation checks.

**Out of scope:**
- **No change for other modes:** `deterministic` and `claude-cli` investigators, HTTP routes, frozen v1/v1.1 contracts, `web/`, model and data artifacts.
- **No new infrastructure:** no new providers, frameworks, BYOK or hosting.
- **No live runs as a gate:** live evaluation numbers are a separate, measured step (below).

## Base and ownership

- **Base and worktree:** the commit Codex names after accepting G3A (G3A's accepted SHA), in a new worktree `task/claude-g3b-workflow`.
- **Owned (new):**
  - `src/sentinel/contracts/agents.py` (from `docs/agents/contracts-draft/g3a_models.py`, `schema_version` set at freeze);
  - `src/sentinel/agents/{__init__,coordinator,capacity,tools,claims,adapters}.py`;
  - `src/sentinel/db/migrations/0005_agent_workflows.sql`;
  - `contracts/agents/*.schema.json` (additive export);
  - `tests/test_agent_*.py` and `tests/support/agent_cases.py` (a new support file only);
  - `scripts/agent_eval.py` (manual live comparator runner, outside pytest);
  - `docs/decisions/0007-three-role-workflow.md`.
- **Owned (narrow edits):**
  - `src/sentinel/investigators.py` (`from_environment` only);
  - `src/sentinel/service.py` (`_ingest` pin, `_claim`, `investigate` dispatch, the shared finish tail, `_recover_lost_run`, the capacity check);
  - `src/sentinel/db/roles.py` (`RUNTIME_PRIVILEGES`, `SEQUENCES`);
  - `scripts/export_contracts.py` (add the agents namespace without changing v1 output);
  - `docs/api/README.md` (one line: `agent_capacity_exhausted`);
  - `docs/agents/*` status lines.
- **Not owned:**
  - `contracts/v1/*`, `contracts/http/*`, `src/sentinel/contracts/{v1,http_v1,guards}.py`;
  - `web/`, existing `tests/support/*` files, `ml/`, `data_pipeline/`, `evals/`;
  - the gate allowlist and checker timeouts; lockfiles; central STATUS/TASK_QUEUE.

## Ordered steps (each with its failing-first test)

1. **Freeze contracts.** Move the draft models to `contracts/agents.py`; export the schemas and examples. *Test:* the export check, and the valid/invalid example suite (port `g3a_models.py --check` into pytest).
2. **Migration and grants.** Migration `0005` adds `agent_workflows`, `agent_steps` (with an append-only trigger), and `agent_runs.workflow_id`/`attempt`. Grants: `agent_workflows` SELECT/INSERT/UPDATE; `agent_steps` SELECT/INSERT plus its sequence USAGE. *Tests:*
   - the C05 grant-map test now requires the new tables;
   - the runtime role cannot UPDATE or DELETE `agent_steps`;
   - one running workflow per case.
3. **Read-only tools** (`agents/tools.py`). They take `(conn, ctx, case, T)` only, with no role-supplied identifiers. *Tests:*
   - temporal bounds: rows ingested after `T`, the alerted row itself, other currencies (30d) and other sessions are excluded;
   - profile `provisioned_at > T` gives `unavailable`;
   - every result digest is stable.
4. **Claims** (`agents/claims.py`): verification (G3A §5) and the rationale renderer (≤600 characters, money via the currency exponent). *Tests:* every `ClaimCheck` reason; the policy-consistency rules; a renderer test with no model text in the output.
5. **Coordinator and leases** (`agents/coordinator.py`, `agents/capacity.py`): the state machine and limits (G3A §3), the process-local `AgentCapacity` workflow and call slots (G3A §3.1), remaining-deadline checks before every step, and bounded `lock_timeout`/`statement_timeout`/`connect_timeout`. It writes each step in its own guarded transaction. *Tests:* D05, D07, D08, D09, D13 and D15, with deterministic or injected adapters and a controllable fake worker that is held, then released, by the test. They assert:
   - the counted limits (≤5 calls, ≤6 tools, ≤1 repeat, and no repeat after a timeout);
   - call slots released only when the worker returns, ≤2 outstanding, and a late result never written;
   - workflow slots released on every path, including exceptions;
   - denials and inconclusive codes;
   - no write after the case left `investigating`.
6. **Service integration.**
   - `three-role` in `from_environment`; ingestion pins `tool_config`; `_claim` checks it.
   - Dispatch in `investigate`. `terminate_workflow` (G3A §6.1) is the only way a workflow ends, with or without a running role. The success tail builds the intent with `agent_run_id` = the eligible basis (same workflow, latest completed investigator).
   - Recovery by workflow deadline through `terminate_workflow` (`terminal_by="recovery"`, `interrupted`, system audit actor).
   - Admission before the claim (409 `agent_capacity_exhausted`, no transaction, no state change, no disclosure).

   *Tests (real PostgreSQL):*
   - D01–D04 and D12 run through `Sentinel.investigate` and the approval and execution path;
   - D06 (owner tamper before the claim and after gathering);
   - D10 (foreign citation unsupported; cross-session 404);
   - D11 (`external_id` and note absent from every recorded role input digest source);
   - `CaseDetail` with 3–5 role runs validates against frozen v1.1;
   - D13 (zero roles: `agent_runs: []`, case open, failure audit by the coordinator principal);
   - D14 (a crash between roles, simulated by abandoning the coordinator after the analyst commits: recovery after the deadline, analyst still `completed`, system audit, 409 `investigation_recovered`);
   - completed role runs are never rewritten by any terminal path.
7. **Claude CLI role adapter** (`agents/adapters.py`): role prompts and JSON schemas pinned in role configs; `--tools ""`, an empty working directory, the subscription preflight and environment scrubbing reused from `investigators.py`; usage recorded only if the envelope reports typed counts. *Tests:* a fake runner only (command shape, scrubbed environment, failure typing, output parsing).
   - **No new pytest skip**, because the structured gate allows exactly one live skip. A live check is manual, through `scripts/agent_eval.py`.
8. **Development harness** (`tests/support/agent_cases.py`): it loads `dev-cases-v1.json`, ingests each case's `runtime` into a fresh session and feeds `faults` to injected adapters, clocks or owner connections. *Tests:* C0 and C2-det over all 15 cases, asserting the machine-checkable `evaluator` expectations and every **hard gate** in protocol-v1 §5. This proves plumbing and security, not quality.
9. **Documentation:** ADR 0007, a G3A design status update and the API error-code line.

## Acceptance checks for G3B

- **Failing first.** New tests fail on the base for the intended reasons (record them); the full suite then passes.
- **Strict gate.** The six-command strict gate passes on Windows, and the native Linux CI-equivalent gate passes, run one after the other. The gate is unchanged: the only allowed skip is still the live-Claude smoke.
- **Unchanged contracts.** `export_http_contract.py --check` passes unchanged, which proves the HTTP v1/v1.1 surface did not change. `export_contracts.py --check` covers v1 (unchanged) plus the new agents schemas.
- **Other modes unchanged.** With the default `deterministic` and with `claude-cli`, existing tests pass unmodified. The browser e2e suite (deterministic investigator) needs no change; run it once to confirm.
- **No forbidden byte changes.** None to frozen contracts, model/data/evaluation artifacts, `web/` or lockfiles.
- **Live check (optional, quota permitting, not a gate).** Run `scripts/agent_eval.py --comparators C1,C2 --cases dev` once and record the actual results under protocol-v1 §6 as *development* results. If quota is unavailable, say so; do not substitute deterministic numbers.

## Dependencies after G3B

1. **Codex** reviews G3B; there is a contract freeze of `sentinel.agents` 1.0.
2. **G3C (API + UI):** the additive v1.2 `GET /v1/cases/{id}/investigation-trace` → `TraceSummary`, its export and frozen examples, then an analyst-UI trace panel (inert text, claim-check badges, budgets). UI work starts only after the v1.2 contract is frozen.
3. **G3D (evaluation):** Codex arranges the separately authored final case set; C0, C1 and C2 are run once on it under the frozen protocol, and negative results are reported.
4. **Later, separately gated:** an Ollama adapter (after measuring laptop feasibility), a notes reader (only if a document input path is added), public BYOK and hosting.
