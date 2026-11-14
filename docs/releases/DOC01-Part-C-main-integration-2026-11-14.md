# DOC01 Part C local Document Review release

On November 14, 2026, local main fast-forwarded to the verified source commit
`3dfbc0054fa34d457f292a3ec916ee0d452b59a2`. It includes Claude's
`ffdad9d4d75cd187914784532405d1ce02737399` and the Codex correction for DELETE
404 messaging. The regression failed on Claude's tip and passes on the
integration commit. R64–R66 are closed. [Independent re-review](../reviews/DOC01-C-ffdad9d.md)

Document Review is available locally for sessions with the `analyze_document`
grant. It accepts synthetic or public CSV, XLSX and PDF files up to 10 MiB.
The workbench displays extraction coverage, reconciliation where applicable,
and paged records with their evidence. An unavailable handle clears the
local display. The workbench reports deletion only after a matching success
response confirms it. [UI workflow](../ui/DOC01-document-review.md)

## Verification on 3dfbc00

| Check | Windows | Native Ubuntu in WSL |
| --- | --- | --- |
| Strict gate | 6/6 | 6/6 |
| Full backend suite | 941 passed, 1 allowed skip | 945 passed, 1 allowed skip |
| Same-run JUnit validation | 942 cases, exit 0 | 946 cases, exit 0 |
| HTTP contract export and ML reproduction | Passed | Passed |
| Frontend typecheck, unit/component tests and build | Passed, 266 tests | Windows coverage |
| Browser suites | Workbench 19/19, trace 10/10, documents 12/12 | Windows coverage |

The document browser suite used the production API, real worker and disposable
PostgreSQL. It verified cleanup and credential scan coverage with a synthetic
canary. The stack directory was empty after teardown. The sole backend skip
was the opt-in live-Claude smoke. The v1.3 contract and its 29 examples
reproduced alongside the earlier frozen contracts.

Windows evidence is in the ignored `.agent/last-check.json` and
`.agent/doc01c-integration/` of the integration checkout, and the JUnit file
at `E:/PHANI/sentinel-tmp/doc01c-3dfbc00-windows.xml`. Native reports are in
`/home/sentinel/codex-doc01c-reports/`. The publication commit after
`3dfbc00` updates documentation.

## Scope and limitations

The UI displays extraction feedback for local review. OCR, PDF table typing,
Windows-to-Linux browser parity and hosted private-document processing remain
outside the verified release scope. The v1.3 API provides no analysis revision
for detecting a replacement with the same status and record count. Signing
out suppresses a late result in the browser while the worker finishes its run.
