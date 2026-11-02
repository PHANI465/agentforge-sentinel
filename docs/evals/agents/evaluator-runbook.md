# Evaluator runbook: manual comparator runner (G3D-P1)

Audience: whoever runs `scripts/agent_eval.py` on development cases. The output is a **development result** under [protocol-v1](protocol-v1.md). It is never a final held-out evaluation, a quality claim or a cost figure.

## 1. Two authorities

The runner uses two database identities. They come from the environment, so they never appear in argv or shell history, and the runner never prints them.

| Variable | Identity | Used for |
| --- | --- | --- |
| `SENTINEL_EVAL_OPERATOR_URL` | The schema owner of a **disposable, migrated** database | (a) Read-only catalog checks of the runtime role (accepted `sentinel.db.roles` checks). (b) Issuing one fresh analyst session per attempt. The runtime role cannot insert sessions. Nothing else. |
| `SENTINEL_EVAL_RUNTIME_URL` | A least-privilege runtime role of the **same** database, created by `python -m sentinel.cli grant-runtime` | Authentication, case ingestion and scoring, evidence reads, the investigation itself (service, coordinator and tools, exactly as the API runs them) and the post-attempt read of step usage sources. |

`--database-url URL` still works but is **provisioning-only**. It is equivalent to `SENTINEL_EVAL_OPERATOR_URL`, and if both are given they must be equal. It never runs investigations. There is no fallback to the operator: without a valid runtime configuration the runner refuses.

### Checks that run before any comparator or case

The live-consent check comes first, then these checks. Each failure prints `refused: <code>: <reason>`, exits 2 and writes nothing. No driver message, URL, credential or traceback is printed.

| Code | Meaning |
| --- | --- |
| `unknown_comparator`, `unknown_case` | The name is not in the catalog. |
| `duplicate_comparator` | A comparator is named twice. Each comparator runs once per run record. |
| `unsupported_case` | The case needs scorer or profile setup this runner does not perform. Today every case uses the rule scorer and no profile. |
| `operator_config_missing`, `runtime_config_missing`, `operator_config_conflict` | The configuration is incomplete or conflicting. |
| `operator_connection_failed`, `runtime_connection_failed` | The connection failed. The driver message is not printed, because it can echo the host and user. |
| `database_mismatch` | The two identities reach different databases. The comparison covers database name, database OID, server start time and port. |
| `runtime_unsafe` | The runtime login is the operator, has switched role, or holds SUPERUSER, CREATEROLE, CREATEDB, REPLICATION or BYPASSRLS. It also fails if `roles.unsafe_reasons`, `roles.verify_effective` (the exact grant map) or `roles.environment_reasons` (PUBLIC authority) report anything. Reasons name privileges and objects, never credentials. |
| `runtime_check_failed`, `operator_check_failed` | A catalog query or the connection close failed after the connection was made: on the runtime side (identity and attributes), or on the operator side (identity and the `roles.py` checks). |

These checks read the catalog only. They do not grant, revoke or refresh anything.

## 2. Procedure (local, disposable)

```sh
uv run --locked python -m sentinel.cli devdb start            # prints the owner URL of a trust-auth local cluster
# create a dedicated disposable database on it (for example createdb, or psql CREATE DATABASE)
export SENTINEL_DATABASE_URL=<owner URL of that database>
uv run --locked python -m sentinel.cli migrate
uv run --locked python -m sentinel.cli grant-runtime --role sentinel_eval_rt   # optional password: SENTINEL_RUNTIME_PASSWORD
export SENTINEL_EVAL_OPERATOR_URL="$SENTINEL_DATABASE_URL"
export SENTINEL_EVAL_RUNTIME_URL=<same URL with user=sentinel_eval_rt (and its password)>
uv run --locked python scripts/agent_eval.py                     # C0,C2-det over all dev cases
uv run --locked python -m sentinel.cli devdb stop
```

Use a fresh database for each run record, then drop it. Do not point the runner at a database holding anything you want to keep: every attempt creates sessions and cases.

## 3. What a run does, and what it does not

- **Comparators.** The default is `C0,C2-det`, both deterministic, with no provider. C1 and C2 call the owner's local Claude subscription. They are refused unless `--allow-live` is given explicitly. There is no API-key or paid fallback. Account isolation and no-fallback rules are unchanged, and G3D-P1 never passes that flag.
- **Per attempt.** An attempt is one `investigate` request (protocol-v1). Setup comes first: the operator issues a fresh session (`provision`), then the runtime role authenticates (`authenticate`) and ingests the case's `runtime.history` and `runtime.alerted` rows with real time (`ingest`). Then the runtime role sends the request. Failed, refused, pending and errored attempts are counted, never dropped or re-run.
- **Role inputs.** Only runtime case inputs reach roles. The case `evaluator` section is never read by the runner.
- **Faults are not applied.** The `faults` listed in a case's runtime section are instructions for the pytest harness: injected adapters, owner tamper or locks, clock advances, process kills, extra sessions or admissions, and human sequences. This runner applies none of them. For D05–D15 it therefore runs the **no-fault baseline of the case's facts**, not the fault scenario. The record lists each case's `faults_not_applied`. Fault behaviour is evidenced only by the pytest suites (`tests/test_agent_*.py`, `tests/test_future_clock.py`), not by this runner. D11's notes reader is deferred.
- **Accounting.** Each comparator reports:
  - `counts`: attempts, dispositions, inconclusive, refused, pending and error;
  - `inconclusive_by_code`;
  - `request_latency_s` per attempt;
  - `attempts`: one row per attempt, with case, outcome, code or failure codes, case state, `usage_sources` and, if that read failed, `usage_error`;
  - `cases_not_attempted`, which is empty unless the run stopped.

  `usage_sources` is one of: the stored step sources; `["no_role_steps"]` for C0; `["not_read"]` after an errored request; or `["unavailable"]` if the read failed.

  `tokens` is `adapter_reported` only if every attempt's `usage_sources` is exactly `["adapter_reported"]`. Any missing, unavailable, not-read, not-applicable or unknown provenance, or zero attempts, gives `unknown`. Deterministic adapters report `not_applicable`, and C0 has no role steps, so their tokens are `unknown`.
  - No money or token-budget claim is made.
- **Run record.** The record holds:
  - `status` (`complete` or `incomplete`), `stopped` and `comparators_not_started` (§4);
  - the git HEAD, marked `+dirty` if the tree is not clean;
  - platform, Python, start and end times;
  - the authority split;
  - per case, the runtime SHA-256 and the faults not applied.

  Workflow elapsed (protocol-v1's C2 gate) is not printed. It is in the stored steps of the disposable database. The pin digests and rubric sheet ID required by protocol-v1 §6 are added by the operator in the owner-reviewed summary.

## 4. Failure and partial-output policy

| Where it fails | What happens | Exit |
| --- | --- | --- |
| Before the run: configuration, connection or catalog check | Typed refusal, as in §1. Nothing is written and no JSON is printed. | 2 |
| Setup of a case: `provision`, `authenticate` or `ingest` | Not an attempt: there is no row, no latency and no denominator change. The run **stops**. Earlier attempts are kept unchanged. The record says `status: incomplete`, gives `stopped` (comparator, case, phase, code) and lists `comparators_not_started`. The stopped comparator lists `cases_not_attempted`, including the case whose setup failed. The full JSON is still printed. | 3 |
| Comparator construction | The same as a setup failure, with phase `comparator` and case `null`. That comparator is listed as not started. | 3 |
| Inside the `investigate` request | It is an attempt: `outcome: error` with a code and its measured `request_latency_s`. The run continues. | 0 when complete |
| The usage read after a known outcome | The outcome stays as recorded, because it was committed, not rolled back. `usage_sources` becomes `["unavailable"]` with `usage_error`. Tokens become `unknown`. The run continues. | 0 when complete |

The policy also covers these cases:
- **Codes.** Every error code is a typed service code or an exception class name, such as `RaiseException` or `OperationalError`. It is never the message, which can carry SQL text, host or user.
- **Interrupts.** KeyboardInterrupt and SystemExit are not caught: an interrupted run prints no report.
- **No silent retries.** Nothing is retried silently. Nothing falls back to the operator.
- **Wrapper scripts.** A script must treat exit 3 as a partial development record, not a failure to discard.

## 5. Limits

- Development cases only. Do not generate or inspect final evaluation cases with this runner.
- Request latency on a laptop with a local cluster is not a capacity or production-latency claim.
- Deterministic C0 and C2-det results show plumbing under the runtime role. They are never evidence of agent quality (protocol-v1 §1).
- The runtime checks cover the current database's relations, columns and schemas and the cluster's databases, as `roles.py` documents. They do not make storage tamper-proof against the owner.
- Evidence for §4 is in `tests/test_agent_eval_failures.py`. It uses test-owned failing triggers and narrow query faults, and checks that canary messages never appear in output.
- Evidence for the authority split is in `tests/test_agent_eval_privileges.py`. A test-owned SECURITY DEFINER trigger records the login of every insert into the session, case and workflow tables, which proves that sessions are inserted by the operator and everything else by the runtime role.
