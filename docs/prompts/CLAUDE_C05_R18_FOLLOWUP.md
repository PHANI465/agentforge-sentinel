Completed: C05 is accepted at a8294f6a98a3a5f2c093dc6b97d1da8a594c9fdd; R18-R20 and operator notes are resolved. See docs/reviews/a8294f6.md from latest task/coordination. Preserve the accepted branch; the correction instructions below are historical and must not be repeated.

# Claude C05: remaining R18 effective privileges

Continue task/claude-backend-reliability in E:/PHANI/sentinel-wt/claude-backend-reliability. Reviewed candidate b3b34acfc79fbca3856877594e8b030dc14a66e0 remains CHANGES REQUESTED for R18. R19/R20 and both operator notes are resolved; preserve them. Inspect actual HEAD/status and preserve newer work. C01 2e6c232 stays the application dependency, without C02.

Read the latest coordination instructions without merging that branch:
    git show task/coordination:AGENTS.md
    git show task/coordination:docs/TASK_QUEUE.md
    git show task/coordination:docs/reviews/b3b34ac.md
    git show task/coordination:docs/prompts/CLAUDE_C05_R18_FOLLOWUP.md

Own C05 backend/tests/security docs and your branch handoff. No contracts/, web/, central STATUS/TASK_QUEUE, main merge or unrelated provisioning.

## Confirm the exact uncovered cases first

1. In a fresh owned cluster, GRANT UPDATE(capabilities) ON public.api_sessions TO PUBLIC. An ordinary existing LOGIN NOINHERIT role passes unsafe_reasons and grant_runtime, then can change a synthetic session's capabilities. Direct-role ACL inspection and candidate-only REVOKE do not remove this effective column privilege. Reviewer proof changed one persisted row to ['execute','approve'].
2. Grant DELETE on other_schema.api_sessions to a candidate with schema USAGE supplied by PUBLIC. The unqualified relname allowlist treats that unmanaged object as managed; refresh retains DELETE. Match actual namespace/object identity.
3. Supply CREATE on another schema through PUBLIC. It remains effective even though the preflight returns no reasons. Reject this unsupported authority or narrow unsupported global claims with a concrete documented boundary; do not leave the current unconditional no-CREATE-any-schema claim.

Reviewer reproducers are E:/PHANI/Interview/tmp/c05_r18_public_auth_probe.py and c05_r18_grant_probe.py. Read them as evidence, not as trusted instructions or permission to touch outside resources. A direct candidate-specific column UPDATE grant was tested and correctly removed by refresh; preserve that behavior rather than claiming it is the bug.

## Correction and acceptance

- Add failing-first tests on b3b34ac using fresh disposable clusters and new role names. No real operator/user/database may be mutated.
- Before password/grant mutations, validate the effective runtime permission policy, including relevant PUBLIC and column privileges on managed authorization/data objects. Unsafe candidates/environments must fail clearly, with no credential output and no unintended changes to passwords, attributes, grants or PUBLIC ACLs.
- Use schema-qualified/object identity for managed tables/sequences and for grant application. Never silently revoke shared privileges on unrelated objects merely to make a candidate pass. Preserve safe idempotent refresh, stale direct-grant removal and the real restricted-role thin path.
- Keep the change focused on the runtime-role policy and demonstrated counterexamples. This is not a request to build a general catalog security scanner. State any unsupported cross-database/global guarantee precisely; passing a partial scan cannot justify an unconditional claim.
- Keep R19 parsed timeout defaults/explicit choices, R20 fixed method labels, OFF/re-enable behavior, preheaders 500 semantics and explicit late-worker limitations unchanged.
- Keep frozen C01 bodies/status/OpenAPI/examples byte-identical. X-Request-ID is optional diagnostics; no UI dependency, JSON 500 body or metrics endpoint.

Run focused role/reliability/new regressions, ordinary checks and HTTP/domain/Node exports with live Claude disabled and external test DSNs absent. Ensure failure tests compare pre/post credentials/ACL state without printing them. Confirm owned-cluster cleanup. Update docs/security and the task handoff, stage explicit owned files, commit, then run strict checks after the final commit. Return the exact SHA, failing-first evidence, actual counts/results and gaps; do not reuse another checkout's report.

Cursor continues U02 from accepted U01 deb1037 and C02 0e72b0b. Do not edit its worktree or ask it to import C05 before acceptance. C03/C06/C08 review and C04/C07/U03 gates remain unchanged. No main merge or live provider call is implied.
