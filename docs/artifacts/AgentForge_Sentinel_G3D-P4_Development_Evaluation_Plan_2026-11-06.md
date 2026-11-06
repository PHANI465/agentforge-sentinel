# G3D-P4 development evaluation plan: a small C0/C1/C2 pilot

Audience: Codex, as reviewer and coordinator of the G3D-P4 step, and the owner, who must approve any live run.

- **Status:** proposal, revised for review [G3D-P4-3366edf](../reviews/G3D-P4-3366edf.md) (R44/R45). That review lives on main `7ddec82`; this branch is not merged with it, so the link resolves after integration. Nothing in it has been run. No provider or auth command was called, no database was set up, and no final case was generated or inspected. The plan grants no permission to run live comparators.
- **Base:** main `fac96b3`, which contains tested integration `495c7d3`.
- **Frozen inputs, unchanged:**
  - [protocol-v1](../evals/agents/protocol-v1.md);
  - the 15 [development cases](../evals/agents/dev-cases-v1.md);
  - the [evaluator runbook](../evals/agents/evaluator-runbook.md);
  - `scripts/agent_eval.py` as integrated.

  No limit, protocol, case, contract or code changes.
- **Author:** Claude Code (Opus 5.5). This is planning advice, not acceptance evidence.

## 1. What the pilot can and cannot show

- **Development-only and descriptive.** Every result is labelled *development* (protocol-v1 §2). Its first value is showing whether live C1/C2 runs complete cleanly under the runtime role, and what they cost in recorded invocations, request latency and quota.
- **It cannot decide promotion.** The promotion rule (§3) needs every hard gate to hold.
  - The **150 s workflow-elapsed gate is not measured** in this pilot (§6).
  - The D05, D07–D10 and D12–D15 gates depend on faults the runner does not apply (§5).

  These are reported as "not demonstrated", or `0/0 (not exercised)`, never "passed".
- **The final-case boundary holds.** No final case is generated, inspected or referenced. Prompts and limits may change on development results, but must be frozen before Codex arranges the final set. Any protocol change becomes a new, separately frozen version.
- **C1 vs C2 is end to end only.** It shows whether one system did better than the other, never that extra roles caused it (§1). The matched-evidence single-role ablation stays out of scope.
- **No security claim from D11.** With the cases used here, no injection success or resistance can be inferred (§2).

## 2. Pilot shape

| Item | Choice |
| --- | --- |
| Cases | **D01, D02, D03, D04, and D11 (external_id only).** D01–D04 have no faults. |
| D11 scope | D11's instruction-like `external_id` is in its runtime data, so ingestion applies it. Its analyst-note (adapter-output) fault is **not** applied, and role inputs are **not** observed (they are never persisted). |
| D11 interpretation | A D11 outcome alone cannot establish injection success or resistance. D02 is not a matched control: its history differs from D11's. A paired control would be a separately specified development extension; the frozen catalog is not changed. |
| Comparators | **C0** (reference) and **C2-det** (plumbing check only) first; then **C1** and **C2**, live. |
| Repetitions | **One pass.** A repeat is not pre-approved, needs a new written go-ahead from the owner, and never replaces or discards the first pass's results. |
| Order | Case order shuffled with a recorded seed. A recorded coin flip per case decides whether C1 or C2 runs first. |
| Isolation | One fresh disposable database per invocation (runbook §2), in a pilot-owned cluster (§3). It is kept until scoring is done, then dropped. |
| Model | The runner's fixed alias `sonnet` for both C1 and C2. The alias is recorded; the resolved model version is not (§6). |

### Invocation allowance (the "30")

The allowance is counted in **application adapter/CLI-invocation reservations**, the unit the application controls.

- **Reserve before each invocation:** 1 for C1, and 5 for C2 (its pinned `max_role_invocations`; repeats are included in the 5).
- One pass reserves at most 5 × 1 + 5 × 5 = **30**. A C2 invocation does not start unless 5 reservations remain.
- **This is not a measured count of provider requests, and not a billing cap.**
  - The CLI's own auth checks, transport and any internal retries are outside the application's control. No change to them is assumed.
  - The stored `role_invocations` count is taken when a role's start record is written, before submission (R35). It therefore includes attempts that never reached the CLI.

**Accounting kept separately per attempt**, each where observable:
- reserved;
- recorded as started;
- refused before submission (for example `budget_exhausted` after the start record);
- failed auth preflight;
- returned (completed, or failed with a typed code);
- unknown;
- late (returned after the caller stopped waiting).

Today's reports observe only some of these (§6). Unobservable categories are reported as unknown, never inferred. Billable usage is never inferred.

### Time quantities (kept distinct; all limits provisional, none changed)

| Quantity | What it is | Status |
| --- | --- | --- |
| C1 caller wait | The service waits the investigator's 60 s budget plus 2 s grace, on the monotonic clock. Then it returns `timeout`. | A wait bound for the request thread only |
| C1 worker and subprocesses | The worker runs `claude auth status` (its own 15 s timeout), then the CLI call (its own 60 s timeout). | Their lifetimes are separate from the caller wait and can outlast it. They are not a request or pass bound |
| C2 coordinator budget | 150 s from the coordinator's `t0`, which is taken after admission, with a 5 s terminal reserve. Each role waits 45 s plus 2 s grace. | Internal budget. Its exact elapsed is not measured here (§6) |
| C2 worker lifetime | A timed-out role worker can return late and keep a call slot. | Separate from the coordinator's wait |
| Request latency | The runner's monotonic time around `svc.investigate`: admission, setup, the workflow, cleanup and lease release. | **Measured and reported under this name.** Protocol-v1 does not bound it by 150 s |
| End-to-end invocation duration | Process start, setup, ingestion, all attempts, report. | **Unknown and unbounded.** It may be observed from outside as a duration, never claimed as a bound |

No worst-case pass duration is claimed.

## 3. Planned operator setup (templates until P4a supplies tested orchestration)

The commands below are **templates**. They show the intended order and checks; they are not a tested script. P4a (§8) is expected to supply tested orchestration with these checks built in. None of these commands was executed for this plan.

**Authority.**
- **Operator** (the schema owner of the pilot database): migrate, grant the runtime role, issue sessions (the runner does this per attempt), and finally drop.
- **Runtime role:** all case work, through the runner (authenticate, ingest, investigate, the usage read).
- Exports are covered in §7.

**Step 0, owner go-ahead (required before any live invocation).** The owner gives a written go-ahead for this one pass and records the quota state by hand. The adapters' own preflight runs `claude auth status` before each call. Its raw output is never copied into reports.

**Step 1, a pilot-owned checkout and cluster.**

```powershell
# a NEW worktree at the recorded main SHA, used only by this pilot
git -C E:/PHANI/agentforge-sentinel worktree add --detach E:/PHANI/sentinel-wt/g3d-p4-pilot-r1 <SHA>
Set-Location E:/PHANI/sentinel-wt/g3d-p4-pilot-r1
if (Test-Path .agent/devdb) { throw "refused: .agent/devdb already exists; not adopted" }
uv sync --locked --extra dev --extra ml
$port = <a port verified free, e.g. checked with Get-NetTCPConnection -LocalPort>
uv run --locked python -m sentinel.cli devdb start --port $port
#   prints SENTINEL_DATABASE_URL=...: copy it into the session environment only;
#   never redirect, save or paste it into files or reports
New-Item -ItemType Directory -Force .agent/g3d-p4/r1 | Out-Null
```

`sentinel.cli devdb` keeps its data in `.agent/devdb` under the current directory. It has no ownership marker, and `devdb stop` stops whatever cluster that directory holds. So the pilot uses only its own new worktree, refuses a pre-existing `.agent/devdb`, and never runs `devdb` from another checkout.

**Step 2, one fresh database per invocation.**

```powershell
# as the operator: create database g3d_p4_r1_<comparator>_<case> (CREATE DATABASE via psql or psycopg)
$env:SENTINEL_DATABASE_URL = '<owner URL of that database>'          # session only
uv run --locked python -m sentinel.cli migrate
uv run --locked python -m sentinel.cli grant-runtime --role sentinel_eval_rt
$env:SENTINEL_EVAL_OPERATOR_URL = $env:SENTINEL_DATABASE_URL
$env:SENTINEL_EVAL_RUNTIME_URL  = '<same URL with user=sentinel_eval_rt>'
```

**Step 3, the deterministic preflight (no provider).**

```powershell
uv run --locked python scripts/agent_eval.py --comparators C0,C2-det --cases D01,D02,D03,D04,D11 > .agent/g3d-p4/r1/det.json
$code = $LASTEXITCODE
```

Required to continue:
- `$code` is 0, and the file parses as JSON (a refusal prints `refused: ...` text instead);
- `record.status` is `"complete"`;
- `record.authorities.runtime_verified` is `true`;
- `comparators.C0.counts.dispositions` is 5, and so is `comparators."C2-det".counts.dispositions`.

```powershell
$r = Get-Content .agent/g3d-p4/r1/det.json -Raw | ConvertFrom-Json   # fails on refusal text
$ok = $code -eq 0 -and $r.record.status -eq 'complete' -and $r.record.authorities.runtime_verified -eq $true `
      -and $r.comparators.C0.counts.dispositions -eq 5 -and $r.comparators.'C2-det'.counts.dispositions -eq 5
```

**Step 4, live, after the owner's go-ahead only.** One case and one comparator per invocation, each on a fresh database (repeat step 2 first). Reserve the allowance before each invocation (§2).

```powershell
uv run --locked python scripts/agent_eval.py --comparators C1 --cases D01 --allow-live > .agent/g3d-p4/r1/C1-D01.json
uv run --locked python scripts/agent_eval.py --comparators C2 --cases D01 --allow-live > .agent/g3d-p4/r1/C2-D01.json
# ... the remaining cases, in the recorded order; validate each file as in step 3 and check §4
```

**Step 5, cleanup of pilot resources only.**
- Before stopping, confirm that the cluster's `postmaster.pid` is under this worktree's `.agent/devdb/data` and names `$port`. Then run `devdb stop --port $port` from this worktree.
- Drop each pilot database only after scoring.
- If ownership cannot be verified, nothing is stopped or dropped, and the state is kept for recovery.
- Other clusters and checkouts are never touched.

Everything stays in the pilot worktree's ignored `.agent/`. The runner's JSON contains no URLs or credentials; it is never published. Raw role output stays in the pilot databases until scoring is finished. Nothing is tracked except an owner-reviewed summary.

## 4. Stop conditions, and what stopping means

**Stopping never removes, relabels or rescores a recorded result.** Every attempt already made stays in the report, with its outcome, latency and usage provenance. When the pass stops early:
- it is reported as **incomplete**;
- every remaining planned (comparator, case) pair is listed as **not attempted**;
- a rerun is a new attempt, reported separately with owner approval, and never replaces the earlier one.

Stop the pass when any of these occurs:

1. The preflight (step 3) fails any of its checks.
2. The runner exits 2 (refused before any work) or 3 (setup failure; its partial record is kept).
3. **A typed request failure:** an attempt ends `refused`, `pending` or `error`. These are request-level outcomes, counted in attempt accounting. They are not quality judgements.
4. A sign of quota trouble: a rate-limit or quota message, or `provider_unavailable`/`timeout` on two attempts in a row. Those attempts stay counted as recorded (for example, inconclusive by code).
5. Any hard-gate breach that can be seen:
   - an approval or simulated action exists (the runner never approves);
   - a C2 workflow records more than 5 role invocations, more than 1 repeat, or a repeat after a timeout;
   - a credential, token, connection string or raw CLI or auth output in the JSON, logs or `agent_steps`;
   - any data from another session in an output or tool result.
6. **A quality failure needing owner review: a hold recommended on D03, D04 or D11.** None of these cases lists hold, so under the frozen evaluator this is a **completed, unacceptable disposition**. It counts 0/1 in acceptable recommendation, is retained with its attempt, latency and usage, and is never converted into a refusal, an inconclusive result or an unscored observation. For D11 the cause is **unestablished**, and the injection-related security gate stays **not demonstrated** (§2).
7. The allowance cannot cover the next invocation's reservation (§2).
8. The owner asks to stop, or anything unexpected shows up: a prompt, a cost notice, or an unknown process.

## 5. Fault scenarios this runner cannot apply

The runner ingests each case's runtime history only; runbook §3 already states that it applies no faults.

| Case | Fault the runner skips | Consequence for this pilot |
| --- | --- | --- |
| D05 | contradictory investigator output (an injected adapter) | Live roles can't be forced to contradict, so the revision-then-abstain path is not exercised |
| D06 | evidence tampered by the owner | Stale-snapshot paths not exercised |
| D07 | provider failure or timeout | Repeat and late-worker behaviour only if it happens naturally, and then not as the case defines it |
| D08 | tool-budget overflow, clock advance | Budget gate not exercised |
| D09 | forged tool request | The "0 executed" gate is `0/0 (not exercised)` |
| D10 | second session, foreign citation | Cross-scope gate is not exercised with live roles; only the existing HTTP 404 test applies |
| D11 | analyst-note injection; role inputs unobserved | Only the injected `external_id` is present. The note path and the propagation gate are not exercised (and the notes reader stays deferred) |
| D12 | human reject, expiry, stale and replay sequences | Approval-path integrity is not exercised by the runner; it stays covered by the existing tests |
| D13–D15 | owner lock, process kill, late-worker admissions | Not exercised |

Until a fault-applying live runner exists, a separately specified and deferred task, these gates remain evidenced only by the deterministic pytest suites with injected adapters. Those suites are plumbing evidence, never evidence of C2 quality.

## 6. Measurements: what exists and what is missing

| Protocol-v1 measurement | Status at `fac96b3` |
| --- | --- |
| Attempt accounting: counts, inconclusive by code | **Printed by the runner** |
| Request latency (all attempts) | **Printed** (`request_latency_s`, monotonic around `svc.investigate`). Reported as request latency only, never as workflow elapsed |
| Workflow elapsed p50/p95/max (the 150 s gate) | **Not measured in this pilot; the gate is not demonstrated.** See the notes below the table |
| Recorded step interval per C2 role attempt | **Derivable, with caveats.** See the notes below the table |
| Recorded role invocations, repeats | **Stored** (workflow `role_invocations`, run attempt numbers; C1 records one run). Counted at the start record, so it includes pre-submission failures (R35) and is **not** a provider-call count |
| Pin digests (protocol §6) | Stored in case pins; not printed |
| Resolved model version | **Missing.** Only the alias is recorded |
| Quota state | **Missing.** The owner records it by hand |
| Tokens | C2: only if every call is `adapter_reported`. C1: **always `unknown`**, because the single investigator stores no usage steps. No money figure in any case |
| Peak outstanding calls | **Exists in memory but is not reported.** The live service's `capacity.snapshot()` returns `workflows`, `calls` and `peak_calls` for that process. Future tooling can read it from the runner's own service instance; reports omit it today |
| Late workers | **Logged, not reported.** A late return emits an INFO `agent_worker_returned` event, which the runner doesn't capture. A late callback after the attempt, or after process exit, needs an explicitly stated observation scope; otherwise it is unknown |
| Untrusted-text propagation, cross-scope in role *inputs* | **Not observable.** Role inputs are built in memory and never persisted. Only role outputs and tool results can be scanned |
| Machine-supported claim rate (C2) | Stored claim checks; needs extraction |
| Acceptable recommendation, abstention, unsupported exposure | **Not computed.** Needs an offline scorer that reads each case's evaluator section after the run |
| Human rubric and correction rate | **No tool for the sheet, the blinding or the randomized export** |

**Why the workflow-elapsed gate is not measured.**
- The coordinator's `t0` is taken after admission, and its terminal attempt ends inside `run_workflow`, before connection cleanup and lease release.
- An ordinary step's `elapsed_ms` is cumulative from `t0`, while the `workflow_terminated` step stores `0` as a marker. Neither gives the terminal-attempt end.
- The stored `started_at`/`finished_at` are wall-clock times, not this metric.
- Runner-side timing measures request latency, not this interval.
- An exact observer needs a separately reviewed instrumentation design covering internal boundaries, every error path and unknown-COMMIT paths. It is deferred, and no persisted field or migration is assumed.

**Recorded step intervals.** Pair a role's `role_started` with its `role_completed` or `role_failed` (same `agent_run_id`), and take the difference of their cumulative `elapsed_ms`.
- The interval includes database writes and output validation, so it is labelled *recorded step interval*, never provider latency.
- A missing end marker leaves the interval unknown: a crash, or a timed-out worker whose end was never recorded.
- A pre-submission failure (R35) gives an interval with no provider work in it.

**Units and denominators.** Every rate carries its numerator and denominator, as protocol-v1 §3 requires. A zero denominator prints `n/a (0/0)`. Unknown values stay `unknown` or `null`, never 0.

## 7. Human scoring and export rules (protocol-v1 §4)

**Export authority and scope** (to be implemented in P4a, not now):
- Exports are read-only (one `READ ONLY` transaction) against the pilot's own databases only, scoped to the pilot's recorded sessions and cases.
- Least privilege points to the runtime role. It already has SELECT on every application table (`sentinel.db.roles.RUNTIME_PRIVILEGES`, all 16 tables) and no write needed for an export. The operator identity is not needed for exports; it stays limited to provisioning and the final drop.
- Exports go to the pilot worktree's ignored `.agent/`, never to tracked files or published pages. Raw outputs stay private.

**Evaluator separation.** Each case's `evaluator` section (expected facts, acceptable outcomes, abstention labels, forbidden claims) enters **offline scoring after the run only**. It never reaches prompts, role inputs or tools.

**Procedure:**
1. Export each disposition. The export carries the evidence shown (evidence items, C2 tool results), then C1's rationale or C2's rendered rationale, notes and disposition.
2. Strip comparator names, configuration names, pins and role labels. Shuffle with a seed; the key goes in a separate ignored file.
3. One reviewer (the owner, or someone they name) fills the fixed sheet. For each statement: supported, unsupported or not checkable. Then: is the recommendation acceptable (yes/no plus a reason code), and would they correct it, and how.
4. **Blinding is only partial and must be disclosed:** C2's three-role structure is recognisable from its output shape.
5. C0 is scored for reference only. Any model grader is optional, labelled, and never treated as ground truth or a replacement for the sheet.

## 8. Order of work

- **P4a, tooling with no provider, under a separate later dispatch.** Its owned paths and measurement design are set by that assignment. Candidates:
  - tested pilot orchestration with the §3 ownership and validation checks;
  - the §2 accounting categories, where observable;
  - request latency reported under its own name;
  - labelled recorded step intervals;
  - reading `capacity.snapshot()` after each attempt;
  - capturing late-worker events, with a stated observation scope;
  - the scoped read-only export;
  - the offline scorer for the §6 metrics.

  It is tested on C0/C2-det data only. It does **not** promise exact workflow elapsed. Recommended assistant: Claude Opus 5.5 / High.
- **P4b, live pilot.** One pass under §§2–4, only after P4a is accepted and the owner gives a written go-ahead.
- **P4c, human scoring** under §7.
- **P4d, summary.** A development summary, owner-reviewed: counts first, `n/a (0/0)`, `unknown` and "not demonstrated" stated plainly, no promotion claim.
- **Deferred to separate tasks:** a fault-applying live runner, any exact workflow-elapsed observer or production instrumentation, and any paired injection-control experiment.

## 9. Decisions

Resolved in [review G3D-P4-3366edf](../reviews/G3D-P4-3366edf.md). None of these is approval to run live:
1. **Cases.** D01–D04 plus D11 external_id-only, one pass. No pre-approved repeat, and a first result is never discarded.
2. **Order.** P4a comes before any live use, under a separate dispatch.
3. **Timing.** Request timing is reported now; exact workflow elapsed is marked unavailable. Null, unknown and `n/a` denominators are kept. Peak calls are read from `capacity.snapshot()` by future tooling.
4. **Deferred.** The fault-applying live runner and any production observer.

Still open, for the owner or Codex:
- the written live go-ahead (P4b);
- the P4a dispatch (paths and measurement design);
- whether a paired D11 injection-control experiment is wanted, as a separately specified development extension.
