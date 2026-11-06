# G3D-P1 final local integration: November 5, 2026

Tested clean commit **aa5ee1e124c4163c124d33a9cb036fadf510b397**, task/codex-g3d-final-integration. Current coordination is
merged with accepted 6e461c0 (evaluator dddd0b4 and reference 8b4e4eb included). Four later
coordination conflicts retain current main history and owner approval. No runtime conflict
or new product fix was introduced. All runtime/test/fixture/UI/model/data/lock bytes match
accepted 6e461c0. Only checker comments and its global command cap differ outside documents.
Author and committer: PHANI465 <pgavara1@asu.edu>, no trailers or history rewriting.

| Exact-commit verification | Windows | Native Ubuntu WSL2, sentinel |
| --- | --- | --- |
| Strict checker |6/6 pass |6/6 pass |
| Full backend |647 pass + one allowed skip |647 pass + one allowed skip |
| Same-run JUnit/skip gate |648 cases, exit0 |648 cases, exit0 |
| Frozen HTTP, packaged install, read-only ML |pass |pass |
| Frontend typecheck/unit/build |pass,133 tests |not run |
| Real legacy/trace browsers |19 /10 pass |not run |

The pinned Starlette/httpx test client emits a deprecation warning on Windows. All
tests pass; dependency migration is a separate maintenance task and no lockfile changed.

The parent waits for each subprocess to return before launching the next. Its monotonic
sequence is nondecreasing at adjacent phase boundaries, which can share a Windows clock
tick, with positive duration for every phase. Both source trees stayed clean. JUnit
comes from each full strict run itself. The package check verifies five migrations and
eight model/data assets plus isolated installed inference. ML reproduction reports true.

## Approved command budget and preserved failures

At b246145, first Windows pytest reached 506 of648 progress markers before1800 seconds;
one controlled rerun after owner-reported app closure/charging reached 637. Neither emitted
an assertion failure before cutoff; neither has a complete JUnit. Other five commands
passed each time. The 11 unreached cases passed separately, never counted as a full gate.
Native647+one skip and Windows UI 133/browser 19+10 also passed on that earlier candidate.

The owner then explicitly approved 2700 seconds (45 minutes) per verification command.
See [decision0009](../decisions/0009-verification-command-budget.md). All commands, test
assertions, case/agent/SQL/HTTP deadlines and skip policy remain unchanged. This provides
additional finite verification budget; it does not establish the slowdown's cause,
fix hardware or prove production capacity. Original reports remain failed and archived.

## Publication, cleanup and limits

The later publication commit changes documents only. Its application bytes equal this
tested commit; no separate exact-HEAD full pass is claimed for the documentation update.
Evidence is archived at `.agent/g3d-approved-budget/aa5ee1e/`; earlier b246145 failures
remain under `.agent/g3d-final-integration/b246145-held/`. Native originals are in
`~/codex-g3d-approved-budget-reports/`. Owned test databases/APIs and browser secrets/recovery
state are gone. The unrelated Windows PostgreSQL service and idle Ubuntu shell were left
alone. Accepted components and Cursor's seven saved edits remain unchanged.

All data synthetic and actions simulated. No live provider/final-case quality comparison,
paid usage, GitHub Actions, Linux browser, macOS, hosting, public BYOK or capacity result.
Existing PID check-to-signal, PostgreSQL realtime, finite fixture-clock margin and operator
limitations remain. No remote, push or deployment. Next is populated-workflow backup proof.
