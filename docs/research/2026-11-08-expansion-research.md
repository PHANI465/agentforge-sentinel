# Public data, subscriptions, automated review and document feedback

Research date: November 8, 2026. Primary sources below were actually opened; account
entitlements and software behavior are kept distinct from public documentation. The
[decision ledger](../decisions/PROJECT_DECISION_LEDGER.md) records owner choices and status.

## Current training and multi-account behavior

The frozen [p1 protocol](../../ml/protocol.json) generates 600 accounts over 150 days,
seed 7. Its stored experiment has 82,819 transactions and 581 synthetic fraud labels. Inputs
are 12 historical numeric features plus currency; unknown delayed labels are excluded
rather than relabelled legitimate. The selected artifact is a balanced CPU histogram
gradient-boosting classifier, not an LLM. No new model was trained for this research.

The generator already varies currencies, activity rates, typical amounts and account age.
It has account-takeover, card-testing and mule-cashout scenarios plus legitimate lookalikes.
Each account can have many events; application scope (tenant/session) is separate from
financial account identity. Current online ingestion is real application execution over
synthetic inputs, not connection to live accounts. The first replay extension should
preserve causal order, ingestion/label availability, source IDs and explicit synthetic
profiles. Do not claim that anonymous ULB PCA rows can be reconstructed into cardholders.

## Dataset acquisition

We downloaded ULB/OpenML1597 and verified its source MD5 plus a new SHA-256; see the
[register](../data/external-dataset-register.md). It is a separate benchmark with a
different schema, not a p1 training refresh. PaySim is a later candidate for account/
transaction-type replay. BAF is account-opening fraud, with unresolved terms differences.
Both are synthetic/generated sources despite originating from financial research.

Research references: [ULB metadata](https://www.openml.org/api/v1/json/data/1597),
[original ULB listing/API](https://www.kaggle.com/api/v1/datasets/view/mlg-ulb/creditcardfraud),
[PaySim listing/API](https://www.kaggle.com/api/v1/datasets/view/ealaxi/paysim1),
[BAF provider](https://github.com/feedzai/bank-account-fraud).

## What the subscriptions actually support

| Product | Official distinction | Local evidence and decision |
| --- | --- | --- |
| Claude Pro | [Plan guidance](https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan) says plan sign-in can back Agent SDK and claude -p within subscription limits. API-key/linked-credit routing is separate. | Auth status verified first-party claude.ai and Pro, with routing keys removed. One tool-free structured smoke passed; CLI reported Sonnet 5 and a Haiku 4.5 identity. No workflow comparison. |
| ChatGPT Plus / Codex | [Authentication](https://learn.chatgpt.com/docs/auth) separates ChatGPT sign-in and API-key access. [SDK](https://learn.chatgpt.com/docs/codex-sdk) controls local Codex threads; it is not a generic ChatGPT completions endpoint. | Installed CLI verified ChatGPT login. One ephemeral read-only fixed-response smoke passed with zero observed tool calls and no API key inherited. Plus is owner-reported; billing entitlement was not queried. |
| Cursor Premium | [SDK auth](https://cursor.com/docs/sdk/python) requires a Cursor user/service API key. [Current pricing](https://cursor.com/pricing) separates included Grok use from separately billed third-party models on Premium. | No SDK key, quota or Grok route was verified and no Cursor inference ran. Do not assume Claude/OpenAI through Cursor is included or enable pay-as-you-go. |

These are local development options, not a public subscription relay. A hosted visitor
must not use the owner's account. Anthropic's [product conditions](https://code.claude.com/docs/en/legal-and-compliance)
describe a distinct end-user-authenticated path; none is implemented here. Do not extract
OAuth tokens into a custom HTTP client. Use supported first-party CLI/SDK authentication.

The smoke prompts requested a fixed harmless response, with no project/customer data.
Claude reported 737 input/78 output tokens; Codex reported 15,702 input/14 output tokens,
including 9,984 cached input tokens. Different runtimes include different overhead, so
these are not a cost, speed or quality comparison. A CLI invocation can involve internal
provider work; no claim of exactly one physical model request or zero billed dollars is
made from token counts. What was verified is first-party login and no API-key fallback.
Usage and quotas remain shared with normal account work; stop on quota rather than retry
through a paid route. Do not expose raw account-status JSON or auth caches in Git.

## What internet research says about agent grading

The practical conclusion is to use a **constrained, evidence-bound development judge**,
not rename an agent as a human. These primary works inform the proposal:

| Source | Relevant finding | Implication for Sentinel |
| --- | --- | --- |
| [MT-Bench/Chatbot Arena](https://arxiv.org/html/2306.05685v4) | Judge preferences can depend on answer order, verbosity and the generating family. | Hide source labels; evaluate A/B and B/A; retain disagreements. |
| [G-Eval](https://arxiv.org/abs/2303.16634) | A structured rubric can align better with human judgements in its studied generation tasks, with limitations. | Use task-specific anchored fields, not an ungrounded overall score. No transfer of paper results to fraud. |
| [FActScore](https://arxiv.org/abs/2305.14251) | Long responses can mix supported and unsupported atomic facts. | Judge individual claims against the supplied evidence; citation existence alone is insufficient. |
| [LLMBar](https://arxiv.org/abs/2310.07641) | Attractive output can mislead instruction-following evaluators. | Plant polished but incorrect controls, abstentions and wrong arithmetic. |
| [Position-bias study](https://arxiv.org/abs/2406.07791) | Order effects vary across judges/tasks. | Measure swap consistency and ties; don't assume one instruction removes bias. |
| [Length-controlled AlpacaEval](https://arxiv.org/abs/2404.04475) | Response length is a confounder in preference measurement. | Match answer presentation and test irrelevant verbosity; do not rank by length. |
| [Prometheus 2](https://arxiv.org/abs/2405.01535) | Specialized open evaluators support direct and pairwise custom criteria. | Possible future local baseline; no download or laptop feasibility claim now. |
| [Adversarial judge study](https://aclanthology.org/2024.emnlp-main.427/) | Candidate text can manipulate a judge into inflated assessments. | Treat all evaluated text as untrusted data; no tools or authority for a judge. |
| [Multi-Agent-as-Judge](https://aclanthology.org/2026.acl-long.790/) | Explores multi-dimensional agent evaluation. | Separate evidence, usefulness and safety dimensions; multiple agents are not automatically independent ground truth. |
| [PDF-review injection study](https://aclanthology.org/2026.findings-aacl.64/) | Document layout/invisible text can target a reviewing model. | Include hostile public/synthetic documents in extraction and grading tests. |

[OpenAI's evaluation guidance](https://developers.openai.com/api/docs/guides/evaluation-best-practices)
also recommends concrete criteria/comparison tasks and validation against human labels.
No paper's reported agreement is used as Sentinel's own accuracy. A search result for
[Reliability without Validity](https://arxiv.org/abs/2606.19544) is **withdrawn by arXiv**;
its numerical claims are excluded as support. The [automated-review proposal](../evals/agents/automated-review-proposal.md)
specifies our intended controls. No judge study or protected final-case evaluation ran today.

## Microsoft MarkItDown: useful extraction, not a safety boundary

The [Microsoft project](https://github.com/microsoft/markitdown) supports PDF and office
conversion to Markdown under [MIT](https://raw.githubusercontent.com/microsoft/markitdown/main/LICENSE).
Its [dependency manifest](https://raw.githubusercontent.com/microsoft/markitdown/main/packages/markitdown/pyproject.toml)
offers format-specific extras. Use only required formats; no application dependency was
added today. Current main requires newer certifi than this project's holdback permits,
so a compatible pinned release or separate worker environment needs review; do not
silently relax the existing supply-chain rule.

The [MCP package documentation](https://raw.githubusercontent.com/microsoft/markitdown/main/packages/markitdown-mcp/README.md)
says it is for local trusted use, has no authentication, and can read permitted local
files or network URIs. We should not expose its unrestricted convert(uri) surface to a
visitor or role. Prefer a scoped uploaded-file handle passed to an owned parser worker.
Plugins are off by default; optional OCR/cloud/vision paths can make provider calls.
No OCR/Azure/LLM fallback should silently activate. Scanned pages may need an explicit
unsupported/partial result until a reviewed OCR path exists.

Conversion can remove irrelevant formatting, but token savings must be measured on the
same corpus/model/tokenizer with extraction coverage. Markdown tables can also get longer
or lose cell structure. Read CSV/XLSX numbers directly; preserve page/sheet/cell evidence.
Extracted document text remains untrusted and never becomes an instruction to tools.

## Concrete next work

Keep Claude's current R53–R57 task first. Then use the [next expansion handoff](../prompts/CLAUDE_EXPANSION_AFTER_M1.md):
an isolated DOC01 design/dependency proof, followed by a bounded extraction worker and
later reviewed API/UI integration; agent-judge sidecar and interpretable metric design
are separate slices. No production upload/report feature is implemented by these notes.
