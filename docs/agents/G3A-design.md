# G3A: three-role investigation workflow design

> **G3B accepted and integrated (e23a7cd / a7c71f5):** the backend slice is implemented in `sentinel.agents`, migration 0005 and `sentinel.contracts.agents`. Implementation decisions beyond this text (COMMIT watchdog, `agent_runs.seq`, packaging entry, admission) are listed in [ADR 0007](../decisions/0007-three-role-workflow.md).

Audience: Codex (contract review, then integrator), the G3B implementer and later the analyst-UI implementer. This is a design and contract proposal for an application runtime feature: Sentinel's own fraud-investigation agents. It is not about how coding assistants collaborate.

- **Status:** accepted design at candidate `43d9e8a5845630deeedfe52fc39b1a6f8ccc1b85` (October 31); runtime accepted separately at e23a7cd and integrated at a7c71f5. See [Codex acceptance](../reviews/G3A-43d9e8a.md). G3B is the separate implementation gate.
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
| 3 | `analyst` | analyst invocation 1 | valid: `analyst_tools` if it requested tools, else `investigator`. Resolved failure (`provider_unavailable`/`invalid_output`): one repeat if a call slot and time remain. Timeout or no repeat left: inconclusive |
| 4 | `analyst_tools` | server: ≤2 validated requests; excess requests are *denied* and recorded | → `investigator` |
| 5 | `investigator` | investigator invocation 1 or 2 | output with a tool request (first invocation only): `investigator_tools`. Otherwise `verifying`. Failure: as for the analyst |
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
| Repeats | ≤1 per workflow, **only for a resolved failure** (`provider_unavailable` or `invalid_output`, where the worker returned). **Never after a `timeout`**, whose worker is still unresolved (§3.1) | Gives one bounded retry for a flaky provider without overlapping calls. Billing is not exactly once: an abandoned call may still have consumed quota |
| Transitions | ≤12 (derivable from the above; enforced as an invariant) | A defensive bound |
| Role timeout | 45 s per live call (5 s for deterministic). `RunBudget.timeout_seconds` allows at most 60 | The live investigator today uses 60 s for one call, and roles have smaller prompts |
| Workflow deadline | 150 s from the claim. It covers gathering, tools, coordinator work and the terminal write, not only role calls (§3.1) | Keeps the synchronous HTTP request bounded. The UI client sets no fetch timeout (`web/src/api/client.ts`). It is a provisional default, not a measured guarantee (review decision 2) |
| Concurrency | ≤1 admitted workflow and ≤2 outstanding provider calls per API process, late workers included (§3.1). A refused admission returns 409 `agent_capacity_exhausted` with no state change and nothing about other cases. Deterministic adapters take no call slots: no provider, no late worker | Protects the owner's subscription quota and the laptop, including against accumulating timed-out workers |
| Delegation | 0. Roles never invoke roles; only the coordinator sequences | No unbounded delegation loop |
| Tokens / money | Recorded only if the adapter reports usage (`Usage.source = adapter_reported`), else `unknown`. There is no monetary cap | The CLI adapter does not meter cost today; a cap would be fiction |

**When a case has an intent.** Exactly when the disposition is `recommend` or `abstain`, and only after the server re-verifies the evidence snapshot (`require_evidence_snapshot`, `contracts/guards.py:46`) at finish.

**When it cannot:**
- after an `inconclusive` disposition;
- when the snapshot changed;
- when the workflow was superseded (case no longer `investigating` at the claimed revision);
- when recovery already reopened the case.

**The `inconclusive` case state stays unused in G3B** (review decision 3). Entering it would strand the case: no route reopens it, and `investigate` requires `open`. An inconclusive *workflow* reopens the case to `open` with no intent, through the workflow-level terminal transaction in §6.1. That transaction does not require a running role. Using the case state needs a later, explicitly versioned reopen route.

### 3.1 Admission, call leases and the full deadline (R31)

**Two separate quantities:**
- The **workflow elapsed budget** (150 s) governs coordinator waiting through the terminal attempt, with the reserve inside it (section 3.2). Request latency is measured separately; response delivery and commit durability are not guaranteed.
- The **worker lifetime** bounds how long a provider call's thread can keep running after the coordinator stopped waiting for it.

The existing `_run_investigator` helper (`service.py:524-546`) returns on timeout and calls `shutdown(wait=False)`, and the thread cannot be killed. Capacity must therefore follow the *thread*, not the request.

**What bounds the worker lifetime.** The Claude CLI adapter runs `subprocess.run(..., timeout=...)`. Python kills the CLI child process when that timeout expires (the auth preflight has its own 15 s bound). A worker therefore returns at most about role timeout + 15 s + scheduling after it started. That ends the local process. It does **not** cancel provider-side work or billing, and nothing here claims it does.

**Leases (process-local, in memory).** One `AgentCapacity` object per API process holds two counters, each with a fixed maximum from the pinned limits.

| Lease | Taken | Owner | Released | Crash |
| --- | --- | --- | --- | --- |
| **Workflow slot** (max `max_live_workflows_per_process` = 1) | Non-blocking, by `investigate` **before** the claim transaction. It also needs ≥1 free call slot. If either is unavailable: 409 `agent_capacity_exhausted`, no transaction, no case change | The request's coordinator | In a `finally` after the terminal transaction commits or fails, on every path: success, inconclusive, superseded, unexpected exception | Lost with the process; nothing persists it |
| **Call slot** (max `max_outstanding_calls_per_process` = 2) | Non-blocking, immediately before a live role call is submitted to its worker thread. If none is free, the call is not made and the workflow ends inconclusive `call_capacity_exhausted` | The **worker thread's future**, not the request | By a done-callback when the worker thread **actually returns** (result, typed error or late completion), never when the coordinator stops waiting | Lost with the process; the worker threads are gone too |

**Consequences of these rules:**
- **Outstanding calls ≤ 2 at all times**, late workers included. Within one workflow at most one call is ever outstanding: roles are sequential, and a timeout ends the workflow because a timed-out call is never repeated.
- **A late result is never written.** Only the coordinator writes, and only after `future.result` returned in time. The done-callback releases the slot and emits one structured log event (`agent_worker_returned`: workflow ID, role, attempt, seconds after the deadline), with no database write and no output content.
- **A repeat needs a resolved failure,** a free call slot and the full role timeout + grace + terminal reserve remaining.

**Full-deadline coverage.** Every coordinator step, including gathering, tools, claim checks and the terminal write, takes its waiting budget from the one absolute deadline defined in §3.2. A lock or statement timeout during a working step is treated like exhaustion: inconclusive `budget_exhausted`. An unexpected exception becomes inconclusive `coordinator_error`. If no safe terminal write is possible, or its commit outcome is uncertain, the workflow stays durably `running` for recovery (§3.2, §6.1).

**Example A: timeout, late completion, another admission** (live adapter, limits as pinned):

| t (s) | Event | Leases (workflow / calls) | Records |
| --- | --- | --- | --- |
| 0 | Case X `investigate`: workflow slot taken, call slot free; claim | 1 / 0 | case X `investigating` r2; workflow W1 `running` |
| 1–2 | Gathering: 3 tools | 1 / 0 | 3 `tool_executed` steps |
| 2 | Analyst call submitted; call slot taken | 1 / 1 | analyst run `running` |
| 49 | Coordinator's wait expires (45 + 2). The worker has not returned | 1 / 1 | analyst run `failed`/`timeout`; step `role_failed` with `worker_unresolved=true`. No repeat (timeout) |
| 49 | Terminal transaction: W1 `inconclusive`/`timeout`, case X → `open` r3, audit failure. Workflow slot released | 0 / 1 | HTTP 200 `CaseDetail`, case open, no intent |
| 50 | Case Y `investigate`: workflow slot free, one call slot free, so admitted | 1 / 1 | W2 `running` |
| 52 | Y's analyst call submitted | 1 / 2 | |
| 55 | X's late worker returns (CLI killed by its own subprocess timeout at about 45 s, plus process exit). Its result is **discarded**, and its call slot is released | 1 / 1 | log `agent_worker_returned`; no database write |
| 56 | Case Z `investigate` while W2 runs: workflow slot busy | 1 / 1 | **409 `agent_capacity_exhausted`**, case Z unchanged, no record |
| 80 | Y's analyst returns in time; W2 continues | 1 / 0 → 1 per call | |

*Variant:* if X's late worker were still running at t = 80 and Y's investigator also timed out, two workers would hold both call slots. Every admission would then be refused until one returns, because outstanding calls never exceed 2.

**Example B: deadline exhaustion during gathering** (zero roles):

| t (s) | Event | Records |
| --- | --- | --- |
| 0 | Claim (case r1 → r2), W `running`, deadline +150 | `investigation_started` audit (human actor) |
| 0.1–0.3 | `case_evidence` and `scoring_outcome` succeed | 2 `tool_executed` steps |
| 0.3 | `account_history` waits on a lock held by an owner-side maintenance session | |
| 5.3 | `lock_timeout` (`db_wait_seconds` = 5) fires. Tool steps are never retried, and a lock or statement timeout counts as exhaustion | |
| 5.4 | Terminal transaction (well inside the deadline): W `inconclusive`/`budget_exhausted`, `role_invocations=0`, `tool_calls=2`, case → `open` r3, audit failure (coordinator principal) | `WorkflowRecord.zero_role_budget_exhausted` (example) |

The same terminal path runs when the deadline itself is reached first, for example when earlier roles were slow and the remaining time cannot cover the next step.

### 3.2 Deadline and transaction budgets (R31 correction)

Revision 2 derived every lock and statement timeout as min(`db_wait_seconds`, remaining − `terminal_reserve`), and ran the terminal write inside the reserve. That fails at and inside the reserve: with 6/5/4/0 s remaining it yields 1/0/−1/−5 s. PostgreSQL treats `statement_timeout = 0` and `lock_timeout = 0` as **no timeout** ([PostgreSQL 16](https://www.postgresql.org/docs/16/runtime-config-client.html#GUC-STATEMENT-TIMEOUT)), so the bound disabled itself exactly when it mattered. This section replaces that rule. [`deadline_budget.py`](deadline_budget.py) is its executable specification.

**One absolute deadline, two phases.**
- **The deadline.** The coordinator reads a monotonic clock `t0` *before* the claim transaction. Its deadline is `t0 + 150 000 ms`. The persisted wall-clock `deadline_at = started_at + 150 s` (`started_at` is read inside the claim, later) is therefore never earlier than the monotonic deadline. Recovery acts only after `deadline_at + RECOVERY_GRACE` (30 s), so a live coordinator and recovery never act at the same time, even with small clock skew.
- **Working phase** (claim, gathering, roles, tools, claim checks): an operation's budget is measured to `work_end = deadline − terminal_reserve` (5 000 ms before the deadline).
- **Terminal phase** (only the terminal transaction of §6.1): measured to the deadline itself. It **does not subtract its own reserve**, so up to 5 000 ms are genuinely available for it.

**Budget rule (units and rounding).**
- **Computation.** Every budget is an integer number of milliseconds, computed as `min(cap, floor(end − now))`. It is never rounded up.
- **Refusal instead of zero.** A budget below its minimum is a **refusal** (the operation is not started), never 0 or a negative value.

| Operation | Phase | Cap | Minimum to start |
| --- | --- | --- | --- |
| Role call (+ grace) | working | 47 000 ms | 47 000 ms (the full call must fit) |
| Tool or claims transaction | working | `db_wait_seconds` 5 000 ms per transaction; each tool statement ≤ `tool_statement_timeout_ms` 2 000 ms | 100 ms |
| Terminal transaction | terminal | 5 000 ms | 1 000 ms to begin; 100 ms per statement and before COMMIT |

**One transaction, one combined budget.** A transaction gets a total budget `B` (above) and an end time `now + B`. Before **every** statement, and before `COMMIT`, it recomputes `remaining = floor(min(tx_end, phase_end) − now)`:
- if `remaining ≥ 100 ms`, it sets `SET LOCAL statement_timeout` and `lock_timeout` to `remaining` and sends the statement;
- otherwise it rolls back.

Sequential lock waits and statements therefore consume one budget. For example, three 1.5 s statements from 5 s get 5 000, 3 500 and 2 000 ms, and COMMIT gets 500 ms. The combined duration cannot exceed `B`, apart from the time the server needs to notice a timeout, which the specification does not claim to measure. `statement_timeout` already includes a statement's lock waits; `lock_timeout` is set to the same value, so neither can exceed the remaining budget.

**Connections.**
- **One connection per workflow.** The coordinator opens a single-host connection during the claim and keeps it for every later step, so the terminal phase needs no new connection.
- **libpq granularity.** `connect_timeout` is whole seconds, `0` means wait forever, `1` is treated as 2, and the limit applies **per host tried** ([libpq](https://www.postgresql.org/docs/16/libpq-connect.html#LIBPQ-CONNECT-CONNECT-TIMEOUT)). A new connection is opened only with `connect_timeout = min(5, floor(available_ms / 1000))` and only if that is ≥ 2. A multi-host connection string is refused for the workflow connection.
- **Lost connection.** A connection lost in the working phase may be replaced within these rules. In the terminal phase, a replacement uses `connect_timeout = floor((available_ms − 1000) / 1000)`, capped at 5 and only if ≥ 2, so its worst case still leaves the 1 000 ms terminal start budget. That needs ≥ 3 s left (4 s left allows 3 s; below 3 s it is refused), so a connection lost late in the reserve means **no safe terminal write**.

**Terminal outcomes.** These are reported honestly; none is promoted to success.

| Terminal attempt | Durable state | HTTP result |
| --- | --- | --- |
| Committed. The `CaseDetail` was read *inside* the terminal transaction, before COMMIT, so no post-commit query is needed | Workflow terminal; case `open` or `awaiting_approval` | 200 `CaseDetail` |
| Refused (less than 1 000 ms left, or no usable connection), or rolled back because a budget ran out or a statement timed out | **Unchanged: workflow `running`, case `investigating`**, known not written | 409 `investigation_in_progress`. The case really is still investigating; lazy recovery closes it after `deadline_at + 30 s` |
| COMMIT sent, but no definitive reply (connection lost, timeout during commit) | **Unknown:** either terminal, or still `running` | 409 `investigation_outcome_unknown` (new, additive). The client re-reads; if it is still `running`, recovery closes it |
| Guard failed (case or workflow already moved on) | Unchanged by this transaction | 409 `investigation_superseded` (existing) |

**In every row, the workflow slot is released** in the request's `finally`. **Call slots are unaffected:** each stays held until its worker thread returns, whether or not the terminal write succeeded (§3.1).

**What this does and does not bound.** It bounds *elapsed waiting* on the coordinator's monotonic clock. It is not a proof that a commit becomes durable within the deadline, that the server notices a timeout instantly, or that the HTTP response leaves the process by then. The protocol therefore measures the bounded quantity (workflow elapsed) and reports request wall time separately ([protocol-v1 §3](../evals/agents/protocol-v1.md#3-metrics)).

**The check.** `uv run --locked python docs/agents/deadline_budget.py` verifies:
- the old formula's 1/0/−1/−5 s at 6/5/4/0 s remaining;
- working refusals at and inside the reserve, and a **valid** terminal budget inside it (5 000 ms at exactly 5 s, 4 000 ms at 4 s, 100 ms at 0.1 s), so an always-refuse helper fails;
- sub-second floors (99 ms gives a refusal, 100 ms passes), and that zero or expired time is never 0 or negative;
- libpq rules (2.5 s gives 2, 1.9 s and 0.9 s give a refusal, multi-host gives a refusal);
- sequential budget consumption with rollback at the deadline, not after it;
- the refused, rolled-back and uncertain terminal outcomes, none reported as completion.

For **committed zero-role Example B only**, the HTTP response is `CaseDetail` with `state=open`, `agent_runs: []` and no intent. Unconfirmed terminal attempts use the section 3.2 outcome table. Nothing invents a role run. The failure shows in `GET /v1/cases/{id}/audit` (`investigation_completed`/`failure`).

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
| `agent_workflows` | `id`, scope, `case_id` (FK), `case_revision`, `status` (`running`/`completed`/`inconclusive`), `started_at`, `deadline_at` (CHECK > `started_at`), `finished_at`, `terminal_by`, `body jsonb` (`WorkflowRecord`). A CHECK mirrors the lifecycle rule (`running` ⇔ no `finished_at`/`terminal_by`). Partial unique index: one `running` row per case | SELECT, INSERT, UPDATE |
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
| `_run_investigator` (`service.py:524`) | Not reused as is for live roles. A role-call wrapper takes a call slot, submits the call, and attaches the slot-releasing done-callback (§3.1) **before** waiting on `role_timeout + grace`. A late result is never written: only the coordinator writes, after `future.result` returns in time |
| `finish_investigation` (`service.py:612`) | Success tail only (`recommend`/`abstain`), inside the workflow terminal transaction (§6.1). The intent is built exactly as today (`HoldParameters`/`EscalateParameters` from the stored transaction), with `agent_run_id` = the disposition's eligible `basis_run_id` |
| `_fail_run` (`service.py:651`) | **Not** used to end a workflow: it requires a run and would rewrite it. The workflow terminal transaction (§6.1) handles inconclusive endings with or without a running role |
| `_recover_lost_run` (`service.py:660`), called from `begin_investigation` (`service.py:560`) | Also look for a `running` workflow on the case. Once `deadline_at + RECOVERY_GRACE < now`, run the terminal transaction with `terminal_by="recovery"` and code `interrupted`. This covers zero-role and between-role crashes, where no running role run exists |

**Resumption.** G3B never resumes a workflow mid-way. After a crash, recovery reopens the case, and a new `investigate` starts a fresh workflow with a new ID, re-running all roles. Every earlier step and run stays recorded with its true status.

**Where a repeat is safe.** Only a call whose worker has *returned* with `provider_unavailable` or `invalid_output` may be repeated, once per workflow, and only with a free call slot and enough remaining time (§3.1). A timed-out call is never repeated: its worker is unresolved, and a repeat would overlap it. Role calls have no side effects inside Sentinel. Provider-side quota use of a finished or abandoned call is not reversible, and is not claimed to be exactly once.

### 6.1 Workflow terminal transaction and recovery (R32)

**One function** (`terminate_workflow` in G3B) ends every workflow. It is independent of whether a role run is active, and does the following in **one terminal-phase transaction**, budgeted by §3.2 (≤ 5 000 ms, never started below 1 000 ms, on the workflow's already-open connection):

1. **Guard by scope and revision.** Lock the case `FOR UPDATE`, filtered by the context's tenant and session (as `_case` does). Require `case.state == "investigating"`, `case.revision == workflow.case_revision`, and the workflow row `status = 'running'`. The workflow update is a compare-and-set (`UPDATE … WHERE id = %s AND status = 'running'`). If any guard fails, change nothing and raise `investigation_superseded`, as `finish_investigation` does today.
2. **Close an active role run, if any.** If one `running` `agent_runs` row exists for this workflow, set it to `failed` with its true code: `timeout` for an expired wait or recovery, else `provider_unavailable`, `invalid_output` or `budget_exhausted`. **Completed, failed or inconclusive role runs are never rewritten.** No role run is created to make the response look complete.
3. **Write the workflow terminal record:** `status`, `finished_at` = now, `terminal_by`, `disposition` with its code, counters. These must satisfy the `WorkflowRecord` lifecycle rules in the draft.
4. **Apply the outcome:**
   - **`recommend`/`abstain`:** re-verify the evidence snapshot (`require_evidence_snapshot`). Then case → `awaiting_approval` (r+2), plus the server-built intent at r+2 with `agent_run_id` = basis. If the snapshot check fails, write instead an `inconclusive`/`stale_evidence_snapshot` record and apply the inconclusive outcome; the same transaction never writes both.
   - **`inconclusive`:** case → `open` (r+2), no intent.
5. **Audit.** Append one `investigation_completed` event (`success` for recommend/abstain, `failure` for inconclusive) at the new revision:
   - with `terminal_by="coordinator"`: actor = the **workflow's coordinator principal** (uuid5 of the workflow config, the `Workflow.principal_id`), `actor_kind="agent"`;
   - with `terminal_by="recovery"`: actor = `SYSTEM_ACTOR`, `actor_kind="system"`, because no coordinator is alive.

   Role principals appear only on their own `agent_runs`.
6. **Read the response, then commit.** Read the `CaseDetail` inside the same transaction, then `COMMIT`. If the transaction was refused or rolled back, or the COMMIT reply is uncertain, the request returns the honest 409 from §3.2 (`investigation_in_progress` or `investigation_outcome_unknown`), never a success. A workflow left `running` is closed later by recovery, which uses this same function in its own transaction (a fresh `db_wait_seconds` budget under the §3.2 rules, outside the expired workflow deadline) with `terminal_by="recovery"`.

**Eligible basis for an intent.** It must be an `agent_runs` row in **the same workflow**, with `role="investigator"`, `status="completed"`, and the **latest** investigator attempt:
- for `recommend`, the adopted output, all claims supported;
- for `abstain`, the latest completed investigator output, whose operation is replaced by the server's escalate/`insufficient_evidence`.

An abstention without an eligible completed investigator run is impossible by the state machine, since the reviewer only runs after one. If the check nevertheless finds none, the outcome is `inconclusive`/`coordinator_error` with no intent. The intent never references an analyst or reviewer run. Human approval and execution remain separate steps, as today.

**What CaseDetail (v1.1) shows after each ending.** The counts below describe a **fresh case and this workflow**. `CaseDetail.agent_runs` keeps returning **every** historical run of the case, as v1.1 does today. After a retry it also contains earlier workflows' runs, and G3B must not filter them to match these illustrative counts.

| Ending | `case.state` / revision | `agent_runs` | Intent | Audit |
| --- | --- | --- | --- | --- |
| recommend / abstain | `awaiting_approval`, r+2 | 3–5 roles, one adopted investigator run with `finding` | 1, at r+2 | started (human), completed/success (coordinator) |
| Exhausted before the first role (Example B) | `open`, r+2 | `[]` | none | started, completed/failure (coordinator) |
| Timeout in a role (Example A) | `open`, r+2 | earlier completed roles + the timed-out run `failed`/`timeout` | none | started, completed/failure (coordinator) |
| **Crash between roles** (analyst completed, process died before the investigator started) | `investigating`, r+1, until the next `investigate` after `deadline_at + 30 s`. That request recovers and returns 409 `investigation_recovered` (existing code); the client re-reads | analyst `completed` (unchanged) | none | started, completed/failure (**system**) |
| Crash during a role | as above after recovery | that role `failed`/`timeout`; earlier roles unchanged | none | started, completed/failure (system) |

The v1.1 UI shows "No investigation has been recorded" when `agent_runs` is empty (`web/src/ui/CaseFile.tsx:162`), which is literally true. The workflow failure is visible only through the audit until the G3C trace route exists. That is a known display limitation, not a contract violation.

**Example C: between-role crash and recovery.** This is `WorkflowRecord.between_role_interrupted` in the examples.

| t (s) | Event |
| --- | --- |
| 0 | Claim r1 → r2; W `running`, deadline 150 |
| 3–20 | Gathering; analyst `completed` |
| 21 | The API process is killed. Leases vanish with it; no role run is `running` |
| 21–179 | `GET` shows `investigating` r2. An `investigate` request before 180 gets 409 `investigation_in_progress` |
| 249 | A human `investigate` (expected revision 2): `begin_investigation` finds W `running` past `deadline_at + RECOVERY_GRACE`. The terminal transaction runs: W `inconclusive`/`interrupted`, `terminal_by=recovery`, analyst run untouched, case → `open` r3, system audit. Response: 409 `investigation_recovered` |
| 250 | The client re-reads (r3) and may start a fresh workflow W2 |

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
- *Investigator timeout:* no repeat, since the worker is unresolved. The result is inconclusive/timeout: the case reopens at revision 3 with no intent, and the late worker keeps its call slot until it returns (§3.1, Example A). The analyst can retry later. An operator switch to the deterministic investigator makes the old case `stale_agent_config`.
- *Investigator `provider_unavailable` once:* one repeat (attempt 2), if a call slot and enough time remain, then the normal flow.

## 8. Errors, compatibility and versions

**Errors.** The existing codes keep their meaning:
- `stale_case_revision`, `investigation_in_progress`, `investigation_recovered`, `approval_expired`, `case_not_investigable`, `stale_agent_config`, evidence-snapshot violations (409);
- `permission_denied` (403);
- `not_found` (404) for a case in another session, unchanged.

There are two new additive codes, both 409. The first is **`agent_capacity_exhausted`** (review decision 1). It means process capacity (the workflow slot or every call slot) is held, possibly by *another* case. It is distinct from `investigation_in_progress`, which means this case is busy. The refusal happens before any transaction. It changes no case, writes no record, and says nothing about which case or how many calls hold capacity. It is additive under the existing `ErrorResponse.error: str`, and is added to the documented handled-code list in G3B, not before.

The second is **`investigation_outcome_unknown`**: the terminal COMMIT was sent but no definitive reply arrived (§3.2). The server makes no claim about the resulting state. The client re-reads the case, and a workflow still `running` is closed by recovery. When the terminal write was refused or rolled back, the case really is still investigating, so the existing `investigation_in_progress` is returned.

**Outcomes as observed through v1.1 (no route change).** `POST /v1/cases/{id}/investigations` returns 200 `CaseDetail` with:
- `state=awaiting_approval`, three to five `agent_runs` (roles), one with a `finding`, and one current intent (recommend or abstain); or
- `state=open`, no current intent, and whatever role runs truly exist: possibly none, possibly only completed ones, possibly one `failed` (inconclusive). See the table in §6.1.

A crash leaves the case `investigating` until lazy recovery returns 409 `investigation_recovered`.

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

## 10. Resolved decisions, assumptions and schema boundary

**Resolved by the review of 06a7c0c** (G3A-06a7c0c.md), and applied throughout:
1. Use 409 `agent_capacity_exhausted` (§8).
2. Keep 45 s per live role and 150 s per workflow as **provisional, unmeasured** defaults. Each call needs its full timeout + grace + terminal reserve remaining, so five calls fit only if earlier calls return quickly. The outstanding-call bound (§3.1) applies separately. A measured change is a new pinned config and protocol version.
3. An inconclusive workflow reopens the case to `open`, with no intent and no reopen route; the case-level `inconclusive` state is not entered (§3, §6.1).
4. Token usage stays `unknown` unless actually reported and validated (`Usage` rules). Parsing tests may use synthetic envelopes; a real CLI observation is a later, explicitly opt-in step.

**Assumptions:**
- **Claude CLI per role.** Each role's adapter uses the same subscription and isolation checks as `ClaudeCliInvestigator`, with a role-specific system prompt and JSON schema.
- **Model alias drift.** The alias (`sonnet`) still resolves over time. Pins record the alias, as ADR 0003 says.
- **The deterministic role adapters** are a plumbing control and a fixture. They are not evidence of multi-agent quality (see the protocol). They take no call slots.

**Schema boundary.** The typed draft enforces everything that one record can show about itself: field types, bounds, the exact role set, usage coherence, the workflow lifecycle and time order, disposition consistency, and tool-result status. **The coordinator must check everything that spans records.** The exact list is in [contracts-draft/README.md](contracts-draft/README.md#coordinator-checks-cross-record). A passing schema check does not establish those.
