"""HTTP boundary. Bodies are validated here with code-only errors; identity comes only from
the bearer token lookup, never from a request or model payload.
"""
from __future__ import annotations

import os
import uuid

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, ValidationError

from sentinel import investigators
from sentinel.contracts.v1 import (
    ApprovalDecisionInput, ExecuteActionInput, InvestigationRequestInput, TransactionInput,
    TrustedContext, safe_validation_errors,
)
from sentinel.service import Sentinel, ServiceError

MAX_BODY_BYTES = 16_384


def create_app(service: Sentinel | None = None) -> FastAPI:
    if service is None:
        service = Sentinel(os.environ["SENTINEL_DATABASE_URL"], investigators.from_environment())
    app = FastAPI(title="AgentForge Sentinel", version="0.1.0", docs_url=None, redoc_url=None)
    app.state.service = service

    @app.exception_handler(ServiceError)
    async def service_error(_request, error: ServiceError):
        return JSONResponse({"error": error.code}, status_code=error.status)

    @app.exception_handler(RequestValidationError)
    async def request_error(_request, _error):
        return JSONResponse({"error": "invalid_request"}, status_code=422)

    def context(request: Request) -> TrustedContext:
        scheme, _, token = request.headers.get("authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise ServiceError("unauthenticated", 401)
        return service.authenticate(token)

    async def body(request: Request, model: type[BaseModel]):
        raw = await request.body()
        if len(raw) > MAX_BODY_BYTES:
            raise ServiceError("body_too_large", 413)
        try:
            return model.model_validate_json(raw)
        except ValidationError as error:
            raise _InvalidBody(safe_validation_errors(error)) from None

    @app.exception_handler(_InvalidBody)
    async def invalid_body(_request, error: _InvalidBody):
        return JSONResponse({"error": "invalid_request", "details": error.details},
                            status_code=422)

    @app.get("/healthz")
    def health():
        return {"status": "ok", "investigator": service.investigator.config.name}

    @app.post("/v1/transactions", status_code=201)
    async def ingest(request: Request, ctx: TrustedContext = Depends(context)):
        return await run_in_threadpool(service.ingest, ctx,
                                      await body(request, TransactionInput))

    @app.get("/v1/cases/{case_id}")
    def get_case(case_id: uuid.UUID, ctx: TrustedContext = Depends(context)):
        return service.get_case(ctx, case_id)

    @app.get("/v1/cases/{case_id}/audit")
    def get_audit(case_id: uuid.UUID, ctx: TrustedContext = Depends(context)):
        return service.get_audit(ctx, case_id)

    @app.post("/v1/cases/{case_id}/investigations")
    async def investigate(case_id: uuid.UUID, request: Request,
                          ctx: TrustedContext = Depends(context)):
        data = await body(request, InvestigationRequestInput)
        # The investigator may block (subprocess); keep it off the event loop.
        return await run_in_threadpool(service.investigate, ctx, case_id, data.expected_revision)

    @app.post("/v1/approvals", status_code=201)
    async def approve(request: Request, ctx: TrustedContext = Depends(context)):
        return await run_in_threadpool(service.record_approval, ctx,
                                      await body(request, ApprovalDecisionInput))

    @app.post("/v1/actions")
    async def execute(request: Request, ctx: TrustedContext = Depends(context)):
        return await run_in_threadpool(service.execute_action, ctx,
                                      await body(request, ExecuteActionInput))

    return app


class _InvalidBody(Exception):
    def __init__(self, details: list[dict[str, str]]):
        super().__init__("invalid_request")
        self.details = details
