# HTTP v1.3 fixture copies

These files are byte-for-byte copies of the accepted DOC01 Part B document examples. They are test fixtures for the analyst UI's Document review. They are not a live server, and the UI never substitutes them when a request fails.

- Source commit: 813b0db3f5e5b289428ea03dc249518f589bf0c2 (main publication of the accepted DOC01 Part B integration e51f47a; Part B accepted at d6d509e555d41638e24050f99bd8e53e1d7f3732)
- Source paths: contracts/http/examples-v1.3/ (29 files at that commit)
- OpenAPI snapshot: contracts/http/openapi.v1.3.json
- OpenAPI SHA-256: d4306c651f8a555fca6e309a27c7bd5b2c133f07d4cfc2f07f1fcde772eae4dc
- Semantics: docs/api/documents-v1.3.md and docs/decisions/0010-document-upload-contract-v13.md at the same commit
- The bytes are checked against this list in src/api/documents.test.ts.

- document_analysis_ambiguous_decimal.json sha256 88d008ccb7466dbc6844e6a6e5ee59c04a7e2de2fdd8e1713f5b64ba156e8f2c (12847 bytes)
- document_analysis_complete_paged.json sha256 364d2e3a47b948fa4d6fc6d74d0731881223832cc6056729225c94ef7b14f8c5 (12436 bytes)
- document_analysis_difference.json sha256 8c9a54c84bb6b962d4f4c677a37f9786cb5a60d4ed06a10f908a764c6744bded (17713 bytes)
- document_analysis_hostile_note.json sha256 098e76f429d80e123f0f76dc38977ed3691ba7ed81686a5e8cd0078b44495618 (11957 bytes)
- document_analysis_missing_values.json sha256 23a66093e20f775a21539568b68a8d67d84a897063fca1997c59c58ad1da9e98 (14095 bytes)
- document_analysis_partial_comma_decimal.json sha256 7db2a09adc6564f930a77e6eb032c8b0a840e2469814dcb4bffe2799d9b4f082 (11790 bytes)
- document_analysis_pdf_encrypted_unsupported.json sha256 8682c9a36027e9e09a29b29c250a3ad0c64ec6096a3d5d8c7e5bb4a94bc512b7 (1718 bytes)
- document_analysis_pdf_scanned_partial.json sha256 c3787ce909426894c1cabcd511afe5937524ee8233173d1d9490f26cd0e84687 (3464 bytes)
- document_analysis_pdf_text.json sha256 aac193913d6ee0664b718b4dc170bd49afd3821565819e823cbf851f1360c4a7 (3053 bytes)
- document_analysis_pdf_truncated_error.json sha256 863f2d8a04c141659e63a07b38484a0b95e1ca8a243be4d73c0417fe235616f7 (1694 bytes)
- document_analysis_two_currency.json sha256 ec1574acf2eae3298b27d6fe3882fcbde3d470824add7c470197af8261567143 (14837 bytes)
- document_analysis_xlsx.json sha256 2f3e6c9c8acc5de8d0ddee2941c516fa99d509a7d0fef9beed4af292a94d99d0 (14182 bytes)
- document_analysis_xlsx_macro_unsupported.json sha256 e801674a4aa835ffaf7c6d8b1dc000fc3e54808d6aa703b485531d0b2cbf5772 (1748 bytes)
- document_analysis_xlsx_partial.json sha256 8ddaeaa86c9547d1669f7a08da23b73fd2e8482377c7125d03735fe0c60cfede (12964 bytes)
- document_deleted.json sha256 4b347e0cbde3ab51f02e3ebfc347b9e1c0d887c9dcff90585586369b18949284 (248 bytes)
- document_records_page.json sha256 7860c42c39d49737dca130ba412e934f93ed69fe815d1056b61c392ac18ea3db (5765 bytes)
- document_upload_csv.json sha256 688f885acfcf59d3c5372602541cadabc6c5e470ac975dfa346247ebcca3fb4d (566 bytes)
- document_upload_pdf.json sha256 611c797cd846a2cce9b892fe802253eb8d8a7501790664c5dc7ac738e20f0ba7 (576 bytes)
- document_upload_xlsx.json sha256 0d418bd7301a131bd6f4fc10f1cef623ddcf44c82d62ed319cae71f4de82781d (625 bytes)
- error_document_format_mismatch.json sha256 5966b234a8e54fe6b3bcf46375a9bdf0127771424a2b1d9cd3028c4f14e1bacc (388 bytes)
- error_document_invalid_format.json sha256 a151a7c55a639b32b99cc276d2cb5ae22111a31ee5dd0c80fea75129b2a98261 (402 bytes)
- error_document_invalid_options.json sha256 65f6457d193c2aa1c21e88675325f82b7a560738b954f15b17f7982028466cb7 (327 bytes)
- error_document_malformed_handle.json sha256 48f8a89c7d421b196ea8b01c9feac71f5e42a1923dae9b033e74400c350e6aa6 (201 bytes)
- error_document_media_type.json sha256 a8189f63424364d45c833aeb47914fc260936bc519cf02f39f20012b3fb9241c (400 bytes)
- error_document_not_found.json sha256 0b4999e2fdf2694e7fee4e8a45caafb4630bae90f32189e172448bd8f3702167 (232 bytes)
- error_document_permission.json sha256 09f88fe2b3cb7f05da850bae32928a6b1f4f5290e817e8cac52efd1eb756be81 (387 bytes)
- error_document_too_large.json sha256 752e10d34632d387ad12bae6ebaa724ef70ad1174d347001a7f898d41e706dd7 (308 bytes)
- error_document_unsupported_container.json sha256 8c4fafa522593deb910d3f7eade614686e2e08fbba0136b021444ab21ff0a33b (451 bytes)
- error_document_worker_unavailable.json sha256 ae9f10e55a34075196be7a53ebedcb9c0416b9d3628179e4cdf7bbf7c734d4b1 (397 bytes)
