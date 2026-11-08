# Sentinel checkpoint: November 8, 2026

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

## Where we stopped

AN01-M1 is delivered for Codex review at **93583a7570ae78f254a2d69e9857b701b0e444ad**, task/claude-an01-m1-prototype. It is clean, unmerged and unaccepted. The previous prototype assignment was correct and is now a delivered assignment, not a fresh task to repeat.

The author reports Windows then native gates passing 876 + one allowed skip each. Tiny smoke at f00df8c remains not demonstrated because native C2:1250 missed a provisional reply margin. The final commit has cleanup and reply-arrival changes; no exact-final smoke is claimed. Independent review must examine changed C2/C3 assertions and timing, Windows clock and disk findings. No full-size measurement is authorized.

Main at the start of this documentation update: a07ec12710c86b15f111d13e3384c4cf0c6c8f6e. Accepted runtime/tooling remains exact tested 871e31d40e93306cfde6617e814c2cb78ae67c9e: independent Windows/native 810 + one skip, six commands, JUnit/HTTP/package/ML. This publication adds documentation and a static explanatory HTML guide only; it is not a new application test gate.

## Read these first

- [Complete current study guide](AgentForge_Sentinel_Complete_Project_Study_Guide_2026-11-08.md): full product idea first; pipeline, architecture, implementation techniques and examples; completed and remaining stages at the end.
- [Offline HTML guide](AgentForge_Sentinel_Complete_Project_Study_Guide_2026-11-08.html): the same guide with navigation, find, print and an illustrative pipeline walkthrough. No credentials, network or application connection.
- [Current overview and remaining work](AgentForge_Sentinel_Overview_and_Remaining_Work.md).
- [AN01-M1 intake](../reviews/AN01-M1-93583a-intake.md): pending review, not acceptance.
- [Claude new-chat resume](../prompts/CLAUDE_RESUME_AN01_M1_REVIEW_2026-11-08.md): restore context and wait, not repeat the build or benchmark.

## Three substantial remaining workstreams

1. Reporting: review M1 and resolve policy/resources; separately authorize measurement; accept v1.3 and implement S1 API/UI; later S2 exports/label availability.
2. Agent value: authorized development comparisons, blinded human review, honest quality/failure/usage accounting, then separately authorized final-case evaluation. Exact workflow-elapsed measurement is not inferred from stored marker times.
3. Release: actual GitHub Actions, Linux browser checks, chosen host/session/retention/abuse limits and authorized deployment. Recorded replay is already accepted locally. Visitor BYOK is optional separate scope; macOS is unverified rather than automatically required.

## Preservation and boundaries

No candidate is accepted by receiving a report. Preserve the tested Claude checkout, all failures and Cursor's original seven edits. No source/runtime/contract change, new dependencies, live/auth/account/final-case work, paid usage, remote push or deployment is part of this documentation update. All new commits use PHANI465 <pgavara1@asu.edu> as sole author and committer, without trailers or history rewriting.
