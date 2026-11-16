# Sentinel hardening handoff

Updated November 16, 2026. Owner selected an invited-user pilot with synthetic
and official public files. The approved release targets are the private GitHub
repository and the existing Vercel project.

- Baseline `3f46ea6`. The application candidate is `e83f5ee`. Follow-up
  `28f8406` updates the worker's old provenance assertions and notices.
- Source and packaging scope covers the hosting wrapper, its SQL, dependency
  locks and browser verification. Backend application code, frozen HTTP
  exports, model artifacts and sample data are byte-identical to the baseline.
- Windows web verified typecheck and 266 tests with the refreshed toolchain.
  Three Windows hosted guard tests passed against a disposable PostgreSQL, and
  the public-document Chromium run passed with the four official PDFs.
- A clean snapshot produced 326 packaged files. Each digest was checked
  before upload. The negative probe refused a dirty checkout containing an
  unexpected untracked static file and created no output.
- The first full Windows worker run had 194 passes, 22 expected POSIX-only
  skips and one obsolete assertion about the old certifi holdback. The
  provenance follow-up asserts the reviewed packages and supported interpreter.
  That targeted check passed. The original failure log is preserved.
- OSV returned zero matches for 270 locked/vendored version identities.
  The upgraded npm audit also returned zero findings.

## Final verification

- Windows full backend run at `e83f5ee`: 1,100 passed, one expected skip and
  two failures caused by placing scratch files inside the checkout. The CI
  fixture inherited the outer pytest root, and the wheel probe correctly saw
  a checkout path where it required an external environment. All five other
  checker commands passed. The isolated fixture commit passed all 17 CI
  gate tests. The unchanged wheel test passed with scratch files on E:
  outside the checkout.
- The first Ubuntu gate at `146b3a4` found a synthetic evaluator failure and
  one browser fixture startup error. The browser fixture passed in isolation.
  A controlled backward-clock regression reproduced the evaluator's missing
  case and traceback on Windows. The correction uses one advancing UTC clock
  within each attempt and reports a missing case as a typed setup failure.
  Both failing-first regressions and the evaluator suites passed on Windows
  after the fix (25 tests).
- Ubuntu at `ae246a6`: all six strict commands passed, with 1,108 tests
  passed and one allowed skip. The same-run JUnit validated. HTTP v1.3
  exports matched and the read-only ML reproduction returned true. The
  separate document worker suite passed 216 tests with the one Windows-only
  skip. The test-only Windows fixes, evaluator
  correction and docs leave the deployed inputs and frozen assets unchanged.
- The packaged Windows browser smoke ran through real FastAPI and disposable
  PostgreSQL, including isolated guest sessions, denied document upload,
  investigation, human approval, simulated execution and idempotent replay.
  Owned local processes were stopped after the run.
- A 36-request local Ubuntu benchmark at `ae246a6` completed all 12 ingests
  and all 12 reads successfully. Investigations succeeded 4/4, 1/4 and 1/4
  at concurrency 1, 2 and 4, respectively. The other six requests received
  `agent_capacity_exhausted`. The run recorded zero approvals or simulated
  actions and verified cleanup. These results describe the local stack.
- The explicit archive allowlist rebuilt the same 326 release files byte for
  byte as the staged build. This ties the staged `e83f5ee` bundle to the tested
  runtime bytes in the follow-up commits.

Evidence lives in the two hardening worktrees' ignored
`.agent/hardening/` directories and the Ubuntu user's
`~/sentinel-hardening-native-reports` and
`~/sentinel-hardening-native-reports-r2` directories.

## Vercel staging

The candidate built successfully from `e83f5ee` at
[staged deployment](https://vercel.com/pgavara1-3079s-projects/agentforge-sentinel/6k8nB7Jy6dVUWPWXVYXYugWAea2P).
Authenticated read-only checks returned 200 on the document page,
workbench entry, IAF and health, with anti-framing and nosniff headers. The
staged session endpoint returned 503 with `private, no-store` before the new
Neon function was installed. The previous production deployment ID is
`dpl_AY2VARxMmcBdFtwnURMbY4L4fQbT` and is the rollback target.

The existing Neon resource was identified as `sentinel-demo-db`. Its owner
operation requires the SQL Editor or an owner connection. The tool session had
Vercel deployment access but the programmatic storage secrets retrieval
returned 403. Use the [additive SQL](../../hosting/vercel/request-limits.sql)
on that database. The SQL works with the existing runtime role and
does not change the earlier deployment's database entry points.

The Vercel CLI generated an automation credential while verifying the protected
URL. It was revoked by matching its creation timestamp, and absence was verified.

After database setup, verify a staged unauthenticated session call returns
401, run the synthetic browser flow with the expected headers and scope,
promote the staged build, then verify the public alias. If live checks fail,
restore the prior deployment by its recorded ID. Keep evidence by exact SHA.

## Pilot and scale

[Pilot readiness](../security/SENTINEL-PILOT-READINESS.md) records the reference
fields and reproducible official-document evaluation. The
[facilitator runbook](../runbooks/invited-document-pilot.md) describes the exercise,
review form and retention window. Participant feedback, broader document
qualification and scaled hosted measurements are separate operational steps.
Managed authenticated tenancy, customer uploads and raising limits are later work.
