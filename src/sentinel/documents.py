"""DOC01 Part B: the API side of local document upload and analysis (HTTP v1.3).

The application never imports the document worker or its dependencies. An operator registers
the worker's own environment through server configuration only:

- SENTINEL_DOC_WORKER_PYTHON: absolute path of the worker environment's interpreter;
- SENTINEL_DOC_STORE: absolute path of a store initialised by `sentinel-docworker init`;
- SENTINEL_DOC_WORKER_SHA256 (optional): pin for the worker's reported source digest.

Each operation is one bounded bridge process (`-I -m docworker.bridge`, protocol
sentinel.doc01.bridge/0.1). It runs with a minimal environment: never the API's database
URL or other secrets. The per-session owner key is passed in SENTINEL_DOC_SESSION, and the
bearer token itself never leaves this process. Nothing here touches transactions, cases,
approvals, audit or simulated actions, and no model receives a document.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import subprocess
import threading
from dataclasses import dataclass

from pydantic import ValidationError

from sentinel.contracts import http_v13
from sentinel.contracts.v1 import TrustedContext
from sentinel.observability import emit
from sentinel.service import ServiceError

LOG = logging.getLogger("sentinel.documents")
BRIDGE_PROTOCOL = "sentinel.doc01.bridge/0.1"
WORKER_PROTOCOL = "sentinel.doc01.worker/0.1"
OWNER_DOMAIN = "sentinel.doc01.owner.v1"
CAPABILITY = "analyze_document"
OWNER_ENV = "SENTINEL_DOC_SESSION"
_HANDLE = re.compile(r"^h_[A-Za-z0-9_-]{22}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
MAX_ANSWER_BYTES = 8 * 1024 * 1024
MAX_STDERR_BYTES = 64 * 1024

UNAVAILABLE = ("document_worker_unavailable", 503)
BUSY = ("document_worker_busy", 503)
RECOVERY_PENDING = ("document_worker_recovery_pending", 503)
TIMEOUT = ("document_worker_timeout", 504)
FAILED = ("document_worker_failed", 502)
# Bridge refusal code -> (HTTP code, status). Anything not listed is a worker failure.
_REFUSALS = {
    "not_found": ("not_found", 404), "analysis_not_found": ("analysis_not_found", 404),
    "format_mismatch": ("format_mismatch", 415),
    "unsupported_container": ("unsupported_container", 415),
    "too_large": ("body_too_large", 413), "invalid_option": ("invalid_request", 422),
    "format_not_supported": ("invalid_request", 422), "not_owned": UNAVAILABLE,
}


class _BridgeFault(Exception):
    def __init__(self, kind: str):
        super().__init__(kind)
        self.kind = kind  # timeout | crashed | invalid | launch


@dataclass(frozen=True)
class WorkerConfig:
    argv: tuple[str, ...]
    store: str
    expected_source_sha256: str | None = None
    analyze_timeout_seconds: float = 90.0  # child deadline 30 s + stop + two interpreters
    call_timeout_seconds: float = 30.0

    @classmethod
    def from_environment(cls, environ=os.environ) -> "WorkerConfig | None":
        python = environ.get("SENTINEL_DOC_WORKER_PYTHON", "")
        store = environ.get("SENTINEL_DOC_STORE", "")
        if not python or not store:
            return None
        return cls(argv=(python, "-I", "-m", "docworker.bridge"), store=store,
                   expected_source_sha256=environ.get("SENTINEL_DOC_WORKER_SHA256") or None)

    def valid(self) -> bool:
        exe, store = self.argv[0], self.store
        return (os.path.isabs(exe) and os.path.isfile(exe) and os.path.isabs(store)
                and os.path.isdir(store) and not os.path.islink(store)
                and (self.expected_source_sha256 is None
                     or bool(_DIGEST.match(self.expected_source_sha256))))


def _bridge_env(owner: str | None) -> dict:
    """Only what an interpreter needs; never the API's environment (database URL, keys)."""
    env = {"PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    if os.name == "nt":
        root = os.environ.get("SYSTEMROOT", r"C:\Windows")
        env.update(SYSTEMROOT=root, WINDIR=root, PATH=os.path.join(root, "System32"))
    else:
        env.update(PATH="/usr/bin:/bin", LANG="C.UTF-8", LC_ALL="C.UTF-8")
    if owner is not None:
        env[OWNER_ENV] = owner
    return env


def owner_key(ctx: TrustedContext, token: str) -> str:
    """Per-session owner of document handles. Derived, so the bearer token never reaches the
    worker; stable across API restarts for as long as the session itself is valid."""
    material = "\0".join([OWNER_DOMAIN, str(ctx.scope.tenant_id), str(ctx.scope.session_id),
                          token])
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _require(ctx: TrustedContext) -> None:
    if CAPABILITY not in ctx.capabilities:
        raise ServiceError("permission_denied", 403)


def _handle(handle_id: str) -> str:
    if not isinstance(handle_id, str) or not _HANDLE.match(handle_id):
        raise ServiceError("not_found", 404)  # indistinguishable from missing or foreign
    return handle_id


class DocumentService:
    def __init__(self, config: WorkerConfig | None, metrics=None):
        self.config = config
        self.metrics = metrics
        self._state_lock = threading.Lock()
        self._analysis_slot = threading.BoundedSemaphore(1)
        self._identity: dict | None = None
        self._recovery_pending = True  # recover once before the first analysis

    @classmethod
    def from_environment(cls) -> "DocumentService":
        return cls(WorkerConfig.from_environment())

    # ---- bridge process ------------------------------------------------------------------

    def _call(self, header: dict, body: bytes = b"", owner: str | None = None,
              timeout: float | None = None) -> dict:
        config = self.config
        line = (json.dumps({"protocol": BRIDGE_PROTOCOL, **header}) + "\n").encode("utf-8")
        try:
            proc = subprocess.Popen([*config.argv, "--store", config.store],
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, env=_bridge_env(owner),
                                    cwd=config.store, close_fds=True)
        except OSError:
            raise _BridgeFault("launch") from None
        out, err, exceeded = bytearray(), bytearray(), threading.Event()

        def read(stream, buffer, cap, flag=None):
            try:
                while chunk := stream.read(65536):
                    if len(buffer) + len(chunk) > cap:
                        if flag is not None:
                            flag.set()
                        continue  # drain so the bridge cannot block on a full pipe
                    buffer += chunk
            except (OSError, ValueError):
                pass

        def write():
            try:
                proc.stdin.write(line)
                proc.stdin.write(body)
                proc.stdin.close()
            except (OSError, ValueError):
                pass

        threads = [threading.Thread(target=read, args=(proc.stdout, out, MAX_ANSWER_BYTES,
                                                       exceeded), daemon=True),
                   threading.Thread(target=read, args=(proc.stderr, err, MAX_STDERR_BYTES),
                                    daemon=True),
                   threading.Thread(target=write, daemon=True)]
        for thread in threads:
            thread.start()
        try:
            proc.wait(timeout=timeout or config.call_timeout_seconds)
        except subprocess.TimeoutExpired:
            proc.kill()  # Windows: closes the bridge's job handle, so its child is killed too
            proc.wait(timeout=10)
            raise _BridgeFault("timeout") from None
        finally:
            for thread in threads:
                thread.join(timeout=5)
        if exceeded.is_set():
            raise _BridgeFault("invalid")
        if proc.returncode != 0:
            raise _BridgeFault("crashed")
        try:
            lines = bytes(out).decode("utf-8").splitlines()
            answer = json.loads(lines[0]) if len(lines) == 1 else None
        except (UnicodeDecodeError, ValueError):
            answer = None
        if not isinstance(answer, dict) or answer.get("protocol") != BRIDGE_PROTOCOL \
                or not isinstance(answer.get("ok"), bool):
            raise _BridgeFault("invalid")
        return answer

    def _event(self, event: str, outcome: str, failure_code: str | None = None) -> None:
        """Safe-log fields only (observability allowlist): fixed or sanitised tokens."""
        def token(value):
            value = str(value)
            return value if re.fullmatch(r"[a-z0-9_]{1,40}", value) else "unrecognised"
        emit(LOG, event, logging.WARNING, outcome=token(outcome),
             failure_code=None if failure_code is None else token(failure_code))
        if self.metrics is not None:
            self.metrics.count(event)

    def _fault(self, fault: _BridgeFault, op: str) -> ServiceError:
        self._event("document_worker_fault", outcome=fault.kind, failure_code=op)
        if op == "analyze" or fault.kind == "timeout":
            with self._state_lock:
                self._recovery_pending = True
        return ServiceError(*(TIMEOUT if fault.kind == "timeout" else
                              UNAVAILABLE if fault.kind == "launch" else FAILED))

    # ---- readiness and recovery ------------------------------------------------------------

    def _ready(self) -> None:
        if self.config is None or not self.config.valid():
            raise ServiceError(*UNAVAILABLE)
        if self._identity is not None:
            return
        try:
            answer = self._call({"op": "status"})
        except _BridgeFault as fault:
            raise self._fault(fault, "status") from None
        pin = self.config.expected_source_sha256
        if not answer["ok"] or answer.get("worker_protocol") != WORKER_PROTOCOL \
                or not _DIGEST.match(str(answer.get("worker_source_sha256", ""))) \
                or (pin is not None and answer["worker_source_sha256"] != pin):
            self._event("document_worker_unregistered",
                        outcome=answer.get("code") or "identity_mismatch")
            raise ServiceError(*UNAVAILABLE)
        self._identity = answer

    def recover(self) -> dict:
        """Re-verify recorded runs; clears the pending flag only when nothing is kept."""
        self._ready()
        try:
            answer = self._call({"op": "recover"}, timeout=self.config.analyze_timeout_seconds)
        except _BridgeFault as fault:
            raise self._fault(fault, "recover") from None
        recovery = answer.get("recovery") if answer["ok"] else None
        kept = recovery.get("kept") if isinstance(recovery, dict) else None
        with self._state_lock:
            self._recovery_pending = not (isinstance(kept, int) and kept == 0)
        if self._recovery_pending:
            self._event("document_worker_recovery_kept",
                        outcome=str(kept) if isinstance(kept, int) else "unknown")
        return {"kept": kept, "pending": self._recovery_pending}

    # ---- operations --------------------------------------------------------------------------

    def _refusal(self, answer: dict) -> ServiceError:
        code = str(answer.get("code"))
        if code in _REFUSALS:
            return ServiceError(*_REFUSALS[code])
        self._event("document_worker_refusal", outcome="refused", failure_code=code)
        return ServiceError(*FAILED)

    def upload(self, ctx: TrustedContext, token: str, fmt: str, data: bytes):
        _require(ctx)
        self._ready()
        try:
            answer = self._call({"op": "ingest", "format": fmt, "size": len(data)}, data,
                                owner_key(ctx, token))
        except _BridgeFault as fault:
            raise self._fault(fault, "ingest") from None
        if not answer["ok"]:
            raise self._refusal(answer)
        handle = answer.get("handle") or {}
        try:
            return http_v13.DocumentUpload(
                handle_id=handle.get("handle_id"), format=handle.get("format"),
                sha256=handle.get("sha256"), size_bytes=handle.get("size"),
                expires_at=http_v13.utc_from_epoch(handle.get("expires_at")))
        except (ValidationError, TypeError, ValueError, OverflowError):
            raise ServiceError(*FAILED) from None

    def analyze(self, ctx: TrustedContext, token: str, handle_id: str,
                request: http_v13.AnalysisRequest):
        _require(ctx)
        handle_id = _handle(handle_id)
        self._ready()
        if self._recovery_pending:
            self.recover()
            if self._recovery_pending:
                raise ServiceError(*RECOVERY_PENDING)
        if not self._analysis_slot.acquire(blocking=False):
            raise ServiceError(*BUSY)
        try:
            options = request.model_dump(exclude={"records_limit"})
            try:
                answer = self._call({"op": "analyze", "handle": handle_id, "options": options,
                                     "page_limit": request.records_limit},
                                    owner=owner_key(ctx, token),
                                    timeout=self.config.analyze_timeout_seconds)
            except _BridgeFault as fault:
                raise self._fault(fault, "analyze") from None
        finally:
            self._analysis_slot.release()
        if not answer["ok"]:
            raise self._refusal(answer)
        compact = answer.get("analysis")
        if not isinstance(compact, dict):
            raise ServiceError(*FAILED)
        stop = (compact.get("supervisor") or {}).get("stop") or {}
        codes = [str(e.get("code")) for e in compact.get("errors") or [] if isinstance(e, dict)]
        if not stop.get("confirmed") or any(c.startswith(("stop_unconfirmed",
                                                          "recovery_record_write_failed"))
                                            for c in codes):
            # The result is already an error document; also block further runs until a
            # recovery pass proves the child and its records are gone.
            with self._state_lock:
                self._recovery_pending = True
            self._event("document_worker_stop_uncertain", outcome="analyze")
        try:
            return http_v13.project_analysis(handle_id, compact)
        except ValidationError:
            self._event("document_worker_invalid_answer", outcome="analyze")
            raise ServiceError(*FAILED) from None

    def records(self, ctx: TrustedContext, token: str, handle_id: str, offset: int,
                limit: int):
        _require(ctx)
        handle_id = _handle(handle_id)
        self._ready()
        try:
            answer = self._call({"op": "records", "handle": handle_id, "offset": offset,
                                 "limit": limit}, owner=owner_key(ctx, token))
        except _BridgeFault as fault:
            raise self._fault(fault, "records") from None
        if not answer["ok"]:
            raise self._refusal(answer)
        page = answer.get("records_page") or {}
        try:
            return http_v13.RecordPage(handle_id=handle_id, status=answer.get("status"),
                                       source_sha256=(answer.get("source") or {}).get("sha256"),
                                       **page)
        except (ValidationError, TypeError):
            raise ServiceError(*FAILED) from None

    def delete(self, ctx: TrustedContext, token: str, handle_id: str):
        _require(ctx)
        handle_id = _handle(handle_id)
        self._ready()
        try:
            answer = self._call({"op": "delete", "handle": handle_id},
                                owner=owner_key(ctx, token))
        except _BridgeFault as fault:
            raise self._fault(fault, "delete") from None
        if not answer["ok"]:
            raise self._refusal(answer)
        return http_v13.DocumentDeleted(handle_id=handle_id,
                                        deleted=answer.get("deleted") is True)

