"""Vercel-only demo entrypoint. The main application still owns case and action rules."""
import json
import os
import secrets
from datetime import timedelta
from uuid import uuid4

from fastapi import Request
from starlette.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, RedirectResponse

from iaf import MAX_QUESTION, answer as answer_iaf
from guard import HostedGuard

from sentinel import db
from sentinel.agents.coordinator import deterministic_workflow
from sentinel.api import create_app
from sentinel.contracts.v1 import Money, Scope, TransactionInput, TrustedContext
from sentinel.documents import DocumentService
from sentinel.service import Sentinel, token_digest, utc_now

CAPABILITIES = frozenset({"read_case", "approve_action", "execute_simulated_action"})


def hosted_app(database_url: str):
    service = Sentinel(database_url, deterministic_workflow())
    api = create_app(service=service, documents=DocumentService(None))
    api.add_middleware(HostedGuard, database_url=database_url)

    @api.get("/", include_in_schema=False)
    def home():
        return RedirectResponse("/index.html")

    @api.get("/workbench", include_in_schema=False)
    def workbench():
        return RedirectResponse("/workbench/index.html")

    @api.post("/demo/session", include_in_schema=False)
    def start_demo():
        token = secrets.token_urlsafe(32)
        scope = Scope(tenant_id=uuid4(), session_id=uuid4())
        actor = uuid4()
        with db.connect(database_url) as conn:
            allowed = conn.execute(
                "SELECT sentinel_demo.issue_session(%s, %s, %s, %s) AS allowed",
                (token_digest(token), scope.tenant_id, scope.session_id, actor),
            ).fetchone()["allowed"]
        if not allowed:
            return JSONResponse({"error": "demo_capacity_reached"}, status_code=429)

        # The grant used to insert the canned rows is internal. The stored guest grant
        # cannot upload transactions or documents through the application.
        seed = TrustedContext(scope=scope, actor_id=actor, actor_kind="human",
                              capabilities=CAPABILITIES | {"ingest_transaction"})
        account = uuid4()
        anchor = utc_now() - timedelta(minutes=1)
        for index, amount in enumerate((8_800, 12_000, 2_750, 3_200, 245_000)):
            service.ingest(seed, TransactionInput(
                external_id=f"demo-{index + 1}",
                account_id=account,
                amount=Money(currency="USD", minor_units=amount, currency_exponent=2),
                direction="debit",
                occurred_at=anchor - timedelta(minutes=(240, 120, 40, 20, 0)[index]),
            ))
        return JSONResponse({"token": token}, headers={"Cache-Control": "no-store"})

    @api.post("/iaf/ask", include_in_schema=False)
    async def iaf_ask(request: Request):
        headers = {"Cache-Control": "no-store"}
        raw = bytearray()
        async for chunk in request.stream():
            if len(raw) + len(chunk) > 4000:
                return JSONResponse({"kind": "bad_request"}, status_code=413, headers=headers)
            raw.extend(chunk)
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeError):
            data = None
        question = data.get("question") if isinstance(data, dict) else None
        if not isinstance(question, str) or not 1 <= len(question.strip()) <= MAX_QUESTION:
            return JSONResponse({"kind": "bad_request"}, status_code=422, headers=headers)
        return JSONResponse(await run_in_threadpool(answer_iaf, question, database_url), headers=headers)

    return api


# Vercel requires an ASGI export. A missing secret leaves the runtime unconfigured.
app = hosted_app(os.environ["SENTINEL_HOSTED_DATABASE_URL"])
