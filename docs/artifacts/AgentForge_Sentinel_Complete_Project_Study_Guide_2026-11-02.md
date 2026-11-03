# AgentForge Sentinel project study guide

November 2 2026 | Study snapshot and pause checkpoint

Prepared for Phaneendra Gavara on November 2 2026

This guide explains the complete project idea, the working software, the techniques behind it and the next research and product steps. Read it alongside the repository. It is a study guide and an implementation map, not a claim that every planned feature already exists.

### The idea in one paragraph

AgentForge Sentinel is a financial fraud investigation workbench. It receives synthetic transactions, records a rule or trained-model risk score, opens cases, gathers scoped evidence and helps an analyst investigate. A bounded multi-agent workflow can propose a precise simulated hold or escalation. A human decides separately whether to approve it, and execution is another explicit step. The database preserves the evidence, model identity, approvals, outcomes and audit history.

### Three different jobs

- The fraud scorer ranks transaction risk. A numeric score is not a finding of guilt.
- The language-model agents interpret allowed facts and recommend an action. Their output is untrusted.
- The application enforces identity, permissions, validation and approval. A model cannot grant authority.

### How to read this guide

Chapters 2–6 cover the product pipeline and data model. Chapters 7–9 explain machine learning. Chapters 10–14 cover agents, security, the interface and evaluation. Chapters 15–16 cover testing and operation. Chapters 17–20 explain future uses, the learning path and the saved resume point.

Status at this checkpoint: the merged application is the G3C local release. The evaluator and R43 fixture correction are accepted components awaiting the next combined main integration. All current financial data is synthetic and every action is simulated. There is no bank connection or real-money movement.

## 2 The complete online transaction pipeline

The database is the durable source of truth. The browser initiates requests and displays stored results; an agent response or a successful-looking screen is not proof that an action occurred.

| Stage | What the server does |
| --- | --- |
| 1 Authenticate | Resolve a bearer token to tenant, session, actor and capabilities. Only the token hash is stored. |
| 2 Validate and order | Validate the transaction and take the account lock before reading decision time. |
| 3 Score and persist | Compute allowed historical features, run the configured scorer and save every scoring outcome. |
| 4 Open the case | If score meets the threshold, create an alert, case, evidence and provenance pins. |
| 5 Investigate | Claim the current revision and run the chosen deterministic, single or three-role investigator. |
| 6 Validate the proposal | Check structured output and claims, then build exact action parameters from stored records. |
| 7 Human decision | Approve or reject the current proposal. A reviewer agent cannot supply human approval. |
| 8 Execute explicitly | Check the approval and execution key, consume approval atomically and record one simulated outcome. |
| 9 Read and audit | Return the stored case, trace and audit. Replays and restarts retain the original decisions. |

### Two important branches

A transaction below the alert threshold still has a saved scoring outcome; it does not need a case. An investigation that cannot reach a valid disposition can end inconclusive and reopen its case without creating an executable proposal. Unknown results are displayed honestly rather than converted into success.

Read: src/sentinel/api.py, service.py, scoring.py, scorers.py and trace.py. The active public response snapshot is contracts/http/openapi.v1.2.json; older v1 and v1.1 snapshots remain frozen.

## 3 A worked fraud review example

Imagine a fictional USD account making two small payments, then a USD 4,800 payment ten minutes later. This example uses the current rule baseline so the arithmetic is transparent; it is not a production fraud policy.

| Time | Payment | Prior events in hour | Rule score |
| --- | --- | --- | --- |
| 09 00 | USD 20 | 0 | 0.0 |
| 09 05 | USD 25 | 1 | 0.2 |
| 09 10 | USD 4,800 | 2 | 1.0 |

For USD, the demonstration large-amount cutoff is 100,000 minor units, or USD 1,000. A large transaction adds 0.6. Each prior event contributes 0.2, with that velocity contribution capped at 0.6; the overall score is capped at 1.0. The third transaction scores 0.6 + 0.4 = 1.0, above the rule alert threshold of 0.5.

### What the analyst sees

The case shows the amount, available history, recorded score and rule identity. The evidence analyst gathers allowed facts. The investigator can recommend a simulated hold, while the reviewer can challenge unsupported statements. Server checks and a deterministic rationale connect the final proposal to actual records.

Suppose the payment is a legitimate supplier invoice. The analyst can reject the hold. A high score only earns review; it is not proof of fraud. A useful system must also help explain false alarms and abstain when evidence is insufficient.

### What happens when the network fails

If execution commits but its response is lost, the browser keeps the same execution idempotency key. A retry retrieves the original action instead of inserting another one. The server rechecks the current actor’s authority. If an unused approval has expired, it cannot be revived; the case must follow the fresh revision and approval path.

Study exercise: change the amount and the number of prior events on paper. Calculate the rule score, then explain why that number still cannot authorize an action.

## 4 Architecture and technology choices

Sentinel uses one application API and one PostgreSQL database. The coordinator is an explicit Python state machine. Separate queues, streaming infrastructure and additional orchestration frameworks are future choices driven by measurement.

| Layer | Implemented technology | Purpose |
| --- | --- | --- |
| Interface | React, TypeScript, Vite | Case workbench, model reports and investigation trace. |
| HTTP and contracts | FastAPI and Pydantic | Typed validation, response schemas and OpenAPI snapshots. |
| Persistence | PostgreSQL and psycopg | Transactions, locks, durable cases, approval and audit. |
| Classical ML | NumPy, scikit-learn, joblib | CPU baselines, pinned artifact and online inference. |
| Agent system | Python coordinator and typed adapters | Bounded roles, scoped tools, claim checks and recovery. |
| Verification | pytest, Ruff, Vitest, Playwright | Backend, component, real browser and security regressions. |
| Build and workflow | uv, setuptools, npm, Git worktrees | Locked dependencies, packaged assets and isolated tasks. |

### Why this shape helps

FastAPI keeps transport separate from service rules. PostgreSQL transactions make approval consumption and action insertion atomic. Versioned contracts let a TypeScript client evolve without inventing endpoints. A small trained CPU model fits the laptop-first budget. Keeping orchestration explicit makes limits and failure transitions inspectable.

The repository includes GitHub Actions configuration, but a real GitHub Actions runner has not been exercised. Native Ubuntu backend checks run under WSL as an unprivileged user. The browser suites have Windows evidence. Hosting, public visitor-key inference and measured production capacity remain future work.

Not yet core dependencies: PyTorch, LangGraph, Kafka, Kubernetes, a vector database, a feature store or hosted MLflow. Learn or introduce them when a concrete experiment or operating requirement benefits.

## 5 What the database remembers

Five packaged SQL migrations create the current 16-table inventory. The design records business objects and execution history separately so a later investigation can explain the original decision rather than recompute it from today’s data.

| Tables | Meaning |
| --- | --- |
| api_sessions | Token hashes, scope, actor, capabilities and expiry. |
| transactions and scoring_outcomes | Submitted transaction and the exact saved scoring decision, including non-alerts. |
| alerts cases evidence_items | Review work, case revisions, pinned identities and supporting facts. |
| agent_runs agent_workflows agent_steps | Individual attempts, coordinated workflows and ordered execution records. |
| action_intents approvals simulated_actions | Server-built proposal, human authorization and recorded simulated effect. |
| audit_events | Application audit history with update/delete protection. |
| account_profiles fraud_disclosures | Operator-provisioned model inputs and known fraud disclosures. |
| schema_migrations | Which schema changes have been applied. |

### Identity and concurrency

Tenant and session scope are attached to records and supplied by trusted authentication context. SQL queries must include that scope. This is application-enforced scoped SQL; do not describe it as an implemented database row-level-security policy. A foreign identifier does not become authorized because a model or browser submits it.

Per-account transaction locks serialize ingestion and operator profile/disclosure changes. Case and approval locks protect revision checks and approval consumption. An execution key binds a retry to the original result. All callers must finish and their individual outcomes must be checked in concurrency tests.

The audit trigger protects normal application behavior, not against the schema owner or superuser. Backups include workflow tables in their inventory; proving a round-trip with populated multi-agent history remains a specific follow-up.

Read: src/sentinel/db/migrations/, db/roles.py and service.py. New tables need explicit role permissions, packaging and backup-inventory review.

## 6 Time contracts and causal correctness

A financial event has several different times. Confusing them leaks future information into a decision, breaks a replay or creates unreliable tests.

| Time | Question it answers |
| --- | --- |
| occurred_at | When did the transaction event happen? |
| ingested_at and decision time | When was the row available to this decision? |
| disclosed_at and recorded_at | Was a fraud disclosure both disclosed and recorded by that time? |
| label_available_at | Was a training or evaluation label actually observable by its cutoff? |
| Monotonic elapsed time | How much waiting budget remains, regardless of wall-clock steps? |

The rule history window is [event time minus one hour, event time). Events at the upper boundary are excluded. Availability uses ingested_at <= decision time. A previously committed row may legitimately share an ingestion timestamp on a coarse clock; a later arrival with that same timestamp was not available yet. The concurrency reference therefore also records decision order.

The service reads time after acquiring the relevant account, case or approval locks. Model operator writers use the same account lock, so a concurrent update cannot leak halfway into a decision. Direct owner SQL can bypass that convention; the ordinary runtime cannot grant itself owner authority.

### Typed boundaries

Pydantic validates fields and variants, rejects unexpected data and publishes schemas. Amounts use integer minor units and an explicit currency exponent. A hold and an escalation have different parameters. The TypeScript parser must accept documented nulls while rejecting malformed responses. Missing values mean unknown, not a fabricated zero.

Read: contracts/v1.py, http_v1.py, http_v12.py, decision 0005 and data_pipeline/features.py. The ML protocol defines exact half-open day windows; informal “days 10 to 55” must not override those bounds.

## 7 The offline machine learning pipeline

1. Generate a versioned synthetic stream with fixed seed, account activity, fraud episodes, legitimate lookalikes, delayed ingestion and delayed labels.
2. Build decision-time features using only rows and disclosures available at each transaction’s decision.
3. Split chronologically, apply label-availability rules and fit preprocessing on training data only.
4. Train the rule, logistic-regression and tree comparators under a protocol frozen before selection.
5. Select on validation average precision, freeze the threshold and model identity, then evaluate the test view.
6. Save the artifact, protocol, selection record, feature/dependency identity, hashes and model/data cards.

### Features and labels

The model uses 12 numeric features plus currency: amount, credit direction, foreign currency, account age, one-hour and 24-hour counts, small-payment count, same-currency amount sum, credit sum, time since previous event, amount-to-median ratio and prior known fraud. Identifiers, scenario tags, timestamps and true labels are excluded as direct model inputs.

A label not yet disclosed is unknown, not legitimate. The protocol lets training labels mature to day 85 and validation labels to day 115. Its numeric windows are train [10,55), validation [56,85) and test [116,150). The gaps are chronological embargoes; feature windows still share historical stream context, so they do not establish independent observations.

The reference experiment uses 600 accounts over 150 generated days. The original short data configuration had too few mature labels for classification. Extending the horizon was preferable to relabeling unknowns as negatives. Final test truth is synthetic simulator truth, including never-disclosed fraud; that is an offline benchmark, not a real bank’s observable labels.

Read: data_pipeline/generator.py, features.py and splits.py; ml/protocol.json, dataset.py, models.py and run.py. Data cards explain the simulator’s assumptions and its deliberately learnable patterns.

## 8 Reading the frozen model results

The selected p1 model is a balanced HistGradientBoostingClassifier behind fixed preprocessing: signed log1p numeric transforms and one-hot currency. It was selected on validation, not by repeatedly choosing whichever test result looked best.

| Candidate | Validation AP | Test AP |
| --- | --- | --- |
| Rule baseline | 0.488 | 0.455 |
| Balanced logistic regression | 0.532 | 0.400 |
| Unweighted logistic regression | 0.636 | 0.622 |
| Unweighted gradient boosting | 0.273 | 0.208 |
| Balanced gradient boosting selected | 0.830 | 0.817 |

| Test review policy | Flagged | Precision | Recall |
| --- | --- | --- | --- |
| Daily top 15 | 510 | 0.198 | 0.927 |
| Frozen validation threshold | 442 | 0.231 | 0.936 |

The test has 18,597 rows and 109 fraud labels. At daily capacity the selected model finds 101 positives with 409 false positives. At the frozen threshold it finds 102 with 340 false positives. These policies answer different operating questions; the API uses the frozen threshold, not a daily top-15 quota.

Average precision summarizes ranked precision at positive examples. Trapezoidal PR-AUC interpolates between curve points and can differ substantially when scores are tied; the rule has AP 0.455 versus trapezoidal PR-AUC 0.579. High accuracy on an imbalanced dataset would be a weak headline by itself.

The 95% account-bootstrap AP interval is approximately 0.697–0.914. It resamples accounts, not independent rows. Scores are uncalibrated rankings, not probabilities. One seed, synthetic truth, small positive counts and legitimate lookalikes limit the conclusion.

Read: ml/results/p1/test_report.json, docs/ml/model-card.md and ml/evaluate.py. Frozen test reproduction recomputes and compares without tuning the artifact or rewriting the result.

## 9 Serving the trained model safely

Rule scoring remains the default. Model scoring requires an explicit operator setting, SENTINEL_SCORER=model:hgb_balanced@p1. An unknown registry entry or failed artifact check refuses startup instead of silently falling back.

1. Load only the registered trusted artifact after verifying hashes, feature schema, model code and expected dependency identity.
2. Require the account profile; refuse a missing one before storing transaction or scoring rows.
3. Under the account lock, compute features with the accepted offline feature code and only available history/disclosures.
4. Store the exact feature inputs, score, threshold, semantics and model provenance with the decision.
5. On a repeated external transaction, return the stored outcome rather than scoring against a different model or newer history.

The frozen streaming threshold is 4.0295386895426815e-6. Its small magnitude does not make it a probability estimate. Class weighting and training behavior affect the score scale. The threshold was chosen by a fixed validation review policy and must be interpreted with the recorded metrics.

### Currency and temporal pitfalls

INR contributes 181 false positives among 201 flagged INR rows in the daily top-15 slice. Raw minor-unit amounts have different scales across currencies. A currency-normalized feature is a reasonable next experiment, but it needs a new feature identity, protocol and validation evidence; it cannot overwrite p1.

Profiles and disclosures are operator data, not model-chosen facts. There is no implemented profile-staleness or disclosure-retraction policy yet. Recorded scores survive a scorer switch and API/database restart. This supports reproducibility, not a promise that old evidence remains sufficient for a real financial decision.

Read: src/sentinel/scorers.py, service.py, ml/artifact.py and decision 0006. joblib deserialization is restricted to trusted pinned local artifacts; visitor-supplied models are not supported.

## 10 How the three roles cooperate

| Role | Its contribution | Its boundary |
| --- | --- | --- |
| Evidence analyst | Requests and summarizes allowed facts. | Cannot choose tenant, account ID, SQL or credentials. |
| Investigator | Builds a structured recommendation or abstention. | Cannot author an executable target or human approval. |
| Reviewer | Accepts or challenges supported claims and the recommendation. | Agreement is advisory, not authorization. |
| Deterministic coordinator | Owns transitions, tools, checks, persistence and final disposition. | Does not treat a model’s JSON or rationale as trusted policy. |

The workflow gathers baseline facts, calls the evidence analyst, then the investigator and reviewer. One bounded investigator revision may address a reviewer challenge. The coordinator validates structured claims against recorded facts and renders the final rationale from server-controlled values. Unsupported claims do not become facts because two agents agree.

The four read-only tools are case_evidence, scoring_outcome, account_history and account_profile. Requests use a small typed vocabulary. The server supplies scope and identifiers, bounds time windows and derives results at the case’s decision boundary. A citation establishes a reference; its claim still needs a value/support check.

### Endings matter

A valid recommendation creates a server-built intent for separate human review. An abstention can create an insufficient-evidence escalation based on a completed investigator. If there is no valid basis, the workflow ends inconclusive and the case returns to open with no intent. The workflow record and case state are distinct objects.

Deterministic roles exercise the plumbing in tests. Optional local Claude role adapters provide the live mode. No live one-agent-versus-three-role quality result is claimed at this checkpoint. Free-text notes remain untrusted, even when their structured claims pass.

Read: agents/coordinator.py, adapters.py, tools.py, claims.py and contracts/agents.py. Role configuration, limits and tool profile are pinned with the case.

## 11 Deadlines concurrency and recovery

| Default limit | Recorded value |
| --- | --- |
| Role attempts / coordinator transitions | 5 / 12 |
| Investigator revisions / repeats | 1 / 1 |
| Role timeout plus grace | 45 seconds plus 2 seconds |
| Workflow waiting deadline / final reserve | 150 seconds / 5 seconds |
| Live workflows / outstanding calls per process | 1 / 2, including late workers |

The coordinator reserves time for its final database write and recalculates remaining budgets before operations. It refuses to submit a role call unless the call and grace still fit. A repeat is allowed only after a worker has already returned with a repeatable error; a timed-out worker may still be running, so it is not immediately repeated.

A workflow slot is released when coordination ends. A call slot stays occupied until its worker actually returns. Database operations whose replies stop arriving are quarantined rather than reusing an uncertain connection. These bounds are process-local, not provider-wide quotas or proof of cancelled remote billing.

### The three commit outcomes

- Confirmed commit: return the stored result.
- Known rollback or refused work: report the corresponding bounded failure or pending state.
- Commit reply lost: report investigation_outcome_unknown and re-read; do not claim success or rollback.

Wall-clock jumps exposed timed-wait problems on the observed portable Python build. Shared monotonic waits now cover database coordination and both Future callers. Polling at up to a 5 ms interval is not a guaranteed response latency. PostgreSQL server timeouts still use realtime, and bounded client waiting does not guarantee commit durability by the deadline.

Recovery uses persisted workflow/revision guards. A trace GET shows overdue status but never recovers it; the mutation path performs recovery. Read clock.py, agents/budget.py, capacity.py and the native-clock diagnosis.

## 12 The security model

The core security question is what an untrusted model or visitor can cause the application to do. Sentinel places permissions and financial effects in server code and database transactions.

| Boundary | Implemented technique |
| --- | --- |
| Session isolation | Hashed bearer tokens, explicit capabilities and tenant/session-filtered queries. |
| Database authority | Restricted runtime role; operator-only provisioning and migrations. |
| Model output | Typed fields, fixed operations, allowlisted tools and server-side fact/claim checks. |
| Human action | Separate approve/reject/execute with revision, expiry, actor and idempotency checks. |
| Browser text | Inert rationale/notes, scoped citation targets and memory-only session token. |
| Diagnostics | Safe request IDs, fixed log fields, code-only errors and secret-scanned test artifacts. |

The restricted role cannot create sessions, change the schema or disable audit protection. Runtime setup checks direct and relevant PUBLIC privileges and exact table identities. The owner remains powerful; application audit protection is not tamper-proof against a database administrator.

Security tests exercise foreign-case access, capability denial, malformed outputs, unsupported claims, approval replay, oversized bodies, timeouts, crashes and secret leakage. Report attacks tested and observed outcomes. Tests do not establish universal prompt-injection prevention or protection against input types that the product does not yet accept.

### Subscription and public key boundaries

The optional local Claude adapter verifies supported first-party login and strips paid-provider routing variables. That is a local account-isolation condition, not proof of a particular subscription allowance. A future public visitor cannot be routed through the owner’s personal subscription. Public BYOK needs its own key handling, isolation, abuse limits and verification.

Read: docs/security/README.md, db/roles.py, investigators.py and the review regressions. Future document retrieval and generated SQL introduce new security boundaries; they cannot inherit a tested claim from today’s structured case flow.

## 13 The analyst interface and trace view

The React workbench includes session entry, queue/overview, case detail, evidence, proposal, approval/rejection, separate execution, audit and model reports. It distinguishes a rule score from a trained score and a deterministic investigator from a live adapter.

The read-only investigation trace uses GET /v1/cases/{id}/investigation-trace, optionally selecting a workflow_id. The server reads a single REPEATABLE READ READ ONLY snapshot scoped to tenant and session. Workflows are ordered by case revision, with up to 25 listed and an explicit total. A selected historical trace cannot authorize a historical action.

### Unknown and stale are real states

- No workflow differs from old single-investigator history and a real zero-role workflow.
- Null counts, usage and limits stay unknown. Zero is displayed as zero.
- Overdue means recovery is due, not that a GET has recovered the workflow.
- An analyst claim check that was not stored is “not recorded,” not verified.
- Recorded role attempts are not proof of provider submission; reported tokens are not billing.

The client fences responses by session, case, selected workflow and generation. Render-time ownership prevents old private content appearing under a new context before React effects run. Sign-out clears memory. A historical selection survives an ordinary refresh; changing session or case starts with the latest workflow.

Malformed or non-JSON server/network responses are unconfirmed, not an invented empty result. A 409 triggers a server re-read. An ambiguous action retry retains one execution key. Unicode note limits count code points, matching the Python schema. Model notes render as text, not HTML or executable Markdown.

Read: web/src/, docs/ui/G3C-trace.md, contracts/http/openapi.v1.2.json and decision 0008. Read_at and elapsed_ms describe recorded snapshots/coordinator work, not live provider state.

## 14 Evaluating agents without inventing evidence

G3D measures whether three roles earn their added complexity. The comparators are C0 deterministic investigator, C1 single live investigator, C2-det deterministic workflow plumbing and C2 live three-role workflow. Deterministic success does not establish live reasoning quality.

The frozen protocol compares supported claims, acceptable recommendations, useful and unnecessary abstention, human correction, security failures, completion counts, workflow/request timing and observable usage. A common blinded human rubric evaluates free text. A model grader may add a labelled signal, but does not replace human ground truth.

### What the accepted development runner does

The evaluator uses SENTINEL_EVAL_OPERATOR_URL for catalog verification and session provisioning only. SENTINEL_EVAL_RUNTIME_URL authenticates, ingests, investigates and reads usage under the restricted role. Unsafe or mismatched authority refuses before comparator construction. C1 and C2 require explicit live consent; no such comparison was run for this checkpoint.

One attempt means one investigate request. Failed provisioning, authentication or ingestion is not an attempt. The corrected runner stops with incomplete JSON and exit 3, preserving earlier requests and listing what did not start. Request errors remain counted. A failed usage lookup cannot erase a known outcome; its provenance becomes unavailable. Missing usage or zero attempts cannot become adapter_reported. Duplicate comparator names are refused.

Development cases include fault instructions that this manual runner does not apply. It records faults_not_applied; those failure scenarios are demonstrated in pytest instead. Runtime facts remain separate from evaluator expectations. Independently authored final cases, live comparisons and blinded review remain future work.

C1 versus C2 is an end-to-end comparison with unequal evidence access. It cannot by itself prove that extra roles caused a quality improvement. Read docs/evals/agents/protocol-v1.md and the accepted candidate’s evaluator-runbook.md and scripts/agent_eval.py.

## 15 Testing and the debugging lessons

Verification is layered so a green mocked interface is not mistaken for a working financial workflow.

| Layer | What it demonstrates |
| --- | --- |
| Contract and unit tests | Validation, variants, scoring arithmetic, metric definitions and parser behavior. |
| Database integration | Real transactions, scoped SQL, locks, races, rollback and role permissions. |
| Real HTTP processes | Production API behavior, restarts, typed errors and failure cleanup. |
| Browser integration | Browser to API to disposable Postgres, approval/execution and trace behavior. |
| Packaging and reproduction | Installed inference outside the checkout, migrations/assets and frozen model results. |
| Cross-platform gates | Windows and native Ubuntu backend runs, with exact commit and allowed skip. |

Regression tests should fail for the claimed defect before a fix. Negative controls and mutations check that an assertion can detect a broken implementation. Concurrent tests must check every caller and the final stored result, not merely that one call succeeded.

### Three useful examples

The old ingestion reference used strict timestamp order and failed when legitimate decisions shared a timestamp. Tracking earlier decisions and testing a fixed clock corrected the reference without changing scoring. Both event-time and availability cutoff mutations are caught.

R43 model fixtures originally used seed-time now as event time. A lagging API clock hit future_event_time before the intended missing-profile check. A five-minute historical event margin, paired with profile opening time, fixes the finite-skew precondition while retaining exact model inputs and scores.

Native realtime steps also exposed wall-clock waits; monotonic waiting and an advisory-lock commit fixture addressed demonstrated paths. Preserve failed reports and qualify uncaptured causes. A later passing run never erases a failure. Strict gates run on clean exact commits; JUnit skip validation uses that same full run.

## 16 Running and operating the local project

The canonical folder is E:/PHANI/agentforge-sentinel. Follow SETUP.md and the current STATUS first, because an accepted component can still await main integration. Do not paste a command from an old dated guide without checking its supported flags.

1. Install the locked development and model extras with uv sync --locked --extra dev --extra ml.
2. Start the local deterministic rule stack with uv run --locked python scripts/local_stack.py up.
3. In web/, run npm ci and npm run dev; enter the private local session token from the owned stack session file.
4. Use the documented smoke command for a synthetic case, then inspect its evidence, approval, execution and audit.
5. Stop through scripts/local_stack.py down. Use the owned recovery records when shutdown cannot be confirmed.

Model mode is explicit and needs operator-provisioned account profiles. The API already supports the three-role investigator setting; the local_stack convenience flag for that mode remains a separate task. The deterministic investigator stays the safe development default.

### Restart backup and process ownership

Local tools record the processes and folders they own. A stop must verify process identity, not kill by executable name. Failed cleanup keeps recovery state. The separate browser stack uses disposable clusters and private manifests; its tokens stay available for artifact secret scanning until teardown finishes.

Backup uses a PostgreSQL custom-format dump and restore into a new owned database, with migration inventory and audit checks. The next persistence task must populate workflow/step tables and verify their contents, rather than showing only matching empty-table counts. The operator’s POSIX orphan-detection limits and PID-check-to-signal window remain disclosed.

Logs use safe request metadata; default web-server access logs can include query strings, so documented local launchers disable them. Metrics are process-memory counters without a public metrics endpoint. Log retention, cloud monitoring, capacity and hosted operations remain future engineering work.

## 17 Future financial analyst uses

The current case and model-report screens are a foundation for a broader financial data workspace. These are proposed workflows and acceptance targets, not shipped capabilities or claims about real institutions.

| Future use | Concrete analyst task | Evidence needed |
| --- | --- | --- |
| Payment reconciliation | Find a missing settlement or duplicate ledger entry. | Seeded totals, matched/unmatched records and independently checked discrepancies. |
| Fraud trend analysis | Compare alert and error rates by week, currency or merchant cohort. | Versioned source rows, clear denominators and delayed-label handling. |
| Case operations | Identify backlogs, false-alarm workload and ageing approvals. | Actual persisted case histories and reproducible aggregates. |
| Marketplace abuse | Investigate seller payout bursts or repeated refund patterns. | Defined entities/events, new labels and scoped evidence. |
| Scam or AML research | Review transfer chains or suspicious account relationships. | Separate task definition, data rights, evaluation and domain review. |
| Credit or market risk | Study default or loss scenarios and exposure changes. | Separate targets, assumptions, backtesting and uncertainty. |

### A useful analyst pipeline

Validate ingestion and reconcile source totals, publish curated scoped views, calculate cohort/temporal measures, investigate exceptions, then export an evidence-backed report. Each displayed count needs a known-answer fixture. Keep actual records, reported model results and hypothetical scenarios visibly distinct.

If natural-language SQL is added, use a dedicated read-only role, curated views, mandatory scope and query/time/row limits. An LLM-generated SELECT is not trusted just because a text filter accepts it. Block filesystem/network extensions and validate export contents.

A fraud model does not become a credit or market-risk model by renaming its screen. Infrastructure can be reused; outcomes, datasets, decision costs and evaluations must be designed for each new problem.

## 18 Future AI and scaling experiments

Expand one measured weakness at a time. Each experiment needs a baseline, data/protocol version, resource measurement and a decision about whether to adopt it.

| Proposed track | Question to answer | Possible techniques |
| --- | --- | --- |
| Better fraud features | Can currency effects and legitimate bursts be separated better? | Normalized amount features, calibration study and new temporal evaluation. |
| Sequence learning | Does ordered history add value beyond window aggregates? | A small PyTorch sequence model against the frozen tree baseline. |
| Entity graphs | Do relationships reveal patterns missed per account? | Defined entity/edge features, then a GNN only if justified. |
| Evidence retrieval | Can investigators use documents safely and accurately? | Permission-filtered RAG, pgvector, reranking and injection tests. |
| Local inference | Which model fits this laptop’s quality and latency budget? | Ollama benchmark; later quantization or PEFT/LoRA if a gap warrants it. |
| MLOps and operation | Can models and services be changed safely under load? | Drift/delayed-label monitoring, registry/promotion, rollback and measured queues. |

Ollama is a model runtime, not the multi-agent coordinator and not free cloud hardware. CPU-first classical training is already useful. GPU experiments depend on measured local capacity or an actual free allowance, with no paid fallback assumed.

### The public product path

First offer a reviewed recorded replay without a model key. Then evaluate restricted staging, genuine CI, session lifecycle, retention, abuse limits and measured capacity. Visitor BYOK must be request-scoped, secret-safe and isolated; never substitute a personal owner key or subscription bridge.

Vercel/Neon or another host can be evaluated later against current official limits and the actual bundle/process model. Durable queues or separate workers become useful when measured replay/concurrency requirements justify them. Kubernetes is an optional infrastructure learning exercise, not evidence of scale by itself.

## 19 How to study and explain the implementation

### First reading pass

1. Explain the online pipeline in chapter 2 without looking. Separate scorer, investigator and approver.
2. Read service.py alongside the v1 contracts and identify the transaction boundary for ingestion and execution.
3. Read the data/model cards, protocol and test report. Recalculate precision and recall from one confusion matrix.
4. Follow one coordinator workflow through tools, claims, role attempts, disposition and terminal transaction.
5. Read the trace API/client and one race regression. Explain why null differs from zero and why stale content must clear before effects.
6. Read the authority, approval/idempotency and clock regressions. Explain what each failure would look like to an analyst.

### Questions you should be able to answer

- Why is random train/test splitting inappropriate for this stream? How do delayed labels change training eligibility?
- What prevents a model from choosing another account or approving its own recommendation?
- What happens if COMMIT succeeds but its response is lost? Why must a retry keep the same execution key?
- Why can two equal ingestion timestamps describe different availability? Why is event time still exclusive at the upper bound?
- What did multi-agent tests demonstrate, and what still needs a live comparison and blinded human review?

### An accurate project explanation

“I am building a synthetic fraud investigation workbench that connects temporal ML scoring to bounded agent investigations and human-approved simulated actions. I implemented persistent, scoped workflows, reproducible classical baselines, typed evidence/tools, failure recovery and an analyst trace interface. The next steps are measured live-agent evaluation, broader financial analytics and a verified public demonstration.”

Your demonstrated skills are Python, SQL, typed APIs, statistical ML, evaluation, concurrency, security boundaries, React/TypeScript and testing. Deep learning, RAG, streaming and cloud operations remain explicit learning tracks until their own artifacts and experiments exist.

## 20 Current checkpoint and resume after the break

November 2 checkpoint. The last merged application is G3C, tested at f788698. Evaluator R41/R42 are accepted at dddd0b4. Their integration candidate 8b4e4eb passed Windows but exposed a separate native fixture-time failure. That failure and the earlier reports remain preserved.

R43 corrects the model fixture timing at 6e461c0b0be9c2ad730191fab0e93768b1db8117. Its author exact-commit records show 647 backend passes and the one allowed live-Claude skip on Windows and native Ubuntu, plus Windows frontend133 and browsers19+10. Codex independently re-reviews the focused clock, real model-stack and original skew probes. The final checkpoint records the actual acceptance outcome; none of these candidate records substitutes for a future merged-commit gate.

### What resumes next

1. Read the latest STATUS, TASK_QUEUE, review record and RESUME_AFTER_BREAK prompt. Check main and worktree state before acting.
2. Integrate the accepted evaluator, timestamp-reference correction and R43 with current coordination. Preserve candidate branches and Cursor’s seven edits.
3. Run one complete final Windows gate, then native Ubuntu, tied to the new exact merge, including same-run skip validation and frozen outputs. Verify browser compatibility for the changed fixtures.
4. After publication, assign the populated-workflow backup proof, then the separate three-role operator helper.
5. Only later, prepare live comparisons and final-case review under the frozen protocol. Continue deeper analytics and public operations afterwards.

### Pause boundaries

The owner requested a one-day break. No new feature task, provider call, final-case evaluation, push or deployment starts during that pause. No automatic restart was created in this session; resume by sending “Resume Sentinel from the saved checkpoint” when you return. Claude should leave its tested branch clean and stop.

Durable references: docs/STATUS.md, docs/TASK_QUEUE.md, docs/artifacts/AgentForge_Sentinel_Session_2026-11-02.md and docs/prompts/RESUME_AFTER_BREAK.md. This study guide is a dated snapshot; those coordination files carry the next accepted state.
