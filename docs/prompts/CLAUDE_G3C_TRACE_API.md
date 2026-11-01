# Claude G3C-A: investigation trace read contract and API

Completed: exact 16b67fd is accepted under [the final review](../reviews/G3C-A-16b67fd.md).
This assignment is historical. Continue with [G3C-B](CLAUDE_G3C_TRACE_UI.md) in a new
worktree from its named accepted dependency, preserving the tested API branch.

Recommended coding assistant: **Claude Opus 5.5 / High**. This task needs careful
versioning, scoped evidence projection and consistent reads, rather than new orchestration.
These settings select the coding assistant; do not call Sentinel's live provider.

## Base and ownership

Read current main AGENTS.md, docs/STATUS.md, docs/TASK_QUEUE.md,
docs/reviews/G3B-e23a7cd.md, docs/releases/G3B-main-integration-2026-11-01.md,
docs/agents/G3A-design.md (trace/read-model sections) and the accepted G3B implementation.
The accepted application integration is a7c71f553328b5872df53039daf572ad3b8fda81.
Start a **new branch/worktree from current published main** (which may add documentation
only after that integration): task/claude-g3c-trace-contract at
E:/PHANI/sentinel-wt/claude-g3c-trace-contract. Record its exact base. Do not edit the
preserved G3B, G3A or original Cursor checkout. Confirm the release record shows successful
integrated gates; if it does not, report that missing prerequisite rather than assuming it.

## Deliverable

Implement only G3C-A: the additive read-only trace HTTP contract/API, generated v1.2 export,
reproducible examples, focused real-Postgres tests and an exact UI-consumer handoff.
**No UI work yet.** Codex accepts this commit/contract before G3C-B consumes it.

The proposed route is GET /v1/cases/{id}/investigation-trace. The accepted agents-1.0
TraceSummary is a starting point, not proof that all UI semantics already fit. Inspect
persisted records first. Write a short docs/api trace contract note defining the response,
then implement that declared behavior on the same task branch for review. Resolve:

- Which workflow is selected by default, deterministic ordering for timestamp ties, how
  repeated/recovered workflows are identified, and whether prior traces are available.
  Keep the API minimal; any pagination/selector must have exact validation semantics.
- A legitimate case with no three-role workflow (including a legacy single investigator),
  a running workflow, completed/abstaining/inconclusive/recovered workflows, zero role
  attempts, failure between roles, failed tools/claims and a repeat/revision. Absence is
  distinct from zero or a failed attempt. Do not fabricate missing historical facts.
- Expose safe server-owned provenance, ordered persisted steps, role attempts/status,
  available claim checks/citations, tool results, dispositions, limits and observable usage
  needed for an honest trace panel. Clarify recorded role attempts vs submitted provider
  calls; pre-submission budget failures count as attempts, not known usage.
- Unknown usage/latency is not zero; per-process limits are not provider-wide limits.
  Show what is persisted; do not infer live worker completion or provider billing.
- Read a consistent stored snapshot. A GET must not run agents/tools, recover or mutate a
  workflow, approve anything or change case state. An expired-but-not-recovered stored
  workflow remains distinguishable from confirmed recovery. Preserve all existing actions.

Use the existing scope/capability patterns and restricted runtime connection. Cross-session
or tenant identifiers must not reveal case existence or traces. Return validated DTO fields
only: no credentials, owner connection strings, raw provider payloads/prompts, exception
messages or internal reasoning traces. Short existing untrusted notes remain inert text;
never turn rationale/claim text into permission, HTML or an executable instruction.

Preserve **byte-identical legacy v1 and v1.1 OpenAPI/examples**, agents-1.0 schemas/examples,
p1 model/data/evaluation files, existing investigator defaults, migrations, role/tool
budgets and R34-R37 semantics. Add new versioned HTTP DTOs/projections rather than changing
frozen shapes. If the accepted draft cannot express the required read model, document the
precise additive v1.2 shape in the contract note. No database migration or new dependency
is expected. Do not broaden grants or change an accepted contract silently.

## Owned paths

HTTP DTO/API/service read projection; scripts/export_http_contract.py and its direct export
fixtures/checks; new contracts/http v1.2 files and examples only; new trace API tests;
docs/api trace notes; a new decision record if a real decision is needed; this branch's
handoff. Prefer a small separate projection module if it keeps workflow code unchanged.
Do not edit web/, the coordinator/budget/adapter machinery, existing frozen contract files,
model artifacts, dependency/lockfiles, CI/skip policy/checker timeout or central STATUS/
TASK_QUEUE. Request only a concrete unavoidable ownership exception, not routine confirmation.

## Evidence and handoff

Write meaningful regressions first. Verify authorization over real HTTP with disposable
Postgres and the runtime role; cover all declared empty/partial/terminal states, repeated
attempt selection/ties, safe text and absence of secret-bearing fields, and consistent
ordering/content against the stored records. Failed tests must reach the missing behavior,
not only fail to import a new module. Include a reproducible example-drift check and prove
old frozen bytes remain unchanged. No live call, no final-case quality evaluation.

Run relevant focused checks while developing. On the final clean owner-authored commit,
run the existing Windows/native Ubuntu backend gates sequentially, validate JUnit with the
single allowed live-Claude skip, domain/HTTP/package checks and read-only ML reproduction.
The unchanged Windows frontend/browser suite is the compatibility check; do not claim its
old 19 cases verify a new trace UI. Keep assertions/timeouts/skip policy unchanged. Preserve
any intermittent failures with safe diagnostics; a later pass is not a root-cause diagnosis.

All new commits: PHANI465 <pgavara1@asu.edu> as sole author and committer, no trailers,
no history rewriting. Commit explicit owned paths. Report exact tested SHA, fixtures and
selection semantics, actual results, cleanup and gaps. No main merge, push, remote, hosting,
paid usage or live provider. Codex reviews/freezes this contract before the UI task.
