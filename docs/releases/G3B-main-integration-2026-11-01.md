# G3B main integration: November 1, 2026

## Accepted source and integration

Exact accepted candidate e23a7cde20d5d1db9202ea66a84f56c8130f3ac8 is the second parent of
merge **a7c71f553328b5872df53039daf572ad3b8fda81**, first parent 99370c5. The merge was
automatic with no content conflicts or hand resolutions. R34-R37 are closed under
[the independent acceptance](../reviews/G3B-e23a7cd.md). Source, tests, scripts, frozen
contracts, UI, model/data/evaluations, CI and dependency files match the exact candidate.
All new commits preserve PHANI465 <pgavara1@asu.edu> as sole author and committer; no trailers.
The containing final publication is documentation only, with the same tested code tree.

## Final integrated evidence

The Windows and native Ubuntu full suites ran one after the other on exact clean a7c71f5.
Both full backend reports contain **540 cases: 539 passed, zero failed, one allowed
live-Claude skip**. JUnit is captured from each strict gate's own pytest run, then validated
with ci_test_gate.py --validate-only; no second backend run was used merely to produce XML.

- Canonical Windows main: all six strict commands pass (Ruff, full pytest, 21 handoff helper
  tests, 15 legacy plus 15 agent schemas/85 examples, Node transport and clean package /
  installed inference check). Frozen HTTP export and read-only ML reproduction pass.
  Frontend: typecheck, 44 unit tests and build pass. Real API/Postgres browser suite:
  **19 passed**, including secret scanning, shutdown and entry-point harness checks.
- Native Ubuntu: the same six-command backend gate, exact skip validation, HTTP export and
  read-only ML reproduction pass as unprivileged sentinel. Native Node/uv/Python and PG16
  are the existing owned WSL environment. Browser execution on Linux was not performed.
- Independent candidate review, separate from these release checks: **90 Windows focused
  cases** and **six native R34-R37 probes** pass. The corrected late-cancel probe still
  fails on old b74473e for missing retirement. The other ownership probe uses real owned
  native sockets and forced descriptor reuse. No subscription or model provider was called.

Raw final evidence is ignored/local under canonical .agent/g3b-integration/windows-standard/
and /home/sentinel/g3b-integration-reports/; copied native JSON/XML and the final audit live
under canonical .agent/g3b-integration/. Reports bind the tested commit and clean tree,
while final-audit.json additionally binds the documentation publication. Candidate review
reports remain under .agent/g3b-review/e23a7cd/. No credentials are included in tracked docs.

## First integration run and retained limits

The first Windows integration run used Codex's external harness with SENTINEL_LOG_LEVEL=off.
That disabled propagation needed by eight logging-sensitive tests. Its failure was reproduced with that
setting; INFO/normal logging passes. Only the external runner was corrected, then the full
gate was rerun in the standard environment. The subsequent XML-validation CLI usage
error was corrected with --validate-only PATH against that same passing report; no
additional backend run was needed, and its usage log is retained separately. Windows
report-path escaping was corrected too; the original XML bytes were moved into ignored
evidence. The failed report/logs are retained under
.agent/g3b-integration/windows/; no product change, test weakening or skip was needed.

Earlier unexplained fixture retries and a slow statement from the b74473e focused Ubuntu
run remain undiagnosed; their old reports and unchanged assertions are retained. A passing
rerun is not a root-cause diagnosis, and no connection to R37 is claimed. Quarantined
helpers are bounded in count, not lifetime. Timing/limits are provisional, per process;
server commit durability, provider billing and global concurrency are not proven bounded.

The manual evaluator still needs operator/runtime connection separation, and backup/restore
still needs a populated workflow-table round trip before those paths can be claimed
verified. All data is synthetic; actions are simulated. No live agent-quality comparison,
GitHub Actions runner, macOS, Linux browser, hosting, public BYOK or production capacity
was verified. Main defaults stay deterministic; local live adapters remain opt-in.

## Next

[G3C-A](../prompts/CLAUDE_G3C_TRACE_API.md) is a new task for the versioned trace read
contract/API and fixtures. UI follows acceptance of that exact contract. G3D evaluation,
advanced analytics and public release remain separate. No remote/push/deployment or
additional spending took place. Accepted component checkouts and Cursor's original seven
saved edits are preserved.

## Operator convenience follow-up

The convenience local_stack.py up command currently accepts only deterministic and claude-cli
investigator flags; it does not expose the new three-role choice. The backend supports
three-role through API environment configuration and controlled tests. Add a tested helper
choice and a deterministic three-role operator smoke in a separate operations follow-up;
do not describe the old helper command as enabling three-role mode. No live adapter is
turned on automatically.
