# Backend CI (C06)

Audience: whoever integrates or runs the backend checks. Refreshed for the accepted f38e920 release (review e7fc868: R25, R27). The frontend/browser workflow is separate.

## What runs

`.github/workflows/backend.yml` is one job on `ubuntu-24.04`, triggered by pushes to `main` and `task/**`, pull requests and manual dispatch. The job is bounded at 60 minutes, and each long step has its own bound.

1. **Checkout and toolchain.** Checkout does not persist credentials. The job has read-only `contents` permission and references no secrets. uv 0.9.26 (pinned) with Python 3.11, and Node 22.
2. **PostgreSQL.** Server binaries come from the runner image, or from apt if absent. `SENTINEL_PG_BIN` is exported. Tests start their own disposable trust-auth clusters on 127.0.0.1; no external database is used.
3. **Install:** `uv sync --locked --extra dev --extra ml`. The lockfile is authoritative, and the accepted C03/C04/C07 code needs numpy, scikit-learn and joblib.
4. **Lint:** `ruff check .`
5. **Tests, through the structured gate** (`scripts/ci_test_gate.py`, bound 30 min). It runs pytest with a JUnit report and accepts the run only if all of these hold:
   - **pytest exited 0.** Any nonzero code (failure 1, collection error 2, usage 4, nothing collected 5) is returned unchanged.
   - **The report is sound:** it exists, parses, and its per-suite totals agree with its test cases. Missing, malformed or truncated reports fail, and a stale report is deleted before the run.
   - **Nothing failed or errored,** and at least one required test executed and passed.
   - **The skipped set is exactly the opt-in live Claude smoke test** (`tests.test_investigators::test_live_claude_cli_smoke`, with its quota reason). Any other skip or xfail fails the gate, and so does that test running or missing.

   `SENTINEL_LIVE_CLAUDE=0` and `SENTINEL_INVESTIGATOR=deterministic` are set, and the runner has no Claude CLI or login.
6. **Handoff helper regressions.** They isolate Git config and set their own identity.
7. **JSON Schema exports are current:** `export_contracts.py --check`, a byte comparison.
8. **HTTP contract is current:** `export_http_contract.py --check`. This covers the frozen legacy v1 (by hash), the active v1.1 and all examples, regenerated from real servers in rule and model mode.
9. **Node transport check.**
10. **Package contents:** `scripts/check_package.py` (below), bound 10 min.
11. **Accepted ML result reproduces,** bound 10 min. `python -m ml test --reproduce` is the accepted read-only path: it recomputes the frozen p1 evaluation and compares it with the stored report.
    - Its output must be exactly `{"reproduced": true}`.
    - Afterwards, `git diff --exit-code` and `git status --porcelain` must show **no change** under `ml/`, `evals/` or `data_pipeline/`.
    - There is no selection, tuning or second writable test evaluation. The plain `test` command refuses because the frozen report exists. Its generated data snapshot goes to the ignored `data/`.

Third-party actions are pinned to full commit SHAs, resolved from their tags on 2026-10-23 with `git ls-remote`; this refresh did not re-resolve them:

| Action | Tag | Commit |
| --- | --- | --- |
| actions/checkout | v4.4.0 | `11d5960a326750d5838078e36cf38b85af677262` |
| astral-sh/setup-uv | v6.8.0 | `d0cc045d04ccac9d8b7881df0226f9e82c39688e` |
| actions/setup-node | v4.4.0 | `49933ea5288caeca8642d1e84afbd3f7d6820020` |

## Package verification

`uv run --locked python scripts/check_package.py`:

- **Clean build.** Builds the wheel and sdist from a clean copy of tracked and non-ignored files. An in-place build can silently reuse a stale `*.egg-info/SOURCES.txt` or `build/`.
- **Migrations.** Every `src/sentinel/db/migrations/*.sql` file (currently four, 0001–0004) must be byte-identical in both archives, with nothing extra.
- **Model and data assets.** The accepted model and data identity assets must be byte-identical in both archives:
  - `ml/protocol.json`;
  - `ml/runs/p1/selection.json` and `select_stats.json`;
  - `ml/artifacts/p1/manifest.json` and `model.joblib`;
  - `ml/results/p1/test_report.json` and `pr_curve_selected.csv`;
  - `data_pipeline/manifests/reference-g1-seed7.json`.

  The wheel must ship **no other** non-Python file under `ml/` or `data_pipeline/`, so an extra artifact fails.
- **Forbidden content.** Caches, `.env`/key files, `.agent/` and generated data are forbidden everywhere. Tests and `evals/` are forbidden in the wheel.
- **Installed check.** The wheel is installed into a fresh virtual environment with the lock's ml pins (`uv export --locked --extra ml`, `--no-deps`) and run with `python -I` from a neutral directory. There, `sentinel`, `ml` and `data_pipeline` must import from that environment, discover exactly the source migrations, bind the registered `hgb_balanced@p1` scorer, and load the frozen results with the accepted artifact hash.

It is the sixth configured command in `scripts/agent_check.py`, which keeps I01's 1800-second per-command limit. A local strict PASS therefore covers it.

## Reproduce locally

```powershell
$env:SENTINEL_LIVE_CLAUDE = "0"; $env:SENTINEL_INVESTIGATOR = "deterministic"
uv sync --locked --extra dev --extra ml
uv run --locked python -m ruff check .
uv run --locked python scripts/ci_test_gate.py --junit pytest-results.xml
uv run --locked python -m unittest discover -s tests_handoff -v
uv run --locked python scripts/export_contracts.py --check
uv run --locked python scripts/export_http_contract.py --check
node scripts/check_contract_examples.mjs
uv run --locked python scripts/check_package.py
uv run --locked python -m ml test --reproduce      # must print {"reproduced": true}
git status --porcelain -- ml evals data_pipeline   # must print nothing
```

Workflow syntax: `uvx --from actionlint-py actionlint .github/workflows/backend.yml`, an ephemeral tool and not a project dependency. Shell snippets were not checked by shellcheck, which is not installed.

## Evidence status

| Item | Status |
| --- | --- |
| R25 regressions (`tests/test_ci_test_gate.py`) | Executed. The workflow's actual Tests step runs under bash with `-eo pipefail` against throwaway suites with real skips. **Baseline at 034c2ed (old grep gate): 3 failed** (an extra skip, an extra xfail, and a run without required tests were all accepted with exit 0). After the fix: 17 passed, including the validator, exit-code preservation and stale-report cases |
| R27 package asset tests (`tests/test_check_package.py`) | 5 passed (missing, altered and extra asset cases) |
| Package check, real build | Exit 0 in about 42 s: 4 migrations and 8 assets; the installed wheel binds the scorer outside the source tree |
| ML reproduce gate, real run | `{"reproduced": true}`, exit 0, 85 s; `ml/`, `evals/` and `data_pipeline/` unchanged |
| Full suite through the gate, real run | 418 passed, 1 allowed skip, gate exit 0. Wall time was 52.5 min because Windows **entered sleep and Modern Standby during the run** (System log events 42/107/506/507); one normally seconds-long test straddled it at 1698 s. That duration is not representative. Earlier awake runs took about 14–16 min |
| actionlint on the workflow | Executed offline: no findings |
| The workflow on GitHub Actions | **Not executed.** No Git remote or runner is configured, so it is unverified, not green |
| Linux (ubuntu-24.04) | **Not executed.** N2 fixed the orphan test's Windows-only launch; one Windows-only skip remains a Linux gate blocker. See [LINUX.md](LINUX.md) |

Running the workflow needs a remote (for example a private GitHub repository) and the free Actions allowance. Configuring a remote is an owner action.
