Delivery update: R28 implementation is delivered at 353ecec and awaits Codex re-review next session. No further Claude rewrite is assigned. Follow docs/prompts/NEXT_SESSION_2026-10-26.md; preserve the original assignment below as history.

# C08 focused startup follow-up: R28

Read latest task/coordination:docs/reviews/784e101.md and current AGENTS/STATUS/TASK_QUEUE. C06 is now accepted at 4f06e32385424613fa0006b5bdbaab81ffea028f; preserve it. C08's 10 original focused checks passed, including the real rollback drill; only the concrete R28 startup paths below block this package. I02 f38e920 remains accepted and Cursor is not needed.

Continue task/claude-operator-prep in E:/PHANI/sentinel-wt/claude-operator-prep from exact 784e1014044920706a41bd91c61b965a03379999. One editor. Do not merge C06, rebase accepted dependencies or change main. Own scripts/local_stack.py, focused operator regressions, runbook and branch handoff. No production src/, contracts, model/artifact/lockfile/UI or central coordination edits.

R28A: Popen can succeed before identity() raises or returns unavailable. Current code saves no API record in that interval; down can then treat the API as absent and stop its database. Persist usable pending recovery authority before an inspection can fail. If identity cannot be established, keep an unresolved launch record and return nonzero; down must refuse database shutdown until owned exit and port closure are proved. Never kill a raw/unverified PID. Include a launcher-gone but child/listener-alive case as well as identity inspection raising.

R28B: start_api ignores the false result of wait_until(ready,...). A live owned listener then produces "API up" with no successful health response. Require actual readiness plus ownership for success. Timeout must return nonzero and either confirm owned cleanup or keep recovery. A bound port alone is insufficient.

Use the existing scratch probe E:/PHANI/Interview/tmp/probe-c08-784e101-startup.py for the exact baseline, but write meaningful committed regressions before fixing. Show they fail for the claimed reasons on 784e101 (not missing symbols). Use real main/up paths where practical; intercept destructive calls in negative cases and confirm no inappropriate kill/database stop. Retain tests for positive startup, failed-factory cleanup, known identity stop/retry, reuse/foreign refusal and actual rollback. Keep any extra changes narrowly necessary for these cases.

Use own locked dev/ml environment, deterministic investigation, SENTINEL_LIVE_CLAUDE=0, external test DB unset. No live subscription/provider calls or extra spending. Do not run concurrent full backend suites. After focused checks pass, commit explicit owned paths and run the required strict check on the exact clean final commit. Keep recovery state for a failed cleanup. Return full SHA, actual baseline/final checks, owned cleanup and remaining limits. No main merge, remote, WSL setup, push or hosting.
