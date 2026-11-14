"""Record real bridge answers for the app's contract examples and API tests (DOC01 Part B).

Runs the registered worker bridge exactly as the API does (a fresh `-I -m docworker.bridge`
process per request) over the synthetic fixtures and writes their compact `analyze` answers
and one `records` page per fixture. Run from this worker project:

    uv run --locked python scripts/record_bridge_fixtures.py ../../tests/fixtures/doc01

The answers carry this worker's version, source digest and library versions at record time.
They are synthetic fixtures only; no private document is ever recorded.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"
PROTOCOL = "sentinel.doc01.bridge/0.1"
OWNER = "recorded-fixture-owner-key-0000000000000000"
CASES = {  # fixture -> (page_limit, records page offset or None)
    "csv_statement_usd.csv": (5, 5), "csv_statement_mismatch.csv": (100, None),
    "csv_two_currency.csv": (100, None), "csv_missing_duplicates.csv": (100, None),
    "csv_ambiguous_decimal.csv": (100, None), "csv_comma_decimal.csv": (100, None),
    "csv_hostile_note.csv": (100, None), "xlsx_statement.xlsx": (100, None),
    "xlsx_hostile.xlsx": (100, None), "xlsx_macro.xlsx": (100, None),
    "pdf_text_statement.pdf": (100, None), "pdf_scanned_mixed.pdf": (100, None),
    "pdf_encrypted.pdf": (100, None), "pdf_truncated.pdf": (100, None),
}
REFUSED_AT_INGEST = ("pdf_not_really.pdf", "xlsx_ole_container.xlsx")


def call(store, header, body=b""):
    env = {"SENTINEL_DOC_SESSION": OWNER, "PYTHONIOENCODING": "utf-8"}
    for key in ("SYSTEMROOT", "WINDIR", "PATH"):
        if key in os.environ:
            env[key] = os.environ[key]
    line = (json.dumps({"protocol": PROTOCOL, **header}) + "\n").encode()
    proc = subprocess.run([sys.executable, "-I", "-m", "docworker.bridge", "--store",
                           str(store)], input=line + body, capture_output=True, env=env,
                          timeout=180, check=True)
    return json.loads(proc.stdout.decode("utf-8"))


def main(out_dir: str) -> int:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        sys.path.insert(0, str(ROOT / "src"))
        from docworker.handles import HandleStore
        store = Path(tmp) / "store"
        HandleStore(store).init()
        status = call(store, {"op": "status"})
        recorded = {"status": status, "fixtures": {}}
        for name, (limit, offset) in CASES.items():
            data = (FIXTURES / name).read_bytes()
            fmt = name.rsplit(".", 1)[1]
            ingest = call(store, {"op": "ingest", "format": fmt, "size": len(data)}, data)
            assert ingest["ok"], (name, ingest)
            handle = ingest["handle"]["handle_id"]
            entry = {"format": fmt, "size": len(data),
                     "analyze": call(store, {"op": "analyze", "handle": handle,
                                             "page_limit": limit, "options": {}})}
            if offset is not None:
                entry["records"] = call(store, {"op": "records", "handle": handle,
                                                "offset": offset, "limit": 100})
            call(store, {"op": "delete", "handle": handle})
            recorded["fixtures"][name] = entry
        recorded["ingest_refusals"] = {}
        for name in REFUSED_AT_INGEST:
            data = (FIXTURES / name).read_bytes()
            recorded["ingest_refusals"][name] = call(
                store, {"op": "ingest", "format": name.rsplit(".", 1)[1], "size": len(data)},
                data)
    (out / "bridge_recorded.json").write_text(
        json.dumps(recorded, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    print(f"recorded {len(CASES)} fixtures with worker {status['worker_source_sha256'][:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
