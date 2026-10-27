"""H01: real PostgreSQL rejects accidental writes before the inspector's first query.

Only manifest URL loading is replaced. The actual CLI entry point, connection context and
database read-only enforcement run; a canary write is injected where a future SQL edit
could accidentally introduce one. No credential or raw database error may be printed.
"""
import importlib.util
import json
import sys
import uuid
from pathlib import Path

import pytest

from sentinel.db import connect

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "sentinel_browser_inspection", ROOT / "web/e2e/support/inspect_case.py")
inspector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inspector)


@pytest.mark.parametrize("selector", [
    ["--external-id", "h01-example", "--presence"],
    ["--external-id", "h01-example", "--scoring"],
    ["--case-id", str(uuid.UUID(int=1)), "--scoring"],
    ["--external-id", "h01-example"],
    ["--case-id", str(uuid.UUID(int=1))],
], ids=["presence", "scoring-external", "scoring-case", "case-external", "case-id"])
def test_inspection_rejects_a_write_before_its_first_query(
        database_url, selector, monkeypatch, capsys):
    with connect(database_url) as conn:
        conn.execute("CREATE TABLE h01_write_canary (marker text PRIMARY KEY)")
        conn.execute("INSERT INTO h01_write_canary VALUES ('owner-write-control')")
    observed = {"attempted": False, "sqlstate": None, "write_succeeded": False}

    class ProbeConnection:
        def __init__(self, url):
            self.raw = connect(url)

        def __enter__(self):
            self.raw.__enter__()
            return self

        def __exit__(self, *args):
            return self.raw.__exit__(*args)

        @property
        def read_only(self):
            return self.raw.read_only

        @read_only.setter
        def read_only(self, value):
            self.raw.read_only = value

        def execute(self, *args, **kwargs):
            if not observed["attempted"]:
                observed["attempted"] = True
                try:
                    self.raw.execute("INSERT INTO h01_write_canary VALUES ('unexpected-write')")
                    observed["write_succeeded"] = True
                except Exception as error:
                    observed["sqlstate"] = getattr(error, "sqlstate", None)
                    raise
            return self.raw.execute(*args, **kwargs)

    monkeypatch.setattr(inspector, "connect", ProbeConnection)
    monkeypatch.setattr(inspector, "load_url", lambda manifest: database_url)
    monkeypatch.setattr(sys, "argv", ["inspect_case.py", "--manifest", "not-opened", *selector])
    try:
        inspector.main()
    except SystemExit as error:
        assert error.code == 1
    assert observed["attempted"]
    assert observed["sqlstate"] == "25006"  # PostgreSQL read_only_sql_transaction
    assert observed["write_succeeded"] is False
    output = capsys.readouterr()
    assert json.loads(output.out) == {"error": "query_failed"}
    assert output.err == "" and database_url not in output.out
    with connect(database_url) as conn:
        rows = conn.execute("SELECT marker FROM h01_write_canary ORDER BY marker").fetchall()
    assert [r["marker"] for r in rows] == ["owner-write-control"]
