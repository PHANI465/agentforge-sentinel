"""G3D-P1 R41/R42: the manual runner fails safely at each boundary and reports truthfully.

Faults are test-owned: a trigger in a separate schema that raises a canary-bearing error
once a first case exists, or a narrow query fault around one runner function. Cases use
only their runtime inputs; deterministic comparators only, no live flag, no provider call.
Policy under test (evaluator-runbook.md §3):
- a preflight failure is a typed refusal (exit 2, nothing written);
- a setup failure (provision, authenticate, ingest) is not an attempt: the run stops,
  earlier attempts are kept, and the report says what stopped and what never started
  (exit 3);
- an investigate failure is an attempt (counted, with its request latency);
- a failed usage read keeps the known outcome and makes usage unavailable, never reported.
"""
import importlib.util
import json
from pathlib import Path

import psycopg
import pytest
from psycopg import sql

from sentinel.investigators import DeterministicInvestigator
from sentinel.service import Sentinel
from test_agent_eval_privileges import count, runner, runtime_role

ROOT = Path(__file__).resolve().parents[1]
CANARY = "CANARY-eval-driver-message-3d41a7"


def module():
    spec = importlib.util.spec_from_file_location("agent_eval_under_test",
                                                  ROOT / "scripts" / "agent_eval.py")
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def fail_after_first_case(owner_url, table):
    """Inserts into `table` raise a canary-bearing error once any case exists."""
    with psycopg.connect(owner_url, autocommit=True) as conn:
        conn.execute("CREATE SCHEMA eval_fault")
        conn.execute(sql.SQL("""
            CREATE FUNCTION eval_fault.fail() RETURNS trigger LANGUAGE plpgsql
            SECURITY DEFINER SET search_path = pg_catalog AS $$ BEGIN
              IF (SELECT count(*) FROM public.cases) > 0 THEN RAISE EXCEPTION '%', {}; END IF;
              RETURN NEW; END $$""").format(sql.Literal(CANARY)))
        conn.execute(sql.SQL("CREATE TRIGGER eval_fault BEFORE INSERT ON {} FOR EACH ROW"
                             " EXECUTE FUNCTION eval_fault.fail()").format(
            sql.Identifier("public", table)))


def awaiting(owner_url) -> int:
    with psycopg.connect(owner_url) as conn:
        return conn.execute("SELECT count(*) FROM cases WHERE state = 'awaiting_approval'"
                            ).fetchone()[0]


def assert_safe(output):
    assert CANARY not in output and "Traceback" not in output, output


# ---- R41: setup failures stop the run, keep earlier attempts and are not attempts ----------

@pytest.mark.parametrize("table, phase, sessions", [("api_sessions", "provision", 1),
                                                     ("transactions", "ingest", 2)])
def test_a_setup_failure_keeps_the_earlier_attempt_and_is_not_an_attempt(
        database_url, table, phase, sessions):
    _role, rt = runtime_role(database_url)
    fail_after_first_case(database_url, table)
    code, output = runner("--cases", "D01,D02", operator=database_url, runtime=rt)
    assert_safe(output)
    assert code == 3, output
    report = json.loads(output)
    assert report["record"]["status"] == "incomplete"
    stopped = report["record"]["stopped"]
    assert (stopped["comparator"], stopped["case"], stopped["phase"]) == ("C0", "D02", phase)
    assert stopped["code"] == "RaiseException"
    assert report["record"]["comparators_not_started"] == ["C2-det"]
    c0 = report["comparators"]["C0"]
    assert c0["counts"] == {"attempts": 1, "dispositions": 1}  # D02 never became a request
    assert [row["case"] for row in c0["attempts"]] == ["D01"]
    assert c0["cases_not_attempted"] == ["D02"]
    assert c0["tokens"] == "unknown"
    assert count(database_url, "api_sessions") == sessions and awaiting(database_url) == 1


def test_an_investigate_failure_is_a_counted_attempt(database_url):
    """A driver error inside the request is an attempt with a latency (a control on the
    request boundary: the run continues and completes)."""
    _role, rt = runtime_role(database_url)
    fail_after_first_case(database_url, "agent_runs")
    code, output = runner("--comparators", "C0", "--cases", "D01,D02", operator=database_url,
                          runtime=rt)
    assert_safe(output)
    assert code == 0, output
    report = json.loads(output)
    assert report["record"]["status"] == "complete" and report["record"]["stopped"] is None
    rows = report["comparators"]["C0"]["attempts"]
    assert [(r["case"], r["outcome"], r.get("code")) for r in rows] == [
        ("D01", "error", "RaiseException"), ("D02", "error", "RaiseException")]
    assert all(r["request_latency_s"] > 0 for r in rows)
    assert report["comparators"]["C0"]["counts"] == {"attempts": 2, "error": 2}


# ---- R41: a failed usage read keeps the committed outcome ----------------------------------

def test_a_failed_usage_read_keeps_the_known_outcome(database_url, monkeypatch):
    runner_module = module()
    _role, rt = runtime_role(database_url)

    def unavailable(*_args):
        raise psycopg.OperationalError(CANARY)
    monkeypatch.setattr(runner_module, "usage_sources", unavailable)
    provisioner = Sentinel(database_url, DeterministicInvestigator())
    row = runner_module.attempt(provisioner, rt, runner_module.comparator("C2-det"), "D01")
    assert row["outcome"] == "disposition" and row["case_state"] == "awaiting_approval"
    assert row["usage_sources"] == ["unavailable"] and row["usage_error"] == "OperationalError"
    assert row["request_latency_s"] > 0
    assert_safe(json.dumps(row))
    assert awaiting(database_url) == 1  # committed; nothing claims a rollback


# ---- R41: preflight catalog queries are inside the typed refusal boundary ------------------

@pytest.mark.parametrize("side", ["runtime", "operator"])
def test_a_preflight_query_failure_is_a_typed_refusal(database_url, monkeypatch, side):
    runner_module = module()
    _role, rt = runtime_role(database_url)
    real = runner_module._connect

    class FailingQueries:
        def __init__(self, conn):
            self.conn = conn

        def __enter__(self):
            self.conn.__enter__()
            return self

        def __exit__(self, *exc):
            return self.conn.__exit__(*exc)

        def execute(self, *_args, **_kw):
            raise psycopg.OperationalError(CANARY)

    monkeypatch.setattr(runner_module, "_connect", lambda url, which: FailingQueries(
        real(url, which)) if which == side else real(url, which))
    with pytest.raises(runner_module.Refused) as refusal:
        runner_module.verify_authorities(database_url, rt)
    assert refusal.value.code == f"{side}_check_failed"
    assert CANARY not in refusal.value.detail
    assert count(database_url, "api_sessions") == 0


# ---- R42: usage is reported only when every attempt's provenance is reported ---------------

@pytest.mark.parametrize("second, tokens", [
    ("missing", "unknown"), ("unknown", "unknown"), ("unavailable", "unknown"),
    ("no_role_steps", "unknown"), ("adapter_reported", "adapter_reported")])
def test_usage_is_unknown_unless_every_attempt_reported_it(monkeypatch, second, tokens):
    runner_module = module()
    rows = [{"case": "D01", "outcome": "disposition", "request_latency_s": 0.1,
             "usage_sources": ["adapter_reported"]},
            {"case": "D02", "outcome": "error", "code": "OperationalError",
             "request_latency_s": 0.1}]
    if second != "missing":
        rows[1]["usage_sources"] = [second]
    monkeypatch.setattr(runner_module, "attempt", lambda *_args: rows.pop(0))
    monkeypatch.setattr(runner_module, "comparator", lambda _name: object())
    result = runner_module.run("unused", "unused", ["C2-det"], ["D01", "D02"])
    assert result["C2-det"]["counts"] == {"attempts": 2, "dispositions": 1, "error": 1}
    assert result["C2-det"]["tokens"] == tokens


# ---- duplicate comparator names --------------------------------------------------------

def test_duplicate_comparator_names_are_refused_before_any_work(database_url):
    _role, rt = runtime_role(database_url)
    code, output = runner("--comparators", "C0,C0", "--cases", "D01", operator=database_url,
                          runtime=rt)
    assert code == 2 and "refused: duplicate_comparator" in output, output
    assert count(database_url, "api_sessions") == 0 and count(database_url, "cases") == 0
