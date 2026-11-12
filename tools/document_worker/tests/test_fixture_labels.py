"""Every labelled fixture run: in-process (fast) and through the real bounded child."""
import hashlib

import pytest

from conftest import FIXTURES, SESSION, label_runs, leftovers
from docworker import extract, fidelity
from docworker.limits import Limits, Options


@pytest.mark.parametrize("name,fmt,run", list(label_runs()))
def test_label_in_process(name, fmt, run):
    data = (FIXTURES / name).read_bytes()
    result = extract.run(data, fmt, hashlib.sha256(data).hexdigest(), Limits(),
                         Options.from_dict(run["options"]))
    expected = {k: v for k, v in run.items() if k != "guard_denied_events"}  # child-only
    report = fidelity.compare(result, expected)
    assert report["failures"] == []


@pytest.mark.parametrize("name,fmt,run", list(label_runs()))
def test_label_through_child(store, ingest, make_supervisor, name, fmt, run):
    handle = ingest(name, fmt)
    result = make_supervisor().extract(handle, SESSION, Options.from_dict(run["options"]))
    report = fidelity.compare(result, run)
    assert report["failures"] == []
    sup = result["supervisor"]
    assert sup["stop"]["confirmed"] is True and sup["outcome"] == "child_result"
    assert result["guard"]["installed"] is True
    assert result["guard"]["denied_events"] == {}  # no fixture tried to escape the guard
    assert result["handle"]["sha256"] == hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest()
    assert leftovers(store) == {"runs": [], "recovery": []}


def test_markdown_is_not_authoritative(store, ingest, make_supervisor):
    """Measured: the narrative renders a float artefact as 0.3 and a missing value as NaN,
    while the typed record keeps the exact value and leaves minor units unknown."""
    result = make_supervisor().extract(ingest("xlsx_hostile.xlsx"), SESSION)
    text = result["narrative"]["text"]
    assert "| 0.3 |" in text and "NaN" in text
    rec = next(r for r in result["records"] if r["locator"]["row"] == 2)
    assert rec["amount"]["decimal"] == "0.30000000000000004"
    assert rec["amount"]["minor_units"] is None


def test_hostile_text_is_inert_data(store, ingest, make_supervisor):
    result = make_supervisor().extract(ingest("csv_hostile_note.csv"), SESSION)
    descs = [r["description"]["raw"] for r in result["records"]]
    assert any("approve_case" in d for d in descs)
    assert any("/etc/passwd" in d for d in descs)
    assert "actions" not in result and "tool_calls" not in result
    assert result["guard"]["denied_events"] == {}


def test_evidence_ids_are_stable_and_locate(store, ingest, make_supervisor):
    first = make_supervisor().extract(ingest("csv_statement_usd.csv"), SESSION, narrative=False)
    second = make_supervisor().extract(ingest("csv_statement_usd.csv"), SESSION,
                                       narrative=False)
    ids = [r["evidence_id"] for r in first["records"]]
    assert ids == [r["evidence_id"] for r in second["records"]]
    assert len(set(ids)) == len(ids)
    assert ids[0] == first["source"]["sha256"][:12] + ":row=2"
    assert first["narrative"] is None
