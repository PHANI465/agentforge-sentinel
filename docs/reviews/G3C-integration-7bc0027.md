# G3C integration review: 7bc0027, native release gate blocked

November 2, 2026, America/Phoenix. Candidate **7bc00272e083bb30d673eb4b11311623b992f942**
on task/codex-g3c-integration combines canonical documentation main 0caadda and accepted
UI 6014680 (containing accepted API 16b67fd). The merge is automatic with no conflicts.
No application, test, contract, dependency or model/data bytes differ from accepted UI
6014680. Only queued documentation/current-coordination corrections are added. The merge
and later publication have PHANI465 <pgavara1@asu.edu> as sole author/committer, no trailers.

**The integration is NOT accepted for main.** Main application stays G3B a7c71f5.
R38/R39 UI closure stands separately under [its review](G3C-B-6014680.md).

## Exact-commit results, sequential platform runs

| Check | Windows | Native Ubuntu, sentinel UID 1000 |
| --- | --- | --- |
| Six-command strict | All six pass | Five pass; pytest fails |
| Full suite, 595 cases | 594 pass, one allowed skip | 592 pass, two fail, one allowed skip |
| Same-run structured JUnit validation | exit 0 | exit 3, correctly rejects failures |
| HTTP frozen/current export | pass | pass separately after failed gate |
| Read-only ML reproduce | reproduced true | reproduced true separately |
| Frontend type / unit / build | pass / 133 / pass | not run |
| Real browser suites | legacy 19, trace 10 pass | not run |

Windows full pytest took 1335.16 s; strict six commands took 1429.016 s. Native strict took
410.573 s. Reports bind exact 7bc0027, with clean before/after. Full suites did not overlap.
Browser scanner and lifecycle harnesses passed; no recovery state was left by these runs.

## Two unresolved full-native failures

1. tests/test_agent_bounds.py::test_withheld_terminal_commit_reply_is_unknown_within_the_budget:
   outcome unknown is returned correctly, but the response interval was 2.953205276 s,
   exceeding the unchanged <2.5 s assertion for its two-second terminal budget.
2. tests/test_agent_workflow.py::test_uncertain_commit_reports_outcome_unknown:
   initial outcome unknown and the investigating state pass. After advancing the test
   clock, recovery returns conflict rather than investigation_recovered. Entire test
   duration was 2.652 s. Do not assume this has the same cause as the first failure.

The same source passed on the earlier component native run at 6014680. That contrast is
not a root-cause diagnosis and does not invalidate the failed integration report.

## Diagnostic evidence, not a fix

One targeted native run of both tests plus test_commit_refused_by_its_timeout_is_a_known_rollback
uses an external pytest fixture wrapping bounded_call/commit to observe timings without
altering source, deadlines or assertions. All three pass. In that run the withheld terminal
commit takes about 1137 ms and recovery's deferred COMMIT about 3009 ms. The observations
do not establish the earlier cause, eliminate state/order effects or certify a full run.
No further full rerun was started and no test/budget/skip was weakened.

Next investigate predecessor/state effects, actual waiter/cancel/retirement/connection
timings and recovery's failure classification. Preserve the distinction between unknown
COMMIT and known rollback; do not infer durability from a response or fix by adding sleeps.

## Evidence and preservation

Windows originals are in the integration worktree .agent/g3c-integration/windows/.
Native originals: /home/sentinel/g3c-integration-reports/ and /home/sentinel/g3c-integration-diagnostics/.
Canonical ignored copies are .agent/g3c-integration/windows/, native-first-failure/ and review/.
The failed XML, strict JSON, safe failure summary and complete diagnostic observations
are retained. The initial archive attempted WSL-to-NTFS timestamp copying, which was
refused; byte-copying completed the archive without changing product files.

Native owned-user process inspection found no remaining Postgres or Sentinel uvicorn,
and no unreadable own process records; Windows stack directories are empty with no recovery.
Candidate/integration/review checkouts are clean. Cursor's original seven edits are unchanged.
No API/model/contract change, main application merge, remote/push, deployment, live provider,
paid usage, final-case evaluation, Linux browser or macOS run occurred. Real CI/hosting
and capacity remain unverified.

Use [the focused Claude investigation](../prompts/CLAUDE_G3C_NATIVE_INTEGRATION_DIAGNOSIS.md),
Opus 5.5 / High. Integration's error-order/SETUP corrections are already present in 7bc0027;
main's older SETUP remains correct for the older runtime until release acceptance.
