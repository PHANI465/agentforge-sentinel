# Next expansion: DOC01 design and bounded extraction Part A

Recommended coding assistant: **Claude Opus 5.5 / High**. Untrusted document bytes,
dependency separation, exact financial fields and owned parser lifecycles require care.

This is the next prepared assignment, **not a request to abandon or concurrently edit
the active R53–R57 branch**. Finish that handoff first. Read current coordination and
confirm no newer task supersedes this one. Start a separate task/claude-doc01-extractor
worktree from then-current accepted main; do not base it on unaccepted M1 code.

Read docs/START_HERE.md, docs/decisions/PROJECT_DECISION_LEDGER.md,
docs/documents/DOC01-local-upload-proposal.md, docs/analytics/metric-explanations-proposal.md,
docs/research/2026-11-08-expansion-research.md and accepted session/tool/cleanup contracts.

## Deliver a reviewable, real Part A without pretending upload is finished

1. Freeze a local worker protocol/design under docs/documents/, with typed extraction,
   findings, provenance, partial/unsupported/error states and concrete proposed bounds.
   Define how an owned file handle differs from an arbitrary path/URI. No public endpoint
   or frozen-contract edits. Propose later API/UI integration and version coordination.
2. Implement a separately locked tools/document_worker/ Python project with its own
   tests. Use an appropriate pinned Microsoft MarkItDown release and only PDF/DOCX/XLSX
   extras actually needed. Application pyproject.toml/uv.lock stay unchanged. Document
   release/license provenance; no relaxing the existing app certifi holdback.
3. Provide a local CLI/stdio prototype over public/synthetic owned files: text-layer PDF,
   CSV and XLSX; DOCX is optional only if included in the reviewed fixture matrix. Exact
   numeric/date extraction uses typed parsers, not reparsing Markdown for authoritative
   sums. Include page/sheet/row locators and explicit unparsed content. No arbitrary URI,
   macros, plugin/cloud/OCR/LLM fallback, direct transaction ingestion or financial action.
4. Run parser work in a bounded owned child process. Reuse accepted lifecycle concepts,
   verify ownership, keep recovery for unconfirmed stop, and prove hostile/oversized/
   malformed/encrypted/partial cases. Do not claim OS-level network isolation from an
   absence of HTTP calls. No install/system/network-policy changes beyond the worker's
   own locked environment; if hard isolation requires new facilities, document the gap.
5. Compute a tiny set of deterministic feedback measures (coverage, missingness,
   duplicate rows and per-currency reconciliation) on labelled synthetic fixtures.
   Uncertain/missing values stay unknown. Any LLM narrative and full browser upload are
   future parts, not completed functionality. Measure extraction fidelity and input-size
   changes; token savings need a specified tokenizer/model and are not assumed.
6. Finish source/fixture/protocol hashes, negative controls, tests and one bounded local
   smoke on Windows then native. Main's normal test gate does not collect worker-project
   tests: run and report the worker's own locked tests explicitly, with no skips hidden.
   Keep all resource-heavy jobs serial. Verify unchanged application source/contracts/
   locks, package/HTTP/ML identities; do not rerun unrelated product browsers without need.

Own tools/document_worker/, docs/documents/ and your branch handoff only. A genuine
application integration dependency must be requested concretely, not patched through a
protected path. No production src/web/contracts/migrations/grants/CI/checker changes,
other agent checkout edits, model training or protected final-case work.

All commits are PHANI465 <pgavara1@asu.edu> as sole author and committer, no trailers,
history rewriting or remote push. No model/auth/account calls or paid resources are
needed for this extraction Part A. Hand off exact SHA, own-test results, fixture coverage,
actual limits/cleanup and gaps. Codex reviews Part A before app upload/feedback integration.

JUDGE01 automated development review and new-data training remain separate assignments;
do not change the frozen human protocol, replace p1 or train on ULB as a side task.
