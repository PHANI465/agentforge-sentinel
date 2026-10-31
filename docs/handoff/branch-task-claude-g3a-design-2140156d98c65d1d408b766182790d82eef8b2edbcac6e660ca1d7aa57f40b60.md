# Handoff: task/claude-g3a-design

- **Task:** the G3A three-role design package, **revision 2**: it resolves review R31–R33 of 06a7c0c. Sources on task/coordination dc47bae: docs/prompts/CLAUDE_G3A_REVIEW_FOLLOWUP.md, docs/reviews/G3A-06a7c0c.md and docs/reviews/G3A-acceptance-checklist.md. The original assignment was CLAUDE_G3A_MULTI_AGENT_DESIGN.md (4730010).
- **Tool and worktree:** Claude Code, E:\PHANI\sentinel-wt\claude-g3a-design (existing; resumed October 31 from a clean tree).
- **Updated:** 2026-10-31.
- **State:** the correction is complete and ready for Codex re-review. **G3B is not started** and needs a separate accepted design SHA and dispatch.
- **History:**
  - application base: exact accepted H01 f091a34c2ed3f6636625b3141be88d86cd5307dd;
  - 06a7c0c: the reviewed revision 1, preserved unchanged;
  - the commit containing this note: revision 2, added on top with no reset, rebase or amend.
- **Code reference tested before this note:** 06a7c0c plus the revision-2 working tree. This is documentation-only: no `src/`, migration, public contract, test, UI, script, model or lockfile change.
- **Changed paths (owned only):**
  - `docs/agents/G3A-design.md`, `docs/agents/G3B-implementation-plan.md`;
  - `docs/agents/contracts-draft/`: README, `g3a_models.py`, schemas (15), valid (35) and invalid (50) examples;
  - `docs/evals/agents/protocol-v1.md`, `dev-cases-v1.json`, `dev-cases-v1.md`;
  - this note.

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

- **Baseline on preserved 06a7c0c:** the 14 `*.r33-*.json` payloads use only 06a7c0c vocabulary. Validated against the 06a7c0c models (extracted with `git show` to the scratchpad, outside the repository), all 14 were **ACCEPTED**. The committed 06a7c0c files were not changed.
- **Revised models:** all 14 are rejected, plus the 3 `*_actor` variants rejected by their own specific contradiction. A per-file listing confirmed each intended reason.
- `g3a_models.py --check` → "15 draft schemas current; 35 valid and 50 invalid examples behave as labelled", exit 0.
- `dev_cases.py` → "15 development cases consistent with sentinel.scoring; three-role implemented in 0", exit 0.
- **Ruff:** passed.
- **Links:** the relative links and anchors of the 5 Markdown documents resolve, 0 broken.
- **Scope:** relative to 06a7c0c, nothing outside `docs/agents/`, `docs/evals/agents/` and this note changed.
- **Not run:** the full backend and browser suites (documentation-only, per the assignment).

## Not verified / limits

- **Nothing is implemented.** Leases, timeouts, the terminal transaction and recovery are designs; runtime proof is G3B acceptance work.
- **Unmeasured limits:** 45/150 s and the 2-call bound are not laptop or subscription measurements.
- **Worker lifetime:** it relies on the CLI adapter's subprocess timeout killing the local process, which G3B must verify. Provider-side cancellation is not claimed.
- **UI display gap:** v1.1 shows "No investigation has been recorded" for a zero-role inconclusive workflow; the failure is visible in the audit. The G3C trace route addresses this.
- **No live usage observation** was made; per the review, it is a later opt-in step.

## Next action

Codex: re-review revision 2 against the acceptance checklist. On acceptance, freeze `g3a-draft-1` and dispatch G3B from that exact SHA.
