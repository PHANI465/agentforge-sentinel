# Corrected batch re-review: R46–R49 closed

Accepted for the scoped local/deterministic tooling and recorded-demo behavior:

| Delivery | Exact reference | Decision |
| --- | --- | --- |
| P4a | b32f45c495ae9f352c59b1e2173b23dc37fe9914 (fix 4b9118d) | Accepted evaluator preparation; no live run authorized |
| DEMO01 | 1289b42df8f0b9b7fc0b208959fb8b3474c7804d | Accepted recorded synthetic replay and scoped freshness |
| PERF01 | 59b0b5496ae718140badd7710691aed23066c873 | Accepted bounded local deterministic measurement tool/report |
| Combined preview | 10a65ee16b77f14a0cd619d4a6ffdc9e4e9c994e | Re-reviewed; no blocking findings for these scopes |
| AN01-r2 | a8c164a3737006ede1bc81b91764654cb718bb53 | Documentation retained as an explicitly unaccepted contract draft |

## R46: coherent accounting, with first bad outcomes kept

The original wrong-hold relabelling/count mutation and complete-run suffix censorship
are now refused. The unchanged control still reports its D03 wrong hold and acceptable
2/3. Complete/incomplete boundaries and known outcome/code/disposition relationships
are checked. Legitimate pending results and unavailable telemetry remain distinct;
unknown recommendations are shown separately, not turned into unacceptable answers.
Editable unsigned reports are not described as tamper-proof.

## R47: bound review material and honest partial answers

Sheet items, kinds and text digests are bound to the generated packets. Duplicate,
missing, substituted and invalid-choice rows are refused. Independent bound-sheet probes
confirm blank acceptable/correction answers have zero answered denominator, an explicit
correction-only yes is counted, and partial review is labelled partial. Supported plus
not-checkable is 1/2 under the frozen common rubric. Older keys without bindings must be
regenerated; this is not independent human-quality evidence.

## R48: history-independent freshness, including a real shallow clone

Canonical digests of the actual generator and src files replace the history-dependent
skip. The recorded capture commit remains provenance. I made a real local shallow clone
at exact10a65ee: the capture ancestor af4890a is absent, yet validation passes. Changing
one source file makes validation fail; restoring it returns the clone to clean state.
This adds actual shallow-checkout evidence to the author's simulated missing-history
tests. No external Git remote or GitHub Actions runner was used.

Freshness covers generator/src content with CRLF→LF normalization. It does not cover
contracts, dependency locks, ML/data assets or local_stack.py, and is not a signature or
dependency/runtime identity guarantee. The capture remains deterministic rule scoring,
scripted human approval and a simulated action.

## R49: recommendations checked against storage before export/packets

The unchanged original independent real-database export probe now passes: changing the
stored D11 recommendation from escalate to hold in the JSON is refused before a packet
is produced. Exports derive the adopted result from stored basis records and compare
known fields, preserving pending/unknown outcome labels. The maintained revision,
abstention, foreign-mapping, owner-refusal and unavailable-telemetry controls also pass.

## Independent verification

- Separate detached checkout at exact10a65ee with its own offline locked dev/ml environment.
- **167 focused tests pass** (245.35 s), including deterministic owned pilot/export/score,
  runtime authority/failure regressions and real benchmark/demo stack tests.
- **11 independent probes pass** (17.34 s): ten accounting/bound-sheet cases and the
  original real-Postgres export refusal probe unchanged.
- Standalone replay Chromium QA **31/31**; its loopback server closes normally. This
  checks the recorded replay, not the product UI. The AN01 checker passes34/34.
- Source/contract/UI/lock/CI/individual timeout boundaries are preserved. All introduced
  commits/merges use the owner identity and no attribution trailers.
- Exact integration871e31d then passes independent sequential Windows/native full gates,
  810 tests plus the one allowed skip each, all six commands, same-run811-case JUnit,
  frozen HTTP/package/ML checks. [Release evidence](../releases/Batch-r2-main-integration-2026-11-07.md).

The author's reports remain author evidence; the above independent checkout/probes and
integration runs are separate. Original failed runs and original probe files are kept.
No live provider, auth/account call, final cases, paid fallback, external push or deployment.
No Linux browser, macOS or actual CI runner result is claimed.
