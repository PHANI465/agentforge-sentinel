# DOC01 Part B: local upload and deterministic feedback API

Recommended coding assistant: **Claude Opus 5.5 / High**. This slice crosses
the HTTP contract, session authority, bounded upload bytes and the separately
locked worker's process lifecycle. Keep Sentinel's investigators deterministic;
no provider or model call is part of this task.

## Dependency and ownership

Read current `task/coordination:AGENTS.md`, STATUS, TASK_QUEUE, the
[Part A acceptance](../reviews/DOC01-8f7bd87.md), the
[worker protocol](../documents/DOC01-worker-protocol-v0.1.md), and the
[local upload proposal](../documents/DOC01-local-upload-proposal.md) with
`git show`. Start a new `task/claude-doc01-upload-api` worktree from the exact
accepted main SHA named in the current queue, including Part A. Preserve the
original DOC01 and AN01-M1 worktrees and Cursor's seven edits. One editor in
this worktree. This task does not integrate or alter the AN01-M1 candidate.

The active public contract is v1.2. **DOC01 owns the next additive v1.3**;
AN01's earlier *provisional* v1.3 label moves to v1.4 or later when its report
API is actually assigned. Do not edit frozen v1/v1.1/v1.2 snapshots or their
examples. Record the contract-order decision and compatibility effect, and
freeze v1.3 DTOs/examples in a commit before implementing the route. A
contract change is part of this assignment, not permission to change the
accepted p1 model or existing case/action shapes.

## Deliver the backend path

Build a local-only, opt-in browser-compatible upload and analysis API over the
accepted Part A worker, with no raw customer files and no hosting claim:

`browser/raw file bytes -> authenticated API -> owned session handle ->
separately locked worker -> typed feedback and evidence locators`.

- Use a raw binary request with an explicit allowed format instead of adding
  a multipart dependency unless a concrete reason requires it. Stream and
  cap bytes before the full body is buffered; never derive a filesystem path
  from a filename, handle, URL or document text. Allow only text-layer PDF,
  UTF-8 CSV and XLSX. Apply Part A's content/sniffing and expansion bounds.
- Add an **opt-in** `analyze_document` capability to session creation and
  server validation while leaving the four default grants unchanged. A
  missing capability returns 403; a missing, expired or foreign handle has
  one indistinguishable not-found response. The UI will ignore unknown
  capability strings in older sessions, as it already does for other opt-ins.
- Use a configured, registered local worker environment and marker-owned
  store. Never import worker dependencies into the app's runtime or accept a
  worker executable/path from an HTTP caller. Fail closed when the worker or
  store is unavailable. No change to the app lockfile without a separately
  justified compatibility review.
- Define the result transport deliberately. The worker can emit roughly
  12 MiB at its row cap; avoid an unbounded HTTP response. Preserve typed
  integer-string money, currency separation, unknown/partial/unsupported
  states, source hash, parser versions, evidence IDs, page/sheet/row locators,
  coverage, missingness, duplicates and reconciliation. Show denominators;
  never present extraction findings as a fraud verdict or calibrated score.
- Keep upload and analysis separate from accepted transactions, cases,
  approvals and simulated actions. No document text may invoke a tool,
  request investigation, approve or execute. No model receives the file.
  Tokens stay in memory and out of paths, logs, errors and artifacts.
- Bound API-to-worker launch, output, cancellation and cleanup. An uncertain
  stop retains a recovery record and blocks unsafe reuse. Before exposing
  this path, resolve the Part A Windows `_write_record`/`os.replace` sharing
  conflict follow-up: reproduce the failure, avoid orphan `.tmp` records,
  and keep a failed/uncertain worker from being reported as a successful
  extraction. Do not hide the earlier intermittent crash-test failure.

## Prove the implementation

Use failing-first tests for the wire contract, capability/session separation,
oversize and wrong-format refusal, tampered/expired/foreign handles, malformed
and partial documents, worker unavailable/timeout/uncertain cleanup, bounded
response, unchanged action boundary and exact feedback arithmetic. Include a
real-process run through the production API, the separately locked worker and
disposable Postgres; verify a restart, cleanup and zero leaked secrets.
Worker tests and smoke are separate from the app gate; run both explicitly.

Own only DOC01's backend, worker, contract/examples, focused tests, security/
API/document docs and branch handoff. No frontend, AN01 report code, p1/data
pipeline/model files, CI weakening, paid use or live provider. Do not merge or
push the task branch. Run exact clean-commit strict Windows and native gates
serially, structured skip validation, HTTP export and read-only ML reproduction;
retain failures and diagnose before a justified rerun. Report exact SHAs,
fixture hashes, versions, actual results, cleanup and limits. New commits:
PHANI465 <pgavara1@asu.edu> sole author and committer, no trailers and no
history rewriting. Codex reviews Part B before the UI slice begins.
