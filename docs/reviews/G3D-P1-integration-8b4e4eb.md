# G3D-P1 integration 8b4e4eb: held for R43

November 2, 2026. Evaluator dddd0b4 is accepted; R41/R42 close. This is a separate
integration finding in an existing fixture, not a regression in agent_eval.py.

## Candidate and results

Main/coordination05b9df7 merged dddd0b4 cleanly as cc9f599af8cb6334d368d630f6f38a09233d1a6c.
Codex added the accepted review and test-only ingestion-reference correction in
**8b4e4ebea6cd317812a36f9f7a667452eee0de3a**. Both new commits are solely authored and
committed by PHANI465 <pgavara1@asu.edu>, no trailers or rewritten history.
Production src, evaluator script, contracts, UI, models/data and lockfiles match dddd0b4.

| Exact 8b4e4eb gate, Windows then native | Windows | Native Ubuntu WSL |
| --- | --- | --- |
| Strict commands | 6/6 pass | 5/6 pass; pytest fails |
| Backend | 634 passed, one allowed skip | 633 passed, one failure, one allowed skip |
| JUnit | same-run635 cases, structured gate exit0 | same-run635 cases, failure preserved |
| HTTP / read-only ML | pass / reproduced:true | not run after strict failure |

Windows strict took1622s (pytest1522s); native strict422s (pytest409s). Parent Windows
monotonic sequence proves the runs did not overlap. No unchanged native full rerun.
No new browser run: production/UI/fixture bytes are unchanged so far. The fixture
correction must check its actual browser consumers before integration resumes.

## R43: fixture current time can hit the wrong production guard

At tests/test_model_browser_fixtures.py:152, the missing-profile POST got422
future_event_time instead of account_profile_missing. tests/support/scenarios.py:_model_body
uses seed-process now as occurred_at; service.py:ingest rejects a future event before
looking up its profile. The failed run did not preserve a paired clock observation.
The known WSL realtime jumps make a mismatch plausible, but this run does not prove a
specific jump occurred. Do not relabel the failure as random load or claim more evidence.

A separate controlled probe invokes the real restricted runtime service and disposable
Postgres: with matching clocks, the intended missing-profile error occurs; with an API
clock3s behind fixture time, the assertion fails with exactly future_event_time.
Both cases leave transactions/outcomes/alerts/cases empty. The system clock is untouched.
This proves the fixture precondition defect under finite relative skew.

Correct fixture event times, not the production guard. Review all model fixture POSTs
and replays. If using a historical margin, keep profile opening time exactly400 days
before the transaction so every accepted input/score remains identical. Preserve IDs,
model pins, threshold, causal disclosures, authority, rollback and browser lifecycle.
No sleeps, accepted alternative error, weakened assertion, new skip or timeout change.
[Exact Claude assignment](../prompts/CLAUDE_G3D_MODEL_FIXTURE_CLOCK.md).

## Other completed integrator work

The old C05 concurrent-ingest reference is deterministically reproduced failing on a
valid equal-ingestion-timestamp schedule. The corrected test tracks earlier decisions,
not timestamp order alone, and runs native/tied clocks. An explicit arrival-order guard
expects[0,0,1,3] with unchanged replay. All21 focused reliability checks pass. Two
mutations are caught: exclusive ingestion produces[0,0,0,0], inclusive event time
produces[0,0,2,3]. Runtime scoring is unchanged. Its first harness draft counted audit
clock reads too; the two failed checks are retained, then fixed to track first reads.

## Evidence and state

Canonical ignored archive .agent/g3d-p1-integration/8b4e4eb/ holds Windows pass,
native failure, sequence and cleanup. .agent/g3d-p1-review/dddd0b4/ holds independent
review, original author records, reference/mutation and relative-clock probes.
Native originals remain ~/codex-g3d-p1-release-reports/. Both systems have no test-owned
PostgreSQL/Sentinel API left; no uncertain process was killed. Main application stays
G3C; only coordination documents are published. Cursor's exact seven edits and all
candidate/review checkouts remain preserved. No provider, CI, hosting or quality claim.
