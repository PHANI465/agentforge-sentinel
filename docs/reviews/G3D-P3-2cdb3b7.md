# G3D-P3 independent review: 2cdb3b7

Accepted November 6, 2026 for explicit three-role local operator selection. No blocking
finding. Candidate 2cdb3b73975511da4bd4551ee828505953c621f0 is a direct child of published
main f45c70347b8969d8bb8579ce95e644928d70611e. Review used a separate detached worktree
E:/PHANI/sentinel-wt/codex-g3d-p3-review, leaving Claude's checkout unchanged.

## Independent findings and evidence

- Explicit `three-role`/adapter selection retains deterministic single/rule defaults.
  Effective child configuration overrides inherited investigator/adapter values;
  deterministic modes remove the live model variable. Configuration-only live probes
  construct environments without launching or authenticating to a provider.
- The helper records effective adapter/live model and restarts from that record. Old
  deterministic records remain usable. Ambiguous three-role or live records refuse
  restart before smoke ingestion or termination. Status/down remain available.
- A different running investigator, adapter, model, scorer, database, API port or DB
  port is refused before database setup. Equal configuration is accepted. Process
  ownership, pending-launch, healthy-owned readiness and recovery code are unchanged.
- Real subprocess tests exercise the default and three-role API with disposable PG.
  The production runtime-role connection, config pins, three completed roles, ordered
  steps and trace persist across restart. The pre-approval state has zero approvals
  and actions; explicit synthetic approval/execution and an idempotent retry leave
  exactly one action. No browser human click or live-agent quality claim is made.
- Smoke reports all role runs and the finding-producing run, plus trace metadata,
  rather than assuming the final role is the investigator. Its scope stays rule-only.
- Production src, contracts/migrations/grants, model/data/evaluation artifacts, UI,
  dependency locks, CI, skip policy and checker deadlines are unchanged.

Independent Windows tests on exact candidate: **32 passed in 129.22s**, new helper,
existing ownership/startup and rollback suites. **Nine independent configuration probes
passed in 0.36s**: implicit live isolation in two modes, recorded model preservation
for both explicit live modes, invalid CLI choices before state creation, model/DB-port
mismatch refusal and legacy deterministic repeat-up compatibility. Ruff passes.
The first lint invocation was blocked by the read-only sandbox cache path; it did not
run lint. The permitted rerun used --no-cache and passed; no source change was involved.

Evidence: review worktree .agent/g3d-p3-review/{focused,probes}.{log,xml}; independent
probe source E:/PHANI/Interview/tmp/test_g3d_p3_review.py. These are independent results,
separate from the author's full gate. Review source remained clean.

## Nonblocking documentation corrections applied in integration

The runbook incorrectly said SENTINEL_CLAUDE_MODEL is never read. An explicitly selected
live mode reads that environment setting once (default sonnet), records it, then reuses
the record for restart. Implicit deterministic modes ignore it. Clarify this distinction.
The runbook also still labelled all POSIX operator paths untested. Native tests exercise
ordinary start/status/smoke/restart/down; orphan edge cases and the PID check-to-signal
window remain limited. Update the statement without claiming all POSIX paths are proven.

## Author evidence inspected, not counted as independent execution

Claude's exact-clean candidate strict records pass six commands on Windows and Ubuntu,
**666 tests plus one allowed skip**, 667-case same-run JUnit. The unchanged skip validator
accepts both saved reports. Windows strict ran 20:12:26-20:39:29 UTC November 6, native
20:41:04-20:47:57 UTC. Saved HTTP/ML outputs and native cleanup report pass. Baseline,
restart mutation and draft-test failures remain preserved in the author's evidence.
No live configurations were executed. The inspected native report is copied separately
at E:/PHANI/Interview/tmp/g3d-p3-author-native; original ~/g3d-p3-reports is untouched.

## Integration and limits

The local integration must pass complete Windows then native gates on its exact clean
commit, six commands, same-run JUnit/skip validation, frozen HTTP, packaged inference
and read-only ML reproduction. The 2700-second verification-command cap and every
individual/application deadline/skip remain unchanged. A later docs-only publication
does not inherit an exact-HEAD strict claim. Frontend/browser rerun is not required
for helper/tests/docs only and none is claimed. Prior UI/browser results stay dated.

Live mode is configuration-tested only; real subscription/provider behavior, measured
agent quality/security, macOS, real CI, hosting, capacity and Linux browsers remain
unverified. Existing local_stack POSIX orphan/check-to-signal limits remain. A stopped
stack still uses its recorded database port; this unchanged behavior is disclosed.
All data/actions are synthetic/simulated. No provider, final-case evaluation, paid
usage, remote/push or deployment. Preserve accepted worktrees and Cursor's seven edits.
