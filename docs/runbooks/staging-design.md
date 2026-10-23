# Restricted staging: design and gating (C08)

Audience: the owner and Codex, before any hosted provisioning. **This is a design, not a deployment.** Nothing has been provisioned, and hosting has not been selected. Provisioning is a later, explicitly instructed owner action.

## Goals and constraints

- **Who:** the owner and named testers only, until the public BYOK gate passes (PROJECT_PLAN G1/G4).
- **Investigator:** deterministic only. No owner model key or subscription credential in any deployment configuration. The `claude-cli` mode refuses non-local mode, and the deployment must never set `SENTINEL_MODE=local` or install a Claude login.
- **Data:** persistent Postgres; synthetic data only.
- **Budget:** existing subscriptions and free allowances only. Do not promise always-on availability from free tiers.

## Components

| Component | Requirement | Notes |
| --- | --- | --- |
| API | One FastAPI/uvicorn process; `SENTINEL_DATABASE_URL` from the platform secret store; `SENTINEL_INVESTIGATOR=deterministic` | Long investigations run in-request today; a serverless request timeout must exceed the run budget, or a worker is needed first |
| Database | Managed Postgres ≥ 14 with TLS, a least-privilege runtime role (C05) and a separate migration role | `migrate` runs as a one-off release step, never at every request |
| Sessions | Issued by an operator command, not an HTTP route (none exists) | Rotate on tester changes; tokens are stored as hashes |
| UI | Cursor's U01 build, served separately or behind the same origin | No broad CORS changes without a contract request |
| Backups | Platform backups plus the `pg_dump -Fc` procedure in local-operations.md | Restore drill before inviting testers |

## Must be verified from official sources before choosing hosting

Not yet checked; do not assume:
- the actual Vercel (or alternative) plan in use, function duration/memory limits, cold starts, regions, and whether a Python ASGI app is supported as deployed;
- the managed Postgres free-tier storage, connection limits, idle suspension and backup retention;
- egress, idle cost and overage behaviour, so that paid overage stays disabled.

Record the source URLs and dates in a decision record when hosting is chosen.

## Release checklist (for when provisioning is authorized)

1. Integrated `main` commit with CI green on a real runner (C06 is configured but not yet executed).
2. C05 least-privilege role applied; the runtime role cannot alter schema or drop the audit triggers.
3. Migrations applied by the migration role; `none pending` on a second run.
4. Synthetic smoke (`scripts/smoke_thin_path.py --base-url <staging>`) passes; Cursor's browser suite passes against staging.
5. Backup taken and a restore drill done into a scratch database.
6. Access limited to named testers; logs checked for absence of tokens and bodies.

## Explicitly out of scope here

Public BYOK, visitor key isolation, quotas and cost controls are a separate G4 gate. So is any always-on or SLA claim.
