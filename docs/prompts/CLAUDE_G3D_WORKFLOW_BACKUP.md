# G3D-P2: prove backup/restore with populated multi-agent workflows

Recommended coding assistant: **Claude Opus 5.5 / High**. This is a bounded persistence
and authority task with real PostgreSQL, scope checks and read-only trace semantics.
Sentinel's investigators remain deterministic; no provider call or --allow-live.

## Accepted base and one editor

Read current task/coordination:AGENTS.md, docs/STATUS.md, docs/TASK_QUEUE.md, the G3D-P1
release record and docs/reviews/G3D-P1-dddd0b4.md using git show. P1 is accepted and
integrated; do not repeat R41/R42/R43 or work in its preserved checkout.

Create task/claude-g3d-workflow-backup in
E:/PHANI/sentinel-wt/claude-g3d-workflow-backup from current published main. Record its
exact SHA and confirm it contains accepted G3D-P1 integration aa5ee1e124c4163c124d33a9cb036fadf510b397.
The future documentation head need not equal the tested integration SHA. One editor;
preserve all reviewed checkouts and Cursor's original seven saved edits.

Read tests/test_backup_restore.py, existing workflow/trace tests and support fixtures,
the accepted runtime role map, docs/runbooks/local-operations.md and the frozen v1.2
trace contract. Reuse production service/coordinator code rather than manufacturing
workflow records or serving fake HTTP responses.

## Deliver one concrete persistence proof

The current backup test inventories agent_workflows and agent_steps but leaves them
empty. Add meaningful coverage that fills both tables, backs up with real pg_dump -Fc,
restores into a new test-owned database and compares the actual stored workflow history.

- Include a completed multi-role workflow with nontrivial role/claim/tool/transition
  records, and an inconclusive or recovery ending. Use deterministic adapters and
  genuine coordinator transitions. If a running/overdue case is included, a trace GET
  after restore must remain read-only and must not silently recover it.
- Provision sessions/operator-only data as operator; seed case data and investigate as
  the restricted runtime role. Read restored case/trace through the real production API
  under that role. Use the same session token without printing or persisting it in any
  tracked artifact. Confirm case/workflow selection and scope denials survive restore.
- Compare workflow/run/step counts AND persisted content, including IDs, revisions,
  pins, ordered seq steps, dispositions/failures, usage provenance and trace nulls. A row
  count alone cannot show a faithful restored investigation. Compare read_at separately:
  it is a read timestamp, not a persisted field that must be identical across requests.
- Retain the existing exact 16-table inventory, migrations/no-pending-migration checks,
  audit update/delete protection and existing single-investigator backup scenario.
- No approval or action is created merely by backup, restore or a trace GET. Preserve
  the human boundary and replay safety. If testing execution after restore, use a real
  approval and one execution key; verify exactly one simulated action across a retry.
- Keep trusted owned database/dump paths, safe parameter handling, normal cleanup on
  failures and original failure evidence. Do not add live routes, schema/grant changes,
  process killing by name or broad filesystem deletion.

## Owned paths and limits

Own a new tests/test_workflow_backup_restore.py, narrow improvements to
tests/test_backup_restore.py if needed without weakening its existing checks,
docs/runbooks/local-operations.md (add the actual verified procedure/scope), and your
branch handoff. Reuse existing support modules without editing their lifecycle code.
Keep central STATUS/TASK_QUEUE with Codex.

Do not edit production src, scripts/local_stack.py or agent_eval.py, contracts, migrations,
role grants, models/data/evals/protocols, UI, dependencies/lockfiles, CI, skip policy,
timeouts or accepted case fixtures. The three-role local_stack choice is a separate
future task. Request a concrete change with evidence if the accepted runtime genuinely
cannot support a required test; do not widen scope preemptively.

## Evidence and handoff

Before implementing, demonstrate the missing assertion: the current round-trip test has
zero workflow/step rows. New tests should fail meaningfully if either workflow table's
dumped content is absent or altered. Keep a negative-control result (for example an
isolated restored copy missing one stored step) proving content checks catch the loss;
do not delete source data or disable assertions to make a pass. State clearly what
failed on the baseline and what is a new guard, rather than counting import errors.

Run focused backup/workflow/trace tests. Then commit explicit owned paths as
PHANI465 <pgavara1@asu.edu>, sole author AND committer, no trailers or history rewriting.
Run the required exact-clean-commit Windows then native Ubuntu backend gates sequentially,
capture JUnit from the same full run and apply the exact skip gate, frozen HTTP export
and read-only ML reproduce. No browser rerun is required solely for test/doc changes;
say it was not run. Preserve and diagnose failures; no blind rerun-until-green.

Return exact SHA/base, populated counts and content checks, authority evidence,
negative-control result, actual gates, cleanup and limits. No main merge, remote/push,
deployment, live comparator, final-case generation/inspection or paid usage. Codex reviews
before integration. This task proves recoverable stored history, not live agent quality.

Current verification-command budget: owner-approved 2700 seconds (decision0009). Keep
all individual assertions/deadlines and skip policy. Existing failure evidence remains.
