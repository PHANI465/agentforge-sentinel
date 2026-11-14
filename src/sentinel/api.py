"""HTTP boundary. Bodies are validated here with code-only errors; identity comes only from
the bearer token lookup, never from a request or model payload. Response shapes are the
typed HTTP v1 contract (sentinel.contracts.http_v1, docs/api/README.md) and its additive
revisions (http_v12: docs/api/investigation-trace-v1.2.md; http_v13: docs/api/documents-v1.3.md).
"""
from __future__ import annotations

import logging
import os
import re
import time
import uuid

from fastapi import Depends, FastAPI, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
from pydantic.json_schema import models_json_schema
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.routing import Match

from sentinel import investigators, model_results, scorers, trace
from sentinel.contracts import http_v13
from sentinel.contracts.http_v1 import (
    DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, CaseDetail, CasePage, CaseState, ErrorResponse,
    ExecuteResponse, Health, IngestResponse, ModelResults, Overview, ScorerInfo, SessionView,
)
from sentinel.contracts.http_v12 import InvestigationTrace
from sentinel.documents import DocumentService
from sentinel.contracts.v1 import (
    Approval, ApprovalDecisionInput, AuditEvent, ExecuteActionInput, InvestigationRequestInput,
    TransactionInput, TrustedContext, safe_validation_errors,
)
from sentinel.observability import (
    Metrics, configure_logging, emit, method_label, request_id,
)
from sentinel.service import MAX_CURSOR_LENGTH, Sentinel, ServiceError

HTTP_LOG = logging.getLogger("sentinel.http")

MAX_BODY_BYTES = 16_384
# v1.3 (DOC01 Part B): additive local document upload/analysis; v1, v1.1 and v1.2 snapshots
# are frozen in contracts/http (decision 0010).
API_VERSION = "1.3.0"
_ERRORS = {status: {"model": ErrorResponse} for status in (401, 403, 404, 409, 413, 422)}
_DOC_ERRORS = {status: {"model": ErrorResponse}
               for status in (401, 403, 404, 413, 415, 422, 502, 503, 504)}
# operation_id -> request model; bodies are read manually (size limit, code-only errors).
REQUEST_BODIES: dict[str, type[BaseModel]] = {
    "ingest_transaction": TransactionInput, "investigate_case": InvestigationRequestInput,
    "record_approval": ApprovalDecisionInput, "execute_action": ExecuteActionInput,
    "analyze_document": http_v13.AnalysisRequest,
}
# Raw-byte upload: the format's own media type or a generic octet stream; never multipart.
DOCUMENT_MEDIA_TYPES = {
    "csv": {"text/csv"}, "pdf": {"application/pdf"},
    "xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}}
GENERIC_MEDIA_TYPE = "application/octet-stream"


def create_app(service: Sentinel | None = None,
               documents: DocumentService | None = None) -> FastAPI:
    if service is None:
        service = Sentinel(os.environ["SENTINEL_DATABASE_URL"], investigators.from_environment(),
                           scorer=scorers.from_environment())
    if documents is None:
        # Opt-in: without a registered worker and store every document route answers 503.
        documents = DocumentService.from_environment()
    app = FastAPI(title="AgentForge Sentinel", version=API_VERSION, docs_url=None,
                  redoc_url=None)
    app.state.service = service
    app.state.documents = documents
    app.state.metrics = Metrics()
    service.metrics = app.state.metrics
    documents.metrics = app.state.metrics
    configure_logging()
    app.add_middleware(RequestContext, metrics=app.state.metrics, router=app.router)

    @app.exception_handler(ServiceError)
    async def service_error(_request, error: ServiceError):
        return JSONResponse({"error": error.code}, status_code=error.status)

    @app.exception_handler(RequestValidationError)
    async def request_error(_request, _error):
        return JSONResponse({"error": "invalid_request"}, status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_request, error: StarletteHTTPException):
        code = {404: "not_found", 405: "method_not_allowed"}.get(error.status_code, "http_error")
        return JSONResponse({"error": code}, status_code=error.status_code)

    @app.exception_handler(_InvalidBody)
    async def invalid_body(_request, error: _InvalidBody):
        return JSONResponse({"error": "invalid_request", "details": error.details},
                            status_code=422)

    def bearer(request: Request) -> str:
        scheme, _, token = request.headers.get("authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise ServiceError("unauthenticated", 401)
        return token

    def context(token: str = Depends(bearer)) -> TrustedContext:
        return service.authenticate(token)

    async def body(request: Request, model: type[BaseModel]):
        raw = await read_limited(request, MAX_BODY_BYTES)
        try:
            return model.model_validate_json(raw)
        except ValidationError as error:
            raise _InvalidBody(safe_validation_errors(error)) from None

    @app.get("/healthz", response_model=Health, operation_id="health")
    def health():
        return {"status": "ok", "investigator": service.investigator.config.name}

    @app.get("/v1/session", response_model=SessionView, responses=_ERRORS,
             operation_id="get_session")
    def get_session(token: str = Depends(bearer)):
        return service.session_view(token)

    @app.get("/v1/scoring", response_model=ScorerInfo, responses=_ERRORS,
             operation_id="get_scorer")
    def get_scorer(ctx: TrustedContext = Depends(context)):
        """v1.1: the configured scorer's identity, provenance and score semantics."""
        if "read_case" not in ctx.capabilities:
            raise ServiceError("permission_denied", 403)
        return service.scorer.info()

    @app.get("/v1/model-results/{results_id}", response_model=ModelResults, responses=_ERRORS,
             operation_id="get_model_results")
    def get_model_results(results_id: str = Path(max_length=32),
                          ctx: TrustedContext = Depends(context)):
        """v1.1: frozen offline C04 results (synthetic). Registry ids only, never a path."""
        if "read_case" not in ctx.capabilities:
            raise ServiceError("permission_denied", 403)
        results = model_results.load(results_id)
        if results is None:
            raise ServiceError("not_found", 404)
        return results

    @app.get("/v1/overview", response_model=Overview, responses=_ERRORS,
             operation_id="get_overview")
    def get_overview(ctx: TrustedContext = Depends(context)):
        return service.overview(ctx)

    @app.post("/v1/transactions", status_code=201, response_model=IngestResponse,
              responses=_ERRORS, operation_id="ingest_transaction")
    async def ingest(request: Request, ctx: TrustedContext = Depends(context)):
        return await run_in_threadpool(service.ingest, ctx,
                                       await body(request, TransactionInput))

    @app.get("/v1/cases", response_model=CasePage, responses=_ERRORS, operation_id="list_cases")
    def list_cases(ctx: TrustedContext = Depends(context),
                   limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
                   state: CaseState | None = Query(None),
                   cursor: str | None = Query(None, min_length=1,
                                              max_length=MAX_CURSOR_LENGTH)):
        return service.list_cases(ctx, limit=limit, state=state, cursor=cursor)

    @app.get("/v1/cases/{case_id}", response_model=CaseDetail, responses=_ERRORS,
             operation_id="get_case")
    def get_case(case_id: uuid.UUID, ctx: TrustedContext = Depends(context)):
        return service.get_case(ctx, case_id)

    @app.get("/v1/cases/{case_id}/audit", response_model=list[AuditEvent], responses=_ERRORS,
             operation_id="get_case_audit")
    def get_audit(case_id: uuid.UUID, ctx: TrustedContext = Depends(context)):
        return service.get_audit(ctx, case_id)

    @app.get("/v1/cases/{case_id}/investigation-trace", response_model=InvestigationTrace,
             responses=_ERRORS, operation_id="get_investigation_trace")
    def get_trace(case_id: uuid.UUID, ctx: TrustedContext = Depends(context),
                  workflow_id: uuid.UUID | None = Query(None)):
        """v1.2: the stored three-role workflow trace. Read-only: it never runs, recovers or
        changes anything (docs/api/investigation-trace-v1.2.md)."""
        return trace.investigation_trace(service, ctx, case_id, workflow_id)

    @app.post("/v1/cases/{case_id}/investigations", response_model=CaseDetail,
              responses=_ERRORS, operation_id="investigate_case")
    async def investigate(case_id: uuid.UUID, request: Request,
                          ctx: TrustedContext = Depends(context)):
        data = await body(request, InvestigationRequestInput)
        # The investigator may block (subprocess); keep it off the event loop.
        return await run_in_threadpool(service.investigate, ctx, case_id, data.expected_revision)

    @app.post("/v1/approvals", status_code=201, response_model=Approval, responses=_ERRORS,
              operation_id="record_approval")
    async def approve(request: Request, ctx: TrustedContext = Depends(context)):
        return await run_in_threadpool(service.record_approval, ctx,
                                       await body(request, ApprovalDecisionInput))

    @app.post("/v1/actions", response_model=ExecuteResponse, responses=_ERRORS,
              operation_id="execute_action")
    async def execute(request: Request, ctx: TrustedContext = Depends(context)):
        return await run_in_threadpool(service.execute_action, ctx,
                                       await body(request, ExecuteActionInput))

    # ---- v1.3: local documents (DOC01 Part B; docs/api/documents-v1.3.md) ----------------

    def authenticated(token: str = Depends(bearer)) -> tuple[TrustedContext, str]:
        # The token is needed only to derive the per-session document owner key in memory.
        return service.authenticate(token), token

    @app.post("/v1/documents", status_code=201, response_model=http_v13.DocumentUpload,
              responses=_DOC_ERRORS, operation_id="upload_document",
              openapi_extra={"requestBody": {"required": True, "content": {
                  media: {"schema": {"type": "string", "format": "binary"}}
                  for media in sorted({GENERIC_MEDIA_TYPE}.union(*DOCUMENT_MEDIA_TYPES.values()))
              }}})
    async def upload_document(request: Request,
                              format: http_v13.DocumentFormat = Query(),  # noqa: A002
                              auth: tuple[TrustedContext, str] = Depends(authenticated)):
        """Raw file bytes; the format is declared, never inferred from a filename."""
        ctx, token = auth
        if "analyze_document" not in ctx.capabilities:
            raise ServiceError("permission_denied", 403)
        media = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if media != GENERIC_MEDIA_TYPE and media not in DOCUMENT_MEDIA_TYPES[format]:
            raise ServiceError("unsupported_media_type", 415)
        data = await read_limited(request, http_v13.MAX_UPLOAD_BYTES)
        if not data:
            raise ServiceError("invalid_request", 422)
        return await run_in_threadpool(documents.upload, ctx, token, format, data)

    @app.post("/v1/documents/{handle_id}/analysis", response_model=http_v13.DocumentAnalysis,
              responses=_DOC_ERRORS, operation_id="analyze_document")
    async def analyze_document(handle_id: str, request: Request,
                               auth: tuple[TrustedContext, str] = Depends(authenticated)):
        """Runs the registered worker's bounded parser; the parser may block, so this runs
        off the event loop. A document that cannot be read is a 200 with status error."""
        ctx, token = auth
        if "analyze_document" not in ctx.capabilities:
            raise ServiceError("permission_denied", 403)
        if not DOCUMENT_HANDLE.match(handle_id):
            raise ServiceError("not_found", 404)
        data = await body(request, http_v13.AnalysisRequest)
        return await run_in_threadpool(documents.analyze, ctx, token, handle_id, data)

    @app.get("/v1/documents/{handle_id}/records", response_model=http_v13.RecordPage,
             responses=_DOC_ERRORS, operation_id="get_document_records")
    def get_document_records(handle_id: str,
                             offset: int = Query(0, ge=0, le=10_000_000),
                             limit: int = Query(http_v13.DEFAULT_RECORDS_LIMIT, ge=1,
                                                le=http_v13.MAX_RECORDS_LIMIT),
                             auth: tuple[TrustedContext, str] = Depends(authenticated)):
        ctx, token = auth
        return documents.records(ctx, token, handle_id, offset, limit)

    @app.delete("/v1/documents/{handle_id}", response_model=http_v13.DocumentDeleted,
                responses=_DOC_ERRORS, operation_id="delete_document")
    def delete_document(handle_id: str,
                        auth: tuple[TrustedContext, str] = Depends(authenticated)):
        ctx, token = auth
        return documents.delete(ctx, token, handle_id)

    app.openapi = lambda: openapi_document(app)
    return app


DOCUMENT_HANDLE = re.compile(r"^h_[A-Za-z0-9_-]{22}$")


def openapi_document(app: FastAPI) -> dict:
    """OpenAPI with the manually validated request bodies and bearer auth declared."""
    if app.openapi_schema:
        return app.openapi_schema
    doc = get_openapi(title=app.title, version=app.version, routes=app.routes,
                      description="Synthetic fraud-investigation workbench API. Scores are "
                      "rule heuristics unless score_semantics says otherwise.")
    models = sorted(set(REQUEST_BODIES.values()), key=lambda m: m.__name__)
    refs, defs = models_json_schema([(m, "validation") for m in models],
                                    ref_template="#/components/schemas/{model}")
    components = doc.setdefault("components", {})
    for name, schema in defs.get("$defs", {}).items():
        # Request (validation) and response (serialization) schemas can differ; keep both.
        existing = components.setdefault("schemas", {}).get(name)
        if existing is not None and existing != schema:
            raise RuntimeError(f"conflicting OpenAPI schema for {name}")
        components["schemas"][name] = schema
    components["securitySchemes"] = {"bearer": {"type": "http", "scheme": "bearer"}}
    for path, operations in doc["paths"].items():
        for operation in operations.values():
            model = REQUEST_BODIES.get(operation.get("operationId"))
            if model is not None:
                operation["requestBody"] = {"required": True, "content": {
                    "application/json": {"schema": refs[(model, "validation")]}}}
            if path != "/healthz":
                operation["security"] = [{"bearer": []}]
    app.openapi_schema = doc
    return doc


class RequestContext:
    """Plain ASGI middleware (keeps request streaming intact): request ID, one safe event and
    metrics per request, and containment of unexpected exceptions.

    An unexpected exception raised before response headers start is answered with the
    same plain-text 500 body as before (the frozen C01 contract). After headers have
    started (no current endpoint streams) the response cannot be replaced; the event then
    records the started status. In both cases the exception is not re-raised, so the server
    never logs its traceback or message; only the exception type name is recorded."""

    BODY = b"Internal Server Error"

    def __init__(self, app, metrics: Metrics, router):
        self.app, self.metrics, self.router = app, metrics, router

    def route_of(self, scope) -> str:
        for route in self.router.routes:
            match, _ = route.matches(scope)
            if match in (Match.FULL, Match.PARTIAL):
                return getattr(route, "path", "unmatched")
        return "unmatched"

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        supplied = dict(scope.get("headers") or []).get(b"x-request-id")
        rid = request_id(supplied.decode("latin-1") if supplied else None)
        scope.setdefault("state", {})["request_id"] = rid
        started = time.perf_counter()
        status: dict = {"code": None}

        async def send_with_id(message):
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
                headers = [h for h in message.get("headers", []) if h[0].lower() != b"x-request-id"]
                message = {**message, "headers": [*headers, (b"x-request-id", rid.encode())]}
            await send(message)

        error_type = None
        try:
            await self.app(scope, receive, send_with_id)
        except Exception as error:  # contained: type name only, never the message
            error_type = type(error).__name__
            if status["code"] is None:
                status["code"] = 500
                await send({"type": "http.response.start", "status": 500, "headers": [
                    (b"content-type", b"text/plain; charset=utf-8"),
                    (b"content-length", str(len(self.BODY)).encode()),
                    (b"x-request-id", rid.encode())]})
                await send({"type": "http.response.body", "body": self.BODY})
        duration_ms = round((time.perf_counter() - started) * 1000, 1)
        code = status["code"] or 500
        route = self.route_of(scope)
        method = method_label(scope["method"])
        self.metrics.observe(method, route, code, duration_ms)
        outcome = ("unexpected_error" if error_type else "ok" if code < 400
                   else "handled_error" if code < 500 else "server_error")
        fields = {"request_id": rid, "method": method, "route": route, "status": code,
                  "duration_ms": duration_ms, "outcome": outcome}
        if error_type:
            fields["error_type"] = error_type
        emit(HTTP_LOG, "http_request", logging.ERROR if code >= 500 else logging.INFO,
             **fields)


async def read_limited(request: Request, limit: int) -> bytes:
    """Reject a declared oversize body unread, and stop consuming a chunked or understated
    body as soon as it passes the limit (review R6)."""
    declared = request.headers.get("content-length")
    if declared is not None:
        if not declared.isdigit():
            raise ServiceError("invalid_content_length", 400)
        if int(declared) > limit:
            raise ServiceError("body_too_large", 413)
    raw = bytearray()
    async for chunk in request.stream():
        # Check the prospective size before copying: one oversize chunk is refused without
        # ever being appended (review R60).
        if len(raw) + len(chunk) > limit:
            raise ServiceError("body_too_large", 413)
        raw += chunk
    return bytes(raw)


class _InvalidBody(Exception):
    def __init__(self, details: list[dict[str, str]]):
        super().__init__("invalid_request")
        self.details = details
