# Handoff: task/claude-doc01-extractor

- **Task and acceptance criteria:** DOC01 Part A as dispatched in
  `docs/prompts/CLAUDE_EXPANSION_AFTER_M1.md` (task/coordination 4d60c53). Deliverables: a frozen
  local worker protocol, a separately locked `tools/document_worker/` project, a CLI/stdio
  prototype over owned synthetic files, a bounded owned child with recovery, deterministic
  measures, and hashes/negative controls/tests/smoke on Windows then native.
- **Tool and worktree:** Claude Code, `E:/PHANI/sentinel-wt/claude-doc01-extractor`, branched
  from accepted main `4d60c53dafa0ca478f32270fa83944d1d7363ef6`. The native clone is WSL
  user `sentinel` at `~/doc01-native`, fast-forwarded from Git bundles of this branch.
- **Updated:** 2026-11-12 (local time).
- **State:** ready for Codex review. Part A only; upload, feedback integration and the LLM
  narrative are not implemented.
- **Code reference tested before this note:** `1ce9a84c8dce53ab0f7024bd762e503d87ac4b44`
  (clean tree, Windows and native).
- **Final check evidence:** rerun on the final commit (this note's commit) and reported in chat.
  This note cannot name its own commit.
- **Owned/changed paths:** `tools/document_worker/**`, `docs/documents/DOC01-worker-protocol-v0.1.md`
  and this note. No other path differs from 4d60c53. The AN01-M1 worktree (`28dfcef`), all other
  worktrees and Cursor's edits are untouched.

## Implemented

- **Protocol v0.1, frozen for review:** `docs/documents/DOC01-worker-protocol-v0.1.md`. It
  covers trust boundaries, owned handle vs path/URI, the stdio framing, the result schema
  (statuses, units, records, unparsed, findings, evidence ids/locators), extraction rules,
  enforced bounds with single-run observations, lifecycle/recovery, explicit isolation gaps,
  measures, the proposed later API/UI and version coordination, and provenance.
- **Separately locked worker:** `tools/document_worker/pyproject.toml` + `uv.lock`, 46 packages.
  Pins `markitdown[pdf,xlsx]==0.1.8` (MIT). 0.1.9 is rejected because it needs certifi ≥
  2026.10.19. The lock keeps the app's certifi holdback, resolves certifi 2026.7.22 and adds a
  two-week `exclude-newer`. App `pyproject.toml` and `uv.lock` are byte-identical to main.
- **Owned handles** (`handles.py`): a marker-owned store, opaque `h_…` ids, session token
  stored only as SHA-256, a 1 h lease, re-hash before every use, verified delete and expiry
  purge. Missing, foreign, expired and malformed handles all return `not_found`. Copy-in
  refuses URIs, UNC paths, directories, links, a swap between lstat and open, a wrong
  extension and anything over 10 MiB.
- **Contained child** (`supervisor.py`, `child.py`): the base interpreter in `-I` mode with a
  minimal env and cwd set to an owned run dir. Windows uses a job object (kill-on-close, one
  active process, 1 GiB committed memory, CPU time, UI limits); POSIX uses setsid plus
  RLIMIT_AS/CPU/FSIZE/NOFILE/CORE. The request is written only after containment. stdout and
  stderr are capped and the deadline is 30 s. The stop is confirmed (job/group empty) before
  the run dir and record are removed. An unconfirmed stop keeps both and returns
  `stop_unconfirmed`. `recover` acts only on a verified process identity.
- **In-child audit-hook guard** (`guard.py`): defense in depth only; no network isolation is
  claimed.
- **Typed extraction** (`extract.py`, `tables.py`, `normalize.py`): CSV via strict UTF-8 and
  `csv`; XLSX via a central-directory precheck and two openpyxl read-only passes; PDF via
  pdfminer.six per page. Amounts are Decimal and converted to minor units by ISO exponent.
  Decimal and date conventions are declared or unambiguous-only, and contradictory ones become
  ambiguous. Every value has an explicit status. MarkItDown converters are called directly for
  the narrative only.
- **Measures** (`measures.py`): coverage, missingness, duplicate groups, per-currency
  reconciliation and running balance. `fidelity.py` compares results with ground-truth labels.
- **CLI** `sentinel-docworker init|ingest|extract|delete|purge-expired|recover`, with the
  session taken from `SENTINEL_DOC_SESSION`.
- **Fixtures:** 18 synthetic files (CSV 7, XLSX 4, PDF 7) and 21 labelled runs.
  `labels.json` is written from the same logical rows as the files. `MANIFEST.json` holds the
  hashes; ZIPs are STORED and PDFs uncompressed, so bytes match on both platforms. Tests
  generate the oversized, cap, ZIP-bomb (member, ratio, lying header) and Flate-bomb inputs.

## Verified (at 1ce9a84, clean tree)

- Worker tests: `uv run --locked python -m pytest -q -rs` in `tools/document_worker`.
  Windows **128 passed, 0 skipped** (JUnit `.agent/doc01/worker-junit-windows-1ce9a84.xml`).
  Native Ubuntu (CPython 3.11.14) **128 passed, 0 skipped**
  (`.agent/doc01/worker-junit-native-1ce9a84.xml`). Ruff is clean on both. Main's gate does
  not collect these tests.
- Smoke: `scripts/smoke.py` (serial, 21 labelled runs + 2 cap probes) is `ok` on both
  platforms. Field fidelity 259/259, behaviour 101/101, statuses complete 11 / partial 4 /
  unsupported 4 / error 2. No handles, run dirs, records or worker processes remained.
  Windows tiny runs peaked at ≤ 79 MiB per child. Row-cap CSV (846 KiB, 20,000 rows) took
  2.8 s / 169.5 MiB on Windows and 1.5 s natively, with 11.7 MB of typed output (near the
  16 MiB stdout cap) and an honestly truncated narrative, giving partial. The 50-page PDF took
  3.9 s / 82 MiB on Windows and 2.0 s natively. Native peaks are `RUSAGE_CHILDREN` upper
  bounds (201.7 MiB). Worker source SHA-256 is `55949e98…f52e` on both.
- Negative controls (tests): URI/UNC/link/directory/oversize refusal; foreign session hidden;
  tamper detected; expiry/purge; foreign directory never adopted. Encrypted (RC4) PDF, image-only
  and mixed scanned PDFs, truncated and mislabelled PDFs, macro workbook, OLE stand-in,
  member/ratio/lying-header ZIP bombs, Flate bomb (stopped at its 20 s deadline, under the
  memory cap), page/row/column/field caps, and non-UTF-8 CSV. Protocol errors covered:
  bad/oversized header, sha, framing, size, options. Supervisor tests cover deadline, output
  cap, memory cap (exit 7), grandchild (Windows blocked; POSIX group killed), crash/garbage/
  forged-id output, guard probe (socket/read-outside/write/subprocess/system/remove/urlopen
  denied, stdlib read allowed, canary never leaked), interrupt cleanup, unconfirmed stop then
  recovery, reused-pid safety, kept unprovable/foreign records, and a hard-killed supervisor
  recovered on both platforms.
- Application unchanged: `git diff --name-only 4d60c53 HEAD` outside the owned paths is empty.
  Tree ids for `src web contracts migrations scripts ml data_pipeline`, `pyproject.toml` and
  `uv.lock` are identical. Windows: `export_http_contract.py --check` passes (v1.2 plus frozen
  v1/v1.1), `ml test --reproduce` returns `reproduced: true`, `export_contracts.py --check`
  passes (15 + 15 schemas, 85 examples) and `check_contract_examples.mjs` passes. Root
  `ruff check .` (which lints the worker) passes.

## Not verified / gaps

- No OS-level network isolation. The Windows job places no filesystem bound; a test child
  without the guard wrote outside its run dir, and the real child relies on the audit hook.
  POSIX allows empty-file create/delete. Closing these needs a system change (AppContainer,
  restricted token, namespace, seccomp, firewall), so it is documented and not made.
- Child Python startup (`.pth` files, imports of markitdown/requests/magika/onnxruntime) runs
  before the guard. On Windows there is a tiny window before job assignment, during which the
  child only waits on stdin.
- PDF tables are not typed, so PDF reconciliation is `not_checkable`. There is no OCR, and
  DOCX is out of the matrix with its extra not installed. The OLE fixture is a magic-byte
  stand-in, not a genuine encrypted workbook. Invisible PDF text is extracted as page text,
  which future narrative/judge work must treat as hostile.
- Token savings are not measured, because no tokenizer/model was specified. On tiny CSVs the
  Markdown is larger than the source.
- Timings are single-run observations, not capacity. macOS was not tested.
- The full strict application gate is run only on the final commit (Windows) and reported in
  chat. Browsers and the frontend were not rerun because no product path changed.

## Next action

Codex independently reviews DOC01 Part A at this branch's final commit (protocol v0.1, worker
behaviour and gaps) before any API/UI upload or feedback integration is assigned.

## Coordination and provenance

- No shared contract, migration, grant, CI, checker or app dependency change. The later API
  slice proposes the next HTTP version after AN01's proposed v1.3 (provisionally v1.4), to be
  sequenced by Codex.
- MarkItDown 0.1.8 (Microsoft, MIT) and all locked distributions are resolved, not vendored;
  see `tools/document_worker/THIRD_PARTY_NOTICES.md`. Fixtures are invented and public-safe.
- No model, auth, account, network-service or paid resource was used. Only PyPI package
  downloads for the worker lock occurred. No remote push.
- AN01-M1 stays accepted-but-unmerged at `28dfcef`. JUDGE01 and new-data training remain
  separate; p1, the frozen protocol and final cases are untouched.
