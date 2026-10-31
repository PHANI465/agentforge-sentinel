# Project status

## October 31 resumption: G3A corrections ready for Claude

The owner resumed work. The October 27 pause is lifted for the
[documentation-only G3A follow-up](prompts/CLAUDE_G3A_REVIEW_FOLLOWUP.md).
Resume existing `task/claude-g3a-design` from exact **06a7c0c779eeb60ff4e57ddab70de07277e27501**
at `E:/PHANI/sentinel-wt/claude-g3a-design`, using **Claude Opus 5.5 / High** on the existing
plan. Codex has prepared the current prompt and [acceptance checklist](reviews/G3A-acceptance-checklist.md);
no Claude process or provider call was started by this coordination update.

**Current gate:** G3A is still changes-requested for [R31-R33](reviews/G3A-06a7c0c.md),
not accepted/frozen/merged. The original candidate is clean; supplied document checks pass,
and all four extra inconsistent-record probes still accept on the baseline. Claude corrects
capacity/late-worker rules, workflow-level completion/recovery and typed record invariants,
then returns the exact tested SHA. Codex reviews that SHA before G3B implementation starts.

**Order after this correction:** accepted G3A -> G3B bounded backend workflow -> accepted
trace API and G3C UI -> measured agent comparison. No later task is dispatched by this
resumption. Keep the existing deterministic default, human approval and synthetic/simulated
scope. Public hosting/BYOK, new providers, spend and remote/push are outside this task.

Main's application remains H01 f091a34; last full backend evidence remains c8b9477 (449+1
per platform). This update changes docs/instructions only, not application acceptance.
Cursor's original seven edits and all delivered task worktrees remain preserved.
See [today's session checkpoint](artifacts/AgentForge_Sentinel_Session_2026-10-31.md).
The entries below are historical; they do not reinstate the October 27 pause.

## October 27 end-of-day pause: G3A reviewed, corrections pending

The owner requested a pause until tomorrow. G3A candidate **06a7c0c779eeb60ff4e57ddab70de07277e27501**
is delivered and independently reviewed: **changes requested, not accepted/frozen/merged**.
[Review R31-R33](reviews/G3A-06a7c0c.md) covers late-worker capacity, terminal recovery
without a running role and inconsistent typed draft records. The supplied schemas/examples,
12 development cases, Ruff and five-document links pass; four extra semantic probes reveal
the missing contract invariants. This is a documentation proposal, not runtime delivery.

Decisions for the revision: new 409 capacity code; provisional 45s role / 150s workflow
limits; inconclusive workflow reopens `open` with no intent; usage unknown unless measured.
[Tomorrow's follow-up](prompts/CLAUDE_G3A_REVIEW_FOLLOWUP.md) is prepared but **paused**:
Claude Opus 5.5 / High, docs only, on the existing G3A branch. **G3B is unstarted and blocked
on design acceptance. No tasks or provider jobs are assigned to run overnight.**

Main's application remains H01 f091a34; the full backend baseline remains c8b9477 (449+1
per platform), with H01's scoped checks separate. Candidate and Cursor's seven saved edits
stay untouched. Codex remains integrator; all new commits use the owner alone. No provider,
remote, push, deployment or new environment setup. See today's
[session artifact](artifacts/AgentForge_Sentinel_Session_2026-10-27.md). Earlier entries below
are chronological history and do not override this stop point.

## Earlier October 27: H01 completed and G3A assigned

H01 is accepted at **f091a34c2ed3f6636625b3141be88d86cd5307dd**. Both browser-hardening
notes are closed: database-enforced read-only inspection and zero approvals/actions before
the fresh-model approval step. Final main checks: five real PostgreSQL cases on Windows,
five on native Ubuntu, Ruff, TypeScript and all 19 real browser cases passed. Read
[the scoped acceptance](reviews/H01.md). The last full backend baseline remains c8b9477
(449+1 per platform); no full-backend rerun is claimed for this test-only increment.

**Claude G3A is assigned, not started:** [multi-agent contracts and evaluation design](prompts/CLAUDE_G3A_MULTI_AGENT_DESIGN.md),
from exact f091a34 in its own worktree. Define evidence analyst, investigator and reviewer
roles, a bounded deterministic coordinator, scoped tools, persisted boundaries, claim support
and the one-agent comparison protocol. G3A is a concrete design/schema package; runtime
implementation is G3B after contract review. No framework migration, live model call, new
provider, public BYOK or hosting is assigned. Codex reviews and integrates; Cursor can stay
inactive and its seven original edits remain preserved. Main is the canonical base; later
coordination updates are documentation-only. All commits use the owner alone.

Today's [session checkpoint](artifacts/AgentForge_Sentinel_Session_2026-10-27.md) records the
actual results and next action. The October 26 Word guide remains an unchanged dated guide.
No remote/push/deployment occurred; GitHub Actions/macOS/Linux browser remain unverified.

## Earlier October 26 records

## Current release: accepted N2-N7 integration

N5-N7 **48633a2fbe0ff477026830e60b36747eaa96154d** is accepted; [R29/R30 are closed](reviews/48633a2.md). The original independent probes now preserve recovery on repeated fresh-load retries and unreadable live membership. Independent final review: 15 focused tests passed on each platform. Owner candidate full reports: 449 passes and one allowed skip per platform, 450 exact native cases. N2/N3/N4 remain accepted.

Merge 9e6b613 combines this exact candidate with current coordination, without conflicts. [The integrated release note](releases/MAIN-linux-readiness-2026-10-26.md) defines final native Linux validation, main promotion and main's own Windows/backend/browser checks. Exact final containing SHA/results live in ignored .agent/linux-readiness-validation/ and the Linux verification report; require matching clean-commit pass records, not an earlier candidate's report. Main is the canonical base after promotion; accepted branches and Cursor's seven saved edits remain preserved. All new commits use the owner alone; no push, remote, deployment or provider call.

Next after final release gates: H01's two low browser-hardening notes, then the bounded three-role fraud-investigation milestone with a measured one-agent baseline. Real GitHub Actions requires an authorized remote. Public BYOK, hosting, deeper analytics and measured capacity remain future gates. Native Linux here is local Ubuntu WSL backend evidence; macOS, Linux browser and Windows cold-cache are unverified. See the roadmap and release limits.

## Historical review/assignment records (superseded by the current release)

## Current Linux review: R29/R30 block N5-N7 integration

Candidate **8a4b3d767772a5cc11fa0d405ae4b8190b974ba3** has passing owner full gates on Windows and native Linux (443 passes plus one allowed skip; 444 cases). Exact Linux collection/report and Windows clean-commit metadata were verified; independent focused lifecycle/wheel runs passed nine tests on each platform, with Windows Ruff passing. N6/N7 have no blocking scoped findings.

However, [review R29/R30](reviews/8a4b3d7.md) independently reproduced real recovery-state deletion while an API group member remained alive: a fresh-load retry forgets the survivor, and a permission-denied stat read is mistaken for disappearance. **The whole candidate is changes-requested and must not be integrated yet.** Main remains clean and verified at a456f51; N2 3c860d4 and N3/N4 476abcc stay accepted/preserved.

Next: [Claude's narrow R29/R30 follow-up](prompts/CLAUDE_N5_REVIEW_FIXES.md) on the existing task/claude-linux-lifecycle branch from exact 8a4b3d7. Preserve N6/N7, add real stop/reload/retry regressions, keep fail-closed inspection and run final platform gates sequentially. Codex remains integrator. Artifact/status records are updated here; no merge, remote, push, deployment or model call. Cursor's seven saved changes are preserved. GitHub Actions/macOS and Windows cold-cache remain unverified. New commits use the owner alone.

## Earlier N3/N4 acceptance and N5/N6/N7 assignment

## Current Linux readiness: N3/N4 accepted; N5/N6/N7 assigned

N3/N4 **476abccc52b5228f71e129f8e3d0a8d9f11bef41** is accepted for its bounded changes: independent Windows and native Linux focused runs each passed 24 tests; Windows Ruff passed. Read [the review](reviews/476abcc.md). The owner full Windows six-check record is verified; the native full report matches all 436 collected cases but has **430 passes, five failures and one allowed skip**. The full Linux gate is not green; no merge/push occurred.

Next: [Claude N5/N6/N7](prompts/CLAUDE_N5_LINUX_LIFECYCLE.md) from exact 476abcc in a new dedicated worktree. This explicitly authorizes narrow browser_stack lifecycle edits, zombie detection and install-cache diagnosis. Both process defects reproduced independently with owned/reaped children. The install failure's missing package is still unknown; require cold-cache CI-order proof, not only a warm-cache rerun. Preserve accepted candidates, production code, contracts/frozen assets and the exact skip policy. Codex batches integration after review and final platform checks. Main remains verified a456f51; Cursor's seven saved edits are untouched.

Ubuntu setup is complete and native Linux is available as sentinel UID 1000. No additional environment approval is pending for this scoped task. GitHub Actions/macOS/hosting remain unverified; the existing orphan/PID-race limitations remain. New commits use PHANI465 <pgavara1@asu.edu> alone.

## Earlier setup and N3/N4 assignment record
## Current Linux readiness: setup complete; N3/N4 assigned

The owner approved Ubuntu setup. Native Linux tools and a non-root sentinel user/clone are ready: [actual results](ci/WSL_SETUP_RESULTS.md). At accepted N2 3c860d4, all six N2 startup cases passed natively; the combined focused run was **13 passed, one failed**. The failure is an actual PostgreSQL startup portability defect [N4](reviews/N4-linux-postgres-startup.md), not missing tooling. A controlled TCP-only cluster succeeded and was verified stopped. No Linux CI pass is claimed.

Claude's [N3/N4 assignment](prompts/CLAUDE_N3_PORTABLE_CLEANUP.md) now explicitly owns the narrow devdb startup correction plus the two Windows-only cleanup cases. Use base 3c860d4 in the separate task worktree. Run native Windows and Linux checks after the fixes, sequentially; preserve all skip/ownership/frozen-asset guarantees. Main remains checked a456f51, and accepted branches/source are unchanged.

Windows PostgreSQL was observed Running; no Windows service management was performed. The new Ubuntu packaged cluster and owned diagnostic cluster are stopped. Setup/test evidence is under canonical .agent/wsl-setup/. No provider call, paid service, GitHub remote, push or deployment. All new commits keep PHANI465 <pgavara1@asu.edu> as sole author/committer. H01 and the bounded multi-agent milestone remain later work.

## Earlier N2 review and pending setup record

**N2 3c860d4f1efa55c6d6e0bc28200b701afdfec837 is accepted** for its Windows-native and controlled POSIX-launch compatibility scope. Independent 14 tests passed in 39.23s, Ruff passed and the old launch negative control failed for the original ValueError. Final owner six-check metadata and all 435 JUnit node IDs match; 434+1 remains Claude execution evidence. No native Linux/CI pass is claimed. See [the review](reviews/3c860d4.md).

**Claude N3 is assigned, not started:** [portable cleanup-failure coverage](prompts/CLAUDE_N3_PORTABLE_CLEANUP.md), from accepted 3c860d4 in a new worktree. The two Windows-only cleanup skips would fail the Linux gate; an independent report-level probe confirms that rejection. Preserve actual Windows coverage, execute equivalent portable failure/retry cases, and keep the allowlist unchanged. Codex will batch N2/N3 integration after N3 review; verified main remains a456f51.

Native Linux needs a suitable environment. [The scoped WSL setup proposal](ci/WSL_SETUP_REVIEW.md) is prepared for the owner's decision; no setup has been performed. N3 code/Windows work can proceed independently. Main's passing source/report is unchanged. All new commits keep the owner's sole identity. H01 and the broader multi-agent/analyst/security feature milestone remain separate; Cursor can stay closed.

## Previous N2 assignment (now delivered)

Verified main remains **a456f510d8053ce67b4334564d75225a756d923d**: all six strict checks, 433 backend passes/one intentional skip, 44 frontend tests, 19 real browser tests, HTTP/package/model checks and final clean-state audit passed. See [the exact main verification](releases/MAIN-verification-2026-10-26.md).

**Claude N2 is assigned, not started:** follow [CLAUDE_N2_LINUX_READINESS](prompts/CLAUDE_N2_LINUX_READINESS.md) in a new worktree from exact main. Fix the Windows-only orphan-test launch while preserving real lifecycle coverage and the exact skip policy. Linux evidence requires an actually available environment; Ubuntu is registered in WSL2, but no Linux packages/users/configuration were changed by this dispatch. Missing setup is a separate concrete follow-up, not grounds to skip the code/Windows work.

These are coordination-document updates on task/coordination; main's tested commit/source remain unchanged. Codex reviews/integrates; all new commits use the owner's sole identity. Next sequence: N2, actual Linux/CI when ready, then bounded three-role fraud investigations with a one-agent comparison. H01 stays a separate low hardening task; Cursor can remain closed.

## Earlier main consolidation record: October 26

The owner designated **Codex as main integrator** and requested PHANI465 <pgavara1@asu.edu> as sole author on all future commits. This mainline consolidates accepted I03 4fff776 with coordination cad89cb. The application, contracts, model/data/evaluation files, frontend, locked dependencies, CI/checker and runtime tests are unchanged from I03. Reviewed component worktrees stay preserved.

Main is now the canonical application and instructions base. Read [the main release record](releases/MAIN-local-release.md) and SETUP.md. Final results are recorded after the containing commit in ignored evidence and the handoff chat; this document is not a self-certifying test pass. The strict gate must match the exact clean main HEAD/branch. The coordination reference is fast-forwarded during this consolidation; future tasks use main unless explicitly assigned another reference.

N2's Windows-only orphan-test launch, real Linux/CI, H01, hosted/public BYOK and the broader analyst/multi-agent/security milestones remain open. No push, remote creation, platform installation, paid/model-provider call or deployment is included. Existing October 25 rendered snapshots remain unchanged dated artifacts; today's Markdown checkpoint carries this integration update.

## Earlier I03 acceptance, before owner designation

**I03 is accepted at 4fff776fc4b6d2d400db74dc3ff7d6cfce43217d** for the combined Windows-local release-candidate scope. It includes accepted I02 f38e920, C06 4f06e32 and C08 353ecec without application/model/UI changes. Independent 37 combined tests (97.64s), clean package/installed-scorer verification and HTTP export checks passed. The final full-suite JUnit's 434 cases match independent collection; 433+1 remains Claude's execution evidence. See [the release review](reviews/4fff776.md).

**Next: the owner names the main integrator.** Main is still 507538e and no push or remote exists. Preserve exact 4fff776 and all tested component checkouts. The main-integration task must include current coordination documentation without overwriting the accepted application, then verify its final combined commit. Cursor can remain closed; no new implementation task is assigned by this review.

Linux/CI is not green: N2 identifies unguarded Windows creationflags in the orphan test, which needs adaptation before an Ubuntu CI run. POSIX operator behavior remains unverified. H01 remains non-blocking/unassigned. Yesterday's rendered HTML/Word checkpoint stays a dated snapshot; today's Markdown checkpoint and these live coordination files carry this update.

## Historical overnight checkpoint October 25

The owner asked to stop project development for today and continue next session, planned for October 26. **Do not start another implementation, merge or full runtime test tonight.** Documentation and artifact preparation are the only current work.

C08 R28 correction **353ecec2fadbba43f939a27f5ad2b9227ff6fe87** is delivered on task/claude-operator-prep, directly above 784e101 with no merge/rebase. Codex observed clean HEAD, matching passed five-check strict metadata and the handoff. Claude reports 411 backend tests passed, one opt-in live skip and 15 focused operator passes. **R28 independent re-review and C08 acceptance are pending**, not implied by that report. Accepted C06 4f06e32, I02 f38e920 and main 507538e are unchanged.

Next session starts with docs/prompts/NEXT_SESSION_2026-10-26.md. Preserve all tested worktrees. Cursor remains inactive, H01 remains non-blocking/unassigned, and no new paid runtime usage is assumed. The expanded vision is approximately **85 out of 200 planning points** under the explicit artifact rubric; this is a subjective scope estimate, not measured completion or a time forecast.

Matching HTML, Markdown and Word checkpoint files are in E:/PHANI/agentforge-sentinel/docs/artifacts/AgentForge_Sentinel_Project_Checkpoint_2026-10-25.{html,md,docx}. Their shared content covers the summary, 21 progress steps, the rubric, tomorrow's handoff and proposed improvements. Final document render/QA results are recorded separately; no future pass is claimed here.


## Earlier checkpoint: C06 accepted; C08 startup follow-up assigned

C06 is **accepted at 4f06e32385424613fa0006b5bdbaab81ffea028f** for the refreshed local CI configuration/gate/package scope. R25/R27 are resolved: independent 22 focused tests, four-migration/eight-asset installed-package check and read-only ML reproduction passed; the frozen files are unchanged. No Linux/GitHub runner result is claimed. See reviews/4f06e32.md.

C08 **784e1014044920706a41bd91c61b965a03379999 remains changes-requested for R28 only**. Its original 10 ownership/rollback/backup tests passed independently, and the documented rollback works. Additional intercepted startup probes confirmed a lost recovery record when identity inspection fails after launch, and false startup success after a readiness timeout. See reviews/784e101.md. Accepted I02 f38e920 is unchanged.

**Historical assignment, now delivered at 353ecec: Claude followed docs/prompts/CLAUDE_C08_STARTUP_FOLLOWUP.md** on the existing C08 branch. Preserve accepted C06 and I02; no C06 rework or broad operator rewrite is assigned. H01 is non-blocking and unassigned. Cursor remains inactive. After the focused correction/re-review, define release integration; main is still 507538e. Portable checkpoint files are in E:/PHANI/agentforge-sentinel/docs/artifacts/AgentForge_Sentinel_Project_Checkpoint_2026-10-25.{html,md} and remain dated snapshots.

Portable HTML/Markdown checkpoint refreshed with 20 progress steps and this C06 acceptance/C08 R28 state. See E:/PHANI/agentforge-sentinel/docs/artifacts/AgentForge_Sentinel_Project_Checkpoint_2026-10-25.html.

## Latest checkpoint: combined local model/browser integration accepted

Codex completed the saved I02 Part B implementation at **f38e92023481a55db1ecf8bcdbe917140bd5d7cd**, branch task/codex-i02-completion in E:/PHANI/sentinel-wt/codex-i02-completion. Cursor remains an implementation contributor: its original seven edited files and exact byte snapshot are preserved. No need to purchase more Cursor usage to continue this work.

The combined local browser/model/API/Postgres path passes the 19-scenario browser suite (including the intentional failure used for credential-artifact checks). The last-run metadata reports passed with no unexpected failures; private lifecycle records were removed and the owned stack folder is empty. The scanner and 20 shutdown / 12 entrypoint harness checks preceded it. Frontend product code passed 44 unit tests and build on 4df18f2; that code is unchanged at final f38e920, whose e2e-inclusive typecheck passed. The final clean f38e920 strict check passed: Ruff, 396 pytest tests plus one opt-in live-Claude skip, 21 helper tests, 15 schemas and Node transport.

**I02 Part B is accepted at f38e920 after Claude's independent review**, forwarded by the owner: no blocking findings, independent 44 frontend tests/build/typecheck and 19 real browser tests (exit 0), plus a negative session-binding probe and seven error-hygiene probes. See [the acceptance record](reviews/f38e920.md). Two low test-hardening suggestions are tracked as non-blocking H01; the accepted commit stays unchanged. C06 is now accepted; C08 has the focused R28 follow-up before release integration. Cursor can remain closed. Main remains baseline 507538e; Linux/CI, hosting/public BYOK and production claims remain unverified. Earlier pending statements below are dated history.

## Goal and delivery

Build AgentForge Sentinel, a fraud-risk investigation workbench demonstrating data analysis, classical ML, bounded multi-agent execution and enforceable AI security. Existing laptop/subscriptions and free resources remain the budget; no additional spending is assumed. No fixed deadline, per the owner's October 23, 2026 instruction. Delivery is milestone-based; see PROJECT_PLAN.md.

## Accepted code and current branch

- Main still holds baseline 507538e (adopted kit and draft contracts); the thin path has not been merged.
- Reviewed implementation: task/thin-path at c6d369f6043a8c9ec86d8f56cf05670e81fba81d, following ed08de0. It implements Postgres + FastAPI, rule scoring, recorded scoring outcomes, deterministic or opt-in local Claude investigation, human approval, idempotent simulated actions and audit.
- Codex independently re-reviewed R1-R8 and found no new blocking defect in those corrections. Focused regressions: 13 passed. Strict clean-commit check: passed; full pytest 106 passed / 1 intentional live-Claude skip, 21 handoff tests, 15 schema exports, Ruff and Node checks.
- Review scope and limitations: [c6d369f review](reviews/c6d369f.md). Claude's live-call, real-server restart and isolation-canary evidence was not independently repeated by Codex.
- C01 is separately accepted at 2e6c2329aafe28b2e7c31ef5078d554cb66ca529. See reviews/2e6c232.md. U01/C02/C05 include that application dependency. task/coordination carries current instructions on the older c6 source; do not use its tip or old main as their application base.
- G0 and G1 remain partial. U01 deb1037 is accepted with R14-R17 resolved. Bounded real-browser hold and escalation paths work; C04's offline trained model is accepted; U02 browser acceptance is complete on Windows for U01+C02; the trained API is separately accepted; combined Windows-local browser/model integration is accepted at f38e920; hosted staging and public BYOK remain incomplete.

## Delivery and review snapshot

| Package | Delivered commit | Review state |
| --- | --- | --- |
| C01 HTTP contract | 2e6c2329aafe28b2e7c31ef5078d554cb66ca529 | ACCEPTED: R9/R10 resolved |
| C02 browser fixtures | 0e72b0bd599ff1707ca5b2507d65a0927894cbe0 | ACCEPTED: Windows local fixtures; R11/R12/R13 resolved; U02 separately accepted |
| U01 analyst UI | deb10370352dc62b0abfa2a5776c185494fcb04e | ACCEPTED: R14-R17 resolved; U02 separately accepted |
| U02 browser acceptance | 5f2855553ac0a445d96914730a89fc3722682830 | ACCEPTED: R21/R22 resolved; independent 14 real browser tests and cleanup passed on Windows |
| C05 backend reliability | a8294f6a98a3a5f2c093dc6b97d1da8a594c9fdd | ACCEPTED: R18-R20 and operator notes resolved within local backend scope; local browser integration now accepted at f38e920 |
| C03 synthetic data | a8e716cdec38fad1c316c6ffa2b722601b50b41d | ACCEPTED: synthetic-data/historical-feature scope; C04 separately accepted |
| C04 trained baselines | 09b5378150faed06caa73b0384b9ff095c095eb8 | ACCEPTED: offline synthetic evaluation/artifact; 29 ML tests and frozen result independently reproduced; C07 separately reviewed |
| C07 model serving | 275509af655a81a62bba28e74e9d8ab6c8d9cf5f | ACCEPTED: local backend; R23 resolved; v1.1 unchanged; local browser integration accepted at f38e920 |
| U03 model/analysis UI | a5716e252af2077a507767a3f819ddf44ea41c12 | ACCEPTED current-p1 frontend; real model-browser integration accepted at f38e920 |
| I01 model-browser fixtures | 7dd9428c70a7741af1c4781d22fd6b184f957444 | ACCEPTED: Windows local fixture/lifecycle dependency; ten independent real-process tests passed |
| I02 Part A | 50856be3da54ffdadd6cda7a0fcd5e59a9b21733 | ACCEPTED: N1 resolved; included in accepted Part B f38e920 |
| I02 Part B continuation | f38e92023481a55db1ecf8bcdbe917140bd5d7cd | ACCEPTED: independent Claude review; Windows local model/browser integration; two non-blocking H01 suggestions |
| C06 backend CI | 4f06e32385424613fa0006b5bdbaab81ffea028f | ACCEPTED: R25/R27 resolved, current local package/CI configuration scope; no GitHub/Linux run |
| C08 local operations | 353ecec2fadbba43f939a27f5ad2b9227ff6fe87 | ACCEPTED: R28 resolved; independent 15 focused tests / six probes; Windows-local scope |
| I03 release integration | 4fff776fc4b6d2d400db74dc3ff7d6cfce43217d | ACCEPTED: combined Windows-local candidate; main integrator decision pending; N2 Linux-test portability open |

C01 acceptance and independent verification are recorded in [the re-review](reviews/2e6c232.md). The original [0a6fb0e review](reviews/0a6fb0e.md) remains history. C03 is separately accepted; see [the review](reviews/a8e716c.md). C06, C08 and I03 4fff776 are accepted for their tested local scopes. Main remains unchanged pending the owner's integrator designation.

Use [the Cursor assignment](prompts/CURSOR_UI.md) for U01 and [the Claude C02 prompt](prompts/CLAUDE_C02.md) for backend browser fixtures. Start from/include accepted C01 2e6c232. The coordination branch is the current instructions reference, not the application base for these tasks.

U01/U02/U03 and the C01-C05/C07 components are preserved accepted contributions. Accepted I02 f38e920 establishes the combined Windows-local rule/model browser workflow; C06 4f06e32 and C08 353ecec are separately accepted. I03 4fff776 now combines these into an accepted Windows-local release candidate. Linux/real CI, main integration and hosted testing remain open. Older component assignments below are retained as history, not new dispatches.

## Immediate executable queue

1. Claude follows prompts/CLAUDE_N2_LINUX_READINESS.md from exact main a456f51 in its own worktree. Preserve tested main and accepted components.
2. Codex reviews the concrete N2 commit and actual Windows/Linux/simulated evidence; source setup and skip-gate boundaries remain enforced.
3. Obtain actual Linux/CI evidence after needed environment/remote setup. No unexpected skip or unsupported POSIX claim.
4. Then select the bounded three-role fraud-investigation increment. H01 and hosting/public mode are separate; Cursor can remain closed and every new commit uses the owner alone.

## Evidence history

- 2026-10-23, Codex-led baseline: domain contracts, 51 contract/schema tests and 21 helper regressions passed.
- 2026-10-23, Claude ed08de0: thin local path and manual live-Claude/server/database restart evidence; Codex review requested R1-R8 changes.
- 2026-10-23, Claude c6d369f: test-first R1-R8 corrections, migration 0002 and harness/line-ending follow-ups; 107 pytest tests with live Claude, 106 + 1 skipped by default. See VERIFICATION.md for attribution and limits.
- 2026-10-23, Codex c6d369f re-review: accepted local corrections; independent focused and ordinary checks passed on the clean reviewed commit. See reviews/c6d369f.md. Final coordination-commit checks are recorded externally in the final chat/local ignored report, not invented inside this commit.

## File ownership and integration

Codex is review/coordination lead and owns central STATUS/TASK_QUEUE. Claude owns backend, data/ML and backend reliability/CI. Cursor is a required implementation contributor and owns the analyst interface and browser tests. Each task uses a branch/handoff and a dedicated worktree for parallel work. No two tools edit a checkout concurrently.

The existing owner-designation gate for the integrator remains: the owner has not explicitly named the main-branch integrator, so this review/queue does not merge into main. Implementation starts from each package's accepted application dependency; task/coordination supplies current instructions.

| Area | Owner | Paths |
| --- | --- | --- |
| Central coordination/review | Codex | AGENTS.md, docs/STATUS.md, docs/TASK_QUEUE.md, review and dispatch docs |
| API/contracts/database | Claude, one writer at a time | src/sentinel/, contracts/, backend tests, docs/api/ |
| Data/ML/evaluation | Claude | data_pipeline/, ml/, evals/ml/, tests/data/, tests/ml/, docs/ml/ |
| Backend reliability/CI/operator tooling | Claude | backend workflows, backend scripts/tests, docs/security/, docs/ci/, docs/runbooks/ |
| Analyst UI/browser acceptance | Cursor REQUIRED | web/, docs/ui/, frontend workflow |

## Open measurements and limitations

- Laptop RAM/GPU/model speed and available disk; do not assume a GPU.
- Source-project tests/provenance, dataset licenses and historical-only evaluation policy still need task evidence.
- Actual Vercel plan, runtime/storage/worker constraints and persistent staging database. Verify current official limits before choosing hosting.
- Exact Claude allowance behavior and global-memory isolation remain unverified; local login is not a public API entitlement.
- Public tester-supplied key, expiry, retention and cost controls need a separate hosted acceptance gate. Never copy key values into planning files.
- Under-threshold scoring is recorded but has no case-bound audit event in v1. Legacy transactions before migration 0002 may have unknown scoring outcomes.
- Approval expiry is observed lazily on execute/investigate. Decide on an active sweeper only with a measured need.
- No CI, Linux/macOS, external test-database path or hosted staging has been independently verified here.

## C07 review on October 24

See [62def10 review](reviews/62def10.md): 37 focused model/contract/installed-wheel tests and ordinary compatibility checks passed independently; two real-Postgres interleavings confirmed post-cutoff operator data enters a captured model decision. R23 blocks backend acceptance. HTTP v1.1 artifact acceptance is explicitly limited to Cursor development. Claude full 372+1 strict evidence is attributed separately; no independent full repeat, main integration, live provider call or hosting occurred.

## Owner checkpoint on October 25

Start with [the project checkpoint](PROJECT_CHECKPOINT.md): summary first, step-by-step completed process, exact saved Cursor state, package register, ML evidence, skills, remaining milestones and restart commands. A standalone readable HTML copy is saved in E:/PHANI/agentforge-sentinel/docs/artifacts/AgentForge_Sentinel_Project_Checkpoint_2026-10-25.html. It is a dated snapshot, not a live dashboard.

C07 275509a passed independent 50 focused tests (142.83 s), Ruff, 21 helpers, 15 schemas, HTTP exports and Node. R23 is resolved. Claude's full386+1 count is attributed. U03 a5716e2 is observed delivered/clean with matching local strict metadata; new UI review remains pending. No new provider call, deployment, install, remote or main merge occurred.

## Integration assignments after U03 review

U03 a5716e2 passed independent37 frontend tests/typecheck/build and nine exact fixture-copy comparisons. Current-p1 increment accepted; legal nullable calibration fields and an omitted optional split field need N1 compatibility correction during I02. No full model-browser or new backend acceptance is claimed by those UI checks. Claude follows prompts/CLAUDE_I01.md; Cursor follows prompts/CURSOR_I02.md. These are task-branch integration assignments, not a main merge. C06/C08 remain review-pending.

## I02 Part A accepted while I01 checks continue

50856be passed independent 16 focused tests/typecheck/build and the original parser/fixture-copy probe. N1 is resolved; full 44 and strict 215+1 remain Cursor-attributed. Claude's I01 candidate is still work in progress; an active backend test process was observed and no final I01 acceptance is recorded. See reviews/50856be.md. Preserve accepted checkouts and avoid duplicate background jobs.

## I01 acceptance and I02 Part B dependency

I01 7dd9428 passed independent 10 real-process tests in 160.73s, Ruff, 21 helpers, 15 schemas, HTTP exports and Node. Exact accepted parents/protected-source equality and owner clean strict metadata were verified. Full 396+1, 40 C02 tests and 14 old rule-browser tests remain Claude-attributed. Final status compatibility and 1800-second checker bound are accepted; model-mode browser acceptance is I02's remaining work. Read reviews/7dd9428.md and prompts/CURSOR_I02_PART_B.md. Earlier candidate/waiting observations are historical.

## Historical I02 ownership handoff before final acceptance

Cursor is unavailable under its existing allowance. Its contribution is preserved at E:/PHANI/sentinel-wt/cursor-model-integration (e0e1b05 plus seven saved edits), with an exact byte snapshot. Codex continues in the isolated task/codex-i02-completion worktree from the same base; initial candidate 4df18f2. No new spending, production backend change or main merge is assigned. Final browser/backend checks are pending; this is an ownership checkpoint, not completion acceptance. Current active owner and provenance: prompts/I02_CODEX_TAKEOVER.md. Earlier Cursor execution instructions are superseded while quota is exhausted.
