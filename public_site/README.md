# Sentinel public website

The buildless site contains the browser PDF explainer, the recorded case replay and the
synthetic p1 dataset download. The live workbench deploys alongside the static files on Vercel. See ../hosting/vercel/README.md.

## Preview and verify

Serve `static/` with a static HTTP server. The Chromium regression test starts its own
loopback server by default. Point it at the application's installed Playwright modules
and synthetic PDF fixtures:

```powershell
node tests/browser.mjs <sentinel>/web/node_modules <sentinel>/tools/document_worker/fixtures <existing-output-directory>
```

An optional fourth argument tests the published origin. The run writes screenshots from
the sample only and checks that the visitor's PDF is handled without any outbound upload.

## Document insights foundation (not yet connected to the UI)

`static/document-evidence.mjs` validates immutable statement-summary evidence and
reconciles exact monetary values. It does not parse files or send data to a provider.
The [roadmap](../docs/documents/INSIGHTS-ROADMAP-2026-11-15.md) and
[Sol dispatch](../docs/prompts/SOL_DOCUMENT_INSIGHTS.md) define the next implementation.

```powershell
node --test public_site/tests/document-evidence.test.mjs public_site/tests/invoice-review.test.mjs
node public_site/tests/document-evidence.browser.mjs <sentinel>/web/node_modules
```

Run these from the repository root. The browser check serves only the new module on
loopback; it verifies a structured-input calculation, not an end-to-end PDF parser.

## Sources and licenses

- The synthetic sample PDF is `tools/document_worker/fixtures/pdf_text_statement.pdf`
  from Sentinel at `46fcb2f`. Its SHA-256 is
  `ca6f3b03164fe6c1735963f8e22684961b8fac7f25026d299628f2c9b4a6e1fc`.
- The original replay, its manifest and its data are preserved from the preceding site
  version. The replay entry lives at `walkthrough.html`.
- The p1 ZIP regenerates the model's source snapshot using `ml/protocol.json` and
  `ml.snapshot.build`. Manifest, feature and row digests match `ml/artifacts/p1/manifest.json`
  in Sentinel at `46fcb2f`. The archive contains generated data only.
- [Mozilla PDF.js 6.5.438](https://www.npmjs.com/package/pdfjs-dist/v/6.5.438) provides the
  vendored module, worker and character maps. Its Apache 2.0 license and the character map
  license are packaged with the assets. Package SHA-256
  `7461aefcd27c4ef0dd76f9ca5760f09466eb6b3f934432670c12132e7b3d6faa`.
- [Geist 5.3.0](https://www.npmjs.com/package/@fontsource-variable/geist/v/5.3.0) provides
  the self-hosted Latin variable font. Its SIL Open Font License is packaged beside it.
  Package SHA-256 `533dd66117795ac12316fb05fce27736c4bc63c31613b302d0a5285ca3a291d7`.
- Layout and copy references include [Elaya's landing page design skill](https://github.com/elayadesign/ai-design-skills/tree/main/skills/landing-page-design)
  and the [GOV.UK start page pattern](https://design-system.service.gov.uk/patterns/start-using-a-service/).
