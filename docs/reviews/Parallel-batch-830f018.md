# Parallel delivery review: 830f018

Historical review: R46–R49 are now closed on the corrected batch under
[the November7 re-review](Batch-r2-10a65ee.md). The findings and evidence below describe
the preserved original candidate; they are not current blockers.

Reviewed preview: `830f01864aec3ff94679cf068b598157c7ee4263`, independently checked out
at `E:/PHANI/sentinel-wt/codex-parallel-batch-review` with its own locked dev/ml environment.
P4a is absent from this preview and is reviewed separately at 96293da.

## Decisions

| Component | Decision | Scope |
| --- | --- | --- |
| PERF01 59b0b54 | No blocking findings for the reviewed local deterministic tool | Eligible for later integration; not a production capacity claim |
| DEMO01 47b7cf1 | Changes requested: R48 | Recorded replay otherwise passes independent tests and Chromium QA |
| AN01-r2 a8c164a | Seven intake clarifications reviewed; contract remains a draft | No reporting API/UI, capability or migration is authorized |
| Combined preview 830f018 | Not accepted for main integration yet | R48 must close; P4a has separate R46/R47/R49 blockers |

## R48 — Medium: capture-history absence adds a forbidden skip

Location: `tests/test_recorded_demo.py:62`,
`test_generator_unchanged_since_the_capture_commit`.

The test skips when Git or the recorded capture commit is unavailable. This introduces
an extra skip into a gate whose only allowed skip is the opt-in live-Claude test.
The current backend checkout step does not request historical depth, so absence of the
capture ancestor is a relevant clean/shallow-checkout condition; no GitHub run is claimed.

Independent probe: the unmodified test passes with full local history. Faulting only
`git cat-file -e` to return missing-object invokes that skip. A minimal report passed to
the real structured validator is rejected with `unexpected skip`, exactly as expected.
This is a controlled missing-history probe, not a real GitHub Actions execution.

Make freshness verifiable without requiring history: for example, record canonical
generator/application content digests at capture and validate them in a shallow or
source checkout. Missing/malformed provenance must fail with a useful error; a changed
generator/application must still be detected. Do not skip or weaken the staleness
assertion, widen the skip allowlist or change the workflow just to fetch more history.
If provenance format changes, recapture once in the heavy execution slot and retain the
old capture and failing evidence. Keep the privacy-path regression fix.

## AN01 decisions still needed before implementation

The revision clearly separates per-request snapshots, current workload state and event
time; fixes request/row counts; bounds output, matching input and database work separately;
keeps currencies separate; and defers labels/CSV. Its checker independently passes all
34 checks with zero failures.

The six questions remain unresolved: zone-data pinning, capability/version compatibility,
cursor integrity, measured query limits, index strategy and UI staleness wording. In
particular, PERF01 measures the existing application, not the proposed report SQL: its
numbers cannot validate AN01's 200,000-row/5-second proposals. Before contract freeze,
also distinguish a PostgreSQL statement/cancel budget from a guaranteed client/request
deadline, consistent with the accepted clock/late-operation lessons. No new runtime
work is assigned by this design review.

## Independent evidence

- **56 focused tests pass**, 45.69 s, including the real local benchmark stack and real
  deterministic replay capture through production HTTP handlers and disposable Postgres.
- Recorded replay Chromium QA: **30/30 pass**, loopback-only server closed by its handle.
  Includes hashes, frame ledger, inert hostile text, navigation, desktop/narrow layouts
  and no requests outside the allowlist. This is the standalone replay, not product UI.
- AN01 arithmetic checker: 34 checks, zero failures. Its SQL/API/browser acceptance
  scenarios remain proposed, not executed.
- Preview scope matches the delivery: 21 files, only demo/docs/two scripts/two tests.
  Application source, frozen contracts, product UI, lockfiles, existing lifecycle and CI
  are unchanged. All introduced commit authors/committers match the owner identity.
- Private JUnit and QA: `.agent/review/` in the independent checkout. The missing-history
  probe is archived in canonical `.agent/batch-review-2026-11-06/`.

Claude's final-preview Windows/native strict results (722 + one allowed skip each,
723-case reports, HTTP and ML) are author certification, not my independent full-suite
results. The local Windows check record names exact 830f018 and a clean tree. I did not
repeat two full gates while blocking corrections remain. Earlier 82316a5 native failures
remain preserved. No live provider, final cases, external push, CI, hosting or spending.

Continue with [the two-worker correction batch](../prompts/CLAUDE_BATCH_REVIEW_CORRECTIONS_2026-11-06.md).
