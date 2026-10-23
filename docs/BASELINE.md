# Initial baseline on October 23 2026

Project path: E:\PHANI\agentforge-sentinel. This is the new Sentinel project, separate from the original AgentForge checkout.

Verified without reading credentials:
- Installed Python: 3.11.3.
- Node: 22.13.1.
- uv: 0.9.26.
- Git, Docker client, Claude, Codex and Cursor command entry points are present.
- Ollama was not found on PATH. This does not prove it is not installed elsewhere.
- The project initially contained only the adopted handoff kit and had no .git directory.

Hardware inventory through Windows CIM was unavailable in the sandbox. RAM, GPU/VRAM, local-model speed and Docker daemon/Postgres availability remain unverified. No zero/empty hardware fallback was treated as a measurement. CLI subscription login, exact plan allowances, provider keys, hosting plan and live inference remain unverified. No paid service or model request was activated.

The global Python already had Pydantic 2.7.1 and pytest 8.3.5. Initial compatibility probes passed there. Project development uses an isolated uv environment and uv.lock instead of depending on those global packages. The locked environment resolved Pydantic 2.14.1, pytest 8.4.2 and Ruff 0.17.2; exact transitive versions/hashes are in uv.lock.

## Source provenance

A separate read-only review located the full original source at E:\PHANI\Main Project ( AgentForce ), with Force in the folder name. The similarly named AgentForge folder is a small unversioned overlay, not the full runtime.

Pinned full-source commit: 1003a5ef815a859efcd2402ea3256bc1af7d7cdd, branch main. Tracked/untracked state was clean at review; ignored files were excluded. MIT license, copyright 2026 Phaneendra Gavara.

No upstream implementation was copied into the initial Sentinel contracts. The source review identified envelope/identifier/tracing conventions for future bounded reuse. Before copying source, record the exact files/commit and preserve required notices. Do not import the entire common package to reuse small transport types.

Source project tests were not run. Earlier reported pass counts are not reproduced by this baseline. Current source runtime defaults, auth/key handling, safety policy, deployment configuration and unrestricted trace dictionaries are not inherited.

## Thin-path increment measurements (October 23 2026, Claude Code)

- PostgreSQL 14.17 binaries at C:\Program Files\PostgreSQLin. initdb/pg_ctl create and start a disposable trust-auth cluster on 127.0.0.1 under the user account. No server answered on localhost:5432. A separate pre-existing postgres process tree (likely a Windows service; a PostgreSQL data folder exists without a bin folder) was observed and left untouched; its credentials were not read.
- The Docker client is present, but the daemon was not running (named pipe missing).
- Claude Code 2.1.224. The npm `claude.cmd` shim launches the native node_modules\@anthropic-ai\claude-codein\claude.exe. A headless `claude -p` call with no tools and API-key variables removed completed in about 7 seconds (live smoke test) and through the API (live investigation). The exact subscription plan and remaining quota were not inspected.
- Git 2.47.1. Global user name/email are configured and were not changed. `init.defaultBranch` is unset; the repo was initialized with `-b main`.
- New locked runtime dependencies: FastAPI 0.143.0, Starlette 1.7.0, psycopg 3.3.6 (binary), uvicorn 0.54.0; dev: httpx 0.28.1. FastAPI, Starlette and certifi are age-limited to releases before 2026-10-09 via `[tool.uv] exclude-newer-package`, because the newest releases were days old. Pydantic stays at 2.14.1, so the existing schema exports are byte-identical.

## Next baseline checks

Measure hardware and a local-model benchmark in the authorized user environment, reproduce selected upstream tests in isolation, confirm Docker/Postgres readiness, choose one supported local live-model integration, and verify hosting/quota settings before deployment. These unknowns do not prevent pure contract work, but G0 is not complete until its documented exit checks pass.
