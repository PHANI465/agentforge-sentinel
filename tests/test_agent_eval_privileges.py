"""G3D-P1: the manual comparator runner separates operator and runtime authority.

The operator (schema owner) may only verify the runtime identity and issue sessions; every
authentication, ingestion, evidence read and investigation runs as the granted
least-privilege runtime role. Authority is proven by the database itself: a test-owned
SECURITY DEFINER trigger records the login (session_user) of every insert into the session,
case-data and workflow tables. The runner runs as a real subprocess against disposable
Postgres with deterministic comparators only; no live comparator flag, no provider call.
"""
import json
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from sentinel import devdb
from sentinel.agents import coordinator
from sentinel.db import roles
from sentinel.investigators import DeterministicInvestigator
from sentinel.service import Sentinel

sys.path.insert(0, str(Path(__file__).resolve().parent / "support"))

import agent_cases as ac  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "agent_eval.py"
PASSWORD_CANARY = "CANARY-pw-7f3a91c2"
URL_CANARY = "canary_app_5be0"  # an application_name: shows if a connection string leaks
TOKEN = re.compile(r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])")
PROBED = ("api_sessions", "transactions", "cases", "evidence_items", "agent_runs",
          "agent_workflows", "agent_steps")


def install_probe(owner_url):
    """Record session_user for every insert into PROBED (outside schema public, so the
    accepted runtime grant map and environment checks are unchanged)."""
    with psycopg.connect(owner_url, autocommit=True) as conn:
        conn.execute("CREATE SCHEMA eval_probe")
        conn.execute("CREATE TABLE eval_probe.writes (tbl text NOT NULL, who text NOT NULL)")
        conn.execute("""
            CREATE FUNCTION eval_probe.record() RETURNS trigger LANGUAGE plpgsql
            SECURITY DEFINER SET search_path = pg_catalog AS $$
            BEGIN
              INSERT INTO eval_probe.writes VALUES (TG_TABLE_NAME, session_user);
              RETURN NULL;
            END $$""")
        for table in PROBED:
            conn.execute(sql.SQL("CREATE TRIGGER eval_probe AFTER INSERT ON {} FOR EACH ROW"
                                 " EXECUTE FUNCTION eval_probe.record()").format(
                sql.Identifier("public", table)))


def writers(owner_url) -> dict[str, set[str]]:
    with psycopg.connect(owner_url) as conn:
        found = {}
        for table, who in conn.execute("SELECT tbl, who FROM eval_probe.writes"):
            found.setdefault(table, set()).add(who)
        return found


def count(owner_url, table) -> int:
    with psycopg.connect(owner_url) as conn:
        return conn.execute(sql.SQL("SELECT count(*) FROM {}").format(
            sql.Identifier(table))).fetchone()[0]


def runtime_role(owner_url) -> tuple[str, str]:
    """A production runtime role with a canary password: (role, runtime URL)."""
    role = f"sentinel_rt_{uuid.uuid4().hex[:10]}"
    roles.grant_runtime(owner_url, role, PASSWORD_CANARY)
    return role, make_conninfo(owner_url, user=role, password=PASSWORD_CANARY)


def user_of(url) -> str:
    with psycopg.connect(url) as conn:
        return conn.execute("SELECT session_user").fetchone()[0]


def runner(*args, operator=None, runtime=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith("SENTINEL_EVAL_")}
    if operator is not None:
        env["SENTINEL_EVAL_OPERATOR_URL"] = operator
    if runtime is not None:
        env["SENTINEL_EVAL_RUNTIME_URL"] = runtime
    done = subprocess.run([sys.executable, str(RUNNER), *args], capture_output=True,
                          text=True, timeout=180, env=env, cwd=ROOT)
    return done.returncode, done.stdout + done.stderr


def assert_no_secrets(output, *urls):
    assert PASSWORD_CANARY not in output and URL_CANARY not in output
    for url in urls:
        assert url not in output
        password = conninfo_to_dict(url).get("password")
        assert not password or password not in output
    assert not TOKEN.search(output), "a bearer-token-shaped string was printed"


@pytest.fixture
def operator_url(database_url):
    return make_conninfo(database_url, application_name=URL_CANARY)


# ---- the runtime role's own boundary (a control: grants are unchanged) ----------------------

def test_runtime_role_cannot_provision_or_alter_schema_but_runs_the_case(database_url):
    _role, rt = runtime_role(database_url)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        Sentinel(rt, DeterministicInvestigator()).create_session(ac.ANALYST)
    for statement in ("CREATE TABLE public.eval_extra (id int)",
                      "ALTER TABLE public.cases ADD COLUMN eval_extra int",
                      "DROP TRIGGER audit_events_no_update ON public.audit_events",
                      "DELETE FROM public.cases"):
        with psycopg.connect(rt) as conn, pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(statement)
    token = Sentinel(database_url, DeterministicInvestigator()).create_session(ac.ANALYST)[0]
    svc = Sentinel(rt, coordinator.deterministic_workflow())
    ctx = svc.authenticate(token)
    case = ac.seed(svc, ctx, "D01", svc.clock)["case"]
    detail = svc.investigate(ctx, case["id"], case["revision"])
    assert detail["case"]["state"] == "awaiting_approval"


# ---- authority separation in the runner ---------------------------------------------------

def test_runner_provisions_as_operator_and_investigates_as_runtime(database_url, operator_url):
    """--database-url is provisioning-only: sessions are inserted by the operator login,
    every case, evidence, run, workflow and step row by the runtime login."""
    install_probe(database_url)
    role, rt = runtime_role(database_url)
    operator = user_of(database_url)
    code, output = runner("--database-url", operator_url, "--comparators", "C0,C2-det",
                          "--cases", "D01,D04", runtime=rt)
    assert code == 0, output
    written = writers(database_url)
    assert written["api_sessions"] == {operator}
    for table in ("transactions", "cases", "evidence_items", "agent_runs", "agent_workflows",
                  "agent_steps"):
        assert written.get(table) == {role}, (table, written.get(table))
    assert count(database_url, "api_sessions") == 4  # one fresh session per attempt
    assert_no_secrets(output, operator_url, rt)


def test_environment_configuration_runs_the_deterministic_comparators(database_url,
                                                                      operator_url):
    install_probe(database_url)
    role, rt = runtime_role(database_url)
    code, output = runner("--cases", "D01,D02", operator=operator_url, runtime=rt)
    assert code == 0, output
    report = json.loads(output)
    assert set(report["comparators"]) == {"C0", "C2-det"}  # the deterministic defaults
    for result in report["comparators"].values():
        assert result["counts"]["attempts"] == 2
        assert result["counts"].get("dispositions", 0) + result["counts"].get(
            "inconclusive", 0) == 2
        assert result["tokens"] == "unknown"  # deterministic adapters measure nothing
    assert report["record"]["authorities"]["runtime_verified"] is True
    assert writers(database_url)["transactions"] == {role}
    assert_no_secrets(output, operator_url, rt)


# ---- refusals: before any provisioning, comparator or case run ----------------------------

def refused(database_url, output, code, expected):
    assert code == 2 and f"refused: {expected}" in output, output
    assert count(database_url, "api_sessions") == 0
    assert count(database_url, "transactions") == 0


def test_operator_url_alone_is_refused_not_used_for_investigations(database_url,
                                                                   operator_url):
    code, output = runner("--database-url", operator_url, "--cases", "D01")
    refused(database_url, output, code, "runtime_config_missing")
    assert_no_secrets(output, operator_url)


def test_missing_operator_configuration_is_refused(database_url):
    _role, rt = runtime_role(database_url)
    code, output = runner("--cases", "D01", runtime=rt)
    refused(database_url, output, code, "operator_config_missing")
    assert_no_secrets(output, rt)


def test_runtime_on_a_different_database_is_refused(database_url, operator_url):
    _role, rt = runtime_role(database_url)
    other = make_conninfo(rt, dbname="postgres")  # PUBLIC CONNECT: the login succeeds
    code, output = runner("--cases", "D01", operator=operator_url, runtime=other)
    refused(database_url, output, code, "database_mismatch")
    assert_no_secrets(output, operator_url, other)


@pytest.mark.parametrize("unsafe", ["operator", "superuser", "extra_grant"])
def test_unsafe_runtime_identity_is_refused(database_url, operator_url, make_role, unsafe):
    if unsafe == "operator":  # the owner itself, under a different-looking URL
        rt = make_conninfo(database_url, application_name="eval_runtime")
    elif unsafe == "superuser":
        role = make_role("LOGIN NOINHERIT SUPERUSER", password=PASSWORD_CANARY)
        rt = make_conninfo(database_url, user=role, password=PASSWORD_CANARY)
    else:  # a granted runtime role that also holds DELETE on cases
        role, rt = runtime_role(database_url)
        with psycopg.connect(database_url, autocommit=True) as conn:
            conn.execute(sql.SQL("GRANT DELETE ON public.cases TO {}").format(
                sql.Identifier(role)))
    code, output = runner("--cases", "D01", operator=operator_url, runtime=rt)
    refused(database_url, output, code, "runtime_unsafe")
    assert_no_secrets(output, operator_url, rt)


@pytest.mark.parametrize("side", ["runtime", "operator"])
def test_unreachable_configuration_fails_safely(database_url, operator_url, side):
    _role, rt = runtime_role(database_url)
    dead = make_conninfo(rt, host="127.0.0.1", port=str(devdb.free_port()),
                         user="canary_user_c4e1", connect_timeout="3")
    urls = {"runtime": rt, "operator": operator_url, side: dead}
    code, output = runner("--cases", "D01", operator=urls["operator"],
                          runtime=urls["runtime"])
    refused(database_url, output, code, f"{side}_connection_failed")
    assert "canary_user_c4e1" not in output and "Traceback" not in output
    assert_no_secrets(output, *urls.values())
