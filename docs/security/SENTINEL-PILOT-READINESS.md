# November 16 Sentinel hardening and pilot readiness

The owner chose an invited pilot with synthetic files and official public
reports, and publication to the private GitHub repository with Vercel
verification. See the [pilot runbook](../runbooks/invited-document-pilot.md).

## Hardening included

- Runtime export uses OpenTelemetry API 1.45.2. The Python locks also contain
  patched certifi 2026.10.23 and pytest 9.2.0. The worker lock includes Soup Sieve
  4.0 and now requires Python 3.11.5 through 3.12 to avoid downgrading its parsers.
  MarkItDown stays at 0.1.8. Vite 6.4.6 and Vitest 5.1.0 pass the web tests on
  Node 22.13.1. The fresh OSV query found zero matches among the 270 scanned
  package/version pairs, including the vendored PDF.js and fflate, and npm audit
  returned zero findings. These results are dated and package scoped.
- App and static hosting add anti-framing headers, nosniff and a referrer
  policy. The hosted API, guest and IAF paths explicitly prohibit caching.
- The PostgreSQL quota reserves requests across instances with IP, session and
  route group limits. Existing global guest and model limits still apply.
  Expired counters are removed on subsequent traffic. The restricted role can
  reserve a request but cannot read or modify the table directly.
- The release package builds the workbench from a clean Git snapshot, copies
  tracked release files, scans the artifact and records 326 file digests
  beside the staged upload. The runbook describes additive migration, staging
  and rollback by deployment ID. See [Vercel release procedures](../../hosting/vercel/README.md).

## Official document evaluation

The reference values were transcribed from the publishers' PDF tables, separate
from Sentinel's extracted text. Browser automation loaded each actual PDF using
the local file picker, checked the document and source label, and verified
that review issued only same-origin asset GETs and used no browser storage.
The two original monthly samples were regression cases. The August report
and daily report were additional cases. Amounts below are USD millions.

| Report | Reference | Outcome |
| --- | --- | --- |
| [January 2025 monthly](https://fiscaldata.treasury.gov/static-data/published-reports/mts/MonthlyTreasuryStatement_202501.pdf) | Page 5, Table 2. Receipts 513,294, outlays 641,935, deficit 128,640 | 3/3 fields matched |
| [May 2025 monthly](https://fiscal.treasury.gov/system/files/files/reports-statements/mts/mts0525.pdf) | Page 5, Table 2. Receipts 371,229, outlays 687,233, deficit 316,004 | 3/3 fields matched |
| [August 2025 monthly](https://fiscal.treasury.gov/system/files/files/reports-statements/mts/mts0825.pdf) | Page 5, Table 2. Receipts 344,315, outlays 689,107, deficit 344,792 | 3/3 fields matched |
| [January 15, 2025 daily](https://fiscaldata.treasury.gov/static-data/published-reports/dts/DailyTreasuryStatement_20250115.pdf) | Daily cash statement, different schema | Readable text, no monthly summary asserted |

The downloaded August and daily source files live outside the committed sample
library. Their SHA-256 digests are respectively
`e12a91c5f61eb7804eb8f6b85cd31750edfc11b0d7e3647d77d9c13ac7c9b6e5` and
`21b87ad8601b7ae5e85309e7a1a5b0c7cf225add9e92038a956eb91a2c40bf69`.
Use `node public_site/tests/insights-browser.mjs <web/node_modules> <output> <corpus>`
with those two files named `treasury-aug-2025.pdf` and
`treasury-daily-2025-01-15.pdf`.

This small evaluation tests extraction and abstention in one family's layouts.
Future evaluation should include unrelated publishers, currencies, periods and
layouts, a reviewer who did not implement the parser and independently labeled
normal and discrepant examples. Keep reasoned missing and wrong counts and
separate extraction performance from fraud classification.

## Capacity and boundaries for this pilot

- Begin with three to five invited participants on the distributed static
  site or in scheduled sessions. Parsing in their browser avoids adding a
  server upload queue, private object storage or per-file provider costs.
- Use the facilitator checklist and recording form. Separate contact
  information, anonymous observations and project issues. Pick a named
  facilitator and have them confirm deletion at the retention deadline.
- The stored rate limiter is tested under concurrent reservations. That
  verifies counter behavior, while a latency or capacity claim needs a
  measured end-to-end workload. Per-instance investigation capacity and
  PostgreSQL connection pressure remain important. See the existing
  [PERF01 local measurement](../benchmarks/PERF01-local-capacity.md).
- Before increasing hosted traffic, benchmark the shipped guard and workbench
  against a disposable environment, with a capped request count and a
  representative mix. Record p95 latency, per-route 429/503, database lock
  waits, connections and expiry cleanup. Repeat at two deployment instances,
  then choose limits from measured results. The current published thresholds
  are operational caps, not capacity measurements.
- Before handling private customer documents, implement named access and
  verified revocation, stronger tenant isolation, abuse controls, deletion
  evidence, backup restore and a sandboxed parser if server uploads are needed.
  No increase to demo caps, server document exposure or live investigation
  capacity is part of the invited-pilot scope.
