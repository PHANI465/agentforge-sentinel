# Analyst UI workflow

Owned by Cursor. The API contract is accepted C01 `2e6c2329aafe28b2e7c31ef5078d554cb66ca529`.

From `web/`:

```
npm ci
npm test
npm run typecheck
npm run build
npm run dev
```

`npm run dev` serves the workbench and proxies `/healthz` and `/v1` to `SENTINEL_API_ORIGIN`. The default is `http://127.0.0.1:8000`, the same default as `scripts/smoke_thin_path.py`. The browser uses same-origin requests. The session token is typed into the page and kept in memory.

Ordinary UI tests use the frozen HTTP examples and a fake client. They do not call a model. `npm test` does not start Postgres. The browser-to-database suite is `npm run test:e2e`, described below.

`npm test` also covers review R14–R17. An escalation renders `transaction_id` and `reason_code` and does not invent an amount. Detail and audit stay on the case that was selected, and a queue response cannot overwrite a newer filter or page. A refresh that waited on overview asks for the filter and cursor that are current when that wait ends. The re-investigation sentence appears only for an open case whose current revision has no proposal; a historical `approval_expired` event stays in the audit after recovery, approval, and closure. Queue amounts use the ink foreground on the desk, on hover, on keyboard focus, and on the selected row. Score text keeps the alert color.

No AgentForge UI source is reused. `web/package-lock.json` is the frontend lock. Backend checks stay on the Python helper; this workflow is the frontend addition for the integrator to wire beside them.

## Browser to Postgres (U02)

Dependencies, merged in `task/cursor-browser-e2e` and not replaced by later work: accepted U01 `deb10370352dc62b0abfa2a5776c185494fcb04e`, accepted C02 `0e72b0bd599ff1707ca5b2507d65a0927894cbe0`, frozen C01 `2e6c2329aafe28b2e7c31ef5078d554cb66ca529`. The integration commit that joins U01 and C02 is `ab82c3ecd4d8252c99934a381becbf0289d78175`. Unaccepted C05 is not included. `main` is not merged.

Checkout: `E:/PHANI/sentinel-wt/cursor-browser-e2e`. The accepted U01 checkout stays at `deb1037`.

Setup from that checkout:

```
uv sync --locked --extra dev
cd web
npm ci
npx playwright install chromium
```

`npm run test:e2e` is the one browser command. It self-tests the artifact scanner, runs the shutdown harness, then Playwright starts `web/e2e/support/serve.mjs`. That process starts the accepted C02 stack with `tests/support/browser_stack.py start --parent-dir web/e2e/.runtime/stacks`, reads the printed manifest path and `base_url` (no token), and starts Vite on `127.0.0.1` at the port in `e2e/.runtime/vite-port.txt` with `SENTINEL_API_ORIGIN` set to that API. The run id in `e2e/.runtime/current-run.json` is passed to the server. Playwright opens the Vite URL. Ports are not assumed to be 8000 or 5173. `SENTINEL_LIVE_CLAUDE` is `0`.

The suite is serial on one disposable database. Short-lived approvals are seeded with `browser_stack.py seed` immediately before use. Expired approvals use the C02 backdated fixture. Restart coverage uses `restart-api` and `restart-db`.

Teardown reads only the runtime record whose run id matches `current-run.json`. A stale `runtime.json` is not authority and is not used to stop a stack or kill a process. Vite is terminated only when its recorded creation time, executable, command line, and this worktree's `vite.js` path still match the live process. An exited child is not killed by a recycled PID. A foreign or reused PID is refused, and the refusal is kept in `e2e/.runtime/recovery.json` without token values. The C02 stop result is checked; a failed stop keeps that recovery record. Teardown does not kill by process name and does not delete another run's database. If the owned `sentinel-browser-*` directory is a real directory, directly inside the recorded parent, and empty, teardown removes that empty directory. The scanner then checks `web/test-results` and `web/e2e/.runtime`, excluding only the exact owned stack directory and the exact private secrets file. A missing secret set, an unreadable artifact, or a directory named `stacks` inside `test-results` cannot produce a clean scan. A successful run leaves no API process, database process, manifest, or secrets file.

### This run

Windows 10, Node `v24.22.1`, npm `10.9.2`, Playwright `1.64.1`, Chromium `156.0.8078.4` (`browser.browserType().name()` and `browser.version()` written by the suite). This is not a Linux, macOS, CI, or hosting result.

### Token and artifact policy

Session bearers stay in the private C02 manifest, in `e2e/.runtime/owned-secrets.json` until the scan finishes, in the Playwright process, and in live `Authorization` headers. The sign-in field is set inside the page from a binding. Tests do not put the bearer in a Playwright fill or evaluate argument. Trace, video, and screenshot capture are off. The line reporter does not write an HTML or JSON report. Failure text is redacted before it is written to `e2e/.runtime/last-command.txt`. The scanner self-test plants a synthetic token and a fake DSN, including under a directory named `stacks`, expects those hits, expects an unreadable input and an empty secret set to fail closed, prints only counts and codes, and deletes the tree. The shutdown harness intercepts taskkill and stack stop and checks reused, foreign, missing, and exited process decisions without touching a live process. The last browser test is an expected post-login failure. Playwright writes its real `error-context.md`, and teardown requires that artifact and a clean scan of it.

### Flows covered

Playwright drives the React UI. Postgres assertions come from `web/e2e/support/inspect_case.py`, which reads the manifest and queries only that loopback database. It prints ids, counts, and codes.

1. Ingest a synthetic transaction, investigate, render the server escalation (`unusual_amount`, transaction id, no amount), approve, execute, closed case, one consumed approval, one action, and `action_succeeded`.
2. Two prior transactions, then a large one: the server hold amount and transaction id render, then approve and execute, with one action row.
3. Reject: closed, the proposal is `rejected`, no simulated action.
4. Expired approval: execute reopens the case, the recovery sentence shows, re-investigate removes that sentence, the `approval_expired` audit remains through the new approval and closure, and the old approval still returns `approval_outside_validity`.
5. A slower detail response does not replace the later selected case.
6. An out-of-band revision returns the stale-submit message and the server state. A closed filter chosen while overview is delayed is the filter used when that refresh continues.
7. Amount `777777` fails `provider_unavailable` with no intent and no action. A seeded failed run can be investigated afterward. No model provider is called.
8. The browser drops a committed action response and the following case read. Retry uses the same idempotency key. The database has that one action id.
9. The same execution is sent again while the first request is in flight, once from the page and once directly. One action id, one replay.
10. Two activations of Execute before the button can disable send one request and leave one action.
11. The foreign case is absent. Foreign detail, audit, and investigate return `not_found`. The read-only session cannot approve or execute. The second actor's execute is `action_denied`. A denied approval writes no approval row.
12. API restart and database restart keep the closed case, the same action id, and a replay of the original idempotency key.
13. Sign-out and reload leave the session field empty. The bearer is not in the URL, cookie, `localStorage`, or `sessionStorage`.
14. After sign-in, an expected failure writes Playwright's `error-context.md`. The page text does not contain the bearer, and teardown's scan of that artifact reports no hits.

A closed case leaves the executed proposal on its earlier revision, so the file shows that revision as approved and executed, plus the audit line. The current revision has no new proposal.

### UI correction found while running U02

Two native clicks on Execute in the same turn both called the API, because `disabled` waits for a render. `Workbench` now ignores a second mutation until the first finishes. `src/ui/App.test.tsx` failed first with two execute calls, then passed with one. The browser suite then recorded one POST and one action row.

### R21 and R22

Reviewed commit `7190c59da14198960397ba02b1edfc35be244a80` killed any live PID whose command line contained `vite.js`, and it could scan with an empty secret set after the manifest was gone. The shutdown harness now refuses a foreign Vite path, a reused creation time, a missing identity, an already exited child, and a stale run id, without issuing taskkill. A failed stop keeps recovery metadata. The scanner detects a canary when the manifest is absent, scans an artifact directory named `stacks`, and fails closed on an unreadable path or a missing secret set. The browser suite still covers the original flows and ends with a real post-login failure artifact.

### Gaps

Linux, macOS, CI, and hosting are not run. This does not measure production fraud detection. C05 is not in this branch. `main` is not merged. C07 and U03 stay behind their model gates. `npm audit` is not treated as acceptance.
