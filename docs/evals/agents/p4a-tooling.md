# G3D-P4a evaluator tooling: artifacts, pilot, export and scoring

Audience: whoever runs or reviews the development pilot planned in the accepted [G3D-P4 plan](../../artifacts/AgentForge_Sentinel_G3D-P4_Development_Evaluation_Plan_2026-11-06.md), under the frozen [protocol-v1](protocol-v1.md).

These are **local evaluator formats**, not HTTP or domain contracts. Everything here is development tooling. A deterministic run (C0, C2-det) proves that the tooling works, never agent quality. A live pair (C1, C2) is never started by this tooling without an explicit flag plus the owner's go-ahead, and P4a itself runs none.

## 1. Run artifact (`sentinel.agent-eval.run/1`)

This is the JSON that `scripts/agent_eval.py` prints. Every G3D-P1 field is kept; P4a only adds fields. A report without `record.artifact_version` is a pre-P4a report, and the P4a tools refuse it instead of reading it as if it had the new measurements.

### `record` additions

| Field | Meaning |
| --- | --- |
| `artifact_version` | `sentinel.agent-eval.run/1` |
| `planned_comparators`, `planned_cases` | What this invocation was asked to run, in order. Used to detect missing attempts |
| `comparator_config.<name>` | `pin` (name, version, sha256 of the investigator or workflow config), `live`, `reservation_per_attempt`, `model_alias` (null when deterministic), `model_version` (`unknown` when live, `not_applicable` otherwise). A config that cannot be described is `{"status":"unavailable"}` and never stops the run |
| `measurements` | Plain-text definitions of the time and usage fields below |
| `quota` | `unknown`, or `annotated` when a manual annotation exists |
| `manual_annotations` | From `--annotations FILE`: `[{field: quota or model_version, value, source, recorded_at}]`. Nothing contacts an account to fill them |

### Per-attempt additions (`comparators.<name>.attempts[]`)

| Field | Meaning, units |
| --- | --- |
| `index`, `attempt_id` | 1-based, contiguous; `"<comparator>:<index>:<case>"` |
| `ids` | `tenant_id`, `session_id`, `case_id` of the attempt's own fresh session. Private machine data. A setup failure produces no row, so no IDs |
| `started_at`, `ended_at` | UTC wall-clock times around the request (labels only, never subtracted for a metric) |
| `request_latency_s` | Seconds on the monotonic clock around `svc.investigate`. This is **request latency**: it includes admission, setup, the workflow, cleanup and lease release |
| `workflow_elapsed_ms`, `workflow_elapsed_status` | Always `null` / `"not_measured"`. The 150 s gate is **not demonstrated** |
| `capacity` | The attempt's own service instance's `capacity.snapshot()` (`workflows`, `calls`, `peak_calls`), read once right after the request returned, with `observed_after_return_s`. This process and instance only, not provider-wide |
| `late_returns` | Workflows: `agent_worker_returned` events observed in this process until the runner's `run()` returned (`observed_count`, `events`); `after_cutoff: "unknown"`. Single investigator: `not_observable` (it emits no such event) |
| `pins` | The case's stored pins (dataset, scorer, policy, agent and tool config, evidence snapshot) |
| `workflow_ids`, `workflows[]` | Stored workflows of the case: id, status, terminal_by, `role_invocations`, `tool_calls`, disposition kind, inconclusive code |
| `disposition` | The **adopted** result. For a workflow, its disposition (kind, operation, reason, `basis_run_id`, supported and unsupported claim counts). For the single investigator, its one run with a finding. Never "the last run" or "attempt 1" |
| `recorded_role_attempts`, `repeats` | Stored `agent_runs` rows and `attempt = 2` rows. These are recorded attempts, not provider calls |
| `role_intervals[]` | Per `role_started`: `interval_ms` = end marker minus start marker (both cumulative from the coordinator's `t0`). Labelled *recorded step interval*. `null` with `status: "unknown (no end marker)"` when the end is missing. `pre_submission: true` for a `budget_exhausted` failure after the start record (R35) |
| `reservation` | `reserved_invocations` (C1 1, C2 5, deterministic 0), `recorded_role_attempts`, `pre_submission_refusals`, `observed_adapter_submissions` (`not_observed` when live; `not_applicable` when deterministic), `provider_reach` (`unknown` / `not_applicable`). These are reservations, not provider requests or billing |
| `telemetry` | `read`, `not_read` (errored request) or `unavailable` with an error class name. Telemetry is read after the outcome and never changes it |

Statuses keep their protocol-v1 meaning: `disposition`, `inconclusive`, `refused`, `pending`, `error`. A setup failure is not an attempt. The record says what stopped, and the stopped comparator lists `cases_not_attempted`.

**Integrity check (`agent_eval_support.artifact.validate_run`).** For every comparator, the attempts plus `cases_not_attempted` must be exactly `planned_cases`, in order. Indices must be contiguous, counts must equal the rows, and `workflow_elapsed_ms` must be null. A removed (censored) attempt therefore makes the artifact invalid; it cannot silently disappear.

**Never in an artifact:** bearer tokens, connection strings, passwords, auth output, or CLI envelopes and stdout.

Example (abridged, from a real C2-det attempt on D01):

```json
{"index": 1, "attempt_id": "C2-det:1:D01", "case": "D01", "outcome": "disposition",
 "request_latency_s": 0.453, "workflow_elapsed_ms": null, "workflow_elapsed_status": "not_measured",
 "disposition": {"source": "workflow_disposition", "kind": "recommend",
                 "operation": "simulated_hold", "reason_code": "velocity_pattern",
                 "basis_run_id": "...", "supported_claims": 4, "unsupported_claims": 0},
 "recorded_role_attempts": 3, "repeats": 0,
 "role_intervals": [{"role": "evidence_analyst", "interval_ms": 16, "status": "recorded",
                     "label": "recorded step interval (includes persistence/validation; not provider latency)"}],
 "capacity": {"workflows": 0, "calls": 0, "peak_calls": 0, "scope": "this attempt's service instance in this process"},
 "reservation": {"reserved_invocations": 0, "provider_reach": "not_applicable"}}
```

## 2. Pilot supervisor (`scripts/agent_eval_pilot.py`, manifest `sentinel.agent-eval.pilot/1`)

```powershell
uv run --locked python scripts/agent_eval_pilot.py plan --root <NEW DIR> [--seed N]
uv run --locked python scripts/agent_eval_pilot.py run --root <DIR> --pair P00-det           # deterministic preflight
uv run --locked python scripts/agent_eval_pilot.py status --root <DIR>
uv run --locked python scripts/agent_eval_pilot.py cleanup --root <DIR> [--drop]
# later, only with the owner's written go-ahead (not run by P4a):
uv run --locked python scripts/agent_eval_pilot.py run --root <DIR> --pair L01-C2-D03 --allow-live
```

- **Root.** `plan` refuses an existing non-empty directory. Old state, including `.agent/devdb`, is never adopted. The root holds:
  - a random-owner marker;
  - the private `pilot.json` manifest;
  - `stack/`, a database-only cluster owned through `local_stack.Stack` and its identity-checked `start_database`/`stop_database` (no API process; no second PID or port discovery);
  - `runs/<pair>.json` (the runner's output, kept as written) and `runs/<pair>.stderr.txt`.
- **Schedule.** The deterministic preflight `P00-det` (C0 and C2-det on D01–D04 and D11, one fresh database) runs first. Then come 10 live pairs, one per (comparator, case), in a seeded case order with a seeded coin flip for which live comparator goes first. Pairs run strictly in order. A pair runs once; a rerun is not offered.
- **Live boundary.**
  - A live pair needs `--allow-live`, the completed preflight, and its full reservation (C1 1, C2 5, of 30), which is reserved before anything starts and never returned.
  - Nothing chains the preflight into live calls, and the runner's own consent check stays in force, with no fallback.
  - P4a's tests intercept the runner for live pairs; no Claude executable, auth command or provider is reached.
- **Authority.** The operator (the cluster owner) creates one fresh, uniquely named database per pair, migrates it, grants `sentinel_eval_rt`, and issues sessions through the runner. All case work runs as the runtime role. The connection strings go to the runner through its environment, never argv, the console or files.
- **Outcomes.** After each run the supervisor validates the artifact (version, integrity, `record.status`, `record.authorities.runtime_verified`, preflight `comparators.*.counts.dispositions`). It then stops the pass, as **incomplete** with the remaining pairs listed in `not_attempted`, on any of:
  - an exit code other than 0 or 3, or a refusal;
  - a setup failure (exit 3);
  - a typed request failure (`refused`, `pending` or `error`);
  - a preflight short of all dispositions;
  - a **wrong hold**: a completed hold on a case whose acceptable list has no hold (D03, D04, D11), which is kept and scored unacceptable.

  The run file is never rewritten.
- **Retention and cleanup.** The cluster is stopped after every run and kept, with its databases, for private scoring. `cleanup` stops it. `cleanup --drop` starts it through the owned lifecycle, drops only the databases recorded in the manifest that carry this pilot's owner prefix (anything else is refused), and stops it again. Nothing is deleted from disk. After cleanup, removing the root directory is a manual step. It is not a production retention promise.

## 3. Export bundle (`sentinel.agent-eval.bundle/1`) and review packets (`sentinel.agent-eval.review-packets/1`)

```powershell
uv run --locked python scripts/agent_eval_report.py export --root <DIR> --pair P00-det   # -> exports/<pair>.bundle.json
uv run --locked python scripts/agent_eval_report.py packets --root <DIR> [--seed N]      # -> review/, keys/
```

**Export** (`exports/<pair>.bundle.json`, private):
- **Authority and isolation.** The export runs as the **runtime role** (never the operator), in one `REPEATABLE READ, READ ONLY` transaction, against the pair's own database only. The supervisor starts the owned cluster for it and stops it afterwards.
- **Scope.** Each query selects by the IDs that the attempt's artifact row names, plus that row's tenant and session. Every returned row is then re-checked against that scope. So a foreign or tampered mapping, or a broken scope filter, is refused with nothing written; the export never widens a query.
- **Workflows.** The stored workflow IDs must equal the artifact's. The adopted run is the artifact's `basis_run_id`, and it must be stored in the same scope.
- **What it records** per attempt:
  - case state and revision, and pins;
  - transaction amount, direction and time, and scoring;
  - evidence facts;
  - workflows (status as stored: a running workflow stays running, and nothing is recovered);
  - runs (role, status, failure code, attempt, config name);
  - validated role outputs, tool results and claim checks;
  - the adopted finding.
- **No-mutation proof.** `mutation_proof` holds a row count and content digest of `cases`, `agent_workflows`, `agent_runs`, `agent_steps`, `action_intents`, `approvals`, `simulated_actions` and `audit_events`, taken before and after the export as the runtime role.
- **Never in a bundle:** tokens, URLs, auth output, or raw CLI stdout.

**Review packets:**
- **One packet per disposition.** Inconclusive and failed attempts have nothing to score.
- **Order and IDs.** Packets come in a seeded random order with opaque IDs (`PK-…`).
- **Content.** Each packet has three parts:
  - the evidence shown: the transaction, the case's evidence facts and, for C2, the tool values;
  - the recommendation (operation and reason);
  - free-text statements: the adopted rationale, then the role notes, without role labels.
- **What is removed:** comparator, config and role names, pins, case and catalog IDs, and expected answers.
- **Blinding is partial and is disclosed in the file:**
  - C2's server-rendered rationale (for example "Reviewer: accept.") and the presence of tool values reveal the system;
  - nothing claims an independent human scored anything.
- **Files.** The packets go in `review/packets.json` and `review/sheet.csv`, with blank scoring columns: `supported`, `acceptable`, `reason_code`, `would_correct` and `correction`. The unblinding key (packet → attempt, comparator, case, run digest) is written separately to `keys/unblinding-key.json`.
- **Inert text.** Text stays data:
  - JSON escapes it;
  - in CSV, a text cell starting with `=`, `+`, `-`, `@`, a tab or a carriage return is prefixed with `'`;
  - typed numbers are written unchanged;
  - no HTML, links or executable content is produced.
