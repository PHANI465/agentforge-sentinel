# Sentinel decision ledger

Updated November 15, 2026. This is the decision-to-decision entry point for future Codex
and Claude chats. It complements numbered ADRs, STATUS and TASK_QUEUE; it is not a verbatim
transcript or automatic shared memory. Read [START_HERE](../START_HERE.md) first when resuming.

## How to maintain this record

Each new decision records date, owner/source, exact choice, reason, status, affected task
and what would change the decision. Keep confirmed choices distinct from research proposals,
implemented behavior and verified results. Supersede a decision with a linked new entry;
do not erase it or silently backfill an undocumented conversation. Evidence for a code
acceptance names the reviewed SHA. Auth tokens, private outputs and raw datasets stay out.

**D20261115-01 · public PDF review and dataset.** The owner requested a public
landing page, PDF explanation and deployment. The published site reads PDFs in
the browser and gives page evidence, so public visitors can use it without a
session or document storage. Publish the exact synthetic p1 snapshot, including
offline labels, with its checksum. Preserve the separate ULB research acquisition
and link to its source. The full hosted workbench remains open pending access to
a runtime and PostgreSQL. [Public site release](../releases/PUBLIC-SITE-2026-11-15.md)

**D20261115-02 · Vercel live synthetic demo.** Vercel CLI login restored deployment access. The free Neon resource and restricted API role serve scoped guest sessions with deterministic roles. PDF checks stay in the browser, with a decimal 10 MB cap. This updates the hosting status in D20261115-01. [Release evidence](../releases/PUBLIC-SITE-VERCEL-2026-11-15.md)

## Earlier decisions with recorded sources

**D20261115-03 · document insights and work split.** In the owner's pop-up answers,
they chose both single-document and cross-document review, initially invoices, statements
and payments, and clearly labeled synthetic scenarios plus official public reports.
They requested Codex's security/architecture foundation and GPT-6.1 Sol / High for all
remaining implementation. [Plan](../documents/INSIGHTS-ROADMAP-2026-11-15.md) and
[dispatch](../prompts/SOL_DOCUMENT_INSIGHTS.md) define source scope and verification.
Status: foundation implemented in its task branch; remaining product work assigned, not
delivered. Revisit when actual file-to-browser checks establish each capability.

**D20261115-04 · delegated privacy and subscription choice.** Owner asked Codex to
choose the better option and preferred existing subscription use. Chosen default is local
browser analysis; optional remote explanation requires explicit consent for selected
evidence and a separately reviewed budget/service before activation. ChatGPT Plus and
Claude Pro do not include ordinary API billing; OpenAI participating-tool allowance sharing
does not establish Sentinel eligibility. No consumer-login relay or new paid mode is
authorized. Current IAF's project-only configuration is unchanged. Sources and the future
activation checklist are in plan section 9. Status: policy/design, no document provider
calls or endpoint implemented. Revisit only with supported authentication, retention and
funding evidence.

These are retrospective summaries of written project records, not reconstructed quotes.

| ID | Decision and current meaning | Source |
| --- | --- | --- |
| H01 | Synthetic financial data and simulated actions are the local product foundation. A live bank connection is not implemented. | [Roadmap](../PROJECT_PLAN.md), [storage/API ADR](0002-thin-path-storage-and-api.md) |
| H02 | Scorers rank risk; model roles cannot grant permissions or approve. Human approval and explicit execution stay separate. | [Contracts ADR](0001-domain-contracts.md), [agent ADR](0007-three-role-workflow.md) |
| H03 | Preserve p1's frozen data/features/model/evaluation identity; new datasets or features need a separate experiment. | [Model-serving ADR](0006-controlled-model-serving.md), [ML protocol](../../ml/protocol.json) |
| H04 | Codex is the local main integrator. New commits use PHANI465 <pgavara1@asu.edu> as sole author and committer; no attribution trailers or history rewriting. | AGENTS.md, owner's recorded October26 instruction |
| H05 | Verification commands have an owner-approved 2700 s cap. Application deadlines, individual assertions and skip policy are not widened by it. | [ADR0009](0009-verification-command-budget.md) |
| H06 | Held-out final cases are separate from development. Unknown usage/timing and missing evidence remain unknown/not demonstrated. | [Agent protocol](../evals/agents/protocol-v1.md), [accepted pilot plan](../artifacts/AgentForge_Sentinel_G3D-P4_Development_Evaluation_Plan_2026-11-06.md) |
| H07 | Cursor delivered its contribution; its original seven saved edits remain preserved. Other tools work in isolated checkouts. | AGENTS.md and current [checkpoint](../artifacts/AgentForge_Sentinel_Session_2026-11-08.md) |
| H08 | AN01-M1 is a measurement prototype, not production Reports. Full-size measurement and performance values are not qualified. Final candidate 28dfcef is accepted for prototype behavior: R53–R57 close; numerical limits and full-size performance remain unqualified. | [M1 review](../reviews/AN01-M1-93583a.md), [r3.2 acceptance](../reviews/AN01-r31-2db42ee.md) |
| H09 | DOC01 Part A `cecccad` is delivered but changes-requested for R58/R59. A separate locked local worker is not yet an accepted upload/feedback feature; recovery must retain uncertain POSIX group state and a failed/incomplete child response must not become a successful extraction. | [DOC01 review](../reviews/DOC01-cecccad.md) |
| H10 | DOC01 candidate `69b51fe` closes R59's invalid-child-success finding but remains changes-requested for R58. An unreadable live `/proc` member must mean unknown/kept, never an empty group. No worker or upload integration is accepted yet. | [DOC01 re-review](../reviews/DOC01-69b51fe.md) |
| H11 | DOC01 candidate `7ec46ae` closes the unreadable-`/proc` case but remains changes-requested for R58: a PID-list snapshot can miss a group descendant forked after enumeration. Confirm group absence after the scan; no worker or upload integration is accepted yet. | [DOC01 re-review](../reviews/DOC01-7ec46ae.md) |
| H12 | DOC01 Part A `8f7bd87` closes R58/R59 and is accepted for a local, separately locked worker over public/synthetic files. Source integration is `662572e`. The Windows recovery-record replacement issue is a required follow-up before API exposure; browser upload, feedback UI and OS network isolation are not delivered by Part A. | [Final review](../reviews/DOC01-8f7bd87.md), [release evidence](../releases/DOC01-Part-A-main-integration-2026-11-12.md) |
| H13 | DOC01 Part B candidates `612934b`, `aca58f2` and `a3d1a6c` went through R60-R63 corrections. The last gap was a cross-process bridge record counted as zero kept while its owner was live. | [Final candidate review](../reviews/DOC01-B-d6d509e.md) |
| H14 | DOC01 Part B `d6d509e` closes R60-R63 for the local upload API. It is integrated on main at source merge `e51f47a` after sequential Windows/native full gates and the unchanged 19+10 browser suites. The document UI, private-customer use and hosting remain separate work. | [Final review](../reviews/DOC01-B-d6d509e.md), [integration evidence](../releases/DOC01-Part-B-main-integration-2026-11-13.md) |
| H15 | DOC01 Part C closes R64–R66 and adds local Document Review at verified source commit `3dfbc00`. An unavailable handle clears the display, and a matching success confirms deletion. Both backend gates and the 41 Windows browser cases passed. | [Part C release](../releases/DOC01-Part-C-main-integration-2026-11-14.md) |
| H16 | AN01-M1 prototype `28dfcef` is integrated at verified merge `1427b2c`. Both backend gates passed. Full-size measurement and the Reports feature remain separate. | [AN01-M1 release](../releases/AN01-M1-main-integration-2026-11-14.md) |

**D20261113-01 — active document contract.** HTTP v1.3 is accepted for the
opt-in local DOC01 API at source merge `e51f47a`; v1/v1.1/v1.2 stay frozen.
This supersedes only the implementation status and active-version wording
in the November 12 contract-order decision below. AN01 Reports remains a
later v1.4-or-higher proposal, without production endpoints or qualified
full-size limits.

**D20261112-02 — contract order for the next local feature.** The active HTTP
snapshot is v1.2. DOC01's opt-in upload/feedback backend takes the next
additive v1.3 because the owner prioritized completing the document feature
and AN01's public Reports API is still unassigned with unqualified limits.
AN01's accepted design used *provisional* v1.3 wording; only that version
label is superseded, and its eventual contract becomes v1.4 or later. Neither
route is implemented by this decision. Revisit only if an AN01 HTTP contract
is frozen before DOC01's v1.3 commit. See the [DOC01 Part B assignment](../prompts/CLAUDE_DOC01_PART_B_BACKEND.md)
and the [AN01 design](../analytics/AN01-decisions-r3.md).

## Owner decisions confirmed November 8

Source: owner's five explicit answers in this session, following a request to ask before
browsing, downloading, publishing or changing code.

| ID | Confirmed choice | Reason / boundary | Status and evidence |
| --- | --- | --- | --- |
| D20261108-01 | New **private** GitHub repository named agentforge-sentinel. | Publish under PHANI465, retain history and source credit; no public release. | Created; accepted main first pushed. [Publication record](../releases/GITHUB_PRIVATE_PUBLICATION_2026-11-08.md). |
| D20261108-02 | Public datasets for local research and benchmarking; check licenses/access/size first. | Supplement synthetic evidence without pretending every downloaded dataset is real or compatible. | ULB/OpenML1597 downloaded and verified in ignored private data. p1 unchanged. [Register](../data/external-dataset-register.md). |
| D20261108-03 | First document feature: **local use with public/synthetic PDFs, CSVs and spreadsheets**. | Private customer files and hosted multi-user uploads are later scope. | Approved direction; extraction/upload feature not implemented. [DOC01 proposal](../documents/DOC01-local-upload-proposal.md). |
| D20261108-04 | Plans reported, in the asked order: Claude Pro, ChatGPT Plus, Cursor Premium. Permit small live tests only within verified included quota, with no paid overage. | Subscription access is provider/product specific, not a pooled API budget. | Claude first-party Pro verified; Codex ChatGPT login verified. One tiny CLI smoke each passed. Cursor SDK inference not run. [Research](../research/2026-11-08-expansion-research.md). |
| D20261108-05 | Research, decision log and GitHub **first**, then assign implementation. | Avoid mixing a new upload feature into Claude's active M1 correction branch. | This publication is docs/research/acquisition, not feature code. Next design/implementation handoff is [prepared](../prompts/CLAUDE_EXPANSION_AFTER_M1.md). |

## Research decisions applied within that authorization

| ID | Choice | Why and status | Revisit when |
| --- | --- | --- | --- |
| D20261108-06 | Push only accepted main; keep Actions disabled for the first private publication. | Existing push workflow would otherwise start runner work. No paid CI allowance was verified; no workflow file changed. | Included budget and an explicit CI dispatch are verified. |
| D20261108-07 | Use ULB as a separate classification benchmark, not an account-profile source. | It has anonymous PCA features and no account IDs. Never reconstruct identities or invent account grouping from PCA. | Another licensed source provides valid entity/time semantics. |
| D20261108-08 | Preserve synthetic multi-account profiles for controlled replay; investigate PaySim for typed entity replay later. | Current generator already has varied account activity/scenarios. An online historical replay is not a bank feed. | A dataset mapping and causal replay protocol are reviewed. |
| D20261108-09 | Interim agent grading is **automated development review**, not human evaluation. | Separate sidecar records; no overwriting human review sheets or claiming human agreement without human labels. | A versioned judge design and later human calibration justify stronger claims. |
| D20261108-10 | Favor deterministic numeric/authorization checks before LLM rubric judgement. | Arithmetic and permissions must not depend on a judge's opinion; disagreements and uncheckable claims stay visible. | Evidence shows a task needs an additional learned check. |
| D20261108-11 | Use Microsoft MarkItDown behind an owned local-file extractor, not unrestricted URI access. | Its library/MCP capabilities differ. Default local text extraction needs no model; OCR/cloud routes can involve calls/cost. | DOC01's bounded worker/interface and dependency review are accepted. |
| D20261108-12 | CSV/XLSX money and dates use typed parsers; Markdown supports narrative evidence, not authoritative arithmetic. | Formatting conversion can lose table semantics; ambiguous amounts need confirmation, not guessed values. | A documented parser demonstrates exact reconstruction. |
| D20261108-13 | Reports show measures, counts, denominators and unknowns rather than one invented fraud-confidence percentage. | p1 scores are uncalibrated; extraction quality, model ranking and investigation quality are different quantities. | A separately validated calibration and decision policy supports a probability. |
| D20261108-14 | Do not bulk-download BAF yet. | Its current listing and repository datasheet disagree on dataset terms; repository code license is not the data license. | Original provider resolves applicable terms/version. |
| D20261108-15 | A fixed-response subscription smoke is connectivity evidence only. | Claude CLI reported two model identities; a single invocation is not necessarily one backend request. Codex's system overhead differs. | A registered, bounded evaluation records model/usage and comparable evidence. |

## What this does not authorize

No new production code, upload route, report contract freeze, full M1 grid, model training,
paid fallback, public hosting or protected final-case evaluation is performed by this
research publication. The latest explicit owner answers supersede older blanket no-remote/
no-auth wording **only** for the private GitHub publication and verified tiny subscription
checks described here. All unrelated safeguards and the active M1 correction scope remain.

## Decision template for the next change

Record: ID/date; exact owner request or accepted source; chosen behavior; alternatives
and reason; status (proposed/confirmed/implemented/verified/superseded); task/path; evidence
SHA and commands; remaining unknowns; supersedes/revisit trigger. Update START_HERE,
STATUS/TASK_QUEUE and the latest checkpoint in the same publication. A new chat must read
these files and inspect Git; the files do not automatically resume jobs or make old tests
valid for a new commit.

## Review decision November 8: corrected M1 remains changes-requested

D20261108-16 — Codex's [independent review of 5e0a578](../reviews/AN01-M1-5e0a578.md)
closes R53/R55/R57 and retains R54/R56. This is a review decision, not a new owner feature
choice. Actual author smoke records pass their unchanged baseline; mutated copies expose
qualification gaps. Preserve those records and all old failures. One newly registered
tiny pair in the narrow follow-up validates changed code only, no timing-limit claim or
full-size permission. DOC01 and live quality work stay separate. Revisit on the exact
next corrected SHA with independent regression evidence.

## November 10 review decision

D20261110-01 — [Independent b54de1a review](../reviews/AN01-M1-b54de1a.md) closes R54
and the post-rollback R56 defect. Interruption inside close still loses retained ownership;
R56 therefore remains open and no source integration is accepted. This is a scoped review
decision, not a new owner feature request. The final-close dispatch assigns no new tiny
benchmark pass: retain both timing misses, all old identities and the unexplained focused
startup failure. No numerical limit qualifies. Revisit after the narrow cleanup fix.

## November 12 review decision

D20261112-01 — [Independent 28dfcef review](../reviews/AN01-M1-28dfcef.md) accepts the measurement prototype and closes final R56. Saved exact-commit Windows/native gates each have 968 passes and one allowed skip; the original 12-case Codex probe passes independently. This is a scoped code review, not a qualification of the 30 ms margin or provisional row/time/capacity limits. The branch remains unmerged. Revisit production reporting only after separate integration and timing/disk decisions.
