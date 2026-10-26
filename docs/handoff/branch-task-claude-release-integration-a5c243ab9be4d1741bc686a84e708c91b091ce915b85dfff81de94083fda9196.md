# Handoff: task/claude-release-integration

- **Task:** I03 local release integration (docs/prompts/CLAUDE_RELEASE_INTEGRATION.md on task/coordination b19317e). Integrator for this task branch only.
- **Tool and worktree:** Claude Code, E:\PHANI\sentinel-wt\claude-release-integration (new; the branch and path did not exist before).
- **Updated:** 2026-10-26.
- **State:** ready for Codex review.
- **Dependencies:**
  - branch created from exact C08 353ecec2fadbba43f939a27f5ad2b9227ff6fe87;
  - merged exact C06 4f06e32385424613fa0006b5bdbaab81ffea028f as **60d796d476b60f0b0e6f410f1fc2e2b945acf575** (parents 353ecec, 4f06e32; merge base f38e920);
  - clean automatic merge with no conflicts and no hand-resolved content.

  The accepted checkouts (C08 353ecec, C06 4f06e32, I02 f38e920) were clean at those SHAs before the merge, and were not edited.
- **Code reference tested before this note:** 60d796d plus this commit's two new documents (no code change). The final strict, JUnit-gate, contract and reproduce results are for the final commit and are reported in chat.
- **Changed paths (this commit):** `docs/releases/I03-local-release.md` and this note. No integration fixes were needed in `scripts/`, tests or docs/ci/runbooks.

## Byte comparison against f38e920

These are identical: `src/`, `contracts/`, `ml/`, `data_pipeline/`, `evals/`, `web/`, `pyproject.toml`, `uv.lock`, `tests/support/`, `docs/api/` and `docs/ui/`.

The only differences are the 17 accepted C06/C08 paths plus the two documents of this commit.

## Verified before the final commit

Windows 11, CPython 3.11.3, uv 0.9.26, Node 22.13.1, PostgreSQL 14.17. Locked dev+ml environment of this worktree, `SENTINEL_LIVE_CLAUDE=0`, `SENTINEL_INVESTIGATOR=deterministic`, no external test DB, `VIRTUAL_ENV` unset.

- **Ruff:** passed.
- **Focused combined tests:** 37 passed in 108 s. Files: `test_ci_test_gate.py` (17), `test_check_package.py` (5), `test_local_stack.py` (8), `test_local_stack_startup.py` (5), `test_local_rollback_drill.py` (1), `test_backup_restore.py` (1).
- **Model-mode operator smoke** (scratch state directory, ports 8095/55495), 56 s:
  - `up --scorer model` exit 0; `status` owned/owned;
  - `/v1/scoring` returned model, `uncalibrated_score`, 4.0295386895426815e-06 and `hgb_balanced`; `/v1/model-results/p1` returned 200 (offline synthetic benchmark);
  - an unprovisioned ingest got 422 `account_profile_missing`;
  - `down` exit 0, with the API and database verified stopped; `status` then exit 1;
  - `api.log` contains the token and `postgresql://` 0 times.

  The owned directory, confirmed by its marker, was removed after the verified stop.
- **`web/`:** `npm ci --offline` exit 0; `npm run typecheck` exit 0; `npm test` 44 passed; `npm run build` exit 0.
- **`npm run test:e2e`, unmodified,** under a process-scoped keep-awake wrapper: harness self-checks passed (scanner, 20 shutdown checks, 12 entry-point checks), then **19 passed** in 2.8 min, exit 0. No recovery or secrets file remained, `stacks/` was empty, and `browser.txt` is the ignored Chromium version file.

## Final-commit verification method (results in chat)

1. Run `scripts/agent_check.py` (six commands) with `PYTEST_ADDOPTS=--junitxml=<scratchpad path>`, so that check 2's single full pytest run writes the JUnit report.
   - Nested pytest runs inside `test_ci_test_gate.py` either drop `PYTEST_ADDOPTS` or pass their own `--junitxml` on the command line, which pytest applies after addopts.
   - The retained report is identified as the full-suite report by its test count and file coverage.
2. Run `scripts/ci_test_gate.py --validate-only` on that report.
3. Run `scripts/export_http_contract.py --check` and `python -m ml test --reproduce` with `git status` on `ml/`, `evals/` and `data_pipeline/`.

## Not verified / gaps

- **Platforms:** Linux, the GitHub Actions run, hosting and macOS were not executed. The POSIX operator path is untested.
- **Scope of claims:** synthetic data only. There is no claim about real fraud performance or capacity.
- **Open items:** the H01 low suggestions remain open (not assigned).
- **Sleep risk:** a long run on this laptop is affected by sleep. Keep-awake was used for the long runs; it changes no system setting.

## Next action

Codex: review the I03 candidate. The owner then decides main integration and designates the integrator.
