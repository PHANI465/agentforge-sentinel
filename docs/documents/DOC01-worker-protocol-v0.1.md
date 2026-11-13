# DOC01 Part A: local document worker protocol v0.1 (frozen for review)

November 12, 2026. Branch `task/claude-doc01-extractor`, started from accepted main `4d60c53`.
This freezes the **local worker** protocol and design for Codex review. It adds no HTTP route,
no frozen-contract edit, no application dependency and no browser upload. Upload, feedback
integration and any LLM narrative are later parts and are **not** claimed here.

Implementation: [tools/document_worker/](../../tools/document_worker/README.md). Proposal it
implements: [DOC01-local-upload-proposal](DOC01-local-upload-proposal.md). Decisions applied:
D20261108-03, -11, -12 in the [ledger](../decisions/PROJECT_DECISION_LEDGER.md).

## 1. Components and trust boundaries

```
 owner (local CLI)            supervisor process                  parser child (contained)
 ----------------  copy-in   ---------------------------------   ---------------------------
 local file path ─────────▶ HandleStore (owned dir, marker)        python -I, cwd = run dir
                             handle_id + session-token hash        minimal env, no path/URI
 handle + session ────────▶ resolve → re-hash bytes ──stdin──────▶ verify sha256 → import
                             run dir + recovery record             parsers → audit guard →
                             job object / setsid+rlimits           typed extraction + narrative
                 ◀────────── result JSON + supervisor block ◀─stdout─ one JSON document
```

* **Only the CLI copy-in step sees a host path**, and it stands in for a future browser
  upload: it refuses URIs (`scheme://`), UNC paths, directories, links, a file swapped between
  `lstat` and `open`, a wrong extension and anything over the input cap.
* After copy-in, the document is addressed by an **owned handle**: `h_` + 22 URL-safe random
  characters issued by the store. A handle is not a path: callers cannot name a directory, the
  store joins only a regex-validated id under its own `handles/` folder, and resolution needs
  the same session token (only its SHA-256 is stored), an unexpired lease (default 1 h) and an
  unchanged content hash. Missing, foreign, expired and malformed handles all return
  `not_found`.
* The **parser child never receives a path, URI or handle**. The supervisor reads and
  re-verifies the bytes and streams them over stdin.
* Everything extracted (cell text, page text, hidden sheets, invisible PDF text, formulas,
  link targets) is **untrusted data**. Part A has no tools, actions, model calls or ingestion
  into accepted transactions, so there is nothing for document text to invoke.

## 2. Child stdio protocol `sentinel.doc01.worker/0.1`

Request on stdin: one UTF-8 JSON header line (≤ 64 KiB, newline-terminated) followed by exactly
`size` raw bytes, then EOF.

| Header field | Meaning |
| --- | --- |
| `protocol` | `"sentinel.doc01.worker/0.1"`; anything else is `bad_header`. |
| `request_id` | Supervisor nonce `q_<16 hex>`; echoed in the response and checked. |
| `format` | `pdf` \| `csv` \| `xlsx` (declared by the uploader; verified by content sniffing). |
| `size`, `sha256` | Exact byte count and digest; mismatch is `framing_mismatch` / `integrity_mismatch`. |
| `limits` | Full `Limits` object (positive numbers only; unknown keys refused). |
| `options` | `decimal_style` (`unspecified`\|`dot`\|`comma`), `date_order` (`iso_only`\|`dmy`\|`mdy`), `default_currency` (ISO code or null). |
| `narrative` | Boolean; false skips MarkItDown. |

Response on stdout: exactly one UTF-8 JSON document. Exit 0 means a result was written (any
extraction status); exit 2 means a protocol error document (`bad_header`, `bad_options`,
`input_too_large`, `framing_mismatch`, `integrity_mismatch`).

The supervisor treats the response as untrusted and accepts it only under these conditions
(`validate.py`, review R59):

* **Exit 2:** accepted only as an `error` document whose codes are all protocol-error codes.
  Only the envelope (`protocol`, `request_id`, `status`, `errors`) is returned.
* **Any exit other than 0 or 2:** always an error, whatever the document claims.
* **Exit 0:**
  * The document must name this protocol and echo the `request_id`.
  * Error codes must be short lowercase tokens; details must be strings of at most 200
    characters.
  * `unsupported`/`error` documents must carry at least one error and no records.
  * `complete`/`partial` documents must carry every result field in section 3. `format`,
    `source.sha256` and `source.size_bytes` must equal the supervisor's own handle, and the
    guard must be installed.
  * Every record must be well-formed: its evidence id carries the source prefix, its kind is
    known, and a value is `known` exactly when its value or minor units are present (minor
    units being an integer string).
  * PDF results carry no records, and at least one unit is parsed.
  * `complete` additionally requires no errors, no unparsed items, units that are only
    `parsed`/`empty`, and a narrative that is absent or `ok`.

A failure is reported as `invalid_child_output:exit_<code>`, with a fixed reason token as its
detail (for example `nonzero_exit` or `records`). The child's bytes are discarded and never
echoed.

## 3. Result document

| Field | Content |
| --- | --- |
| `status` | `complete`: every unit parsed, nothing unparsed, narrative ok. `partial`: something was read and something was not (unsupported page, unparsed row/part, reader stop, truncated or failed narrative, record cap). `unsupported`: a refused feature (encryption, macros, OLE container, limits, image-only/no extractable content). `error`: malformed input, type mismatch, parser/containment failure, deadline/output cap, `stop_unconfirmed`. |
| `errors[]` | `{code, detail}`; codes are stable identifiers, details never contain document text. |
| `source`, `handle` | SHA-256 and size of the parsed bytes; the owned handle id and declared format. |
| `parser` | Worker version, SHA-256 of the worker's own source files, library versions, the full limits and options used. |
| `units[]` | PDF: one per page `{evidence_id, locator:{page}, status, reason, chars, images, text}`. CSV: `{locator:{file:"csv"}}`. XLSX: one per sheet `{locator:{sheet}}`. Unit status: `parsed` \| `partial` \| `unsupported` \| `failed` \| `empty`. |
| `records[]` | Typed statement rows (CSV/XLSX only), below. |
| `unparsed[]`, `unparsed_total` | Explicit content not turned into records: `{evidence_id, locator, reason, raw_excerpt≤200}`; capped list plus an exact total. |
| `findings[]` | `{finding_id, kind, severity: info\|warning, detail, evidence_ids≤50, evidence_count}`. Findings are review aids, never verdicts. |
| `typed` | Decimal-style decision `{value, source, evidence_counts}`, document currency and source, sign conventions, recognised tables and unmapped columns; for PDF the page-tree/trailer/encryption facts. |
| `measures`, `coverage` | Section 6. |
| `narrative` | `{status: ok\|truncated\|failed, format: markdown, text, chars, truncated, producer, authority}`. |
| `guard` | Audit-hook summary including every denied event (section 5). |
| `supervisor` | Run/request ids, exit code, stdout/stderr bytes, elapsed ms, peak memory, containment kind, `stop {requested, confirmed, method, run_dir_removed}`, outcome. |

Locators are 1-based: `{row}` for CSV records, `{sheet,row}` for XLSX, `{page}` for PDF and
`{part}` for an OOXML package part. `evidence_id = <sha256[:12]>:<sheet=…!>row=N` (sheet names
percent-encoded), so the same bytes always produce the same ids.

**Record** (`kind`: `transaction` \| `opening_balance` \| `closing_balance`): `date {raw, value
ISO|null, status}`, `amount {raw, decimal, minor_units, exponent, status, source}` (null for
balance rows), `balance {…}`, `currency {raw, value, status, source: row|metadata_key|document|
option|null}`, `description` and `reference {raw, status}`. Value statuses: `known`,
`missing`, `ambiguous`, `invalid`, `unknown_currency`, `precision_exceeds_currency`,
`formula_without_cached_value`. Every non-`known` value has `minor_units = null`; nothing is
defaulted to zero.

## 4. Extraction rules (typed parsers, never Markdown)

* **CSV**: strict UTF-8 (BOM allowed); other encodings are `unsupported_encoding`, never
  guessed. The stdlib `csv` reader runs with `field_size_limit = max_field_chars`; a reader
  error stops the file with an explicit `csv_reader_stopped` finding and partial status.
* **XLSX**: the ZIP central directory is checked before any decompression (member count,
  per-member and total uncompressed size, ratio > 200 for members over 1 MiB, encrypted
  members, required parts). Macro-enabled content types or `vbaProject.bin` are refused, never
  executed. External-link parts are listed as unparsed and not followed. openpyxl is used in
  read-only mode with `keep_links=False`, ignoring declared sheet dimensions. A first pass finds
  formula cells and a second reads cached values: cached values are used but flagged as not
  recomputed, and uncached formulas are unknown. Spreadsheet floats become `Decimal(repr())`,
  so `0.30000000000000004` is kept exact and fails the currency-precision check instead of
  being rounded.
* **Tables**: a header is the first row (within 10) that maps at least two known column
  synonyms including a value column. Rows before it must be key/value metadata (`Currency`,
  `Opening balance [(CCY)]`, `Closing balance`, `Account`, `Period …`), otherwise they are
  unparsed. A sheet with neither is `unsupported`. `Opening/Closing balance` rows with no amount
  become balance records. Extra cells beyond the header width are `column_count_mismatch`.
* **Amounts**: the decimal convention comes from the caller (`declared`) or is inferred only
  from unambiguous tokens across the whole document. If both `1,234.56`-style and
  `1.234,56`-style appear, the source is `conflicting` and every amount containing a separator
  is ambiguous. `1,234`/`1.234` stay ambiguous unless a convention is declared. Tokens that are
  malformed under both conventions are invalid. Debit/credit columns produce signed
  `credit − debit`; both sides present, or a negative debit, is ambiguous. Minor units use ISO
  4217 exponents for 16 listed currencies; any other code is `unknown_currency`.
* **Dates**: ISO `YYYY-MM-DD` and typed spreadsheet dates are known. `d/m/y` or `m/d/y` forms
  need a declared `date_order`; otherwise they are ambiguous. Impossible dates are invalid.
* **PDF**: pdfminer.six per page. Pages with text are `parsed`. Image-only pages are
  `unsupported` (`no_text_layer_image_only`; there is no OCR) and never count as empty evidence.
  Password-protected files are `encrypted_pdf`; more than 50 pages is `page_limit_exceeded`. A
  missing trailer (`%%EOF`/`startxref`) adds `pdf_trailer_missing` and forces at most partial.
  PDF tables are **not typed in Part A**, so PDF reconciliation is `not_checkable`.
* **Narrative**: MarkItDown's `PdfConverter`, `CsvConverter` or `XlsxConverter` is called
  directly on the owned bytes with an explicit `StreamInfo`. This bypasses `MarkItDown()`
  itself and with it URI handling, plugins, magika guessing, OCR and LLM paths. It is capped at
  1,000,000 characters (truncation means partial). Measured on the hostile XLSX fixture, the
  narrative renders `0.30000000000000004` as `0.3`, an uncached formula as `NaN` and `-10` as
  `-10.0`. That is why the narrative is never authoritative.

## 5. Bounded child, cleanup and recovery

| Bound (enforced) | Value | Mechanism |
| --- | --- | --- |
| Input bytes | 10 MiB | store copy-in, child header check |
| PDF pages / table rows / columns / field chars | 50 / 20,000 / 64 / 4,096 | parser loop |
| XLSX sheets / cells / ZIP members | 16 / 500,000 / 256 | parser loop, central directory |
| ZIP member / total uncompressed | 32 MiB / 64 MiB; ratio 200 | central directory before inflate |
| Records / unparsed list / page text / narrative | 20,000 / 500 / 100,000 / 1,000,000 chars | collector |
| stdout / stderr | 16 MiB / 64 KiB | capped reader threads (drained, then error) |
| Wall-clock deadline | 30 s | supervisor loop → terminate |
| Memory | Windows 1 GiB committed per process; POSIX RLIMIT_AS 4 GiB | job object / rlimit |
| CPU | 2 × deadline | job per-process user time / RLIMIT_CPU |
| Processes | Windows: exactly 1 active process; POSIX: own session, killed as a group | job / setsid + killpg |
| Files | POSIX RLIMIT_FSIZE 0, NOFILE 256, CORE 0; cwd and TEMP = owned run dir (Windows: no OS file bound, see gaps) | rlimits / env |
| Stop confirmation | 5 s | job ActiveProcesses = 0 / process group gone |
| Handle lease | 3,600 s | store |

The POSIX address-space cap is virtual memory, so it sits above the Windows committed-memory
cap because numpy/onnxruntime reserve address space at import. These are caps, not
measured capacity. Single-run Windows observations from development, which are not
throughput claims: tiny fixtures took 1.5–2.0 s and about 78 MiB. A 20,000-row CSV (846 KiB)
took 2.5 s and 169 MiB, producing 11.7 MB of typed JSON (near the stdout cap) and a truncated
narrative. A 50-page text PDF took 3.6 s and 82 MiB. A PDF content stream that inflates to
64 MiB of operators hit the 20 s test deadline and was stopped, staying under the memory cap.

**Lifecycle.** The supervisor writes a recovery record (`state: starting`) and an owned run
directory (marker with a random nonce) before spawning. It launches the *base* interpreter in
isolated mode (`-I`) with an explicit import path, so no venv redirector process is involved.
The child gets a minimal environment, `cwd` set to the run directory and no inherited handles.
On Windows the child is assigned to the job before any request byte is written. The record is
then updated with the pid and a process identity: the creation time from `GetProcessTimes`,
or `/proc/<pid>/stat` start time. Every exit path, including deadline, cap, crash, invalid
output and `KeyboardInterrupt`, runs a stop step: terminate the job or kill the process group,
then wait until the process has exited **and** the job/group has no live member. Only a
confirmed stop removes the run directory (after its marker nonce is verified) and the record.
An unconfirmed stop keeps both, marks the record `stop_unconfirmed` and makes the result
`error` with code `stop_unconfirmed`.

**Recovery** (`sentinel-docworker recover`) re-reads each record. It terminates a pid only if
its current identity equals the recorded one; a reused pid is left untouched. A record with a
pid but no provable identity is kept. A run directory whose marker nonce does not match is
kept as not owned. Unreadable records are kept. When the supervisor itself is killed, the
Windows job's kill-on-close stops the child and the record is recovered later; on POSIX the
child survives in its session until `recover` kills it after verifying its identity. Both
paths are tested.

On POSIX, recovery also requires the recorded **process group** (the child is its session and
group leader) to be empty before it reports `recovered` (review R58):

* **Verified leader alive and still in that group:** a group id cannot be reused while its
  leader exists, so recovery signals the group, then waits until the leader is gone and no
  live member remains.
* **Leader already exited:** that is not proof the group is empty, and the group can no
  longer be proven ours, so recovery never signals it. Any live member yields
  `group_members_alive_kept`; an undeterminable `/proc` yields `group_state_unknown_kept`.
  Either way the record and owned run directory are kept for a later retry or manual
  recovery.
* **Group state is determined fail-closed** (follow-up review of 69b51fe). Only a `/proc`
  entry that genuinely disappeared (`ENOENT`/`ESRCH` on its `stat`) is skipped. If `/proc`
  cannot be listed, or any listed entry's `stat` raises another error (permission, I/O) or
  is malformed, membership is unknown and the result is `group_state_unknown_kept`; nothing
  is signalled, and repeated retries stay kept until the entry is readable and no member
  remains.
* **Kernel confirmation after the scan** (review of 7ec46ae). A `/proc` snapshot alone cannot
  prove a group empty: a member can fork a new member after the listing and then exit. When
  the scan finds no live member, recovery asks the kernel with a non-signalling
  `killpg(pgid, 0)`. Only `ESRCH` (no process at all in the group) lets it report
  `recovered`. A live, zombie-only, inaccessible (`EPERM`) or reused group gives
  `group_members_alive_kept`, and any other error gives `group_state_unknown_kept`. The record
  and run directory are kept and nothing is signalled. A zombie-only group is kept on purpose
  until its parent reaps it; after a supervisor crash that parent is init.
* **Process-group layout of a reused pid.** A recorded pid whose identity does not match is
  never signalled. If that stranger happens to lead a live group with the recorded id, the
  group cannot be proved empty and the record is kept (`group_members_alive_kept`);
  otherwise the record is recovered.
* **Platform limit.** Recovery sees only what `/proc` shows. With a `hidepid` mount, other
  users' processes are invisible rather than unreadable; the parser's group runs as the
  supervisor's user, so its members remain visible, but no claim is made for a group whose
  members changed user.

On Windows no group exists: one-process jobs are killed on close, and reused-pid refusal is
unchanged.

**In-child guard.** After the parser libraries are imported and before the first document
byte is parsed, a PEP 578 audit hook denies Python-level sockets, HTTP/URL requests, process
creation, `ctypes.dlopen`, file writes/renames/deletes/mkdir, environment changes, and reads
or directory listings outside the interpreter/worker installation. Every fixture run reports
zero denials, and a probe child shows each class denied while stdlib reads stay allowed.

### Isolation claims and gaps (explicit)

* The audit hook is **defense in depth, not a sandbox**: native code can bypass it. **No
  OS-level network isolation is claimed.** Neither the Windows job object nor the POSIX rlimits
  restrict network access. Hard isolation would need a facility not added here (AppContainer,
  a firewall rule, a network namespace or seccomp), each of which is a system/policy change.
* Python startup in the child (site-packages `.pth` files, then imports of `markitdown`,
  which also imports `requests`, `magika` and `onnxruntime`) runs before the guard. That is
  locked installed code, not document bytes. On Windows a sub-millisecond window exists
  between process start and job assignment, but the child only waits on stdin during it.
* File writes are bounded at the OS level only on POSIX. There, `RLIMIT_FSIZE 0` stops any
  non-empty write but still allows creating or deleting empty files. The Windows job object
  does not restrict the filesystem at all: a test child without the guard wrote 4 KiB outside
  its run directory. In the real child only the audit-hook guard blocks writes, and on Windows
  the child runs with the owner's file permissions. A restricted token or AppContainer would
  be needed to close this gap; that is a system/policy change, so it is not made here.
* The POSIX memory figure is `RUSAGE_CHILDREN` max RSS, an upper bound across children. The
  POSIX grandchild and hard-kill recovery paths are untested on macOS (identity uses `/proc`;
  without it records are kept, not acted on).

## 6. Deterministic measures (CSV/XLSX)

* **Coverage**: unit status counts, typed records and unparsed rows; for PDF, page status
  counts and text characters. Coverage counts what was read and is not a confidence.
* **Missingness**: for each field over transaction records, known/missing/unknown counts and
  `{numerator, denominator}` ratios. A 0/0 is left for the consumer to show as n/a.
* **Duplicates**: groups of transactions with an identical known date, minor-unit amount,
  currency, case/space-normalised description and reference. Rows with unknown key fields are
  counted as not checkable. These are possible duplicates, not evidence of fraud.
* **Reconciliation**, per currency and never merged: `opening + credits − debits − closing`
  in minor units, with credits positive and debits negative. Result is `reconciled` (0),
  `difference` or `not_checkable` with a reason: `opening/closing_balance_absent`,
  `…_unknown`, `conflicting_…_balances` or `unknown_transaction_amounts`. Records whose currency
  is unknown are counted separately.
* **Running balance**: previous known balance + known amount = stated balance. An unknown
  value breaks the chain and is never bridged.

The labelled fixture matrix currently covers 21 runs over 18 files (CSV 7, XLSX 4, PDF 7):
reconciling and mismatched statements, two currencies, conflicting and declared decimal
conventions, day-first dates, debit/credit columns with missing/invalid/duplicate values,
hostile notes, typed XLSX with metadata and cached formulas, a hostile XLSX (float artefact,
uncached formula, hidden instruction sheet, external link), a macro workbook, an OLE-magic
stand-in, text/mixed/image-only/encrypted/truncated/mislabelled/hostile PDFs. Tests also
generate oversized, page/row/column-cap, member-size, ratio, lying-header and Flate bombs.
DOCX is **not** in the matrix and its extra is not installed. Token savings are not measured,
because no tokenizer/model is specified; only bytes and characters are reported.

## 7. Later API/UI integration proposal (not implemented)

Proposed for coordination with Codex; no route, DTO snapshot or migration is added here:

1. A session-scoped `POST /documents` would accept multipart bytes and apply the same
   input/extension/sniff checks. Bytes go to private server storage, and the response returns
   only the handle id, format, size, sha256 and expiry. `DELETE /documents/{handle}` would give
   verified cleanup.
2. `POST /documents/{handle}/extractions` with explicit `options` would run this worker as a
   bounded job (one heavy job at a time). `GET …/extractions/{id}` would return this result
   document minus `narrative.text` by default. Evidence ids link UI rows to page/sheet/row.
3. A separate human-confirmation DTO would record confirmed conventions or corrected fields.
   It stays distinct from approval of any action, and nothing is ingested into transactions.
4. Version: AN01 proposes HTTP **v1.3**. DOC01 should take the next free contract version
   after Codex sequences both (provisionally v1.4), with new frozen snapshots only at that
   acceptance. The worker protocol keeps its own `sentinel.doc01.worker/x.y` version.
5. The worker would stay out-of-process with its own lock; the API would call it the same way
   this CLI does. Any app-side dependency on it would be a concrete integration request.

## 8. Dependency and provenance

`markitdown[pdf,xlsx]==0.1.8` (Microsoft, MIT, released 2026-09-21) lives in a separate
`tools/document_worker/uv.lock`, with 46 packages including dev tools. MarkItDown 0.1.9 was
not used because it requires `certifi>=2026.10.19`, which the application's certifi holdback
(pre-2026-10-09) excludes. The worker lock applies the same certifi holdback and a two-week
`exclude-newer` (2026-10-29), and resolves certifi 2026.7.22. The application `pyproject.toml`
and `uv.lock` are unchanged. No Microsoft or third-party code is copied or vendored; licenses
are listed in [THIRD_PARTY_NOTICES](../../tools/document_worker/THIRD_PARTY_NOTICES.md).
