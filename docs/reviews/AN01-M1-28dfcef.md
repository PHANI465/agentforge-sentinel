# AN01-M1 final-close re-review: 28dfcef accepted for prototype scope

November 12, 2026 (America/Phoenix). Exact candidate **28dfcefb301b4657522181a400354f4c90d4abb7** is clean on `task/claude-an01-m1-prototype`, a direct descendant of preserved `b54de1a`. The two new commits have PHANI465 <pgavara1@asu.edu> as sole author and committer, without trailers. The correction changes `ReportQuarantine` and `ReportConnection`, maintained R56 tests, the benchmark note and branch handoff. It does not change production source, SQL statements, contracts, dependencies, CI or the frozen model.

## Decision

**Accept the AN01-M1 measurement prototype at 28dfcef; close residual R56.** R53, R54, R55 and R57 remain closed for their reviewed scopes. This acceptance covers prototype behavior and the final-close resource ownership fix. It does **not** qualify the provisional 30 ms reply margin, 200,000-row cap, 5,000 ms budget, 250 ms rollback reserve, 2/2 admission limits, or full-size performance. It does not approve a production Reports route or v1.3 contract. The branch has not been merged into main by this review.

## Independent review and evidence

- I inspected the complete `b54de1a..28dfcef` diff and the relevant admission, quarantine, normal-close, retirement and retry paths. A connection whose `close()` raises `KeyboardInterrupt` or `SystemExit` now has a retained owner and `close_failed` state before the exception propagates. An unconfirmed close retains its reservation. A successful retry releases it once. The workflow quarantine remains separate.
- I ran the original independently authored, unmasked 12-case Codex probe against exact 28dfcef: **12 passed, 0 failed, 0 errors**. It includes the normal close, both post-rollback interruption controls and the two inside-close cases that failed at b54de1a. These are synthetic connection probes, not real measurement records or a full benchmark. The unchanged probe source is in canonical ignored `.agent/an01-m1-r3-review/probe_an01_m1_r3_unmasked.py`; this run wrote ignored output in the candidate worktree.
- The author reports maintained focused tests **158 passed on Windows and 158 on native Ubuntu**, plus adapted 14 and unmasked 12 probes passing on both. The new eight tests were run first against b54de1a: six intended assertion failures and two failures at the then-missing `owner()` entry point; 84 existing tests passed. These author runs are not independent gate results.
- I inspected both exact-commit `last-check.json` files and independently ran `ci_test_gate.py --validate-only` on both saved same-run JUnit reports (exit 0 each). Windows and native each report six gate commands passed on a clean tree, **968 passed and one allowed live-Claude skip**, 969 JUnit cases with no failures/errors. Saved HTTP v1.2/frozen legacy contract, package and read-only ML results also report pass. I did not rerun the full suites.
- `git diff --check` is clean. The candidate worktree remains at 28dfcef with no tracked changes. No new tiny smoke, full-size grid, live provider, browser test or production reporting route was run in this review.

## Limits retained

The author's documentation identifies untested asynchronous bytecode windows around `close()`. The implementation retains an owner/reservation through an unconfirmed close, but an interruption between reservation release and quarantine removal can leave a stale registry entry. This is a prototype limitation to address before a production report adapter; it does not reproduce the reviewed explicit `close()` exception defect.

The registered tiny pair at `af6292f` still has the Windows C2:400 miss and `S9 = not demonstrated`; the earlier native C2:1250 miss remains. No new measurement on 28dfcef supersedes either. The unexplained earlier focused startup stall also remains recorded. Production clock coarseness and the 4 GB/backing-disk preflight refusal are unresolved. Keep all old reports and source hashes bound to their own commits.

## Next step

Codex may plan a separate main integration of the accepted prototype, with conflict review and exact integrated Windows then native gates. Until that happens, main's application/tooling is unchanged. DOC01 can proceed in its separate worktree from accepted main; it must not import this unmerged prototype. Any full-size AN01 run needs a new decision on timing and disk bounds. No live evaluation, external training or deployment is implied.
