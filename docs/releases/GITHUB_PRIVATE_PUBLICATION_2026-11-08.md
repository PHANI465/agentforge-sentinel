# First private GitHub publication — November 8, 2026

Owner explicitly selected a new private repository named agentforge-sentinel, preserving
existing history and PHANI465 <pgavara1@asu.edu> as sole future author/committer.

- Repository: https://github.com/PHANI465/agentforge-sentinel, private, owner PHANI465.
- First pushed main: 1d42d5b0d90a320d0d43b9a7efbc1132d29062e7. GitHub API and ls-remote
  confirmed that SHA. All 193 existing reachable commits have the one owner author and
  committer identity; GitHub's contributors API lists PHANI465 only, 193 contributions.
- No history rewrite, force push, mirror, tags, correction branches, raw datasets or
  ignored local evidence. Source/license credit remains. This is a private code backup,
  not hosted product deployment or a CI pass.
- The connector verified the owner but has no repository-creation/push capability.
  GitHub CLI used the existing Git Credential Manager account; a credential was passed
  in memory to the child process, never printed, saved in a script or put in a remote URL.
- Actions were disabled **before** the first push; the existing workflow file is unchanged.
  [GitHub docs](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository)
  state that disabled repositories run no workflows. [Billing guidance](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
  distinguishes included private-runner compute from additional charges. Actual remaining
  allowance was not checked, so no metered workflow was enabled.
- Prepublication scan examined 1,747 reachable blobs, 25,012,160 bytes, with no oversized
  file and no selected credential-signature hits. An initial generic-key pattern matched
  a substring inside a task path; the signature boundary was corrected and the initial
  report retained. This limited pattern scan is not a proof that every possible secret
  format is absent. Tracked/private-path and Git-exclusion checks supplement it.

New research/decision documentation is a later owner-authored fast-forward publication
of the same accepted application. Its exact push SHA and verification are recorded in
the final chat and ignored .agent/github-publication/ records; a document cannot name
the SHA of its own containing commit. No new full backend or browser claim is made.

Next: verify included allowance and issue an explicit CI dispatch before enabling a
runner. Preserve current Actions settings until then. Branch protection/review policy,
public visibility, hosting and visitor BYOK remain separate choices.
