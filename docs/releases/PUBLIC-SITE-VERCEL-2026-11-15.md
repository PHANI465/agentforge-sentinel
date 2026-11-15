# Invoice checks and live synthetic workbench

The [Vercel production homepage](https://agentforge-sentinel.vercel.app/) serves the
browser PDF explainer, recorded case, training ZIP and [live analyst workbench](https://agentforge-sentinel.vercel.app/workbench).
The [existing Sites homepage](https://agentforge-sentinel-walkthrough.engagingfoxglove1.chatgpt.site/)
links to the same live workbench.

## PDF regression and design

PDF.js extracted the text of all three user-supplied QA invoices on the original site
build. The original extraction rules returned zero findings on each. The new rules
recognize the supported table headers and printed amounts, check invoice arithmetic
using integer cents and explain observable remittance details. They use the invoice
body and exclude its QA answer annotations.

- **Arithmetic.** The second row gives $480.00 at its printed rate and quantity, versus
  $680.00 printed. The printed rows sum to $1,280.00 versus the stated $1,480.00
  subtotal. The stated subtotal plus tax is $1,598.40 versus $1,898.40 due.
- **Threshold.** The notes report a $4,995.00 request, $5.00 under the stated $5,000.00
  approval threshold. They cite a second $4,995.00 invoice, totaling $9,990.00 if both
  apply. The reviewer must confirm the records and actual policy.
- **Remittance.** The invoice requests changed payment details, prints a different
  beneficiary name and supplies an all-zero routing number. Sender/domain and
  vendor-master checks are follow-up prompts. The site cannot verify sender identity.

The browser limit is exactly 10,000,000 bytes (10 MB). The separate local DOC01 API
retains its existing 10 MiB contract. PDF explanations remain browser-only and work
on supported readable text. OCR and arbitrary table layouts are outside this release.
The attachments stay local and are not present in Git or the deployment archive.

The redesigned walkthrough uses five steps and retains the recorded ten-frame view
and original JSON under a technical replay link. It follows the supplied Elaya design
reference and uses a single current step, readable copy and optional technical detail.
Landing page highlights explain the PDF QA, synthetic model inputs and approval checks.
[Elaya design reference](https://github.com/elayadesign/ai-design-skills/tree/main/skills/landing-page-design)
· [IC3 guidance on verifying payment changes](https://www.ic3.gov/CrimeInfo/BEC)

## Hosting and verification

The Vercel connector returned 403. CLI device authorization restored access to the
existing Hobby project. Neon was provisioned on `free_v3` and the owner URL was used
locally for migrations and role setup, then detached from the Vercel project.
The deployed app uses the restricted runtime role and deterministic code. The workbench
runs actual API calls and persists its synthetic case, approval, action and audit in
PostgreSQL. Test visitors do not have the ingest or document-analysis grant.

Checks on the release source include 7 invoice unit tests, the exact three local PDFs
in Chromium on the public site, and desktop/narrow walkthrough navigation. Frontend
typecheck, 266 unit/component tests, and the hosted Vite build passed. The live Vercel
smoke exercised two isolated scopes, denied document upload, checked zero actions
before approval and execution, then checked one action and an idempotent retry.
There was one initial deployment command refusal because the existing Vercel project
expects a `web` directory. Packaging inside that directory resolved it.
[Deploy and repeat verification](../../hosting/vercel/README.md)
