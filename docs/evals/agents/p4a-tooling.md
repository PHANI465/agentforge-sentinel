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

Consistency rules added for review finding R46 (each refused, never repaired):
- **Status and the stop boundary.** `status` is `complete` or `incomplete`. A `complete` record has no `stopped`, no comparator not started and **no case not attempted** on any comparator. An `incomplete` record must say where it stopped: for a setup stop, the stopped comparator is the last one that ran and its first not-attempted case is the stopped case; for a comparator-construction stop, the stopped comparator is the first one not started. No other comparator may list cases not attempted. Comparators appear in the planned order.
- **Each row tells one story.** `disposition`: no code, case state `awaiting_approval` (when recorded), and a recorded disposition unless telemetry was `unavailable` (then none: the recommendation is unknown). `inconclusive`: no code, not `awaiting_approval`, no disposition. `refused`: code `agent_capacity_exhausted`, no case state, no disposition, no recorded role attempt. `pending`: an `investigation_in_progress`/`investigation_outcome_unknown` code; it may carry the stored state read afterwards, but stays pending. `error`: a non-typed code and no disposition. A disposition's `kind` and `source` must fit the comparator (`recommend`/`abstain` for workflow comparators, `null` for the single investigator).
- So a wrong hold relabelled `refused` with matching counts, or a complete record whose suffix was moved into `cases_not_attempted`, is refused. This is consistency checking of an editable, unsigned file, not tamper-proofing: a fully coherent rewrite is not detectable from the file alone (the export below checks the file against storage).

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
- **Workflows.** The stored workflow IDs must equal the artifact's.
- **Adopted disposition (R49).** The adoption is rebuilt from storage by the runner's own rule (a workflow's recorded `disposition` and its `basis_run_id`, or the single investigator's one run with a finding). Every recommendation and claim field the artifact records (`source`, `kind`, `operation`, `reason_code`, `basis_run_id`, `workflow_id`, `supported_claims`, `unsupported_claims`) must equal it, and the basis must be a run with a finding in the adopted workflow and scope. A disagreement, or a stored adoption contradicting a recorded `inconclusive`/`refused` outcome, is refused before any bundle or packet exists; nothing is repaired. Exported fields come from storage, labelled `verification: matches stored disposition`. A disposition whose run-artifact telemetry was unavailable is exported from storage labelled `stored only (...)`; stored state found after a `pending`/`error` outcome is labelled as found later. The recorded outcome is never changed.
- **Identity.** Before reading, the export login is refused if it owns (or is a member of the owner of) a mutable table, holds administration attributes or runs as a switched role.
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
- **Bundle check.** Before any packet is built, each bundle's run digest and run artifact are re-validated, and every adopted record must agree with its run row (R49). A bundle edited in one place but not the other is refused.
- **Files.** The packets go in `review/packets.json` and `review/sheet.csv`, with blank scoring columns: `supported`, `acceptable`, `reason_code`, `would_correct` and `correction`. The unblinding key (packet → attempt, comparator, case, run digest, and the sheet binding: each generated row's item, kind and text digest) is written separately to `keys/unblinding-key.json`.
- **Inert text.** Text stays data:
  - JSON escapes it;
  - in CSV, a text cell starting with `=`, `+`, `-`, `@`, a tab or a carriage return is prefixed with `'`;
  - typed numbers are written unchanged;
  - no HTML, links or executable content is produced.

## 4. Summary (`sentinel.agent-eval.summary/1`)

```powershell
uv run --locked python scripts/agent_eval_score.py --root <DIR> [--sheet <completed sheet.csv>]   # -> summaries/
uv run --locked python scripts/agent_eval_score.py --run <run.json> [--run ...]
```

**Before scoring**, every artifact is validated (§1). Each planned case must be in the frozen catalog with a matching runtime digest. A second attempt of the same comparator on the same case is refused (a rerun is reported separately). Every pilot pair that ran must have its artifact. A record that fails any of these is refused, never dropped. Evaluator expectations are read here only, after execution.

Per comparator, with counts beside every rate:

| Metric | Formula |
| --- | --- |
| Counts | attempts, dispositions, inconclusive (by last failure code), refused, pending, error, not attempted |
| Acceptable recommendation | dispositions whose (operation, reason) is in the case's acceptable list, or an explicit `abstain` the case permits / dispositions. A hold on a case listing no hold is unacceptable |
| Wrong holds | the attempt IDs of completed holds on D03, D04 or D11 (and any case without hold). Each is kept, counting 0/1 |
| Useful / unnecessary abstention (workflow comparators) | `abstain` dispositions on `required`/`appropriate` (respectively `acceptable_not_preferred`) cases / dispositions on those cases. **Unobservable for C0/C1**: they have no explicit abstention signal, and an escalate is not an abstention |
| Machine-supported claims (C2, C2-det) | sum of adopted supported claims / sum of adopted supported + unsupported claims. Plus recommends with any unsupported claim / recommends. Never compared with the human rubric |
| Calls | reserved invocations; recorded role attempts (total, n, max, unknown); repeats; pre-submission refusals. Provider requests: `unknown` |
| Request latency | p50, p95 and max by **nearest rank** (the ceil(p·n)-th smallest), with n, over all non-refused attempts. Refusals are reported separately |
| Workflow elapsed | "not measured (150 s gate not demonstrated)" |
| Tokens | `adapter_reported` only if every row is; otherwise `unknown` |

**Human rubric (R47).** Scored only from the generated `review/sheet.csv`, with its key; the key's run digests must be the runs being scored. The sheet is refused unless:
- its columns are exactly the generated ones, every row's packet, item, kind and text match the key's binding, each item appears once and every generated item is present;
- `supported` is blank or `supported`/`unsupported`/`not_checkable`, `acceptable` and `would_correct` are blank or `yes`/`no`, answers appear only in the columns that apply to the row's kind, and a written `correction` has `would_correct = yes`. Free text (`reason_code`, `correction`) is never interpreted.

**Blank is unknown, never "no".** Each metric reports its answered and unanswered counts, and a blank is excluded from that metric's denominator:
- Rubric-supported statements = statements marked `supported` / **all statements the rubric scored** (`supported` + `unsupported` + `not_checkable`), the frozen protocol-v1 §3 denominator. Unanswered statements are counted apart.
- Human acceptable = `acceptable = yes` / packets with `acceptable` answered. Human correction = `would_correct = yes` / packets with `would_correct` answered.
- `review_status` per comparator: `complete`, `partial (N of M answer fields blank; blank is unknown, not no)`, or `not scored (blank sheet)`. A partially answered sheet is never called a completed review.

**Unknown recommendations (R46).** A disposition whose recommendation is unknown (telemetry unavailable) is listed under `recommendation_unknown` and excluded from the acceptable-recommendation denominator (with a note); it is never counted acceptable, unacceptable or a wrong hold. A `pending` attempt whose stored state shows a hold is listed under `wrong_holds.pending_with_stored_hold`, not inferred to be a completed disposition.

**Always shown:** the faults not applied per case, and the hard gates, each "not demonstrated", "not exercised" or `0/0 (not exercised)`.

The summary also states plainly that:
- C2-det and C0 are plumbing and reference only;
- a D11 result alone establishes neither injection success nor resistance;
- no p-value, significance or promotion claim is made.

`summary.md` contains counts and labels only, never role-originated text.
