# DOC01 Part C: Document review in the analyst workbench

The Document Review UI is integrated on local main at verified source commit
`3dfbc00`. [Release verification](../releases/DOC01-Part-C-main-integration-2026-11-14.md)

The contract it uses is HTTP v1.3, unchanged:
[documents-v1.3.md](../api/documents-v1.3.md) and
[decision 0010](../decisions/0010-document-upload-contract-v13.md).
`contracts/http/openapi.v1.3.json` has SHA-256
`d4306c651f8a555fca6e309a27c7bd5b2c133f07d4cfc2f07f1fcde772eae4dc`. The 29 frozen examples are
copied byte-for-byte to `web/src/fixtures/http-v1.3/`, with per-file hashes in `PROVENANCE.md`.

## Where and for whom

The workbench shows a separate **Document review** section only when the session holds the
opt-in `analyze_document` capability. The four default grants never show it, and the
session line then adds "review local documents".

The section has no path into transactions, cases, investigations, approvals or actions. The
case pane, its human approval and its idempotency key are unchanged.

## Flow

1. **Choose a local file.** The 10 MiB limit is stated before selection. An empty or
   oversized file is refused in the browser and never sent. The server's 413 still governs.
2. **Choose the format** (CSV, XLSX or PDF). It is preselected from the extension when that
   is one of the three.
   - The upload sends the file's raw bytes with the format's v1.3 media type: no multipart
     body and no filename.
   - The file name and local path are never shown.
   - After a successful upload the browser drops its reference to the file.
3. **Run the analysis** explicitly. The interpretation assumptions (decimal style, date
   order, optional default currency) are visible, and undeclared conventions stay unknown.
   - A second analysis first explains that it replaces the stored result and asks for
     confirmation.
4. **Read the result:**
   - the actual status and its reason codes;
   - coverage with its counts;
   - missingness, where each ratio is shown as n of d and 0/0 as "not applicable";
   - reconciliation per currency, in plain language;
   - running-balance and duplicate summaries;
   - data-quality observations;
   - table typing, or PDF structure ("PDF tables are not typed and there is no OCR");
   - units, rows not parsed, and paged records;
   - source and parser provenance in an expandable section.
5. **Page records** with `GET .../records`, using the returned `next_offset`. The total and
   the current range are always shown. Previous pages are revisited from a stack of offsets
   that were actually returned.
6. **Delete** uses the accepted DELETE route. A matching confirmation clears local
   content and reports deletion. A 404 also clears local content and reports that
   the handle is unavailable.

## States and what they mean

| Situation | Shown as |
| --- | --- |
| `complete` | "Extraction complete": every unit read, nothing unparsed. Not a finding. |
| `partial` | "Partly extracted", with the counts of what was not read. |
| `unsupported` / `error` (HTTP 200) | "Not supported" or "Could not be read": nothing was extracted, the reason codes are listed, and no measures or records are shown. |
| 4xx refusal | The server's code, as a short message; focus moves to the message. |
| 404 on analysis, records or delete | Missing, deleted, expired and foreign look the same. Stale content is cleared. |
| Worker 5xx (busy, recovery pending, timeout, failed, identity changed, unavailable) | Not a document result. Any result shown is cleared, because the stored result may have changed, and a retry is offered. |
| Malformed or empty JSON, non-JSON 5xx, wrong shape | "The server did not confirm a result." Nothing is shown. |
| Network failure | "Sentinel could not be reached." |

## Strict, safe rendering

- **Strict parsing** (`web/src/api/documents.ts`): a required field that is missing or of
  the wrong type makes the response *unconfirmed*, never an empty report. So does a count
  that contradicts what was returned. The client re-checks the server's own relations:
  - the page rule and `next_offset`;
  - records and unparsed totals against what was returned;
  - coverage counts;
  - missingness sums and exact ratios;
  - the reconciliation difference, recomputed with `BigInt`;
  - known value ⇔ value present.
- **Money** stays an integer minor-unit string and is formatted by its exponent with string
  arithmetic. An unknown amount, date or currency is shown as unknown with its status; a
  real zero stays zero.
- **Currencies** are never combined or converted.
- **Inert text.** Every document-derived string (cells, headers, sheet names, excerpts,
  reason details) is rendered as text. Nothing becomes a link or markup.
  - An evidence id is a button only when the referenced record is on the current page; the
    button moves focus to that row. Any other id is plain text.
- **Wording.** It is extraction and consistency checking only: not fraud detection,
  authenticity, a calibrated score or an approval.

## Every success must describe the current document (R64)

Each v1.3 response can be valid on its own and still describe another document. The UI
therefore checks each success against what it already holds (`web/src/api/documents.ts`:
`uploadMatches`, `analysisMatches`, `pageMatches`, `deletionConfirmed`):

| Response | Must agree with | On disagreement |
| --- | --- | --- |
| Upload receipt | the chosen file's size and the format it was sent as | The handle is not adopted and nothing from the receipt is shown. The file stays selected so it can be uploaded again. |
| Analysis | the current handle, the receipt's SHA-256, size and format, and every submitted option (decimal style, date order, default currency, records per page) | No result is shown as current, including an earlier one, because the stored result may have changed. The state is *unconfirmed*, and a retry is offered. |
| Records page | the current handle, the analysis shown (source digest, status and records total), the requested offset and limit, and the page rule (`next_offset` follows the returned records exactly) | The page is refused and the analysis above it is cleared, because another tab may have replaced it. The upload stays; running the analysis again shows the current result. |
| DELETE | the current handle and `deleted: true` | The UI does not say "Deleted". It keeps the document and asks for another try. |

**Limit:** this is a consistency check, not a pinned snapshot. v1.3 has no analysis revision
or version field. If another tab replaces the stored analysis with one that has the same
status and the same records total, a later page cannot reveal it, and the page is shown under
the earlier analysis.

## Ownership of late responses

Every request takes a new generation number and its own `AbortController`. A response
applies only if its generation is still current and the handle is unchanged.

- **Changing session:** sign-out unmounts the workbench, and the section is keyed by
  `session_id`, so the content is cleared at once.
- **Abandoning a request:** choosing a new file, deleting or unmounting abandons whatever
  is in flight.
- **Busy controls:** they are disabled while a request is running.

The token and the handle stay in memory only. They never go into a URL, browser storage, a
log, a screenshot or diagnostics, and the handle is never displayed.

## Verification

- **Unit and component tests:**
  - `web/src/api/documents.test.ts`: fixture hashes, strict parsing of every example, 19
    tampered variants, money and ratio formatting, and client mapping of every HTTP code,
    non-JSON and network failures.
  - `web/src/ui/DocumentReview.test.tsx`: visibility; upload refusals; every result state;
    unknown versus zero; 0/0; separate currencies; hostile text; evidence linking; paging by
    `next_offset`, including a page cut early; 404 clearing; worker failures with retry;
    re-analysis confirmation; delete; reversed responses across upload, session and handle
    changes.
- **Real browser suite** (`npm run test:e2e:documents`, `web/e2e/documents.pw.ts`).
  - **Setup:** the accepted browser stack with the production app, a registered real DOC01
    worker, and a fresh marker-owned store created by `launch.mjs` under `e2e/.runtime/`,
    over a disposable PostgreSQL. No request is intercepted. Opt-in sessions come from
    `tests/support/doc01_browser.py` (operator-issued, ownership-checked manifest).
  - **Covers:**
    - opt-in denial (UI and 403);
    - CSV complete with reconciliation;
    - XLSX partial with unknown values;
    - PDF partial with no OCR;
    - 230-row paging driven by `next_offset` (offsets 100, 200, then 100 again);
    - hostile cells;
    - a server refusal moving focus, with keyboard return;
    - two currencies;
    - delete, after which records return 404;
    - session switch, after which another tenant gets 404;
    - API restart, after which paging continues from the stored analysis;
    - a late analysis after sign-out, suppressed;
    - casework table counts unchanged.
  - **Cleanup** (`web/e2e/support/docArtifacts.ts`):
    - The suite deletes its documents.
    - **Token scan (R65):** while the stack still runs, it searches for the three
      document-session tokens in test results, the whole runtime directory, the stack's own
      directory (API log, manifest, PostgreSQL files) and the stack's secret file. Nothing is
      skipped, because a document token has no expected place on disk. A match is reported
      by relative file name only; a link or unreadable entry is reported as a problem. A
      test-owned synthetic canary file under the stack directory must be reported by its
      relative name and is removed before shared teardown.
    - **Store removal (R66):** the store is removed only when its whole tree is exactly the
      empty `docworker init` layout: the marker file, empty `handles`, `runs` and `recovery`,
      and optionally an empty `api-bridge`. Any other file, directory, link or unreadable
      entry, at the root or below, is refused by name and left in place. Removal is entry by
      entry without recursion, so anything that appears after the check stops it. A kept
      store is recovery evidence, and a later launch refuses to start over it.
    - The shared teardown still stops the stack, checks the controlled-failure artifact and
      scans for the stack's own secrets.
  - **Canary tests:** `web/e2e/support/docArtifacts.test.ts` runs under Vitest on throwaway
    directories. It covers an unexpected root file, directory and link, contents inside known
    directories, a wrong entry type, an unreadable entry, a normal empty store, and a token
    canary in a stack log, in the secret file and in nested directories.
  - **QA:** screenshots go to `web/test-results/qa-documents/`, which is private and ignored.
- **Unchanged:** the legacy 19-case and trace 10-case browser suites; `suite-harness`
  asserts their starts.

## Limits

- Only local synthetic or public files. No hosting, private customer documents, OCR, PDF
  table typing or LLM narrative.
- A worker-side analysis that the browser abandons (sign-out mid-run) still completes on the
  server and replaces the stored result. The UI never shows it to the departed session.
- Linux browser execution is not verified here; the browser suites ran on Windows.
- Records pages are bound to the analysis shown only by handle, source digest, status and
  total (see R64 above). v1.3 has no analysis revision.
