# HTTP v1.2 fixture copies

These files are byte-for-byte copies of the accepted G3C-A trace examples. They are test fixtures for the analyst UI. They are not a live server, and the UI must never substitute them when a request fails.

- Source commit: 16b67fd0cd09cdd08bbfa64a159035a7a188bf5b (G3C-A, accepted in docs/reviews/G3C-A-16b67fd.md on task/coordination)
- Source paths: contracts/http/examples-v1.2/ (read with git show)
- OpenAPI snapshot: contracts/http/openapi.v1.2.json
- OpenAPI SHA-256: b52f8fd4d323f59565b3e1148557cb85221b76c793377e021c32f9c877e5b053
- Semantics: docs/api/investigation-trace-v1.2.md and docs/decisions/0008-investigation-trace-read-contract.md at the same commit
- The bytes are checked against this list in src/api/trace.test.ts.

- error_trace_invalid_workflow_id.json sha256 7fa450020df3d75e495c7cea099b462ff817639279625823c182ed0816c4559d (262 bytes)
- error_trace_not_found.json sha256 6c83006720d26f24cd7a3cf819b425c0598eefa45b63b1e20e7cf7861a49ae17 (233 bytes)
- error_trace_permission.json sha256 05b5fccb7f038c869d1009d307e96c8ec4eaa325568b205d1c3a6eb011736f17 (241 bytes)
- error_trace_workflow_not_found.json sha256 03dfc0cccc71a1733415a77112963279297dea180037d5c4be9637bc9ad484af (282 bytes)
- trace_abstain_after_challenge.json sha256 065c07d5751f7ced36a2685cc699d0fb6981cae2ce32db568a8e268bd7b96fe6 (33073 bytes)
- trace_completed_recommend.json sha256 356589d13203296b81e770df3f1b4811813db8c426400e01e2695216236b1fa0 (24534 bytes)
- trace_legacy_investigator.json sha256 80506ab5c84d9f9c11010bbc2b803c6c7c771f89f034d7597e4a9aa9c86b0a05 (467 bytes)
- trace_no_workflow.json sha256 82a5c1bac98b388031384dab7ce6bb60631125603ccbce2bfa5ea198bfdadc2b (454 bytes)
- trace_recovered.json sha256 e90d1e22cae2215af2663dbb123b6397527eac7e148d3e5f828137b953714c4a (13993 bytes)
- trace_repeat_after_provider_failure.json sha256 fb32640a931492607509e6185f519e2debb7f9067cb2cb9ff55cef1596eb40ec (25288 bytes)
- trace_retry_latest.json sha256 60002c78eb016ff6e99642114113be97eb4c9338e0d0d26903c322d03c87755d (23849 bytes)
- trace_retry_prior.json sha256 d58b549ba25b9bed0be99afe87b6faa07568df6ee4140c5c7db702a8ff567298 (14438 bytes)
- trace_running_between_roles.json sha256 8984a74e1b764c9fd4a53b21b93d96ae932ee65b9c2944505ca3ab55b4a54814 (13219 bytes)
- trace_running_recovery_due.json sha256 5f330c473b6137c0251b9ebe05bde4971921bf52f54eb74ea6694aa33006f6be (13216 bytes)
- trace_untrusted_note.json sha256 24bee29f12ef0079048e9d865dd06e662be4bfe984cbaa3c161660b825d7060d (23528 bytes)
- trace_zero_roles.json sha256 109e6182a6d881d79166de5975cfc9359673b2e751af74255db9a167b5255063 (6873 bytes)
