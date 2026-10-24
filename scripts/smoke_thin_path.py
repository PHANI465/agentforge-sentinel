"""Drive the thin path against a running server, in two stages so the server can be restarted
between them. Prints only ids, states and codes; reads the token from SENTINEL_TOKEN.

    python scripts/smoke_thin_path.py investigate      # ingest + investigate; prints case id
    python scripts/smoke_thin_path.py execute CASE_ID  # approve + execute + retry + audit
    python scripts/smoke_thin_path.py model --account ID  # model mode: needs a provisioned
                                                       # profile for ID; investigates
"""
from __future__ import annotations

import argparse
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import httpx


def client(base_url: str) -> httpx.Client:
    token = os.environ.get("SENTINEL_TOKEN")
    if not token:
        sys.exit("Set SENTINEL_TOKEN (from: python -m sentinel.cli create-session).")
    return httpx.Client(base_url=base_url, timeout=150,
                        headers={"Authorization": f"Bearer {token}"})


def expect(response: httpx.Response, status: int) -> dict:
    if response.status_code != status:
        sys.exit(f"{response.request.method} {response.request.url.path}: "
                 f"{response.status_code} {response.text[:200]}")
    return response.json()


def investigate(http: httpx.Client) -> None:
    account, now = str(uuid.uuid4()), datetime.now(timezone.utc)
    run = uuid.uuid4().hex[:8]
    for i, (minor, minutes_ago) in enumerate([(1500, 30), (1600, 20), (1700, 10), (250_000, 0)]):
        body = expect(http.post("/v1/transactions", json={
            "external_id": f"smoke-{run}-{i}", "account_id": account, "direction": "debit",
            "amount": {"currency": "USD", "minor_units": minor, "currency_exponent": 2},
            "occurred_at": (now - timedelta(minutes=minutes_ago)).isoformat()}), 201)
    case = body["case"]
    print(f"alert score={body['rule_score']} case={case['id']} state={case['state']}")
    view = expect(http.post(f"/v1/cases/{case['id']}/investigations",
                            json={"expected_revision": case["revision"]}), 200)
    run_body = view["agent_runs"][-1]
    print(f"investigator={run_body['run']['config']['name']} status={run_body['run']['status']}"
          f" failure={run_body['run']['failure_code']}")
    if run_body["finding"]:
        finding = run_body["finding"]
        print(f"finding operation={finding['operation']} reason={finding['reason_code']}")
    print(f"case state={view['case']['state']} revision={view['case']['revision']}")
    print(f"CASE_ID={case['id']}")


def model(http: httpx.Client, account: str) -> None:
    info = expect(http.get("/v1/scoring"), 200)
    print(f"scorer mode={info['mode']} semantics={info['score_semantics']}"
          f" threshold={info['threshold']} results={info['results_id']}")
    now, run = datetime.now(timezone.utc), uuid.uuid4().hex[:8]
    body = {"external_id": f"smoke-model-{run}-0", "account_id": str(uuid.uuid4()),
            "direction": "debit", "amount": {"currency": "USD", "minor_units": 1500,
                                             "currency_exponent": 2},
            "occurred_at": now.isoformat()}
    missing = http.post("/v1/transactions", json=body)
    print(f"unprovisioned status={missing.status_code} error={missing.json().get('error')}")
    for i, (currency, minor, minutes_ago) in enumerate([("USD", 1500, 30), ("GBP", 250_000, 0)]):
        body = {"external_id": f"smoke-model-{run}-{i + 1}", "account_id": account,
                "direction": "debit", "amount": {"currency": currency, "minor_units": minor,
                                                 "currency_exponent": 2},
                "occurred_at": (now - timedelta(minutes=minutes_ago)).isoformat()}
        result = expect(http.post("/v1/transactions", json=body), 201)
        scoring = result["scoring"]
        print(f"txn {i + 1} kind={scoring['scoring_kind']} score={scoring['score']}"
              f" alerted={scoring['alerted']} history_rows={scoring['inputs']['history_rows']}"
              f" artifact={scoring['model']['artifact_sha256'][:12]}")
    replay = expect(http.post("/v1/transactions", json=body), 201)
    print(f"replay replayed={replay['replayed']} same={replay['scoring'] == scoring}")
    case = result["case"]
    if case:
        print(f"case pins scorer={case['pins']['scorer']['name']} state={case['state']}")
        view = expect(http.post(f"/v1/cases/{case['id']}/investigations",
                                json={"expected_revision": case["revision"]}), 200)
        print(f"investigation status={view['agent_runs'][-1]['run']['status']}"
              f" case state={view['case']['state']} revision={view['case']['revision']}")
        print(f"CASE_ID={case['id']}")


def execute(http: httpx.Client, case_id: str) -> None:
    view = expect(http.get(f"/v1/cases/{case_id}"), 200)
    intent = view["action_intents"][-1]["intent"]
    approval = expect(http.post("/v1/approvals", json={"action_intent_id": intent["id"],
                                                       "decision": "approved"}), 201)
    key = str(uuid.uuid4())
    first = expect(http.post("/v1/actions", json={"approval_id": approval["id"],
                                                  "idempotency_key": key}), 200)
    retry = expect(http.post("/v1/actions", json={"approval_id": approval["id"],
                                                  "idempotency_key": key}), 200)
    print(f"action={first['action']['id']} state={first['action']['state']}"
          f" mode={first['action']['mode']} retry_replayed={retry['replayed']}"
          f" same_action={retry['action']['id'] == first['action']['id']}")
    audit = expect(http.get(f"/v1/cases/{case_id}/audit"), 200)
    print("audit=" + ",".join(f"{e['event_type']}:{e['outcome']}" for e in audit))
    final = expect(http.get(f"/v1/cases/{case_id}"), 200)["case"]
    print(f"case state={final['state']} revision={final['revision']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("stage", choices=("investigate", "execute", "model"))
    parser.add_argument("--account", help="model stage: a provisioned account id")
    parser.add_argument("case_id", nargs="?")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    with client(args.base_url) as http:
        if args.stage == "investigate":
            investigate(http)
        elif args.stage == "model":
            if not args.account:
                parser.error("model needs --account")
            model(http, args.account)
        elif args.case_id:
            execute(http, args.case_id)
        else:
            parser.error("execute needs CASE_ID")


if __name__ == "__main__":
    main()
