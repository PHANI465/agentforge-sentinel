# Cursor U02: real browser -> API -> disposable Postgres

U01 is ACCEPTED at deb10370352dc62b0abfa2a5776c185494fcb04e. C02 is ACCEPTED at 0e72b0bd599ff1707ca5b2507d65a0927894cbe0 for Windows local fixtures. C01's frozen HTTP contract remains 2e6c2329aafe28b2e7c31ef5078d554cb66ca529. U02 is now ready. Preserve the completed U01 corrections; do not restart R14-R17.

Read current instructions explicitly:
    git show task/coordination:AGENTS.md
    git show task/coordination:docs/TASK_QUEUE.md
    git show task/coordination:docs/reviews/deb1037.md
    git show task/coordination:docs/reviews/0e72b0b.md
    git show task/coordination:docs/prompts/CURSOR_U02.md
    git show 0e72b0bd599ff1707ca5b2507d65a0927894cbe0:docs/api/browser-fixtures.md

## Branch and ownership

Use task/cursor-browser-e2e in E:/PHANI/sentinel-wt/cursor-browser-e2e, starting from accepted U01 deb1037. If this task branch/worktree already exists, inspect its ownership, HEAD and changes and reuse it safely; never reset or overwrite unfamiliar work. Otherwise create the dedicated task worktree. Include accepted C02 0e72b0b in this task branch, resolving only legitimate task-dependency conflicts, and record the merge/integration base. This dependency merge is not a main merge. Leave the accepted U01 worktree intact. Keep this U02 dependency combination stable. C05 a8294f6 is accepted separately and joins later combined-stack verification; do not interrupt/rebase running U02 work to include it. Do not merge task/coordination just to copy its docs.

Own web/ (including browser tests, small test adapters and package/lock), docs/ui/, your task handoff and the frontend workflow if needed. Do not edit src/sentinel/, contracts/, backend migrations, Python dependencies or accepted tests/support/ helpers. Request backend changes with an exact reproducible request, response/status and dependency SHA rather than inventing routes or changing the API contract. Models and subscription runtimes are off.

## Real stack and runner

- Use Playwright with the actual React UI, the accepted C02 real uvicorn API and disposable Postgres. Add only the required frontend test dependency/lock changes; use the installed/official browser runtime and report actual versions. Do not substitute a mock-only app or fake database.
- Set up the new worktree's own locked Python environment with the dev extra; verify Sentinel imports from this worktree. Do not accidentally run the older coordination environment. Live Claude stays off; do not use an external test database.
- Drive C02 start/seed/restart-api/restart-db/status/stop through structured process arguments, preserving real exit codes. start uses --parent-dir and always creates its own fresh child; it does not accept the old --state-dir. Parse its manifest path without printing tokens or a credential-bearing DSN.
- Start/readiness-check the API before starting Vite with SENTINEL_API_ORIGIN pointing to that exact random API port. Give the browser the actual Vite base URL; do not assume ports 8000/5173. Provide one reproducible command such as npm run test:e2e with bounded waits and reliable teardown.
- Seed short-lived approved states immediately before use with fresh single-use ordinals. Initial approvals expire after five minutes, so do not reuse one throughout a long suite. Use C02's backdated expiry fixture rather than sleeps or a test clock endpoint.

## Acceptance flows

Cover each with actual requests, rendered state and authoritative persisted state where relevant:
1. Enter the synthetic analyst session in the UI; ingest a synthetic transaction; investigate; inspect exact server-built escalation/hold fields; approve; execute separately; verify closed state and audit. Keep both hold and escalation rendering covered.
2. Reject a proposal and verify the resulting closed/rejected state; no simulated action is persisted.
3. Observe expired approval, reopen, re-investigate the new revision, issue fresh approval and execute; the old approval never becomes usable, and the historical expiry instruction does not persist after recovery.
4. Change revision out of band, then submit stale UI state; assert the handled 409 and authoritative refetch. Exercise the selected-case/filter behavior fixed in U01.
5. Provider-failure fixture: genuine failed run/provider_unavailable and reopened case, plus seeded failed-run recovery, without any model/network provider call.
6. Ambiguous execution retry: let the real server commit the first action, then drop its response in the browser/network layer. Exercise a UI retry with the same idempotency key and assert the original action ID and exactly one database effect. If necessary, make the immediate case read temporarily unavailable so the UI must retry while the outcome is still ambiguous; do not fabricate a committed action in a fake client. Keep duplicate click/concurrent retry coverage meaningful.
7. Session/capability isolation: foreign case absent from the UI queue; real API denial for foreign detail/audit/actions; read-only controls and the second-actor approval restriction match the accepted fixture semantics.
8. API restart and database restart preserve the case/action/audit and replay behavior. These must be real process restarts through C02, not reconstructed service objects.
9. Sign-out and browser reload clear the session; no token is recovered from URLs, localStorage or sessionStorage.

A small test-only inspection adapter under web/e2e/support/ may read the private manifest and query ONLY this disposable database through the existing Python dependencies to assert one action/audit/consumption. Return code-only or numeric assertions; never emit tokens/DSNs. No inspection/seed/bypass endpoint is added to the production API. Distinguish HTTP/UI observations from actual database assertions.

## Token hygiene and cleanup

Keep ephemeral bearer values in private manifest/test-process memory and in the necessary live Authorization headers. Keep them out of saved artifacts, captured headers, URLs, logs and reports. Disable authenticated-context tracing, raw network recording, video and sensitive DOM captures unless complete redaction is verified. Masking a password field or the fill step alone is not proof: action errors and reporters can include supplied values. Avoid raw credential-bearing error output and debug environment settings; verify both successful and deliberately failing test artifact paths with a synthetic-token scan that reports only pass/fail/counts, never the token itself. Post-login screenshots of synthetic cases may be saved after confirming no credential field/value is exposed.

Use finally/global teardown even when a browser assertion fails. Stop only the exact owned C02 stack via its manifest; preserve protected recovery metadata if shutdown is uncertain. Validate resolved owned targets before any cleanup, never kill by process name and never delete another run's database. C02 has a documented nonblocking final-empty-directory rmdir caveat; report/manual-clean only an exactly verified empty owned folder if encountered. Confirm owned API/DB processes and temporary token files are gone after successful teardown.

## Verification and handoff

Retain the current unit/regression and contrast tests. Run npm test, typecheck/build and the fresh browser suite on the final integrated code, plus backend/HTTP/domain/helper/Node checks from the accepted dependency stack. Coordinate bounded checker runtime with C02's accepted 900-second limit; do not weaken assertions to obtain a green result.

Update docs/ui/workflow.md with setup/run/teardown, actual browser/platform, fixture dependencies, token/artifact policy, tested flows and gaps. Record meaningful failing regressions for any UI correction made during U02. Stage explicit owned files, inspect for secrets, commit, then run final checks after the final commit. Return exact SHA, dependency/merge base, actual counts and commands, browser-to-database evidence, cleanup and remaining gaps. Do not claim Linux/macOS/CI/hosting or production fraud effectiveness without running/verifying them.

Do not merge main. C05 a8294f6 is separately accepted with R18-R20 resolved; its later integration requires the combined backend/frontend/browser checks. Finish the current U02 snapshot first. C07/U03 remain behind the model gates.
