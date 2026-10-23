# Codex C02 review: c3fd83d

Exact commit: c3fd83df78f2d8e90598508f3779c33a3fdad0a5.
Branch/worktree: task/claude-browser-fixtures, E:\PHANI\sentinel-wt\claude-browser-fixtures.
Base: accepted C01 2e6c2329aafe28b2e7c31ef5078d554cb66ca529.
Date: October 23, 2026.

**Outcome: changes requested before C02 acceptance/U02 consumption. Cursor U01 continues against accepted C01.** These findings concern the test helper, not a regression in the accepted production API.

## R11 [P1]: require ownership before accepting or deleting a state directory

Locations: [browser_stack.py:145](E:/PHANI/sentinel-wt/claude-browser-fixtures/tests/support/browser_stack.py:145), [load:119](E:/PHANI/sentinel-wt/claude-browser-fixtures/tests/support/browser_stack.py:119), [recursive removal:231](E:/PHANI/sentinel-wt/claude-browser-fixtures/tests/support/browser_stack.py:231).

start accepts an existing --state-dir with mkdir(exist_ok=True), creates its own files inside it, and stop recursively removes the entire directory. A caller selecting a project or another populated directory can therefore lose unrelated files. Loading a JSON manifest checks only its version and also supplies its parent as the deletion target, without establishing helper ownership.

Safe independent reproduction used a fresh, verified temporary subtree with an unrelated canary file and fake services. start accepted the pre-existing directory; stop scheduled recursive removal of that directory. The deletion call was intercepted, so no canary, user file or project was actually deleted.

Correction: use a dedicated helper-owned directory. Either create a fresh private child under a caller-selected parent or reject pre-existing/unowned targets before writing. Validate ownership/marker, expected manifest and canonical paths before any process mutation or recursive removal. Refuse links/reparse points or resolved targets that do not match the owned directory. Do not overwrite another stack's active state.

Acceptance: a pre-existing nonempty directory and its canary remain unchanged; wrong/missing ownership and mismatched/redirected paths are rejected safely; default and explicit valid owned stacks still work. Tests use disposable verified paths only. Never probe this with a real repository/home/drive directory.

## R12 [P2]: preserve recovery state until both resources are confirmed stopped

Locations: [stop:216](E:/PHANI/sentinel-wt/claude-browser-fixtures/tests/support/browser_stack.py:216), [finally/removal:221](E:/PHANI/sentinel-wt/claude-browser-fixtures/tests/support/browser_stack.py:221), [startup failure:164](E:/PHANI/sentinel-wt/claude-browser-fixtures/tests/support/browser_stack.py:164).

stop_api can raise because API shutdown or ownership verification failed. stop nevertheless enters finally and deletes the directory whenever the database is stopped. The manifest and process identity can disappear while the API may still be alive. Startup failure handling also unconditionally unlinks the manifest after stop returns, even when database_stopped is false.

Independent safe probe injected an API-stop failure, simulated successful database shutdown and intercepted recursive deletion. The deletion was still attempted. No actual process was launched or terminated by that probe.

Correction: track API/database outcomes honestly. Remove an owned state directory only after BOTH shutdowns are verified. On uncertain/failed cleanup, return a failure and retain private recovery metadata rather than erase it. Startup-failure handling must follow the same invariant; it must not unconditionally delete the only recovery record. Document token retention/removal accurately for incomplete cleanup.

Acceptance: injected API-stop and DB-stop failures preserve recoverable owned state and report failure; retrying cleanup can complete. Successful stop removes the owned state. Readiness/crash startup tests remain green. Identity failures do not authorize killing an unrelated process. Include meaningful failure-injection regressions that fail on this commit.

## R13 [P2]: match fixture expectations to the accepted API

Locations: [browser-fixtures.md:74](E:/PHANI/sentinel-wt/claude-browser-fixtures/docs/api/browser-fixtures.md:74), [scenarios.py:151](E:/PHANI/sentinel-wt/claude-browser-fixtures/tests/support/scenarios.py:151), [scenarios.py:201](E:/PHANI/sentinel-wt/claude-browser-fixtures/tests/support/scenarios.py:201).

The rejected scenario promises that approving its rejected intent again gives 409 approval_exists. Accepted service.py:552 first rejects the closed case and actually returns 409 stale_case_revision. The current rejected test asserts only execution denial, so it misses that promised response.

The limited_capabilities manifest also says all denied operations are audited as action_denied. record_approval returns permission_denied before any audit write; only denied executions produce those audit events. The current test correctly expects exactly two execution-denial audit events.

Correction: update fixture manifest prose and docs to the actual accepted semantics. Add the missing real-HTTP rejected-intent reapproval assertion, and keep the execution-only audit wording accurate. Do not change production API behavior merely to match a mistaken fixture description.

## Evidence and scope

- Independently executed focused C02 suite: 13 passed, exit 0; 134.87 seconds. These are real Uvicorn/socket/PostgreSQL tests. They do not cover R11/R12 failure invariants or the missing R13 reapproval assertion.
- Independent read-only lifecycle probes and fixture/source review confirm R11-R13 as described. Dangerous deletes were intercepted inside a verified temporary test tree.
- Full baseline strict-check results, if completed separately, are additional evidence recorded externally against this exact commit. A green baseline does not resolve these counterexamples.
- All reviewer runs use deterministic investigations, no model calls and isolated disposable databases. Cursor's running checkout is not modified.

The 300-to-900-second helper timeout change is bounded and reasonable for the measured suite; checks still fail closed. C06 changes a different region of scripts/agent_check.py, so a later integrator must preserve both changes and rerun helper regressions. This review does not accept C06, Linux/macOS or actual Playwright execution.

U02 token-hygiene verification must include network headers and stored artifacts, not just visual masking of the token field. Keep traces disabled for authenticated contexts unless their complete redaction is actually verified.

## Next handoff

Claude corrects R11-R13 on the existing C02 task branch, updates its handoff, commits explicit task files and runs final checks after the commit. Return the new exact commit for Codex re-review. Cursor continues U01; U02 waits for accepted corrected C02. C05 may start in its own worktree from accepted C01 after the C02 correction handoff, without merging unaccepted fixture code. Main remains unchanged.
