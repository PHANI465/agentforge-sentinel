# Verification

## Thin-path increment (branch task/thin-path)

Verified October 23, 2026 by Claude Code in E:\PHANI\agentforge-sentinel (Windows 11). Environment: isolated .venv from uv.lock; Python 3.11.3, Pydantic 2.14.1, FastAPI 0.143.0, psycopg 3.3.6, pytest 8.4.2, Ruff 0.17.2, Node 22.13.1, PostgreSQL 14.17 (disposable test clusters), Claude Code 2.1.224.

### Working-tree checks (before the task commit)

| Command | Actual result | Exit |
| --- | --- | --- |
| uv run --locked python -m ruff check . | All checks passed | 0 |
| SENTINEL_LIVE_CLAUDE=1 uv run --locked python -m pytest -q | 86 passed, 1 warning (Starlette httpx deprecation) in 55.6 s | 0 |
| uv run --locked python -m pytest -q (default, no live call) | 85 passed, 1 skipped (live Claude test, opt-in) | 0 |
| uv run --locked python -m unittest discover -s tests_handoff | 21 tests OK | 0 |
| uv run --locked python scripts/export_contracts.py --check | 14 draft v1 schemas verified (11 existing byte-identical, 3 new) | 0 |
| node scripts/check_contract_examples.mjs | transport checks passed | 0 |

The strict `scripts/agent_check.py` result after the commit is reported in the final chat/PR, not in this file.

### What the 86 tests cover

- 51 pre-existing contract/schema tests (unchanged).
- 17 integrated Postgres/API tests (tests/test_thin_path.py):
  - the full path with a fresh service/app between every step; the case moves open(1) -> investigating(2) -> awaiting_approval(3) -> closed(4);
  - the server fills the intent's target and amount from stored records;
  - an idempotent retry returns the original action;
  - exact audit sequence; below-threshold ingestion; ingestion replay/conflict; future event rejection;
  - 401 without or with a bad token; code-only 422 that never echoes a canary secret;
  - same-tenant other-session isolation (404 on read, audit, investigate, approve, execute); stale revision and wrong state;
  - 4 concurrent executions (2 sharing a key): exactly one action row, the same id for the shared key;
  - idempotency-key reuse across approvals -> 409; expired approval denied and audited, approval left unconsumed;
  - rejected approval closes the case and cannot execute; missing execute capability inside scope -> 403 and audited;
  - investigator failure reopens the case for retry; a crashed run is recovered after a restart; a late finish after recovery is superseded;
  - audit UPDATE/DELETE/TRUNCATE rejected; migrations apply once.
- 16 investigator tests (tests/test_investigators.py), mostly with a fake runner:
  - locked-down CLI flags: no `--bare`, no permission bypass;
  - API-key variables stripped; working directory outside the project;
  - the Windows `.cmd` shim is never executed;
  - typed failures for timeout, missing binary, non-zero exit, error envelope, prose, and smuggled fields (`approved`, `transaction_id`, unknown operation, oversized rationale);
  - local-only mode switch;
  - **1 live call** through the owner's Claude login (opt-in).
- 2 scoring tests.

### Mutation checks (manual, reverted)

- Removing the approval row lock and the `consumed_at IS NULL` guard -> the concurrency test failed.
- Breaking the case compare-and-set WHERE clause -> an isolation test failed. No test exercises a pure stale-write race on compare-and-set alone, because row locks and explicit revision checks precede it.

### Manual two-process smoke (real uvicorn, real Postgres, live Claude)

1. `sentinel.cli devdb start`, then `migrate` twice (the second applied nothing), then `create-session`.
2. Start uvicorn with `SENTINEL_INVESTIGATOR=claude-cli`. `scripts/smoke_thin_path.py investigate` returned:
   - alert score 1.0;
   - investigator `claude-cli-investigator`, status completed;
   - finding `simulated_hold` / `unusual_amount`;
   - case `awaiting_approval`, revision 3.
3. Kill uvicorn, then stop and restart Postgres, then start a new uvicorn.
4. `smoke_thin_path.py execute <case>` returned:
   - action `succeeded`, mode `simulated`;
   - the retry replayed the same action id;
   - audit = transaction_received, alert_raised, investigation_started, investigation_completed, approval_recorded, action_succeeded (all success);
   - case `closed`, revision 4.
5. An unauthenticated GET returned 401. The dev DB was stopped and the token file deleted.

### Not verified

- No UI and no browser-to-database end-to-end test. No hosted staging, hosted BYOK or deployment.
- No trained model: scores are rule heuristics.
- Not tested in CI or on Linux/macOS (devdb path discovery for those systems is untested).
- Not measured: Claude subscription plan/quota behavior and real model latency distribution (one call took about 7 s); behavior under quota exhaustion is only simulated.
- No least-privilege database role. Audit triggers do not stop a database owner, so the audit log is not tamper-proof.
- No load/performance testing; one connection is opened per operation.
- Secret-safe trace inspection is limited to error bodies; no structured logging exists yet.

### Source SHA256 values (tested working tree, LF line endings as committed)

- `pyproject.toml`: `7e4646abb5ea59da1cf8055478585b1cae125b006c29767a1899c6bc83164dd8`
- `uv.lock`: `be1d0a2be2bc2875a485e163edba40b1a1d51ecbd4ce299222068675bd86e788`
- `src/sentinel/contracts/v1.py`: `31a1004aa78cad401824bc8b280ddde3860f6efa2c3819aec7d07909ea9e2489`
- `src/sentinel/contracts/guards.py`: `880379270667231e8a17e74b65a3b15654c83aef5b7391806f931a2386a2cef5` (unchanged)
- `src/sentinel/db/__init__.py`: `c49508df972cfe5d3f6fe9987c0031ca5e3d2283231041ca584e50e975f22821`
- `src/sentinel/db/migrations/0001_thin_path.sql`: `b47c467e6274dc9edf7b7c427148447371f9f9f8ec9972cfed03cd941feac087`
- `src/sentinel/service.py`: `3d9077d350f291ce13ccdfef8fe280b20bdae865a729c3c4f28683b5b11c45d4`
- `src/sentinel/api.py`: `d51f265acfc669b05ee760d2993ef076f3d3e75e066e60ab0965777273cb2dc0`
- `src/sentinel/investigators.py`: `67f1c8fca564178fce0cd42dd37b0d19d5279a0f2dff19794bb68ce65243eb87`
- `src/sentinel/scoring.py`: `6b52b272e4bb6522396bc6d8dc945e21ef31b394a369b55c3b4101f73e70c9dc`
- `src/sentinel/devdb.py`: `51d155fead427de6ff43f8e34a0e86340926c4a2c9412f697f5a72dbd3085305`
- `src/sentinel/cli.py`: `83dd2c4e475ea1f7403e1d16b7e5613e952ec64474cf63330d358197115abc4e`
- `tests/test_thin_path.py`: `e9dd83ca05b73ef30ee7781ea1d8cc82147f991005ea4b730fb34620c80a6742`
- `tests/test_investigators.py`: `47bb653538f5788c4d378cac08e5a0bc68a59a92b95bbdcdc72c50a2aade5013`

## Previous: initial domain contract verification (Codex-led, baseline commit 507538e)

Verified October 23, 2026 with Python 3.11.3, Pydantic 2.14.1, pytest 8.4.2, Ruff 0.17.2, Node 22.13.1. Ruff passed; 51 contract/schema tests passed; 21 helper regressions passed; 11 schema exports verified; the Node transport check passed. That was working-tree evidence before Git existed. The source hashes listed then for `v1.py`, `pyproject.toml` and `uv.lock` describe that earlier state; this increment changed those three files. Historical handoff-kit verification is in HANDOFF_VERIFICATION_HISTORY.md.

The Node check verifies basic JSON transport and money bounds, not generated frontend types or full schema validation. Pure hash/precondition checks do not establish data authenticity or HTTP authorization; the integration tests above cover those boundaries only for this local path.
