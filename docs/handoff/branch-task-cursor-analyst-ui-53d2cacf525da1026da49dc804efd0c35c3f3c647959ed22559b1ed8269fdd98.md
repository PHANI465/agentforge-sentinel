# Handoff: task/cursor-analyst-ui

- Task and acceptance criteria: U01 analyst workbench in `web/` and `docs/ui/`. Typed client, in-memory session, queue, overview, case detail, evidence, audit, approve/reject, separate execute, one idempotency key across an ambiguous retry, 409 refresh, and safe non-JSON failures. U02 waits for accepted C02. U03 waits for accepted C07.
- Tool and worktree: Cursor, `E:\PHANI\sentinel-wt\cursor-analyst-ui`.
- Updated: October 23, 2026, UTC-7.
- State: ready for review. U01 is implemented. U02 and U03 are not started.
- Code reference tested before this note: merge `ed61cc99dfaf754c1b085ffcbb46b9bda7e027fd` plus the uncommitted `web/` and `docs/ui/` changes. Planning commit `b3e58ea3a6b99db89761eb5c7e30ab6615e165b1` remains an ancestor. Accepted C01 dependency: `2e6c2329aafe28b2e7c31ef5078d554cb66ca529`.
- Final check evidence: run the strict helper after this commit. Frontend test/build results below were run on the working tree before the commit. This note does not claim its own commit SHA.
- Owned/changed paths: `web/` (source, lockfile, Vite config) and `docs/ui/`. This handoff note. No `src/sentinel/`, `contracts/`, migrations, Python dependencies, `docs/STATUS.md`, or `docs/TASK_QUEUE.md`.

## Implemented

- Merged accepted C01 `2e6c2329aafe28b2e7c31ef5078d554cb66ca529` into `task/cursor-analyst-ui` (merge `ed61cc99dfaf754c1b085ffcbb46b9bda7e027fd`). No content conflicts.
- React/TypeScript/Vite workbench. Same-origin dev proxy for `/healthz` and `/v1` to `SENTINEL_API_ORIGIN`, default `http://127.0.0.1:8000`.
- Session token is React state only. Sign-out drops it. Requests send `Authorization: Bearer` and put no token in the URL.
- Queue, overview, case detail, evidence, server-built proposal, approve/reject, and a separate execute step. Rule scores stay labeled as rule scores. Deterministic and local Claude investigators are labeled from the server name. Rationale is a text node.
- One execution UUID is kept when the response is missing, non-JSON, a 5xx, or a network failure. A handled 4xx clears it. A 409 reloads the case.
- Synthetic ingest uses `POST /v1/transactions` when the session has `ingest_transaction`. An ambiguous ingest can be retried with the same body.

## Verified

- `npm test` in `web/` -> 16 passed (5 files): 21 frozen examples, non-JSON/empty/invalid/network failures, money formatting, inert rationale, permission hiding, reopened case, provider failure, 409 refetch, lost execution retaining one key and one stored action, token absent from storage and the URL.
- `npm run build` in `web/` -> `tsc --noEmit` and Vite production build passed.
- These commands ran on the working tree before the UI commit. The strict Python helper is run after that commit.

## Not verified / gaps

- No browser-to-Postgres run. U02 still needs an accepted C02 fixture. Reload-clears-token, cross-session denial, rejection, expiry, and restart are not exercised against a real server.
- No live model call. Ordinary tests use fixtures and the deterministic labels from those fixtures.
- `npm audit --omit=dev` reported 0 vulnerabilities. The full audit reported dev-only Vitest/tinypool advisories. They were not force-upgraded to Vitest 5.
- Backend strict checks on this commit are recorded after the commit, outside this note.
- U03 is not started.

## Next action

Codex reviews the U01 commit. Start U02 only after that review and an accepted C02 fixture commit.

## Coordination and provenance

- Accepted dependency: C01 `2e6c2329aafe28b2e7c31ef5078d554cb66ca529`, recorded in coordination `f6236672685fe9508a645f62fac7d9fdb4e21fd6`.
- No reused AgentForge UI source. Public Sans is the `@fontsource/public-sans` package (SIL Open Font License), loaded locally.
- Frontend commands for the integrator are in `docs/ui/workflow.md`.
