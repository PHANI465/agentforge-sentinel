# November7 local release: evaluator preparation, benchmark and recorded replay

**Tested integration:** `871e31d40e93306cfde6617e814c2cb78ae67c9e`, branch `task/codex-batch-r2-integration`.
It merges exact main6303236 (first parent) with corrected preview10a65ee (second parent).
The merge is automatic with no conflicts. Application/tooling/test/demo bytes are
identical to the reviewed preview; existing coordination/review documents are retained.
The later publication commit adds documentation only and has no separate exact-head
full-suite claim. [Independent re-review](../reviews/Batch-r2-10a65ee.md) closes R46–R49.

## What is delivered

- P4a's versioned artifacts, owned deterministic pilot supervision, restricted-role
  extraction, partially blinded review packets and offline scoring. Wrong outcomes stay
  counted; blank/unknown values stay unknown. Live evaluation remains disabled/unassigned.
- PERF01's bounded deterministic local benchmark and its one-laptop report. Its observed
  capacity refusals are counted, not retried or reclassified as success. These numbers
  do not establish bank/hosting capacity or validate AN01's proposed report-query caps.
- DEMO01's portable key-free recorded replay of a synthetic case, with provenance and
  content freshness checks, inert notes, scripted approval and an idempotent simulated
  action. It is not a live service, provider-quality demonstration or deployment.
- AN01's revised documentation is included as a **draft** only. No reports route, new
  capability, migration, export or reporting UI is implemented or accepted by this release.

## Exact integrated-commit checks

Windows completes before native Ubuntu starts. Live Claude is off; investigators are
deterministic; databases are disposable and task-owned. Locked dev/ml and the existing
2700-second per-command cap are used; no individual deadline/assertion/skip is changed.

| Check | Windows | Native Ubuntu, unprivileged sentinel |
| --- | --- | --- |
| Six-command strict gate | Passed, 1664.234 s | Passed, 464.091 s |
| Backend | 810 passed + one allowed skip | 810 passed + one allowed skip |
| Same-run JUnit | 811 cases, zero failures/errors; exact skip validation exit0 | Same |
| Handoff helpers / schemas / Node / package | Passed inside the same strict run | Same |
| HTTP export | Passed; v1/v1.1 frozen, v1.2 current | Same |
| Read-only ML reproduction | reproduced:true | reproduced:true |
| Clean before and after | Yes, exact871e31d | Yes, exact871e31d |

Windows interval: `2026-11-07T16:53:18.767812+00:00` to `2026-11-07T17:21:55.824896+00:00`.
Native interval: `2026-11-07T17:22:13.315054+00:00` to `2026-11-07T17:30:17.791949+00:00`.
The shared heavy slot is held one job at a time. No repeat-until-green evidence is used.

Before the integrated gates, independent candidate checks pass167 focused tests plus11
additional probes, replay Chromium31/31, AN01 arithmetic34/34, and actual local shallow
clone freshness/mutation controls. Product frontend/browser suites are not rerun because
web and production src are unchanged; older product UI results remain dated prior evidence.

Private evidence: canonical `.agent/batch-r2-integration/871e31d/windows/` and `native/`;
candidate review `.agent/review/` in `E:/PHANI/sentinel-wt/codex-batch-r2-review`;
native clone/reports `~/codex-batch-r2-integration-native` and
`~/codex-batch-r2-integration-reports`. The earlier author's failures/reports and original
Codex probes are preserved. No test-owned Postgres remains on native; final local cleanup
and original Cursor seven-file/diff-hash checks are recorded privately.

## Remaining work and limits

1. P4b live development comparisons need separate written authorization, an explicit
   schedule/allowance and model/quota annotations. They have not run. Workflow elapsed's
   150-second quality gate remains not measured/demonstrated by the pilot tooling.
2. AN01's six contract decisions remain: zone rules, capability/version compatibility,
   cursor integrity, measured query limits, index strategy and UI staleness wording.
   A database cancellation budget must not be promised as a hard request deadline.
3. Real GitHub Actions/remote publication, Linux browser tests, macOS, hosting and BYOK
   remain unverified/unassigned. No external remote, push, deployment or new spending.
4. Demo freshness has its documented generator/src scope; old review keys need packet
   regeneration. Synthetic data, small local samples and simulated actions are not
   real-world fraud detection, calibrated probability or provider-quality evidence.
