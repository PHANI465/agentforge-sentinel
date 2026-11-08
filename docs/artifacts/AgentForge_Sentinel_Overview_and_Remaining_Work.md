# AgentForge Sentinel: project overview and remaining work

## November 8 independent re-review of corrected AN01-M1

Corrected candidate **5e0a578be91b7739e5d08fc315dc37504f0df188** is reviewed, not accepted
or merged. [Review](../reviews/AN01-M1-5e0a578.md): R53/R55/R57 close for the reviewed scope;
R54 and R56 remain open. Independent Windows focused tests pass 123/123. Original 14 probes
pass after the disclosed fake read_at addition; eight additional probes on Windows/native
give six assertion failures, two controls and zero errors. Contradictory summaries/missing
control diagnostics still qualify; a post-rollback-reply interrupt can orphan ownership.

[Current Claude dispatch](../prompts/CLAUDE_AN01_M1_R2_FOLLOWUP.md), **Opus 5.5 / High**:
continue the existing branch from 5e0a578 with only those two fixes. Preserve93583a,
5e0a578 and all prior evidence. Author exact-commit gates are inspected/validated:
933 passed + one allowed skip on each platform; they are not independent full reruns.
Tiny stages completed on corrected code 73984b9, still no qualified limits or full grid.
The 30 ms margin, production clock and disk questions stay open. No candidate code merge,
full-size measurement or production Reports. DOC01 follows this correction handoff in
its own worktree; do not combine them. Accepted runtime remains 871e31d plus documents.

## Owner expansion: decisions and private GitHub

Read [the decision ledger](../decisions/PROJECT_DECISION_LEDGER.md) for every confirmed
choice and [research](../research/2026-11-08-expansion-research.md) for sources/evidence.
The private [GitHub repository](https://github.com/PHANI465/agentforge-sentinel) contains
accepted main; PHANI465 is the sole listed contributor and Actions are disabled.
ULB1597 is downloaded/checksummed privately, not trained. Included-access connectivity
smokes passed for Claude Pro and Codex/ChatGPT; Cursor inference remains unverified.
Local public/synthetic document feedback, provisional agent reviews and interpretable
metrics are prepared directions, not app features. [DOC01 handoff](../prompts/CLAUDE_EXPANSION_AFTER_M1.md)
follows the active M1 correction handoff in a separate worktree. New chats start with
[START_HERE](../START_HERE.md); no automatic job/context synchronization is claimed.

## Latest review: R53–R57 corrections next

Codex independently reviewed 93583a: the 66 existing focused tests pass; 14 additional
probes on Windows and native give 11 intended failures and 3 passing controls. The
[review](../reviews/AN01-M1-93583a.md) requests corrections for recovery locks, evidence
validation, statement deadlines, resource error paths and read-result/provenance semantics.
Use [the concrete Claude correction prompt](../prompts/CLAUDE_AN01_M1_REVIEW_FIXES.md)
on the existing branch. The prior wait instruction and intake descriptions below are
historical. The candidate remains unaccepted/unmerged; no full-size run or production
change is authorized. The accepted local application remains unchanged.

Updated November 8, 2026. Start with the [complete current study guide](AgentForge_Sentinel_Complete_Project_Study_Guide_2026-11-08.md) or its [offline HTML edition](AgentForge_Sentinel_Complete_Project_Study_Guide_2026-11-08.html). The [current checkpoint](AgentForge_Sentinel_Session_2026-11-08.md) records the precise stop. Earlier dated guides remain preserved historical snapshots.

## What we are building

A synthetic financial investigation workbench connects transaction ingestion, rule or trained-model scoring, evidence, bounded agent investigation, a human decision and an audited simulated action. The planned second workspace adds curated financial reports and source-row drilldowns. A demonstration/release layer includes an accepted recorded replay, with controlled hosting and optional visitor-key inference still future work.

The scorer ranks risk; agents propose; server rules and a human govern effects. It connects to no bank account and moves no real money. Synthetic ML scores, deterministic test success and a recorded replay do not establish real-world fraud effectiveness or live-agent quality.

## Accepted work

- Local transaction → score → alert/case → investigation → human approval → explicit simulated action → audit.
- Temporal synthetic data, reproducible CPU ML baselines and p1 serving, pinned inputs/results and model reports.
- Bounded three-role coordinator, typed scoped tools, server claim checks, recovery and read-only trace API/UI.
- Restricted database role, safe logs, revision/expiry/idempotency checks, package/install tests and Windows/native backend validation.
- Populated-workflow backup/restore, explicit operator mode/restart settings, safe evaluation preparation and review-packet tooling.
- Bounded deterministic local benchmark and key-free recorded replay.
- Reviewed AN01 r3.2 design for measurement-prototype work; public v1.3 and production reports are not frozen or implemented.

Accepted application/tooling is exact tested 871e31d, with independent Windows/native gates of 810 + one allowed skip each. Later main publications add documentation, not a new full-suite claim. Last applicable Windows product UI evidence remains 133 unit tests and 19 legacy + 10 trace browser cases; it is not rerun for tooling-only documentation.

## Current handoff, not accepted yet

AN01-M1 candidate 93583a is delivered on task/claude-an01-m1-prototype. The author reports final gates of 876 + one skip on Windows and native. Earlier tiny smoke ends not demonstrated after native C2:1250 missed a reply margin. Codex must review timing policy, changed assertions, clock observations, disk estimates and controller/resource ownership. See [the intake](../reviews/AN01-M1-93583a-intake.md). No full-size run is authorized.

## What remains

| Workstream | Next steps |
| --- | --- |
| Financial reporting | Review M1, resolve resources/timing, separately run approved measurements, review/freeze v1.3, implement S1 API/UI and end-to-end tests; later S2 exports and label availability. |
| Agent quality | Explicitly authorized development comparison and blinded human review, then separately authorized final-case evaluation; keep missing measurements and failures visible. |
| Verified release | Actual GitHub Actions, Linux browser checks, chosen hosting/session/retention/abuse controls and an authorized deployment. BYOK is optional separate scope. |

Optional future experiments include better currency features/calibration, drift monitoring, sequence/graph models, permission-filtered retrieval and new AML/scam domains. Each needs its own data, evaluation and security case. They are not prerequisites for the already working local case workflow.

## What to tell Claude now

Use the [new-chat resume prompt](../prompts/CLAUDE_RESUME_AN01_M1_REVIEW_2026-11-08.md), recommended Opus 5.5 / High. The previous implementation prompt was correct and has been delivered. Restore context, preserve 93583a and wait for Codex's specific review dispatch. Do not repeat implementation or start the full grid. Context persists in commits and documents; a chat is not shared runtime memory.
