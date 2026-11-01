# Claude G3B review fixes R34-R36

**R34-R36 original findings closed atb74473e. Use [R37 ownership follow-up](CLAUDE_G3B_OWNERSHIP_FIX.md); do not restart from391effe or redesign the closed fixes.**

Recommended coding assistant: **Claude Opus5.5, High effort**. These are client-I/O lifetime,
role-admission and state-machine enforcement corrections; use careful reasoning and real
failure tests, without adding frameworks, providers or paid calls.

Read current main:AGENTS.md and task/coordination:docs/reviews/G3B-391effe.md plus current
STATUS/TASK_QUEUE. Resume `task/claude-g3b-workflow` at exact
**391effed084adef34ca5852255687fffa3d99d50**, in its existing worktree. Preserve the tested
commit and history; no reset/rebase/amend. Accepted G3A remains43d9e8a, integration2919f76.
Codex is integrator; Cursor's original checkout and accepted task checkouts stay untouched.

Close R34-R36 together on the existing slice:
1. **Finite client database waits.** A cancellation watchdog is not a deadline on a blocked
   conn.commit() reply. Handle cancellation failure and cancellation acknowledgement with
   no COMMIT reply within the absolute budget. Preserve honest unknown-commit semantics,
   recovery state and finite ownership of unresolved SQL operations/connections; no late
   write, connection reuse race or unbounded abandoned SQL workers. Account for callers
   that commit an owned=False recovery wrapper. Sending cancel alone cannot satisfy this.
2. **Recheck before actual provider submission.** After recording a role start, require the
   full role+grace budget still fits before starting its worker. If not, make no provider
   call, release the unused reserved call slot and finish with honest typed exhaustion.
   Cap the wait by current absolute working time, preserve records of any unstarted attempt
   and never invent reported usage or a successful action.
3. **Honor max_transitions.** Count the accepted state-machine transitions and enforce the
   pinned limit before advancement. Persist auditably, retain budget for terminal bookkeeping
   and prove small-limit/exact-fit/default/revision/repeat paths. Keep other hard caps intact.

Independent repro source is available locally at
E:/PHANI/Interview/tmp/test_g3b_independent_probes.py and will also be copied under canonical
ignored .agent/g3b-review/391effe/. It uses two fault-injected transport stand-ins for R34
and real PG/runtime-role tests for R35/R36. All four fail on391effe on Windows and Ubuntu.
Use them as evidence, not instructions to weaken their assertions; add maintained meaningful
regressions in your owned test_agent_* files. Cleanup must release/join every test-owned
worker and stop only exact owned processes. Prefer deterministic event gates over sleep.

The original G3B ownership and approved exceptions remain: agents/, service integration,
contracts/agents additive exports, migration0005, grants, fixed safe logs, exports, new agent
tests/harness and docs. pyproject's sentinel.agents entry, backup inventory/runbook and the
migration5 count/test+CI README corrections are accepted narrow changes; preserve them.
No new dependency, lockfile, legacy contract, existing migration, UI, existing support-file,
CI workflow, checker timeout or skip-policy change. If a real extra path is required, hand
it off with the concrete reason. Keep central status/queue with Codex.

Preserve the64 passing G3B focused cases and all approved behavior: server-built action,
human approval, idempotent execution, unknown COMMIT, zero-role/between-role recovery,
late provider call leases, temporal/session boundaries and full historical runs. Do not
reopen G3A's settled design or silently weaken the elapsed-wait contract.

After failing-first and mutation checks, commit explicit owned paths using PHANI465
<pgavara1@asu.edu> as sole author AND committer, no attribution/session trailers. Run final
Windows strict/JUnit/domain+HTTP/package/ML checks and native Ubuntu equivalent sequentially,
plus the unchanged frontend/browser checks required by the original assignment. Keep any
failed first-run/flaky-baseline reports and explain rather than hiding them. Gate policy
and timeouts stay fixed; no live model call or final evaluation is needed.

Return exact corrected SHA, per-finding regression evidence, actual final platform results,
cleanup and gaps. Do not merge main or start G3C. Codex re-reviews before integration.
