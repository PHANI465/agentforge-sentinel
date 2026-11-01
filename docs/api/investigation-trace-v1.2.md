# HTTP v1.2: investigation trace read contract (G3C-A)

Status: **candidate for Codex review; not accepted.** G3C-B (the trace UI) must not consume it
until Codex accepts it by commit. Base: main b69b8bc (application a7c71f5, accepted G3B).

v1.2 adds one read-only route. Everything else is unchanged:

- `contracts/http/openapi.v1.2.json` is the active snapshot (`info.version` 1.2.0).
- `openapi.v1.json` (legacy) and `openapi.v1.1.json` are **frozen** and checked by SHA-256 in
  `scripts/export_http_contract.py`. The v1 and v1.1 example sets are still regenerated and
  must stay byte-identical.
- Every v1.1 path, method, request body, response and security entry is identical in v1.2,
  and every v1.1 component schema is byte-identical (tested in
  `tests/test_http_contract_v12.py`).
- The agents-1.0 schemas, examples and `TraceSummary` are unchanged. v1.2 reuses their
  nested models (`ToolResult`, `ClaimCheck`, `Disposition`, `Usage`, `WorkflowLimits`, the
  role outputs) as they are.
- No migration, grant, dependency, investigator default, budget or workflow change.

## Route

`GET /v1/cases/{case_id}/investigation-trace[?workflow_id=<uuid>]` returns
`InvestigationTrace`.

| Check, in order | Result |
| --- | --- |
| Missing or invalid bearer token | `401 unauthenticated` |
| Session lacks `read_case` | `403 permission_denied` |
| `case_id` or `workflow_id` is not a UUID | `422 invalid_request` |
| Case not in the caller's tenant **and** session (missing or foreign) | `404 not_found` |
| `workflow_id` is not a workflow of this case in this scope | `404 not_found` |

A foreign case, or a foreign workflow id, is indistinguishable from a missing one. The only
query parameter is `workflow_id`. Unknown query parameters are ignored, as on every other
route.

**The GET never writes.** The whole response is read inside one
`REPEATABLE READ READ ONLY` transaction, so all parts come from one stored snapshot and the
database refuses any write. It never runs a role or tool, recovers or terminates a workflow,
expires an approval or changes a case. Recovery still happens only through
`POST /v1/cases/{id}/investigations`, as in G3B.

## Selection and ordering

- **Workflows of a case** are ordered by `case_revision`, newest first. Each claim moves
  the case `open → investigating` by compare-and-set, so every workflow of a case has a
  strictly larger `case_revision` than the one before. Clock ties in `started_at` therefore
  do not affect the order. `started_at`, then `id`, break a tie that the claim rule makes
  impossible.
- **Default selection:** without `workflow_id`, `selected` is the newest workflow (highest
  `case_revision`), whatever its status. With `workflow_id`, it is that workflow.
- **Prior traces are available.** `workflows` lists at most 25 newest summaries.
  `workflow_count` is the total. Any listed or older workflow of the case can be read with
  `workflow_id`. There is no other pagination.
- **Repeats, revisions and retries:**
  - A retry after an inconclusive or recovered workflow is a **new workflow** with its own
    id and a higher `case_revision`.
  - A repeat after a resolved provider failure is attempt 2 of the same role, in the same
    workflow.
  - An investigator revision (tool follow-up, or a reviewer challenge) is a later
    investigator attempt row with `attempt` 1. `attempt` counts repeats, not revisions.
- **Inside one workflow:**
  - `attempts` are ordered by insertion (`agent_runs.seq`);
  - `steps` by `step_seq`. It is unique per workflow and can have gaps: a step whose COMMIT
    was uncertain is skipped, never renumbered;
  - `tool_results` by their step's `step_seq`.

## Empty, partial and terminal states

| Stored situation | Response |
| --- | --- |
| Case never investigated | `workflow_count` 0, `workflows` [], `selected` null, `legacy_investigator_runs` 0 |
| Only the single (legacy) investigator ran | as above, with `legacy_investigator_runs` N. Those runs remain in `CaseDetail.agent_runs`. No workflow is invented for them |
| Workflow running (live or crashed) | `status` running, `terminal_by`/`finished_at`/`disposition` null, `recorded_role_invocations`/`recorded_tool_calls` null, and the attempts and steps persisted so far |
| Running and past its deadline, not recovered | as above, with `deadline_status` `past_deadline`, or `recovery_due` once past `deadline_at` + 30 s. It stays `running` until a POST recovers it |
| Recovered | `status` inconclusive, `terminal_by` recovery, `disposition.inconclusive_code` interrupted. An attempt that was running then has `failure_source` `workflow_terminal` |
| Ended before any role | terminal record with `attempts` [] and `recorded_role_invocations` 0 |
| Failure between or within roles | the earlier completed attempts; the failed attempt with its `failure_code`; no later attempts |
| Completed (recommend or abstain) | `disposition` with `basis_run_id`; that attempt has `basis` true and the server-rendered `finding` |

Absence is never shown as zero:

- an unknown count or measurement is `null`, not `0`;
- an empty list means the record has none;
- a failed attempt is not omitted.

## `InvestigationTrace`

| Field | Meaning |
| --- | --- |
| `case_id`, `case_state`, `case_revision` | the case in the same snapshot |
| `read_at` | the server clock at the read. `deadline_status` is relative to it |
| `legacy_investigator_runs` | the number of the case's `agent_runs` with no workflow (single-investigator mode) |
| `workflow_count`, `workflows` | all workflows of the case, and the newest at most 25 as `WorkflowSummary` |
| `selected` | a `WorkflowTrace`, or null when the case has no workflow |

`WorkflowSummary` has `id`, `case_revision`, `status`, `terminal_by`, `started_at`,
`deadline_at`, `finished_at`, `disposition_kind` and `inconclusive_code`.

### `WorkflowTrace`

- **`workflow`** holds:
  - the stored record's `id`, `case_revision`, `status`, `terminal_by`, `started_at`,
    `deadline_at`, `finished_at`, `config`, `tool_profile`, `input_snapshot_sha256` and
    `disposition`;
  - `recorded_role_invocations` and `recorded_tool_calls`: the terminal record's counters,
    and **null while running**. The stored running body still has its start-time zeros,
    which are not measurements;
  - `deadline_status`: null when the workflow is terminal. Otherwise `before_deadline`,
    `past_deadline` or `recovery_due`.
- **`limits`** is the pinned `WorkflowLimits`, only when this server's configured three-role
  workflow has exactly the stored `config` digest. Otherwise it is null (unknown): the
  digest names the limits, but the database does not store the document. Times are
  provisional defaults. `max_live_workflows_per_process` and
  `max_outstanding_calls_per_process` are **per API process** admission limits. They are
  not provider-wide or account-wide limits.
- **`attempts`**: one `RoleAttempt` per **recorded role attempt**, meaning a `role_started`
  step and its `agent_runs` row. The fields are:
  - `agent_run_id`, `role`, `attempt`, `status`, `failure_code`, `started_at`,
    `finished_at` and the role `config`;
  - `failure_source`: `role_step` when the coordinator recorded the failure; `workflow_terminal`
    when the terminal or recovery transaction closed a still-running attempt; else null;
  - `worker_unresolved`, from the `role_failed` step. It is null when there is no such step;
  - `output` and `output_sha256`: the validated role output from `role_completed`. They are
    null otherwise;
  - `claim_checks`: the server's recorded checks of this attempt's claims, or null when none
    was recorded. G3B records them only for the investigator attempt that went to
    verification. Analyst checks are computed for the investigator's input but **not
    persisted**, so they are null, not recomputed here;
  - `elapsed_ms`: the end step's `elapsed_ms` minus the `role_started` one. That is
    coordinator time including persistence, not provider latency. It is null without a
    recorded end step;
  - `usage`: the adapter's usage from `role_completed`. It is null when none was recorded,
    for a failed or running attempt (unknown, **not zero**). `not_applicable` means no
    provider was involved (deterministic roles);
  - `basis` and `finding`: whether this is the disposition's basis run, and its
    server-rendered finding.

  **An attempt is not a provider call.** The stored records cannot tell whether a provider
  call was submitted for a failed attempt. For example, the pre-submission budget recheck
  (R35) fails a recorded attempt as `budget_exhausted` with nothing submitted. Such an
  attempt counts in `attempts` and `recorded_role_invocations`, with no usage.
- **`steps`** are the persisted `StepRecord`s without `workflow_id` and `usage`:
  - `seq`, `kind`, `state`, `role`, `agent_run_id`, `attempt`, `tool`, `tool_result_id`,
    `output_sha256`, `checks`, `failure_code`, `worker_unresolved`, `elapsed_ms` and `at`;
  - step-level usage is omitted because `role_failed` and tool steps store `not_applicable`
    by construction. Per-attempt `usage` above is the only usage field;
  - the `workflow_terminated` step has `elapsed_ms` 0 by construction.
- **`tool_results`** are the stored `ToolResult` payloads of `tool_executed` and `tool_denied`
  steps, including denied ones.
- **`usage_summary`** has:
  - `reported_attempts`, `not_applicable_attempts` and `unknown_attempts` (unknown, or no
    usage recorded);
  - `input_tokens` and `output_tokens`: sums over reported attempts only, and null when none
    reported.

  These are adapter-reported token counts for this workflow, **not provider billing**.
  Nothing about a late worker's completion is inferred.

## Safety of the response

- Responses are validated DTO fields only. They never contain bearer tokens, credentials,
  connection strings, tenant or session ids, the `AgentRun.scope`, raw provider output,
  prompts, exception messages or reasoning traces.
- Role outputs are the coordinator-validated agents-1.0 models; anything else was refused
  as `invalid_output`.
- `note` (at most 400 characters) and `finding.rationale` are untrusted display text. Render
  them as inert text. Never treat them as HTML, a link target, an instruction or a
  permission. Claims, verdicts and notes never authorize anything; approval stays the
  separate human step.

## Examples

`contracts/http/examples-v1.2/` is regenerated by the deterministic three-role workflow
(`scripts/export_http_contract.py`; `--check` compares bytes):

| File | Shows |
| --- | --- |
| `trace_no_workflow` | a case never investigated |
| `trace_legacy_investigator` | a case investigated in single-investigator mode |
| `trace_completed_recommend` | recommend. The analyst's three follow-up requests give 30-day history `ok`, profile `unavailable` and 7-day history `denied` (`budget_exhausted`, over the analyst's two follow-ups) |
| `trace_abstain_after_challenge` | a contradiction, a reviewer challenge, a revision, then abstain |
| `trace_repeat_after_provider_failure` | an investigator attempt 1 failed, then attempt 2 completed |
| `trace_zero_roles` | a transition limit exhausted before the first role |
| `trace_running_between_roles` | a crash after the analyst, before the deadline |
| `trace_running_recovery_due` | the same workflow past its deadline and grace, still running |
| `trace_recovered` | after the POST that recovered it |
| `trace_retry_latest`, `trace_retry_prior` | the default newest workflow after a retry, and the prior one by `workflow_id` |
| `trace_untrusted_note` | an analyst note with markup and instruction-like text, returned verbatim as data |
| `error_trace_not_found`, `error_trace_workflow_not_found`, `error_trace_invalid_workflow_id`, `error_trace_permission` | safe errors |

These examples are deterministic plumbing fixtures, not evidence of agent quality. Each
scripted role advances the example clock by 2 s, so `elapsed_ms` values are reproducible.

## For the UI consumer (G3C-B), after acceptance

- **Inputs:** read the accepted commit with `git show`, not a working tree:
  - `contracts/http/openapi.v1.2.json` (SHA-256
    `b52f8fd4d323f59565b3e1148557cb85221b76c793377e021c32f9c877e5b053` at this candidate);
  - the 16 files in `contracts/http/examples-v1.2/`;
  - this note.

  Record provenance as for the v1.1 fixtures.
- **Call:** `GET /v1/cases/{id}/investigation-trace` once per case view, plus
  `?workflow_id=` for a prior workflow from `workflows`. Never call `POST …/investigations`
  to refresh a trace; that request can recover a workflow.
- **Show absence honestly:**
  - `selected` null with `legacy_investigator_runs` > 0 means "investigated by the single
    investigator; no workflow trace". With 0, it means "no investigation recorded";
  - null counters, usage or `elapsed_ms` mean "not recorded". Never show them as 0;
  - `limits` null means "limits unknown to this server", not "unlimited".
- **Running workflows:** `deadline_status` `recovery_due` means "overdue; not yet
  recovered". Do not present it as recovered or failed. Recovery is
  `terminal_by: recovery`.
- **Attempts are not provider calls.** Label `attempts` as recorded role attempts. The
  `usage_summary` token sums are adapter-reported counts, not billing. Per-process limits
  are labelled per API process.
- **Text:** render `output.note` and `finding.rationale` as inert text only. Never use them as
  HTML, Markdown links or an action. The trace shows no approve or execute control; those
  stay on the existing approval flow.
- **Unchanged:** the 19 existing browser cases verify the existing UI only. They do not cover
  a trace view.
