# Handoff for task/codex-browser-hardening

- Task: H01, the two non-blocking browser-hardening suggestions from accepted I02.
- Tool and worktree: Codex, E:/PHANI/sentinel-wt/codex-browser-hardening.
- Date: October 27, 2026, America/Phoenix.
- Base: exact main 5d4266e9cbcf7e1c198b286ab3640e7206a1fc82; application baseline c8b9477.
- State: narrow fix prepared for integration and final scoped verification.
- Changed paths: web/e2e/support/inspect_case.py, web/e2e/workbench.pw.ts,
  tests/test_browser_inspection.py, docs/ui/workflow.md and this handoff.

## Change

Both inspector connection paths enter read-only mode before any query. Each selector path
is covered by a real PostgreSQL write-rejection test; only URL loading and the first-query
fault are injected. The connection and database enforcement are real. The successful
owner-write control rules out missing privileges as the reason the guarded INSERT fails.
The outward result stays the existing safe query_failed code.

The fresh-model browser test now asserts zero approvals and zero simulated actions
immediately before Approve, retaining its final exactly-one and replay assertions.

## Evidence before commit

Tests were written first locally. On base 5d4266e plus the new tests, all five selector cases
failed for the actual allowed INSERT (no 25006). With the two read_only assignments, all
five passed in 21.61s; targeted Ruff passed. Baseline and corrected JUnit files are under
E:/PHANI/Interview/tmp/h01-{baseline,fixed}-20261027.xml. No production source, contracts,
fixtures, dependency pins, browser runner or frozen model/evaluation assets changed.

## Final checks and limits

Final integrated main gets its own five-case database check, Ruff, TypeScript check and
the complete 19-case real browser suite, including secret scanning and verified cleanup.
The five read-only cases also run on native Ubuntu. Exact final results are recorded after
commit without editing this note to name its own SHA. This maintenance increment does not
rerun the unchanged full application backend, training or frozen-model evaluation; the
last full cross-platform backend evidence remains c8b9477 (449 passes plus one allowed
live-Claude skip). Do not present the new total collected count as executed coverage.

The owner connection can still write if future trusted code deliberately clears read_only;
this protects against accidental SQL changes, not arbitrary malicious code. GitHub Actions,
macOS, Linux browser and public hosting remain unverified. No provider/model call or paid
fallback. All new project commits use PHANI465 <pgavara1@asu.edu> alone, without trailers.

## Next

Codex integrates the scoped fix, records actual final checks and dispatches G3A's runtime
multi-agent contract and evaluation design to Claude in a separate worktree. Preserve all
accepted task branches and Cursor's seven original edits. No remote, push or deployment.
