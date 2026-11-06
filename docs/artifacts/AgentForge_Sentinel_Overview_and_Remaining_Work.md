# AgentForge Sentinel: project overview and remaining work

Current checkpoint, November 6: **G3D-P2 accepted and integrated at tested 5a1776b.**
Independent Windows/native backend gates pass 649+one skip each, six commands and same-run
JUnit/HTTP/package/ML. Populated workflow history survives backup/restore with full content,
authority/scope and approval/replay checks. Production code is unchanged. Frontend/browser
checks were not rerun; P1's UI133/browser19+10 remain prior evidence.
[Current checkpoint](AgentForge_Sentinel_Session_2026-11-06.md).

Next: the separate three-role operator helper in a future task, then measured agent
evaluation, deeper analytics and public operations. No live evaluation is assigned.
The approved 2700-second verification-command cap and individual deadlines are unchanged.
Older dated release descriptions below remain historical context.

**Start studying here:** [Complete20-chapter guide in Word](AgentForge_Sentinel_Complete_Project_Study_Guide_2026-11-02.docx) or
[the same guide in Markdown](AgentForge_Sentinel_Complete_Project_Study_Guide_2026-11-02.md). It covers the complete pipeline, architecture,
implementation techniques, ML results, security, agents, examples and future use cases.
[Resume checkpoint](../prompts/RESUME_AFTER_BREAK.md).
Earlier G3C release summary follows.

November 2: **G3C is integrated and verified at f788698.** R38/R39/R40 are closed.
Both complete backend platform gates pass 609+one allowed skip; Windows frontend133 and
real browsers19 legacy +10 trace pass. Main carries this tested application and updated
documentation. [Today's checkpoint](AgentForge_Sentinel_Session_2026-11-02.md).

Historical November 1, 2026 checkpoint: accepted G3B is integrated at a7c71f5 and passes full
Windows/native Ubuntu backend gates, Windows frontend and browser checks. See the
[release record](../releases/G3B-main-integration-2026-11-01.md) and
[session checkpoint](AgentForge_Sentinel_Session_2026-11-01.md).
The [Word guide](AgentForge_Sentinel_Project_Guide_2026-10-26.docx) remains a dated snapshot.

## The project in plain language

AgentForge Sentinel is a financial-fraud investigation workbench. It receives transactions,
ranks risk, opens alerts, gathers evidence, helps an analyst investigate, asks a human to
approve or reject a precise proposal, and records a simulated outcome and audit trail.
All current data is synthetic; it does not move real money or connect to bank accounts.

The fraud model and the language-model agents have different jobs. A rule or trained model
scores the transaction. Agents interpret scoped facts and make a recommendation. Server
code enforces permissions and builds the action. A human authorizes it separately. The
interface exposes the stored facts, score, case history, proposal and final outcome.

## A real-life-style example

Imagine several rapid payments followed by an unusually large payment. A risk score raises
an alert. The analyst opens the case, checks the available history and recorded model/rule
identity, and requests an investigation. In the accepted three-role backend, the evidence
analyst gathers allowed facts, the investigator proposes hold/escalate, and the reviewer
challenges unsupported claims. The server checks claims and builds the exact proposal.

A legitimate invoice can look unusual too. The human can reject a proposed hold rather than
following the AI blindly. If an approval expires, the old proposal cannot be executed. If
a network reply is lost, an idempotent action retry avoids a second simulated effect.
Audits show the decisions. The examples illustrate intended use, not measured real-bank
accuracy. The three-role backend is accepted at e23a7cd and has passed integrated release checks.

This demonstrates fraud-review work found in banks, payment processors and marketplaces.
It is a portfolio/research system; real deployment would require domain, privacy, regulatory
and operational work beyond this synthetic demonstration. No real financial advice is given.

## What already exists

| Area | Current state |
| --- | --- |
| Local end-to-end case workflow | Accepted: transaction -> score -> alert/case -> one investigator -> human approval -> simulated action -> audit |
| Backend/security foundation | FastAPI, typed contracts, PostgreSQL migrations, scoped sessions, least-privilege runtime role, protected audit, revision/expiry checks and idempotency |
| ML/data pipeline | Accepted synthetic generator, delayed-label/time-aware features, rule/logistic/tree comparisons, frozen p1 artifact/manifests, reproducible offline evaluation and online scoring |
| Analyst interface | Accepted case queue/detail/evidence/audit/approval and model-results views, React/TypeScript/Vite, real browser/API/PostgreSQL tests |
| Local operations | Windows and native Ubuntu backend validation, package installation checks, restart/recovery and backup/restore tooling; actual GitHub Actions/hosting still unverified |
| Multi-agent design | G3A accepted: analyst/investigator/reviewer, scoped tools, server-checked claims, finite budgets and persisted boundaries |
| Multi-agent runtime | G3B accepted, R34-R37 closed; included in verified G3C f788698 |
| Investigation trace | Read-only API/UI plus monotonic SQL/caller waits integrated; R38/R39/R40 closed |

Independent R40 review passes Windows34+six original probes and native17+six. The current
integrated backend has 609 passes and one allowed skip per platform; Windows frontend133
and browser19 legacy +10 trace pass. Earlier G3B review has Windows90/native six. None
of these checks establish live agent quality or production capacity.

## How much is left?

The core local application and classical ML foundation are built. There are **three main
product workstreams remaining** after the verified trace API/UI/clock integration. Some original
milestones span both completed and pending work: G1's local path is done while its hosted
path is not; G2's ML is done while the broader analyst workspace is incomplete. G3's design and runtime
and trace UI are accepted while measured live quality evaluation remains.

A single percentage would depend on whether the optional G5 research extensions are counted.
Use accepted capabilities and these concrete next deliverables to track progress.

| Order | Remaining deliverable | What will demonstrate completion |
| --- | --- | --- |
| Done | G3C trace API/UI and clock waits | Integrated/tested f788698; both backend platform gates and Windows frontend/29 browser checks pass |
| 1 | G3D measured agent evaluation | Safe runtime-role evaluator; separately authored final synthetic cases; actual one-live vs three-role comparisons under the frozen protocol, human rubric and reported failures/latency/observable usage |
| 2 | Deeper data-analyst workspace | Curated read-only queries, data quality, financial reconciliation, cohorts/time trends, error slices and exports checked against known answers |
| 3 | Public demo and operational release | Recorded replay, authorized staging/remote/real CI, measured capacity, secret-safe visitor BYOK if included, session isolation, retention/cleanup and deployment/run instructions; README and short demo video |

Security tests belong to each workstream. Public keys/retention, document prompt injection
and public SQL introduce new boundaries and cannot inherit a safety claim from the local
case workflow. No public personal-subscription bridge or owner-key fallback is planned.

## What you should do next

1. Assign the separate three-role local operator helper from current main, using a new
   isolated worktree and preserving the accepted defaults, authority and recovery checks.
2. After that task, explicitly scope measured G3D comparisons under the frozen protocol
   and human rubric; no live or final-case evaluation is assigned by this checkpoint.
3. Deepen the analyst workspace and prepare public demonstration/operations gates.
   Preserve frozen contracts/model/evaluation bytes and accepted/Cursor worktrees.

The local_stack.py convenience command still needs a tested three-role choice; API
configuration already supports it. The evaluator authority split and populated-workflow
backup proof are now integrated and independently verified. Earlier intermittent failures
remain preserved, with no unproven root-cause claim. This does not establish live quality,
fresh-cluster role provisioning or production capacity.

## The stack being exercised

Python/typing/Pydantic, FastAPI, PostgreSQL/SQL/migrations, NumPy/scikit-learn/joblib,
React/TypeScript/Vite, Git/worktrees, uv, pytest/Ruff, Playwright, packaging and CI definitions.
The local Claude adapter is opt-in and uses supported local account isolation; subscriptions
are not a pooled public inference budget. The three-role runtime uses the established Python
coordinator rather than adding a framework merely for another technology name.

The engineering evidence includes temporal evaluation/leakage controls, provenance, pinned
artifacts, human approval, scoped tools, untrusted-output checks, concurrency and recovery.
A trained fraud score is a ranking score, not an automatically calibrated probability.

## Optional expansion after a complete release

Choose extensions based on a measured weakness and learning goal: drift/label monitoring and
model promotion; a PyTorch transaction-sequence baseline; graph features/GNNs only with real
entity/edge semantics; permission-filtered RAG/pgvector and injection evaluations if documents
are introduced; PEFT/LoRA after a justified quality gap and compute measurement; streaming
when measured load requires it. Ollama needs an actual laptop benchmark first.

AML/scam/account-opening, credit risk and market risk require separate targets, datasets,
assumptions and evaluations. They can reuse infrastructure but are not covered by the current
fraud model. These options are G5 research increments, not prerequisites for the first
credible portfolio release. See the [complete roadmap](../PROJECT_PLAN.md).
