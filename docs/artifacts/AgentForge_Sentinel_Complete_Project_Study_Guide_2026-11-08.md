# AgentForge Sentinel: the complete project guide

**Browser document insights.** The source release includes statement reconciliation,
document comparisons, check coverage, and complex examples. The live public site and
synthetic workbench use the preceding deployment. See the
[source release](../releases/DOCUMENT-INSIGHTS-GITHUB.md) and
[user guide](../ui/PUBLIC-DOCUMENT-INSIGHTS.md). The completion tables below describe their dated scope.

November 8 edition · Updated November 13, 2026 · Project idea, implementation and remaining stages

**November 14 integration update.** Document Review is integrated locally at source commit `3dfbc00`. With the document grant, an analyst can upload a public or synthetic CSV, XLSX or PDF, review extraction coverage and available reconciliation, and page through evidence. The AN01-M1 prototype is integrated at `1427b2c`, with full-size Reports measurements still ahead. [Part C release](../releases/DOC01-Part-C-main-integration-2026-11-14.md) · [AN01-M1 integration](../releases/AN01-M1-main-integration-2026-11-14.md) · [Current work](../START_HERE.md)

**Historical review update (November 12, 2026):** AN01-M1 candidate [28dfcef](../reviews/AN01-M1-28dfcef.md) is accepted for its measurement-prototype behavior, with R53–R57 closed. It remains unmerged. Its earlier tiny timing controls still do not demonstrate the provisional performance limits. The November 10 review narrative later in this edition records the earlier b54de1a state as history. Read the linked review and [START_HERE](../START_HERE.md) for the next task.

**Historical later November 12 DOC01 update:** The [local document worker](../reviews/DOC01-8f7bd87.md) is accepted at `8f7bd87` and integrated in source merge `662572e`. It parses public/synthetic text-layer PDF, CSV and XLSX with bounded child processes and typed feedback measures; it did not yet provide a browser upload or API at that point. The [backend assignment](../prompts/CLAUDE_DOC01_PART_B_BACKEND.md) was prepared. AN01-M1 remains accepted but unmerged, and its provisional limits are unchanged. The stage table below is the November 8 snapshot; use [current status](../START_HERE.md) for subsequent changes.

Prepared for Phaneendra Gavara. This edition replaces the November 2 guide for current reading. That edition remains a preserved historical snapshot. The final chapter separates accepted work, delivered candidates, unmeasured claims and future plans. Product fixtures use synthetic financial data and simulated actions. The separately downloaded ULB research dataset is real anonymized data, ignored locally and not used by the product model.

## 1 The complete project we are building

AgentForge Sentinel is an evidence-driven financial investigation workbench. It connects transaction data, reproducible fraud scoring, bounded AI investigation and a human decision in one auditable system. Its purpose is to help an analyst answer: **What happened, what was known at the time, why was this transaction flagged, what evidence supports a recommendation, and who authorized the outcome?**

The complete planned product has three connected experiences. The investigation workbench handles individual cases. The financial-analysis workspace will explain patterns, reconcile measures and let analysts drill into the records behind a report. A demonstration and operations layer will make the project understandable and, after separate verification, usable in a controlled hosted environment.

| Experience | What a user should be able to do | Position today |
| --- | --- | --- |
| Investigate a transaction | Inspect the score and evidence, run an investigation, see disagreements, approve or reject, execute a simulated action and inspect its audit. | Implemented locally, accepted and integrated. |
| Analyze a portfolio of transactions and cases | Compare totals by currency and day, inspect data quality and case workload, drill into source rows, then produce controlled reports. | AN01 design accepted for prototype work; measurement prototype delivered for review. Production reports API/UI and exports are not built. |
| Understand or try the system | Watch a key-free recorded replay; later use restricted staging and explicitly supported live inference. | Recorded replay accepted locally. Real CI, hosting and visitor live inference remain separate work. |

### Three different jobs, three different kinds of evidence

- **Fraud scorer:** a rule or trained classical model ranks a transaction. Its score is not a finding of guilt and cannot authorize an action.
- **Investigation agents:** bounded analyst, investigator and reviewer roles interpret allowed facts and propose a disposition. Their outputs are untrusted inputs to the server.
- **Application and human:** server code enforces scope, checks facts and builds a precise proposal. A human approves or rejects it; execution is a separate request.

There are also three distinct evaluation questions. ML evaluation asks whether scores rank synthetic fraud well. Agent evaluation asks whether investigations produce useful, supported recommendations. Software verification asks whether authentication, state transitions, failures and simulated effects behave correctly. Passing one does not answer the other two.

### A realistic use, without pretending it is a bank deployment

A payments analyst sees a large transaction after a burst of small payments. Sentinel shows the stored rule or model score, the prior transactions that were actually available, and any permitted account facts. The investigator proposes a hold or escalation; a reviewer can challenge the reasoning. The analyst may recognize a legitimate supplier invoice and reject the proposal. If the analyst instead approves and explicitly executes, Sentinel records one simulated effect with an audit trail.

Later, a team lead could use the planned reporting workspace to ask whether alerts increased in one currency, how much review work is waiting, and whether a count agrees with its underlying transactions. These aggregates require their own scoped queries, known-answer tests and performance limits; they are not already available because the case screen exists.

Banks, payment processors, marketplaces and internal risk teams have related investigation needs. Sentinel is a portfolio and research implementation of those patterns. Real financial deployment would additionally require suitable data rights, domain validation, privacy controls, regulatory review and operational evidence. It currently connects to no bank account and moves no money.

### How to study the project

Read the pipeline and worked example first. Then study storage and time, the offline/online ML boundary, agents and permissions, and the UI. The later chapters explain reporting, evaluation and future uses. The final chapter is the current completion map and exact resume point. Technology names describe actual components unless explicitly labelled proposed.

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

The audit trigger protects normal application behavior, not against the schema owner or superuser. Backups include workflow tables in their inventory. G3D-P2 has since proved backup/restore with populated workflows and steps, including authority and corruption controls; it is accepted and integrated.

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
- An analyst claim check that was not stored is “not recorded, ” not verified.
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

Development cases include fault instructions that this manual runner does not apply. It records faults_not_applied; those failure scenarios are demonstrated in pytest instead. Runtime facts remain separate from evaluator expectations. Protected final-case evaluation, live comparisons and completed blinded quality review remain future work. The accepted preparation tools do not establish a live quality result.

C1 versus C2 is an end-to-end comparison with unequal evidence access. It cannot by itself prove that extra roles caused a quality improvement. Read docs/evals/agents/protocol-v1.md, docs/evals/agents/evaluator-runbook.md and scripts/agent_eval.py. Accepted P4a adds pilot supervision, bound review packets, safe extraction and offline scoring; chapter 21 explains the remaining evaluation work.

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

Model mode is explicit and needs operator-provisioned account profiles. The API and accepted local_stack helper support explicit investigator and adapter selection, including the three-role mode, with recorded restart settings. That configuration support is not evidence of a live provider run. The deterministic investigator stays the safe development default.

### Restart backup and process ownership

Local tools record the processes and folders they own. A stop must verify process identity, not kill by executable name. Failed cleanup keeps recovery state. The separate browser stack uses disposable clusters and private manifests; its tokens stay available for artifact secret scanning until teardown finishes.

Backup uses a PostgreSQL custom-format dump and restore into a new owned database, with migration inventory and audit checks. The accepted populated-workflow round-trip verifies stored workflow/step content, rather than showing only matching empty-table counts. The operator’s POSIX orphan-detection limits and PID-check-to-signal window remain disclosed.

Logs use safe request metadata; default web-server access logs can include query strings, so documented local launchers disable them. Metrics are process-memory counters without a public metrics endpoint. Log retention, cloud monitoring, capacity and hosted operations remain future engineering work.

## 17 Future financial analyst uses

The current case and model-report screens are a foundation for a broader financial data workspace. AN01 now has an accepted design and a delivered measurement prototype, but no accepted production reports API/UI. The uses below are proposed workflows and acceptance targets, not shipped banking capabilities.

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

A reviewed recorded replay without a model key is now accepted locally. The next release work is restricted staging, genuine CI, session lifecycle, retention, abuse limits and measured capacity. A local static replay is not a hosted service. Visitor BYOK must be request-scoped, secret-safe and isolated; never substitute a personal owner key or subscription bridge.

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

## 20 The financial-analysis workspace: what AN01 adds

The investigation workbench explains one case. AN01 is intended to explain a scoped collection of financial records. Its first production slice, S1, is planned as curated read-only reports rather than a free-form SQL console. Export and label-availability extensions are later S2 work. Saved queries, arbitrary natural-language SQL, settlement matching and new business domains require additional design; they are not silently included in the first reports slice.

**Two uses of stage names:** reporting feature slices S1/S2 describe future product delivery. The M1 benchmark also has orchestration stages named S1–S9. Finishing tiny benchmark stages S1–S9 does not ship the production reporting slice S1. Read each stage name with its task prefix.

### The report pipeline

1. Authenticate the session and check the future report capability under an accepted versioned contract.
2. Validate the requested UTC interval or local-date interval, timezone, cutoff, currency and page parameters.
3. Admit the operation only when both coordinator and held-resource capacity are available. Reserve before connecting.
4. Open a restricted connection, then start the report budget and one REPEATABLE READ READ ONLY transaction.
5. Arm positive statement and lock budgets before each statement. Run guard, consistency and result statements in the same snapshot.
6. Return typed measures with their currency, denominators, time semantics and change flags. End with ROLLBACK; reports do not write business state.
7. Show the chosen cutoff and server read time. The client measures receipt age using its own monotonic clock. A refresh is another read, not an investigation or action.

This is the intended production pipeline. The current M1 code is a measurement-only prototype in scripts, with no reports route or capability issuance. A copied budget adapter must still be checked for production equivalence before S1 can use it.

### Seven complete operations in the prototype

| Operation | Analyst question | Important distinction |
| --- | --- | --- |
| totals | How many matching transactions and how much money are present? | Keep currencies and exponents separate; do not add USD to INR. |
| daily_utc | How do counts and amounts vary by UTC day? | A daily row is a defined bucket, not a naive string prefix. |
| daily_ny | How do they vary under a selected supported local timezone? | This prototype operation serves the non-UTC choices; daylight-saving days can be 23 or 25 hours. |
| workload | What case work was created, completed or remains open? | Case creation, action completion and current backlog use distinct time bases. |
| quality | Do transaction/outcome records agree, and how long did ingestion take? | Unknown outcomes differ from real zero; counts and lag quantiles need defined denominators. |
| drill_first | Which exact records contribute to a report? | Stable order and page counts are part of the report contract. |
| drill_cursor | What is the next scoped page? | A cursor positions a query; it grants no authority and is validated against the request. |

M1 has 22 tagged SQL statements and 3 control templates. Statement and operation hashes bind a measurement to the exact SQL. Measuring a convenient query and shipping a different one would not qualify its performance.

### Correctness details worth understanding

**Time:** the proposed public UTC request range is [2000-01-01, 2038-01-01). A pinned local-midnight table covers extra dates from 1999-12-31 through 2038-01-02 because a UTC edge can lie in a different local day and the final day needs its next midnight. The five zones are UTC, Europe/London, America/New_York, Asia/Kolkata and Asia/Tokyo. Unsupported lookups are refused, not clamped. The 92-day request window is a policy choice.

**Snapshots:** each request gets one read-only snapshot, but two separate requests can observe different database states. An ingestion cutoff is a filter on stored ingestion time, not proof that every row with that timestamp had committed when an earlier request ran. The design includes consistency/change detection instead of pretending that a timestamp recreates an old commit snapshot.

**Money:** aggregate integer minor units and publish an explicit currency/exponent. Large totals use the specified integer-string representation at the API boundary. Avoid floating-point display arithmetic. A count of matching rows, a count with known outcomes and a flagged count are different measures.

**Capacity:** two admitted coordinators and two held-resource reservations are provisional process-local limits. Connecting, open and retired-but-not-finally-closed resources consume reservations. A coordinator timing out does not release a connection that still exists. Report quarantine must remain separate from workflow quarantine so a stuck report cannot quietly consume an investigation slot.

**Permissions and versions:** read_report and opt-in v1.3 are proposed for S1; they are not in the accepted active API. Strict older clients can be incompatible with sessions carrying the new capability. That compatibility boundary must be reviewed before introducing it.

### Why measurement comes before the production route

The provisional figures are 200,000 matching rows, a 5,000 ms report budget, a 250 ms rollback reserve and 2/2 capacity limits. They are not promises. The grid compares index configurations on both platforms, chooses one common configuration, measures complete operations, checks refusal/cancel/lock/no-reply behavior and compares matched storage designs. Missing required evidence means not demonstrated.

The tiny profile is a plumbing proof, not a smaller statistical version of production capacity. Its selected N* of 80 does not qualify 200,000 rows. The full grid has not run. A later resource/controller review must authorize it, and its disk estimates currently require a decision.

## 21 Evaluation preparation, local performance and the recorded demo

Three accepted supporting packages make the project easier to evaluate and explain. They answer different questions and must not be combined into one success claim.

### P4a: prepare a reviewable agent experiment

The accepted tooling supervises a bounded development pilot, records attempts and incomplete work, extracts pilot-owned data as the restricted runtime role, creates review packets with a binding to their exact contents, and scores completed or partial human sheets offline. It rebuilds recommendations from storage and refuses disagreement. Contradictory run records, duplicate or invalid sheet rows and stale packet bindings are refused.

A blank answer is unanswered, not a negative judgement. Supported plus not-checkable claims give the denominator required by the protocol, not a flattering rate that excludes uncertainty. An unacceptable hold is a completed bad recommendation and remains counted. Setup failures, refused investigations, dispositions, inconclusive results and unavailable usage stay separate.

Preparation is complete; live C1 versus C2 development evaluation is not. It needs explicit authorization, a recorded model/configuration and quota state, one registered pass, retained failure counts and completed blinded human review. The pilot's request latency is measurable. Its exact 150-second workflow-elapsed gate is not demonstrated merely by stored timestamps or a terminal step with elapsed_ms=0. An exact observer is separate design work.

Fault instructions that the manual runner does not apply remain labelled faults_not_applied. Development D11 alone does not establish a matched injection-control experiment. The frozen protocol, original failures and reporting limitations remain part of the evidence.

### PERF01: an initial local benchmark

PERF01 is accepted as a bounded deterministic benchmark, not a production load qualification. In its recorded small Windows sample, ingestion and reads succeeded at concurrency 1, 2 and 4. Investigations succeeded 12/12 at concurrency 1, 2/12 at concurrency 2 and 1/12 at concurrency 4; other requests were counted as capacity refusals because only one workflow is admitted per API process. No approval or simulated action occurred.

This shows the cost of an explicit concurrency policy, not that the system is broken or that more processes are automatically safe. It does not measure full reports, hosted capacity, live provider latency or fraud accuracy. A future queue or worker design needs its own requirements and measurements.

### DEMO01: show the system without a key

The accepted recorded replay captures one real deterministic synthetic case in ten frames. It shows no approval or action before the human boundary, then one approval, one simulated action and an idempotent retry. Its content validator and freshness checks bind the capture to the generator and production source it records. It is not a live agent result.

This is useful for an interview, a portfolio walkthrough and an eventual public key-free mode. A visitor can understand the flow without supplying credentials. Publishing or hosting it still needs a separate release step. Freshness currently covers the captured generator and src; changes in contracts, local_stack or lockfiles are not automatically covered by that freshness claim.

## 22 How to continue safely and keep context between chats

Git commits, the coordination queue and handoff documents preserve context. A long assistant conversation is not the project database. Opening a new chat does not erase committed code; it does require the assistant to read the correct references before acting. No chat automatically knows another chat's uncommitted work or private background-job state.

### How to read our task names

- G0–G5 are broad roadmap milestones, not individual commands. G5 is optional research.
- C01–C08 identify earlier backend/data/ML/CI/operator packages; U01–U03 identify UI/browser packages; I01–I03 identify integration packages. Their task numbers are historical ownership labels.
- G3A is agent design, G3B is the coordinator, G3C is the trace API/UI, and G3D is evaluation and operating preparation. A completed preparation task does not complete all of G3D.
- P4a means evaluation tooling; the live pilot is a later separately authorized step. AN01 is the analyst-reporting workstream; AN01-M1 is its measurement prototype.
- R numbers identify review findings. Closing a design finding proves neither implementation nor a performance value. A named commit and scoped acceptance determine what is actually complete.

### Our working method

- Main is the canonical accepted application and documentation. Codex coordinates independent review and local integration.
- Claude develops in its named task worktree and hands off an exact commit. Its passing checks are author evidence until independently reviewed.
- Cursor has already supplied the required substantive UI/browser contribution. Its original seven saved edits remain preserved; another tool does not overwrite them to resume work.
- All future commits and merge commits use PHANI465 <pgavara1@asu.edu> as sole author and committer, without co-author or AI trailers. Existing history is preserved.
- Heavy database, browser, benchmark and full-gate jobs run one at a time. Interruption can bypass shell finally blocks: verify processes, recovery state and ownership before clearing a stale lock or restarting.
- No live provider, account/auth probe, paid overage, full-size measurement, remote push or deployment is implied by a document describing it.

### Your last Claude prompt was correct

The instruction to read CLAUDE_AN01_M1_IMPLEMENTATION.md and implement the prototype and tiny proofs was the assigned task. Claude delivered that work as candidate 93583a. Do not send the original implementation prompt again as if nothing exists. Codex reviewed the corrections through b54de1a. R53/R54/R55/R57 and the post-rollback R56 case now close; only interruption inside close remains R56. Continue the final-close dispatch on the same branch, preserving every candidate and earlier failure.

A fresh Claude chat is reasonable after the large idle context you reported. Use the saved resume prompt linked in the source map below. It restores the exact candidate and points to the correction dispatch. It does not authorize a full-size benchmark or replacement implementation.


### New directions confirmed November 8

The owner chose research/decisions/private GitHub first. Accepted main is now in the
private PHANI465/agentforge-sentinel repository, with one listed contributor and Actions
disabled. The [decision ledger](../decisions/PROJECT_DECISION_LEDGER.md) records each
choice, status, source and revisit condition; [START_HERE](../START_HERE.md) restores context.

ULB/OpenML1597 was downloaded and validated: 284,807 rows, 492 fraud labels, anonymous PCA
features and no account IDs. It is a separate benchmark, not a p1 refresh or a source for
reconstructing cardholders. Current synthetic generation already spans many accounts,
currencies, activity patterns and fraud/lookalike scenarios. PaySim is a later licensed
candidate for account/type replay. Historical replay is not a live bank feed.

The first document feature will use local public/synthetic files. Microsoft MarkItDown
is a proposed extraction dependency behind an owned file interface, not unrestricted
URI access. Typed CSV/XLSX arithmetic, partial/OCR states and source locators are needed;
conversion alone neither proves fraud nor guarantees fewer model tokens. No new upload
route or parser dependency was added today.

For now an agent may provide explicitly automated development review in a separate
sidecar, with deterministic checks, a fixed evidence rubric, order/verbosity controls
and recorded failures. It does not fill a human review sheet or establish human agreement.
Claude Pro and Codex/ChatGPT passed fixed-response local connectivity smokes; that is not
an investigation-quality result. Cursor's included third-party inference is not assumed.

Metrics should explain precision, recall, false-positive burden, label/extraction coverage,
reconciliation, atomic claim support, completion and latency with their denominators.
No single invented fraud-confidence percentage. See [research](../research/2026-11-08-expansion-research.md),
[document proposal](../documents/DOC01-local-upload-proposal.md), [judge proposal](../evals/agents/automated-review-proposal.md)
and [metric vocabulary](../analytics/metric-explanations-proposal.md). Feature implementation
is the next isolated assignment after the active M1 correction handoff, not a side edit
to that branch.

## 23 What is complete, where we stopped, and what remains

This is the status as of November 8, 2026. **Accepted** means reviewed and integrated for the stated scope. **Delivered for review** means a candidate exists and its author's evidence is recorded; it is not accepted merely because tests pass. **Planned** means work remains. Local readiness is distinct from public production readiness.

### Completed and accepted

| Stage | Accepted result | Practical limits |
| --- | --- | --- |
| Foundation and contracts, G0 core | Typed domain/HTTP boundaries, scoped identity, migrations, isolated worktrees and reproducible checks. | Hosting/hardware experiments are not all demonstrated just because contracts exist. |
| Local case workflow, G1 local | Transaction, saved score, alert/case, investigation, human decision, simulated execution and audit. | No bank connection, hosted release or general live-provider quality claim. |
| Data and ML, G2 ML | Synthetic generator, temporal/label-aware features, baseline selection, pinned p1 model, online/offline parity and model-results UI. | One synthetic world; financial-analysis depth is incomplete. |
| G3A/G3B agent design and runtime | Bounded roles/tools, server claim checks, persisted state, capacity, failure handling and recovery. | Deterministic plumbing does not establish live-agent superiority. |
| G3C trace and clock corrections | Read-only trace API and UI, stale-response protection, unknown states and monotonic caller/database waiting fixes. | PostgreSQL realtime behavior and documented OS/process limitations remain. |
| G3D preparation, P1–P4a | Operator/runtime separation, fixture/reference fixes, populated workflow backup, operator selection, pilot packets and offline scoring. | Live development comparison and final-case evaluation remain unrun. |
| Local benchmark and replay | PERF01 and DEMO01, accepted for their deterministic laptop/static scopes. | No hosted capacity or deployment claim. |
| AN01 design | Reviewed r3.2 design with zone, stage-supervision and held-resource reservation corrections. | No active v1.3 report contract, production reports route or reporting UI. |

The latest accepted application/tooling integration is 871e31d40e93306cfde6617e814c2cb78ae67c9e. Its independent Windows and native Ubuntu gates each passed 810 tests plus the one allowed live-Claude skip, with six commands, same-run JUnit, HTTP, package and read-only ML checks. Main was a07ec12710c86b15f111d13e3384c4cf0c6c8f6e at the start of this guide update; the later documentation publication does not claim a new application gate.

The last applicable Windows product UI evidence is 133 unit tests and browser suites of 19 legacy plus 10 trace tests on the trace/clock release. Those suites were not rerun for later tooling-only work. A test count is evidence tied to a specific code state, not a universal completeness score.

### Delivered candidate: accepted for measurement-prototype scope

Exact **28dfcefb301b4657522181a400354f4c90d4abb7** is [independently accepted](../reviews/AN01-M1-28dfcef.md) for the AN01-M1 measurement prototype; R53–R57 are closed. It remains unmerged. No production Reports API, v1.3 contract or full-size benchmark was delivered by this candidate.

| Evidence | Status and meaning |
| --- | --- |
| Exact-commit gates | Saved clean-tree Windows/native six-command gates each report 968 passed and one allowed live-Claude skip. Codex validated both 969-case JUnit reports; the full suites were not independently rerun. |
| Independent probe | The original unmasked 12-case Codex probe passes 12/12 on 28dfcef, including the two inside-close cases that failed on b54de1a. |
| Resource ownership | A close that raises an interruption retains its owner and reservation with a retryable failed state. A confirmed retry releases once. Async bytecode windows remain documented prototype limits. |
| Tiny measurement | The earlier af6292f Windows C2:400 miss and f00df8c native C2:1250 miss remain failed. S9 is not demonstrated; no new tiny run was made for the close correction. |
| Still unqualified | 30 ms margin, 200k row cap, 5000 ms budget, 250 ms reserve and M/Q 2/2; production clock and 4 GB/backing-space constraints remain separate decisions. |

Read [the current review](../reviews/AN01-M1-28dfcef.md) and [START_HERE](../START_HERE.md). Earlier failed candidates and reports remain preserved.

### Remaining work in dependency order

| Next stage | Work to do | Evidence needed before calling it done |
| --- | --- | --- |
| 1 Integrate accepted AN01-M1 prototype | Review the exact merge against main, preserve reviewed source and all earlier evidence. | Clean integrated Windows/native gates; record separately from the candidate gates. |
| 2 Decide and measure reports | Resolve reply policy and realistic disk/workload bounds, then separately assign the full grid if resources permit. | Both platforms, common index choice, complete required cells, retained failures and qualified limits or an honest not-demonstrated result. |
| 3 Ship AN01 S1 | Review/freeze v1.3, implement capability and curated read-only API, integrate the report UI and known-answer/browser tests. | Browser → production API → Postgres with scope, exact money/time semantics, capacity/error handling and secret-safe lifecycle. |
| 4 Extend analyst depth | S2 exports/label availability and separately scoped saved analysis, reconciliation/cohort tasks as needed. | Controlled export content, correct denominators, data/label availability and independent known answers. |
| 5 Run agent development evaluation | Explicitly authorize the limited live pilot, record model/quota context and complete blinded reviews. | Attempt/failure accounting, security gates, supported/unsupported claims, quality and honest timing/usage. Exact workflow timing remains separately instrumented or not demonstrated. |
| 6 Evaluate held-out cases | Freeze chosen behavior and authorize a final evaluation separate from development tuning. | No repeated tuning on final cases; retained negative outcomes and limitations. |
| 7 Verify the release environment | Private GitHub publication is done with Actions off; real GitHub Actions, Linux browser execution and chosen platform/session/retention/abuse policies remain. | Runner and deployment evidence tied to actual source/configuration; no assumption that WSL equals hosted CI. |
| 8 Host, if chosen | Private source publication is done; package the replay for an audience and deploy a controlled service only after the host and budget are approved. | Reachable reviewed release, operational recovery, secret handling and realistic resource limits. Visitor BYOK needs its own accepted design and tests. |

Steps can be split into isolated tasks, but resource-heavy verification stays sequential. Reports and evaluation are separate workstreams; completing one does not demonstrate the other. macOS remains unverified and is not automatically a mandatory release target unless we choose it.

### Newly planned document and data work

DOC01 adds bounded local extraction first, then a separately reviewed upload/feedback API and UI. JUDGE01 adds a provisional automated review sidecar. An external-data experiment needs its own protocol and model identity; downloaded data is not a trained model. These changes do not qualify AN01 limits or authorize protected final-case work.

### Optional improvements after the core milestones

Currency-normalized features, calibration, drift monitoring, sequence models, entity graphs, retrieval/RAG, an isolated document reader, AML/scam modules and queues are worthwhile experiments when a measured weakness motivates them. They are optional extensions, not hidden requirements for declaring the present local investigation workflow complete. Each new domain needs its own labels, data rights, metrics, safety boundaries and comparison baseline.

There is no defensible single percentage for this open-ended roadmap. The local investigation product and preparation tooling are built. Reporting, local document feedback, measured agent value and a verified public release are the four substantial workstreams still ahead. The final-close R56 path is accepted for the prototype scope; integration and numerical qualification remain separate work. Full-size measurement is still unassigned.

### Source map and the next chat

- [Decision ledger](../decisions/PROJECT_DECISION_LEDGER.md) and [new-chat entry](../START_HERE.md).
- [Current project status](../STATUS.md) and [task queue](../TASK_QUEUE.md): current ownership and authorization.
- [November 10 checkpoint](AgentForge_Sentinel_Session_2026-11-10.md): current stopping point and preserved candidates.
- [Claude new-chat resume prompt](../prompts/CLAUDE_RESUME_AN01_M1_REVIEW_2026-11-08.md): read the current correction dispatch without repeating the original implementation.
- [AN01-M1 intake](../reviews/AN01-M1-93583a-intake.md): original delivery record; the completed review above requests corrections.
- [Milestone roadmap](../PROJECT_PLAN.md): complete planned product; proposed technologies are not all installed dependencies.
- [Active API contract](../../contracts/http/openapi.v1.2.json), [API notes](../api/README.md) and [trace contract](../api/investigation-trace-v1.2.md).
- [ML protocol](../../ml/protocol.json), [data card](../ml/data-card.md), [model card](../ml/model-card.md) and [frozen model report](../../ml/results/p1/test_report.json).
- [Agent protocol](../evals/agents/protocol-v1.md), [evaluator runbook](../evals/agents/evaluator-runbook.md) and [security notes](../security/README.md).
- [Reviewed reports design](../analytics/AN01-decisions-r3.md) and [prototype assignment](../prompts/CLAUDE_AN01_M1_IMPLEMENTATION.md). Candidate M1 write-up is on task/claude-an01-m1-prototype at docs/benchmarks/AN01-M1.md; read it with git show until integration.
- [Accepted tooling/demo release](../releases/Batch-r2-main-integration-2026-11-07.md), [populated backup proof](../releases/G3D-P2-main-integration-2026-11-06.md) and [operator-mode integration](../releases/G3D-P3-main-integration-2026-11-06.md).

For an interview, explain one transaction, one temporal leakage risk, one claim check, one human-approval boundary and one ambiguous failure before listing frameworks. Be clear that synthetic accuracy, deterministic tests and a static replay answer different questions. The project is strongest when every claimed capability has a traceable artifact and every unmeasured limit stays visible.
