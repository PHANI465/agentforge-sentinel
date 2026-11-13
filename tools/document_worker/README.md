# Sentinel document worker (DOC01 Part A)

A separately locked, local-only prototype that extracts typed evidence from **public or
synthetic** text-layer PDFs, CSVs and XLSX workbooks inside a bounded, owned child process.
It is not an application dependency, an HTTP endpoint or a browser upload. Its design and
protocol are frozen in [DOC01-worker-protocol-v0.1](../../docs/documents/DOC01-worker-protocol-v0.1.md).

## Install and test (from this directory)

```
uv sync --locked --extra dev
uv run --locked python -m ruff check .
uv run --locked python -m pytest -q
uv run --locked python scripts/smoke.py <out.json>      # serial labelled smoke + cap probes
uv run --locked python fixtures/generate.py <dir>        # regenerate fixtures elsewhere
```

The application's own gate does not collect these tests. Run and report them explicitly.
If a `VIRTUAL_ENV` from the application is active, unset it first so uv uses this
project's `.venv`.

## CLI

```
export SENTINEL_DOC_SESSION=<at least 16 characters>     # never passed on argv
uv run --locked sentinel-docworker init    --store STORE_DIR
uv run --locked sentinel-docworker ingest  --store STORE_DIR --format csv --file fixtures/csv_statement_usd.csv
uv run --locked sentinel-docworker extract --store STORE_DIR --handle h_... \
        [--decimal-style dot|comma] [--date-order dmy|mdy] [--default-currency USD] [--no-narrative]
uv run --locked sentinel-docworker delete  --store STORE_DIR --handle h_...
uv run --locked sentinel-docworker purge-expired --store STORE_DIR
uv run --locked sentinel-docworker recover --store STORE_DIR
```

`extract` exits 0 for `complete`/`partial`, 3 for `unsupported`/`error` and 4 for a refusal
(not found, invalid session, invalid option).

## Layout

| Path | Role |
| --- | --- |
| `src/docworker/handles.py` | Owned store, session-scoped opaque handles, verified copy-in/delete/purge |
| `src/docworker/supervisor.py` | Contained child lifecycle, caps, confirmed stop, recovery |
| `src/docworker/child.py` | stdio child entrypoint (bytes in, one JSON out) |
| `src/docworker/guard.py` | In-child audit-hook guard (defense in depth, not a sandbox) |
| `src/docworker/extract.py`, `tables.py`, `normalize.py` | Sniffing, typed extraction, exact values |
| `src/docworker/measures.py`, `fidelity.py` | Deterministic measures; label comparison |
| `fixtures/` | Synthetic fixtures, ground-truth `labels.json`, `MANIFEST.json` hashes, generator |
| `tests/` | Worker tests (`helpers/fake_child.py` is test-only) |

Everything the worker extracts is untrusted data. It has no tools, model calls, network
features, transaction ingestion or actions.
