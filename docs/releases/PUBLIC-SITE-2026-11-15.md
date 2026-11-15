# Public PDF explainer and p1 dataset

Published November 15, 2026 at the existing public ChatGPT Sites URL.

- [Public landing page](https://agentforge-sentinel-walkthrough.engagingfoxglove1.chatgpt.site/)
- [Recorded fraud case](https://agentforge-sentinel-walkthrough.engagingfoxglove1.chatgpt.site/walkthrough.html)
- [Synthetic p1 dataset](https://agentforge-sentinel-walkthrough.engagingfoxglove1.chatgpt.site/dataset.html)

## What is deployed

Visitors can select a PDF or use the synthetic statement. PDF.js extracts readable
text inside the browser. Sentinel finds explicitly labeled amounts and financial
terms, explains them in plain language, and shows the source page and excerpt.
The site handles up to 10 MiB, 40 pages and 240,000 extracted characters per review.
It does not apply OCR, calculate from PDF tables, validate an invoice or run fraud
scoring on the document. Document bytes and extracted text stay in memory and are
not sent to a backend or model. The original recorded case and its data are preserved.

The dataset ZIP contains 82,819 generated transactions, 600 accounts, 581 synthetic
fraud rows, the labels, the frozen f1 features and the manifest. These are counts for
the full snapshot across chronological splits. The model used only eligible training
rows. The snapshot was regenerated with the frozen p1 protocol and the row, feature
and manifest hashes matched the model's recorded provenance.

ZIP SHA-256: `5fae73952bf4776992502b935ae21105de06d56e2efadf08ce14e32dff2a042d`.
The separate ULB/Worldline research dataset did not train p1. Its source links and
identifiers remain in the [dataset register](../data/external-dataset-register.md).

## Source and verification

- Sites source `54193852d0f8ae6ab82b566f26950b81f2504faf`, version 2,
  deployment `appgdep_6af970406ac081918ab7a4c83471c83b`.
- The app repository mirrors the exact static payload in [public_site/static](../../public_site/static/).
  [Site source notes](../../public_site/README.md) record reproducibility and license provenance.
- Chromium passed the browser check against the local and anonymous production URLs:
  sample and selected PDFs, image-only and mixed PDFs, plain-text hostile content,
  file size and invalid file refusal, clearing the results, keyboard navigation,
  390 px layout and replay navigation. The test observed no request carrying the
  selected PDF during review. The hosted ZIP downloaded with the expected digest.
- Application source, model, API, CI and contracts were untouched. Their release
  verification is recorded in the existing integration notes.

## Full workbench hosting

The live site serves static files. Running fresh fraud cases still needs a hosted
FastAPI runtime, PostgreSQL and a way to provision visitor sessions independently
of operator credentials. The Vercel connector returned 403 for the account scope.
The local Vercel CLI's token was also invalid. No new managed service was created.

Keep public PDF handling browser-based while bringing up the synthetic hosted
workbench. If enabling server-side document uploads later, put the parser behind a
separate sandbox with a durable store and bounded usage. The existing local DOC01
worker has no OS-level file or network sandbox, and the API keeps recovery records
on disk. Vercel Functions also cap request and response bodies at 4.5 MB, below
DOC01's 10 MiB upload contract. A container host with persistent storage or a
separate object-storage and isolated-worker design can preserve that contract.
[Local DOC01 security boundary](../security/DOC01-document-upload.md) · [Vercel limits](https://vercel.com/docs/functions/limitations)
