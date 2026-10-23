# 0002: Postgres + FastAPI thin path with database-enforced invariants

- Status: accepted for the G1 thin path; contracts remain draft v1
- Date: 2026-10-23
- Decided by: project owner (requested the STATUS "immediate implementation target"); implemented by Claude Code

## Context

STATUS.md's next target was a restart-safe path: synthetic transaction -> rule score -> alert -> investigation -> human approval -> simulated action -> audit, with server-built identity, full evidence verification, compare-and-set revisions and atomic approval/idempotency. The budget allows no paid services. Docker was not running; PostgreSQL 14.17 binaries were installed locally.

## Decision

- **Storage:** PostgreSQL via psycopg 3, plain numbered SQL migrations (`src/sentinel/db/migrations`) applied under an advisory lock and recorded in `schema_migrations`. No ORM. Each row stores the validated v1 contract as `body jsonb`, plus key columns for constraints and lookups.
- **Invariants in the database:** unique `(tenant, session, external_id)` for ingestion idempotency; one approval per intent; one action per approval; unique `(tenant, idempotency_key)`; at most one running agent run per case; append-only `audit_events` enforced by triggers on UPDATE/DELETE/TRUNCATE.
- **Concurrency:** case transitions are compare-and-set on `(revision, state)`. Execution locks the approval row (`FOR UPDATE`), checks the idempotency key, runs the pure `require_executable_approval` guard, consumes with `WHERE consumed_at IS NULL`, then inserts the action, closes the case and appends audit in one transaction. Denials are audited in a separate transaction.
- **Identity:** random bearer tokens issued by `sentinel.cli create-session`. Only SHA-256 digests are stored. `TrustedContext` is built solely from that lookup. Every query filters on tenant AND session; foreign and missing records both return `not_found`.
- **Investigation:** two transactions around the investigator call (claim `open -> investigating`; then finish). A run older than its budget timeout plus 30 seconds is presumed lost and reopened on the next request (`investigation_recovered`). The investigator returns only an enumerated `InvestigationFinding`. The server builds the `ActionIntent` from stored records.
- **HTTP:** FastAPI. Bodies are validated by the handler with code-only errors (`safe_validation_errors`). FastAPI's default validation response is replaced because it echoes input.
- **Tests:** a disposable `initdb` cluster per test run (trust auth on 127.0.0.1, no stored credentials), with a migrated template database cloned per test. `SENTINEL_TEST_DATABASE_URL` can point at another server.

## Alternatives considered

- SQLAlchemy/Alembic: more machinery than eight tables need now; can be adopted later if migrations multiply.
- SQLite for tests: does not exercise row locks, partial unique indexes or the triggers this path depends on.
- Docker Postgres: the daemon was not running; native binaries avoid a new dependency.
- A queue/worker for investigations: deferred. Synchronous two-transaction handling plus stale-run recovery meets the restart target with less machinery.

## Consequences

- Tests require local PostgreSQL binaries (or a test URL). Without them the database tests are skipped with a visible reason, not passed.
- Audit immutability is enforced only for application roles. A database owner can drop the triggers, so this is not tamper-proof.
- Under-threshold transactions create no case, so no audit event: `AuditEvent.case_id` is required in v1. Revisit if transaction-level audit is needed.
- The prototype requires the approving human to execute in the same session (inherited from the pure guard). A worker identity needs its own authorization design.
