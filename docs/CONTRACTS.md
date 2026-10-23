# Draft v1 domain contracts

The contracts define eight persisted/read models: Transaction, Alert, EvidenceItem, Case, AgentRun, Approval, SimulatedAction and AuditEvent. Narrow untrusted request DTOs deliberately omit server authority: TransactionInput, InvestigationRequestInput, ApprovalDecisionInput and ExecuteActionInput. ActionIntent binds proposed action content. InvestigationFinding is untrusted agent output. JSON Schema exports (14) live in contracts/v1; the synthetic transaction example is in contracts/examples.

The contracts are still draft. Since the thin-path increment (decision 0002), a Postgres/FastAPI boundary uses them: see "Storage/service boundary" below. No schema grants authorization. Server code builds TrustedContext only from a bearer-token lookup and resolves every identifier under that scope. It never deserializes TrustedContext from a public/model payload.

## Values and time

- Monetary values are positive integer magnitudes in minor units. Direction is separate. v1 supports USD/INR/GBP with exponent 2 and JPY with exponent 0. The cap is 9,000,000,000,000 minor units, within JavaScript safe-integer range; aggregate arithmetic still needs independent overflow/precision care. Floats, bools, strings and unsupported currency precision are rejected.
- Timestamps accept aware Python datetime objects or RFC3339 strings with up to six fractional digits. Numeric Unix timestamps and numeric strings are rejected. Output is normalized to UTC. v1 rejects future transaction event time at ingestion instead of silently allowing unspecified clock skew.
- Event/observation time and ingestion/availability time are distinct. Evidence must be available by the decision time, and the supplied current case snapshot cannot be from the future. Same-timestamp historical feature ordering and delayed-label training rules still need the data-pipeline implementation.
- Fraud truth/labels and credentials are absent from decision-time transaction DTOs. Unknown fields are rejected. Public errors must use the safe code-only formatter; raw ValidationError.errors(), provider exceptions, input bodies and traces must not be logged wholesale.

## Identity, evidence and approvals

All references need service/database resolution under tenant AND session ownership. UUID shape, a model's role field and a content hash do not prove identity, permissions, source authenticity or claim support.

Evidence content hashing excludes the hash field itself, includes provenance/scope/time/facts, and sorts uniquely named facts. The complete snapshot hash sorts evidence IDs and content hashes. Pure guards verify per-item content, the complete referenced set, decision-time availability and the case's pinned snapshot. Case updates must increment revision; storage enforcement is pending.

Action-intent canonicalization is versioned as sentinel.action-intent.v1. It hashes sorted compact JSON with the full typed intent, including identity scope, case/revision, exact parameters, evidence snapshot and policy artifact. There are no float values in the action-intent document. The approval guard requires the exact stored intent digest, approved/unconsumed state, a currently valid interval, the expected human actor, execution capability, matching case state/revision and an independently supplied active policy. The current case snapshot must precede the approval.

The prototype pure guard intentionally limits execution to the approving human within the same session. A later background-worker service identity needs a separate explicit authorization design.

## Agent output

InvestigationFinding selects `operation` (simulated_hold | escalate) and `reason_code` from enums, plus a rationale of at most 600 characters. Extra fields are rejected. The rationale is display text only. The server, not the agent, builds the ActionIntent: the transaction id and hold amount come from stored records, and the case revision, evidence snapshot and policy come from the case. Additions in this increment: InvestigationFinding, InvestigationRequestInput, ExecuteActionInput, and the `ingest_transaction` TrustedContext capability (TrustedContext is not exported).

## Storage/service boundary (thin path, decision 0002)

Implemented and tested against real Postgres:
- Bearer-token sessions: only token SHA-256 is stored. Context comes from the lookup; tenant AND session filters apply to every query. Foreign and missing records both return `not_found`.
- Ingestion idempotency on `(tenant, session, external_id)`: an identical payload replays the original; a different payload returns `idempotency_conflict`. Future event time is rejected.
- Rule score with pinned scorer/feature/threshold artifacts. Velocity counts prior transactions in `[t-1h, t)` within the same scope (same-timestamp transactions are excluded).
- Case transitions are compare-and-set on revision and state: open(1) -> investigating(2) -> awaiting_approval(3) -> closed(4). A failed run reopens the case. A lost run is reopened after timeout + 30 s.
- Full evidence snapshot verification before investigation. The case's agent-config pin must match the running investigator (`stale_agent_config`).
- Approval: human with `approve_action`, one per intent, 5-minute validity, exact intent digest. Rejection closes the case.
- Execution: row-locked approval, unique `(tenant, idempotency_key)`, the pure guard, atomic consume + simulated action + case close + audit. A retried identical key returns the original. Key reuse for another approval returns `idempotency_conflict`. Denials are audited as `action_denied`.
- Audit is append-only for application roles via triggers. It is not tamper-proof.

Still required:
- Signed browser approval tokens if a UI uses them; the SHA binding is not a signature.
- Transaction-level audit for transactions that raise no case (AuditEvent.case_id is required in v1).
- Audit retention policy, a least-privilege database role and connection pooling.
- A durable worker for long investigations, and a separate service identity for background execution.
- Freeze v1 only after the UI consumes these contracts.

## Verification

Run uv sync --locked --extra dev, then the commands in SETUP.md. Lockfile versions determine JSON Schema output; regenerated exports must be reviewed when dependencies or contracts change. A small Node check verifies fixture transport and money bounds, not complete frontend type generation. JSON Schema compatibility is not equivalent to semantic backward compatibility; freeze v1 after API/storage integration and evolve through reviewed versioned changes.
