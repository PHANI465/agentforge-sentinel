# Main: consolidated Windows-local release

The owner designated Codex to integrate the accepted local release on October 26, 2026. This commit combines exact I03 4fff776fc4b6d2d400db74dc3ff7d6cfce43217d with coordination cad89cb0d8ccf8b6e21ded0dbacaa59af7cf612b. The merge was automatic, with no conflicts. Main is promoted by fast-forward to this containing commit; no accepted task checkout is rewritten.

## Preserved application

Production src/, contracts/, ml/, data_pipeline/, evals/, web/, pyproject.toml, uv.lock, .github/, scripts/ and tests/ remain byte-identical to I03. Four migrations, eight trusted model/data assets, six strict commands and the 1800-second per-command limit are retained. The changes beyond accepted I03 are current coordination/artifacts, setup/README and author/tool instructions/settings.

The current local application includes rules or registered trained-model scoring, analyst UI and synthetic benchmark views, bounded investigation, human approval, simulated idempotent actions, audit history, runtime database permissions, operator backup/rollback and deterministic real browser fixtures. See [I03's release note](I03-local-release.md) and [acceptance](../reviews/4fff776.md). Source/model/UI checks from I03 are preserved, but final main verification is recorded separately for this exact containing commit.

## Run and verify

Start at [SETUP](../../SETUP.md). The default is local rule scoring with deterministic investigations; no model subscription is needed. The operator stack supplies the private local session; the UI uses an in-memory bearer token. Model mode requires operator-provisioned profiles. Native Postgres binaries, Python 3.11+, uv and Node 22+ are required.

After this final commit, run the six-command strict gate on main, validate JUnit from its same full pytest run, verify HTTP exports/read-only ML reproduction, then run frontend typecheck/unit/build and the real browser/API/Postgres suite. Check cleanup and compare protected source against I03. The containing SHA cannot be written inside itself: exact results belong in ignored .agent/ evidence and the final handoff. A report from an older branch/commit is not a main PASS.

## Sole author for new commits

The owner requested PHANI465 <pgavara1@asu.edu> as the sole author for future project commits. New integration commits use that author and committer, without Co-Authored-By or AI session trailers. Repository-local identity is pinned to the owner's existing configured identity; global Git settings and existing commit history are preserved. AGENTS.md/CLAUDE.md carry the policy. .claude/settings.json sets attribution.commit to an empty string and attribution.sessionUrl to false, preserving its existing hooks settings. See the [official Claude attribution reference](https://code.claude.com/docs/en/settings-reference#attribution-commit).

## Remaining scope

Windows-local, synthetic data and simulated actions only. Linux/macOS/real CI/hosting/public BYOK are not accepted. N2 identifies Windows-only flags in the orphan-process test and must be adapted before Ubuntu CI; the POSIX operator limitation remains. H01 is still open. PID timing, profile staleness/retraction, owner-SQL locking bypass, calibration/currency issues and measured serving capacity remain disclosed. No new training/evaluation selection, provider call, external database, push, remote, platform install or deployment occurs in this integration.
