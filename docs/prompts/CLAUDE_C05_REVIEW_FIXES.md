Current follow-up: b3b34ac resolves R19/R20 and both operator notes; R18 retains an effective PUBLIC privilege/object-identity gap. Read docs/prompts/CLAUDE_C05_R18_FOLLOWUP.md and docs/reviews/b3b34ac.md from latest task/coordination. The original assignment below is historical; do not repeat resolved corrections.

# Claude C05: correct R18-R20

Continue task/claude-backend-reliability in E:/PHANI/sentinel-wt/claude-backend-reliability. Reviewed candidate 0119ca73e6ae3b4df9f9eeffcea8b15911f716e6 has changes requested. Keep accepted C01 2e6c232 as its application base; no C02 merge is required. Preserve all existing/newer work and inspect actual HEAD/status before editing.

Read current shared instructions:
    git show task/coordination:AGENTS.md
    git show task/coordination:docs/TASK_QUEUE.md
    git show task/coordination:docs/reviews/0119ca7.md
    git show task/coordination:docs/prompts/CLAUDE_C05_REVIEW_FIXES.md

Own C05 backend/tests/docs/security and its branch handoff. No contracts/, web/, central STATUS/TASK_QUEUE or main changes. Do not merge task/coordination to copy its files; that checkout still carries older c6 source.

Write meaningful failing-first regressions, then fix:

1. R18 existing runtime identities: restricted role attributes are currently applied only on CREATE. A pre-existing superuser retains superuser and can disable audit triggers; even an ordinary existing role retains a direct CREATE schema grant. Validate attributes, memberships/SET ROLE reach, ownership and effective relevant permissions before changing passwords or privileges. Reject unsafe existing identities clearly; do not silently demote an operator or claim a successful least-privilege refresh. Keep safe idempotent runtime refresh and the actual runtime-role thin path. All tests use newly created role names in fresh disposable clusters; never mutate a real existing operator/database to prove the bug. Ensure rejection leaves unrelated role credentials/grants unchanged.
2. R19 connection timeout: replace substring matching with parsed connection-option detection using the installed psycopg API. application_name=connect_timeout_probe is not a connect_timeout option. Cover keyword and URI forms, misleading text in values and real explicit timeout settings; preserve explicit choices and never print credential-bearing strings. A capture of connect kwargs suffices for these cases; no 130-second external outage probe is needed.
3. R20 bounded metrics: normalize unsupported HTTP methods to one fixed metric bucket while preserving response behavior. Many distinct unauthenticated unsupported methods currently create a permanent label per request. Test fixed label cardinality, aggregate request totals and latency counts; retain route-template and status metrics.

Also handle the bounded operator notes while in these owned files: make SENTINEL_LOG_LEVEL=off match its documented behavior for first-use and INFO->OFF/root-handler cases, and narrow the 500 containment prose to failures before headers start. No streaming feature needs to be added. Keep the documented late-worker limitation; do not claim a process-wide work cap that is not implemented.

Contract decision: retain plain-text 500/C01 body-status shapes and the byte-frozen OpenAPI/examples. X-Request-ID remains optional diagnostics; no UI reliance until a later accepted HTTP revision declares it. Do not add a JSON 500 body, metrics endpoint or unrelated API feature.

Run focused role/reliability regressions, full ordinary checks and HTTP/domain exports with live Claude off. Update docs/security and the task handoff, stage explicit owned paths, inspect the diff, commit, then run final strict checks AFTER the final commit. Return the exact SHA, failing-first evidence, actual commands/counts, cleanup and limitations; do not borrow another checkout's report.

C02 is now accepted at 0e72b0bd599ff1707ca5b2507d65a0927894cbe0 for Windows local fixtures. No further C02 correction is required before its acceptance, apart from a nonblocking documentation note for an empty directory left if final rmdir fails. Cursor owns the remaining U01 R15 fix and U02 after U01 acceptance. The later integrator must rerun C02/backend/frontend/browser checks when combining accepted packages, preserving the C02 timeout/C06 checker edits. No main merge, WSL/GitHub provisioning, extra spending or live-provider test is implied. C03/C06/C08 still await separate review; C04/C07 retain their gates.
