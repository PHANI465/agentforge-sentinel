# PERF01: bounded deterministic local capacity measurement

Status: one local measurement on one Windows laptop. Not a capacity promise for banks, free
hosting or any production deployment. A neutral or poor result is a valid result; the
application was not changed to improve these numbers.

## What the tool does

`scripts/benchmark_local.py` (tests: `tests/test_local_capacity_benchmark.py`):

- Starts a **fresh, test-owned** stack with the accepted helper `scripts/local_stack.py`,
  unchanged (ownership marker, identity checks, `up`/`down`, recovery), in a new run
  directory (default `.agent/perf01/<UTC stamp>-<seed>/`, git-ignored) on free loopback
  ports. Rule scorer; deterministic three-role investigator (adapter always deterministic);
  the API connects as the runtime role, the owner only provisions.
- There is no target option: the only target is the owned loopback API. Inherited
  investigator/adapter/model/database/provider-key variables are removed from the helper's
  environment, `SENTINEL_LIVE_CLAUDE=0`, the Claude executable points at a missing path and
  the HTTP client ignores proxy settings (`trust_env=False`).
- Setup (counted separately): health, scorer and session checks; synthetic alert cases
  (one large debit on a fresh account each) for the read and investigate workloads; then
  sequential warm-up requests per workload.
- Measurement, closed loop at each concurrency, no retries, no sweep, server limits
  unchanged:
  - `ingest`: unique non-alerting synthetic transactions (fresh account, small amount);
  - `read`: `GET /v1/cases/{id}` of existing scoped cases;
  - `investigate`: one independent fresh alert case per request.
- Verification (counted separately): every scoped case is read back; approvals and
  simulated actions must be 0; transactions are reconciled against known writes; unknown
  investigations are reconciled from the case read and still reported as unknown.
- The helper's own `down`; cleanup is "verified" only when the recorded API launcher and
  listener and the postmaster are gone and both ports are free (or still held by a foreign
  listener that held them before the run). Otherwise the state is kept, a recovery command
  is printed and the exit code is 2. Nothing is killed by name; no directory is removed.

Outcomes: **success** (expected status and body); **refused** (any 4xx, service code kept;
409 `agent_capacity_exhausted` is refused, never success, never retried); **failed** (5xx,
unexpected body, or a request that provably never reached the server); **unknown** (client
timeout or broken connection after sending, `investigation_outcome_unknown`, or still in
flight when the bounded wait ended).

Caps (option defaults / hard ceilings): 12 / 50 requests per cell; concurrency 1,2,4 / at
most 4; 108 / 200 measured requests in total; 300 / 600 s active measurement; 2 / 5 warm-ups
per workload; at most 300 setup and 400 verification requests. Caps stop **new** work only;
in-flight requests finish within their client timeout (30 s; investigate 175 s, above the
server's 150 s workflow deadline).

Definitions: latency is `time.perf_counter` seconds from just before sending until the
response is classified; all-attempt latency includes refused/failed/unknown, success latency
only successes. Quantiles are nearest-rank (rank ceil(q*n) of the sorted sample). Cell window
is first request start to last request end; throughput is started (attempted) or successful
requests divided by that window. Empty samples and denominators are `n/a`.

Resident memory: Windows working set (Linux: VmRSS), sampled every 0.5 s during the
measurement phase only, on verified owned processes: `api` = the recorded API launcher and
listener identities; `postgres` = the verified postmaster plus descendants created no
earlier than it. Each read is accepted only if the identity matches before and after.
Sums double-count shared pages; short peaks between samples can be missed.

## Run

    uv run --locked python scripts/benchmark_local.py

The JSON summary is printed and written with raw per-request records to the run directory.
Reports contain no token, URL, host name, user, command line or environment.

## Result (run 2, accepted measurement)

- Source: `9d625cf4d042224009feb823b89dac5b5778867e`, clean tree; default configuration;
  seed 20261106; November 7, 2026 00:58 UTC.
- Platform: Windows 10/11 (release "10"), AMD64, Intel64 Family 6 Model 154, 16 logical
  CPUs, 15.7 GiB RAM with **0.9 GiB available at start** (other sessions were open);
  CPython 3.11.3; PostgreSQL 14.17; clock QueryPerformanceCounter, resolution 1e-07 s.
- Stack: helper `up` 11.9 s (fresh initdb + migrations + API), three-role / deterministic
  adapter / no model / rule scorer, postmaster verified. Total wall time 34 s.
- Setup 53 requests (53 success; p50 0.075 s, max 0.210 s). Warm-up 6 (6 success).
- Measurement: 108 of 108 planned requests started, 0 not started, 8.87 s active; no cap
  was reached.

| workload | c | n | success | refused | failed | unknown | all p50 / p95 / max (s) | success p50 / p95 / max (s) | window (s) | attempted/s | success/s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ingest | 1 | 12 | 12 | 0 | 0 | 0 | 0.078 / 0.220 / 0.220 | same | 1.078 | 11.1 | 11.1 |
| ingest | 2 | 12 | 12 | 0 | 0 | 0 | 0.098 / 0.213 / 0.213 | same | 0.646 | 18.6 | 18.6 |
| ingest | 4 | 12 | 12 | 0 | 0 | 0 | 0.095 / 0.211 / 0.211 | same | 0.358 | 33.5 | 33.5 |
| read | 1 | 12 | 12 | 0 | 0 | 0 | 0.074 / 0.118 / 0.118 | same | 0.951 | 12.6 | 12.6 |
| read | 2 | 12 | 12 | 0 | 0 | 0 | 0.084 / 0.204 / 0.204 | same | 0.713 | 16.8 | 16.8 |
| read | 4 | 12 | 12 | 0 | 0 | 0 | 0.101 / 0.116 / 0.116 | same | 0.320 | 37.5 | 37.5 |
| investigate | 1 | 12 | 12 | 0 | 0 | 0 | 0.310 / 0.338 / 0.338 | same | 3.732 | 3.2 | 3.2 |
| investigate | 2 | 12 | 2 | 10 | 0 | 0 | 0.034 / 0.367 / 0.367 | 0.346 / 0.367 / 0.367 (n=2) | 0.683 | 17.6 | 2.9 |
| investigate | 4 | 12 | 1 | 11 | 0 | 0 | 0.037 / 0.383 / 0.383 | 0.383 / 0.383 / 0.383 (n=1) | 0.384 | 31.2 | 2.6 |

All refusals are 409 `agent_capacity_exhausted`: the accepted server admits one live
three-role workflow per process (`max_live_workflows_per_process = 1`). In a closed loop
without retries, extra workers are refused within about 0.03 s and move on to the next
fresh case, so contended cells consume their cases quickly with one or two successes.
Successful investigation throughput stays near 3/s at every concurrency. The high
attempted rate in contended cells is the rate of fast refusals, not useful work.

- Verification: 52 requests (52 success). 50 scoped cases: 33 open (read cases and the
  refused investigation cases), 17 awaiting approval (2 warm-up + 12 + 2 + 1). Approvals
  **0**, simulated actions **0** on cases and **0** in the overview. Transactions 88 = 88
  known writes; 0 unknown requests, so nothing needed reconciliation.
- Resident memory during measurement (18 samples each, no unreadable reads): API peak sum
  65.9 MiB (2 processes); PostgreSQL peak sum 118.2 MiB (up to 9 processes).
- Cleanup verified: helper `down` exit 0, both API processes and the postmaster gone, both
  ports free (free before the run too). `local_stack.py status` afterwards: database
  stopped, api down. No token, connection string or password text in stdout, summary,
  records or the API log.

## Run 1 (kept as defect evidence, numbers not used)

Run 1 on `0ae199c` (00:55 UTC, same configuration) completed with the same outcome counts
and verified cleanup, but its latencies were quantized: on this Windows Python
`time.monotonic` is GetTickCount64 with 15.625 ms resolution, so every value was a multiple
of about 15.6 ms. Commit `9d625cf` switched measurement to `time.perf_counter` and records
the clock implementation and resolution in provenance. Its private records remain in that
run directory.

## Limitations

- One laptop, one accepted run, n = 12 per cell (n = 1-2 successes in contended
  investigate cells). With n = 12, nearest-rank p95 is rank 12, i.e. the maximum. No
  confidence intervals; these numbers do not support a capacity claim.
- The machine had little free memory at start; other applications and sessions shared it.
- Client and server share the machine; the client's CPU use is included.
- Deterministic adapters only: no provider latency, so `investigate` here is a lower bound
  on workflow overhead, not a live-agent measurement.
- Windows only. The tool's POSIX paths (VmRSS, `/proc` identity) are exercised by unit
  tests on whichever platform runs them; no Linux benchmark run is reported here.
- No approval/execution workload by design.
