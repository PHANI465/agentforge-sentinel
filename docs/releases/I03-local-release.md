# I03 local release candidate

Audience: Codex (review) and the owner (main-integration decision). This candidate consolidates the accepted application with the accepted CI and operator packages for the **Windows-local** scope. It is not a hosted, Linux-verified or production release.

## Code references

| Item | Commit |
| --- | --- |
| Accepted application (I02, with C01–C05, C07, U01–U03, I01) | `f38e92023481a55db1ecf8bcdbe917140bd5d7cd` |
| Accepted C08 operator tooling (base of this branch) | `353ecec2fadbba43f939a27f5ad2b9227ff6fe87` |
| Accepted C06 backend CI | `4f06e32385424613fa0006b5bdbaab81ffea028f` |
| Integration merge (first parent 353ecec, second 4f06e32; merge base f38e920) | `60d796d476b60f0b0e6f410f1fc2e2b945acf575` |
| Final candidate | the commit containing this note (its SHA and final checks are reported in the review handoff chat and the ignored strict report) |

**The merge** was a clean automatic merge. C06's nine paths applied without conflict:
- `.github/workflows/backend.yml`, `SETUP.md`, `docs/ci/README.md` and the C06 handoff;
- the sixth `agent_check` command, `check_package.py` and `ci_test_gate.py`;
- their tests.

No content was hand-resolved.

**Byte comparison against f38e920:** these paths are **identical**: `src/`, `contracts/`, `ml/`, `data_pipeline/`, `evals/`, `web/`, `pyproject.toml`, `uv.lock`, `tests/support/`, `docs/api/` and `docs/ui/`.

The candidate differs from f38e920 only in the accepted C06/C08 files (17 paths: CI workflow and gate, package checker, operator stack, runbooks, their tests and handoffs) plus this note and the I03 handoff. There are no model, threshold, training, evaluation, fixture, contract, dependency or UI changes.

## What it contains

- **Application.** Analyst workbench (React/Vite) over the FastAPI/PostgreSQL API, with:
  - deterministic bounded investigation;
  - human approval and simulated actions;
  - an append-only audit trail;
  - a least-privilege runtime role;
  - the rule scorer (default) or the registered trained `hgb_balanced@p1` model (explicit).

  Model results are a frozen offline synthetic benchmark. HTTP contract v1 is frozen and v1.1 is active; there are four migrations.
- **Operator stack** (`scripts/local_stack.py`, C08/R24/R26/R28): identity-verified up/status/down, a model or rule scorer, backup, and restore into a new database with a rollback runbook. Startup fails closed: an unresolved launch blocks `down` from stopping the database, and readiness needs a real health response.
- **CI** (C06), unexecuted on a real runner:
  - the backend workflow with locked dev+ml;
  - the structured JUnit skip gate;
  - HTTP contract, package and read-only ML reproduce gates;
  - pinned actions and read-only permissions.
- **Strict local check:** `scripts/agent_check.py`, with six commands and an 1800-second bound per command.

## Start the integrated app locally

```powershell
uv sync --locked --extra dev --extra ml
uv run --locked python scripts/local_stack.py up                 # rule scorer (default); add --scorer model for p1
uv run --locked python scripts/local_stack.py status
uv run --locked python scripts/local_stack.py smoke              # rule mode
# UI: in web/, npm ci; then set SENTINEL_API_ORIGIN=http://127.0.0.1:8000 and run npm run dev
uv run --locked python scripts/local_stack.py down
```

See `docs/runbooks/local-operations.md`. Model mode needs operator-provisioned account profiles (`python -m sentinel.cli provision-accounts`); otherwise ingestion returns 422.

## Verified on this branch (Windows 11, before the final commit)

Platform: Windows 11 Home 10.0.26300, CPython 3.11.3, uv 0.9.26, Node 22.13.1, PostgreSQL 14.17 disposable clusters. Settings: `SENTINEL_LIVE_CLAUDE=0`, `SENTINEL_INVESTIGATOR=deterministic`, no external test database, no model-provider calls.

| Check | Result |
| --- | --- |
| Focused combined CI/operator tests (C06 gate and package tests; C08 lifecycle, R28 startup, rollback drill, backup) | 37 passed, 108 s |
| `local_stack.py` model mode, on test-owned resources | `up --scorer model` (4 migrations, API up), `status` owned/owned; `/v1/scoring` model / `uncalibrated_score` / 4.0295386895426815e-06 / `hgb_balanced`; results route 200 (offline synthetic benchmark); unprovisioned ingest 422 `account_profile_missing`; `down` verified API and database stopped; `status` then exit 1. `api.log` contains the token 0 times and `postgresql://` 0 times. Owned directory removed after the verified stop. 56 s |
| `web/` `npm ci --offline` (existing lock) | exit 0, 167 packages |
| `npm run typecheck` | exit 0 |
| `npm test` | 44 passed (10 files) |
| `npm run build` | exit 0 |
| `npm run test:e2e`, unmodified (real browser, API and disposable Postgres; rule and registered model; expected failure-artifact scan; token retention and secret scan; identity-verified cleanup) | scanner self-test, 20 shutdown and 12 entry-point harness checks passed, then **19 passed** (2.8 min), exit 0. No recovery or secrets file remained, and the owned `stacks/` directory was empty |

The final-commit checks (six-command strict check, JUnit validation from that same run, HTTP contract export check, read-only ML reproduce) run after the commit; their results are reported with the final SHA.

## Limitations

- **Platforms.** Windows-local only. Linux, the GitHub Actions workflow, macOS, hosting and public BYOK were not executed. The POSIX operator path is untested.
- **Data.** Synthetic data and simulated actions only. Model scores are uncalibrated rankings from an offline synthetic benchmark. This makes no claim about real fraud-detection performance, alert volume, latency, throughput or memory at scale.
- **Operator.** Disclosed limits remain:
  - a non-atomic window between checking a PID and killing it;
  - Windows-specific detection of orphaned children;
  - no staleness or retraction policy for operator-provisioned profiles;
  - direct owner SQL bypasses the cooperative decision lock.
- **Open items.** The two low H01 browser-hardening suggestions remain open and not assigned. The strict checker's pytest step does not use the structured skip gate; CI and this release validation do.

## Remaining gates

1. Codex reviews this candidate.
2. The owner designates the main integrator and decides on main integration.
3. A real CI run needs a remote and runner, which is an owner action.
4. Hosting, staging and any public mode stay gated.
