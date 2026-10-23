# AgentForge Sentinel

A fraud investigation workbench being built incrementally: transactions, risk scoring, bounded agent investigations, analyst review, approved simulated actions and an audit history.

Current state: draft versioned domain contracts plus a thin integrated API path on Postgres. A synthetic transaction is rule-scored and raises an alert and case. One bounded investigation (deterministic, or opt-in local Claude via the owner's CLI login) proposes an enumerated action. The server builds the exact action intent; a human approves it; a simulated action is recorded once, idempotently. Every step is audited, and the path survives server and database restarts. All data is synthetic.

Start with [setup](SETUP.md), [current status](docs/STATUS.md), [contract semantics](docs/CONTRACTS.md) and [the full milestone roadmap](docs/PROJECT_PLAN.md).

Not yet built: the analyst UI, hosted staging, a trained fraud model and public BYOK. These remain later acceptance gates.
