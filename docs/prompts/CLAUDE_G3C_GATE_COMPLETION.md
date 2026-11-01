# Claude G3C-A: finish existing gates at 16b67fd

Completed: exact 16b67fd is accepted under [the final review](../reviews/G3C-A-16b67fd.md).
This assignment is historical. Continue with [G3C-B](CLAUDE_G3C_TRACE_UI.md) in a new
worktree from its named accepted dependency, preserving the tested API branch.

Recommended coding assistant: **Claude Opus 5.5 / High**, continuing the current task.
Use it for diagnosing real gate failures and preserving contract/security semantics; this
is not a new implementation assignment or a request for provider calls.

Read current task/coordination:docs/reviews/G3C-A-16b67fd.md with git show. Stay in the
existing task/claude-g3c-trace-contract checkout at
16b67fd0cd09cdd08bbfa64a159035a7a188bf5b. Keep the tracked tree unchanged while its checks
run. Do not merge, start G3C-B or repeat already-completed work simply to fill a report.

1. Inspect the running Windows job/output and its actual completion status. Do not start
   another full suite. When it finishes, validate the JUnit from that exact strict run:
   python scripts/ci_test_gate.py --validate-only PATH_TO_JUNIT. Windows PYTEST_ADDOPTS
   report paths should use forward slashes or a safe relative path. Do not set a global
   log-off mode for the test suite; existing tests assert observable logging.
2. Before starting the prepared native runner, fix its ignored harness/preflight if needed.
   The current .agent/g3c/linux_gate.sh can continue after failed setup and returns the last
   echo's status. Guard clone/directory/fetch/checkout, exact HEAD, clean tree and native
   tools/unprivileged user. Collect all required check exits and fail the wrapper when any
   required step fails; do not interpret a final echo's 0 as a passing gate. This is an
   ignored local script adjustment, not a tracked code change or a new candidate commit.
3. Run the exact native candidate only after Windows finishes, as sentinel in the separate
   ~/g3c-trace-contract clone. Preserve /home/sentinel/agentforge-sentinel at a7c71f5.
   Require six passing strict commands, exact SHA and clean before/after, matching JUnit
   with only the allowed live-Claude skip, HTTP export and read-only ML reproduction.
4. Complete frontend typecheck/unit/build and existing 19-browser compatibility checks.
   Report actual results; those cases do not cover a trace UI. Keep secret scanning and
   ownership-verified teardown intact; preserve recovery state on a failed cleanup.
5. Return the exact full SHA, per-platform actual test counts and gate results, example
   export/ML outcomes, frontend/browser results, cleanup and remaining limits. Preserve
   every failed report. A later pass alone is not a root-cause diagnosis.

No source change is requested by this preliminary review. The small error-order table
correction and SETUP's active version can be handled by Codex at accepted integration;
do not invalidate this running code gate just for those doc edits. If a genuine code
failure requires a fix, write the meaningful regression and a new sole-owner commit,
then certify that new SHA honestly. Keep timeout/skip policy and assertions unchanged.
All new commits remain PHANI465 <pgavara1@asu.edu> alone, no trailers or history rewriting.
No live provider, paid fallback, remote/push/deployment, UI work or accepted/Cursor edits.
