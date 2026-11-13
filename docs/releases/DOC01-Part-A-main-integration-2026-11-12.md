# DOC01 Part A: local worker integration

**Reviewed candidate:** `8f7bd87226418acaed6c4436d3122d4a60d9ff94`.
**Source merge:** `662572e250807d6bbb26e4cb0d37d572e51aed7f`, first
parent main `28330b2`, second parent the reviewed candidate. The automatic
merge had no conflicts. The worker subtree is byte-identical to the candidate;
the application `src/`, `web/` and `contracts/` trees match the first parent.
The merge has PHANI465 <pgavara1@asu.edu> as sole author and committer, with
no trailers. The later publication commit changes only documentation.

## Delivered

A separately locked `tools/document_worker/` local extractor for
public/synthetic text-layer PDF, UTF-8 CSV and XLSX. Owned session handles,
bounded child processes, source/protocol hashes, exact typed money/date
parsing, page/sheet/row locators and deterministic coverage, missingness,
duplicate and per-currency reconciliation measures are included. MarkItDown
serves narrative conversion only; typed parsers supply numbers. Recovery
retains uncertain process groups and validates child responses before
returning success. There is no application upload route, browser UI, OCR,
live-model call or automatic transaction/action ingestion.

## Exact merge checks

Windows and native Ubuntu jobs run sequentially. App tests use the existing
2700-second command cap, deterministic investigator and live Claude off.

| Check | Windows | Native Ubuntu |
| --- | --- | --- |
| Six-command app strict gate on merge | 6/6, 810 passed + 1 allowed skip | 6/6, 810 passed + 1 allowed skip |
| Same-run JUnit and allowed-skip validation | 811 cases, 0 failures/errors, 1 allowed skip; validator exit 0 | Same |
| HTTP export, frozen snapshots | v1.2 verified; v1/v1.1 frozen; exit 0 | Same |
| Read-only ML reproduction | `reproduced: true`, exit 0 | Same |
| Root Ruff and package check | Both passed in strict gate; wheel/sdist include 5 migrations and 8 model/data assets | Same |
| Clean integration tree | Before and after all checks | Before and after all checks |

The Windows pytest step took 1985 seconds, within the unchanged 2700-second
command cap. Its JUnit reports 1984.880 seconds. The native JUnit reports
538.347 seconds. Each full gate completed before the next platform started.
The DOC01 worker suite is independent of the app gate and appears below.

Independent checks on the exact candidate before merging: Windows worker
suite 173 passed/22 expected POSIX skips; native worker suite 195 passed/0
skips. Both 21-run smokes plus two cap probes reported 259/259 field values,
101/101 behaviour checks and no handles, run dirs or recovery records left.
The native fork-after-`/proc`-listing probe returned
`group_members_alive_kept` with its record intact; the unreadable-member probe
returned `group_state_unknown_kept`; the invalid-child probe returned an
error. The independent Windows focused run had one failure in the previously
intermittent crashed-supervisor test; the subsequent independent full worker
run passed. See the [review](../reviews/DOC01-8f7bd87.md) for the retained
reliability note.

The worker's CSV fixtures deliberately preserve CRLF bytes and hashes through
`tools/document_worker/.gitattributes` (`-text`). `git diff --check` flags
their carriage returns as trailing whitespace; source and documentation
lines have no whitespace errors. The fixture hashes and labelled smoke
values match on both platforms.

## Limits and next stage

Part A's child guard is not OS-level filesystem or network isolation.
Windows jobs have no OS file-write boundary; POSIX uses process groups and
resource limits. PDF tables are not typed, OCR is absent, token savings are
unmeasured, and only synthetic/public files were used. The Windows
recovery-record sharing conflict is a required follow-up before HTTP
exposure. The next [DOC01 Part B assignment](../prompts/CLAUDE_DOC01_PART_B_BACKEND.md)
adds an opt-in local upload/feedback backend under a new contract; its UI is
later. AN01-M1 remains accepted for prototype scope but unmerged, and its
full-size limits are still not demonstrated.
