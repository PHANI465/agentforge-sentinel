# G3D-P4a: evaluation tooling, one coherent implementation batch

Recommended coding assistant: **Claude Opus5.5 / High**. This task crosses accounting,
database scope, lifecycle ownership and offline metric definitions. Sentinel verification
uses deterministic adapters only; coding-assistant development use is distinct from an
app provider call. No live comparator or auth command is authorized by this assignment.

## Base, worktree and completion boundary

Read current task/coordination:AGENTS.md, STATUS/TASK_QUEUE and
[P4 acceptance](../reviews/G3D-P4-cee83f9.md) with git show. Accepted plan is exact
cee83f92677a3aab2c46f7a802c5cf7c0c695344, now integrated into current main as docs.
Read [the plan](../artifacts/AgentForge_Sentinel_G3D-P4_Development_Evaluation_Plan_2026-11-06.md),
frozen protocol-v1, dev-cases-v1 and evaluator runbook. Their historical pending-P4a
sentences are superseded only by this dispatch; R44/R45 are closed.

Create task/claude-g3d-p4a-tooling at E:/PHANI/sentinel-wt/claude-g3d-p4a-tooling
from current published main. Record its exact SHA and confirm it contains accepted
cee83f9 and tested G3D-P3 integration495c7d3. Do not reuse the plan/P3 checkouts or
Cursor's original checkout. One editor; one coherent branch for milestones A-E below.
You may finish these internal milestones without an intermediate Codex approval after
each; hand off the complete tested candidate for independent review. Do not merge main.

Read agent_eval.py and its authority/failure tests; existing local_stack Stack and
database lifecycle; trace/workflow storage and grant map; agent_cases runtime seeding.
Reuse these foundations. No new orchestrator, hosting service or production observer.

## A. Versioned run artifacts and honest measurements

First write a small documented versioned evaluation-artifact contract with example
fields/units/statuses. This is a local evaluator format, not a new HTTP/domain contract.
Implement producers/consumers against it on this same branch; preserve existing runner
CLI/defaults, run() return shape and R41/R42 setup/attempt/telemetry failure semantics.
Prefer additive fields. Do not make an old report appear to contain new measurements.

- Record attempt identity, comparator/case catalog ID, actual scoped tenant/session/case
  IDs and workflow IDs when available, runtime digest, exact source/config pins, alias,
  platform, start/end and request latency. IDs are allowed in private machine reports;
  bearer tokens, URLs/passwords/auth output/CLI envelopes are not. Missing IDs from
  setup failure remain missing and never become fake attempts.
- Workflow_elapsed_ms remains null/not measured; the150s gate is not demonstrated.
  Do not subtract wall-clock timestamps, use the terminal0 marker or rename request
  latency to obtain this metric. Recorded role intervals pair start/end by agent_run_id,
  with missing endpoints unknown and pre-submission failures labelled. They include
  persistence/validation and are not provider latency.
- Read the actual service instance's capacity.snapshot after the request, with an
  explicit observation cutoff and service/process scope. Existing safe late-return
  events may be observed up to that cutoff, but an unobserved late return is unknown,
  not zero. Do not wait without a bound, cancel/force-join workers, patch coordinator
  timing or claim provider-wide counts. Do not add production instrumentation.
- Keep reserved allowances, stored role attempts, observed adapter submission and
  provider/CLI reach distinct. Unknown reach, usage, model version and quota stay unknown.
  A failed preflight and a pre-submission budget refusal are not billable calls. No
  money figure. Manual quota/model-version annotations need a recorded source/time;
  do not contact an account to fill them during this task.

## B. Safe deterministic pilot orchestration

Provide a small local supervisor for a reproducible deterministic preflight and a
seeded schedule of the planned pairs. Use D01-D04/D11 as frozen development inputs.
Run C0/C2-det only in actual verification. Build a plan/reservation mechanism for later
live pairs (1 C1,5 C2; no start without the full allowance), without running those pairs.
Do not automatically chain a preflight into live calls. Any future live flag must be
explicit, preserve the existing consent boundary and never enable a fallback. Tests
may intercept live submission; no real Claude executable/auth call is made.

- Use a newly created pilot-owned root and explicit state. Reuse local_stack.Stack,
  start_database/stop_database and their existing identity checks for a database-only
  cluster, or an equally concrete already-reviewed lifecycle path. Do not implement a
  second PID/group/port-discovery system or edit the existing helpers. Never adopt an
  old .agent/devdb or assume clean Git proves ignored state is unused. Use free ports.
- One fresh uniquely named database per runner invocation; deterministic preflight may
  run both controls on one fresh DB as the accepted plan specifies. Operator does only
  DB/schema/grant/session provisioning and verified lifecycle/drop. Actual case work
  remains runtime; no owner fallback. DSNs go via environment, not argv or console.
- Keep a private owned manifest mapping only this pilot's resources and run artifacts.
  Validate ownership/path/identity before stop/drop; refuse ambiguous/foreign state
  and keep recovery. No kill-by-name, broad deletion, stale-run adoption or changes
  behind helper ownership checks. No API process is needed solely to call the runner.
- Preserve each outcome/report and check nested status/authority/disposition counts.
  On setup/refusal/error/quality-stop keep earlier attempts, mark the pass incomplete
  and enumerate not-attempted pairs. No silent retries or overwritten first reports.
  A real wrong hold must be scored unacceptable before/while the supervisor stops.
- Keep DBs needed for private human scoring stopped and recoverable until explicit
  owned cleanup; document resource retention and safe cleanup commands. Deterministic
  smoke may fully drop its own data after verifying exports/round trips. No production
  retention promise or final-case generation. Failures keep enough nonsecret recovery
  metadata; secrets never go in the public run record or failure output.

## C. Scoped read-only extraction and partially blinded review packets

Use the runtime identity and a consistent read-only snapshot. Select only the manifest's
actual tenant/session/case/workflow relationships, then validate those relationships
against storage. Refuse a foreign ID or tampered mapping rather than broadening a query.
Do not silently recover/investigate/write when exporting. Keep unknown/running trace
states honest. Operator is not an export identity.

- Include factual evidence actually available, recorded model/rule/agent provenance in
  the private machine bundle, adopted disposition/claim checks and recorded attempts/
  tools. Select the adopted investigator by basis_run_id, not the last role or attempt1.
- Generate UTF-8 JSON/CSV review sheets with a seeded random order, opaque packet IDs
  and a separate private unblinding key. Human packets omit comparator/config/role names,
  pin hashes, expected answers and source filenames that reveal them. Blinding is partial;
  output shape may reveal the system. Never claim an independent human scored a template.
- Render role-originated text inertly. No HTML, executable content or links invented
  from model text. Escape spreadsheet formula-like strings in CSV output without
  corrupting typed numeric fields. No new frontend/dependency is needed.
- Capture a post-export row snapshot/count proof that exports did not mutate cases,
  workflows, approvals or actions. Real runtime-role tests must reject writes. Keep
  validated notes/rationales private; never dump raw CLI/auth stdout to any artifact.

## D. Offline scoring and descriptive summary

Evaluator expectations enter this module after case execution only, never role/tool
inputs. Validate the run/catalog/digest association before scoring; refuse mismatched
or missing records rather than quietly dropping them. Keep per-comparator attempt,
disposition, inconclusive/refusal/pending/error and not-attempted counts together.

- Compute supported metrics from known structured data with hand-verifiable formulas:
  accepted operation/reason or permitted explicit abstention, known abstention categories,
  C2 adopted-claim checks, outcome/call-reservation/repeat counts and request-latency
  p50/p95/max with a stated quantile convention and sample count. Keep every attempt in
  the right denominator. No p-value, significance or promotion claim from a tiny pilot.
- An ordinary escalate is not automatically an abstention. If C1/C0 lacks a reliable
  explicit abstention signal, mark that metric unobservable or use separately sourced
  human annotation under the frozen rubric; do not invent a classification rule.
- Common rubric support/correction/unsupported factual exposure requires completed
  human sheets. Blank sheets mean not scored. Keep C2 machine-supported claims separate
  from human-supported statements; do not treat keyword checks or an LLM as ground truth.
- Wrong holds on D03/D04/D11 contribute0/1 and remain present even if a run stops. A
  D11 result alone establishes neither injection success nor resistance. Existing
  faults_not_applied must be prominent. Unexercised hard gates are not demonstrated;
  zero denominators print n/a(0/0), missing values remain unknown/null, real0 stays0.
- Summary labels are development/tooling verification. C2-det is plumbing only, never
  evidence that live C2 beats C1. Preserve negative/neutral results and all first attempts.

## E. Verification, ownership and handoff

Own scripts/agent_eval.py plus new scripts/agent_eval_report.py,
scripts/agent_eval_pilot.py and scripts/agent_eval_score.py (small shared evaluator
utilities may live in a new scripts/agent_eval_support/ package if useful). Own new
tests/test_agent_eval_reporting.py, test_agent_eval_pilot.py, test_agent_eval_scoring.py
and minimal tests/fixtures/agent_eval_p4a/ records. Narrow existing evaluator tests may
be updated for additive outputs without weakening their authority/failure assertions.
Own docs/evals/agents/p4a-tooling.md, a narrow evaluator-runbook update and your handoff.

Do not edit production src, local_stack.py or browser lifecycle code, the accepted plan,
frozen protocol/cases, HTTP/domain contracts, migrations/grants, model/data/evals assets,
UI, dependencies/locks, CI/skip policy/checker timeouts or central coordination. A need
outside those paths gets a concrete evidence handoff, not a unilateral architecture change.
Use existing stdlib/Pydantic/psycopg; no new dependency or protocol version is required.

Keep logical commits for A-D, focused checks as you go, one final complete verification
after all source edits. Do not rerun the entire backend gate after every internal commit.
Tests must cover hand-calculated rates/quantiles/zero denominators, wrong-hold retention,
unknowns, adopted-run selection, scoped read-only real DB exports, partial/failed reports,
blinding/key separation, hostile Unicode/formula text, secret canaries and lifecycle
refusal/recovery. Fake/injected worker outputs are test fixtures, never live evidence.
Prove a deliberately broken scope filter and a deliberately censored wrong result are
caught. New functionality can be absent on baseline; do not count import errors as a
meaningful reproduced production defect.

Run one real deterministic pilot of the five planned development cases, export/score
and build blank human sheets; verify no approval/action, no data mutation by exports,
authority and ownership/cleanup. Do not report a completed human evaluation. Then final
exact-clean Windows and native Ubuntu full gates sequentially: six strict commands,
same-run JUnit/exact skip validation, frozen HTTP, package and read-only ML. Keep2700s
per command and all individual deadlines/assertions/skips. No new browser run solely for
evaluator/tests/docs; say it was not run. Preserve failures; diagnose before any justified rerun.

All new commits: PHANI465 <pgavara1@asu.edu> sole author AND committer, no trailers,
history rewrite or global Git change. Commit explicit owned paths. Return exact base/SHA,
format/version, real control results vs fixtures, negative controls, checks, cleanup,
private evidence locations and gaps. No main merge, provider/auth call, final cases,
new spending, external remote/push or deployment. After this handoff you may take the
independent AN01 design assignment from the batch driver without waiting for P4a review.
