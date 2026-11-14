# DOC01 Part C review: 8bee376 (changes requested)

Reviewed November 13, 2026. Exact candidate:
`8bee376620aead6f44a090c7c2c3d7112f4a0291` on
`task/claude-doc01-ui`, based on accepted main `813b0db`. This review does
not accept or merge the UI. The candidate checkout was clean before and after
the independent checks. All four task commits have PHANI465
<pgavara1@asu.edu> as sole author and committer, with no trailers.

## Findings

### R64 — related success responses can be mixed (blocking)

`web/src/ui/DocumentReview.tsx:214-307` checks the handle on an analysis and
the handle, source hash and offset on a record page. It does not compare an
upload receipt's format/size with the selected file, an analysis's
`source.sha256`/size/format with the upload, or a page's status/total with the
analysis shown above it. A successful DELETE with `deleted: false` is also
presented as deleted. These are valid individual DTO shapes but contradictory
facts about the current document.

A temporary independent component probe used the frozen CSV examples and
three valid-shape changes: a one-byte selected file with a 547-byte receipt,
an analysis with the same handle but another 64-digit source digest, and a
page marked `partial` under a displayed `complete` analysis. All three
negative controls failed on their intended assertions: the UI showed the
receipt, the different-source result, and the mixed page. The probe file was
removed afterward. A second tab can legitimately replace a stored analysis
before the first tab pages, so the page mismatch is not only a malformed-body
scenario. The v1.3 page carries enough status/total fields to detect these
specific contradictions. A same-status, same-total replacement remains
unobservable without a version field and should not be claimed as a pinned
snapshot.

Refuse contradictory success bodies as unconfirmed, clear stale result/page
where a re-analysis may have changed storage, and add maintained component
tests. Verify the upload receipt against the chosen file, analysis against
the upload and submitted options, page against the displayed analysis, and
DELETE's handle and `deleted: true` before saying deletion succeeded.

### R65 — the document-token scan excludes stack artifacts (blocking)

`web/e2e/support/documents.ts:135-162` scans the document sessions' tokens
but excludes `runtime.stackDir` and `runtime.secretsPath`. It runs in
`web/e2e/documents.pw.ts:22-30` before shared teardown, while the stack still
exists. Shared teardown (`web/e2e/global-teardown.ts`) also excludes the
stack directory and scans the remaining artifacts for its own retained
stack secrets, not the three new document-session tokens. Thus a document
token written to an API log or other stack-owned artifact
would not be detected by either scan. Keep the expected stack secret file
protected from output, but scan stack artifacts for the document tokens. Add
a synthetic canary-token regression in a test-owned stack artifact; the scan
must report its relative path without printing the token.

An independent temporary Vitest control wrote a synthetic canary token into
an owned stack log while a test runtime record pointed to that stack. The
scanner returned `leaks: []`, and the control failed. It removed its runtime
record, log and stack directory afterward.

### R66 — store cleanup deletes unknown entries (blocking)

`web/e2e/support/documents.ts:117-133` checks that four known store
subdirectories are empty, then recursively deletes the whole marker-bearing
`doc-store`. It never checks for unexpected root entries, extra directories,
symlinks or files inside them. A canary under that path would be deleted by
`rmSync` while `storeLeftovers()` still reports all four known directories
empty. The assignment calls for verified cleanup with recovery evidence
preserved on uncertainty. Enumerate the exact expected store tree and refuse
cleanup if anything else remains; add a canary test that proves it survives.
An independent temporary canary control confirmed `removeVerifiedStore()`
returned `removed: true` with an unexpected file in the store root. The
control failed as intended and left no store behind.

## Evidence and scope

- `contracts/http/examples-v1.3/` has **29** files on `813b0db`, not the 31
  stated in the original Part C dispatch. The UI copied all 29 byte for byte,
  and the active OpenAPI digest matches the dispatch. Correct the dispatch;
  do not manufacture two examples.
- Independent `npm test`: **228 passed**. Independent real document browser
  suite: **12 passed** through production API, real worker and disposable
  PostgreSQL. Its store and run record were removed by the suite. The
  temporary R64 negative controls failed **3/3**, and the R65/R66 canaries
  failed **2/2** as described. All temporary probe files were removed; the
  candidate tree and runtime are clean.
- I inspected the desktop and 390-pixel screenshots. No separate visual
  blocker was found. The existing 19/10 browser suites and full Windows/
  native backend gates are author-reported, not independently rerun for this
  review. Application `src/`, contracts, worker, locks and CI are unchanged
  from main.

The UI has a useful baseline, including opt-in display, inert text, honest
unknown values and real browser proof. R64-R66 need correction on the
existing task branch before acceptance or main integration. No live model,
remote push, deployment or private-customer file was involved.
