# G3A: three-role investigation workflow design

Audience: Codex (contract review, then integrator), the G3B implementer and later the analyst-UI implementer. This is a design and contract proposal for an application runtime feature: Sentinel's own fraud-investigation agents. It is not about how coding assistants collaborate.

- **Status:** proposal. Nothing here is implemented. Acceptance by Codex freezes these interfaces for G3B.
- **Source base:** accepted H01 `f091a34c2ed3f6636625b3141be88d86cd5307dd`, which includes the N2–N7 release. Line references below are to that commit.
- **Companion files:**
  - [contracts-draft/](contracts-draft/README.md): typed draft schemas, valid and invalid examples, compatibility notes;
  - [protocol-v1](../evals/agents/protocol-v1.md) and the [development case catalog](../evals/agents/dev-cases-v1.md): evaluation;
  - [G3B implementation plan](G3B-implementation-plan.md): the next task.

## 1. What exists today (and its real limits)

| Area | Current behaviour (f091a34) | Limit for G3 |
| --- | --- | --- |
| Investigator interface | `Investigator` protocol (`src/sentinel/investigators.py:40`): `config`, `principal_id`, `timeout_seconds`, `investigate(view) -> InvestigationFinding` | One call, one role, one output. There is no tool use, no follow-up and no claim structure |
| What an agent sees | `InvestigationView` (`investigators.py:31`): `facts` (the case's EvidenceItem facts: only `amount_minor` and `transaction_count_1h`, built in `service.py:245-250`), currency, `large_amount`, the alert score and the threshold | No history beyond the 1-hour count, no account profile and no model inputs. `Fact.name` already allows `account_age_days` (`contracts/v1.py:218`), but nothing produces it |
| Output | `InvestigationFinding` (`v1.py:363`): an enumerated operation and reason, plus a 600-character rationale | The rationale is free text from the model. Nothing checks its claims; the UI renders it as inert text |
| Live adapter | `ClaudeCliInvestigator` (`investigators.py:116`): subscription-only, no tools/MCP/settings, empty working directory, JSON schema output, typed failures | It produces one finding per call and does not read usage |
| Lifecycle | `investigate` → `begin_investigation` / `_claim` (open→investigating, one `agent_runs` row) → `_run_investigator` (thread plus deadline) → `finish_investigation` (completed→awaiting_approval and a server-built intent, or `_fail_run`→open) (`service.py:517-658`) | One run per attempt. `_recover_lost_run` (`service.py:660`) relies on that one running run's budget |
| Contracts already present but unused | `AgentRun.role` allows `evidence_analyst` and `reviewer`. Status allows `inconclusive` and `cancelled`. `failure_code` allows `budget_exhausted`. `RunBudget` has `max_tool_calls` and `max_delegations`. `Case.state` allows `inconclusive` (`v1.py:279`, `294-322`), and so does the migration CHECK | No transition reaches the `inconclusive` case state, and nothing reopens it |
| Pins | `CasePins.agent_config` and `tool_config` (`v1.py:264`) are set at ingestion from `self.investigator.config` and `scoring.TOOL_PROFILE` (`no-tools` n1) (`service.py:251-256`). `_claim` refuses `stale_agent_config` (`service.py:579`) | `tool_config` is never checked. The investigator choice is operator-global |
| Persistence | `agent_runs` holds one running row per case, by unique index (0001). `action_intents.agent_run_id` is NOT NULL. `audit_events` is append-only | There is no role trace, tool record or workflow deadline |
| HTTP | v1.1: `CaseDetail.agent_runs[*].finding` is typed `InvestigationFinding \| None` (`http_v1.py`, `AgentRunView`) | A role output that is not an InvestigationFinding cannot appear there |

Conclusion: the frozen v1 contracts already anticipate roles and inconclusive runs. What is missing is a coordinator, scoped read tools, claim verification and durable per-role records. This design adds exactly those and leaves the HTTP surface unchanged for G3B (see §8).

## 2. Roles and the coordinator

**Operator choice.** The workflow is selected the way the live investigator is today, with `SENTINEL_INVESTIGATOR=three-role`. A role adapter is chosen separately, `deterministic` (default) or `claude-cli`, and `claude-cli` stays local-only. The default remains `deterministic` (the single deterministic investigator, `i1`), so its HTTP and approval path is unchanged. Because the agent and tool configs are pinned on each case at ingestion, switching modes makes older open cases fail with `stale_agent_config`; configurations are never mixed.

**Roles.**

| Role | Sees | Can produce | Cannot |
| --- | --- | --- | --- |
| Evidence analyst | Server-rendered decision-time facts from the baseline tools | Claims about facts, a list of missing facts, ≤2 follow-up tool requests | Recommend an operation; see notes from other roles |
| Investigator | The same facts, follow-up results, the analyst's *checked* claims and missing list (structured only) | One operation and reason, ≥1 claim, ≤1 follow-up tool request (one round) | Choose action parameters, amounts or IDs |
| Reviewer | The investigator's output and the server's claim-check results | `accept`, `challenge` (with indices and reasons) or `abstain` | Approve anything. `accept` is not authorization |

**The coordinator** is server code, not a model. It owns:
- role identity (each role's `principal_id` = uuid5 of its config, as `_principal` does today);
- state transitions, tool execution, budgets and deadlines, and claim verification;
- the final disposition, and building any action intent.

**Agents never choose** tenant, session, actor, case or evidence scope; capabilities; action parameters; approval; or execution.

## 3. State machine

```
open ──claim──▶ investigating ─┬─ recommend ─▶ awaiting_approval (intent: hold|escalate) ─▶ human
 ▲  (rev r)      (rev r+1)     ├─ abstain   ─▶ awaiting_approval (intent: escalate/insufficient_evidence) ─▶ human
 │                             └─ inconclusive ─▶ open (rev r+2, no intent; retry allowed)
 └─────────────────────────────── lapsed approval / reject (existing rules) ◀─┘
```

**Coordinator states** (inside one `investigating` revision; each change is one `transition` step):

| # | State | Actor | Exits |
| --- | --- | --- | --- |
| 1 | `claimed` | server | → `gathering` |
| 2 | `gathering` | server runs the baseline tools: `case_evidence`, `scoring_outcome`, `account_history(24h)` | → `analyst` |
| 3 | `analyst` | analyst invocation 1 | valid: `analyst_tools` if it requested tools, else `investigator`. Failure: a repeat (if budget allows), else inconclusive |
| 4 | `analyst_tools` | server: ≤2 validated requests; excess requests are *denied* and recorded | → `investigator` |
| 5 | `investigator` | investigator invocation 1 or 2 | output with a tool request (first invocation only): `investigator_tools`. Otherwise `verifying`. Failure: a repeat, else inconclusive |
| 6 | `investigator_tools` | server: ≤1 request | → `investigator` (this consumes the one revision) |
| 7 | `verifying` | server: claim and policy checks (§5) | → `reviewer` |
| 8 | `reviewer` | reviewer invocation 1 or 2 | `accept` with all adopted claims supported and policy consistent: **recommend**. `accept` while the server found problems, or `challenge`: back to `investigator` if a revision remains, else **abstain**. `abstain`: **abstain** |
| 9 | `done` | server | finish (§6) |

**Hard limits** (`WorkflowLimits` in the draft; each is pinned through the workflow config):

| Limit | Value | Reason |
| --- | --- | --- |
| Role invocations | ≤5 (analyst 1, investigator ≤2, reviewer ≤2) | Covers one revision cycle. It costs at most five subscription calls per case |
| Investigator revisions | ≤1, shared between a tool follow-up and a reviewer challenge | Prevents ping-pong between roles; a second disagreement becomes abstain |
| Follow-up tool calls | ≤3 (analyst ≤2, investigator ≤1). The baseline adds 3, so ≤6 tool executions | Tools are cheap SQL aggregates. The limit bounds latency and prompt size |
| Repeats | ≤1 per workflow, for a `timeout`, `provider_unavailable` or `invalid_output` role call | Gives one bounded retry for a flaky provider. Billing is not exactly once: an abandoned call may still have consumed quota |
| Transitions | ≤12 (derivable from the above; enforced as an invariant) | A defensive bound |
| Role timeout | 45 s per live call (5 s for deterministic). `RunBudget.timeout_seconds` allows at most 60 | The live investigator today uses 60 s for one call, and roles have smaller prompts |
| Workflow deadline | 150 s from the claim. No role starts unless the remaining time ≥ role timeout + 2 s grace; otherwise **inconclusive / budget_exhausted** | Keeps the synchronous HTTP request bounded. The UI client sets no fetch timeout (`web/src/api/client.ts`) |
| Concurrency | ≤1 live workflow per API process (non-blocking semaphore taken *before* the claim; otherwise 409 `agent_capacity_exhausted`, with no state change). Deterministic adapters are not limited beyond the existing one running run per case | Protects the owner's subscription quota and the laptop |
| Delegation | 0. Roles never invoke roles; only the coordinator sequences | No unbounded delegation loop |
| Tokens / money | Recorded only if the adapter reports usage (`Usage.source = adapter_reported`), else `unknown`. There is no monetary cap | The CLI adapter does not meter cost today; a cap would be fiction |

**When a case has an intent.** Exactly when the disposition is `recommend` or `abstain`, and only after the server re-verifies the evidence snapshot (`require_evidence_snapshot`, `contracts/guards.py:46`) at finish.

**When it cannot:**
- after an `inconclusive` disposition;
- when the snapshot changed;
- when the workflow was superseded (case no longer `investigating` at the claimed revision);
- when recovery already reopened the case.

**The `inconclusive` case state stays unused in G3B.** Entering it would strand the case: no route reopens it, and `investigate` requires `open`. An inconclusive *workflow* therefore reopens the case to `open`, exactly as `_fail_run` does today. The `AgentRun` that ended it gets status `inconclusive` (or `failed` with a code), and the audit records `investigation_completed`/`failure`. Using the case state needs a later, explicitly versioned reopen route.

## 4. Read-only tool registry (`agent-read-tools` t1)

**Rules for every tool:**
- It is server code with no role-supplied identifiers. Scope comes from the `TrustedContext` of the human who started the investigation. The case comes from the coordinator. The account comes from the case's stored transaction.
- It runs on the API's existing least-privilege runtime connection (`src/sentinel/db/roles.py`, `RUNTIME_PRIVILEGES`). It never uses an owner/cluster URL, a browser inspector, SQL text, the shell, the filesystem, the web or MCP.
- Decision time `T` = `alert.created_at`. Only rows with `ingested_at <= T` (and profile or disclosure availability ≤ `T`) count. Results are therefore reproducible: the runtime role cannot UPDATE or DELETE `transactions`.
- Simulator ground truth, scenario names, benchmark gold labels and future disclosures are never readable. Runtime tables do not contain the first three, and the fourth is excluded by `T`.
- Each result is a `ToolResult` with a content digest, stored as a step.

| Tool | Arguments (all a role may send) | Values | Source |
| --- | --- | --- | --- |
| `case_evidence` | none | `amount_minor`, `transaction_count_1h`, plus `evidence_ids` | The case's EvidenceItems (snapshot-verified) |
| `scoring_outcome` | none | `large_amount_rule_hit` (`scoring.is_large_amount` on the stored transaction). In model mode only, `prior_known_fraud` from `ScoringOutcome.inputs` | `scoring_outcomes` row |
| `account_history` | `window`: `24h` \| `7d` \| `30d` | 24h: `history_count_24h`. 7d: `history_count_7d`. 30d: `history_median_amount_minor_30d` and `history_max_amount_minor_30d`, same currency as the alerted transaction, excluding it | `transactions`, same scope and account, `occurred_at` in `[t − window, t)`, `ingested_at ≤ T` |
| `account_profile` | none | `account_age_days` = whole days from `opened_at` to `T`. `unavailable` if there is no profile or `provisioned_at > T`, since a later upsert cannot prove the decision-time value | `account_profiles` |

**What the scoring tool does not return.** It never returns the numeric score or threshold as claimable facts. The fraud model's score is the scorer's output, and roles cite rule hits and recorded facts instead of restating a risk number. The score is still shown to the analyst through the existing `scoring` field.

**Denials are records, not crashes.** An excess or unknown request yields `ToolResult(status="denied", denial=...)`; schema rejection happens before any execution. A forged argument (any ID, a path, SQL, an unknown window) makes the *role output* invalid, because tool requests are `extra="forbid"`. It counts as an `invalid_output` failure (repeat budget) and as an unauthorized request in evaluation.

## 5. Claims and verification

Each claim is structured (`Claim` in the draft): a fact claim `fact relation value`, citing an evidence ID or tool-result ID, or a `missing` claim. The server checks each one deterministically:

| Claim | Supported when | Otherwise |
| --- | --- | --- |
| fact, cites evidence | The ID is in `case.evidence_ids`, the item carries that fact, and its stored integer satisfies the relation | `citation_not_in_scope`, `fact_not_in_cited_record` or `value_mismatch` |
| fact, cites a tool result | The ID is an `ok` result recorded *in this workflow* that holds the fact, and the value satisfies the relation | same codes |
| missing | No `ok` result or evidence in this workflow provides that fact | `fact_was_available` |

**What a valid ID does and does not prove.** It proves that the record exists in scope, not that a sentence about it is true. That is why claims are typed relations over stored values, and why roles cannot introduce new numeric facts.

**Policy consistency checks** (server-side, independent of the reviewer):
- `velocity_pattern` needs a supported claim on `transaction_count_1h` or `history_count_24h`/`7d`.
- `unusual_amount` needs a supported claim on `amount_minor`, `large_amount_rule_hit` or a 30-day amount statistic.
- `insufficient_evidence` permits `escalate` only.
- `simulated_hold` needs reason `velocity_pattern` or `unusual_amount`, every adopted claim supported, and reviewer `accept`.

**Rendered rationale.** The adopted investigator run's `InvestigationFinding.rationale` (≤600 characters) is **rendered by the server** from the supported claims and the stored values. Money is formatted through the currency exponent. For example: "simulated_hold (velocity_pattern). Supported: amount 2,500.00 USD [evidence …e01]; 2 transactions in the prior hour [evidence …e02]; large-amount rule hit; 30-day maximum same-currency payment 98.00 USD. Reviewer accepted."

**Free-text notes.** Role `note`s (≤400 characters) are untrusted and display-only. They are never forwarded to another role, never rendered into the rationale and never counted as supported. Their quality is judged only by the human rubric in the protocol. Another model's agreement is not ground truth.

## 6. Integration points and persistence

**Proposed migration `0005_agent_workflows`.** The runtime grants must be added to `RUNTIME_PRIVILEGES`; the C05 guard test requires that.

| Object | Columns | Runtime grants |
| --- | --- | --- |
| `agent_workflows` | `id`, scope, `case_id` (FK), `case_revision`, `status` (`running`/`completed`/`inconclusive`), `started_at`, `deadline_at`, `finished_at`, `body jsonb` (`WorkflowRecord`). Partial unique index: one `running` row per case | SELECT, INSERT, UPDATE |
| `agent_steps` | `seq bigserial`, `id`, scope, `workflow_id` (FK), `case_id`, `body jsonb` (`StepRecord`), `payload jsonb` (a validated `RoleOutput` or `ToolResult`). Append-only trigger like `audit_events` | SELECT, INSERT |
| `agent_runs` additions | `workflow_id uuid NULL` (FK), `attempt smallint NULL` | unchanged |

**Unchanged:**
- `AgentRun` bodies keep the frozen v1 contract.
- One `agent_runs` row per role invocation (`role`, the role `config`, its own `RunBudget`), so the existing unique index (one running per case) still holds: roles run sequentially.
- `agent_runs.finding` is set **only** for the adopted investigator run (the rendered `InvestigationFinding`). It stays NULL for analyst, reviewer and superseded investigator runs, so v1.1 `CaseDetail` stays valid.

**Exact integration (G3B):**

| Today | Change |
| --- | --- |
| `investigators.from_environment` (`investigators.py:202`) | Add `three-role`. It returns a `Workflow` object exposing `config` (the composite `ArtifactRef`), `tool_profile`, `principal_id` (coordinator principal) and `timeout_seconds` (= deadline) |
| `Sentinel._ingest` pins (`service.py:251-256`) | `tool_config` = the selected workflow's tool profile when a workflow is configured (else `scoring.TOOL_PROFILE`) |
| `Sentinel._claim` (`service.py:570`) | Also check `case.pins.tool_config`, using the same `stale_agent_config` code. For a workflow: insert the `agent_workflows` row (deadline = now + 150 s) instead of one investigator run |
| `Sentinel.investigate` (`service.py:517`) | If a workflow is configured, call `coordinator.run(ctx, workflow, view)`. Each step commits in its own short transaction, guarded by "case is `investigating` at the claimed revision and the workflow is `running`" (compare-and-set, like `_transition`). Otherwise the existing path is unchanged |
| `_run_investigator` (`service.py:524`) | Reused per role invocation (thread plus `role_timeout + grace`). A late result is never written: only the coordinator writes, after `future.result` returns in time |
| `finish_investigation` (`service.py:612`) | Shared tail. `recommend`/`abstain` build the intent exactly as today (`HoldParameters`/`EscalateParameters` from the stored transaction), with `agent_run_id` = the disposition's `basis_run_id`. `inconclusive` uses the `_fail_run` path, with `AgentRun.status="inconclusive"` or `failed`+code |
| `_recover_lost_run` (`service.py:660`) | Also recover a `running` workflow when `deadline_at + RECOVERY_GRACE < now`: fail its running role run (`timeout`), mark the workflow `inconclusive`/`timeout` and reopen. This makes a workflow interrupted between roles (no running run) recoverable |

**Resumption.** G3B never resumes a workflow mid-way. After a crash, recovery reopens the case, and a new `investigate` starts a fresh workflow with a new ID, re-running all roles. Every earlier step and run stays recorded.

**Where a repeat is safe.** A single role call whose completion is uncertain (`timeout`, `provider_unavailable`) may be repeated once inside the same workflow. This is safe because role calls have no side effects. The abandoned thread cannot be force-stopped and may still finish and consume quota; its result is dropped.

**What is untouched.** `audit_events` gets no new event types: `investigation_started` and `investigation_completed` with success/failure, as today. Per-role detail lives in `agent_steps`. Approval, expiry, rejection, stale revision and idempotent execution code is untouched.

## 7. Worked fraud case (D01)

**The case.** Rule mode, a USD debit of 250,000 minor units (2,500.00 USD). The account had 2 earlier transactions in the prior hour and smaller payments over 30 days. The rule score is 0.6 (large) + 0.4 (2 × 0.2) = 1.0, against threshold 0.5, so an alert is raised and the case opens at revision 1.

**The workflow:**

1. **Claim** at expected revision 1. The case moves to `investigating` (revision 2), and the workflow row is created with deadline +150 s.
2. **Gathering:**
   - `case_evidence` returns E1 `amount_minor=250000` and E2 `transaction_count_1h=2`;
   - `scoring_outcome` returns `large_amount_rule_hit=true`;
   - `account_history(24h)` returns `history_count_24h=4`.
3. **Analyst:** claims about E1, E2 and the rule hit, `missing=[account_age_days]` and a request for `account_history(30d)`. The server checks the 3 claims: all supported. The missing claim is supported too (no profile tool was run), and it is advisory.
4. **Analyst tools:** `account_history(30d)` returns median 4,200 and max 9,800.
5. **Investigator:** `simulated_hold` with `velocity_pattern` and 4 claims. All are supported, and the policy is consistent (a velocity claim on E2).
6. **Reviewer:** `accept`.
7. **Disposition** `recommend`. `finish_investigation` re-verifies the snapshot, and the case moves to `awaiting_approval` (revision 3). Intent `HoldParameters(transaction_id, amount=2,500.00 USD)` is bound to revision 3 and the snapshot digest.
8. **The human** approves (TTL 300 s) and executes with an idempotency key. The simulated action succeeds, and the case closes at revision 4.

Exact payloads are in [contracts-draft/examples/valid](contracts-draft/examples/valid/): `AnalystOutput.d01`, `InvestigatorOutput.d01_hold`, `WorkflowRecord.d01_completed` and `TraceSummary.d01`.

**Variants:**
- *Reviewer challenge with no revision left:* abstain. The intent is `escalate`/`insufficient_evidence`, at revision 3.
- *Investigator timeout twice:* inconclusive/timeout. The case reopens at revision 3 with no intent; the analyst can retry, or switch to the deterministic investigator through operator configuration (which makes the old case `stale_agent_config`).

## 8. Errors, compatibility and versions

**Errors.** The existing codes keep their meaning:
- `stale_case_revision`, `investigation_in_progress`, `investigation_recovered`, `approval_expired`, `case_not_investigable`, `stale_agent_config`, evidence-snapshot violations (409);
- `permission_denied` (403);
- `not_found` (404) for a case in another session, unchanged.

There is one new code: **409 `agent_capacity_exhausted`** (live adapter busy; no state change). It is additive under the existing `ErrorResponse.error: str`. The docs/api error list needs one line.

**Outcomes as observed through v1.1 (no route change).** `POST /v1/cases/{id}/investigations` returns 200 `CaseDetail` with:
- `state=awaiting_approval`, three to five `agent_runs` (roles), one with a `finding`, and one current intent (recommend or abstain); or
- `state=open` with the last run `inconclusive`/`failed` (inconclusive).

**HTTP revision.** None is needed for G3B. A **v1.2 additive** read route, `GET /v1/cases/{id}/investigation-trace` → `TraceSummary`, is drafted for the analyst UI (G3C). It needs its own contract freeze, an export update and UI work. Legacy v1 and v1.1 bytes stay frozen.

**Versions.**

| Item | Version |
| --- | --- |
| Workflow artifact | `three-role-workflow` w1 |
| Role configs | `analyst-*` a1, `investigator-*` i2, `reviewer-*` r1, each per adapter |
| Tool profile | `agent-read-tools` t1 |
| Claim schema | `g3a-draft-1` |
| Migration | 0005 |
| Action policy | `p1`, unchanged |

## 9. Security boundaries (summary)

- **Identity.** Role identity and scope are server-assigned. Tool arguments contain no identifiers. Claims cite IDs that are verified against the case scope.
- **Untrusted text.** Role notes and `external_id` never reach another role. `external_id` is a `Name`-pattern string that could hold instruction-like tokens, and roles do not need it. Role inputs are server-rendered integers, booleans, enums and UUIDs.
- **Outputs.** Every role output is validated with `extra="forbid"` before any use. Invalid output is a typed failure, and an excess tool request is a denial. Neither raises or crashes the workflow.
- **Rendering.** The UI keeps rendering every model-originated string as inert text, as today (`web/src/ui/CaseFile.tsx`).
- **What is not stored.** No raw prompts with credentials, no provider auth output (the existing CLI rule: stdout is never logged) and no chain-of-thought dumps. Steps store validated outputs and digests.
- **Deferred.** There is no notes or document input path today. An isolated untrusted-notes reader is not designed or claimed here.

## 10. Assumptions and open decisions

- **Claude CLI per role.** Each role's adapter uses the same subscription and isolation checks as `ClaudeCliInvestigator`, with a role-specific system prompt and JSON schema. Whether the CLI envelope reports usage is verified in G3B, not assumed.
- **Model alias drift.** The alias (`sonnet`) still resolves over time. Pins record the alias, as ADR 0003 says.
- **The deterministic role adapters** are a plumbing control and a fixture. They are not evidence of multi-agent quality (see the protocol).
- **Decision for Codex:** accept `agent_capacity_exhausted`, or reuse `investigation_in_progress`. The recommendation is the new code, because the case is not busy.
