# Automated development review — proposal JUDGE01

November 8, 2026. Owner requested an agent reviewer for now. This is a proposed additional
development signal, not a replacement result under the frozen human-evaluation protocol.
No implementation, experiment scores or new human agreement claim is present.

## Output and authority

Keep separate versioned judge_annotations artifacts bound to case/evidence/disposition
hashes. Record judge_kind=llm, human_reviewed=false, actual model identity, prompt/rubric
hash, attempt/parse/failure status, usage provenance and cited evidence IDs. Never insert
agent answers into the existing human review CSV or mark human-correction metrics measured.
Do not overwrite accepted P4a packets or source recommendations. A judge cannot approve,
execute, change tenant/session, mutate records or request privileged tools.

## Proposed protocol

1. Run deterministic checks first: exact amounts/dates, evidence existence, scope,
   prohibited operations, revision/approval boundary and schema consistency.
2. Use newly registered development examples only. Keep runtime facts, evaluator
   expectations and judge inputs separate. No access to protected final cases.
3. Give a tool-free judge the same evidence packet and explicit rubric. Structured
   fields are supported/contradicted/not-checkable, usefulness 0–3 with anchored examples,
   appropriate abstention, unsafe recommendation flag and short evidence citations.
   Unknown is allowed. Do not request hidden chain-of-thought; request concise rationale.
4. For pairwise review, hide model/provider identities, randomize order and also swap A/B.
   A flip becomes inconsistent, not a chosen win. Keep ties, abstentions and invalid outputs.
5. Test planted arithmetic errors, nonexistent citations, verbose incorrect answers,
   appropriate abstention, hostile notes and irrelevant instructions. Disagreement with a
   deterministic fact is a judge failure, not a vote to change arithmetic.
6. Freeze prompt/model/configuration before measured development use. Same-family review
   is explicitly not independent; a second family is useful only when its adapter enforces
   the same tool/permission boundary. Observing no tool call once is not proof tools are disabled.
7. Report coverage, failures, atomic supported/contradicted/not-checkable counts, swap
   consistency and seed/repeat conditions. Pairwise ties/inconsistencies remain denominators.
   Human agreement and Cohen's kappa are n/a until actual calibrated human labels exist.

No automatic multi-judge debate is required initially: it increases quota use and can
repeat correlated mistakes. A small later human calibration sample can assess the judge
without pretending that all development work must wait for manual scoring. No model-only
result satisfies the original protocol's human promotion conditions.

## Live access and budget

Claude's existing local adapter has an enforced empty tool/MCP surface and first-party
subscription preflight; a judge-specific wrapper/schema still needs review. Same-family
bias must be measured/disclosed. Codex's fixed-response smoke verifies access, not a
tool-free untrusted-content judge adapter. Cursor's paid/entitlement boundary is unverified.
Do not extract OAuth tokens, proxy an owner account publicly or fall back to API charges.

Use a separately registered small pilot with an explicit CLI-invocation allowance and
wall-time bound. An invocation need not equal a physical provider request. Preserve
quota errors, usage unknowns and early stop; no retries into a better score.

Primary research and exclusions are listed in the [research note](../../research/2026-11-08-expansion-research.md).
