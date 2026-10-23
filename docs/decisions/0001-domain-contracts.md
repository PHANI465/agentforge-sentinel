# 0001 Domain contracts before application integration

- Status: accepted implementation choice for this initial increment; contracts remain draft
- Date: 2026-10-23
- Basis: the user's milestone plan and adopted AGENTS.md

Use a small Python package with Pydantic v2, versioned JSON Schema exports and explicit request/read-model separation. Start with exact minor-unit money, UTC availability times, bounded values, pinned artifacts and typed action intents. Pure guards enforce deterministic snapshot and approval preconditions.

Keep the Python/AgentForge architecture selected in the project plan. No agent runtime/framework or model provider is added by this increment. The new package is independently implemented and does not import the original runtime/auth/configuration stack.

The initial local environment and a Node transport check make contracts reviewable before API, storage and UI work proceed. Database authorization, concurrency, audit durability and real inference require separate implementations and acceptance evidence. A hash binds content; it does not authenticate a source or authorize an action.
