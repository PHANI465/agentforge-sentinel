# Third-party provenance (document worker)

No third-party source code is copied, modified or vendored into this repository. Dependencies
are resolved from PyPI by `uv` into this tool's local `.venv` (ignored by Git) from the pinned
[uv.lock](uv.lock). They are not redistributed. If this worker is ever packaged or distributed,
the notices of the shipped distributions must be included at that time.

Primary dependency: **MarkItDown 0.1.8** by Microsoft, MIT License,
https://github.com/microsoft/markitdown (PyPI release uploaded 2026-09-21). It is used
through its `PdfConverter`, `CsvConverter` and `XlsxConverter` classes only. The `MarkItDown()`
facade, its URI handling, plugins, magika file-type guessing, OCR/Azure/LLM paths and the
MCP server are not used.

Locked runtime distributions (installed license metadata, Windows/Python 3.11, November 12):

| Distribution | Version | License (as declared) |
| --- | --- | --- |
| markitdown | 0.1.8 | MIT |
| pdfminer.six | 20260107 | MIT |
| pdfplumber | 0.11.10 | MIT |
| pypdfium2 | 5.14.0 | BSD-3-Clause, Apache-2.0 (+ bundled PDFium dependency licenses) |
| openpyxl / et_xmlfile | 3.1.5 / 2.0.0 | MIT |
| pandas | 3.1.0 | BSD-3-Clause |
| numpy | 2.4.6 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| magika | 0.6.3 | Apache-2.0 |
| onnxruntime | 1.20.1 | MIT |
| flatbuffers / protobuf | 25.12.19 / 7.36.2 | Apache-2.0 / BSD-3-Clause |
| coloredlogs / humanfriendly / pyreadline3 | 15.0.1 / 10.0 / 3.5.6 | MIT / MIT / BSD |
| sympy / mpmath | 1.14.0 / 1.3.0 | BSD |
| beautifulsoup4 / soupsieve / markdownify | 4.15.0 / 2.10 / 1.2.3 | MIT |
| charset-normalizer / defusedxml | 3.5.2 / 0.7.1 | MIT / PSF |
| requests / urllib3 / idna / certifi | 2.34.2 / 2.8.0 / 3.20 / 2026.7.22 | Apache-2.0 / MIT / BSD-3-Clause / MPL-2.0 |
| cryptography / cffi / pycparser | 50.0.2 / 2.1.1 / 3.12 | Apache-2.0 OR BSD-3-Clause / MIT-0 / BSD-3-Clause |
| pillow | 13.0.0 | MIT-CMU |
| python-dateutil / six / tzdata | 3.0.0 / 1.17.0 / 2026.6 | BSD + Apache-2.0 / MIT / Apache-2.0 |
| click / colorama / python-dotenv / packaging / typing_extensions | 8.5.0 / 0.4.6 / 1.2.4 / 26.3 / 4.16.0 | BSD-3-Clause / BSD / BSD-3-Clause / Apache-2.0 OR BSD-2-Clause / PSF-2.0 |

Development only: pytest 8.4.2, pluggy 1.7.0, iniconfig 2.3.1, pygments 2.21.0 (MIT/BSD) and
ruff 0.17.3 (MIT). `uv.lock` also resolves a second numpy version for other Python markers.
The lock is authoritative for exact versions and hashes. The table records declared
metadata, not a legal review.

Supply chain: `exclude-newer = 2026-10-29` (two weeks before lock creation) and the
application's original certifi holdback (`2026-10-09`). MarkItDown 0.1.9 was excluded because
it requires `certifi>=2026.10.19`.
