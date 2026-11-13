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
import secrets
import threading
import time
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

# Durable records of bridge processes whose stop could not be confirmed (review R62). They
# live beside the worker's marker-owned store, hold only a pid and its creation identity,
# and are cleared only once that exact process is verified gone.
BRIDGE_RECORD_DIR = "api-bridge"
STOP_CONFIRM_SECONDS = 10.0
UNAVAILABLE = ("document_worker_unavailable", 503)
IDENTITY_CHANGED = ("document_worker_identity_changed", 503)
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
        self.kind = kind  # timeout | crashed | invalid | launch | identity


# ---- process state (R62): a pid is acted on only while its creation identity matches ------
# GONE is confirmed absence. LIVE comes with the creation identity, so a different identity
# means the pid was reused. UNKNOWN (inaccessible, unreadable, malformed or unsupported) is
# never treated as gone and never signalled.
GONE, LIVE, UNKNOWN = "gone", "live", "unknown"

if os.name == "nt":
    import ctypes
    from ctypes import wintypes

    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _k32.OpenProcess.restype = wintypes.HANDLE
    _k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _QUERY, _TERMINATE, _STILL_ACTIVE = 0x1000, 0x0001, 259
    _ERROR_INVALID_PARAMETER = 87  # OpenProcess: no process has this id

    def _open_process(pid: int, access: int):
        handle = _k32.OpenProcess(access, False, pid)
        return (handle, 0) if handle else (None, ctypes.get_last_error())

    def process_state(pid: int) -> tuple[str, str | None]:
        handle, error = _open_process(pid, _QUERY)
        if not handle:
            # Only "no such process" is absence; access denied and anything else are unknown.
            return (GONE, None) if error == _ERROR_INVALID_PARAMETER else (UNKNOWN, None)
        try:
            code = wintypes.DWORD()
            if not _k32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return UNKNOWN, None
            if code.value != _STILL_ACTIVE:
                return GONE, None  # exited (the object outlives it only while referenced)
            times = [wintypes.FILETIME() for _ in range(4)]
            if not _k32.GetProcessTimes(handle, *[ctypes.byref(t) for t in times]):
                return UNKNOWN, None
            created = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
            return LIVE, f"win-created:{created}"
        finally:
            _k32.CloseHandle(handle)

    def _terminate_pid(pid: int) -> None:
        handle, _error = _open_process(pid, _TERMINATE)
        if handle:
            try:
                _k32.TerminateProcess(handle, 1)
            finally:
                _k32.CloseHandle(handle)
else:
    import signal

    PROC_ROOT = "/proc"

    def _read_proc_stat(pid: int) -> str:
        with open(f"{PROC_ROOT}/{pid}/stat", encoding="ascii", errors="replace") as fh:
            return fh.read()

    def process_state(pid: int) -> tuple[str, str | None]:
        if not os.path.isdir(PROC_ROOT):
            return UNKNOWN, None  # no /proc (macOS and others): cannot tell, so keep
        try:
            raw = _read_proc_stat(pid)
        except (FileNotFoundError, ProcessLookupError):
            return GONE, None
        except OSError:
            return UNKNOWN, None  # permission or I/O error: maybe alive
        _head, sep, tail = raw.rpartition(")")
        fields = tail.split()
        if not sep or len(fields) < 20 or not fields[19].isdigit():
            return UNKNOWN, None
        if fields[0] == "Z":
            return GONE, None  # exited; a zombie's pid cannot be reused until it is reaped
        return LIVE, f"linux-start:{fields[19]}"

    def _terminate_pid(pid: int) -> None:
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass


def process_identity(pid: int) -> str | None:
    """The creation identity of a live process, or None when gone or unknown."""
    state, identity = process_state(pid)
    return identity if state == LIVE else None


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


_OPS = ("status", "ingest", "analyze", "records", "delete", "recover")


def _unlink(path) -> bool:
    try:
        path.unlink(missing_ok=True)
        return True
    except OSError:
        return False


class DocumentService:
    def __init__(self, config: WorkerConfig | None, metrics=None):
        self.config = config
        self.metrics = metrics
        self._state_lock = threading.Lock()
        self._analysis_slot = threading.BoundedSemaphore(1)
        self._identity: dict | None = None
        self._registered: str | None = None  # worker source digest bound at registration
        self._recovery_pending = True  # recover once before the first analysis
        self._inflight: set[str] = set()  # this process's own running bridge calls
        self._owner = {"owner_pid": os.getpid(), "owner_identity": process_identity(os.getpid())}

    @classmethod
    def from_environment(cls) -> "DocumentService":
        return cls(WorkerConfig.from_environment())

    # ---- bridge process ------------------------------------------------------------------

    def _call(self, header: dict, body: bytes = b"", owner: str | None = None,
              timeout: float | None = None) -> dict:
        config = self.config
        expected = self._registered or config.expected_source_sha256
        if expected is not None:
            # The bridge refuses before doing anything if it is not this worker (R63).
            header = dict(header, expect_source_sha256=expected)
        line = (json.dumps({"protocol": BRIDGE_PROTOCOL, **header}) + "\n").encode("utf-8")
        nonce = secrets.token_hex(8)
        with self._state_lock:
            self._inflight.add(nonce)
        try:
            return self._run_bridge(config, nonce, header.get("op"), line, body, owner,
                                    timeout, expected)
        finally:
            with self._state_lock:
                self._inflight.discard(nonce)

    def _run_bridge(self, config, nonce, op, line, body, owner, timeout, expected) -> dict:
        """One bridge process with durable evidence (R62). A launch intent is written before
        the process starts, and its pid and creation identity right after; if no durable
        evidence can be kept, the process is stopped before the request returns."""
        base = {"nonce": nonce, "op": op if op in _OPS else "unknown", **self._owner}
        if not self._write_record(nonce, dict(base, state="launching", pid=None,
                                              identity=None)):
            raise _BridgeFault("evidence")  # nothing launched
        try:
            proc = subprocess.Popen([*config.argv, "--store", config.store],
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, env=_bridge_env(owner),
                                    cwd=config.store, close_fds=True)
        except OSError:
            self._remove_records(nonce)
            raise _BridgeFault("launch") from None
        launched = process_identity(proc.pid)  # before any reuse of the pid is possible
        running = dict(base, state="running", pid=proc.pid, identity=launched)
        if not self._write_record(nonce, running):
            # No durable pid evidence: stop it now so it cannot outlive this request.
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                try:
                    stream.close()
                except OSError:
                    pass
            if self._stop_bridge(proc):
                self._remove_records(nonce)
            else:
                self._mark_pending("bridge")  # launch intent (and any pid temporary) stays
            raise _BridgeFault("evidence")
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
            if self._stop_bridge(proc):
                self._remove_records(nonce)
            else:
                # The running record already holds the pid; mark it best effort.
                self._write_record(nonce, dict(running, state="stop_unconfirmed"))
                self._mark_pending("bridge")
            raise _BridgeFault("timeout") from None
        finally:
            for thread in threads:
                thread.join(timeout=5)
        self._remove_records(nonce)  # exited and reaped: a leftover is cleared by recovery
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
        if expected is not None and (answer.get("code") == "identity_mismatch"
                                     or answer.get("worker_protocol") != WORKER_PROTOCOL
                                     or answer.get("worker_source_sha256") != expected):
            raise _BridgeFault("identity")
        return answer

    @staticmethod
    def _stop_bridge(proc) -> bool:
        """Kill the timed-out bridge and confirm its exit; any failure is uncertainty."""
        try:
            proc.kill()  # Windows: its job handle closes, so the parser child stops too
        except OSError:
            return False
        try:
            proc.wait(timeout=STOP_CONFIRM_SECONDS)
        except (subprocess.TimeoutExpired, OSError):
            return False
        return True

    def _record_folder(self):
        from pathlib import Path
        return Path(self.config.store) / BRIDGE_RECORD_DIR

    def _mark_pending(self, outcome: str) -> None:
        with self._state_lock:
            self._recovery_pending = True
        self._event("document_worker_stop_uncertain", outcome=outcome)

    def _write_record(self, nonce: str, data: dict) -> bool:
        """Atomically write bridge-<nonce>.json; two attempts with fresh temporary names.
        A temporary that carries a pid is kept if its replace fails: recovery reads it as
        evidence. Returns False if no complete record could be made durable."""
        folder = self._record_folder()
        target = folder / f"bridge-{nonce}.json"
        payload = json.dumps(dict(data, recorded_at=time.time()))
        for _attempt in range(2):
            tmp = folder / f"bridge-{nonce}.json.{secrets.token_hex(4)}.tmp"
            try:
                folder.mkdir(exist_ok=True)
                tmp.write_text(payload)
            except OSError:
                _unlink(tmp)
                continue
            try:
                os.replace(tmp, target)
                return True
            except OSError:
                if data.get("pid") is None:
                    _unlink(tmp)
        return False

    def _remove_records(self, nonce: str) -> bool:
        folder = self._record_folder()
        ok = True
        for path in [folder / f"bridge-{nonce}.json",
                     *folder.glob(f"bridge-{nonce}.json.*.tmp")]:
            ok = _unlink(path) and ok
        return ok

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
                              UNAVAILABLE if fault.kind in ("launch", "evidence") else
                              IDENTITY_CHANGED if fault.kind == "identity" else FAILED))

    # ---- readiness and recovery ------------------------------------------------------------

    def _ready(self) -> None:
        if self.config is None or not self.config.valid():
            raise ServiceError(*UNAVAILABLE)
        if self._identity is not None:
            return
        try:
            answer = self._call({"op": "status"})
        except _BridgeFault as fault:
            if fault.kind == "identity":  # not the pinned worker: registration fails
                self._event("document_worker_unregistered", outcome="identity_mismatch")
                raise ServiceError(*UNAVAILABLE) from None
            raise self._fault(fault, "status") from None
        pin = self.config.expected_source_sha256
        if not answer["ok"] or answer.get("worker_protocol") != WORKER_PROTOCOL \
                or not _DIGEST.match(str(answer.get("worker_source_sha256", ""))) \
                or (pin is not None and answer["worker_source_sha256"] != pin):
            self._event("document_worker_unregistered",
                        outcome=answer.get("code") or "identity_mismatch")
            raise ServiceError(*UNAVAILABLE)
        self._identity = answer
        self._registered = answer["worker_source_sha256"]  # every later call must match

    def _recover_bridges(self) -> int:
        """Verify recorded bridge processes; returns how many groups must still be kept.

        Records and their temporaries are grouped per call. A group is skipped while it is
        this process's own running call, or owned by another API process that is verifiably
        still alive. Otherwise every recorded pid must be confirmed gone (or reused by a
        different process) before the group is removed. A pid still verified as the recorded
        process is stopped, and its exit confirmed. Unknown state, an unreadable file or a
        launch intent with no pid evidence keeps the group and sends no signal.
        """
        folder = self._record_folder()
        if not folder.is_dir():
            return 0
        groups: dict[str, list] = {}
        for path in sorted(folder.glob("bridge-*")):
            key = path.name.split(".json", 1)[0]
            groups.setdefault(key, []).append(path)
        kept = 0
        for key, paths in groups.items():
            records, unreadable = [], False
            for path in paths:
                try:
                    data = json.loads(path.read_text())
                    if not isinstance(data, dict):
                        raise ValueError
                    records.append(data)
                except (OSError, ValueError):
                    unreadable = True
            if unreadable:
                kept += 1  # cannot prove which process it named
                continue
            nonce = next((r.get("nonce") for r in records if r.get("nonce")), None)
            with self._state_lock:
                if nonce in self._inflight:
                    continue  # this process's own call, still running
            if self._owned_by_another_live_api(records):
                continue
            if not self._confirm_stopped(records):
                kept += 1
                continue
            if not all(_unlink(path) for path in paths):
                kept += 1
        return kept

    def _owned_by_another_live_api(self, records) -> bool:
        owner = next(((r.get("owner_pid"), r.get("owner_identity")) for r in records
                      if r.get("owner_pid") is not None), None)
        if owner is None or owner[0] == os.getpid():
            return False
        state, identity = process_state(int(owner[0]))
        if state == UNKNOWN:
            return True  # cannot tell: leave it to its owner or to a later pass
        return state == LIVE and identity is not None and identity == owner[1]

    def _confirm_stopped(self, records) -> bool:
        pids = {}
        for rec in records:
            if rec.get("pid") is not None:
                try:
                    pids[int(rec["pid"])] = rec.get("identity")
                except (TypeError, ValueError):
                    return False
        if not pids:
            return False  # launch intent only: a bridge may exist without known pid
        for pid, recorded in pids.items():
            state, current = process_state(pid)
            if state == LIVE and recorded is not None and current == recorded:
                _terminate_pid(pid)  # exactly the recorded process: ours to stop
                deadline = time.monotonic() + STOP_CONFIRM_SECONDS
                while time.monotonic() < deadline:
                    state, current = process_state(pid)
                    if not (state == LIVE and current == recorded):
                        break
                    time.sleep(0.05)
            if state == GONE:
                continue
            if state == LIVE and recorded is not None and current != recorded:
                continue  # the pid now names a different process (reused): not signalled
            return False  # unknown, still the recorded process, or never identified
        return True

    def recover(self) -> dict:
        """Re-verify recorded runs; clears the pending flag only when nothing is kept."""
        self._ready()
        try:
            answer = self._call({"op": "recover"}, timeout=self.config.analyze_timeout_seconds)
        except _BridgeFault as fault:
            raise self._fault(fault, "recover") from None
        recovery = answer.get("recovery") if answer["ok"] else None
        kept = recovery.get("kept") if isinstance(recovery, dict) else None
        bridges_kept = self._recover_bridges()
        if isinstance(kept, int):
            kept += bridges_kept
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
        parser = compact.get("parser") or {}
        if compact.get("protocol") != WORKER_PROTOCOL \
                or parser.get("worker_source_sha256") != self._registered:
            # Parsing ran under a worker that is not the registered one: no report, and a
            # recovery pass before any reuse (review R63).
            with self._state_lock:
                self._recovery_pending = True
            self._event("document_worker_identity_changed", outcome="analyze")
            raise ServiceError(*IDENTITY_CHANGED)
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
        except (ValidationError, ValueError, TypeError):
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

