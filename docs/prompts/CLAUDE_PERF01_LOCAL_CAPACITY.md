# PERF01: bounded deterministic local capacity measurement

Recommended assistant: **Claude Opus5.5 / High**. Measurements must distinguish successful,
refused, failed and unknown requests, with safe resource ownership. No live agent/provider.

Read current task/coordination instructions and the batch driver. Create
task/claude-perf01-local-capacity at E:/PHANI/sentinel-wt/claude-perf01-local-capacity
from the current published main containing d8443a1 and tested495c7d3. Record exact base.
Do not import P4a96293da or AN01 draft code. Both are review-pending.

Own new scripts/benchmark_local.py (or a new scripts/benchmark_local/ package),
tests/test_local_capacity_benchmark.py, docs/benchmarks/PERF01-local-capacity.md,
small new tests/fixtures/local_capacity/ if necessary, and your branch handoff.
Read existing local_stack.py and its ownership/startup tests. Reuse it unchanged.
No production src, local_stack/browser helpers, API/schema/grant/migration, scorer/model/
data/evals, evaluator/P4a, UI, deps/locks, CI/skip/deadline or central coordination edits.

## Implement one bounded local benchmark, not an optimization project

- Run only against a fresh test-owned loopback API/Postgres stack using the accepted
  helper's marker, identity checks and recovery. The API connects as runtime; operator
  only provisions. Default: rule scorer and deterministic three-role investigator.
  No caller-supplied remote target, paid backend, credential/key fallback or provider call.
- Curated workloads: ingest unique synthetic transactions; read existing scoped cases;
  investigate independent fresh alert cases. Keep preparation/warm-up separate from
  measurement. Use concurrency1/2/4 and a small default sample (for example12 requests
  per workload/concurrency); hard-cap total requests and active measurement duration
  (for example300seconds). Document actual setup/request counts as well as measured ones.
- No automatic sweep, tuning, hidden retries or modified server limits. A client
  timeout means outcome unknown until explicitly reconciled; it does not prove no
  server write. Do not classify expected409 agent_capacity_exhausted as a success or
  silently retry it. Preserve every started request and its observed result/code.
- Report all-attempt and successful-request latency separately (monotonic seconds,
  n, nearest-rank p50/p95/max), status/service-code counts, attempted/success throughput
  with exact window definition, and setup/warm-up separately. Empty denominators are
  n/a, not0% or100%. State small-sample limitations; no confidence/production capacity claim.
- Record source/config/seed and nonsecret platform/resource provenance. RSS means only
  what is actually sampled on verified owned processes, with sampling interval and scope;
  unsupported values are unknown. No process command-line/env/URL/hostname/user dump in
  reports. Do not add psutil or any new dependency just for a metric.
- No approval/execution workload or real money. Confirm scoped approvals/actions stay0.
  Keep controlled sessions separate; do not alter datasets or model/evaluation protocols.
  No ML or agent final/holdout asset is needed for this traffic generator.
- Bound submissions, in-flight waits and shutdown. Use existing owned helper stop;
  keep recovery if stop cannot be verified, and do not stop unrelated services. Never
  kill by name or recursively remove a computed/shared temp directory.

## Evidence and handoff

Tests must prove failed/refused/unknown requests remain counted, quantiles and units
are correct on hand-computed samples, request/time caps stop new work, secrets are
absent, and owned cleanup/refusal preserves foreign resources. Do not replicate the
entire existing process safety suite; use it and add benchmark-specific cases.

Run a small real deterministic workload only when the parent grants the single heavy
execution slot. Keep private raw records ignored; commit an honest local-only summary
with actual n, hardware/config and limits if useful. Do not improve the numbers by
changing the app. A neutral or poor result is valid. This is one laptop, not a capacity
promise for banks, free hosting or a production deployment.

Run focused tests on your clean final commit and hand off SHA/base, results, metadata,
cleanup and unknowns. The parent will run complete Windows/native gates once on the
combined batch-preview commit; do not launch a full gate independently or claim that
its later result certifies your individual branch HEAD. Wait for the parent to schedule
any DB/load run. All commits PHANI465 <pgavara1@asu.edu> sole author AND committer, no
trailers/rewrite/global Git changes. Do not merge main or edit another agent's files.
