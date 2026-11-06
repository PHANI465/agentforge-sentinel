# G3D-P2 local integration: November 6, 2026

Independent acceptance: candidate **61cc4b44d0b6dcdf15664be96ecf2cfd96048c4c**;
[review](../reviews/G3D-P2-61cc4b4.md). Tested clean integration
**5a1776be20a85124705a893c81b142384e31d67b**, task/codex-g3d-p2-integration,
E:/PHANI/sentinel-wt/codex-g3d-p2-integration. Parents are published main d3b6aff and
candidate 61cc4b4; merge was conflict-free. The integration adds only the independent
review and its handoff beyond the candidate. All candidate test/runbook bytes match.
Production src, scripts, contracts, migrations/grants, UI, model/data/evaluation assets,
dependencies and locks match prior published main. Owner is sole author and committer;
new commit messages have no trailers and existing history is preserved.

## Independent evidence

| Exact integration check | Windows | Native Ubuntu WSL2, sentinel |
| --- | --- | --- |
| Six-command strict gate | 6/6 pass | 6/6 pass |
| Complete backend | 649 passed + one allowed live-Claude skip | 649 passed + one allowed live-Claude skip |
| Same-run structured JUnit/skip validation | 650 cases, exit 0 | 650 cases, exit 0 |
| Frozen HTTP export | pass | pass |
| Packaged install/inference | pass | pass |
| Read-only ML reproduction | true | true |
| New frontend/browser run | not run: tests/docs only | not run |

The full Windows sequence ran 2026-11-06T18:17:06.470347+00:00 to
2026-11-06T18:45:09.618853+00:00; native started only after Windows completed, at
2026-11-06T18:45:42.953263+00:00, ending 2026-11-06T18:53:35.958296+00:00.
Each parent waits for subprocess completion before starting the next phase. Clean
before/after snapshots name the exact integration SHA and all six exit codes are zero.
JUnit is from the strict helper's own pytest process; no second full pytest was used
for validation. No command exceeded the owner-approved 2700-second individual-command
budget. All application/test/SQL/HTTP deadlines and skip policy are unchanged.

Independent candidate review first passed 92 focused Windows tests, then four controls
confirming actual runtime identity/privileges, baseline empty workflows and precise
count/content assertion failures on damaged restored copies. The new suite proves seven
workflows, 20 runs, 128 steps, all-table stored content, null/usage provenance, old/new
workflow selection and scope denials, read-only overdue traces, explicit recovery and
one approved simulated action across retry. The old backup scenario remains unchanged.
Claude's inspected full-candidate Windows/native results are separately attributed in
the review; they are not substituted for these independent integration runs.

P1's Windows frontend133 and browser19+10 remain prior results at aa5ee1e, not new
G3D-P2 runs. The pinned Starlette/httpx deprecation warning remains non-blocking.

## Publication and retained evidence

The later publication commit changes documentation only. Its protected application,
scripts, tests, fixture, UI, model/data and lock bytes equal this tested integration.
After that publication, check the changed-document links, diff, owner metadata, source
equality and clean tree; do not call an old strict report an exact-publication-HEAD pass.
The canonical main checkout's own stale strict report is not overwritten with evidence
from another worktree. Exact full-run certification belongs to the worktrees above.

Independent Windows/native copies: integration `.agent/g3d-p2-integration/windows/`
and `native/` (all copied report SHA256 hashes match untouched originals); native originals: `/home/sentinel/codex-g3d-p2-integration-reports/`.
Focused/probe evidence remains in the review worktree `.agent/g3d-p2-review/` and
canonical ignored `.agent/g3d-p2-review/`. Author originals and all earlier failures
remain untouched. No test-owned database/API process is left on either platform; unrelated
services and accepted worktrees are preserved. Cursor's exact seven saved file hashes
and original HEAD remain equal to the pre-integration snapshot.

## Limits and next step

Same-cluster restore reuses/re-grants the existing runtime role; a new cluster needs
role provisioning and has not been tested. Private temp dumps remain synthetic backup
artifacts containing session hashes, never raw tokens. The new module calls native
pg_dump/pg_restore; the unchanged operator rollback drill covers helper processes.
This proves recoverable stored history, not live agent quality or production capacity.
No live provider, final-case evaluation, spending, remote/push or deployment occurred.
Linux browser, macOS, real CI, hosting/public BYOK and capacity remain unverified.
Next is the separate three-role operator helper in a future assigned task; no live
evaluation is assigned. Preserve all prior failure records and accepted components.
