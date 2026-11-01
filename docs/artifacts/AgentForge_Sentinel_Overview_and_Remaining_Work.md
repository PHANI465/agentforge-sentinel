# AgentForge Sentinel: what it is and what remains

Current checkpoint: October31,2026. Read this first for current scope. The
[Word guide with real-life examples](AgentForge_Sentinel_Project_Guide_2026-10-26.docx)
and its [Markdown copy](AgentForge_Sentinel_Project_Guide_2026-10-26.md) remain useful
October26 snapshots. [STATUS](../STATUS.md) and the
[session checkpoint](AgentForge_Sentinel_Session_2026-10-31.md) hold detailed review history.

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
identity, and requests an investigation. In the candidate three-role backend, the evidence
analyst gathers allowed facts, the investigator proposes hold/escalate, and the reviewer
challenges unsupported claims. The server checks claims and builds the exact proposal.

A legitimate invoice can look unusual too. The human can reject a proposed hold rather than
following the AI blindly. If an approval expires, the old proposal cannot be executed. If
a network reply is lost, an idempotent action retry avoids a second simulated effect.
Audits show the decisions. The examples illustrate intended use, not measured real-bank
accuracy. The three-role backend is implemented on a review branch and still needs R37
closure before it is accepted into main.

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
| Multi-agent runtime | G3B implemented atb74473e; original R34-R36 closed, new R37 connection/helper ownership races pending; not merged into main |

Current main application code remains f091a34. The corrected G3B candidate has85 independent
agent/original-probe passes; supplied full gates have535 passes and one allowed skip. Those
counts are evidence for specific checks, not a percentage-complete score or proof of agent
quality. The two new R37 probes still reproduce a resource-lifetime problem.

## How much is left?

The core local application and classical ML foundation are built. There are **five main
release workstreams remaining**, including the current integration gate. Some original
milestones span both completed and pending work: G1's local path is done while its hosted
path is not; G2's ML is done while the broader analyst workspace is incomplete. G3's design
is accepted while runtime integration/UI/quality evaluation remain.

A single percentage would depend on whether the optional G5 research extensions are counted.
Use accepted capabilities and these concrete next deliverables to track progress.

| Order | Remaining deliverable | What will demonstrate completion |
| --- | --- | --- |
| 1 | Finish G3B review and integration | Fix R37 ownership, preserve closed limits, independent re-review and final integrated Windows/Linux/browser gates |
| 2 | G3C trace API and analyst UI | Freeze the additive trace contract, then show roles, tools, citations, claim checks, disagreement, budgets and incomplete recovery honestly |
| 3 | G3D measured agent evaluation | Safe runtime-role evaluator; separately authored final synthetic cases; actual one-live vs three-role comparisons under the frozen protocol, human rubric and reported failures/latency/observable usage |
| 4 | Deeper data-analyst workspace | Curated read-only queries, data quality, financial reconciliation, cohorts/time trends, error slices and exports checked against known answers |
| 5 | Public demo and operational release | Recorded replay, authorized staging/remote/real CI, measured capacity, secret-safe visitor BYOK if included, session isolation, retention/cleanup and deployment/run instructions; README and short demo video |

Security tests belong to each workstream. Public keys/retention, document prompt injection
and public SQL introduce new boundaries and cannot inherit a safety claim from the local
case workflow. No public personal-subscription bridge or owner-key fallback is planned.

## What you should do next

1. Give Claude the [R37 prompt](../prompts/CLAUDE_G3B_OWNERSHIP_FIX.md), using Opus5.5/High,
   in the existing G3B worktree atb74473e. Keep the tested branch/history and do not merge.
2. Return its exact committed result and real checks to Codex for re-review/integration.
3. After that gate, start G3C with the API contract first, then the trace UI. Cursor may
   contribute again when available; it has already supplied substantive frontend work.
4. Run agent quality evaluations only after the implementation/configuration/protocol are
   frozen and safe evaluation connections are prepared. Deterministic fixtures alone are
   not evidence that three language-model agents improve fraud investigations.

The two previously noted manual-evaluator operator/runtime split and a backup round-trip
with populated workflow tables remain explicit follow-ups before claiming those paths
verified. Earlier intermittent failures are retained, with no unproven root-cause claim.

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
