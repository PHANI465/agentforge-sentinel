# Handoff: task/claude-fraud-data

- Task and acceptance criteria: C03 (docs/TASK_QUEUE.md). A reproducible synthetic generator with fraud scenarios and legitimate lookalikes; hidden labels separated from decision-time rows; historical-only features; same-timestamp and availability rules; a chronological split policy; manifests, quality checks and reconciliation; measured runtime and memory; a data card.
- Owner: Claude Code. Accepted dependency: task/coordination at fcc04c5. Independent of C01; no API, contract or web/ edits.
- Tool and worktree: Claude Code, E:\PHANI\sentinel-wt\claude-fraud-data (branch task/claude-fraud-data)
- Updated: 2026-10-23
- State: ready for Codex review. Acceptance unblocks C04.
- Code reference tested before this note: working tree on top of fcc04c5 (strict checks rerun after the commit; reported in chat)
- Owned/changed paths: data_pipeline/ (new: generator, features, splits, manifest, fixtures, CLI, manifests/reference-g1-seed7.json), tests/data/ (new tests plus fixtures/tiny/), docs/ml/data-card.md (new), .gitignore (`data/generated/`), pyproject.toml (pytest `pythonpath` adds "."; no dependency change; uv.lock unchanged), this note.

## Implemented

- **Generator g1:** deterministic, seeded, standard library only.
  - Three fraud scenarios (account takeover, card testing, mule cash-out) and three legitimate lookalikes (payday burst, large purchase, micro-payments).
  - Four currencies with exact minor units; late ingestion for 1% of rows.
  - Delayed labels: fraud disclosed after 1–45 days, 10% never disclosed; legitimate labels mature after 30 days.
  - A row limit with an honest `truncated` flag.
- **Features f1:** 12 historical-only features. Decision key `(ingested_at, external_id)`; strict event window `[t−30d, t)`; labels usable only once disclosed. Batch and online implementations.
- **Split s1:** chronological 60/20/20 with a 1-day embargo. Training eligibility comes from labels disclosed by `train_end` (`train_ineligible` is kept, not dropped silently).
- **Manifests:** file hashes, row counts, per-currency/direction totals, label and scenario stats, config and version. `verify` recomputes everything. Quality checks: TransactionInput contract validation, no label fields in decision rows, 1:1 labels, known accounts, no ingestion before occurrence.

## Verified (working tree before the commit)

- `tests/data/`: 21 passed (generation/fixtures/quality/reconciliation, features/invariance, splits).
- Leak mutation check: removing the availability filter failed 3 feature tests; removing the label cutoff failed 4. Both were reverted.
- Reference run (CLI): 50,768 rows and 335 fraud rows (0.66%), generated in 9.2 s with a 79.2 MiB Python peak; features for all rows took 6.5 s; `verify` passed. CPython 3.11.3, Windows.
- The full suite and strict checks after the commit are reported in chat.

## Not verified / gaps

- Reproduction on another Python version or OS has not been run (the manifest hash would reveal drift).
- Process RSS was not measured (tracemalloc only).
- With 30-day legitimate maturity and a 30-day horizon, the default 18-day training window has few eligible training rows. C04 must choose a longer `--days`, a maturity strategy, or document a synthetic-truth training view.
- No fitted preprocessing exists here (C04). Data is illustrative, not calibrated.

## Next action

Codex: review C03 (leakage rules, split and eligibility semantics, reconciliation). On acceptance, C04 starts from this commit.

## Coordination and provenance

- pyproject change: pytest `pythonpath` only. C06 owns CI/tooling and C04 owns dependency changes, so rebase onto this or coordinate.
- No dependencies added; no third-party simulator code or data; no live model calls.
