# AgentForge Sentinel setup

The canonical project is E:/PHANI/agentforge-sentinel on main after the October 26 integration. Use new task branches/worktrees for later work; preserve reviewed component checkouts. Main combines the accepted I03 application, reviewed N2-N7 Linux-readiness changes and current coordination. Accepted G3B adds bounded three-role orchestration and migration 0005. G3C adds the read-only investigation trace API and analyst panel; see docs/releases/G3C-main-integration-2026-11-02.md for passing combined verification evidence and limits.

## Requirements and install

Use Python 3.11+, uv, Git, Node 22+ and native PostgreSQL binaries (initdb, pg_ctl, pg_dump and pg_restore; tested on Windows with PostgreSQL 14.17 and native Ubuntu WSL with PostgreSQL 16.15). Set SENTINEL_PG_BIN if necessary. Docker is not required. The native Linux backend uses an unprivileged user; run initdb/tests as that user. GitHub Actions/macOS and Linux browser execution remain unverified. See [Linux setup/results](docs/ci/WSL_SETUP_RESULTS.md) and [portability notes](docs/ci/LINUX.md); the separate operator orphan limitations remain.

```powershell
uv sync --locked --extra dev --extra ml
$env:SENTINEL_LIVE_CLAUDE = '0'
$env:SENTINEL_INVESTIGATOR = 'deterministic'
```

The ml extra is required for the complete test suite and packaged model even when the default scorer is rule. Tests use disposable local Postgres. Leave SENTINEL_TEST_DATABASE_URL unset for ordinary development; if required database coverage is skipped, the structured CI gate rejects that run.

## Run the app

```powershell
uv run --locked python scripts/local_stack.py up
uv run --locked python scripts/local_stack.py status
```

The default is the rule scorer and deterministic investigator. Private local session details are in `.agent/stack/session.json`; read its token locally and enter it into the analyst UI. Do not put it in a URL, commit, screenshot or public log. The API uses a restricted runtime role; migrations/session provisioning use operator authority.

In a second terminal:

```powershell
Set-Location web
npm ci
$env:SENTINEL_API_ORIGIN = 'http://127.0.0.1:8000'
npm run dev
```

Use the URL Vite prints. In the project root, `uv run --locked python scripts/local_stack.py smoke` verifies one synthetic rule case through investigation, approval and simulated execution. The UI starts empty on a new database until transactions/cases are created. `uv run --locked python scripts/local_stack.py down` verifies shutdown and keeps database data. See the [operator runbook](docs/runbooks/local-operations.md) for model mode, profiles/disclosures, ownership/recovery, backup and rollback.

## Required checks

On a clean committed tree, the strict gate runs six commands including the complete backend suite and clean package/install check:

```powershell
uv run --locked python scripts/agent_check.py
uv run --locked python scripts/export_http_contract.py --check
uv run --locked python -m ml test --reproduce
```

The strict helper has a 2700-second bound per command and records ignored evidence in `.agent/last-check.json`. An old report or one from another checkout does not certify current HEAD. HTTP checks cover frozen v1/v1.1/v1.2 and active v1.3/examples. ML reproduction is the accepted read-only comparison; do not rerun model selection or tune against frozen p1 test data.

For CI-equivalent structured test validation, `uv run --locked python scripts/ci_test_gate.py --junit .agent/pytest-results.xml` runs the full suite and permits exactly the opt-in live-Claude skip. During final integration, use a JUnit report from the strict gate's same pytest run and `--validate-only PATH` to avoid a duplicate full run. Current CI setup and package details are in [docs/ci](docs/ci/README.md).

From web/ run:

```powershell
npm run typecheck
npm test
npm run build
npm run test:e2e
npm run test:e2e:trace
```

The original 19-case browser suite and separate 10-case trace suite use real disposable API/Postgres stacks and the deterministic investigator, including registered-model cases, restart/replay, authorization, secret scanning and identity-verified cleanup. It does not use a model subscription or external database. Keep recovery files if teardown cannot be confirmed; never kill by process name.

## Local live AI and project workflow

The deterministic investigator is the default. The opt-in claude-cli adapter uses a local first-party subscription login and is forbidden in public mode. It is not required for ordinary checks; leave SENTINEL_LIVE_CLAUDE=0 unless explicitly testing that mode. See decisions/0003 and decisions/0005 plus [API/security documentation](docs/security/README.md).

AGENTS.md is shared by Codex/Claude/Cursor, and CLAUDE.md imports it. New commits must be solely authored and committed by PHANI465 <pgavara1@asu.edu>, without AI co-author/session trailers. Existing history is preserved. Codex is the owner-designated integrator for this main consolidation. No remote, push, deployment, new spend or public provider-key bridge is part of this release.
