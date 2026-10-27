# Claude G3A multi-agent contracts and evaluation design

Recommended development settings: Claude Opus (the available Opus option on the owner's
existing plan), effort High. This task needs architectural reasoning about role permissions,
persistence and evaluation. In Claude Code use /model opus and /effort high, or the model
picker's effort control. This selects the coding assistant, not an application runtime model.

Read current main:AGENTS.md and the latest task/coordination versions of docs/STATUS.md,
docs/TASK_QUEUE.md, docs/PROJECT_PLAN.md, docs/reviews/H01.md and this prompt through git show.
Read the actual current contracts, service investigation boundary, Investigator interface,
artifact pins and approval/execution checks. Do not rely on an old chat or a dated snapshot.
Codex remains the owner-designated integrator. Cursor can stay inactive while quota is
exhausted; its required contribution is already delivered and its seven saved edits remain
untouched. This is an application-runtime design task, not coding-assistant delegation.

## Base and worktree

The exact application dependency is accepted H01 f091a34c2ed3f6636625b3141be88d86cd5307dd,
which includes the accepted N2-N7 release. Create task/claude-g3a-design in
E:/PHANI/sentinel-wt/claude-g3a-design from that commit. Inspect refs/paths first; resume an
existing matching task without reset/rebase, and report any mismatched state. Record the
actual base. Current coordination contains later documentation only; read instructions from
the named ref rather than assuming another worktree's files are your copy.

## Deliver one concrete design package

Own docs/agents/, docs/evals/agents/ and your branch handoff. Do not edit src/, migrations,
public/domain contracts, dependencies/lockfiles, model/data/evaluation artifacts from C03/C04,
web/, tests/support/, scripts/, central STATUS/TASK_QUEUE or accepted checkouts. Put proposed
schemas and example payloads under docs/agents/contracts-draft/, not the frozen contracts/.

Deliver:
1. docs/agents/G3A-design.md: implementation-ready state machine, data ownership, integration
   points with exact source file/function references, and a small worked fraud case.
2. docs/agents/contracts-draft/: proposed typed schemas and representative valid/invalid
   messages, role findings, tool requests/results, trace summaries and final dispositions.
   Include compatibility/error semantics and whether an HTTP revision is actually needed.
3. docs/evals/agents/protocol-v1.md: metrics, development versus final evaluation boundaries,
   comparator configurations, cost/latency reporting and security acceptance criteria.
4. A small development-case catalog with expected observable facts, permitted conclusions,
   appropriate abstention and failure behavior. Mark unimplemented paths explicitly.
5. docs/agents/G3B-implementation-plan.md: one narrow vertical slice, owned files, migrations
   if justified, acceptance checks and ordered UI/backend dependencies. Keep it executable
   as the next task rather than a catalog of every possible framework or feature.

The design must resolve the choices below with concrete defaults and examples. Keep the
package focused; do not generate an app skeleton or claim mock-only multi-agent delivery.

## Target product behavior

Start with three sequential roles behind an explicit operator choice, while preserving the
current deterministic/single-investigator default and its HTTP/approval path:
- Evidence analyst: obtains only scoped decision-time facts and identifies missing evidence.
- Investigator: proposes an allowed recommendation with supported factual claims.
- Reviewer: challenges unsupported claims or contradictions and can request abstention or
  escalation. Agreement is not a vote that authorizes action.

A deterministic coordinator owns role identity, allowed transitions, evidence access,
budgets and final disposition. Agents cannot choose tenant/session/actor IDs, grant tool
capabilities, approve cases or execute simulated actions. Server code still builds exact
action parameters and the human separately approves and executes.

Use the established Python/FastAPI/PostgreSQL/AgentForge design. Do not scaffold eve,
LangGraph or another runtime, introduce an AI gateway or add provider dependencies as a
default. The existing one-investigator interface has a narrow fact view; identify its real
limitations and propose the smallest reviewed extension instead of pretending it already
has evidence retrieval or durable multi-agent trace support.

## Required design decisions

- Define the role/coordinator state machine, allowed follow-ups and an explicit inconclusive
  path. State when a case can have an intent and when it cannot. Map this to existing case
  revisions, failed/recovered investigations and evidence/policy/config pins.
- Define structured claims that can be checked against server-derived facts and snapshot
  provenance. An existing evidence ID proves existence, not semantic claim truth. Numeric
  facts should be rendered/verified from stored values. Explain human or independent rubric
  review for free-text claims; do not call another model's agreement ground truth.
- Define a minimal read-only tool registry. The server injects scope and validates IDs;
  tools cannot run arbitrary SQL, shell commands, filesystem reads, web browsing or MCP.
  Use production TrustedContext/runtime-role boundaries; browser inspectors and cluster-owner
  connection URLs must never become agent tools.
  Preserve decision-time history/disclosure boundaries and exclude simulator truth, future
  labels and benchmark gold from runtime inputs.
- Pin the composite workflow, role configurations, tool profile and policy versions. Propose
  persisted role boundaries and attempt records so interruption/retry is auditable. State
  where resumption is safe, and where an uncertain provider completion may require a
  bounded repeat. Do not claim exactly-once model billing or force-stop of late threads.
- Choose hard initial limits for transitions, follow-ups, tool calls, elapsed time and
  concurrency, with reasons. Declare token/usage unknown when the adapter cannot measure it;
  do not promise a monetary cap from an unavailable meter. No unbounded delegation loop.
- Preserve rejection, approval expiry, stale revision, snapshot changes, idempotent action
  retry and cross-session denial. Give concrete status/error/outcome examples. Do not
  silently change the frozen legacy v1/v1.1 behavior or invent UI endpoints as accepted.
- Trace concise role findings, evidence references, tool outcomes and budget/transition
  metadata. Do not expose raw credentials, provider auth data or private reasoning dumps.
  Role text is untrusted and remains inert in the browser.

## Evaluation before optimization

Compare the existing deterministic investigator, a single live investigator and the proposed
three-role workflow on the same case definitions. Distinguish agent investigation quality
from the fraud model's AP/recall. Keep current p1 artifacts and test results untouched.

Specify numerator/denominator and acceptance conditions for supported factual claims,
unsupported claims, useful abstention, acceptable recommendations, human correction,
unauthorized requests, cross-scope disclosure, latency, calls/tokens where observable and
failure recovery. A sensible recommendation is judged using available evidence and an
explicit rubric, not hidden fraud labels leaked into the prompt. Describe runtime facts
separately from evaluator-only expectations.

Start with development cases covering a large payment after prior activity, small-payment
velocity, a legitimate lookalike, incomplete evidence, contradictory role output, stale
evidence, provider failure/timeout, a budget boundary, a forged tool request and cross-session
IDs. Define prompt-injection coverage at actual untrusted boundaries; document any deferred
document/note path rather than claiming a defense for an input the app cannot receive.

Freeze the protocol before tuning. Use development cases for architecture choices; Codex
will arrange a separately authored final case set after those choices are fixed. Do not
construct, inspect or repeatedly optimize against a purported final held-out set in this
task. Document the limits of independence honestly. No live quality/performance numbers
may be invented from deterministic fixtures or from the number of roles.

## Providers and resources

No live provider call or spending is needed for this design package. Plan first around the
existing deterministic adapter and isolated local Claude adapter, subject to actual quota.
Ollama is a later optional adapter requiring measured laptop feasibility, not an implemented
agent orchestrator. Public BYOK, new subscription bridges, automatic paid fallbacks, public
hosting and additional model providers are out of this increment. No environment installs,
WSL changes, remote creation, push or deployment.

## Handoff and checks

Validate draft schemas and example consistency using existing dependencies where practical;
report actual commands/results and unresolved questions. Do not add tests that merely search
for document headings, or rerun the full backend/browser suite for a documentation-only
proposal. Verify protected source/contract/model/UI/lockfile bytes unchanged and check links.
Record design assumptions, exact source base, proposed version changes and the concrete next
implementation task. Identify any true blocker before handing off, but make routine design
choices with rationale rather than asking for a menu of frameworks.

All new project commits must be solely authored and committed by PHANI465 <pgavara1@asu.edu>,
without Co-Authored-By or AI session trailers. Verify actual metadata, commit explicit owned
paths and update your task handoff. Return the exact tested SHA, deliverables, checks and
remaining decisions. Do not merge main or start G3B until Codex accepts this contract/eval
package. That acceptance freezes interfaces for the backend and later analyst UI work.
