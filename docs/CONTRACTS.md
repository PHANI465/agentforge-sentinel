# Draft v1 domain contracts

The initial implementation defines eight persisted/read models: Transaction, Alert, EvidenceItem, Case, AgentRun, Approval, SimulatedAction and AuditEvent. Narrow TransactionInput and ApprovalDecisionInput request DTOs deliberately omit server authority. ActionIntent binds proposed action content. JSON Schema exports live in contracts/v1; the synthetic transaction example is in contracts/examples.

These are draft contracts and pure precondition checks. HTTP authentication, database migrations/constraints, durable orchestration and simulated effects are the next increment. No schema grants authorization. Server code must build TrustedContext from authenticated identity, resolve every identifier under that scope and never deserialize it from a public/model payload.

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

## Work still required at the storage/service boundary

- Authenticate identity and load active policy and current records from trusted storage.
- Resolve and verify the full evidence snapshot before presenting an investigation/action.
- Prevent invalid transitions with compare-and-set case revisions.
- Atomically consume an approval, enforce unique idempotency, record a simulated effect and append audit evidence. Retried identical intents return the original result; conflicting key reuse fails.
- Enforce append-only audit behavior and retention; do not claim tamper-proof records.
- Sign/verify browser approval tokens if used; the current SHA binding is not a signature.
- Add Postgres migrations and cross-session/concurrent/restart tests. Pure contract tests do not establish these properties.

## Verification

Run uv sync --locked --extra dev, then the commands in SETUP.md. Lockfile versions determine JSON Schema output; regenerated exports must be reviewed when dependencies or contracts change. A small Node check verifies fixture transport and money bounds, not complete frontend type generation. JSON Schema compatibility is not equivalent to semantic backward compatibility; freeze v1 after API/storage integration and evolve through reviewed versioned changes.
