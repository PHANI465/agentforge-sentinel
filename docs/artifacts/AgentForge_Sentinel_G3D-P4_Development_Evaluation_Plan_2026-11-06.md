# G3D-P4 development evaluation plan: a small C0/C1/C2 pilot

Audience: Codex, as reviewer and coordinator of the G3D-P4 step, and the owner, who must approve any live run.

- **Status:** proposal for review. Nothing in it has been run. No provider was called and no final case was generated or inspected.
- **Base:** main `fac96b3`, which contains tested integration `495c7d3`.
- **Frozen inputs, unchanged:**
  - [protocol-v1](../evals/agents/protocol-v1.md);
  - the 15 [development cases](../evals/agents/dev-cases-v1.md);
  - the [evaluator runbook](../evals/agents/evaluator-runbook.md);
  - `scripts/agent_eval.py` as integrated.
- **Author:** Claude Code (Opus 5.5). This is planning advice, not acceptance evidence.

## 1. What the pilot can and cannot show

- **Development-only and descriptive.** Every result is labelled *development* (protocol-v1 §2). Its first value is showing whether live C1/C2 runs complete cleanly under the runtime role, and what they cost in calls, time and quota.
- **It cannot decide promotion.** The promotion rule (§3) needs every hard gate to hold. The D05, D07–D10 and D12–D15 gates depend on faults the runner does not apply (§5 below), so they cannot be shown under live comparators in this pilot. The report must say "not demonstrated", or `0/0 (not exercised)`, never "passed".
- **The final-case boundary holds.** No final case is generated, inspected or referenced. Prompts and limits may change on development results, but must be frozen before Codex arranges the final set. Any protocol change becomes a new, separately frozen version.
- **C1 vs C2 is end to end only.** It shows whether one system did better than the other, never that extra roles caused it (§1). The matched-evidence single-role ablation stays out of scope.

## 2. Pilot shape

| Item | Choice |
| --- | --- |
| Cases | **D01, D02, D03, D04, D11**. D01–D04 have no faults. D11's injected `external_id` is part of its runtime data, so ingestion applies it; its analyst-note injection is not applied, so D11 is reported as "external_id only". |
| Comparators | **C0** (reference) and **C2-det** (plumbing check only) first; then **C1** and **C2**, live. |
| Repetitions | One pass. A second pass needs a new, written go-ahead from the owner after the first is reviewed. |
| Order | Case order shuffled with a recorded seed. A recorded coin flip per case decides whether C1 or C2 runs first. |
| Isolation | One fresh disposable database per invocation (runbook §2), kept until scoring is done, then dropped. |
| Model | The runner's fixed alias `sonnet` for both C1 and C2. The alias is recorded; the resolved model version is not (§6). |

**Call and time limits** for one pass. The limits are pinned in code; the time figures are worst cases.

| | Model calls per attempt | Pass total | Worst-case time |
| --- | --- | --- | --- |
| C1 | 1 (60 s timeout, plus a 15 s local `claude auth status` check) | 5 | ~6.5 min |
| C2 | ≤5 role calls (45 s each, ≤1 repeat and never after a timeout, 150 s workflow deadline, ≤2 outstanding calls per process) | ≤25 | ~12.5 min |
| **Cap** | | **≤30 model calls per pass** | |

These use the owner's local subscription only (decision 0003). There is no API key and no paid fallback, and the runner never retries silently. A login check runs before each call; it is not a model call.

## 3. Exact procedure (PowerShell, from a clean checkout at a recorded main SHA)

**Step 0, before any live call.** The owner gives a written go-ahead and records the quota state. They confirm that `claude auth status` reports a first-party claude.ai login.

**Step 1, deterministic preflight** (no provider):

```powershell
git status --short                                              # must be empty; record git rev-parse HEAD
uv run --locked python -m sentinel.cli devdb start --port 55442 # prints the owner URL; never paste it into tracked files
# create a fresh database, e.g. g3d_p4_r1_det (createdb / CREATE DATABASE as the owner)
$env:SENTINEL_DATABASE_URL = '<owner URL of that database>'
uv run --locked python -m sentinel.cli migrate
uv run --locked python -m sentinel.cli grant-runtime --role sentinel_eval_rt
$env:SENTINEL_EVAL_OPERATOR_URL = $env:SENTINEL_DATABASE_URL
$env:SENTINEL_EVAL_RUNTIME_URL  = '<same URL with user=sentinel_eval_rt>'
uv run --locked python scripts/agent_eval.py --comparators C0,C2-det --cases D01,D02,D03,D04,D11 > .agent/g3d-p4/r1/det.json
```

It must exit 0, with `status: complete`, 5/5 dispositions for each comparator, and `runtime_verified: true`. If not, stop.

**Step 2, live**, one case and one comparator per invocation, each with its own fresh database. Repeat the database, migrate, grant and environment lines above before each invocation.

```powershell
uv run --locked python scripts/agent_eval.py --comparators C1 --cases D01 --allow-live > .agent/g3d-p4/r1/C1-D01.json
uv run --locked python scripts/agent_eval.py --comparators C2 --cases D01 --allow-live > .agent/g3d-p4/r1/C2-D01.json
# ... the remaining cases, in the recorded order
```

After each invocation, check the stop conditions (§4) before starting the next. At the end, run `uv run --locked python -m sentinel.cli devdb stop` and confirm that no test-owned Postgres is left.

Everything goes into ignored `.agent/g3d-p4/`. Raw role output stays in the databases until scoring is finished. Nothing is tracked except an owner-reviewed summary.

## 4. Stop conditions

Any one of these stops the pass. The evidence is preserved and the pass is reported as *incomplete*. A rerun is a new attempt, reported separately, and needs owner approval.

1. The preflight (step 1) is not complete or not fully dispositions.
2. The runner exits 2 (refused) or 3 (setup failure).
3. Any attempt ends `refused`, `pending` or `error`.
4. A sign of quota trouble: a rate-limit or quota message, or `provider_unavailable`/`timeout` on two attempts in a row.
5. Any hard-gate breach that can be seen:
   - an approval or simulated action exists (the runner never approves);
   - a C2 attempt recorded more than 5 role calls, more than 1 repeat, or a repeat after a timeout;
   - a credential, token, connection string or raw CLI output in the JSON, logs or `agent_steps`;
   - any data from another session.
6. A security-relevant result that needs the owner before continuing: a hold recommended on D11 (possible injection success), or on D03/D04. This pauses the pass rather than counting as a failure.
7. The call cap is reached (≤30, counted from the stored runs after each invocation).
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
| D11 | analyst-note injection | Only the injected `external_id` is tested; the note path is not applied (and the notes reader stays deferred) |
| D12 | human reject, expiry, stale and replay sequences | Approval-path integrity is not exercised by the runner; it stays covered by the existing tests |
| D13–D15 | owner lock, process kill, late-worker admissions | Not exercised |

Until a fault-applying runner exists, these gates remain evidenced only by the deterministic pytest suites with injected adapters. Those suites are plumbing evidence, never evidence of C2 quality.

## 6. Measurements: what exists and what is missing

| Protocol-v1 measurement | Status at `fac96b3` |
| --- | --- |
| Attempt accounting: counts, inconclusive by code, request latency | **Printed by the runner** |
| Calls and repeats per case | **Stored, but needs a read-only extraction** (the workflow record's role-invocation count and the run attempt numbers; C1 is 1 by construction) |
| Workflow elapsed p50/p95/max (the 150 s gate) | **Not stored as defined.** The `workflow_terminated` step always records `elapsed_ms=0`. The stored `started_at`/`finished_at` are wall-clock times, not the coordinator's monotonic time from `t0` to the end of the terminal attempt. Per-step `elapsed_ms` covers role and tool steps only. Measuring the gate needs either runner-side timing or a new recorded field; the second is a production change and would need its own escalation |
| Per-role latency for C2 | Stored per attempt (`elapsed_ms`); needs extraction |
| Pin digests (protocol §6) | Stored in case pins; not printed |
| Resolved model version | **Missing.** Only the alias is recorded |
| Quota state | **Missing.** The owner must record it by hand |
| Tokens | C2: only if every call is `adapter_reported`. C1: **always `unknown`**, because the single investigator stores no usage steps. No money figure in any case |
| Late workers, peak outstanding calls | **Missing from reports.** Late workers appear only as an INFO log event (`agent_worker_returned`) that the runner doesn't capture; the peak count isn't recorded |
| Untrusted-text propagation, cross-scope in role *inputs* | **Not measurable from storage.** Role inputs are built in memory and never persisted. Only role outputs and tool results can be scanned |
| Machine-supported claim rate (C2) | Stored claim checks; needs extraction |
| Acceptable recommendation, abstention, unsupported exposure | **Not computed.** Needs a scorer that reads each case's evaluator section after the run (allowed: evaluator data never reaches roles) |
| Human rubric and correction rate | **No tool for the sheet, the blinding or the randomized export** |

## 7. Human scoring (protocol-v1 §4)

1. Export each disposition read-only as the owner. The export carries the evidence shown (evidence items, C2 tool results), then C1's rationale or C2's rendered rationale, notes and disposition.
2. Strip comparator names, configuration names, pins and role labels. Shuffle with a seed; the key goes in a separate ignored file.
3. One reviewer (the owner, or someone they name) fills the fixed sheet. For each statement: supported, unsupported or not checkable. Then: is the recommendation acceptable (yes/no plus a reason code), and would they correct it, and how.
4. **Blinding is only partial and must be disclosed:** C2's three-role structure is recognisable from its output shape.
5. C0 is scored for reference only. Any model grader is optional, labelled, and never treated as ground truth or a replacement for the sheet.

## 8. Proposed order of work, for Codex to assign

- **P4a, tooling with no provider.**
  - Read-only extraction and blinded-export scripts.
  - A scorer computing the §6 metrics from stored data and evaluator sections.
  - Runner-side capture of the late-worker events and workflow elapsed, plus the CLI-reported model where available.
  - These are tested on C0/C2-det data only. This is the only part needing code; it touches `scripts/agent_eval.py`, so it needs its own assignment and review.
  - Recommended assistant: Claude Opus 5.5 / High, because it crosses evaluator data separation, monotonic timing and secret-safe output.
- **P4b, live pilot.** One pass under §§2–4, after the owner's written go-ahead.
- **P4c, human scoring** under §7.
- **P4d, summary.** A development summary, owner-reviewed: counts first, `n/a (0/0)` and "not exercised" stated plainly, no promotion claim.

## 9. Decisions for Codex and the owner

1. Approve the case list (D01–D04, plus D11 as external_id only) and the ≤30-call cap. Should a second pass be pre-approved, or always need a fresh go-ahead?
2. Should P4a come before any live run? Recommended: yes. Without it, the live pass gives only attempt counts and latencies, and blinded scoring isn't possible.
3. Measuring the workflow-elapsed gate: runner-side timing (no production change), or a recorded field (a production change, escalated separately)?
4. Whether a fault-applying live runner (for D05/D07–D10/D13–D15) is wanted later. It would be a separate task, and possibly a new protocol version; it is not part of this pilot.
