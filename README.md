# AgentForge Sentinel

A fraud investigation workbench being built incrementally: transactions, risk scoring, bounded agent investigations, analyst review, approved simulated actions and an audit history.

The first implementation provides draft versioned domain contracts and precondition guards. It includes eight persisted/read models, narrow untrusted request DTOs, deterministic evidence/action bindings, JSON Schema exports and acceptance tests. All example data is synthetic.

Start with [setup](SETUP.md), [current status](docs/STATUS.md), [contract semantics](docs/CONTRACTS.md) and [the full milestone roadmap](docs/PROJECT_PLAN.md).

The next increment adds the persistent API path from transaction through rule score, investigation, human approval and simulated action. Trained fraud models, live model integration, the analyst UI and hosted public BYOK remain later acceptance gates.
