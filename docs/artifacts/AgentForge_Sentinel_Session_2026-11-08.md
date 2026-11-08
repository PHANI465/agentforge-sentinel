# Sentinel checkpoint: November 8, 2026

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
