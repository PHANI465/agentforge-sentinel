# AgentForge Sentinel: milestone roadmap

Current planning basis: October 23, 2026. The user has removed the November 7 deadline. Earlier dated plans and the imported expansion catalog are research inputs; their dates, default hardware/hosting assumptions and un-reproduced verification claims do not govern this plan.

## Product in one paragraph

An analyst opens a fraud alert, sees the transaction history and model score, asks bounded agents to investigate the supporting evidence, reviews their disagreements, and approves or rejects a simulated action. Every important fact links to evidence, every tool action is constrained by server permissions, and the case can be replayed and audited. A second workspace lets the analyst query synthetic financial data, reconcile totals, examine model errors and export an evidence-backed report. Visitors can inspect a recorded replay without a key and explicitly run supported live model steps with their own provider key.

The initial product uses synthetic transactions and simulated outcomes. A trained fraud model scores risk; LLM agents investigate and explain. The LLM does not invent numeric risk scores or authorize financial actions.

## Design principles

- Deliver one complete thin path early, including an early hosted staging path. More available time funds better evidence and depth; it does not justify integrating everything at the end.
- Budget: use the laptop, existing subscriptions/allowances and genuinely free resources. No additional paid services, model API purchases or overage charges are assumed. Exhausted quota pauses the affected live mode; there is no paid fallback. Verify allowance and billing controls before activating a service.
- Scale the architecture by measuring queue depth, latency, memory, concurrent sessions and cost. A scalable design is not a claim that the laptop/free-tier deployment supports production banking traffic.
- Train and evaluate classical models on CPU first. Local model feasibility is measured on the actual laptop. Ollama is a model runtime, not an agent orchestrator or a source of free cloud compute.
- Prefer one application API, one database and one orchestration approach. Add workers, queues or separate services when a measured requirement needs them.
- Public key handling, tenant identity, permissions and approvals are enforced from the first public path, even while investigation is simple.
- Freeze evaluation cases/split policy before optimization. Keep development scenarios separate from final held-out and adversarial evaluations; seeds improve repeatability, not validity by themselves.
- Each milestone retains a deployable integrated path, reproducible run instructions and honest limitations.

## Gates and acceptance evidence

### G0: measured baseline and shared contracts

Inspect the existing AgentForge repository at a pinned commit, check license/provenance and reproduce relevant tests. A document's report that tests passed is not a substitute for running them. Measure laptop RAM/GPU and one small local-model benchmark; identify actual tool versions, hosting plan and spend limits without reading/pasting credential values.

Define versioned Transaction, Alert, EvidenceItem, Case, AgentRun, Approval, SimulatedAction and AuditEvent schemas. Specify identifiers, tenant/session ownership, event/ingestion/label-availability times, currency/unit handling, idempotency keys, allowed transitions and error behavior. Pin each case to its data snapshot, feature/model artifact, threshold, policy and agent/tool configuration versions from the start, so its evidence and outcome can be reproduced. Establish deterministic fake-provider fixtures, temporal data tests and initial attack cases.

Exit evidence: schema validation, migration from an empty database, cross-language/API contract compatibility, a baseline test report tied to source/version, and a short decision record for runtime/deployment. No application claims yet.

### G1: first integrated local and hosted path

One synthetic transaction is scored by an explicit simple rule, creates an alert, triggers one bounded model investigation over allowlisted evidence, pauses for human approval, records a simulated action and leaves an audit history. Label rule scoring as rule scoring until a trained model replaces it. A deterministic provider fixture supports CI without billable calls, and a separate opt-in local live-model smoke test proves actual inference using Ollama, a documented personal subscription integration or an available provider API allowance. Hosted public BYOK is a separate integration test; existing app subscriptions do not automatically supply its visitor API keys.

Run the full path locally and in a small staging deployment using persistent database state. Keep staging restricted to the project owner/testers until the required session, authorization, key-isolation and abuse-limit checks pass. A public replay may expose only deliberately reviewed static fixtures. Public entry must never fall back to an owner model key. If local/hosted parity is not available, document the gap instead of presenting a laptop-backed service as autonomous hosting.

Exit evidence: browser-to-database end-to-end test; restart/resume test; reject/expired/duplicate approval cases; secret-safe trace inspection; and one explicitly authorized local live-model test. Record a separate hosted BYOK smoke test when a tester with a supported key/allowance is available; until then that boundary remains unverified. Keep the recorded replay clearly separate from live execution.

### G2: data, ML and analyst depth

Create an independently implemented, versioned synthetic simulator with fraud scenarios, legitimate lookalikes, realistic imbalance and delayed labels. Store generation parameters, seeds, data hash and scenario assumptions. A separate appropriately licensed public benchmark is an optional second evaluation, not proof of real-bank effectiveness.

Build rule, logistic-regression and CPU tree baselines using historical-only features. Separate chronological train/validation/test sets; fit preprocessing on training data only. Verify same-timestamp ordering, feature availability and delayed-label availability. Hidden simulator truth/future outcomes never enter an investigation's decision-time context.

Report average precision/PR-AUC, precision and recall at an explicit review capacity, false positives, calibration and latency. Keep average precision and trapezoidal PR-AUC definitions distinct. Show ROC-AUC only alongside imbalance-aware measures. State the unit of review, ranking/tie behavior, time window and assumed error costs. Select thresholds on validation data; evaluate the held-out set after choices are fixed. Keep losing baselines in the report.

Analyst workspace: transaction/case drilldown, saved queries, data-quality and financial reconciliation checks, fraud cohorts, temporal distributions, model-error slices and report exports. Public SQL is constrained by a dedicated read-only role, curated views, session filters, query/time/row limits and no filesystem/network extensions. Generated SQL does not gain trust by passing a text filter.

Include a small seeded generation/training/evaluation CI run with recorded versions and defined metric tolerances. Do not hardcode a fragile exact floating-point score.

Exit evidence: reproducible experiment/model card/data card, leakage tests, baseline comparison with uncertainty, verified totals, and analyst tasks completed against known answers.

### G3: bounded multi-agent investigations with measurable value

Introduce three useful roles: evidence analyst, investigator and reviewer. The evidence analyst can request scoped facts; the investigator can request missing evidence; the reviewer can challenge claims or escalate. A deterministic coordinator controls identity, allowed transitions, tool access, step/depth/fan-out/token/time limits and cancellation. Agents cannot choose arbitrary agent UUIDs or credentials.

Use an isolated untrusted-notes reader only if document scenarios justify it. Keep raw hostile text and quoted attack excerpts out of privileged prompts. Store original excerpts for the analyst UI as inert, escaped evidence; pass minimal validated fields/enums through a constrained interface. Structured output is still untrusted and requires policy validation.

An existing evidence ID proves reference existence, not claim truth. Render numeric facts deterministically from source values. Evaluate citation/claim support, contradictions, unsupported conclusions and appropriate abstention with independent cases and calibrated human review.

Use development cases to select the agent architecture and tune defenses. After choices are fixed, compare deterministic evidence templates, one agent and multiple agents on the same final held-out cases; do not repeatedly optimize against that frozen suite. Measure investigation quality, human correction, abstention, security failures, latency, tokens and cost. Multi-agent complexity earns its place through quality or useful role separation; report negative results honestly.

Exit evidence: role/permission tests, bounded failure behavior, documented ablation study, claim-support evaluation, and a complete user path that handles an unavailable model call with a bounded retry or an explicit, auditable inconclusive result.

### G4: public BYOK and operational reliability

Offer a replay mode requiring no model key. In live mode the browser sends the visitor's key over TLS only for the requested step; the server uses it in memory and never stores/logs it, forwards it to other tenants or substitutes the owner's key. Disclose that the application server and chosen provider process it. Avoid browser persistent key storage and scrub telemetry/error reporting.

Persist workflow state, not visitor keys. For hosted serverless execution, complete a bounded step per request and ask the visitor to supply a key again to resume. Do not claim unattended background LLM work after a request ends without a separate explicitly consented credential design. The local worker profile can run continuously with locally configured credentials; expose no personal subscription bridge publicly.

Treat workflow resumption and side-effect safety separately: database state transitions, atomic approval consumption, concurrency checks, worker leases if workers exist, idempotency, retries, duplicate delivery, crash reconciliation and cancellation all need tests. Bind an approval to case, session/tenant, action parameters, current evidence/policy version and expiry; an LLM's text is never approval.

Attack suite: direct/indirect prompt injection, forged evidence, cross-session ID access, unauthorized tools, approval tampering/replay, malicious SQL, oversized inputs, cost amplification, crash/timeout/provider failure and secret leakage. Report observed success/failure on the tested suite, never universal prevention.

Define and implement deletion/expiry for cases, keys, audit data and traces. A short-retention promise requires a scheduler/TTL mechanism that still runs when there are no visitor requests, plus appropriate backup handling. Publish only retention guarantees the chosen free/paid services can deliver.

Exit evidence: two independent tester sessions, cross-tenant denial tests, no-key failure, key/log inspection with fake secrets, duplicate/concurrent action tests, restart recovery, enforced cleanup, bounded load test and reproducible deployment instructions. Report actual tested load and infrastructure cost/limits.

### G5: deepen one measured weakness at a time

Possible increments, chosen by evidence and learning goals:

1. Drift and delayed-label monitoring, champion/challenger experiments, richer dataset/model lineage and registry automation beyond the core pinned versions, controlled rollback and retraining policy.
2. PyTorch: a small transaction-sequence model compared against time-window tree features. Then graph-derived features; only then consider a GNN when actual entity/edge semantics and labels justify one. Do not invent graphs from PCA-only benchmark columns.
3. Evidence retrieval: permission-filtered RAG, embeddings, pgvector, retrieval/reranking evaluation and document extraction. Fine-tune a small model with PEFT/LoRA on appropriately licensed data only when a baseline exposes a specific gap and measured compute is available.
4. AML/scam/account-opening modules using separately defined targets, data rights, privacy constraints, evidence and evaluation. They reuse infrastructure, not automatically the fraud model or its success criteria.
5. Credit or market-risk research with its own domain assumptions, outcome definitions, backtesting, uncertainty and limitations.
6. A bounded defensive red-team lab, with attacks restricted to this application and isolated fixtures.
7. A larger deployment, queue or streaming transport when a measured replay/concurrency/recovery requirement needs it. Kubernetes is an optional infrastructure learning exercise, not an MVP dependency.

## Stack: adopt progressively

| Layer / skill | Initial choice | Add when justified |
| --- | --- | --- |
| Software foundations | Python, typing, Pydantic, SQL, Git, uv, pytest, Ruff, mypy | Profiling, concurrency and deeper system design throughout |
| Data analysis/engineering | PostgreSQL/Neon, migrations/Alembic, DuckDB, Parquet, pandas or Polars, reproducible manifests | Scheduler and streaming with demonstrated data/update requirements |
| Core ML/statistics | NumPy, scikit-learn, logistic regression, CPU boosting, calibration, temporal evaluation, uncertainty/error analysis | PyTorch, sequence learning, graph features/GNNs |
| Agent orchestration | Typed tools, bounded AgentForge execution loop and explicit persisted state machine | Evaluate LangGraph as a replacement if its checkpoint/resume semantics simplify the design; avoid two competing orchestrators |
| Model runtime | One provider adapter, deterministic CI fake, Ollama local benchmark | Additional provider and efficient local serving after hardware/quality measurements |
| NLP/GenAI | Structured outputs, tool use, evidence-grounded explanations, retrieval evaluation | pgvector/RAG, PEFT/LoRA and small-model optimization if required |
| API / analyst product | FastAPI, PostgreSQL, React/TypeScript, accessible charts and tables; reuse the existing Vite frontend unless a decision record establishes a benefit from Next.js | WebSocket/live updates only if the request/response model is insufficient |
| Experiment/MLOps | Dataset/model manifests, MLflow locally, model cards, repeatable training and promotion checks | Hosted registry, automated retraining, feature store if it removes real duplication |
| Security | Threat model, scoped server-side authorization, secret-safe tracing, sandbox boundaries, attack/eval suites, dependency/secret scanning | Public code execution only with a real sandbox and measured need |
| Delivery / observability | Docker Compose locally, GitHub Actions, structured logs/OpenTelemetry, metrics for data/model/agent/runtime | Prometheus/Grafana or a hosted alternative when actual operational questions need them |

Vercel is a candidate for the web/short-request surface and Neon for persistent state. Verify the actual plan and current runtime limits before placing the Python runtime there. Training remains local or in a quota-limited notebook/compute environment; free resources have availability limits and must not be required for always-on serving. No pricing/quota guarantee is assumed by this plan.

## Using existing subscriptions and tools

Use the existing tools heavily for development, review, tests, explanations and local documented integrations. Verify each product's supported subscription authentication before using it as a local runtime. ChatGPT/Claude/Cursor subscriptions are not a pooled public inference budget; provider API keys and billing are separate unless current official documentation explicitly establishes an applicable entitlement.

Suggested workflow: one lead tool builds contracts and the thin path; another reviews API/security boundaries; a third handles a disjoint ML or UI task only after interfaces stabilize. Rotate these roles based on results, not model brand. Keep one integrator and explicit acceptance criteria. More agents do not create more human review capacity.

## Subscription integrations to validate first

Official documentation checked October 23, 2026 gives concrete options, subject to the actual account and current limits:

- Claude: the Agent SDK and headless claude -p can use subscription limits for ordinary individual use. Max/Team may also include API credits; the exact plan must be checked. Never collect Claude.ai tokens or route visitors through the owner's subscription. Hosted end-user sign-in through an unmodified Claude Code binary is a distinct documented product path, not the initial Sentinel BYOK design. See [plan usage](https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan) and [authentication/product scope](https://code.claude.com/docs/en/legal-and-compliance).
- Cursor: the Python SDK accepts a user Cursor API key and follows the same plan pools/pricing as agent runs. The documented legacy Pro/Pro+/Ultra plans include SDK access; confirm the actual account plan and disable paid overage. This is an agent SDK with workspace/tool behavior, not a generic chat-completions API. See [SDK](https://cursor.com/docs/sdk/python) and [plan entitlements](https://cursor.com/docs/account/pricing/legacy-cursor-plans).
- Codex: its SDK can automate coding workflows. Validate the documented local authentication path for the installed version/account before treating it as a Sentinel runtime adapter; its SDK is distinct from the OpenAI model API. See [Codex SDK](https://learn.chatgpt.com/docs/codex-sdk).

Start by proving one local integration against the same small investigation fixture, with scoped tools and an isolated workspace. Do not bypass tool approval or expose the host filesystem merely to reuse a subscription. Add adapters only when their authentication, permissions, structured results, cancellation and usage accounting meet the shared contract.

## What this project can demonstrate

Strong evidence across data analysis, statistical ML, agent systems, security and operations is a credible AI/ML-engineering portfolio. It cannot prove mastery of every AI subfield. Track skills as demonstrated artifacts/experiments rather than technologies mentioned in a README. Advanced research tracks should strengthen the product or answer a clear research question, while preserving a usable core.
