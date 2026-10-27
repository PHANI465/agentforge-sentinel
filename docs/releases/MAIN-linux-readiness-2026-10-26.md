# Main: N2-N7 Linux readiness integration

October 26, 2026, America/Phoenix. The owner designated Codex as integrator. Merge 9e6b613d8533d6a2d6823fbd5b832069f3f3b358 combined exact coordination ddc3103 with accepted 48633a2fbe0ff477026830e60b36747eaa96154d automatically, without conflicts or manual resolutions. The containing documentation commit completes the integration; main is fast-forwarded only after its native Linux gates pass, then gets its own Windows full checks and browser run. No accepted task checkout or existing history is rewritten.

## What is integrated

- N2: native-platform orphan-launch test support.
- N3/N4: executed recovery-refusal coverage on Linux and Windows, plus explicit TCP-only disposable PostgreSQL startup.
- N5/N6: bounded identity-verified API group termination and exited-zombie handling; R29/R30 preserve recovery across retries and unreadable membership.
- N7: artifact-URL/hash pylock export for offline installed-wheel testing after a fresh locked sync.

Application/scoring behavior, frozen contracts/model/data/evaluations, UI, dependency pins, CI workflow, six-command check configuration and 1800-second bound remain unchanged. Relative to previous main a456f51, the only production-source change is disposable devdb startup. All code/test/script/dependency assets of the containing commit are byte-identical to accepted 48633a2; integration changes only documentation/instructions. Recorded sole-author policy and Claude attribution settings are preserved.

## Verification records for the containing commit

The [accepted candidate](../reviews/48633a2.md) has owner full passes of 449 backend tests and one allowed live-Claude skip on both platforms. Independent review passed 15 targeted cases on each platform and replayed the original failure probes. These are candidate results; they do not substitute for the integrated commit's validation.

Final validation is deliberately recorded after the containing commit, without editing tracked files to name their own SHA:
- Native Linux: /home/sentinel/linux-integration-reports/report.json, junit.xml and per-stage logs. A copied record is kept in canonical .agent/linux-readiness-validation/linux-report.json. Run the structured full backend gate plus lint/helpers/domain+HTTP/Node/package and read-only ML reproduction. Expect 450 collected cases with exactly the live-Claude skip; report actual results.
- Canonical Windows main: .agent/linux-readiness-validation/report.json, pytest-results.xml and logs; .agent/last-check.json must name current main HEAD, its clean tree, all six checks passed. Capture JUnit from that same pytest run and validate the exact skip set. Also run HTTP exports, read-only ML reproduction, frontend typecheck/unit/build and all 19 real browser/API/Postgres tests because the lifecycle helper changed.
- .agent/linux-readiness-validation/final-audit.json binds both platform reports, exact commits/trees, preserved assets and worktrees to the final main state. Earlier .agent/main-validation/ remains the a456f51 snapshot.

Do not read a stale/missing/running report as a pass. All reports must match the exact containing commit and clean source. Full backend runs are sequential across platforms, and unchanged source does not require duplicate full runs merely to change report format. Main's own Windows strict evidence is produced in its own checkout. No LLM/model provider calls occur; the deterministic investigator and SENTINEL_LIVE_CLAUDE=0 are used.

## Remaining work and limits

Native Ubuntu means the local unprivileged WSL backend environment, not GitHub Actions or a hosted release. Windows browser validation does not establish Linux browser/macOS support. Windows cold-cache remains unmeasured. /proc visibility and rare PGID reuse can require manual recovery; identity check-to-signal races and separate local_stack non-listening-orphan limits remain. Model quality is synthetic, uncalibrated and not a bank-performance claim.

H01's two low browser-hardening notes remain separate. The next product milestone is bounded evidence-analyst/investigator/reviewer orchestration with deterministic/one-agent comparisons; deeper analytics and public BYOK/hosting stay in the roadmap. Do not introduce frameworks/services before a measured need. A real GitHub run still needs an explicitly authorized remote. No remote, push, deployment or paid fallback is performed by this integration. Cursor can remain closed while quota is exhausted.
