# Local disk space for Sentinel development

## November 14 folder measurements

These figures sum file lengths without following directory links. Actual
disk space recovered may differ because of file allocation and hard links.

| Location under `E:\PHANI` | Size | What it holds |
| --- | ---: | --- |
| `agentforge-sentinel` | 0.65 GiB | The main checkout and shared Git database, plus its local environment and data. |
| `sentinel-wt` | 20.59 GiB | 81 linked checkouts at inspection. Python environments account for 16.16 GiB, Node dependencies for 2.12 GiB and `.agent` evidence for 0.39 GiB. |
| `sentinel-tmp` | 1.10 GiB | Scratch space for heavy Windows runs. Retained pytest directories account for about 1.08 GiB, including disposable database and package installation fixtures. This folder also holds named reports and Git bundles. |

The worktrees are siblings of the main checkout so each task has its own
files and Git index. They share the main repository's Git objects and keep
local installs and uncommitted changes in their own checkout. Heavy test
commands use the sibling temp directory through process-scoped `TEMP` and
`TMP` to conserve C: space and keep test output outside the clean checkout.

For E: cleanup, the largest rebuildable items are `.venv` and
`web/node_modules` inside inactive worktrees. Check that a worktree has no
running job or recovery store before removing generated dependencies, and
keep its source, branches and `.agent` evidence. Reports and bundles in
`sentinel-tmp` need individual review. Remove an entire retired checkout
through Git only after checking for uncommitted and ignored files worth
keeping. The volume check reported approximately 12.7 GiB free on C: and
85.3 GiB free on E:. No cleanup was performed during the inventory.

## November 13 baseline

Snapshot taken **November 13, 2026** on the owner's Windows laptop. These
numbers change with every gate; measure again before cleanup. This is an
operator note, not a request to delete evidence.

| Location | Measured size or free space | Relationship to Sentinel |
| --- | ---: | --- |
| C: free | about 6 GB at inspection | Heavy Windows runs failed earlier when only 0.17 GB remained. |
| E: free | about 88 GB | Main checkout, task worktrees and `E:\PHANI\sentinel-tmp` live here. |
| Ubuntu WSL `ext4.vhdx` on C: | 8.91 GB | Native Linux clones, environments, reports and tests contribute to it. |
| Docker Desktop data VHD on C: | 17.42 GB | Separate from Sentinel's current direct-PostgreSQL tests; it may serve other projects. |
| Windows uv cache on C: | 1.65 GB | Locked/offline installs may need cached files. |
| Windows user Temp on C: | 2.16 GB | Mixed app and test files; only about 0.06 GB was under its `claude` folder and 0.03 GB under `pytest-of-Phaneendra` at inspection. |
| `.codex` on C: | 1.88 GB | Includes chat sessions/history, plugins and caches. Preserve it. |

## Low-risk sequence

1. Keep `TEMP` and `TMP` set to `E:\PHANI\sentinel-tmp` **for heavy Windows
   test commands**. This is why the DOC01 Part B gates moved temporary files
   to E:. It does not move source code or alter test assertions. Native WSL
   tests still use their Linux filesystem inside the Ubuntu VHD.
2. In Windows, open **Settings → System → Storage → Temporary files** or
   **Cleanup recommendations**. Review selected categories and leave
   **Downloads**, cloud/offline files and any material you need unchecked.
   Use Windows' own cleanup action rather than deleting the whole Temp
   directory. [Microsoft's Storage Sense guide](https://support.microsoft.com/en-us/windows/experience/storage-filemanagement/manage-drive-space-with-storage-sense)
   explains the categories and settings.
3. If C: remains tight, review Docker Desktop's disk usage and, if that disk
   is needed, use Docker Desktop's **Disk image location** setting to move it
   to E:. Check other projects that use Docker first. Do not remove its VHD
   manually. [Docker's settings guide](https://docs.docker.com/desktop/settings-and-maintenance/settings/)
   describes the managed move.
4. Treat moving Ubuntu WSL as a separate backed-up maintenance job. It holds
   native test clones and evidence. Do not move or delete `ext4.vhdx` in
   Explorer and do not run `wsl --unregister` without a verified export.
   [Microsoft's WSL FAQ](https://learn.microsoft.com/en-us/windows/wsl/faq)
   describes export/import and warns that unregister erases the old distro;
   [WSL disk-space guidance](https://learn.microsoft.com/en-us/windows/wsl/disk-space)
   warns against manipulating the AppData VHD directly.

Preserve `.agent` failure evidence, accepted and review worktrees, `.codex`
sessions/history, and the uv cache while offline checks depend on it. A
blanket cleanup of those locations could impair review or reproducibility.
No files were deleted during the November 13 inspection.
