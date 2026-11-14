# DOC01 Part B: local document API integration

**Accepted candidate:** `d6d509e555d41638e24050f99bd8e53e1d7f3732`
([independent review](../reviews/DOC01-B-d6d509e.md)). **Source merge:**
`e51f47aa21606425e132afc05ac19a3bd145099d`, first parent main
`0dd848e`, second parent the accepted candidate. The automatic merge had
no conflicts, and the merge tree is byte-identical to the candidate.
PHANI465 <pgavara1@asu.edu> is sole author and committer of the merge,
without trailers. Main fast-forwarded to that tested merge. Nothing was
pushed or deployed.

## Delivered

An opt-in, local HTTP v1.3 document API for public or synthetic CSV, XLSX
and text-layer PDF. It uploads raw bytes, analyses through the separately
locked DOC01 worker, pages typed records and deletes a handle. The worker
source is checked at every bridge call. Session-scoped handles expire after
one hour; missing, foreign, malformed and expired handles share one 404.
The API returns exact extraction/coverage/reconciliation measures, not a
fraud verdict or authenticity claim. No document route creates a
transaction, case, approval or action. The browser document UI is a later
slice.

## Independent and combined checks

Before merging, Codex reran the earlier real-process R62 probe: the fresh
API service counted a bridge owned by a live second process as `kept: 1`
and `pending: true`, without signalling either process. The focused Windows
candidate run passed **131 tests**. The real API, real worker and disposable
PostgreSQL run passed **32/32** and cleaned up. These are independent of
Claude's candidate gates.

The exact merge received sequential Windows and native Ubuntu full gates:

| Check | Windows | Native Ubuntu (WSL, `sentinel`) |
| --- | --- | --- |
| Six-command strict gate | 6/6, clean tree | 6/6, clean tree |
| Full backend suite | 941 passed, 1 allowed skip; 1742 s | 945 passed, 1 allowed skip; 550 s |
| Same-run JUnit and exact skip validator | 942 cases, 0 failures/errors; exit 0 | 946 cases, 0 failures/errors; exit 0 |
| HTTP export | v1.3 reproduced; v1/v1.1/v1.2 frozen | same |
| Read-only ML reproduction | `reproduced: true` | `reproduced: true` |
| Package check | wheel/sdist pass | wheel/sdist pass |

The backend counts differ by four because the POSIX-only R62 process
classification tests are defined only on native Linux. The sole skip on
each platform is the opt-in live-Claude smoke test. Application dependencies,
model/data artifacts and the frozen earlier HTTP contracts were unchanged.

On the merge, frontend typecheck and build passed, **133 unit tests** passed,
and both existing real browser suites passed: **19 legacy + 10 trace**.
Those suites exercise the existing UI against the integrated API; they do
not cover a document upload panel. Browser stacks stopped with an empty
`web/e2e/.runtime/stacks` directory. No native test PostgreSQL process
remained. The Windows and native reports are private/ignored in the
integration worktree and `/home/sentinel/codex-doc01b-reports/`.

## Preserved failed certification and rerun

The first Windows integration gate ran all six checks successfully, but the
strict checker marked the tree **CHANGED**. The `PYTEST_ADDOPTS` path used
Windows backslashes, which pytest's argument parsing removed, so it wrote
an untracked JUnit file into the checkout. That report was moved to E:
under `sentinel-tmp` for preservation. No source changed. The gate was
rerun once on the same merge with a forward-slash report path; all six
checks and the clean-tree condition passed. Its own JUnit file is the one
validated above. The first gate's log remains under the integration
worktree's ignored `.agent/doc01b-integration/`.

The first incremental Git bundle for native testing required `0dd848e`;
the new native clone did not have that object because it had been cloned
from an older detached checkout. A complete, SHA-256-verified bundle was
used instead. No native test ran before the correct merge was checked out.

## Limits and next work

The API remains local, opt-in and for public/synthetic files. There is no
document UI, OCR, typed PDF table extraction, OS-level network isolation,
per-session upload quota, hosting or private-customer-data claim. An
unresolvable launch intent without PID needs operator inspection. Busy
state remains per API process. The first recovery pass can refuse one
analysis while another bridge call is active; it does not alter a running
call. These limits are described in the [API contract](../api/documents-v1.3.md)
and [security note](../security/DOC01-document-upload.md).

The next task is a separate document review UI with real browser → API →
worker → disposable PostgreSQL proof. AN01-M1 remains accepted for its
prototype behavior but unmerged; its full-size timing and disk limits are
not demonstrated. No live provider or final-case evaluation was run here.
