# Public financial samples, Office document review and IAF

The [public Sentinel website](https://agentforge-sentinel.vercel.app/) has a
labeled sample selector, charted document findings, and IAF. The document review
runs independently of the assistant.

## Verified sample documents

| Label | Original publisher | Checks |
| --- | --- | --- |
| U.S. Treasury, January 2025 | [Monthly Treasury Statement, Bureau of the Fiscal Service](https://fiscal.treasury.gov/system/files/files/reports-statements/mts/mts0125.pdf) | PDF page 5, Table 2. Receipts 513,294, outlays 641,935 and deficit 128,640, in USD millions. |
| U.S. Treasury, May 2025 | [Monthly Treasury Statement, Bureau of the Fiscal Service](https://fiscal.treasury.gov/system/files/files/reports-statements/mts/mts0525.pdf) | PDF page 5, Table 2. Receipts 371,229, outlays 687,233 and deficit 316,004, in USD millions. |
| Synthetic bank statement | Existing Sentinel synthetic fixture | Closing balance of USD 1,554.90 on page 2. |

The originals are served as downloaded. The January sample SHA-256 is
`6c39f80675b641970bcadca9372872c3d50f675604429de80a5e4e709dc1a3e9`; the May
sample SHA-256 is `f73005ace5c3c8114f51997d3e0d12600e493fa2e786a26ab730a30896d7bdd7`.
The Treasury results come from the “This Month” cells in Table 2. A discrepancy
of up to USD 1 million can come from published rounding.

## Reading Office documents

The browser uses fflate 0.8.3 to unpack the relevant XML parts. Its license is
included in the vendor directory. XLSX shows worksheet previews and same-currency
totals for explicitly supported headers. Formula cells are skipped. DOCX shows
body text, table-derived lines and supported invoice findings. Save older Word
DOC files as DOCX before reviewing them. Windows browser tests check both
Treasury reports, same-currency workbook totals and formula exclusion, and Word
source evidence. The earlier synthetic invoice checks and both case replays
remain covered by the same browser suite.

## IAF

IAF answers from the project library and the author’s public portfolio. It can
optionally use an OpenAI API key to select a supported answer.
[Key setup and scope](../../hosting/vercel/IAF.md)
