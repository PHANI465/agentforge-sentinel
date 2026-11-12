# DOC01 Part A: independent review of cecccad

**November 12, 2026 — changes requested.** Reviewed exact
`cecccadfaad6f2cde0cd42543517685fa0235ea8` on
`task/claude-doc01-extractor`, based on main `4d60c53`. This is a review of
the local worker only. The candidate remains clean, unmerged and unpushed.

## Findings

### R58 — POSIX recovery discards a live process group (blocking)

`tools/document_worker/src/docworker/supervisor.py:489-525` checks only the
recorded **leader PID**. If that process has exited but a parser descendant
remains in its process group, `recover()` deletes the owned run directory and
the recovery record and returns `recovered`. The live member is then no longer
tracked. This contradicts the worker's confirmed-stop and recovery contract.

Independent native Ubuntu probe: a test-owned session leader spawned a sleeping
child in its own process group and exited. The child kept the same recorded
identity and group. The real `Supervisor.recover()` returned:

```json
{"report":"recovered","recovery_record_exists":false,"child_alive_after_recovery":true}
```

The probe stopped its own child by verified PID and start identity. Fix recovery
so it retains the record whenever group emptiness cannot be established. A
leader that has exited is not proof its group is empty. Do not signal a reused
process group on PID alone; a fail-closed/manual-recovery result is acceptable.
Add a real-process regression for leader-exited/member-alive, including a
fresh supervisor invocation and an ordinary successful recovery only after
the test-owned member exits.

### R59 — an invalid child success is accepted (blocking)

`supervisor.py:447-455` receives the child's exit code but does not use it,
and validates only three JSON fields. With a correct protocol and request ID,
the real supervisor returned `status: complete` for a child that exited **7**
and omitted the required `source`, `parser`, `units`, `records`, `findings`,
`typed`, `measures`, and `coverage` fields. Independent native probe result:

```json
{"status":"complete","exit_code":7,"errors":null,"records_present":false}
```

The frozen worker protocol says exit 0 accompanies a written extraction result
and defines the result fields. Reject a nonzero exit masquerading as success,
and validate the required result structure and status consistency before
returning a successful extraction. Keep error reporting free of document bytes
and secrets. Add regressions for nonzero success, missing required fields and a
valid child response.

## Scope and evidence

- Independent existing supervisor suite: **15 passed on Windows and 15 passed
  on native Ubuntu** at the exact candidate. These tests do not cover R58 or
  R59. No full product gate was rerun for this review.
- The author's final-commit report lists worker tests **128 passed, 0 skipped**
  on each platform, a 21-run fixture smoke plus two cap probes on each, and a
  Windows application strict gate of 810 passes plus one allowed skip. These
  are author evidence, not independent acceptance of the two missing cases.
- The three commits have PHANI465 as sole author and committer and no trailers.
  Changed paths are limited to `tools/document_worker/**`, the worker protocol
  document and the branch handoff. Application source, contracts and locks are
  unchanged. The candidate's disclosed lack of OS network isolation and the
  Windows filesystem guard limit are retained as explicit gaps, not new
  acceptance claims.
- No main merge, remote push, provider call, upload feature or full-size AN01
  measurement was performed in this review.

**Next:** correct R58/R59 on the existing DOC01 branch, preserve `cecccad` and
its test evidence, then hand off a new exact SHA for re-review. The focused
[correction assignment](../prompts/CLAUDE_DOC01_REVIEW_FIXES.md) is the current
dispatch; the original Part A assignment is delivered history.
