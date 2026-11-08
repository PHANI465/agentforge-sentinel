# AgentForge Sentinel: project overview and remaining work

Updated November 8, 2026. Start with the [complete current study guide](AgentForge_Sentinel_Complete_Project_Study_Guide_2026-11-08.md) or its [offline HTML edition](AgentForge_Sentinel_Complete_Project_Study_Guide_2026-11-08.html). The [current checkpoint](AgentForge_Sentinel_Session_2026-11-08.md) records the precise stop. Earlier dated guides remain preserved historical snapshots.

## What we are building

A synthetic financial investigation workbench connects transaction ingestion, rule or trained-model scoring, evidence, bounded agent investigation, a human decision and an audited simulated action. The planned second workspace adds curated financial reports and source-row drilldowns. A demonstration/release layer includes an accepted recorded replay, with controlled hosting and optional visitor-key inference still future work.

The scorer ranks risk; agents propose; server rules and a human govern effects. It connects to no bank account and moves no real money. Synthetic ML scores, deterministic test success and a recorded replay do not establish real-world fraud effectiveness or live-agent quality.

## Accepted work

- Local transaction → score → alert/case → investigation → human approval → explicit simulated action → audit.
- Temporal synthetic data, reproducible CPU ML baselines and p1 serving, pinned inputs/results and model reports.
- Bounded three-role coordinator, typed scoped tools, server claim checks, recovery and read-only trace API/UI.
- Restricted database role, safe logs, revision/expiry/idempotency checks, package/install tests and Windows/native backend validation.
- Populated-workflow backup/restore, explicit operator mode/restart settings, safe evaluation preparation and review-packet tooling.
- Bounded deterministic local benchmark and key-free recorded replay.
- Reviewed AN01 r3.2 design for measurement-prototype work; public v1.3 and production reports are not frozen or implemented.

Accepted application/tooling is exact tested 871e31d, with independent Windows/native gates of 810 + one allowed skip each. Later main publications add documentation, not a new full-suite claim. Last applicable Windows product UI evidence remains 133 unit tests and 19 legacy + 10 trace browser cases; it is not rerun for tooling-only documentation.

## Current handoff, not accepted yet

AN01-M1 candidate 93583a is delivered on task/claude-an01-m1-prototype. The author reports final gates of 876 + one skip on Windows and native. Earlier tiny smoke ends not demonstrated after native C2:1250 missed a reply margin. Codex must review timing policy, changed assertions, clock observations, disk estimates and controller/resource ownership. See [the intake](../reviews/AN01-M1-93583a-intake.md). No full-size run is authorized.

## What remains

| Workstream | Next steps |
| --- | --- |
| Financial reporting | Review M1, resolve resources/timing, separately run approved measurements, review/freeze v1.3, implement S1 API/UI and end-to-end tests; later S2 exports and label availability. |
| Agent quality | Explicitly authorized development comparison and blinded human review, then separately authorized final-case evaluation; keep missing measurements and failures visible. |
| Verified release | Actual GitHub Actions, Linux browser checks, chosen hosting/session/retention/abuse controls and an authorized deployment. BYOK is optional separate scope. |

Optional future experiments include better currency features/calibration, drift monitoring, sequence/graph models, permission-filtered retrieval and new AML/scam domains. Each needs its own data, evaluation and security case. They are not prerequisites for the already working local case workflow.

## What to tell Claude now

Use the [new-chat resume prompt](../prompts/CLAUDE_RESUME_AN01_M1_REVIEW_2026-11-08.md), recommended Opus 5.5 / High. The previous implementation prompt was correct and has been delivered. Restore context, preserve 93583a and wait for Codex's specific review dispatch. Do not repeat implementation or start the full grid. Context persists in commits and documents; a chat is not shared runtime memory.
