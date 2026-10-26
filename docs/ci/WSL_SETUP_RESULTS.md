# WSL setup and first native Linux verification

October 26, 2026 (America/Phoenix). The owner explicitly approved setup of the existing Ubuntu WSL. **Environment setup is complete; project Linux CI is not green.** No application source was edited during setup.

## Installed and verified

| Item | Actual result |
| --- | --- |
| OS | Ubuntu 24.04.3 LTS, WSL2, Linux 5.15.167.4, glibc 2.39, x86_64 |
| Linux account | Unprivileged sentinel, UID/GID 1000; home /home/sentinel |
| uv | 0.9.26, official Linux archive SHA256 verified |
| Python | Managed CPython 3.11.14, native Linux; system Python was not replaced |
| Node/npm | Native Linux Node v22.23.4 / npm 10.9.9; official archive SHA256 verified |
| PostgreSQL | Ubuntu PostgreSQL 16.15 binaries; new packaged main cluster stopped and service disabled |
| Python environment | Locked dev+ml; NumPy 2.4.6, scikit-learn 1.9.1 |
| Project | /home/sentinel/agentforge-sentinel, clean detached accepted N2 3c860d4f1efa55c6d6e0bc28200b701afdfec837 |
| Git identity | Local clone author/committer configuration PHANI465 <pgavara1@asu.edu> |
| Source transfer | Verified local Git bundle; origin points to the bundle, not a GitHub/network remote |

Normal user shell discovery resolves uv/node under /home/sentinel/.local/bin, and Node reports process.platform=linux. New tool directories are user-owned. Initial root ownership on parent .local directories was corrected before installation. Direct cloning across the Windows mount hit Git's ownership protection; a verified local bundle transferred the exact committed source without changing global safe.directory settings. Windows main remains clean at a456f51; the Windows PostgreSQL 14 service was observed Running and was not managed by this setup.

Host C: had about 7.1 GB free after setup; E: about 112.7 GB. No WSL storage migration or unrelated cleanup was performed.

## Actual Linux results

At unmodified accepted N2 3c860d4, ran tests/test_local_stack_startup.py and tests/test_local_stack.py as UID 1000: **13 passed, 1 failed, 23.686s**. All **six N2 startup cases passed natively**, including the real Linux orphan/listener behavior. This extends N2 evidence beyond the earlier Windows simulation; it does not remove the documented non-listening orphan limitation.

The failed case is test_startup_failure_cleans_up_the_owned_api_and_keeps_the_database. It fails earlier than the intended API-factory failure: the test-owned PostgreSQL cluster cannot create its default Unix-socket lock in /var/run/postgresql. See [N4](../reviews/N4-linux-postgres-startup.md).

A fresh owned diagnostic cluster reproduced the default startup failure. Starting that same cluster with Unix sockets disabled succeeded over loopback TCP; a query returned current_user=sentinel and an empty unix_socket_directories setting. The cluster was then verified stopped. No global socket-directory permissions or database-user privilege grants were used to make the project appear green.

The full Linux suite was not run because this shared startup defect blocks its database-dependent tests. N3's two Windows-only skip cases remain another known gate blocker. Claude's [combined N3/N4 assignment](../prompts/CLAUDE_N3_PORTABLE_CLEANUP.md) now has the necessary narrow helper ownership. Main integration remains batched after that candidate's review and actual platform checks.

## Evidence and use

Canonical Windows evidence: E:/PHANI/agentforge-sentinel/.agent/wsl-setup/ contains setup-final.json, native-focused.xml/log, pg-startup-diagnostic.json, root/tool/clone logs, verified checksum records and the local source bundle. These are ignored local records, with no provider keys or real financial data.

Enter the environment from PowerShell:

```powershell
wsl -d Ubuntu -u sentinel
```

Then `cd /home/sentinel/agentforge-sentinel`. Use the existing locked environment and explicit native PostgreSQL bin path. This clone is a read-only verification checkout: transfer a committed candidate and check it out only with a clean tree and no active test run. Windows .venv/node_modules are not Linux environments. The current local bundle contains main/N2 only; a later candidate needs a fresh bundle/fetch.

Source/setup references: [Microsoft WSL](https://learn.microsoft.com/en-us/windows/wsl/setup/environment), [uv Python management](https://docs.astral.sh/uv/guides/install-python/), [PostgreSQL initdb](https://www.postgresql.org/docs/current/app-initdb.html) and [PostgreSQL socket settings](https://www.postgresql.org/docs/16/runtime-config-connection.html). Actual versions/results above come from local execution, not those references. No provider call, paid service, network remote, push or deployment was performed.
