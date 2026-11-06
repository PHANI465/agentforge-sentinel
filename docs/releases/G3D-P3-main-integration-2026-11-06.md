# G3D-P3 local integration: November 6, 2026

Candidate 2cdb3b73975511da4bd4551ee828505953c621f0 accepted under [the independent review](../reviews/G3D-P3-2cdb3b7.md).
Tested integration **495c7d33424054d27d68d08004191d4be37adaf9** on task/codex-g3d-p3-integration has parents
f45c70347b8969d8bb8579ce95e644928d70611e and 2cdb3b73975511da4bd4551ee828505953c621f0. The merge was conflict-free. Beyond the candidate it adds
the review/handoff and two runbook wording corrections; scripts/tests match the
candidate exactly. Production src, frozen contracts, migrations/grants, agent engine,
models/data/evals, UI, dependencies/locks, CI and check deadlines are unchanged.

## Independent exact-integration evidence

| Check | Windows | Native Ubuntu WSL2, sentinel |
| --- | --- | --- |
| Six-command strict gate | 6/6 pass | 6/6 pass |
| Complete backend | 666 passed + one allowed live-Claude skip | 666 passed + one allowed live-Claude skip |
| Same-run JUnit / exact skip gate | 667 cases, exit0 | 667 cases, exit0 |
| Frozen HTTP export | pass | pass |
| Packaged install/inference | pass | pass |
| Read-only ML reproduce | true | true |
| New frontend/browser run | not run: helper/tests/docs only | not run |

Independent review first passed32 tests in129.22s and nine configuration probes in0.36s,
with Ruff. Claude's inspected candidate666+one skip/platform is separately attributed;
the integration runs above are independent executions. All new commits use
PHANI465 <pgavara1@asu.edu> as sole author and committer, without trailers or history rewriting.

The single Windows parent awaited each phase: Windows 2026-11-06T21:30:41.445120+00:00
to 2026-11-06T22:00:02.435349+00:00; native 2026-11-06T22:00:02.440350+00:00
to 2026-11-06T22:08:10.605086+00:00. Sources were clean before/after. XML comes from
the strict helper's same pytest process; no second full run was used just to obtain XML.
No individual test, application or SQL deadline/skip was relaxed; cap remains2700 seconds.
The package checker retains its existing network behavior; no new paid service is used.
Prior P1 frontend133/browser19+10 are dated prior results, not new P3 verification.

## What the helper now proves

`up --investigator three-role` launches deterministic analyst/investigator/reviewer
roles. `--agent-adapter claude-cli` requires explicit selection, remains local-only,
and was tested by intercepted configuration only. Implicit deterministic modes ignore
ambient live selections. An explicitly selected live mode reads its model setting once
and records it. API restart preserves those settings and the original case pins.
Missing configuration refuses a restart before work, without blocking owned shutdown.
Repeat-up mismatches refuse before database setup. The API still connects as runtime.

Real-stack tests show the persisted workflow/roles/steps and trace, zero actions or
approvals before the approval phase, unchanged trace/pins after restart and exactly one
simulated action across an explicit synthetic approval/execution and retry. This is an
automated operator test, not a claim of a browser human click or live-agent quality.

## Publication, cleanup and limits

The later publication changes docs only. Its protected script/test/application bytes
equal this tested integration; no extra full strict run on the publication HEAD is
claimed. Main's local stale check record is not overwritten with another worktree's
report. Exact evidence lives in integration `.agent/g3d-p3-integration/`, with native
originals `/home/sentinel/codex-g3d-p3-integration-reports/`. Canonical ignored archive
`.agent/g3d-p3-integration/495c7d3` retains matching report copies and phase records.
Independent probes are archived separately. Original author/failure reports are kept.

No test-owned PG/API remains. Unrelated services, accepted worktrees and Cursor's seven
saved edits are preserved. Ordinary native Ubuntu operator start/status/smoke/restart/down
is now exercised. The separate POSIX orphan and PID-check-to-signal limits remain,
and macOS is untested. Live configuration was not executed; no provider account was used.
The helper's existing stopped-stack database-port reuse is unchanged. Same-cluster
workflow backup is already proven; fresh-cluster role provisioning remains unverified.
GitHub Actions, Linux browsers, public BYOK/hosting, live quality and capacity remain
unverified. No live/final-case evaluation, new spending, remote/push or deployment.
Next is measured agent/security evaluation planning, followed by analytics and public operations.
