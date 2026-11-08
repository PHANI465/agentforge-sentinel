# DOC01: local financial-document feedback

November 8, 2026. Confirmed first scope: public/synthetic files on the owner's local
machine. This proposal does not add routes, libraries, upload storage or a UI today.

## User journey to implement

Upload a permitted local PDF, CSV or spreadsheet; inspect what was actually extracted;
confirm ambiguous fields; view deterministic reconciliation/data-quality findings and
optional evidence-grounded narrative. Each finding links to its page, sheet/cell or
source row. Show document identity, extraction coverage, warnings and missing evidence.
Feedback is a review aid, not proof that a document is authentic or that a person committed fraud.

## First implementation boundary

1. A bounded local extractor worker accepts only a server-owned uploaded-file handle.
   No arbitrary URI, host path, network fetch, shell command, plugin, macro or external link.
2. Validate extension/content type/size and archive expansion; enforce reviewed file,
   page/sheet/row/output bounds and a child-process deadline. Assign concrete limits in
   the implementation design; do not advertise unmeasured capacity.
3. Use MarkItDown for narrative conversion on allowed formats, with cloud clients and
   plugins absent. Text-layer PDFs first; scanned/unreadable pages are unsupported/partial,
   not empty evidence. CSV/XLSX authoritative numbers use typed parsers and Decimal.
4. Preserve source hash, parser version/configuration and evidence locators. Conversion
   to Markdown is not proof of page/table fidelity; measure it against labelled fixtures.
5. Normalize dates, currencies and signed minor-unit amounts with explicit locale/period
   assumptions. Never silently merge currencies or guess missing values. Human confirmation
   of extraction is distinct from approval of any action.
6. Compute deterministic totals, duplicates, missingness, sequence/date inconsistencies
   and reconciliation differences. Behavioral anomalies require real available history;
   a one-page document cannot supply p1's account features automatically.
7. Optional narrative consumes a minimal typed evidence view, never raw privileged
   instructions. No auto-ingestion into accepted transactions or automatic proposal/action.
8. Keep session scope/expiry, memory-only tokens, private temporary storage and verified
   cleanup. Do not send uploaded data to any model by default. New privacy scope needs
   an explicit choice; private customer and hosted multi-user files remain out of scope.

MarkItDown is [MIT](https://raw.githubusercontent.com/microsoft/markitdown/main/LICENSE).
Its [MCP server](https://raw.githubusercontent.com/microsoft/markitdown/main/packages/markitdown-mcp/README.md)
is a local trusted tool with broad URI access, so wrapping an owned file is preferable
to exposing convert_to_markdown(uri). Parser isolation and an absence of observed network
traffic are different claims; a future sandbox must demonstrate any promised network ban.

## Dependency and interface proof first

Current source dependency metadata can conflict with this project's certifi holdback.
Use a separately locked worker project or a reviewed compatible release; do not change
the application lock/supply-chain rules by accident. No Microsoft code is copied today.
Record license notices when distribution actually includes a dependency or copied code.

Define upload/feedback DTOs, error behavior, storage lifecycle, evidence IDs and worker
protocol in draft documentation before app integration. Choose the next HTTP contract
version with Codex; do not collide with AN01's proposed v1.3 or edit frozen snapshots.
The initial extractor CLI is Part A, not a finished browser-upload feature. A later
accepted API/UI slice must demonstrate browser → owned bytes → extractor → typed findings.

## Acceptance examples

- A synthetic bank statement reconciles opening balance + signed flows to closing balance,
  or explicitly says the needed balance/period is absent.
- Two currencies remain separate. An ambiguous 1,234.56 versus 1.234,56 is flagged.
- A scanned page is not falsely counted as fully extracted.
- A hostile note cannot call a tool, retrieve a host file or approve an action.
- A truncated, encrypted, oversized or decompression-bomb fixture fails safely and cleans
  up its owned worker/resources. Foreign-session handles are denied.
- Token savings are measured as a same-model input comparison with coverage, not promised
  from the word Markdown. Upload and feedback functionality are not claimed before integration.
