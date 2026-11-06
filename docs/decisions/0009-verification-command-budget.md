# Decision0009: verification-command budget

Accepted by explicit owner approval on November5 2026, America/Phoenix.

The six-command local checker now allows2700 seconds (45 minutes) per command, previously
1800. It still fails on timeout, launch error, assertion failure, dirty or changed tree.
This is a verification runner limit, not an application latency promise. No individual
test assertion/timeout, agent deadline, SQL/HTTP wait, approval rule, skip allowlist,
test selection or configured command changed. No dependency/model/contract changed.

On exact b246145, Windows full attempts reached506 then637 of648 progress markers before
the1800-second cap. No assertion failure was reported before cutoff; both attempts stay
failed, with no complete JUnit. The11 unreached cases pass separately. Native Ubuntu's
complete647+one-skip gate passed under1800. UI133 and browser19+10 passed. These establish
a command-runtime limitation on this laptop, not its cause. User-reported resource and
charging changes are recorded; programmatic power readings disagreed.

The owner approved the bounded increase after reviewing the concrete proposal. It does
not relabel prior failures, fix the unknown slowdown, certify production capacity or
permit live/paid usage. A new clean commit must pass the required complete Windows and
native gates sequentially, same-run structured skip gate, exports/package/ML and UI/
browser checks before integration is promoted. Earlier failed evidence remains intact.
