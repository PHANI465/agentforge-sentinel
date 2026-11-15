# Handoff for task/sol-document-insights

Worktree: `E:/PHANI/sentinel-wt/sol-document-insights`. Foundation:
`aa1c0690d8592cdbb5cb62827218059564feddc6`.
Application ancestor: `4bff7e12ca7d6eeaeca5061531d9011902038513`.
Scope: public static reviewer, samples, targeted tests, UI and handoff documents.
This is a delivery for independent review. Resolve the candidate SHA and compare it
to the foundation with Git.

## Delivery

- S1 connects PDF, XLSX and DOCX readers to the foundation's immutable, fixed-precision
  statement summary. A bounded PDF.js worker provides text. The review worker streams
  selected ZIP parts and runs typed checks. Office XML is parsed with DOMParser on the
  main thread under the byte and row limits. SHA-256 binds the file bytes to the review.
  Changing files or settings aborts the prior work and advances the generation.
- S2 adds findings with evidence controls, calculations, coverage, capability status
  and chart tables. Legacy invoice arithmetic now recognizes the unit-cost header
  variant and supported discount, shipping and handling adjustments.
- S3 provides 24 synthetic PDF, XLSX and DOCX files, eight scenario/control families
  and the two original Treasury reports. Files have different ground-truth outcomes
  and a deterministic manifest. The browser test checks curated results, a held-out
  Word layout and same-currency arithmetic. Official bytes remain those in
  [the original provenance record](../releases/PUBLIC-DOCUMENTS-IAF-2026-11-15.md).
- S4 implements explicit purchase, item, delivery, payment and baseline matches.
  A user-entered approval policy checks grouped invoices within its time window.
  One document supplies one record in this layout. Exact file copies count once,
  repeated record IDs prevent double counting, and deliveries shared across invoices
  remain unallocated until verified.
- S5 adds documented layouts, accessible result tables, a source pane, sample library,
  responsive observations, browser checks and privacy wording. The
  [user guide](../ui/PUBLIC-DOCUMENT-INSIGHTS.md) spells out the fields and limits.

## Evidence

Use the commands in [public_site/README.md](../../public_site/README.md). Raw logs and
screenshots are under the ignored `.agent/document-insights/` folder in the Sol worktree.
The final report names exact-commit Windows Node and Chromium evidence. The browser
checks run serially, with their own local servers and browser teardown. No backend,
native browser or hosted certification is claimed for this static change.

Earlier browser failures are retained there. The wider sample selector overflowed the
390 px layout. The settlement oracle originally said USD 960 after reversals when
600 + 390 − 40 is USD 950. The new examples heading once matched the sample selector
in the test. The first visual PDF QA tried to close the loaded document instead of
its loading task. Each issue was corrected before the final checks.

## Scope of capability claims

Typed comparisons need the documented inputs. A printed summary pass covers four
printed amounts. The transaction table check covers detected rows in the stated
layout. Detection coverage on unseen financial institutions and wide population
error rates are unmeasured. Printed source excerpts are available in the UI. PDF
coordinates refer to extracted text lines and Word to blocks, without pixel-level
highlights. OCR, digital authenticity, near-duplicate heuristics, automated field
correction, a cross-browser matrix and optional remote explanations remain open.
Temporary previews remain local. Existing IAF and synthetic casework have separate
interfaces and purposes.

The review branch is the next input for Codex. Verify exact ancestry and protected
paths, then independently review parsing assumptions, financial comparisons, public
claims and browser behavior. Preserve owner commit identity PHANI465
<pgavara1@asu.edu> and the original worktrees.
