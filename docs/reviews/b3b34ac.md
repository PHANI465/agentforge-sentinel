# Codex C05 re-review: b3b34ac

Exact commit: b3b34acfc79fbca3856877594e8b030dc14a66e0.
Branch/worktree: task/claude-backend-reliability, E:/PHANI/sentinel-wt/claude-backend-reliability.
Parent: 0119ca73e6ae3b4df9f9eeffcea8b15911f716e6. Accepted C01 2e6c2329aafe28b2e7c31ef5078d554cb66ca529 remains its base; no C02 merge.
Date: October 24, 2026, America/Phoenix.

**Outcome: changes requested for the remaining R18 effective-privilege gap. R19, R20 and both operator corrections are resolved. C05 is not accepted.** Cursor U02 retains its accepted U01/C02 dependencies and can continue independently.

## R18 [P1] remains: PUBLIC privileges can still modify session authorization

Locations: src/sentinel/db/roles.py:88-108 (direct ACL checks), 144-145 (candidate-only revocation).

The new preflight correctly rejects the tested unsafe role attributes, memberships, ownership and direct grants. However, ACL checks filter a.grantee to the candidate role OID. They do not account for effective permissions obtained through PUBLIC, including column-level ACLs. REVOKE ALL ... FROM candidate does not remove a grant held by PUBLIC.

A fresh owned disposable cluster reproduced this concrete authorization failure:

```sql
GRANT UPDATE(capabilities) ON public.api_sessions TO PUBLIC;
```

An ordinary existing LOGIN NOINHERIT candidate returned unsafe_reasons=[] before refresh. grant_runtime succeeded. A real connection as the resulting runtime role then updated one synthetic api_sessions row to capabilities ['execute','approve']; the operator connection verified that the change persisted. has_column_privilege remained true and unsafe_reasons still returned [] afterward. This contradicts the stated inability to modify or issue sessions; no elevated attributes, ownership or memberships were needed.

Reproducer: E:/PHANI/Interview/tmp/c05_r18_public_auth_probe.py. Its code/boolean-only results included runtime_updated_rows=1, persisted_session_capabilities_changed=true, public_column_privilege_survives_refresh=true, owned_cluster_stopped=true and owned_state_removed=true. No real user/session or outside database was used.

## Supporting R18 object-identity and schema cases

At roles.py:95-102, an allowed managed relation is recognized by unqualified relname. A direct DELETE grant on probe_other.api_sessions is therefore mistaken for a grant on the managed public.api_sessions. With PUBLIC supplying USAGE on the other schema, preflight returned [] and refresh retained the privilege; the runtime deleted one synthetic row from the unmanaged table.

The same bounded probe confirmed that CREATE on another schema via PUBLIC is missed too: preflight returned [] and a candidate created probe_other.new_object after refresh. Reject unsupported ambient privilege paths or explicitly narrow the scope of claims; checking only direct schema ACLs does not establish the current no-CREATE-on-any-schema statement.

Reproducer for both: E:/PHANI/Interview/tmp/c05_r18_grant_probe.py. The exact owned cluster was stopped and removed. A separate initial hypothesis was disproved: a direct candidate-specific column UPDATE grant is removed by the existing refresh. That is not reported as a surviving privilege.

## Required focused correction

Before password or permission mutations, account for effective PUBLIC permissions on managed authorization/data objects, including column ACLs. Reject unsafe candidates/environments without silently rewriting shared PUBLIC permissions or demoting operators. Match managed relations by exact schema/object identity, not a name that another schema can reuse. Keep safe idempotent refresh and actual runtime-role application execution.

Add failing-first disposable-cluster tests for the PUBLIC session-capability mutation, same-name unmanaged relation and effective schema CREATE cases. Check that refusal leaves password/attributes/grants/PUBLIC ACLs unchanged. Retain the working removal of stale direct grants. Keep this bounded to the verified runtime permission policy; a general PostgreSQL security-auditor rewrite is not required. Narrow any unsupported global claims honestly.

## Resolved corrections and independent evidence

- R19: parsed libpq options distinguish option names from misleading values. Independent keyword/URI probes preserve explicit 3/0 and apply default 10 otherwise.
- R20: 128 unsupported ASGI methods produce one OTHER request label and one latency key with total 128; log methods are bounded too.
- OFF logging: first-use OFF and INFO -> OFF suppress HTTP INFO/service ERROR output with root/stderr handlers; re-enabling works.
- Operator prose now limits clean plain-text 500 replacement to failures before headers and explicitly states no process-wide cap on late investigator threads.
- Exact clean HEAD, own Python/source imports and C01 ancestry verified. contracts/ and web/ have no diff from accepted C01; frozen OpenAPI and all 21 examples are byte-identical. No response-body/status or required-header change is accepted here.
- Independent focused tests: 64 passed (202.09 seconds), covering the 28 new regressions, 17 role tests and 19 reliability tests. Ruff, 21 helper regressions, 15 domain schemas, HTTP export/examples and Node transport checks passed independently.
- Owner strict metadata matches this clean commit/tree, five exit-0 checks and current checker digest. Its 239 passed plus one intentional live-Claude skip remain owner-reported counts; a redundant full repeat was not needed to demonstrate the uncovered defect.
- No reviewer implementation changes, installs, provider calls or external database use. Probe clusters were stopped and removed. Linux/macOS, CI, log shipping/retention and the combined C02+C05+UI stack remain unverified.

## Next action

Claude follows docs/prompts/CLAUDE_C05_R18_FOLLOWUP.md from current task/coordination, preserving accepted C01 and the resolved corrections. No contracts/, web/, C02 merge, main merge or environment provisioning is required. X-Request-ID stays optional diagnostics until a later accepted contract declares it. JSON 500 and metrics endpoints remain proposals only.
