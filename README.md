# AgentForge Sentinel

A local fraud investigation workbench using synthetic financial transactions, rule or trained-model scoring, evidence review, bounded investigation, human approval, simulated actions and an audit trail.

The consolidated Windows-local codebase includes the React/TypeScript analyst UI, FastAPI/PostgreSQL API, reproducible scikit-learn baseline and model reports, persisted approval/replay workflow, operator backup/rollback tooling and backend CI configuration. Main combines I03 `4fff776` with accepted N2-N7 native Linux backend portability/recovery changes. See the [current integration](docs/releases/MAIN-linux-readiness-2026-10-26.md) for exact platform verification records. GitHub Actions, macOS, Linux browser and hosted/public access are not verified. Model scores are uncalibrated rankings from a synthetic benchmark.

## Run locally

Requires Python 3.11+, uv, Node 22+ and native PostgreSQL binaries. Run from the project root:

```powershell
uv sync --locked --extra dev --extra ml
$env:SENTINEL_INVESTIGATOR = 'deterministic'
uv run --locked python scripts/local_stack.py up
uv run --locked python scripts/local_stack.py status
```

In a second terminal:

```powershell
Set-Location web
npm ci
npm run dev
```

The UI proxies API requests to `http://127.0.0.1:8000`. Read your local bearer token from `.agent/stack/session.json` and enter it in the UI; keep it private. The UI holds it in memory only. A new database starts with no cases. To verify the synthetic rule workflow, run `uv run --locked python scripts/local_stack.py smoke` from the project root. Stop the owned API/database with `uv run --locked python scripts/local_stack.py down`.

Model mode is explicit (`up --scorer model`) and requires operator-provisioned account profiles. See [setup](SETUP.md), the [operator runbook](docs/runbooks/local-operations.md), [API documentation](docs/api/README.md) and [browser fixture guide](docs/api/model-browser-fixtures.md).

## Verify and understand the project

- [Current local release](docs/releases/MAIN-local-release.md): integrated references, verification commands and limits.
- [Current status](docs/STATUS.md), [task queue](docs/TASK_QUEUE.md) and [roadmap](docs/PROJECT_PLAN.md): accepted scope and remaining milestones.
- [Project artifacts](docs/artifacts/README.md): saved HTML, Word and Markdown checkpoints.
- [Setup and checks](SETUP.md): locked dev+ml, strict/package/contract checks and real browser/API/Postgres tests.

The rule scorer and deterministic investigator need no model key. The optional local Claude adapter is separate from hosted inference. Public visitor keys, bounded multi-agent orchestration, deeper financial analytics, AI attack evaluations and hosted operation remain future work; native Linux coverage is currently the local backend scope. All actions are simulated; there is no real-bank fraud-performance or production-capacity claim.
