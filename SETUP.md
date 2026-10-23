# AgentForge Sentinel development setup

Open E:\PHANI\agentforge-sentinel as the project root. The adopted handoff kit now has an initial Python contracts package; the application API, database and UI are the next increment.

## Install and verify

Requires Python 3.11+, uv, Git for helper tests, and Node 22+ for the small transport check. Development dependencies install into this folder's .venv; no global Python packages need changing.

```powershell
uv sync --locked --extra dev
uv run --locked python -m ruff check .
uv run --locked python -m pytest -q
uv run --locked python -m unittest discover -s tests_handoff -v
uv run --locked python scripts/export_contracts.py --check
node scripts/check_contract_examples.mjs
```

All checks run locally without model keys or paid services. Regenerate draft schema exports after intentional model/dependency changes with uv run --locked python scripts/export_contracts.py, then review the diff.

## Coordination

AGENTS.md is the shared instruction source; CLAUDE.md imports it. Start with one implementation lead until contracts and the first complete path stabilize. Use separate worktrees for later parallel tasks and one integrator for shared contracts/migrations.

Briefing: uv run --locked python scripts/agent_status.py. Startup hooks remain disabled; installed-tool hook loading has not been verified.

The strict helper, uv run --locked python scripts/agent_check.py, records full-commit evidence only on a clean, committed Git tree. Manual checks can verify an initial uncommitted increment without claiming a clean-commit PASS. Do not create a commit merely to manufacture that status. No repository remote, commit, push or deployment is configured by these instructions.

## Initial implementation

See docs/CONTRACTS.md for contract semantics, docs/BASELINE.md for measured facts/unknowns, and docs/STATUS.md for the next milestone. The current code does not call a model or perform financial actions. All examples are synthetic.
