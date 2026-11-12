"""Regressions for review DOC01-cecccad: R58 (POSIX group recovery) and R59 (child output)."""
import json
import os
import signal
import subprocess
import sys
import time

import pytest

from conftest import SESSION, fake_argv, leftovers
from docworker.handles import HandleStore
from docworker.supervisor import Supervisor, process_identity
from test_supervisor import _plant_record

posix_only = pytest.mark.skipif(
    os.name == "nt", reason="POSIX process groups; on Windows the parser runs in a job with one "
    "active process and kill-on-close (see test_grandchild_cannot_outlive_supervision)")

# A session leader that starts one sleeping member in its own process group, prints the
# member's pid, then lives for argv[1] seconds.
LEADER = ("import subprocess, sys, time; "
          "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)']); "
          "print(p.pid, flush=True); time.sleep(float(sys.argv[1]))")


def _wait(predicate, seconds=10.0):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return predicate()


def _pgid(pid):
    try:
        return os.getpgid(pid)
    except ProcessLookupError:
        return None


def _start_group(leader_seconds: float):
    leader = subprocess.Popen([sys.executable, "-c", LEADER, str(leader_seconds)],
                              start_new_session=True, stdout=subprocess.PIPE, text=True)
    member = int(leader.stdout.readline())
    assert _wait(lambda: process_identity(leader.pid) and process_identity(member))
    return leader, member


def _stop_verified(pid, identity):
    """The test stops only a process whose recorded identity it re-verifies."""
    if identity is not None and process_identity(pid) == identity:
        os.kill(pid, signal.SIGKILL)
    assert _wait(lambda: process_identity(pid) != identity)


def _fresh_recover(store):
    return Supervisor(HandleStore(store.root)).recover()


@posix_only
def test_r58_leader_exited_member_alive_is_kept_not_recovered(store):
    leader, member = _start_group(0.5)
    member_identity = process_identity(member)
    try:
        run_id = _plant_record(store, leader.pid, process_identity(leader.pid))
        leader.wait(timeout=10)
        assert process_identity(member) == member_identity and _pgid(member) == leader.pid
        report = _fresh_recover(store)["records"]
        assert len(report) == 1 and report[0]["result"] != "recovered"
        assert "terminated_pid" not in report[0]
        assert leftovers(store) == {"runs": [run_id], "recovery": [f"{run_id}.json"]}
        assert process_identity(member) == member_identity  # never signalled
        _stop_verified(member, member_identity)
        retry = _fresh_recover(store)["records"]
        assert [r["result"] for r in retry] == ["recovered"]
        assert leftovers(store) == {"runs": [], "recovery": []}
    finally:
        if process_identity(member) == member_identity:
            _stop_verified(member, member_identity)


@posix_only
def test_r58_live_leader_and_member_are_stopped_and_confirmed(store):
    leader, member = _start_group(120)
    member_identity = process_identity(member)
    try:
        _plant_record(store, leader.pid, process_identity(leader.pid))
        report = _fresh_recover(store)["records"]
        assert [r["result"] for r in report] == ["recovered"]
        leader.wait(timeout=10)
        assert _wait(lambda: process_identity(member) != member_identity)
        assert leftovers(store) == {"runs": [], "recovery": []}
    finally:
        if leader.poll() is None:
            leader.kill()
        if process_identity(member) == member_identity:
            os.kill(member, signal.SIGKILL)


def _codes(result):
    return [e["code"] for e in result.get("errors") or []]


def test_r59_nonzero_exit_with_complete_document_is_an_error(store, ingest, make_supervisor):
    result = make_supervisor(child_argv=fake_argv("complete_nonzero")).extract(
        ingest("csv_statement_usd.csv"), SESSION)
    assert result["status"] == "error"
    assert "invalid_child_output:exit_7" in _codes(result)
    assert "records" not in result or not result["records"]
    assert leftovers(store) == {"runs": [], "recovery": []}


def test_r59_complete_document_missing_required_fields_is_an_error(store, ingest,
                                                                   make_supervisor):
    result = make_supervisor(child_argv=fake_argv("complete_minimal")).extract(
        ingest("csv_statement_usd.csv"), SESSION)
    assert result["status"] == "error"
    assert "invalid_child_output:exit_0" in _codes(result)
    assert leftovers(store) == {"runs": [], "recovery": []}


def test_r59_protocol_error_document_is_returned_as_error(store, ingest, make_supervisor):
    result = make_supervisor(child_argv=fake_argv("protocol_error")).extract(
        ingest("csv_statement_usd.csv"), SESSION)
    assert result["status"] == "error"
    assert _codes(result) == ["integrity_mismatch"]
    assert result["supervisor"]["exit_code"] == 2


@pytest.mark.parametrize("name,status", [("csv_statement_usd.csv", "complete"),
                                         ("csv_comma_decimal.csv", "partial"),
                                         ("pdf_encrypted.pdf", "unsupported"),
                                         ("pdf_not_really.pdf", "error")])
def test_r59_genuine_child_positive_controls(store, ingest, make_supervisor, name, status):
    result = make_supervisor().extract(ingest(name), SESSION)
    assert result["status"] == status
    assert result["supervisor"]["exit_code"] == 0
    assert not any(c.startswith("invalid_child_output") for c in _codes(result))
    assert json.dumps(result)  # serialisable for later consumers


@posix_only
def test_r58_member_surviving_the_group_kill_keeps_the_record(store, monkeypatch):
    """If the group cannot be confirmed empty after stopping a verified leader, nothing is
    reported recovered and the record and owned run dir stay for a later retry."""
    import docworker.supervisor as sv
    leader, member = _start_group(120)
    member_identity = process_identity(member)
    try:
        run_id = _plant_record(store, leader.pid, process_identity(leader.pid))
        monkeypatch.setattr(sv, "group_members", lambda pgid: [member])
        report = Supervisor(HandleStore(store.root)).recover()["records"]
        assert [r["result"] for r in report] == ["group_members_alive_kept"]
        assert leftovers(store) == {"runs": [run_id], "recovery": [f"{run_id}.json"]}
        monkeypatch.undo()
        assert [r["result"] for r in _fresh_recover(store)["records"]] == ["recovered"]
    finally:
        if leader.poll() is None:
            leader.kill()
        if process_identity(member) == member_identity:
            os.kill(member, signal.SIGKILL)


@posix_only
def test_r58_unknown_group_state_fails_closed(store, monkeypatch):
    import docworker.supervisor as sv
    run_id = _plant_record(store, 999999, "linux-start:1")  # leader gone
    monkeypatch.setattr(sv, "group_members", lambda pgid: None)
    report = Supervisor(HandleStore(store.root)).recover()["records"]
    assert [r["result"] for r in report] == ["group_state_unknown_kept"]
    assert leftovers(store)["runs"] == [run_id]


# ---- R59 validator unit tests over genuine results -------------------------------------------

def _genuine(name, fmt, **options):
    import hashlib
    from conftest import FIXTURES
    from docworker import extract
    from docworker.limits import Limits, Options
    data = (FIXTURES / name).read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    doc = extract.run(data, fmt, sha, Limits(), Options(**options))
    doc.update(request_id="q_test", guard={"installed": True, "denied_events": {}})
    expected = {"format": fmt, "sha256": sha, "size": len(data),
                "max_records": Limits().max_records}
    return doc, expected


def _check(doc, expected, exit_code=0):
    from docworker.validate import validate
    return validate(json.loads(json.dumps(doc)), "q_test", exit_code, expected)


@pytest.mark.parametrize("name,fmt,status", [
    ("csv_statement_usd.csv", "csv", "complete"), ("xlsx_statement.xlsx", "xlsx", "complete"),
    ("pdf_text_statement.pdf", "pdf", "complete"), ("csv_comma_decimal.csv", "csv", "partial"),
    ("xlsx_hostile.xlsx", "xlsx", "partial"), ("pdf_scanned_mixed.pdf", "pdf", "partial"),
    ("xlsx_macro.xlsx", "xlsx", "unsupported"), ("pdf_truncated.pdf", "pdf", "error")])
def test_r59_validator_accepts_genuine_results(name, fmt, status):
    doc, expected = _genuine(name, fmt)
    assert doc["status"] == status
    assert _check(doc, expected)["status"] == status


REQUIRED = ("format", "source", "parser", "units", "records", "unparsed", "unparsed_total",
            "findings", "typed", "measures", "coverage", "guard")


@pytest.mark.parametrize("field", REQUIRED)
def test_r59_validator_rejects_missing_required_field(field):
    from docworker.validate import Invalid
    doc, expected = _genuine("csv_statement_usd.csv", "csv")
    del doc[field]
    with pytest.raises(Invalid):
        _check(doc, expected)


def _mutations():
    def unit_unsupported(d):
        d["units"][0]["status"] = "unsupported"

    def unparsed(d):
        d["unparsed_total"] = 1

    def errors(d):
        d["errors"] = [{"code": "x", "detail": ""}]

    def narrative(d):
        d["narrative"]["status"] = "truncated"

    def wrong_sha(d):
        d["source"]["sha256"] = "0" * 64

    def wrong_format(d):
        d["format"] = "xlsx"

    def known_without_value(d):
        d["records"][1]["amount"]["minor_units"] = None

    def unknown_with_value(d):
        d["records"][1]["amount"]["status"] = "ambiguous"

    def non_integer_minor(d):
        d["records"][1]["amount"]["minor_units"] = "12.5"

    def foreign_evidence(d):
        d["records"][1]["evidence_id"] = "ffffffffffff:row=3"

    def bad_kind(d):
        d["records"][1]["kind"] = "approval"

    def guard_off(d):
        d["guard"]["installed"] = False

    def leaking_detail(d):
        d["status"] = "partial"
        d["errors"] = [{"code": "parser_exception", "detail": "x" * 500}]

    def bad_code(d):
        d["status"] = "partial"
        d["errors"] = [{"code": "Account 1234 / secret", "detail": ""}]

    return [unit_unsupported, unparsed, errors, narrative, wrong_sha, wrong_format,
            known_without_value, unknown_with_value, non_integer_minor, foreign_evidence,
            bad_kind, guard_off, leaking_detail, bad_code]


@pytest.mark.parametrize("mutate", _mutations(), ids=lambda f: f.__name__)
def test_r59_validator_rejects_inconsistent_success(mutate):
    from docworker.validate import Invalid
    doc, expected = _genuine("csv_statement_usd.csv", "csv")
    mutate(doc)
    with pytest.raises(Invalid):
        _check(doc, expected)


def test_r59_exit_codes():
    from docworker.validate import Invalid
    doc, expected = _genuine("csv_statement_usd.csv", "csv")
    for code in (1, 3, 7, None, -9):
        with pytest.raises(Invalid):
            _check(doc, expected, exit_code=code)
    with pytest.raises(Invalid):  # a success document cannot ride on the protocol-error exit
        _check(doc, expected, exit_code=2)
    proto = {"protocol": doc["protocol"], "request_id": "q_test", "status": "error",
             "errors": [{"code": "framing_mismatch", "detail": ""}], "records": [{"x": 1}]}
    clean = _check(proto, expected, exit_code=2)
    assert clean == {"protocol": doc["protocol"], "request_id": "q_test", "status": "error",
                     "errors": [{"code": "framing_mismatch", "detail": ""}]}
    unsupported, exp_u = _genuine("xlsx_macro.xlsx", "xlsx")
    unsupported["records"] = [{"kind": "transaction"}]
    with pytest.raises(Invalid):
        _check(unsupported, exp_u)
