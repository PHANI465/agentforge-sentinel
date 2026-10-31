# Claude G3B: implement the bounded three-role investigation backend

**Delivered at391effe and changes-requested: use [R34-R36 follow-up](CLAUDE_G3B_REVIEW_FIXES.md) on the existing task branch. Do not restart from the old base.**

Recommended coding assistant: **Claude Opus 5.5, High effort**. This slice changes
transaction boundaries, recovery, concurrency leases and scoped evidence/claim checks.
Use the existing plan; do not change global model settings or enable paid fallback.

## Read and start from the accepted base

Read current main:AGENTS.md and current task/coordination versions of STATUS/TASK_QUEUE,
docs/reviews/G3A-43d9e8a.md, this prompt, docs/agents/G3A-design.md,
docs/agents/G3B-implementation-plan.md, docs/agents/contracts-draft/README.md and
docs/evals/agents/protocol-v1.md.
Codex remains integrator. Cursor can stay inactive; its original seven dirty files and all
accepted worktrees are protected. Other worktrees' files are not your working copy.

**Exact implementation base:** 2919f76a5cad729ea078d5bfb35c226a3d2bff3f.
This accepted integration includes design candidate 43d9e8a plus current acceptance and
instruction records; its pure draft checks pass. It contains no G3B runtime code.
Create branch `task/claude-g3b-workflow` in `E:/PHANI/sentinel-wt/claude-g3b-workflow`
from this exact SHA. Inspect refs/paths first; resume a matching existing task rather than
resetting, rebasing, amending or overwriting unfamiliar work. Record the actual dependency.

## Deliver one complete vertical backend slice

Follow the nine ordered implementation steps in the accepted plan. With explicit operator
choice `SENTINEL_INVESTIGATOR=three-role`, run evidence analyst -> investigator -> reviewer,
with deterministic coordinator, scoped read-only tools, structured claims, persisted steps
and human approval still separate. The existing deterministic single investigator remains
the default, and existing single-Claude mode keeps its current behavior.

Use deterministic role adapters for ordinary checks; the local-only Claude role adapter is
opt-in and keeps all current subscription/isolation checks. This assignment needs **no real
model/subscription call**, final-case evaluation or provider install. Validate local process
and worker lifetime using a real test-owned subprocess/controlled worker, not a billable call.
A manual comparator script may be built, but do not run live comparators automatically.

Freeze the accepted draft semantics. Mechanical promotion to `schema_version="1.0"` and
matching claim-schema name in the new agents namespace is approved; export additive schemas
and port examples. Keep legacy domain/HTTP v1 and v1.1 bytes exactly unchanged. Use explicit
pins for composite workflow, roles/prompts/schemas/tools/policy, and the accepted digest
namespaces. Runtime changes beyond the accepted design need a specific review handoff.

Implement and prove:
- Migration0005: scoped workflow/append-only steps and role links, one running workflow per
  case, least-privilege runtime grants/sequence access. Existing migrations stay unchanged.
- Four allowlisted tools; inject scope/case/account from TrustedContext and stored records.
  Use production runtime privileges, never owner URLs or browser inspectors. Preserve
  decision-time history/profile/disclosure bounds; no hidden labels, gold or cross-session IDs.
- Typed claim verification against actual cited values, correct integer/boolean/currency
  semantics, deterministic bounded rationale from stored facts, display-only notes. Reviewer
  agreement is never authority. Server builds exact hold/escalate parameters and intent.
- Separate workflow(max1) and outstanding-call(max2) leases per process. A timed-out worker
  retains its call slot until actual completion, no repeat after timeout, no late writes.
  Repeat only a resolved eligible failure once within every budget; cleanup releases workflow
  admission on all paths. Inject held/released workers; avoid timing-only race assertions.
- One monotonic deadline; work excludes reserve, terminal uses it. Positive floored
  millisecond budgets, single-host connection, per-operation remaining-time recomputation,
  finite connection/statement/lock/commit handling, and separate fresh bounded recovery.
  The pure deadline spec is not proof of actual PostgreSQL behavior: test both.
- One scope/revision/CAS-guarded terminal transaction, even before any role or between roles.
  Preserve completed runs. Recommend/abstain needs eligible completed investigator basis;
  missing basis or failed/inconclusive workflow creates no intent. Never drop historical runs.
- Honest persistence outcomes: committed -> pre-commit-read CaseDetail only after confirmed
  COMMIT; known refused/rollback ->409 investigation_in_progress with recovery state kept;
  uncertain COMMIT ->409 investigation_outcome_unknown, client re-read. Never retry a terminal
  transaction blindly after an unknown commit. A superseded workflow cannot alter newer state.
- Default/local-Claude compatibility, evidence tamper/stale config/revision/session denial,
  reject/approval expiry and idempotent simulated action replay. Agents create no approval.

## Ownership

New files: src/sentinel/contracts/agents.py; src/sentinel/agents/{__init__,coordinator,
capacity,budget,tools,claims,adapters}.py (other small files in that package if justified);
0005_agent_workflows.sql; contracts/agents/ additive exports/examples; tests/test_agent_*.py;
tests/support/agent_cases.py; scripts/agent_eval.py; ADR0007 and task handoff/run notes.
Narrow existing edits: service.py at the accepted integration points; investigators.py
from_environment (reuse existing guard helpers without weakening them); db/roles.py;
export_contracts.py; docs/api/README.md; owned agent/evaluation documentation.

Additionally authorized: **observability.py fixed safe-log fields only**, if needed for
workflow_id/role/attempt metadata from the design. Keep an explicit scalar allowlist and
bounded metric labels; no raw prompts/output/notes, secrets, arbitrary field acceptance or
tracebacks. Add meaningful tests. Prefer existing safe keys where sufficient.

API docs must list **both** additive codes, capacity_exhausted and outcome_unknown using
their full accepted names. Correct client guidance so a handled 409 outcome_unknown is not
mistaken for a confirmed result. No route/response shape change is authorized in G3B.

Do not edit web/, current tests/support files, src/sentinel/contracts/{v1,http_v1,guards}.py,
legacy contracts, existing migrations, C03/C04/p1 model/data/eval artifacts, dependency or
npm lockfiles, checker timeouts, skip allowlist, CI workflow or central STATUS/TASK_QUEUE.
Request any necessary extra path with a concrete example/result instead of silently expanding.
No framework migration, hosting/BYOK, new providers/dependencies, remote, push or deployment.

## Checks and handoff

Write meaningful failing-first regressions and record the reason they fail on the accepted
base; avoid counting an import/setup error as proof of a behavioral regression. Implement
all 15 development cases for C2-det, and compare C0 only where its catalog applicability
permits; do not fabricate unsupported baseline coverage or add pytest skips. Never feed
case evaluator/fault metadata to roles. This proves plumbing/safety, not agent quality.

Test real PostgreSQL using the runtime role: terminal commit inside reserve, actual blocked
lock/statement budgets, lost connection, known rollback, uncertain COMMIT and recovery,
zero-role/between-role cases, cross-session boundaries, races and complete historical runs.
Clean up only exact test-owned processes/state; preserve recovery on unconfirmed cleanup.

On the final clean commit: six-command Windows strict gate, JUnit structured skip validation
from that same pytest run, unchanged HTTP export, new+legacy domain exports, package wheel/
sdist check with migration5/agent modules, read-only ML reproduce; native Ubuntu equivalent
backend gates, sequentially with Windows; frontend type/build/unit and unchanged 19-test
browser suite once on the integrated candidate. Use existing locked dev+ml tools and owned
Linux clone; no tool installation needed. Only the existing opt-in live-Claude skip is
allowed. Do not extend timeouts or weaken assertions to get a pass. Record actual gaps.

Commit explicit owned paths; **PHANI465 <pgavara1@asu.edu> sole author and committer**, no
coauthor/AI/session trailers. Return exact tested SHA, base, changed files, failure-first
results, final per-platform checks, cleanup and unverified limits. Do not merge main or
start G3C/final/live evaluation. Codex reviews and integrates the implementation separately.
