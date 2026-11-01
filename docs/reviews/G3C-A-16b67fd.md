# G3C-A acceptance: HTTP v1.2 at 16b67fd

November 1, 2026 (America/Phoenix). **Accept and freeze**
**16b67fd0cd09cdd08bbfa64a159035a7a188bf5b** for the trace read API/contract.
No blocking findings remain in the reviewed scope. Decision 0008's new InvestigationTrace
read model, the v1.2 revision and the two live-schema assertion updates are accepted.
The frozen agents-1.0 TraceSummary is not silently changed into this response.

This is an **accepted dependency on its preserved task branch**, not a main-runtime merge.
Main application remains G3B a7c71f5; G3C-B starts from exact 16b67fd and API/UI integration
follows UI review. No full integrated-main gate or trace UI result is claimed here.

## Independent review and checks

Isolated Windows checkout with its own locked dev/ml environment: **95 passed**, 174.64s,
across trace/real-Postgres and legacy/v1.1/v1.2 HTTP tests; Ruff passes. Real HTTP auth,
foreign-session/tenant denial, workflow selection/cap, retry/revision, zero/legacy/running/
recovery cases, immutable reads and repeatable read during a concurrent recovery are covered.
Native Ubuntu: **3 passed**, 21.16s, independently exercising real HTTP authorization,
consistent snapshot during recovery and database-enforced read-only refusal.

Three extra real-Postgres probes pass on **each platform** with controlled adapters:
partial reported usage after a failed retry (one reported, one not-applicable, two unknown),
reported 0/0 kept distinct from null, and investigator tool-followup producing another
attempt 1 with no invented checks on the first output. These are plumbing probes, not
live provider/token/billing measurements. All test-owned clusters were stopped.

Review confirms scoped pure projection, one read-only consistent snapshot, stable
case-revision ordering, preserved legacy behavior, safe DTO fields, unknown data left
unknown and no inference about current late workers. Git comparisons preserve all frozen
v1/v1.1, agents-1.0, migrations/grants, G3B, model/data/evals, UI, locks and CI/check policy.
Owner-only author/committer and clean exact candidate are verified; Cursor remains untouched.

## Owner full-gate evidence verified

Windows and native strict records both name clean exact 16b67fd, six passed commands.
Their JUnit reports contain **581 cases: 580 passed, one allowed live-Claude skip, zero
failures/errors**. Each matches its current platform collection. The native individual
sync/strict/JUnit/HTTP/ML statuses are all 0 and ML reports reproduced:true. Its separate
clone /home/sentinel/g3c-trace-contract is clean; the accepted a7c71f5 clone is preserved.
These full gates are Claude's runs, not new Codex full-suite runs. Frontend 44/typecheck/
build and baseline browser 19 are Claude-reported compatibility; no new trace UI was tested.

The initial native non-login attempt's 127 logs are kept under attempt1-no-path. It ran no
checks and is not counted as a pass. Login-shell results above are the actual passing run.
Wrapper exit 0 alone was not used as evidence; structured records and individual statuses
were checked. Preserve fail-closed setup/aggregation in future runners.

## Frozen UI inputs and documentation addendum

- Source: exact 16b67fd, contracts/http/openapi.v1.2.json, SHA-256
  **b52f8fd4d323f59565b3e1148557cb85221b76c793377e021c32f9c877e5b053**.
- Sixteen examples under contracts/http/examples-v1.2/; record exact per-file hashes when
  copying into UI fixtures. The contract note is docs/api/investigation-trace-v1.2.md at
  the dependency commit. Current raw hash/probe reports are ignored under .agent/g3c-review/16b67fd/.
- Accepted correction to that note's error-order table: authentication failure is 401;
  for an authenticated caller UUID validation can return 422 before the endpoint's
  read_case check returns 403. Scope/not-found lookup follows. Four TestClient scenarios
  with an authentication stand-in prove this; it is not a permission bypass.
- At combined integration, correct that documentation table and SETUP's active version.
  SETUP remains correctly active-v1.1 on current main until API/UI integration. These
  documentation edits do not require a backend or frozen OpenAPI change.

## Remaining limits and next task

The read has no dedicated statement timeout; public load/retention/abuse protection is not
certified. Analyst checks and provider-submission flags are not stored; neither may be
invented by the UI. Limits are resolved only for the current matching config, per process.
No new UI, live comparison, final-case quality evaluation, macOS, real CI/hosting or Linux
browser test is accepted. Earlier G3B intermittent failures remain disclosed, not diagnosed.
Manual-evaluator least privilege, populated workflow backup and a three-role convenience
CLI option remain separate follow-ups.

[Assign G3C-B](../prompts/CLAUDE_G3C_TRACE_UI.md), **Claude Opus 5.5 / High**, from exact
16b67fd in a new worktree. Preserve existing approval/idempotency, contract bytes and
lifecycle/secret protections. Codex reviews the UI, then integrates API/UI together.
No provider call, paid fallback, push, remote or deployment occurred in this review.
