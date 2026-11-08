# AN01-M1 93583a: delivery intake, independent review pending

November 8, 2026. This is an intake record, **not an acceptance or a completed independent review**.

- Candidate: 93583a7570ae78f254a2d69e9857b701b0e444ad, task/claude-an01-m1-prototype.
- Base: a07ec12710c86b15f111d13e3384c4cf0c6c8f6e, containing the reviewed r3.2 design.
- Source candidate checkout was observed clean. Author and committer are PHANI465 <pgavara1@asu.edu>.
- Diff against the base is limited to scripts/benchmark_reports.py, scripts/report_benchmark_support.py, tests/test_report_benchmark.py, docs/benchmarks/AN01-M1.md and its branch handoff. Production src, contracts, web, migrations, dependencies/locks and CI are unchanged.

## Evidence received

Claude reports exact-final Windows then native gates: all six commands, 876 tests plus one allowed skip each, same-run JUnit validation, frozen HTTP check and read-only ML reproduction. The local ignored Windows checker metadata names the exact candidate, clean before/after, and state passed. These author results have not been independently rerun or accepted by this documentation task.

Tiny smoke was at f00df8c, not the final candidate. It ends not demonstrated: native C2:1250 missed the provisional 30 ms reply margin in one of five trials. It was retained rather than retried. Final code changes cleanup and arrival-time recording; unchanged SQL digests do not turn an earlier smoke into a final-commit run.

## Independent review still required

1. SQL and scoped snapshot semantics, known-answer coverage, money/time/cursor behavior, and query digest binding.
2. Supervisor/process/cluster ownership, pending launch and recovery, stale identity refusal, finite resource reservations and final-close ownership.
3. R-M1-1: server timeout versus client work deadline, reply arrival versus notice, feasible rollback reserve and the provisional reply margin.
4. Specifically examine the post-failure C2/C3 assertion changes. Accepting both handled race outcomes may verify mechanics while failing to qualify the desired timing policy; keep those claims separate and independently probe both paths.
5. R-M1-2: the reported Windows clock coarseness in accepted budget.py. No production fix is accepted or assigned here.
6. R-M1-3: full-grid disk estimate versus the 4 GB cluster bound, actual target volume and WSL backing-volume headroom. Do not delete, resize, install or enlarge limits to force a run.
7. Validate the retained failed runs and missing-result interruption record. Gate success does not erase them or qualify failed strict benchmark cells.

No full-size grid is authorized. The 200,000-row cap, 5,000 ms budget, 250 ms reserve and 2/2 capacities remain provisional. No v1.3 freeze, production report route/UI, live provider, account/auth probe, protected final-case evaluation, new spending or remote operation is assigned.

The next task is Codex's independent review and a concrete correction/design decision if needed. Claude should preserve the tested candidate and wait. Read [the current checkpoint](../artifacts/AgentForge_Sentinel_Session_2026-11-08.md) and [new-chat resume prompt](../prompts/CLAUDE_RESUME_AN01_M1_REVIEW_2026-11-08.md).
