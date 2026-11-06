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
