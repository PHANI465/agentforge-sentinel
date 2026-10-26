# AgentForge Sentinel development setup

Open E:\PHANI\agentforge-sentinel as the project root. It is a Git repository (default branch `main`); work happens on `task/<slug>` branches (see docs/decisions/0004).

## Install and verify

Requires Python 3.11+, uv, Git, Node 22+ (small transport check) and local PostgreSQL binaries (`initdb`/`pg_ctl`, tested with 14.17). The tests start their own disposable cluster on 127.0.0.1 with no stored credentials. If initdb is not on PATH or in a standard install location, set SENTINEL_PG_BIN to its bin folder, or set SENTINEL_TEST_DATABASE_URL to an admin URL of a server you control. Without either, the database tests are skipped with a visible reason.

```powershell
uv sync --locked --extra dev
uv run --locked python -m ruff check .
uv run --locked python -m pytest -q
uv run --locked python -m unittest discover -s tests_handoff -v
uv run --locked python scripts/export_contracts.py --check
node scripts/check_contract_examples.mjs
uv run --locked python scripts/check_package.py   # wheel/sdist ship the migrations (docs/ci/README.md)
```

All of these run locally without model keys or paid services. One opt-in live test uses your logged-in Claude subscription (a single small call):

```powershell
$env:SENTINEL_LIVE_CLAUDE = "1"; uv run --locked python -m pytest -q tests/test_investigators.py -k live
```

Regenerate draft schema exports after intentional contract/dependency changes with `uv run --locked python scripts/export_contracts.py`, then review the diff. The HTTP v1 contract (OpenAPI + examples, docs/api/README.md) is regenerated with `uv run --locked python scripts/export_http_contract.py` (needs local Postgres binaries); pytest fails if it drifts.

## Run the thin path locally

```powershell
uv run --locked python -m sentinel.cli devdb start          # prints SENTINEL_DATABASE_URL; data under .agent/devdb
$env:SENTINEL_DATABASE_URL = "postgresql://sentinel@127.0.0.1:55432/postgres"
uv run --locked python -m sentinel.cli migrate
uv run --locked python -m sentinel.cli create-session        # prints token=... once; keep it out of files you commit
$env:SENTINEL_INVESTIGATOR = "claude-cli"                    # optional; default is the deterministic investigator
uv run --locked uvicorn sentinel.api:create_app --factory --host 127.0.0.1 --port 8000
```

In a second terminal, with `$env:SENTINEL_TOKEN` set to the printed token:

```powershell
uv run --locked python scripts/smoke_thin_path.py investigate        # prints CASE_ID=...
# optionally restart the server (and devdb) here
uv run --locked python scripts/smoke_thin_path.py execute <CASE_ID>
uv run --locked python -m sentinel.cli devdb stop
```

Endpoints: `POST /v1/transactions`, `GET /v1/cases/{id}`, `GET /v1/cases/{id}/audit`, `POST /v1/cases/{id}/investigations`, `POST /v1/approvals`, `POST /v1/actions`, `GET /healthz`.

Investigator modes (decision 0003): `deterministic` (default, no AI) or `claude-cli` (local only; refused unless `SENTINEL_MODE=local`, which is the default). The Claude mode removes every `ANTHROPIC_*`/`CLAUDE_CODE_USE_*` variable, then requires `claude auth status` to report first-party claude.ai login before any model call. Otherwise it fails closed (decision 0005). Switching modes makes cases created under the other mode fail investigation with `stale_agent_config`.

## Coordination

AGENTS.md is the shared instruction source; CLAUDE.md imports it. Codex and Claude Code stay in sync through Git: one branch and handoff note per task, separate worktrees for parallel work, and one integrator who merges to `main` and reruns checks. See docs/decisions/0004.

Briefing: `uv run --locked python scripts/agent_status.py`. Startup hooks remain disabled.

The strict helper, `uv run --locked python scripts/agent_check.py`, records full-commit evidence only on a clean, committed tree. No remote, push or deployment is configured.

## Scope

See docs/CONTRACTS.md for contract and storage semantics, docs/BASELINE.md for measured facts/unknowns, and docs/STATUS.md for the next milestone. Scores are rule heuristics, not trained-model probabilities. Actions are simulated records only. All data is synthetic.
