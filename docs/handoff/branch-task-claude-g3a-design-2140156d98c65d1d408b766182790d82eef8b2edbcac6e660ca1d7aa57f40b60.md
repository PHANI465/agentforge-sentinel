# Handoff: task/claude-g3a-design

- **Task:** the G3A three-role design package, **revision 3**: the narrow R31 deadline correction from review G3A-feb80d1. Sources on task/coordination 96ce294: docs/reviews/G3A-feb80d1.md and docs/prompts/CLAUDE_G3A_DEADLINE_FOLLOWUP.md. Revision 2 resolved R31–R33 of 06a7c0c; feb80d1 closed R32, R33 and R31's capacity rules, which are preserved unchanged. The original assignment was CLAUDE_G3A_MULTI_AGENT_DESIGN.md (4730010).
- **Tool and worktree:** Claude Code, E:\PHANI\sentinel-wt\claude-g3a-design (existing; resumed from a clean tree at feb80d1).
- **Updated:** 2026-10-31.
- **State:** the deadline correction is complete and ready for Codex re-review. **G3B is not started** and needs a separate accepted design SHA and dispatch.
- **History:**
  - application base: exact accepted H01 f091a34c2ed3f6636625b3141be88d86cd5307dd;
  - 06a7c0c: revision 1;
  - feb80d1: revision 2 (reviewed; one R31 deadline blocker);
  - the commit containing this note: revision 3, on top of feb80d1 with no reset, rebase or amend.
- **Code reference tested before this note:** feb80d1 plus the revision-3 working tree. This is documentation-only: no `src/`, migration, public contract, test, UI, script, model or lockfile change. All 15 draft schema files are byte-identical to feb80d1.
- **Changed paths in revision 3 (owned only):**
  - `docs/agents/G3A-design.md` (§3.1 pointer, new §3.2, §6.1, §8);
  - `docs/agents/deadline_budget.py` (new executable budget specification);
  - `docs/agents/G3B-implementation-plan.md`;
  - `docs/agents/contracts-draft/README.md` (error codes only);
  - `docs/evals/agents/protocol-v1.md`;
  - this note.

## Revision 3: deadline correction (R31 remainder)

- **The defect.** Revision 2's `min(db_wait, remaining − reserve)` gave 1/0/−1/−5 s at 6/5/4/0 s remaining. PostgreSQL 0 disables `statement_timeout` and `lock_timeout`, and the terminal write subtracted its own reserve.
- **The fix** (G3A-design §3.2):
  - **One deadline, two phases.** One monotonic deadline is read before the claim, so it is never after the persisted `deadline_at`; recovery waits for `deadline_at + 30 s`. The **working** phase is measured to `deadline − 5 s`. The **terminal** phase is measured to the deadline itself, so up to 5 s are truly available inside the reserve.
  - **Budgets.** Integer milliseconds, `min(cap, floor(end − now))`, refused below a positive minimum (100 ms per statement or COMMIT, 1 000 ms to start a terminal transaction), never 0 or negative. They are recomputed before every statement and before COMMIT, so sequential waits share one budget.
  - **Connections.** One single-host workflow connection is opened at the claim. libpq `connect_timeout` is whole seconds, with a minimum of 2 (0 means forever, 1 means 2); multi-host strings are refused. A terminal reconnect is allowed only if it still leaves the 1 s start budget.
- **Honest outcomes:**

  | Terminal attempt | Result |
  | --- | --- |
  | committed | 200 `CaseDetail`, read inside the transaction before COMMIT |
  | refused or rolled back | 409 `investigation_in_progress`; the workflow stays `running`, and recovery closes it |
  | COMMIT reply lost | 409 `investigation_outcome_unknown` (new, additive); the client re-reads |
  | guard failed | 409 `investigation_superseded` |

  The workflow slot is always released. Call slots stay with their workers.
- **Protocol.** One definition: *workflow elapsed* (monotonic, `t0` to the end of the terminal attempt) ≤ 150 s, with the reserve inside, is the gate. *Request latency* is reported, not claimed. The pending-recovery outcomes are counted in attempt accounting and in failure recovery.
- **Clarification recorded.** `CaseDetail` keeps returning every historical run of the case. The draft's counts describe a fresh case and must not become a filter (§6.1, G3B plan).

## R31–R33 resolution

- **R31 (capacity and late workers):** G3A-design §3.1.
  - **Two leases**, process-local and in memory:
    - a workflow slot (max 1), taken before the claim and released in `finally` after the terminal write;
    - a call slot (max 2 outstanding per process, late workers included), taken at submission and released **only when the worker thread actually returns**, by a done-callback.
  - **Repeats** only after a *resolved* failure, never after a timeout. So there is no overlap within a workflow, and outstanding calls stay ≤ 2.
  - **Deadline coverage:** the request deadline covers gathering, tools, claim checks and the terminal write. There are remaining-time checks before every step, a 5 s terminal reserve, and bounded `lock_timeout`, `statement_timeout` and `connect_timeout`. A tool statement is bounded at 2 s.
  - **Worker lifetime** is bounded by the CLI adapter's own subprocess timeout. Provider-side cancellation or billing is not claimed.
  - **Examples:** A (timeout → late completion → second admission → refused third, then release) and B (lock timeout during gathering).
- **R32 (terminal state):** G3A-design §6.1.
  - **One terminal transaction,** independent of an active role: scope/revision/workflow compare-and-set guards; fail only a truly running role run, with its true code; never rewrite completed runs or invent runs; case → `open` (or `awaiting_approval` with an intent).
  - **Audit actor:** the coordinator principal (`agent`) or `SYSTEM_ACTOR` for recovery.
  - **Eligible basis:** the same workflow's latest *completed investigator* run, or else inconclusive with no intent. The abstain example previously cited the reviewer run; it now cites the investigator.
  - **CaseDetail** is specified for every ending, including zero roles (`agent_runs: []`) and between-role recovery. Example C covers a crash, then 409 `investigation_recovered`.
- **R33 (contract invariants):**
  - the exact role set;
  - coherent `Usage` (unknown/not-applicable are unmeasured with no counts; reported is measured with both counts);
  - the `WorkflowRecord` lifecycle (running/completed/inconclusive with finish, disposition, `terminal_by`, ≥3 roles for completed, recovery ⇔ `interrupted`) and time order;
  - coherent `WorkflowLimits` (the deadline fits a call plus the reserve; call slots ≥ workflows);
  - `StepRecord` failure-code and `worker_unresolved` rules;
  - new inconclusive codes: `call_capacity_exhausted`, `coordinator_error`, `interrupted`.

  The 11 cross-record coordinator checks are listed explicitly in contracts-draft/README.
- **The four decisions,** applied verbatim: the 409 code, the provisional 45/150 s, reopen to `open`, and usage unknown unless observed.
- **Evaluation:** C1 versus C2 is an end-to-end system comparison with unequal evidence. A role-specific claim needs a future matched-evidence ablation under a new protocol. Cross-system claim quality uses one common human rubric; the machine rate is C2-only. The protocol now covers attempt accounting (refused, dispositions, inconclusive by code), `n/a (0/0)` zero denominators (not met / not exercised), and late-worker metrics.
- **Development cases:** now 15. D07 has no repeat after a timeout. New: D13 (zero-role exhaustion), D14 (between-role crash and recovery), D15 (late worker against admissions).

## Verified (Windows 11, this worktree's locked dev+ml, `python -B`, no provider/database/model)

**Revision 3, before its commit:**
- `deadline_budget.py` → exit 0: the old formula gives 1/0/−1/−5 s at 6/5/4/0 s; working refusals at and inside the reserve; valid terminal budgets inside it (5 000/4 000/100 ms); sub-second floors; zero and expired never 0 or negative; libpq granularity; sequential waits; refused, rolled-back and uncertain outcomes never reported as success.
- **Negative controls** (in-memory substitutions of the helper):
  - always-refuse: 15 failing checks;
  - terminal subtracting its own reserve: 8;
  - rounding up: 3;
  - allowing 0 or negative values: 14;
  - the real helper: 0.
- `g3a_models.py --check`: 15 schemas current; 35 valid and 50 invalid examples behave as labelled. The schema files are unchanged from feb80d1.
- `dev_cases.py`: 15 cases consistent with `sentinel.scoring`.
- **Ruff:** passed. **Links and anchors:** 0 broken.
- **Scope:** only owned paths changed relative to feb80d1.

**Revision 2 evidence (feb80d1), unchanged:** the 14 `*.r33-*.json` payloads were accepted by the preserved 06a7c0c models and rejected by revision 2, together with the 3 `*_actor` variants.

**Not run:** the full backend and browser suites (documentation-only, per the assignment).

## Not verified / limits

- **Nothing is implemented.** Leases, budgets, the terminal transaction and recovery are designs; runtime proof against a real PostgreSQL connection is G3B acceptance work.
- **Elapsed waiting, not durability.** The budget rules bound elapsed waiting on the coordinator's clock. They do not prove commit durability within the deadline, instant server-side timeout detection, or response transport time.
- **Unmeasured limits:** 45/150 s, the 5 s reserve, the 100 ms and 1 000 ms minimums and the 2-call bound are not measurements.
- **Worker lifetime:** it relies on the CLI adapter's subprocess timeout killing the local process, which G3B must verify. Provider-side cancellation is not claimed, and the process-local call cap is not a cross-process provider cap.
- **UI display gap:** v1.1 shows "No investigation has been recorded" for a zero-role inconclusive workflow; the failure is visible in the audit. The G3C trace route addresses this.
- **No live usage observation** was made.

## Next action

Codex: re-review revision 3 (the R31 deadline correction) against G3A-feb80d1. On acceptance, freeze `g3a-draft-1` and dispatch G3B from that exact SHA.
