# HTTP v1.3: local document upload and extraction feedback (DOC01 Part B)

This version is additive to v1.2, and the reason is recorded in
[decision 0010](../decisions/0010-document-upload-contract-v13.md). The DTOs are in
`src/sentinel/contracts/http_v13.py`, and the examples are in `contracts/http/examples-v1.3/`.
It is meant for local synthetic or public files only; no hosting is claimed. The feedback is
a review aid, **not** a fraud verdict, an authenticity check or a calibrated score.

## Authority

Every route needs a bearer session that holds the **opt-in** capability `analyze_document`.
It is never part of the four default grants. Requests are answered as follows:

| Situation | Response |
| --- | --- |
| Missing or invalid token | `401 unauthenticated` |
| Session without `analyze_document` | `403 permission_denied` |
| Handle that is missing, expired, malformed, deleted or another session's | `404 not_found` (all identical) |

A handle is an opaque lease that only its session can use, for one hour. It is never a path.

## Routes

| Method and path | Body | Success |
| --- | --- | --- |
| `POST /v1/documents?format=csv\|xlsx\|pdf` | the file's raw bytes | `201 DocumentUpload` |
| `POST /v1/documents/{handle_id}/analysis` | JSON `AnalysisRequest` | `200 DocumentAnalysis` |
| `GET /v1/documents/{handle_id}/records?offset=0&limit=100` | none | `200 RecordPage` |
| `DELETE /v1/documents/{handle_id}` | none | `200 DocumentDeleted` |

**Upload.** The `Content-Type` must be `application/octet-stream` or the format's own media
type:

| Format | Media type |
| --- | --- |
| csv | `text/csv` |
| xlsx | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` |
| pdf | `application/pdf` |

The upload is checked in this order:

1. A declared body over 10 MiB is refused unread, and a streamed one stops at 10 MiB
   (`413 body_too_large`).
2. An empty body is `422 invalid_request`.
3. The worker then checks the content:
   - `format_mismatch`: the declared format is not what the bytes are;
   - `unsupported_container`: a legacy or encrypted OLE file declared as xlsx.

   Both return `415`.

No filename is read.

**Analysis** runs the accepted Part A parser in its bounded child. A document that cannot be
read is still `200`, with `status` `unsupported` or `error` and the reason codes in
`errors`. A worker that cannot run returns `5xx`, as listed below.

The response includes:

- `source`: sha256 and size;
- `parser`: worker protocol, version, source digest, libraries and the options used;
- `units`: file, sheets or pages, each with its status and reason;
- the first `records_limit` records (at most 500) and `records_total`;
- `unparsed` (at most 100) and `unparsed_total`;
- `findings`, each with at most 50 evidence ids and its `evidence_count`;
- `table_typing` (CSV/XLSX) or `pdf_structure` (PDF);
- `measures`: missingness, duplicates, per-currency reconciliation and running balance;
- `coverage`, `errors` and `worker_run`;
- the fixed `interpretation` text.

Page text and narrative text are never returned. A further analysis of the same handle
replaces the stored result.

**Records** pages come from the stored analysis; the parser is not run again. A page stops at
`limit` records or 2 MiB of records, whichever comes first, so follow `next_offset` rather
than computing it. A handle that has not been analysed gives `404 analysis_not_found`, which
only its own session can see.

## Value semantics

- **Money** is a signed integer string of minor units with its `exponent`. Currencies are
  never merged or converted. Reconciliation is per currency:
  `opening + credits - debits - closing`.
- **Unknown values:** `status` other than `known` means the value is unknown. Its
  `minor_units` and `value` are then `null`, never zero. An undeclared decimal or day/month
  convention leaves ambiguous values unknown.
- **Ratios** are `{numerator, denominator}` pairs, and `0/0` means n/a. Counts always show
  their population.
- **Evidence ids** are `<sha256[:12]>:<locator>`, and the `locator` gives the
  page, sheet, row or column.
- **Document-derived strings are inert display text.** This covers raw cells, headers, sheet
  names, excerpts and hostile instructions. They cannot invoke a tool, request an
  investigation, approve or execute anything.

## Worker failures

| Status | Code | Meaning |
| --- | --- | --- |
| 503 | `document_worker_unavailable` | No registered worker or store is configured, or it is invalid. |
| 503 | `document_worker_busy` | Another analysis is running in this API process. |
| 503 | `document_worker_recovery_pending` | An earlier run's stop was not confirmed; recovery has not yet cleared it. |
| 504 | `document_worker_timeout` | The bridge exceeded its wall-clock bound; the API stopped it and recovery is pending. |
| 503 | `document_worker_identity_changed` | The worker answering is not the registered one (see "Worker identity"). |
| 502 | `document_worker_failed` | The bridge crashed or returned an answer outside the contract, including counts or page metadata that are missing or contradict the returned records. |

Error bodies are `{"error": code}` only. No token, path or document text is echoed.

## Worker identity and uncertain stops (review 612934b)

**Worker identity.** The API registers the worker's protocol and source digest from its first
`status` answer. With `SENTINEL_DOC_WORKER_SHA256` set, that answer must equal the pin, or
the routes stay `503 document_worker_unavailable`. After registration:

- Every bridge request names the registered digest. A worker whose own digest differs
  refuses before doing anything.
- Every answer carries the bridge's digest, and the API rejects an answer whose digest
  differs or is absent.
- Every analysis must report the registered digest in its `parser` block.

A mismatch gives `503 document_worker_identity_changed`, and no report is returned. If the
mismatch shows up in an analysis result, parsing may already have run under an
unregistered worker. The API therefore also marks recovery pending, and the next analysis
is refused until a recovery pass keeps nothing. Restarting the API registers again: it
fails closed with a pin, and without one it registers the worker now on disk.

**Uncertain bridge stop.** When a bridge exceeds its bound, the API kills that bridge
process and waits to confirm its exit.

- If the kill fails, or exit cannot be confirmed, the API writes the bridge's pid and its
  creation identity to `<store>/api-bridge/bridge-<pid>.json`. That file holds no token or
  path. The API marks recovery pending and answers `504 document_worker_timeout`.
- Recovery runs on the next analysis, including after an API restart. It stops the process
  only while its identity still matches the record, and confirms the exit.
- A reused pid, which now names another process, is never signalled; the record is
  cleared. An unreadable record, or a live process without a recorded identity, keeps
  analysis refused (`503 document_worker_recovery_pending`).
