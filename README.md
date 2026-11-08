# AgentForge Sentinel

A local financial investigation workbench: synthetic transactions, temporal rule/trained
ML scoring, bounded agent investigation, human approval, explicit simulated actions and
an auditable trace. It connects to no bank account and moves no real money.

**Start here:** [complete guide](docs/artifacts/AgentForge_Sentinel_Complete_Project_Study_Guide_2026-11-08.md),
[offline HTML](docs/artifacts/AgentForge_Sentinel_Complete_Project_Study_Guide_2026-11-08.html),
[decision ledger](docs/decisions/PROJECT_DECISION_LEDGER.md) and
[current status](docs/STATUS.md). New assistant chats read [START_HERE](docs/START_HERE.md).

Accepted application/tooling is the tested 871e31d release plus documentation: independent
Windows/native Ubuntu backend gates passed 810 + one allowed skip each. Earlier Windows
UI evidence is 133 unit and 19 legacy + 10 trace browser cases, not rerun for later tooling.
See [release evidence](docs/releases/Batch-r2-main-integration-2026-11-07.md).

AN01-M1 corrected prototype5e0a578 still needs R54/R56 follow-up; R53/R55/R57 close
for the scoped review. It is not accepted or integrated. See the [review](docs/reviews/AN01-M1-5e0a578.md). The downloaded ULB public dataset is a separate future
benchmark; p1 is unchanged. Local document feedback, automated development grading and
more readable metrics are [planned slices](docs/research/2026-11-08-expansion-research.md),
not shipped functionality. Current scores are uncalibrated synthetic-benchmark rankings.

This repository is private. GitHub lists PHANI465 as the sole contributor. Actions are
disabled pending verified included budget and explicit CI dispatch. Real CI, Linux browser,
macOS and hosted/public deployment remain unverified. Raw datasets, credentials and local
evidence are excluded; download/source manifests provide provenance without redistribution.

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
