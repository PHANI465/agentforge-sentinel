# AgentForge Sentinel

AgentForge Sentinel is a local financial investigation workbench. It scores
synthetic transactions, opens cases, records the investigation and its evidence,
and requires human approval before a simulated action.

## Try Sentinel online

[Open the public Vercel site](https://agentforge-sentinel.vercel.app/). You can review a PDF, workbook, or Word document, follow a recorded case or run a fresh synthetic case.

- [Review documents](https://agentforge-sentinel.vercel.app/#review). Review PDF, XLSX, or DOCX files, compare related records, or try the [sample library](https://agentforge-sentinel.vercel.app/examples.html).
- [Ask IAF](https://agentforge-sentinel.vercel.app/iaf.html) about the project and its creator. [OpenAI key setup](hosting/vercel/IAF.md).
- [Walk through a fraud case](https://agentforge-sentinel-walkthrough.engagingfoxglove1.chatgpt.site/walkthrough.html). Follow five plain language steps, or [explore all ten steps](https://agentforge-sentinel.vercel.app/walkthrough-details.html) with diagrams and recorded evidence.
- [Download the synthetic p1 dataset](https://agentforge-sentinel-walkthrough.engagingfoxglove1.chatgpt.site/dataset.html). Includes 82,819 generated transactions, 600 fictional accounts, labels, features and the manifest used to verify the snapshot.

The public site requires no account or API key. Start a [live workbench case](https://agentforge-sentinel.vercel.app/workbench) to try investigation and simulated execution. The 30 minute session contains only synthetic data. [Public release and checks](docs/releases/PUBLIC-SITE-VERCEL-2026-11-15.md)

## What you can run locally

- **Browser document insights.** Reconcile statement balances and compare linked
  invoices, orders, deliveries, and payments in the static site. Serve
  `public_site/static` to try the new examples and source viewer.
  [Document insights guide](docs/ui/PUBLIC-DOCUMENT-INSIGHTS.md)
- **Case investigation.** Use the rule scorer or opt into the registered ML
  scorer. Inspect evidence, review the investigation trace, and approve or
  reject a proposed simulated action.
- **Document Review.** An opt-in analyst session can upload synthetic or
  public CSV, XLSX, or PDF files for extraction and review. Configure the
  local worker and document grant first. [Worker setup](docs/security/DOC01-document-upload.md)
- **Reporting prototype.** AN01-M1 provides tools and tests for measuring
  report queries against synthetic PostgreSQL fixtures. The full-size
  measurements and the Reports screen are future work. [Benchmark notes](docs/benchmarks/AN01-M1.md)

## Run locally

Requires Python 3.11+, uv, Node 22+ and native PostgreSQL binaries. Run from the project root:

```powershell
uv sync --locked --extra dev --extra ml
$env:SENTINEL_LIVE_CLAUDE = '0'
uv run --locked python scripts/local_stack.py up
uv run --locked python scripts/local_stack.py status
```

In a second terminal:

```powershell
Set-Location web
npm ci
npm run dev
```

Open the URL printed by Vite. Copy the bearer token from
`.agent/stack/session.json` into the sign-in field. To create and verify
one synthetic case, run `uv run --locked python scripts/local_stack.py smoke`
from the project root and refresh the case queue. Stop Vite with Ctrl+C,
then run `uv run --locked python scripts/local_stack.py down` to stop the
API and database.

The default rule scorer and deterministic investigator need no model key.
Model mode (`up --scorer model`) requires operator-provisioned account
profiles. [Setup and checks](SETUP.md) · [Operator runbook](docs/runbooks/local-operations.md) · [HTTP API](docs/api/README.md)

## Verification and project guide

The AN01-M1 integration passed 1,099 backend tests on Windows and 1,103 on
Ubuntu in WSL, with one allowed live-provider skip each. The Document Review
integration passed 266 frontend tests and 41 Windows Chromium cases. The
recorded walkthrough passed 31 local browser checks. [AN01-M1 release](docs/releases/AN01-M1-main-integration-2026-11-14.md) · [Document Review release](docs/releases/DOC01-Part-C-main-integration-2026-11-14.md) · [Walkthrough release](docs/releases/DEMO01-public-walkthrough-2026-11-14.md)

Sentinel uses synthetic transactions and simulated actions. The verification
covers the local workflow and the hosted synthetic demo. Live provider quality
evaluation remains future work.

[Complete guide](docs/artifacts/AgentForge_Sentinel_Complete_Project_Study_Guide_2026-11-08.md) · [Offline HTML](docs/artifacts/AgentForge_Sentinel_Complete_Project_Study_Guide_2026-11-08.html) · [Current status](docs/STATUS.md) · [Contributor and assistant handoff](docs/START_HERE.md)
