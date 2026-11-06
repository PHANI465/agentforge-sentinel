# G3D-P4 plan correction: R44/R45

Recommended assistant: **Claude Opus5.5 / High**. This is a bounded document revision
about measurement validity, outcome accounting and safe pilot operation. It is not
permission to run a provider or implement evaluator tooling.

Continue task/claude-g3d-p4-eval-plan in its existing worktree from preserved3366edf
(3366edf247f2ec5ccff6d8f80b6c24519d7255cd). Read current task/coordination:AGENTS.md, STATUS,
TASK_QUEUE and [Codex's review](../reviews/G3D-P4-3366edf.md) with git show. Current
application main remains G3D-P3; no P4 implementation has been assigned.

Own only `docs/artifacts/AgentForge_Sentinel_G3D-P4_Development_Evaluation_Plan_2026-11-06.md` and your existing branch handoff.
Do not amend/rebase/reset3366edf, merge coordination/application branches, or edit code,
tests, protocol/cases, contracts/migrations, dependencies, limits or central coordination.

## R44: use the measured quantity's real definition

- Correct the measurements table and P4a/decision sections: request-wrapper timing is
  request latency, not exact internal workflow elapsed. The150s gate remains not
  measured/not demonstrated for this pilot. Do not choose a new persisted field or
  promise runner-only exact timing. An exact observer can be proposed separately later.
- Ordinary StepRecord.elapsed_ms is cumulative since t0; the terminal zero is a marker.
  Per-attempt matching of role_started and role_completed/role_failed by agent_run_id
  may yield a clearly labelled step interval, not automatically provider latency.
  Describe failed/missing endpoints and include persistence/validation caveats.
- Remove "worst-case pass time" claims. Distinguish C1's caller wait, CLI auth/subprocess
  lifetimes, C2's150s coordinator budget, request latency and actual end-to-end duration.
  Keep numbers provisional and unknowns honest; change no limit or frozen protocol.
- Existing capacity.snapshot exposes calls/peak_calls. Future tooling may observe this
  instance in memory; do not say peak state does not exist merely because reports omit it.

## R45: stopping preserves and scores the bad result

- A hold on D03/D04/D11 is a completed, unacceptable disposition under the frozen
  evaluator. Retain it and its attempt/latency/usage; update the pass to incomplete if
  stopping, and list future cases as not attempted. No exclusion, relabelling or rerun
  replaces that result. Distinguish quality failure from a typed request failure.
- D11 by itself cannot establish injection success or resistance; D02's history differs.
  Keep external_id-only scope and missing note/input observations explicit. Do not add
  a control fixture or edit the frozen catalog in this correction.

## Apply review decisions and operational clarifications

- Plan one pass on D01-D04/D11 external_id-only; no live permission and no pre-approved
  repeat. P4a comes before live use, with a later separately owned assignment. Defer
  fault-applying live harness and production instrumentation.
- Define the30 allowance in controllable units: worst-case app adapter/CLI-invocation
  reservations before each run (1 C1, up to5 C2), not a proven provider-request or
  billing cap. Stored attempts may never have reached the CLI/provider; failed auth,
  pre-submission refusal, unknown and late work need honest distinct accounting.
- Mark current command examples as templates until P4a supplies tested orchestration,
  or make the planned setup complete without executing it: use fresh owned worktree/
  state/DB/port, create .agent output directories and validate record.status and
  record.authorities.runtime_verified at their actual nested paths. Do not adopt/stop
  a pre-existing `.agent/devdb`; preserve recovery and verify pilot ownership.
- Read-only exports must be scoped and keep raw outputs private; evaluator expectations
  enter offline scoring only, never prompts or tools. Separate operator provisioning
  from runtime case work and explain export authority. Do not implement export tools now.

Check relative links, unchanged protocol/case/code bytes, clear units/denominators and
consistency of the plan's sections. Source-based checks or no-I/O examples are enough;
do not run full gates for docs alone. Record what was actually inspected and not run.
New commit: PHANI465 <pgavara1@asu.edu>, sole author AND committer, no trailers/history
rewrite. Return exact new SHA, R44/R45 resolution and remaining unknowns. No main merge,
provider/auth call, final-case generation/inspection, spending, external push or deployment.
