# Handoff: task/claude-perf01-local-capacity

- Task and acceptance criteria: PERF01 (docs/prompts/CLAUDE_PERF01_LOCAL_CAPACITY.md), Worker B
  of docs/prompts/CLAUDE_PARALLEL_BATCH_2026-11-06.md: one bounded deterministic local capacity
  benchmark, not an optimization project.
- Tool and worktree: Claude Code (Opus 5.5 / High), E:/PHANI/sentinel-wt/claude-perf01-local-capacity
- Updated: 2026-11-07 ~01:05 UTC
- State: ready for review
- Base: 7e5d367b09f1f8677b69e572654c8d23220e29c9 (main; contains d8443a1 and tested 495c7d3)
- Code reference tested before this note: 9d625cf4d042224009feb823b89dac5b5778867e (clean)
- Final check evidence: non-DB unit tests and ruff rerun after the final docs commit; see the
  final chat report. The docs commit changes no code.
- Owned/changed paths: scripts/benchmark_local.py, tests/test_local_capacity_benchmark.py,
  docs/benchmarks/PERF01-local-capacity.md, this note. No other path changed.

## Implemented

- scripts/benchmark_local.py: fresh owned stack through unchanged local_stack.py (rule scorer,
  deterministic three-role investigator, runtime-role API, loopback only, no target option);
  setup/warm-up/measurement/verification counted separately; success/refused/failed/unknown
  accounting with no retries; nearest-rank p50/p95/max for all attempts and successes;
  windowed attempted/success throughput; n/a for empty denominators; hard request/time caps
  that stop only new work; bounded in-flight wait (unfinished requests stay unknown);
  read-back of zero approvals/actions; transaction reconciliation; resident memory sampled
  only on verified owned processes; non-secret provenance; verified owned cleanup with
  recovery message and exit 2 when unverifiable.
- 0ae199c initial tool; 9d625cf switches the measurement clock to time.perf_counter after
  run 1 showed 15.625 ms quantization from Windows time.monotonic.

## Verified

- ruff on owned files -> clean (9d625cf).
- `pytest tests/test_local_capacity_benchmark.py -k "not small_real_run"` -> 34 passed (9d625cf;
  no DB/API started; includes the real-helper foreign-listener refusal test).
- Heavy slot 1 on 0ae199c: focused DB tests (benchmark + test_local_stack*.py) -> 65 passed in
  105.9 s; default real benchmark run 1 -> exit 0, cleanup verified (latencies quantized).
- Heavy slot 2 on 9d625cf: `pytest tests/test_local_capacity_benchmark.py` -> 35 passed in
  20.9 s (includes the small real-stack end-to-end test); default real benchmark run 2 -> exit
  0, 108/108 started, results in docs/benchmarks/PERF01-local-capacity.md; cleanup verified
  (helper down 0, processes gone, ports free; status: database stopped, api down); no token or
  connection string in outputs or api.log.
- Private raw records: .agent/perf01/20261107T005517Z-20261106/ (run 1) and
  .agent/perf01/20261107T005827Z-20261106/ (run 2), ignored, kept.

## Not verified / gaps

- Full six-command gate not run (coordinator runs it on the combined preview).
- No Linux/native Ubuntu benchmark run; POSIX VmRSS path only exercised there by the gate.
- The end-to-end test adds about 20 s of real-stack time to the full pytest command.
- n = 12 per cell; no confidence or production capacity claim.

## Next action

Codex reviews PERF01 on the combined batch preview; the coordinator reruns the benchmark focused
tests there.

## Coordination and provenance

- local_stack.py, production src, schema/grants, deps/locks, CI/skips and central STATUS/
  TASK_QUEUE are unchanged. No P4a or AN01 code imported. No new dependency (httpx is the
  existing dev dependency; memory via ctypes / /proc). No provider/auth call, approval or
  execution.
