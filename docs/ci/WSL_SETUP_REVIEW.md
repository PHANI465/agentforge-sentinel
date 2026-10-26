# Proposed WSL environment for real Linux verification

**Owner approved and setup completed October 26.** Read [actual setup/results](WSL_SETUP_RESULTS.md) and [N4](../reviews/N4-linux-postgres-startup.md). The original proposal below is retained as history. Existing Ubuntu WSL2 is registered. Claude's read-only inventory found Ubuntu 24.04.3, a root-only account, system Python 3.12, and missing uv, native Node and PostgreSQL. The Windows PostgreSQL system service is unrelated to these tests.

## Proposed changes inside existing Ubuntu

1. Recheck existing tools/accounts/paths, then create an unprivileged `sentinel` user with a home directory if absent. Invoke it explicitly with `wsl -d Ubuntu -u sentinel`; changing the distro's default user is unnecessary.
2. Install the PostgreSQL binaries and basic download/certificate prerequisites from Ubuntu packages. Use test-owned disposable clusters on loopback for all validation. Any packaged service management is confined to a newly installed Ubuntu service; the Windows service remains outside this task.
3. Install the project's uv version and let uv provision Python 3.11 in the Linux user environment. uv-managed Python supplies the complete interpreter environment; the missing Ubuntu Python 3.11 package alone does not require changing the system Python.
4. Install native Node 22 under the Linux user from official distribution files with checksum verification. Confirm node/npm execute Linux binaries rather than Windows interop.
5. Create an owned clone on the Linux filesystem, such as /home/sentinel/agentforge-sentinel, from the local Windows repository. Use a specific candidate commit, local owner Git identity and the locked dev+ml environment. The source repository is not a new network remote or public publication.
6. Run focused N2/N3 and lifecycle coverage as non-root; after the candidate is ready run the actual structured backend/contract/package/model checks. Preserve frozen data/results and report real failures rather than widening tolerances/skips. Coordinate full suites with Windows. Record versions, cleanup and any POSIX limits separately from CI status.

This proposal creates a Linux user and installs Linux packages/toolchains. It uses downloads and local disk space, with no paid service or model-provider call. Ubuntu setup and a GitHub network remote are separate choices. A real GitHub Actions run can follow after a repository/remote is selected; neither option has been performed here.

## Why these prerequisites

PostgreSQL documents that initdb must run as the database owner and refuses root. Microsoft recommends storing projects in the same filesystem as the tools, and documents Linux accounts within WSL. uv can install/manage a chosen Python version. These primary references support the plan, not a claim that the project has passed Linux:

- [PostgreSQL initdb](https://www.postgresql.org/docs/current/app-initdb.html)
- [Microsoft WSL environment setup](https://learn.microsoft.com/en-us/windows/wsl/setup/environment)
- [uv Python management](https://docs.astral.sh/uv/guides/install-python/)

Existing N2 inventory and the earlier suggested commands are at task/claude-linux-readiness:docs/ci/LINUX.md. This scoped proposal is the approval target; no changes to the WSL user, packages or services were made by Codex while preparing it.
