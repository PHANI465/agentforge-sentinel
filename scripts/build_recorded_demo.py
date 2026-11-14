"""DEMO01: capture one synthetic case through the unchanged Sentinel service and project it
into the allowlisted fixture behind the static recorded replay in demo/.

    uv run --locked python scripts/build_recorded_demo.py capture [--keep-cluster]
    uv run --locked python scripts/build_recorded_demo.py validate [--data FILE]

`capture` starts its own disposable PostgreSQL cluster in .agent/demo01/ (the accepted
scripts/local_stack.py ownership machinery: marker, recorded identity, verified stop),
migrates it, grants the production least-privilege runtime role and has the operator issue
one analyst session. Everything after that runs as the runtime role through the production
HTTP app (sentinel.api.create_app, in process via the FastAPI TestClient, no network port):
rule scoring, the deterministic three-role workflow, a *scripted* approval and one simulated
execution plus an idempotent retry. No model, provider or auth call is made.

The raw capture stays private (.agent/demo01/, git-ignored). Only an explicit allowlisted
projection is written to demo/data/, after every generated file has been scanned for the
real session token (held in memory), its digest, connection strings, scope/actor
identifiers and local paths. A failed capture, validation or scan writes no public data and
never falls back to fixture or invented data.

`validate` re-checks the tracked fixture (chronology, pins, citations, approval/action
counts per frame, replay identity, audit order, manifest hash) without a database.
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import logging
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

DEMO_DIR = ROOT / "demo"
DATA_FILE = DEMO_DIR / "data" / "recorded-case.json"
MANIFEST_FILE = DEMO_DIR / "data" / "manifest.json"
PRIVATE_DIR = ROOT / ".agent" / "demo01"
SCHEMA = "sentinel.demo01.recorded-replay.v1"
DATABASE = "sentinel_demo01"
RUNTIME_ROLE = "sentinel_demo01_runtime"
# The application the capture was taken from; the capture records whether src/ equals it.
# Was accepted G3D-P3 495c7d3. DOC01 Part B changes src/ (v1.3 document routes, the
# R60-R63 corrections at cfa94ab, the R62 follow-ups at 097eb77 and 89c34ea), so the
# capture is retaken against that source; pending Codex review and integration.
TESTED_APPLICATION = "89c34ea4960322891faa89c0e003a6ff164e6cd6"
# Paths whose working-tree state must be committed for a capture to name its source commit.
GENERATOR_PATHS = ("src", "scripts", "contracts", "pyproject.toml", "uv.lock")
# Freshness inputs (R48): the generator and the application whose behaviour the capture
# records. Their canonical content digests are recorded at capture time and re-checked
# against the checkout's actual bytes, so freshness needs neither Git nor capture history.
CONTENT_SCOPE = ("scripts/build_recorded_demo.py", "src")
CANONICALIZATION = "sha256 of file bytes with CRLF replaced by LF"
# Untracked build/interpreter output under src/ that is not application input.
_IGNORED_DIRS = ("__pycache__",)
_IGNORED_DIR_SUFFIXES = (".egg-info",)
_IGNORED_FILE_SUFFIXES = (".pyc", ".pyo")
CAPABILITIES = frozenset({"ingest_transaction", "read_case", "approve_action",
                          "execute_simulated_action"})
LABELS = ("recorded", "synthetic", "rule baseline", "deterministic roles",
          "scripted approval", "simulated action")
STAGES = ("ingest", "case_opened", "analyst", "investigator", "reviewer", "proposal",
          "approval", "execution", "replay", "audit")
TITLES = {
    "ingest": "Synthetic transactions ingested and rule-scored",
    "case_opened": "Alert raised: case opened with pinned evidence",
    "analyst": "Evidence analyst and server-run read tools",
    "investigator": "Investigator proposal and server claim checks",
    "reviewer": "Reviewer verdict and workflow disposition",
    "proposal": "Exact action intent built by the server",
    "approval": "Scripted analyst approval recorded",
    "execution": "One simulated action executed",
    "replay": "Retry with the same idempotency key",
    "audit": "Audit trail for the whole case",
}
OBSERVATION_OF = {"ingest": "after_ingest", "case_opened": "case_opened",
                  "analyst": "after_investigation", "investigator": "after_investigation",
                  "reviewer": "after_investigation", "proposal": "after_investigation",
                  "approval": "after_approval", "execution": "after_execution",
                  "replay": "after_replay", "audit": "final"}
AUDIT_SEQUENCE = ("transaction_received", "alert_raised", "investigation_started",
                  "investigation_completed", "approval_recorded", "action_succeeded")
ACTOR_LABELS = ("scripted-analyst", "system", "three-role-workflow")
# Never present anywhere in the public fixture, at any depth.
FORBIDDEN_KEYS = {"scope", "tenant_id", "session_id", "token", "token_sha256", "password",
                  "actor_id", "principal_id", "dsn", "database_url", "authorization",
                  "stdout", "stderr", "prompt", "api_key"}
# One small coherent synthetic account: four earlier debits, then a large debit. Minutes
# are before the capture start; every event time therefore precedes the recording.
SCENARIO = {
    "id": "demo01-velocity-large-debit",
    "description": ("One synthetic account: four small earlier debits (two in the hour "
                    "before) followed by one large debit that crosses the rule threshold."),
    "currency": "USD",
    "history": [{"minutes_before": 9 * 24 * 60, "amount_minor": 8800},
                {"minutes_before": 2 * 24 * 60, "amount_minor": 12000},
                {"minutes_before": 40, "amount_minor": 2750},
                {"minutes_before": 20, "amount_minor": 3200}],
    "alerted": {"minutes_before": 2, "amount_minor": 245000},
}


class DemoError(RuntimeError):
    """Capture/validation failure. Messages carry codes and counts only, never secrets."""


# ---- capture (runtime role, production HTTP app) -----------------------------------------

@dataclass
class Capture:
    raw: dict
    token: str
    secrets: list[str] = field(default_factory=list)  # strings that must never be published
    log_lines: list[str] = field(default_factory=list)


class _Lines(logging.Handler):
    def __init__(self, sink: list[str]):
        super().__init__(logging.DEBUG)
        self.sink = sink

    def emit(self, record):
        self.sink.append(self.format(record))


def runtime_role_checks(runtime_url: str, role: str) -> dict:
    """Facts about the connection the API uses, read through that connection."""
    import psycopg

    from sentinel.investigators import DeterministicInvestigator
    from sentinel.service import Sentinel
    with psycopg.connect(runtime_url) as conn:
        user, superuser, createrole, createdb = conn.execute(
            "SELECT current_user, rolsuper, rolcreaterole, rolcreatedb FROM pg_roles"
            " WHERE rolname = current_user").fetchone()
        server = conn.execute("SHOW server_version").fetchone()[0]
    refused = False
    try:  # sessions are operator-issued; the runtime role may only read them
        Sentinel(runtime_url, DeterministicInvestigator()).create_session(CAPABILITIES)
    except psycopg.errors.InsufficientPrivilege:
        refused = True
    if user != role or superuser or createrole or createdb or not refused:
        raise DemoError("the API connection is not the restricted runtime role")
    return {"connected_as_runtime_role": True, "superuser": False, "createrole": False,
            "createdb": False, "session_issuance_refused": True,
            "postgres_server_version": server.split(" ")[0]}


def capture_case(owner_url: str, runtime_role: str, *, clock=None) -> Capture:
    """Run the scenario once. `owner_url` is a migrated database the caller owns."""
    from fastapi.testclient import TestClient
    from psycopg.conninfo import make_conninfo

    from sentinel import scoring
    from sentinel.agents import coordinator
    from sentinel.api import API_VERSION, create_app
    from sentinel.db import roles
    from sentinel.investigators import DeterministicInvestigator
    from sentinel.service import SYSTEM_ACTOR, Sentinel, token_digest, utc_now

    clock = clock or utc_now
    roles.grant_runtime(owner_url, runtime_role)
    runtime_url = make_conninfo(owner_url, user=runtime_role)
    # Operator: issue exactly one analyst session. Nothing else is done as the owner.
    token, ctx = Sentinel(owner_url, DeterministicInvestigator(), clock).create_session(
        CAPABILITIES, ttl=timedelta(hours=1))
    checks = runtime_role_checks(runtime_url, runtime_role)
    workflow = coordinator.deterministic_workflow()
    svc = Sentinel(runtime_url, workflow, clock)
    lines: list[str] = []
    handler = _Lines(lines)
    handler.setFormatter(logging.Formatter("%(name)s %(levelname)s %(message)s"))
    logger = logging.getLogger("sentinel")
    client = TestClient(create_app(svc))  # configures the sentinel logger; ours is added after
    logger.addHandler(handler)
    requests: list[dict] = []
    headers = {"Authorization": f"Bearer {token}"}

    def call(label, method, path, body=None, expect=200):
        response = client.request(method, path, json=body, headers=headers)
        if response.status_code != expect:
            code = response.json().get("code") if response.headers.get(
                "content-type", "").startswith("application/json") else None
            raise DemoError(f"{label}: HTTP {response.status_code} ({code})")
        payload = response.json()
        requests.append({"label": label, "method": method, "path": path,
                         "status": response.status_code, "at": clock().isoformat(),
                         "body": payload})
        return payload

    observations: dict[str, dict] = {}

    def observe(name, case_id):
        detail = call(f"{name}:case", "GET", f"/v1/cases/{case_id}")
        audit = call(f"{name}:audit", "GET", f"/v1/cases/{case_id}/audit")
        overview = call(f"{name}:overview", "GET", "/v1/overview")
        observations[name] = {"observed_at": clock().isoformat(), "detail": detail,
                              "audit": audit, "overview": overview}
        return detail

    try:
        started = clock()
        account = uuid.uuid4()
        prefix = f"demo01-{uuid.uuid4().hex[:6]}"
        ingests = []
        rows = [*({**r, "external_id": f"{prefix}-h{i}"}
                  for i, r in enumerate(SCENARIO["history"])),
                {**SCENARIO["alerted"], "external_id": f"{prefix}-alert"}]
        for row in rows:
            occurred = started - timedelta(minutes=row["minutes_before"])
            body = {"external_id": row["external_id"], "account_id": str(account),
                    "direction": "debit",
                    "amount": {"currency": SCENARIO["currency"],
                               "minor_units": row["amount_minor"], "currency_exponent": 2},
                    "occurred_at": occurred.isoformat()}
            ingests.append(call(f"ingest:{row['external_id']}", "POST", "/v1/transactions",
                                body, 201))
        alerted = ingests[-1]
        if alerted["case"] is None or any(i["alert"] for i in ingests[:-1]):
            raise DemoError("scenario did not alert exactly on the final transaction")
        case_id = alerted["case"]["id"]
        observe("after_ingest", case_id)
        opened = observe("case_opened", case_id)
        investigated = call("investigate", "POST", f"/v1/cases/{case_id}/investigations",
                            {"expected_revision": opened["case"]["revision"]})
        trace = call("trace", "GET", f"/v1/cases/{case_id}/investigation-trace")
        observe("after_investigation", case_id)
        intents = investigated["action_intents"]
        if investigated["case"]["state"] != "awaiting_approval" or len(intents) != 1:
            raise DemoError("workflow did not produce exactly one action intent")
        # Scripted: the capture script, not a person, sends the analyst's decision.
        approval = call("approval", "POST", "/v1/approvals",
                        {"action_intent_id": intents[0]["intent"]["id"],
                         "decision": "approved"}, 201)
        observe("after_approval", case_id)
        key = str(uuid.uuid4())
        execution = call("execute", "POST", "/v1/actions",
                         {"approval_id": approval["id"], "idempotency_key": key})
        observe("after_execution", case_id)
        replay = call("retry", "POST", "/v1/actions",
                      {"approval_id": approval["id"], "idempotency_key": key})
        observe("after_replay", case_id)
        final_trace = call("final_trace", "GET", f"/v1/cases/{case_id}/investigation-trace")
        observe("final", case_id)
        finished = clock()
    finally:
        logger.removeHandler(handler)
        client.close()
    raw = {
        "capture_started_at": started.isoformat(), "capture_finished_at": finished.isoformat(),
        "api_version": API_VERSION, "runtime_role_checks": checks,
        "scorer": {"mode": svc.scorer.mode, "scorer": svc.scorer.scorer.model_dump(mode="json"),
                   "threshold": svc.scorer.threshold, "rule_config": scoring.RULE_CONFIG},
        "workflow": {"config": workflow.config.model_dump(mode="json"),
                     "roles": {r: a.config.model_dump(mode="json")
                               for r, a in workflow.adapters.items()},
                     "tool_profile": workflow.tool_profile.model_dump(mode="json"),
                     "live": workflow.live},
        "actors": {str(ctx.actor_id): "scripted-analyst", str(SYSTEM_ACTOR): "system",
                   str(workflow.principal_id): "three-role-workflow"},
        "ingests": ingests, "investigated": investigated, "trace": trace,
        "approval": approval, "execution": execution, "replay": replay,
        "final_trace": final_trace, "observations": observations, "requests": requests,
    }
    secrets = [token, token_digest(token), owner_url, runtime_url, "postgresql://",
               str(ctx.scope.tenant_id), str(ctx.scope.session_id), str(ctx.actor_id)]
    return Capture(raw=raw, token=token, secrets=secrets, log_lines=lines)


# ---- allowlisted projection ----------------------------------------------------------------

def _pick(obj: dict | None, keys) -> dict | None:
    if obj is None:
        return None
    missing = [k for k in keys if k not in obj]
    if missing:
        raise DemoError(f"captured record lacks fields {missing}")
    return {k: obj[k] for k in keys}


def _artifact(ref: dict) -> dict:
    return _pick(ref, ("name", "version", "sha256"))


TXN_KEYS = ("id", "external_id", "account_id", "direction", "amount", "occurred_at",
            "ingested_at")
SCORING_KEYS = ("transaction_id", "scored_at", "features_as_of", "scoring_kind",
                "score_semantics", "score", "threshold", "alerted", "prior_count_1h")
ALERT_KEYS = ("id", "transaction_id", "created_at", "scoring_kind", "score_semantics", "score",
              "threshold")
CASE_KEYS = ("id", "alert_id", "revision", "state", "evidence_ids", "created_at", "updated_at")
EVIDENCE_KEYS = ("id", "case_id", "source", "source_ref", "observed_at", "available_at",
                 "facts", "content_sha256")
WORKFLOW_KEYS = ("id", "case_revision", "status", "terminal_by", "started_at", "deadline_at",
                 "finished_at", "input_snapshot_sha256", "disposition",
                 "recorded_role_invocations", "recorded_tool_calls", "deadline_status")
ATTEMPT_KEYS = ("agent_run_id", "role", "attempt", "status", "failure_code", "started_at",
                "finished_at", "output", "output_sha256", "claim_checks", "elapsed_ms",
                "usage", "basis", "finding")
STEP_KEYS = ("seq", "kind", "state", "role", "agent_run_id", "attempt", "tool",
             "tool_result_id", "at", "elapsed_ms", "failure_code", "output_sha256", "checks")
TOOL_KEYS = ("id", "tool", "window", "status", "denial", "values", "evidence_ids", "as_of",
             "content_sha256")
AUDIT_KEYS = ("id", "case_revision", "correlation_id", "actor_kind", "event_type", "outcome",
              "occurred_at", "recorded_at")


def _case(body: dict) -> dict:
    out = _pick(body, CASE_KEYS)
    out["pins"] = {k: (v if k == "evidence_snapshot_sha256" else _artifact(v))
                   for k, v in body["pins"].items() if k != "schema_version"}
    return out


def _actor(actors: dict, actor_id: str) -> str:
    if actor_id not in actors:
        raise DemoError("an actor in the capture has no public label")
    return actors[actor_id]


def _observation(obs: dict) -> dict:
    detail, overview = obs["detail"], obs["overview"]
    intents = detail["action_intents"]
    return {"observed_at": obs["observed_at"], "case_state": detail["case"]["state"],
            "case_revision": detail["case"]["revision"], "action_intents": len(intents),
            "approvals": sum(i["approval"] is not None for i in intents),
            "simulated_actions": overview["simulated_actions"],
            "audit_events": len(obs["audit"]), "transactions": overview["transactions"],
            "alerts": overview["alerts"], "cases_by_state": overview["cases_by_state"]}


def _requests_for(raw_requests: list[dict], prefixes: tuple[str, ...]) -> list[dict]:
    return [{"method": r["method"], "path": r["path"], "status": r["status"]}
            for r in raw_requests if r["label"].startswith(prefixes)]


def project(raw: dict, provenance: dict) -> dict:
    """The explicit public projection. Fields not named here are never exported."""
    actors = raw["actors"]
    alerted = raw["ingests"][-1]
    opened = raw["observations"]["case_opened"]["detail"]
    investigated = raw["investigated"]
    selected = raw["trace"]["selected"]
    intent_view = investigated["action_intents"][0]
    intent = intent_view["intent"]
    final_detail = raw["observations"]["final"]["detail"]
    final_view = final_detail["action_intents"][0]

    def action(response):
        body = response["action"]
        out = _pick(body, ("id", "approval_id", "intent_sha256", "idempotency_key", "mode",
                           "state", "created_at", "completed_at"))
        out["intent_id"] = body["intent"]["id"]
        return {"action": out, "replayed": response["replayed"]}

    approval = raw["approval"]
    final_trace = raw["final_trace"]
    records = {
        "ingests": [{"transaction": _pick(i["transaction"], TXN_KEYS),
                     "scoring": _pick(i["scoring"], SCORING_KEYS),
                     "alert_id": i["alert"]["id"] if i["alert"] else None,
                     "case_id": i["case"]["id"] if i["case"] else None,
                     "replayed": i["replayed"]} for i in raw["ingests"]],
        "alert": _pick(alerted["alert"], ALERT_KEYS),
        "case_opened": _case(opened["case"]),
        "evidence": [_pick(e, EVIDENCE_KEYS) for e in opened["evidence"]],
        "workflow": {**_pick(selected["workflow"], WORKFLOW_KEYS),
                     "config": _artifact(selected["workflow"]["config"]),
                     "tool_profile": _artifact(selected["workflow"]["tool_profile"])},
        "limits": selected["limits"],
        "attempts": [{**_pick(a, ATTEMPT_KEYS), "config": _artifact(a["config"])}
                     for a in selected["attempts"]],
        "steps": [_pick(s, STEP_KEYS) for s in selected["steps"]],
        "tool_results": [_pick(t, TOOL_KEYS) for t in selected["tool_results"]],
        "usage_summary": selected["usage_summary"],
        "trace_read": {"read_at": raw["trace"]["read_at"],
                       "case_state": raw["trace"]["case_state"],
                       "case_revision": raw["trace"]["case_revision"],
                       "workflow_count": raw["trace"]["workflow_count"],
                       "legacy_investigator_runs": raw["trace"]["legacy_investigator_runs"]},
        "final_trace_read": {"read_at": final_trace["read_at"],
                             "case_state": final_trace["case_state"],
                             "case_revision": final_trace["case_revision"],
                             "workflow_count": final_trace["workflow_count"],
                             "workflow_id": final_trace["selected"]["workflow"]["id"],
                             "steps": len(final_trace["selected"]["steps"])},
        "case_after_investigation": _case(investigated["case"]),
        "intent": {**_pick(intent, ("id", "case_id", "case_revision",
                                    "evidence_snapshot_sha256", "parameters")),
                   "policy": _artifact(intent["policy"]),
                   "intent_sha256": intent_view["intent_sha256"],
                   "agent_runs_in_case_detail": len(investigated["agent_runs"])},
        "approval": {**_pick(approval, ("id", "intent_sha256", "actor_kind", "decision",
                                        "decided_at", "expires_at", "consumed_at")),
                     "intent_id": approval["intent"]["id"],
                     "actor": _actor(actors, approval["actor_id"]),
                     "consumed_at_final": final_view["approval"]["consumed_at"]},
        "execution": action(raw["execution"]),
        "replay": action(raw["replay"]),
        "case_final": _case(final_detail["case"]),
        "audit": [{**_pick(e, AUDIT_KEYS), "actor": _actor(actors, e["actor_id"])}
                  for e in raw["observations"]["final"]["audit"]],
    }
    request_groups = {
        "ingest": ("ingest:", "after_ingest:"), "case_opened": ("case_opened:",),
        "analyst": ("investigate", "trace", "after_investigation:"),
        "investigator": ("trace",), "reviewer": ("trace",),
        "proposal": ("after_investigation:",), "approval": ("approval", "after_approval:"),
        "execution": ("execute", "after_execution:"),
        "replay": ("retry", "after_replay:"),
        "audit": ("final_trace", "final:"),
    }
    frames = []
    for index, stage in enumerate(STAGES, 1):
        reqs = _requests_for(raw["requests"], request_groups[stage])
        frames.append({"index": index, "id": stage, "stage": stage, "title": TITLES[stage],
                       "observation": OBSERVATION_OF[stage], "requests": reqs})
    fixture = {
        "schema": SCHEMA,
        "labels": list(LABELS),
        "notice": ("Recorded synthetic replay. Not live inference: no backend, model or "
                   "provider is contacted. The rule score is a heuristic, not a fraud "
                   "probability. Approval was scripted by the capture program; the action "
                   "is simulated."),
        "provenance": provenance,
        "scenario": {"id": SCENARIO["id"], "description": SCENARIO["description"],
                     "synthetic": True, "currency": SCENARIO["currency"]},
        "observations": {name: _observation(obs)
                         for name, obs in raw["observations"].items()},
        "records": records,
        "frames": frames,
    }
    bad = forbidden_keys(fixture)
    if bad:
        raise DemoError(f"projection contains forbidden keys {sorted(bad)}")
    return fixture


def forbidden_keys(value, found=None) -> set[str]:
    found = set() if found is None else found
    if isinstance(value, dict):
        for key, item in value.items():
            if key in FORBIDDEN_KEYS:
                found.add(key)
            forbidden_keys(item, found)
    elif isinstance(value, list):
        for item in value:
            forbidden_keys(item, found)
    return found


def provenance_for(raw: dict, git: dict, identity: dict | None = None) -> dict:
    return {
        "generator": "scripts/build_recorded_demo.py",
        "generator_commit": git["commit"], "generator_tree_clean": git["clean"],
        "content_identity": content_identity() if identity is None else identity,
        "tested_application_reference": TESTED_APPLICATION,
        "src_identical_to_tested_application": git["src_identical"],
        "capture_started_at": raw["capture_started_at"],
        "capture_finished_at": raw["capture_finished_at"],
        "api_version": raw["api_version"],
        "http_path": ("production FastAPI app (sentinel.api.create_app) driven in process by "
                      "the FastAPI TestClient; no network port"),
        "database": "disposable local PostgreSQL cluster owned by the capture, stopped after",
        "runtime_role": raw["runtime_role_checks"],
        "scorer": {"mode": raw["scorer"]["mode"], "artifact": _artifact(raw["scorer"]["scorer"]),
                   "threshold": raw["scorer"]["threshold"],
                   "rule_config": raw["scorer"]["rule_config"]},
        "workflow": {"kind": "three-role", "config": _artifact(raw["workflow"]["config"]),
                     "roles": {r: _artifact(c) for r, c in raw["workflow"]["roles"].items()},
                     "tool_profile": _artifact(raw["workflow"]["tool_profile"]),
                     "adapters": "deterministic (no provider; usage not applicable)",
                     "live": raw["workflow"]["live"]},
        "operator_actions": ["created and migrated a disposable database",
                             "granted the restricted runtime role",
                             "issued one analyst session (token kept in memory only)"],
        "scripted_steps": ["the capture program sent decision 'approved' via POST /v1/approvals",
                           "the capture program executed once and retried once with the same "
                           "idempotency key via POST /v1/actions"],
        "exercised": ["POST /v1/transactions (5 synthetic debits, rule scorer)",
                      "POST /v1/cases/{id}/investigations (deterministic three-role workflow)",
                      "GET /v1/cases/{id}/investigation-trace (twice)",
                      "POST /v1/approvals", "POST /v1/actions (execute and retry)",
                      "GET /v1/cases/{id}, /v1/cases/{id}/audit, /v1/overview per frame"],
        "limitations": [
            "One recorded synthetic case; nothing is re-run when the page is viewed.",
            "Rule baseline only: the score is a heuristic, not a fraud probability; the "
            "trained model path was not exercised.",
            "Deterministic role adapters: plumbing control, not evidence of model "
            "investigation quality; no LLM or provider was called; token usage is not "
            "applicable.",
            "The approval decision was scripted by the capture program, not a human review.",
            "The action is a simulated record; no external system was contacted.",
            "HTTP ran in process (TestClient); uvicorn, browser auth and the product web UI "
            "were not exercised by the capture.",
            "No account profile was provisioned, so the profile tool is recorded as "
            "unavailable.",
        ],
    }


# ---- validation (pure; no database) --------------------------------------------------------

def _t(value: str) -> datetime:
    when = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if when.tzinfo is None:
        raise DemoError("naive timestamp")
    return when


def validate(fx: dict) -> list[str]:
    """Problems with a fixture; empty means valid. Never raises on malformed shape."""
    try:
        return _validate(fx)
    except (KeyError, TypeError, ValueError, IndexError, AttributeError, DemoError) as error:
        return [f"malformed fixture ({type(error).__name__}: {error})"]


def _validate(fx: dict) -> list[str]:
    p: list[str] = []

    def need(ok, message):
        if not ok:
            p.append(message)

    need(fx["schema"] == SCHEMA, "schema")
    need(tuple(fx["labels"]) == LABELS, "labels")
    bad = forbidden_keys(fx)
    need(not bad, f"forbidden keys {sorted(bad)}")
    prov, rec, obs = fx["provenance"], fx["records"], fx["observations"]
    start, finish = _t(prov["capture_started_at"]), _t(prov["capture_finished_at"])
    need(start < finish, "capture interval")
    need(prov["scorer"]["mode"] == "rule", "scorer is not the rule baseline")
    need(prov["workflow"]["live"] is False, "workflow is not deterministic")
    need(prov["runtime_role"].get("session_issuance_refused") is True, "runtime role check")
    if "content_identity" not in prov:
        p.append(_NO_IDENTITY)
    else:
        p.extend(identity_shape_problems(prov["content_identity"]))
    frames = fx["frames"]
    need([f["stage"] for f in frames] == list(STAGES), "frame stages/order")
    need([f["index"] for f in frames] == list(range(1, len(STAGES) + 1)), "frame indexes")
    for f in frames:
        need(f["observation"] in obs, f"frame {f['id']} observation missing")

    # chronology of observations, in frame order, inside the capture interval
    times = [_t(obs[f["observation"]]["observed_at"]) for f in frames]
    need(all(a <= b for a, b in zip(times, times[1:])), "frames out of chronological order")
    need(all(start <= t <= finish for t in times), "observation outside capture interval")

    # transactions and rule scoring
    ingests = rec["ingests"]
    txns = {i["transaction"]["id"]: i["transaction"] for i in ingests}
    for i in ingests:
        t = i["transaction"]
        need(_t(t["occurred_at"]) < start, "event time does not precede the recording")
        need(_t(t["occurred_at"]) <= _t(t["ingested_at"]) <= finish, "ingest time")
        s = i["scoring"]
        need(s["transaction_id"] == t["id"], "scoring/transaction link")
        need(s["scoring_kind"] == "rule" and s["score_semantics"] == "heuristic",
             "scoring is not the rule heuristic baseline")
        need(s["alerted"] == (s["score"] >= s["threshold"]), "alert decision vs threshold")
        need((i["alert_id"] is not None) == s["alerted"], "alert presence")
    need([i["scoring"]["alerted"] for i in ingests] == [False] * (len(ingests) - 1) + [True],
         "exactly the final transaction alerts")
    alerted = ingests[-1]
    alert, case0 = rec["alert"], rec["case_opened"]
    need(alert["id"] == alerted["alert_id"] and alert["transaction_id"] in txns, "alert link")
    need(alert["score"] == alerted["scoring"]["score"], "alert score")
    need(case0["alert_id"] == alert["id"] and case0["id"] == alerted["case_id"], "case link")
    need(case0["state"] == "open" and case0["revision"] == 1, "case opened state")

    # evidence and pins
    evidence = {e["id"]: e for e in rec["evidence"]}
    need(len(evidence) == len(case0["evidence_ids"]) == 2
         and set(evidence) == set(case0["evidence_ids"]), "case evidence ids")
    need(all(e["case_id"] == case0["id"] for e in evidence.values()), "evidence case link")
    for e in evidence.values():
        ref = e["source_ref"]
        need(ref.endswith(alerted["transaction"]["id"]), "evidence source_ref target")
    snapshot = case0["pins"]["evidence_snapshot_sha256"]
    wf = rec["workflow"]
    need(wf["input_snapshot_sha256"] == snapshot, "workflow input snapshot pin")
    need(rec["intent"]["evidence_snapshot_sha256"] == snapshot, "intent evidence snapshot pin")
    for later in ("case_after_investigation", "case_final"):
        need(rec[later]["pins"] == case0["pins"], f"{later} pins changed")
        need(rec[later]["id"] == case0["id"], f"{later} case id")
    need(case0["pins"]["agent_config"] == wf["config"] == prov["workflow"]["config"],
         "agent config pin")
    need(case0["pins"]["tool_config"] == wf["tool_profile"], "tool profile pin")
    need(case0["pins"]["scorer"] == prov["scorer"]["artifact"], "scorer pin")

    # trace: steps, tool results, citations, disposition
    tools = {t["id"]: t for t in rec["tool_results"]}
    attempts = {a["agent_run_id"]: a for a in rec["attempts"]}
    need([a["role"] for a in rec["attempts"]] == ["evidence_analyst", "investigator",
                                                  "reviewer"], "role attempts")
    seqs = [s["seq"] for s in rec["steps"]]
    need(seqs == sorted(set(seqs)), "step sequence")
    step_times = [_t(s["at"]) for s in rec["steps"]]
    need(all(a <= b for a, b in zip(step_times, step_times[1:])), "step chronology")
    w_start, w_end = _t(wf["started_at"]), _t(wf["finished_at"])
    need(_t(case0["created_at"]) <= w_start <= w_end, "workflow after case")
    need(all(w_start <= t <= w_end for t in step_times), "steps inside workflow")
    for s in rec["steps"]:
        if s["tool_result_id"] is not None:
            need(s["tool_result_id"] in tools, "step cites a missing tool result")
        if s["agent_run_id"] is not None:
            need(s["agent_run_id"] in attempts, "step cites a missing attempt")
    for t in tools.values():
        need(all(e in evidence for e in t["evidence_ids"]), "tool result cites missing evidence")
    cites = 0
    for a in rec["attempts"]:
        need(a["status"] == "completed", "attempt not completed")
        need(w_start <= _t(a["started_at"]) <= _t(a["finished_at"]) <= w_end,
             "attempt outside workflow")
        need(a["usage"]["source"] in ("not_applicable", "unknown", "adapter_reported"),
             "usage source")
        for claim in (a["output"] or {}).get("claims", []):
            cite = claim["cite"]
            target = evidence if cite["kind"] == "evidence" else tools
            need(cite["kind"] in ("evidence", "tool_result") and cite["id"] in target,
                 "claim cites a missing record")
            cites += 1
    need(cites > 0, "no citations")
    disposition = wf["disposition"]
    need(wf["status"] == "completed" and disposition["kind"] == "recommend", "disposition")
    basis = attempts.get(disposition["basis_run_id"])
    need(basis is not None and basis["role"] == "investigator" and basis["basis"],
         "disposition basis")
    reviewer = rec["attempts"][-1]
    need(reviewer["output"]["verdict"] == "accept", "reviewer verdict")
    need(rec["final_trace_read"]["workflow_id"] == wf["id"]
         and rec["final_trace_read"]["steps"] == len(rec["steps"]), "trace changed after reads")
    need(rec["usage_summary"]["reported_attempts"] == 0
         and rec["usage_summary"]["input_tokens"] is None, "usage must stay not-applicable")

    # proposal -> approval -> one action -> idempotent replay
    intent, approval = rec["intent"], rec["approval"]
    exe, rep = rec["execution"], rec["replay"]
    case1 = rec["case_after_investigation"]
    need(case1["state"] == "awaiting_approval" and intent["case_revision"] == case1["revision"],
         "proposal case state/revision")
    need(intent["case_id"] == case0["id"], "intent case")
    need(intent["parameters"]["operation"] == disposition["operation"], "intent operation")
    need(intent["parameters"]["transaction_id"] == alert["transaction_id"], "intent target")
    need(intent["policy"] == case0["pins"]["policy"], "intent policy pin")
    need(approval["intent_id"] == intent["id"]
         and approval["intent_sha256"] == intent["intent_sha256"], "approval binding")
    need(approval["decision"] == "approved" and approval["actor"] == "scripted-analyst"
         and approval["actor_kind"] == "human", "scripted approval identity")
    need(approval["consumed_at"] is None and approval["consumed_at_final"] is not None,
         "approval consumption")
    decided = _t(approval["decided_at"])
    need(w_end <= decided < _t(approval["expires_at"]), "approval timing")
    act = exe["action"]
    need(exe["replayed"] is False and rep["replayed"] is True, "replay flags")
    need(rep["action"] == act, "replay returned a different action")
    need(act["approval_id"] == approval["id"] and act["intent_id"] == intent["id"]
         and act["intent_sha256"] == intent["intent_sha256"], "action binding")
    need(act["mode"] == "simulated" and act["state"] == "succeeded", "action mode/state")
    need(decided <= _t(act["created_at"]) <= _t(approval["expires_at"]),
         "action not inside the approval window")
    need(approval["consumed_at_final"] == act["created_at"], "approval consumed by the action")
    need(rec["case_final"]["state"] == "closed", "final case state")

    # per-frame observed counts
    before = STAGES[:STAGES.index("approval")]
    for f in frames:
        o = obs[f["observation"]]
        if f["stage"] in before:
            need(o["approvals"] == 0 and o["simulated_actions"] == 0,
                 f"frame {f['id']}: approval/action before the approval frame")
        elif f["stage"] == "approval":
            need(o["approvals"] == 1 and o["simulated_actions"] == 0,
                 "approval frame counts")
            need(_t(o["observed_at"]) >= decided, "approval frame observed before decision")
        else:
            need(o["approvals"] == 1 and o["simulated_actions"] == 1,
                 f"frame {f['id']}: exactly one simulated action")
            need(_t(o["observed_at"]) >= _t(act["created_at"]), "action frame before action")
        if f["stage"] in ("ingest", "case_opened"):
            need(o["action_intents"] == 0 and o["case_state"] == "open", "pre-workflow state")
    for name in ("after_execution", "after_replay", "final"):
        need(obs[name]["case_state"] == "closed", f"{name} case state")

    # audit trail
    audit = rec["audit"]
    need(tuple(e["event_type"] for e in audit) == AUDIT_SEQUENCE, "audit event sequence")
    need(all(e["outcome"] == "success" for e in audit), "audit outcomes")
    need(all(e["actor"] in ACTOR_LABELS for e in audit), "audit actor labels")
    occ = [_t(e["occurred_at"]) for e in audit]
    need(all(a <= b for a, b in zip(occ, occ[1:])), "audit chronology")
    by_type = {e["event_type"]: e for e in audit}
    need(by_type["approval_recorded"]["actor"] == "scripted-analyst", "approval audit actor")
    need(_t(by_type["approval_recorded"]["occurred_at"]) == decided, "approval audit time")
    need(_t(by_type["action_succeeded"]["occurred_at"]) == _t(act["created_at"]),
         "action audit time")
    for name, o in obs.items():
        seen = sum(t <= _t(o["observed_at"]) for t in occ)
        need(seen == o["audit_events"], f"{name}: audit count does not match its time")
    return p


# ---- files, hashing and secret scan --------------------------------------------------------

def serialize(fixture: dict) -> bytes:
    return (json.dumps(fixture, indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def manifest_for(data: bytes, provenance: dict) -> dict:
    return {"schema": SCHEMA, "data_file": "recorded-case.json", "sha256": sha256(data),
            "bytes": len(data), "generator": provenance["generator"],
            "generator_commit": provenance["generator_commit"]}


def _current_user() -> str | None:
    try:
        return getpass.getuser() or None
    except (OSError, KeyError):
        return None


def path_variants(*, root: str | Path | None = None, home: str | Path | None = None,
                  user: str | None = None) -> list[str]:
    """Local filesystem/user strings that must not appear in public files.

    The checkout and home paths are matched in every separator form (native, forward slash,
    JSON-escaped backslash). The account name is matched only where it identifies a local
    account in a path (`/home/<u>`, `Users/<u>`, `Users\\<u>` and its JSON-escaped form,
    `/root` for root): a bare name would also match ordinary words, for example an account
    named "sentinel" against the product name (native Ubuntu preview gate, 82316a5)."""
    values = set()
    for base in (ROOT if root is None else root, Path.home() if home is None else home):
        text = str(base)
        values |= {text, text.replace("\\", "/"), text.replace("\\", "\\\\"),
                   text.replace("/", "\\"), text.replace("/", "\\\\")}
    name = _current_user() if user is None else user
    if name:
        values |= {f"/home/{name}", f"Users/{name}", f"Users\\{name}", f"Users\\\\{name}"}
        if name == "root":
            values.add("/root/")
    return sorted(v for v in values if len(v) >= 4)


def scan(files: list[Path], forbidden: list[str]) -> list[str]:
    """Names of files containing any forbidden string (case-insensitive for paths)."""
    if not forbidden or any(not f for f in forbidden):
        raise DemoError("scan needs every forbidden value; an empty source is not a scan")
    hits = []
    needles = [(f, f.lower()) for f in forbidden]
    for path in files:
        text = path.read_bytes().decode("utf-8", errors="replace")
        low = text.lower()
        for raw_value, lowered in needles:
            if raw_value in text or lowered in low:
                hits.append(path.name)
                break
    return hits


def public_files() -> list[Path]:
    files = [p for p in DEMO_DIR.rglob("*") if p.is_file()]
    doc = ROOT / "docs" / "demo" / "DEMO01.md"
    return files + ([doc] if doc.exists() else [])


# ---- content identity: history-independent capture freshness (R48) -------------------------

_NO_IDENTITY = ("provenance has no content_identity: the fixture cannot show which generator "
                "and application bytes it was captured from; re-run the capture")
_HEX64 = frozenset("0123456789abcdef")


def canonical_digest(path: Path) -> str:
    """Digest of a file's bytes with CRLF canonicalized to LF, so that Windows (autocrlf)
    and Ubuntu checkouts of the same commit agree. Lone CR and all other bytes are kept."""
    return sha256(path.read_bytes().replace(b"\r\n", b"\n"))


def _aggregate(files: dict) -> str:
    return sha256("".join(f"{files[name]}  {name}\n" for name in sorted(files)).encode())


def content_files(root: Path | None = None) -> list[str]:
    """Relative POSIX names of the freshness inputs present in a checkout (no Git): the
    generator file and every file under src/ except interpreter/build output."""
    base = ROOT if root is None else Path(root)
    found = []
    for entry in CONTENT_SCOPE:
        path = base / entry
        if path.is_file():
            found.append(entry)
            continue
        if not path.is_dir():
            continue
        for item in path.rglob("*"):
            rel = item.relative_to(base)
            if (not item.is_file() or item.name.endswith(_IGNORED_FILE_SUFFIXES) or any(
                    part in _IGNORED_DIRS or part.endswith(_IGNORED_DIR_SUFFIXES)
                    for part in rel.parts[:-1])):
                continue
            found.append(rel.as_posix())
    return sorted(found)


def content_identity(root: Path | None = None) -> dict:
    base = ROOT if root is None else Path(root)
    files = {name: canonical_digest(base / name) for name in content_files(base)}
    return {"inputs": list(CONTENT_SCOPE), "canonicalization": CANONICALIZATION,
            "files": files, "sha256": _aggregate(files)}


def _safe_name(name) -> bool:
    if not isinstance(name, str) or not name or "\\" in name or name.startswith("/"):
        return False
    parts = name.split("/")
    if any(part in ("", ".", "..") for part in parts) or ":" in parts[0]:
        return False
    return any(name == entry or name.startswith(entry + "/") for entry in CONTENT_SCOPE)


def identity_shape_problems(identity) -> list[str]:
    """Problems with a recorded content_identity's shape; never raises."""
    if not isinstance(identity, dict):
        return ["content_identity is malformed (not an object); re-run the capture"]
    p = []
    if identity.get("inputs") != list(CONTENT_SCOPE):
        p.append(f"content_identity inputs {identity.get('inputs')!r} is not "
                 f"{list(CONTENT_SCOPE)!r}; re-run the capture")
    if identity.get("canonicalization") != CANONICALIZATION:
        p.append("content_identity canonicalization is not the current rule; re-run the "
                 "capture")
    files = identity.get("files")
    if not isinstance(files, dict) or not files:
        return p + ["content_identity files is missing, empty or not an object; re-run the "
                    "capture"]
    bad = sorted(str(n) for n, d in files.items() if not _safe_name(n) or not (
        isinstance(d, str) and len(d) == 64 and set(d) <= _HEX64))
    if bad:
        p.append(f"content_identity has invalid entries {bad}; re-run the capture")
    if CONTENT_SCOPE[0] not in files:
        p.append(f"content_identity does not record the generator {CONTENT_SCOPE[0]}")
    aggregate = identity.get("sha256")
    if not isinstance(aggregate, str):
        p.append("content_identity has no aggregate sha256; re-run the capture")
    elif not bad and aggregate != _aggregate(files):
        p.append("content_identity aggregate sha256 does not match its file digests "
                 "(edited or corrupted provenance); re-run the capture")
    return p


def freshness_problems(fixture, root: Path | None = None) -> list[str]:
    """Whether the checkout's generator/application bytes equal those recorded at capture.

    Reads files only; no Git call, so a shallow, exported or history-less checkout is
    checked exactly like a full clone. Empty means fresh; never raises."""
    prov = fixture.get("provenance") if isinstance(fixture, dict) else None
    if not isinstance(prov, dict) or "content_identity" not in prov:
        return [_NO_IDENTITY]
    identity = prov["content_identity"]
    shape = identity_shape_problems(identity)
    if shape:
        return shape
    base = ROOT if root is None else Path(root)
    try:
        current = content_identity(base)["files"]
    except OSError as error:
        return [f"content_identity inputs could not be read ({error}); re-run the capture"]
    recorded = identity["files"]
    commit = prov.get("generator_commit", "an unrecorded commit")
    where = f"since the capture (recorded generator_commit {commit}); re-run the capture"
    p = [f"{name} changed {where}" for name in sorted(set(recorded) & set(current))
         if recorded[name] != current[name]]
    p += [f"{name} missing from this checkout {where}" for name in
          sorted(set(recorded) - set(current))]
    p += [f"{name} added {where}" for name in sorted(set(current) - set(recorded))]
    return p


# ---- git provenance ------------------------------------------------------------------------

def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True,
                          stdin=subprocess.DEVNULL, timeout=60)


def git_state() -> dict:
    head = _git("rev-parse", "HEAD")
    if head.returncode != 0:
        raise DemoError("not a git checkout; the capture must name its source commit")
    dirty = _git("status", "--porcelain", "--", *GENERATOR_PATHS).stdout.strip()
    same = _git("diff", "--quiet", TESTED_APPLICATION, "HEAD", "--", "src").returncode == 0
    return {"commit": head.stdout.strip(), "clean": not dirty, "src_identical": same and not
            _git("status", "--porcelain", "--", "src").stdout.strip()}


# ---- commands ------------------------------------------------------------------------------

def cmd_capture(args) -> int:
    import psycopg

    import local_stack
    from sentinel import db, devdb
    git = git_state()
    if not git["clean"] and not args.allow_dirty:
        raise DemoError("generator paths have uncommitted changes; commit first "
                        "(--allow-dirty records the capture as unclean)")
    PRIVATE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stack = local_stack.Stack(PRIVATE_DIR / f"stack-{stamp}")
    data = stack.load(create=True)
    capture = None
    try:
        local_stack.start_database(stack, data, devdb.free_port())
        with psycopg.connect(local_stack.owner_url(stack, data), autocommit=True) as conn:
            conn.execute(f'CREATE DATABASE "{DATABASE}"')
        url = local_stack.owner_url(stack, data, DATABASE)
        db.migrate(url)
        capture = capture_case(url, RUNTIME_ROLE)
    finally:
        local_stack.stop_database(stack, data)  # verified stop of our own cluster only
    print(f"database stopped: {local_stack.database_state(stack, data)}")
    if not args.keep_cluster:
        try:
            shutil.rmtree(stack.dir)
            print("disposable cluster directory removed")
        except OSError:
            print("disposable cluster stopped; its directory could not be removed (kept)")
    raw_path = PRIVATE_DIR / f"raw-capture-{stamp}.json"
    raw_path.write_text(json.dumps(capture.raw, indent=1, sort_keys=True) + "\n",
                        encoding="utf-8", newline="\n")
    log_path = PRIVATE_DIR / f"capture-{stamp}.log"
    log_path.write_text("\n".join(capture.log_lines) + "\n", encoding="utf-8", newline="\n")
    private_hits = scan([raw_path, log_path], capture.secrets[:4])
    if private_hits:
        raise DemoError(f"credential material in private capture files {private_hits}")
    provenance = provenance_for(capture.raw, git)
    fixture = project(capture.raw, provenance)
    problems = validate(fixture)
    if problems:
        raise DemoError("captured fixture failed validation: " + "; ".join(problems))
    payload = serialize(fixture)
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_bytes(payload)
    MANIFEST_FILE.write_bytes(serialize(manifest_for(payload, provenance)))
    forbidden = capture.secrets + path_variants()
    hits = scan(public_files(), forbidden)
    report = {"stamp": stamp, "data_sha256": sha256(payload), "bytes": len(payload),
              "public_files_scanned": len(public_files()), "forbidden_values": len(forbidden),
              "token_length": len(capture.token), "public_hits": hits,
              "private_files_scanned": 2, "private_hits": private_hits,
              "generator_commit": git["commit"], "generator_tree_clean": git["clean"]}
    (PRIVATE_DIR / f"capture-report-{stamp}.json").write_text(
        json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n")
    if hits:
        DATA_FILE.unlink()
        MANIFEST_FILE.unlink()
        raise DemoError(f"forbidden material found in public files {hits}; outputs removed")
    print(f"captured {len(fixture['frames'])} frames; validation passed")
    print(f"scan: {len(public_files())} public files x {len(forbidden)} forbidden values "
          f"(real token of length {len(capture.token)} included): clean")
    print(f"data sha256 {sha256(payload)} ({len(payload)} bytes)")
    print(f"private raw capture and report under .agent/demo01/ (stamp {stamp})")
    return 0


def load_fixture(path: Path) -> tuple[dict, bytes]:
    payload = path.read_bytes()
    return json.loads(payload.decode("utf-8")), payload


def cmd_validate(args) -> int:
    data_path = Path(args.data) if args.data else DATA_FILE
    fixture, payload = load_fixture(data_path)
    problems = validate(fixture)
    if not args.data:
        manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
        if manifest["sha256"] != sha256(payload) or manifest["bytes"] != len(payload):
            problems.append("manifest hash/size does not match the data file")
        if not fixture["provenance"]["generator_tree_clean"]:
            problems.append("tracked fixture was captured from an unclean tree")
        problems.extend(x for x in freshness_problems(fixture) if x not in problems)
    hits = scan([data_path], path_variants())
    if hits:
        problems.append("local path or user path in the data file")
    for problem in problems:
        print(f"FAIL {problem}")
    if problems:
        return 1
    print(f"ok: {len(fixture['frames'])} frames valid; sha256 {sha256(payload)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    cap = sub.add_parser("capture", help="real capture on an owned disposable cluster")
    cap.add_argument("--keep-cluster", action="store_true",
                     help="keep the stopped cluster directory under .agent/demo01/")
    cap.add_argument("--allow-dirty", action="store_true")
    val = sub.add_parser("validate", help="validate the tracked (or given) fixture")
    val.add_argument("--data")
    args = parser.parse_args(argv)
    try:
        return {"capture": cmd_capture, "validate": cmd_validate}[args.command](args)
    except DemoError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
