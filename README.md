# AgentForge Sentinel

A local fraud investigation workbench using synthetic financial transactions, rule or trained-model scoring, evidence review, bounded investigation, human approval, simulated actions and an audit trail.

The consolidated Windows-local codebase includes the React/TypeScript analyst UI, FastAPI/PostgreSQL API, reproducible scikit-learn baseline and model reports, persisted approval/replay workflow, operator backup/rollback tooling and backend CI configuration. The tested G3C foundation (`f788698`) includes: the trace API/UI and monotonic workflow deadlines on the accepted I03 and native Linux backend foundation. See the [G3C foundation](docs/releases/G3C-main-integration-2026-11-02.md) for exact platform verification records. GitHub Actions, macOS, Linux browser and hosted/public access are not verified. Model scores are uncalibrated rankings from a synthetic benchmark.

G3D-P3 three-role operator selection is independently accepted and integrated at
`495c7d3`: Windows then native Ubuntu backend gates pass666+one allowed skip, six commands,
same-run JUnit/HTTP/package/ML. The helper preserves explicit adapter/model settings across
restart, with deterministic defaults and human approval/replay boundaries. G3D-P2's
populated workflow backup proof remains integrated. No frontend/browser rerun for this
helper/tests/docs change; prior UI133/browser19+10 stay dated. The45-minute cap applies
only to verification commands, not application deadlines. See the
[current checkpoint](docs/artifacts/AgentForge_Sentinel_Session_2026-11-06.md) and
[release record](docs/releases/G3D-P3-main-integration-2026-11-06.md).
Study the [complete project guide](docs/artifacts/AgentForge_Sentinel_Complete_Project_Study_Guide_2026-11-02.md).

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

- [Current local release](docs/releases/G3D-P3-main-integration-2026-11-06.md): integrated references, verification commands and limits.
- [Current status](docs/STATUS.md), [task queue](docs/TASK_QUEUE.md) and [roadmap](docs/PROJECT_PLAN.md): accepted scope and remaining milestones.
- [Project artifacts](docs/artifacts/README.md): saved HTML, Word and Markdown checkpoints.
- [Setup and checks](SETUP.md): locked dev+ml, strict/package/contract checks and real browser/API/Postgres tests.

The rule scorer and deterministic investigator need no model key. The optional local Claude adapter is separate from hosted inference. Bounded evidence-analyst/investigator/reviewer orchestration is integrated; its read-only investigation trace UI is integrated, while measured live quality comparison remains next. Public visitor keys, deeper financial analytics, broader AI attack evaluations and hosted operation remain future work; native Linux coverage is currently the local backend scope. All actions are simulated; there is no real-bank fraud-performance or production-capacity claim.
