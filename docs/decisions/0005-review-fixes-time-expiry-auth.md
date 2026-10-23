# 0005: Decision time, approval-expiry lifecycle and subscription-auth preflight

- Status: accepted; amends 0002 (time capture, expiry, scoring persistence) and 0003 (environment scrub)
- Date: 2026-10-23
- Decided by: project owner (requested fixes R1–R8 from Codex review Sentinel_Review_ed08de0); implemented by Claude Code

## Context

Codex's read-only review of ed08de0 reproduced several problems:

- **R1:** Foundry routing leaked through the environment scrub.
- **R2:** approval validity was judged with a time read before lock waits.
- **R3:** velocity features counted history unavailable at the recorded decision time.
- **R4:** replays skipped current authorization.
- **R5:** non-alert scores were lost on replay.
- **R6:** the body was fully buffered before the size check.
- **R7:** the concurrency test could pass with crashed callers.
- **R8:** an expired approval stranded its case.

## Decision

- **Time capture rule:** any time that decides validity, availability or an effect is read after the locks the decision depends on are held. This applies to execution (approval then case), investigation (case) and ingestion (the per-account lock).
- **Ingestion decision time:** ingestion takes a transaction-scoped advisory lock per (tenant, session, account), then reads `now`. Velocity counts events with `occurred_at` in `[t-1h, t)` and `ingested_at <= now`. Same-timestamp events are excluded regardless of arrival order. Decisions for one account are serialized; different accounts are unaffected.
- **Scoring outcomes:** every ingestion records a `ScoringOutcome` (new v1 contract, migration 0002) with score, threshold, alert flag, prior count, decision time and pinned artifacts. Replays return it unchanged and never recompute against later history or rules. Rows ingested before 0002 replay `rule_score: null`.
- **Replay authority:** an idempotent replay re-checks `require_execution_authority` (human, `execute_simulated_action`, same approver) against the current session, but not freshness (expiry, consumption, case state). A legitimate retry after expiry still returns the original action.
- **Expiry lifecycle:** when the current intent's approval has lapsed unused, the case moves `awaiting_approval -> open` at a new revision, with an `approval_expired` audit event (new v1 event type). This is detected lazily, by a denied execution or an investigation request (which returns `approval_expired` for the client to re-read). A fresh investigation creates a new intent at a newer revision that needs a new approval. The old approval is never revived: it stays bound to the superseded revision, and the guard rejects it.
- **Body limit:** reject a declared Content-Length over 16 KiB without reading. Otherwise stop consuming the stream as soon as it passes the limit.
- **Claude adapter:**
  - remove every `ANTHROPIC_*` and `CLAUDE_CODE_USE_*` variable plus `AWS_BEARER_TOKEN_BEDROCK` from the child environment;
  - before any model call, run `claude auth status --json` with the same environment and working directory, and require `loggedIn=true`, `authMethod=claude.ai` and `apiProvider=firstParty`, otherwise fail closed (`provider_unavailable`) with no model call;
  - add `--disable-slash-commands`.

  Guarantee, stated narrowly: the adapter sends a model request only when the CLI itself reports first-party claude.ai login in that environment. It does not prove which plan pool a request draws from.
- **Schema exports:** written and compared as exact LF bytes.

## Alternatives considered

- Recording `features_as_of` later without serializing: still races with concurrent commits.
- An approval-renewal endpoint that extends validity: it would revive a stale approval and bypass a fresh human decision.
- A terminal `expired` case state: it would discard a still-relevant alert; reopening keeps the case reviewable.
- An allowlist environment for the child: brittle on Windows (the OAuth credential lookup depends on profile variables); the auth-status preflight checks the outcome instead.

## Consequences

- Same-account ingestion is serialized, which is acceptable at prototype volume; revisit if one account needs high throughput.
- Lazy expiry means a lapsed case stays `awaiting_approval` until someone touches it. A sweeper can be added with the worker.
- The auth-status output schema is undocumented CLI output. If a CLI update changes it, the adapter fails closed rather than open.
