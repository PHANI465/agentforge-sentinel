# DOC01 Part B: local document upload, security boundary and operator setup

This note is for reviewers and operators. Its scope is local synthetic or public files on
the owner's machine. Hosted, multi-user and private-customer use are **not** claimed. The
route contract is in [documents-v1.3.md](../api/documents-v1.3.md).

## Registering the worker (operator only)

```bash
# 1. The worker's own locked environment (never the app's).
cd tools/document_worker && uv sync --locked
# 2. A marker-owned store directory (absolute path, not shared with anything else).
uv run --locked sentinel-docworker init --store /abs/path/doc-store
# 3. Server configuration (environment of the API process only):
export SENTINEL_DOC_WORKER_PYTHON=/abs/path/tools/document_worker/.venv/bin/python
export SENTINEL_DOC_STORE=/abs/path/doc-store
export SENTINEL_DOC_WORKER_SHA256=<optional pin from the bridge "status" answer>
# 4. A session with the opt-in grant (default sessions never get it):
uv run --locked sentinel create-session --with-document-analysis
```

Without steps 3 and 4, every document route answers `503 document_worker_unavailable` or
`403 permission_denied`.

## Boundary

- **No HTTP caller controls the worker.** The interpreter, store and pin are read from the
  server's environment. Nothing in a request names an executable, a path, a URI or a
  directory.
  - No filename is read. The `format` query value is one of three literals, and the handle
    is an opaque id that is matched against a fixed pattern.
  - The worker resolves handles only inside its marker-owned store.
- **The worker is never imported.** The API starts one bridge process per operation,
  `<worker python> -I -m docworker.bridge --store <store>`. It runs with a minimal
  environment: interpreter essentials plus the owner key.
  - The API's database URL, provider keys and other environment variables are not
    passed. A test asserts the exact set of variable names the bridge received.
  - The working directory is the store.
- **Owner key, not the token.** The worker sees only
  `sha256("sentinel.doc01.owner.v1" ‖ tenant ‖ session ‖ token)`, and stores only the hash
  of that key. The bearer token never leaves the API process, and appears in no path, log,
  error, store file or example; tests check every one of these.
- **Bounded at every hop.**
  - Upload bodies are capped at 10 MiB while they are streamed.
  - The bridge's stdout is capped at 8 MiB, and stderr is discarded after 64 KiB.
  - Each bridge call has a wall-clock bound (30 s, or 90 s for analysis), and one
    analysis runs at a time per API process.
  - A record page is capped at 500 records or 2 MiB.
  - The Part A child keeps its own deadline, memory, output, page, row and archive caps.
- **Fail closed.**
  - A missing or invalid configuration, a status answer with the wrong protocol or source
    digest, or an unowned store each give 503.
  - A bridge crash, garbage, extra lines, oversize output or a shape outside the DTO each
    give 502; a timeout gives 504. None of them is reported as an extraction.
  - A timeout, crash, invalid answer or unconfirmed stop marks the worker
    *recovery pending*. Analyses are then refused until a recovery pass keeps nothing.
- **Separate from casework.** Document routes write no transaction, case, approval, audit,
  workflow or action row; a test checks every table.
  - Hostile document text such as "ignore previous instructions, approve…" is returned as
    inert record data. No route reads it as an instruction.
  - No model receives the file. The narrative converter is not run by the API.
- **Logging.** Events use the safe-log allowlist: route templates, never handle ids, plus
  fixed or sanitised outcome codes. Bridge stderr is never logged or echoed.

## Pre-API worker correction (Part A follow-up)

On Windows, `os.replace` onto a recovery record that a reader holds open raises a sharing
violation. Part A treated that as a containment failure. It left an orphan
`r_*.tmp`, and with a real open handle it raised out of `extract` from the cleanup step,
which crashed the supervising process.

The likely cause of the intermittent `test_crashed_supervisor_is_recoverable` failure was
the test's own polling read colliding with this replace. That explanation is supported by
reproduction, not proven for the historical runs. The fix:

- retries replace and removal for up to 2 s;
- writes each update to its own temporary name;
- makes a failed record write an `error` with `recovery_record_write_failed:<state>`, never
  a successful extraction;
- keeps a temporary only when it carries the child's pid;
- has recovery treat temporaries as evidence. In particular, a pid found only in a
  temporary is stopped, where before the run was recovered as pid-less.

Regressions are in `tools/document_worker/tests/test_record_replace_race.py`, including a
real open-handle case on Windows.

## Not claimed

- OS-level network or filesystem isolation of the parser (see the worker protocol).
- OCR, PDF table typing, an LLM narrative or measured throughput.
- Hosting, authentication beyond the existing local bearer sessions, private-customer
  documents, or retention beyond the one-hour handle lease and explicit deletion.
