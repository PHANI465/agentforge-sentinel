# G3D-P1: evaluator operator/runtime separation, deterministic development verification

**Delivered at 5811a29; current task is the
[R41/R42 correction](CLAUDE_G3DP1_REVIEW_FIXES.md) on the existing branch.** Core authority
tests pass; error/reporting probes require focused changes before acceptance. Do not
restart this original worktree-creation assignment. Original instructions follow.

Recommended coding assistant: **Claude Opus 5.5 / High**. This is a bounded database-role
and credential-isolation change with real Postgres negative tests, not an architecture rewrite.
It selects the coding assistant; Sentinel test investigators stay deterministic.

## Base, ownership and boundaries

G3C API/UI integration is accepted/tested at **f78869834597840934fb449da10c2adfb440145a**;
read its release record and current task/coordination AGENTS/STATUS/TASK_QUEUE with git show.
Create task/claude-g3d-evaluator-prep in E:/PHANI/sentinel-wt/claude-g3d-evaluator-prep
from current canonical main after that release is published; record exact base SHA.
Read scripts/agent_eval.py, runtime role/grant code, tests/support/agent_cases.py, the
accepted protocol-v1 and existing case/evaluator documentation before changing anything.
One editor only. Keep accepted worktrees and Cursor's seven saved edits untouched.

Own scripts/agent_eval.py, a new focused tests/test_agent_eval_privileges.py,
docs/evals/agents/evaluator-runbook.md and one branch handoff. Do not edit production src,
contracts, migrations/grants, frozen protocol/case/model/data/eval outputs, UI, dependency
files, lifecycle helpers, CI/skip allowlist or checker timeouts. Central coordination stays
with Codex. Backup and operator-helper tasks are separate; do not bundle them here.

## Problem and required behavior

The current manual runner uses one operator URL for session provisioning AND investigations.
Separate these authorities so comparisons exercise the same restricted runtime privileges
as the production API. Use operator authority only for the explicitly documented setup /
session provisioning. Authentication, case ingestion, evidence reads and investigation
must use the runtime connection and real service/coordinator path.

Design a clear CLI/configuration contract for both connections. Prefer environment-variable
names or another private local configuration rather than credentials in shell history /
argv. Do not print either connection string, password, bearer token or raw exception.
If retaining the old --database-url flag, define it as provisioning-only and refuse to run
without an explicit valid runtime configuration; never silently fall back to owner execution.
Both identities must address the same intended disposable database. Reject an unsafe
owner/superuser runtime configuration before any comparator/provider construction or case
run; reuse accepted privilege validation where appropriate without changing its grants.

Keep C0 and C2-det as the deterministic development defaults. Existing C1/C2 local live
comparators must still require explicit --allow-live and preserve account isolation with
no API-key/paid fallback. Do not pass that flag or make any provider call in this task.
Only runtime case inputs may reach roles; evaluator expectations and fault instructions
remain outside them. Preserve protocol names/denominators, unknown usage and honest
failure/refusal accounting. Do not imply every development fault is implemented by this
manual runner: document the actual supported development path and its limits.

## Meaningful verification

Write failing-first tests on the accepted base that demonstrate the authority separation
is absent, then pass with the fix. Use real disposable Postgres and the actual granted
runtime role. Prove the runtime cannot create sessions or alter schema while its seeded
case ingestion and deterministic investigation succeed. Prove provisioning occurs only
under operator authority and each investigation uses runtime authority, not just two
variables with different names. Cover mismatched databases, missing/unsafe runtime config,
typed safe failures and canary credentials never appearing in CLI output/error paths.
No seed/clock/token route, fake completed workflow or permission weakening.

Run a small reproducible deterministic development smoke (C0 and C2-det) with safe results;
report attempts, outcomes, failures/refusals and timing without claiming a final held-out
quality result. Do not generate or inspect final evaluation cases, tune the frozen fraud
model or change the promotion protocol. No new money/token-budget claims.

Run meaningful focused tests plus the required exact-clean-commit Windows/native backend
gates sequentially, with same-run JUnit and exact structured skip validation, frozen
exports and read-only ML reproduction. No new skips or altered assertions/timeouts.
No frontend edits means browser reruns are not required solely for unchanged UI; state
that scope explicitly. Preserve/diagnose any failure; do not rerun until green without an
explanation. Stop only verified test-owned processes and keep recovery state if uncertain.

New commits: PHANI465 <pgavara1@asu.edu> as sole author AND committer, no trailers and no
reset/rebase/amend. Commit explicit owned paths. Hand off exact SHA, failing-first proof,
actual platform results, deterministic smoke, cleanup and limitations. No merge to main,
remote/push/deployment, live model call, paid usage or final-case evaluation. Codex reviews
before the next G3D step. A useful negative/neutral live result later is acceptable; no
assumption that three roles outperform one.
