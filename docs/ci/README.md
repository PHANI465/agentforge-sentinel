# Backend CI (C06)

Audience: whoever integrates or runs the backend checks. Cursor owns the separate frontend/browser workflow.

## What runs

`.github/workflows/backend.yml`, one job on `ubuntu-24.04`, triggered by pushes to `main` and `task/**`, pull requests and manual dispatch:

1. Checkout without persisted credentials. Read-only `contents` permission; no secrets are referenced.
2. uv 0.9.26 (pinned) with Python 3.11, and Node 22.
3. PostgreSQL server binaries from the runner image, or apt if absent. `SENTINEL_PG_BIN` is exported, and tests start their own disposable trust-auth cluster on 127.0.0.1.
4. `uv sync --locked --extra dev`; the lockfile is authoritative.
5. `ruff check .`
6. `pytest -q -rs`. The step then **asserts** the opt-in live Claude test was skipped. `SENTINEL_LIVE_CLAUDE=0` and `SENTINEL_INVESTIGATOR=deterministic` are set, and the runner has no Claude CLI or login, so the adapter would fail closed anyway.
7. Handoff helper regressions (they isolate Git config and set their own identity).
8. JSON Schema exports are current (`export_contracts.py --check`, byte comparison).
9. Node transport check.
10. `scripts/check_package.py` (below).

Third-party actions are pinned to full commit SHAs, resolved from their tags on 2026-10-23 with `git ls-remote`:

| Action | Tag | Commit |
| --- | --- | --- |
| actions/checkout | v4.4.0 | `11d5960a326750d5838078e36cf38b85af677262` |
| astral-sh/setup-uv | v6.8.0 | `d0cc045d04ccac9d8b7881df0226f9e82c39688e` |
| actions/setup-node | v4.4.0 | `49933ea5288caeca8642d1e84afbd3f7d6820020` |

The workflow does not run the ML job yet. It will be added only after C03 and C04 are accepted, so a missing ML gate never shows up as a green skip.

## Package verification

`uv run --locked python scripts/check_package.py`:

- Builds the wheel and sdist **from a clean copy of tracked + non-ignored files**. An in-place build can silently reuse a stale `src/*.egg-info/SOURCES.txt` or `build/`; during development that masked a removed `package-data` entry.
- Requires every `src/sentinel/db/migrations/*.sql` file, byte-identical and nothing extra, in both the wheel and the sdist.
- Forbids caches, `.env`/key files, `.agent/` and generated data in either archive, and tests in the wheel (setuptools adds test files to the sdist by default).
- Installs the wheel into a fresh virtual environment and checks that the installed package (not the source tree) discovers exactly the source migrations.

It is also the sixth configured command in `scripts/agent_check.py`, so a local strict PASS covers it.

## Reproduce locally

The same commands as the workflow, from the repository root:

```powershell
$env:SENTINEL_LIVE_CLAUDE = "0"; $env:SENTINEL_INVESTIGATOR = "deterministic"
uv sync --locked --extra dev
uv run --locked python -m ruff check .
uv run --locked python -m pytest -q -rs
uv run --locked python -m unittest discover -s tests_handoff -v
uv run --locked python scripts/export_contracts.py --check
node scripts/check_contract_examples.mjs
uv run --locked python scripts/check_package.py
```

Workflow syntax check: `uvx --from actionlint-py actionlint .github/workflows/backend.yml`. This is an ephemeral tool, not a project dependency. Shell snippets were not checked by shellcheck (not installed).

## Evidence status

| Item | Status |
| --- | --- |
| Every workflow command, locally on Windows 11 (CPython 3.11.3, PostgreSQL 14.17, Node 22.13.1) | Executed. Pass: ruff; 106 passed / 1 skipped (live Claude), and the skip assertion held; 21 helper tests; 15 schemas; Node; package OK |
| Package check negative case (no `package-data`) | Executed: failed for wheel, sdist and installed discovery, as intended |
| actionlint 1.7.12 on the workflow | Executed: no findings |
| The workflow on GitHub Actions | **Not executed.** No Git remote or runner is configured. It is unverified, not green |
| Linux (ubuntu-24.04, PostgreSQL 16 from the image) | **Not executed.** WSL Ubuntu 24.04 exists locally but lacks uv/Node/PostgreSQL and runs as root (initdb refuses root). Preparing it needs the owner's approval |

Running it needs a remote (for example a private GitHub repository) and the free Actions allowance. Configuring a remote is an owner action; this task does not do it.
