# Sol dispatch: document insights and comparison release

Coding assistant: **GPT-6.1 Sol / High** for every slice, per owner request.
This is a coding setting, not a change to IAF's production model.

## Start from the foundation, not an older application branch

Read `task/codex-document-insights-foundation:AGENTS.md`,
`docs/START_HERE.md`, `docs/documents/INSIGHTS-ROADMAP-2026-11-15.md`,
`docs/handoff/CODEX-document-insights-foundation.md`, and this prompt with `git show`.
Inspect current main, task/coordination and the foundation branch read-only. The foundation
is based on application `4bff7e12ca7d6eeaeca5061531d9011902038513`. Resolve and record
the full foundation tip SHA and clean status before creating your branch. If it moved,
read the new handoff rather than guessing. Foundation is a library, not a deployed feature.

Create `task/sol-document-insights` in `E:/PHANI/sentinel-wt/sol-document-insights` from
that exact foundation tip. If that worktree already exists, inspect it and resume its
handoff; do not overwrite or recreate it. One editor. No subagents are required or assigned.
Preserve the original Cursor checkout and all other accepted/task worktrees.

Complete roadmap S1-S5 in dependency order. Do not merely restate the plan or stop after
adding a landing-page mockup. You can make reversible implementation decisions inside the
boundaries below. Keep live public capability labels aligned with working features.

## Scope and ownership

Own `public_site/` except frozen replay data/vendor bytes, new documentation under
`docs/documents/`, `docs/ui/`, `docs/handoff/`, and sample generators/tests under
`public_site/`. Read the existing public browser tests and original frontend/hosted smoke
commands before changing behavior. Keep reproducible source credits/licenses.

Do not change production `src/`, frozen HTTP/agent schemas, p1/model/evaluation data,
database grants/migrations, local DOC01 worker/API, `hosting/vercel/` runtime or provider
configuration, CI/timeouts/skip policy, dependency lockfiles, STATUS/TASK_QUEUE, or other
people's worktrees. No main merge, push, deployment, paid calls, consumer-auth relay or
private financial uploads. Small new dependencies require a concrete necessity/license/
size/security justification before changing the allowed paths; prefer the existing stack.

## Delivery sequence

1. **S1: extraction and statement insights.** Add adapters from actual PDF/XLSX/DOCX
   content into the new evidence boundary. Preserve coordinates and hash source bytes.
   Handle documented header/locale variants and multi-page tables; abstain on ambiguity.
   A monetary currency must be supported by source context or an explicit user correction.
   Create separate account/period scopes. Use Web Workers and generation fences.
   Connect printed-summary reconciliation to the public results with a clear scope label.
   Distinguish printed-summary checks from complete-row checks. Add real file regressions
   for the header variant and the 1,000 + 500 - 200 versus 900 example.
2. **S2: findings and capability catalog.** Implement the roadmap UI and `capabilities.html`.
   Build the catalog from a shared registry used by the checks/tests where practical.
   Show required evidence and limitation for each detector. Use passed/flagged/inconclusive/
   not-applicable/not-run honestly. No unsupported inference from a missing field.
   Add ordinary financial summaries so a clean document still yields useful information.
3. **S3: complex samples.** Generate the roadmap's synthetic scenario families with normal
   paired controls, manifest/hashes and separately maintained expected answers. Include
   PDF, XLSX and DOCX. Keep fixtures below existing limits. Use deterministic financial
   source records, inspect rendered documents, and verify through the real browser parser.
   Keep existing Treasury originals unchanged; additional official sources require reuse
   checks and provenance. Never put expected labels into detector input or branch on a
   sample filename/hash. Public educational answer keys are display-only.
4. **S4: local packets.** Add bounded multi-file selection and explicit matching of invoice,
   purchase order, delivery, payment and trusted baseline records. Introduce a documented
   typed packet schema, not overloaded statement-summary fields. Implement D04, D06-D10
   when required inputs exist; near-duplicate heuristics may remain Planned until measured.
   Distinguish repeated copies, installments, credits/reversals and currency differences.
   No automatic payment, fraud verdict or summing overlapping discrepancy amounts.
5. **S5: finish and verify.** Accessible source viewer, metric tables, purposeful charts,
   a compact relationship diagram and capability-linked sample gallery. Keep public
   document review, synthetic casework and IAF clearly separate. Update public README,
   privacy wording, UI guide and your handoff; record remaining limits candidly.

Optional remote AI is **designed, not activated**. Do not use the existing IAF key/endpoint
for documents or bypass local-only promises. You may implement an explicit local export
of selected findings for a visitor to paste into their own subscribed assistant, with a
preview and no automatic send. No remote request or raw financial text in a link.

## Foundation rules that must remain true

- `document-evidence.mjs` v1 is statement-summary evidence only. Keep its old tests and
  semantics. New types/checks are additive/versioned and tested; do not weaken validation.
- Financial arithmetic uses decimal strings/integer minor units. Never coerce missing
  values to zero, merge currencies, invent dates or treat a checksum as account ownership.
- Raw text, embeddings, model output and a user's asserted digest are not trusted server
  evidence. No remote service is part of these slices.
- Real files must exercise detectors. JSON-only tests do not establish format support.
- Every source hyperlink resolves to a known local evidence record. Source text is inert;
  no model-generated URL, macro, formula, HTML or remote document relationship executes.
- Replacing a review invalidates old tasks/results; cancellation alone is insufficient.
- No persistent browser storage, upload, analytics content or logged filenames/account data.

## Verification and handoff

First run the foundation and existing invoice tests:

```powershell
node --test public_site/tests/document-evidence.test.mjs public_site/tests/invoice-review.test.mjs
```

Add meaningful parser/detector/negative-control tests as implemented. Run the public site
browser suite against actual files and the new packet flow, with request monitoring,
malformed/oversize files, unsupported layouts, hostile text, cancellation and stale results.
Use existing installed Playwright modules from the preserved public-site worktree if needed;
do not copy its node_modules. Follow `public_site/README.md` for existing command arguments.
Keep private logs/QA in ignored `.agent/document-insights/`, with no visitor secrets.

Inspect 360/390/768/1440 widths, 200% zoom and keyboard navigation. Check numeric and source
answers for every sample; include valid controls and held-out layout variants. Record
per-check denominators and unrun cases; never rerun an unexplained failure into a claimed
clean result. Diagnose/preserve it first. Run heavy jobs sequentially with temp files on E:.

For static-only changes, the targeted Node and real-browser checks are the relevant gates;
do not rerun 40-minute backend suites for unchanged code. If a separately approved change
touches backend behavior, use its required sequential Windows/native gates without changing
assertions, timeouts or skips. Do not claim broader platform coverage than was executed.

Commit explicit owned paths as PHANI465 <pgavara1@asu.edu>, sole author and committer, no
trailers or history rewriting. Validate the final commit, then hand off exact SHA, diff
scope, tests, evidence, sample provenance, privacy checks, failure history and gaps.
Do not publish a partial capability as Available. Stop for Codex review after S1-S5 delivery;
do not self-approve, merge or deploy. This is one complete implementation assignment, not
five separate requests for routine permission.
