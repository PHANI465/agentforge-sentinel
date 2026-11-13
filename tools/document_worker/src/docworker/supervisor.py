"""Owned, bounded parser child lifecycle with verified stop and recovery.

Lifecycle per extraction (concepts reused from the accepted local-stack/benchmark lifecycles:
ownership marker, verified-owned termination, explicit unconfirmed-stop recovery):

1. resolve the handle (session-scoped) and re-verify the stored bytes' SHA-256;
2. create an owned run directory (marker + nonce) and a recovery record BEFORE spawning;
3. spawn the base interpreter in isolated mode with a minimal environment and cwd = run dir;
4. contain it: Windows job object (kill-on-close, one active process, per-process committed
   memory, CPU time, UI restrictions); POSIX new session + RLIMIT_AS/CPU/FSIZE/NOFILE/CORE;
5. only then write the framed request; read stdout/stderr with byte caps; enforce a deadline;
6. always stop and CONFIRM the stop (job has no active process / process group is gone);
   confirmed -> remove the run dir and recovery record; unconfirmed -> keep both and report
   ``stop_unconfirmed``; ``recover()`` later re-verifies identity before acting.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import sysconfig
import threading
import time
from pathlib import Path

from . import PROTOCOL
from .handles import HandleStore, StoreError
from .limits import Limits, Options
from .validate import Invalid, validate

_RUN_RE = re.compile(r"^r_[0-9a-f]{16}$")
# Temporary record names: r_<id>.<8 hex>.tmp (unique per write), or the pre-fix r_<id>.tmp.
_TMP_RE = re.compile(r"^(r_[0-9a-f]{16})(?:\.[0-9a-f]{8})?\.tmp$")
# Windows reports a sharing violation (a reader holding the file open) as PermissionError;
# it is transient, so record replacement and removal retry for this long before failing.
RECORD_IO_RETRY_SECONDS = 2.0


class RecordWriteError(OSError):
    """A recovery record could not be written; the run must not be reported as a success."""


def _retry_sharing(operation, seconds: float = RECORD_IO_RETRY_SECONDS):
    deadline = time.monotonic() + seconds
    delay = 0.01
    while True:
        try:
            return operation()
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 0.2)
RUN_MARKER = ".docworker-run"


# ---- platform containment ----------------------------------------------------------------------

if os.name == "nt":
    import ctypes
    from ctypes import wintypes

    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class _BASIC(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64),
                    ("PerJobUserTimeLimit", ctypes.c_int64), ("LimitFlags", wintypes.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", wintypes.DWORD), ("Affinity", ctypes.c_size_t),
                    ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]

    class _IO(ctypes.Structure):
        _fields_ = [(n, ctypes.c_uint64) for n in ("ReadOps", "WriteOps", "OtherOps",
                                                   "ReadBytes", "WriteBytes", "OtherBytes")]

    class _EXTENDED(ctypes.Structure):
        _fields_ = [("Basic", _BASIC), ("Io", _IO), ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t)]

    class _ACCOUNTING(ctypes.Structure):
        _fields_ = [("TotalUserTime", ctypes.c_int64), ("TotalKernelTime", ctypes.c_int64),
                    ("ThisPeriodTotalUserTime", ctypes.c_int64),
                    ("ThisPeriodTotalKernelTime", ctypes.c_int64),
                    ("TotalPageFaultCount", wintypes.DWORD), ("TotalProcesses", wintypes.DWORD),
                    ("ActiveProcesses", wintypes.DWORD),
                    ("TotalTerminatedProcesses", wintypes.DWORD)]

    class _UI(ctypes.Structure):
        _fields_ = [("UIRestrictionsClass", wintypes.DWORD)]

    _k32.CreateJobObjectW.restype = wintypes.HANDLE
    _k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    _k32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                             wintypes.DWORD]
    _k32.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                               wintypes.DWORD, ctypes.c_void_p]
    _k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    _k32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    _k32.CloseHandle.argtypes = [wintypes.HANDLE]
    _k32.OpenProcess.restype = wintypes.HANDLE
    _k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _k32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(ctypes.c_uint64)] * 4
    _k32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    _k32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]

    _LIMIT_PROCESS_TIME, _LIMIT_ACTIVE_PROCESS = 0x2, 0x8
    _LIMIT_PROCESS_MEMORY, _LIMIT_DIE_ON_EXCEPTION, _LIMIT_KILL_ON_CLOSE = 0x100, 0x400, 0x2000
    _QUERY_LIMITED, _TERMINATE, _STILL_ACTIVE = 0x1000, 0x1, 259

    class Containment:
        def __init__(self, limits: Limits):
            self.job = _k32.CreateJobObjectW(None, None)
            if not self.job:
                raise OSError(ctypes.get_last_error(), "CreateJobObject failed")
            info = _EXTENDED()
            info.Basic.LimitFlags = (_LIMIT_KILL_ON_CLOSE | _LIMIT_ACTIVE_PROCESS
                                     | _LIMIT_PROCESS_MEMORY | _LIMIT_DIE_ON_EXCEPTION
                                     | _LIMIT_PROCESS_TIME)
            info.Basic.ActiveProcessLimit = 1
            info.Basic.PerProcessUserTimeLimit = int(limits.deadline_seconds * 2 * 10_000_000)
            info.ProcessMemoryLimit = int(limits.memory_bytes)
            if not _k32.SetInformationJobObject(self.job, 9, ctypes.byref(info),
                                                ctypes.sizeof(info)):
                err = ctypes.get_last_error()
                self.close()
                raise OSError(err, "SetInformationJobObject failed")
            ui = _UI(0xFF)  # no desktop, clipboard, global atoms, display/system settings
            _k32.SetInformationJobObject(self.job, 4, ctypes.byref(ui), ctypes.sizeof(ui))

        def popen_kwargs(self) -> dict:
            return {"creationflags": 0x08000000 | 0x00000200}  # NO_WINDOW | NEW_PROCESS_GROUP

        def attach(self, proc: subprocess.Popen) -> None:
            if not _k32.AssignProcessToJobObject(self.job, int(proc._handle)):
                raise OSError(ctypes.get_last_error(), "AssignProcessToJobObject failed")

        def terminate(self, proc: subprocess.Popen) -> None:
            if self.job:
                _k32.TerminateJobObject(self.job, 1)

        def active(self, proc: subprocess.Popen) -> int:
            acct = _ACCOUNTING()
            if not self.job or not _k32.QueryInformationJobObject(
                    self.job, 1, ctypes.byref(acct), ctypes.sizeof(acct), None):
                return -1
            return int(acct.ActiveProcesses)

        def peak_memory(self) -> int | None:
            info = _EXTENDED()
            if self.job and _k32.QueryInformationJobObject(
                    self.job, 9, ctypes.byref(info), ctypes.sizeof(info), None):
                return int(info.PeakProcessMemoryUsed)
            return None

        def close(self) -> None:
            if self.job:
                _k32.CloseHandle(self.job)  # kill-on-close: a last-resort stop
                self.job = None

    def process_identity(pid: int) -> str | None:
        handle = _k32.OpenProcess(_QUERY_LIMITED, False, pid)
        if not handle:
            return None
        try:
            code = wintypes.DWORD()
            if not _k32.GetExitCodeProcess(handle, ctypes.byref(code)) \
                    or code.value != _STILL_ACTIVE:
                return None
            times = [ctypes.c_uint64() for _ in range(4)]
            if not _k32.GetProcessTimes(handle, *[ctypes.byref(t) for t in times]):
                return None
            return f"win-created:{times[0].value}"
        finally:
            _k32.CloseHandle(handle)

    def kill_pid(pid: int) -> None:
        handle = _k32.OpenProcess(_TERMINATE, False, pid)
        if handle:
            _k32.TerminateProcess(handle, 1)
            _k32.CloseHandle(handle)

else:
    import resource

    class Containment:
        def __init__(self, limits: Limits):
            self.limits = limits

        def popen_kwargs(self) -> dict:
            limits = self.limits

            def preexec() -> None:
                os.setsid()
                aspace = int(limits.posix_address_space_bytes)
                cpu = int(limits.deadline_seconds * 2) + 1
                resource.setrlimit(resource.RLIMIT_AS, (aspace, aspace))
                resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
                resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
                resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
                resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
            return {"preexec_fn": preexec}

        def attach(self, proc: subprocess.Popen) -> None:
            return None  # limits applied in the child before exec

        def terminate(self, proc: subprocess.Popen) -> None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass

        def active(self, proc: subprocess.Popen) -> int:
            if proc.poll() is None:
                return 1
            try:
                os.killpg(proc.pid, 0)
            except ProcessLookupError:
                return 0
            except PermissionError:
                return -1
            return 1  # a group member (e.g. a grandchild) is still alive

        def peak_memory(self) -> int | None:
            kib = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
            return int(kib) * 1024 if kib else None  # max over children of this process

        def close(self) -> None:
            return None

    class _StatUnknown(Exception):
        """/proc/<pid>/stat exists but cannot be read or parsed: state is unknown (R58)."""

    def _read_stat(pid: int) -> str:
        return Path(f"/proc/{pid}/stat").read_text()

    def _proc_pids() -> list[int]:
        return [int(name) for name in os.listdir("/proc") if name.isdigit()]

    def _stat_fields(pid: int) -> list[str] | None:
        """Fields after the comm, or None only when the process has genuinely disappeared.

        ENOENT/ESRCH mean the entry vanished (the process exited and was reaped). Any other
        error (permission, I/O) or malformed content raises _StatUnknown: an unreadable entry
        may be a live process and is never treated as absent.
        """
        try:
            raw = _read_stat(pid)
        except (FileNotFoundError, ProcessLookupError):
            return None
        except OSError as exc:
            raise _StatUnknown(type(exc).__name__) from None
        _, sep, tail = raw.rpartition(")")
        fields = tail.split()
        if (not sep or len(fields) < 20 or not fields[2].lstrip("-").isdigit()
                or not fields[19].isdigit()):
            raise _StatUnknown("malformed")
        return fields

    def process_identity(pid: int) -> str | None:
        """Start-time identity of a live process; None if gone, a zombie or unreadable.

        None never proves a process group empty: recovery checks the group separately and
        fails closed when any /proc entry is unreadable.
        """
        try:
            fields = _stat_fields(pid)
        except _StatUnknown:
            return None
        if fields is None or fields[0] == "Z":
            return None
        return f"linux-start:{fields[19]}"

    def kill_pid(pid: int) -> None:
        """Kill one verified process (not its group; see recover())."""
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass

    def process_pgid(pid: int) -> int | None:
        try:
            fields = _stat_fields(pid)
        except _StatUnknown:
            return None
        return None if fields is None or fields[0] == "Z" else int(fields[2])

    def group_members(pgid: int) -> list[int] | None:
        """Live (non-zombie) pids whose process group is pgid; None if it cannot be determined.

        A process group id is never reused while any member exists, so a non-empty result
        means the recorded group (or a later group that reused the id) is still populated.
        Fails closed (None) if /proc cannot be listed or any listed entry, other than one
        that genuinely disappeared, cannot be read or parsed: that entry might be a member.
        """
        try:
            if not Path("/proc/self/stat").exists():
                return None
            pids = _proc_pids()
        except OSError:
            return None
        members = []
        for pid in pids:
            try:
                fields = _stat_fields(pid)
            except _StatUnknown:
                return None
            if fields is not None and fields[0] != "Z" and int(fields[2]) == pgid:
                members.append(pid)
        return sorted(members)

    def _group_exists(pgid: int) -> bool | None:
        """Kernel answer, taken after the /proc scan, to whether any process (live or zombie)
        is in the group. Signal 0 is an existence/permission query only: nothing is sent.

        A /proc snapshot alone cannot prove emptiness: a member can fork a new member after
        the listing and then exit (review DOC01-7ec46ae). ESRCH proves the group empty;
        EPERM means a process exists that we may not signal (inaccessible or reused id);
        any other error is unknown.
        """
        try:
            os.killpg(pgid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return None
        return True

    def kill_group(pgid: int) -> None:
        try:
            os.killpg(pgid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass


# ---- helpers -------------------------------------------------------------------------------------

def default_child_argv() -> list[str]:
    """Base interpreter, isolated mode, explicit import path (no venv redirector process)."""
    base = getattr(sys, "_base_executable", None) or sys.executable
    src = str(Path(__file__).resolve().parent.parent)
    paths = [src]
    for key in ("purelib", "platlib"):
        p = sysconfig.get_paths()[key]
        if p not in paths:
            paths.append(p)
    boot = ("import sys; sys.path[:0] = " + repr(paths) + "; "
            "from docworker.child import main; sys.exit(main())")
    return [base, "-I", "-c", boot]


def _child_env(run_dir: Path) -> dict:
    env = {"TEMP": str(run_dir), "TMP": str(run_dir), "TMPDIR": str(run_dir),
           "HOME": str(run_dir), "PYTHONIOENCODING": "utf-8", "PYTHONHASHSEED": "0",
           "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
    if os.name == "nt":
        root = os.environ.get("SYSTEMROOT", r"C:\Windows")
        env.update(SYSTEMROOT=root, WINDIR=root,
                   PATH=os.pathsep.join([os.path.dirname(default_child_argv()[0]),
                                         os.path.join(root, "System32")]))
    else:
        env.update(PATH="/usr/bin:/bin", LANG="C.UTF-8", LC_ALL="C.UTF-8")
    return env


class _CappedReader(threading.Thread):
    def __init__(self, stream, cap: int):
        super().__init__(daemon=True)
        self.stream, self.cap = stream, cap
        self.chunks: list[bytes] = []
        self.size = 0
        self.exceeded = threading.Event()

    def run(self) -> None:
        try:
            while True:
                chunk = self.stream.read(65536)
                if not chunk:
                    return
                self.size += len(chunk)
                if self.size > self.cap:
                    self.exceeded.set()
                    continue  # drain and discard so the child cannot block on a full pipe
                self.chunks.append(chunk)
        except (OSError, ValueError):
            return

    def data(self) -> bytes:
        return b"".join(self.chunks)


def _writer(stream, header: bytes, data: bytes, failed: list) -> None:
    try:
        stream.write(header)
        view = memoryview(data)
        for start in range(0, len(view), 1 << 20):
            stream.write(view[start:start + (1 << 20)])
        stream.close()
    except (OSError, ValueError) as exc:  # the child exited or closed stdin early
        failed.append(type(exc).__name__)


# ---- supervisor ------------------------------------------------------------------------------------

class Supervisor:
    def __init__(self, store: HandleStore, limits: Limits | None = None,
                 child_argv: list[str] | None = None, hooks: dict | None = None):
        self.store = store
        self.limits = limits or store.limits
        self.child_argv = child_argv or default_child_argv()
        self.hooks = hooks or {}  # test seams: after_spawn, confirm_stop, child_output

    def _record_path(self, run_id: str) -> Path:
        return self.store.root / "recovery" / f"{run_id}.json"

    def _write_record(self, run_id: str, data: dict) -> None:
        """Atomically replace the run's record, retrying transient sharing violations.

        Each write uses its own temporary name, so concurrent or failed writes never collide.
        If the replace still fails, a temporary that carries the child's pid is kept, since it
        may be the only copy recovery can use; a pid-less one is removed. RecordWriteError is
        raised either way, so the caller cannot report the run as a success.
        """
        path = self._record_path(run_id)
        tmp = path.with_name(f"{run_id}.{secrets.token_hex(4)}.tmp")
        try:
            tmp.write_text(json.dumps(data))
            _retry_sharing(lambda: os.replace(tmp, path))
        except OSError as exc:
            if data.get("pid") is None:
                try:
                    _retry_sharing(lambda: tmp.unlink(missing_ok=True))
                except OSError:
                    pass
            raise RecordWriteError(exc.errno, f"recovery record write failed: "
                                              f"{type(exc).__name__}") from None

    def _remove_records(self, run_id: str) -> bool:
        """Remove the run's record and any temporary records; True when none remain."""
        folder = self.store.root / "recovery"
        paths = [self._record_path(run_id)] + [
            p for p in folder.glob(f"{run_id}*.tmp") if _TMP_RE.match(p.name)
            and _TMP_RE.match(p.name).group(1) == run_id]
        ok = True
        for p in paths:
            try:
                _retry_sharing(lambda p=p: p.unlink(missing_ok=True))
            except OSError:
                ok = False
        return ok

    def _new_run(self) -> tuple[str, str, Path]:
        run_id = "r_" + secrets.token_hex(8)
        nonce = secrets.token_hex(16)
        run_dir = self.store.root / "runs" / run_id
        run_dir.mkdir()
        (run_dir / RUN_MARKER).write_text(json.dumps({"run_id": run_id, "nonce": nonce,
                                                      "owner": self.store.owner()}))
        return run_id, nonce, run_dir

    def _remove_run_dir(self, run_id: str, nonce: str) -> bool:
        run_dir = self.store.root / "runs" / run_id
        if not run_dir.exists():
            return True
        base = os.path.normcase(os.path.realpath(self.store.root / "runs")) + os.sep
        if os.path.islink(run_dir) or not os.path.normcase(
                os.path.realpath(run_dir)).startswith(base):
            return False
        try:
            marker = json.loads((run_dir / RUN_MARKER).read_text())
        except (OSError, ValueError):
            return False
        if not secrets.compare_digest(str(marker.get("nonce")), nonce):
            return False
        shutil.rmtree(run_dir, ignore_errors=True)
        return not run_dir.exists()

    def extract(self, handle_id: str, session_token: str, options: Options | None = None,
                narrative: bool = True) -> dict:
        options = options or Options()
        resolved = self.store.resolve(handle_id, session_token)
        data = self.store.read_verified(resolved)
        request_id = "q_" + secrets.token_hex(8)
        header = (json.dumps({"protocol": PROTOCOL, "request_id": request_id,
                              "format": resolved.format, "size": len(data),
                              "sha256": resolved.sha256, "limits": self.limits.to_dict(),
                              "options": options.to_dict(), "narrative": narrative})
                  + "\n").encode("utf-8")
        run_id, nonce, run_dir = self._new_run()
        record = {"run_id": run_id, "nonce": nonce, "state": "starting", "pid": None,
                  "identity": None, "created_at": time.time(), "handle_id": handle_id}
        sup = {"run_id": run_id, "request_id": request_id, "exit_code": None,
               "stdout_bytes": 0, "stderr_bytes": 0, "elapsed_ms": None,
               "peak_memory_bytes": None, "containment": None, "stop": None,
               "outcome": None}
        started = time.monotonic()
        proc = None
        containment = None
        outcome, outcome_code = None, None
        out_reader = err_reader = None
        try:
            self._write_record(run_id, record)  # before any child exists
            containment = Containment(self.limits)
            proc = subprocess.Popen(self.child_argv, stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    cwd=str(run_dir), env=_child_env(run_dir),
                                    close_fds=True, **containment.popen_kwargs())
            containment.attach(proc)
            sup["containment"] = ("windows_job_object" if os.name == "nt"
                                  else "posix_session_rlimits")
            record.update(state="running", pid=proc.pid, identity=process_identity(proc.pid),
                          pgid=None if os.name == "nt" else proc.pid,
                          containment=sup["containment"])
            self._write_record(run_id, record)
            if "after_spawn" in self.hooks:
                self.hooks["after_spawn"](proc)
            out_reader = _CappedReader(proc.stdout, self.limits.max_stdout_bytes)
            err_reader = _CappedReader(proc.stderr, self.limits.max_stderr_bytes)
            out_reader.start()
            err_reader.start()
            write_failed: list = []
            threading.Thread(target=_writer, args=(proc.stdin, header, data, write_failed),
                             daemon=True).start()
            deadline = started + self.limits.deadline_seconds
            while True:
                try:
                    proc.wait(timeout=0.05)
                    break
                except subprocess.TimeoutExpired:
                    pass
                if out_reader.exceeded.is_set():
                    outcome, outcome_code = "error", "output_limit_exceeded"
                    break
                if time.monotonic() >= deadline:
                    outcome, outcome_code = "error", "deadline_exceeded"
                    break
        except RecordWriteError:
            # No durable record of this child: stop it now; never report the run a success.
            outcome, outcome_code = "error", f"recovery_record_write_failed:{record['state']}"
        except OSError as exc:
            outcome, outcome_code = "error", f"containment_failed:{exc.__class__.__name__}"
        finally:
            stop = self._stop(proc, containment)
            sup["stop"] = stop
            sup["elapsed_ms"] = round((time.monotonic() - started) * 1000, 1)
            if containment is not None:
                sup["peak_memory_bytes"] = containment.peak_memory()
                containment.close()
            for reader in (out_reader, err_reader):
                if reader is not None:
                    reader.join(timeout=2)
            if stop["confirmed"]:
                stop["run_dir_removed"] = self._remove_run_dir(run_id, nonce)
                if stop["run_dir_removed"]:
                    # A failed removal leaves a record whose child is confirmed gone; a
                    # later recover() re-verifies and removes it. Never raised from here.
                    stop["record_removed"] = self._remove_records(run_id)
            else:
                record.update(state="stop_unconfirmed", stopped_at=time.time())
                try:
                    self._write_record(run_id, record)
                    stop["record_written"] = True
                except RecordWriteError:
                    # The earlier 'running' record (or its kept temporary) still names the
                    # child, so recovery can re-verify it.
                    stop["record_written"] = False
        sup["exit_code"] = proc.returncode if proc is not None else None
        sup["stdout_bytes"] = out_reader.size if out_reader else 0
        sup["stderr_bytes"] = err_reader.size if err_reader else 0
        if out_reader is not None and out_reader.exceeded.is_set():
            outcome, outcome_code = "error", "output_limit_exceeded"
        result = None
        reason = ""
        if outcome is None:
            raw = out_reader.data()
            if "child_output" in self.hooks:
                self.hooks["child_output"](raw)
            expected = {"format": resolved.format, "sha256": resolved.sha256,
                        "size": resolved.size, "max_records": self.limits.max_records}
            result, outcome_code, reason = self._parse(raw, request_id, proc.returncode,
                                                       expected)
            outcome = None if result is not None else "error"
        if result is None:
            result = {"protocol": PROTOCOL, "request_id": request_id, "status": "error",
                      "errors": [{"code": outcome_code, "detail": reason}]}
        if not sup["stop"]["confirmed"]:
            result["status"] = "error"
            result.setdefault("errors", []).append(
                {"code": "stop_unconfirmed",
                 "detail": "recovery record retained; run `recover` to re-verify"})
        sup["outcome"] = outcome_code or "child_result"
        result["supervisor"] = sup
        result["handle"] = {"handle_id": resolved.handle_id, "format": resolved.format,
                            "sha256": resolved.sha256, "size_bytes": resolved.size}
        return result

    def _parse(self, raw: bytes, request_id: str, code: int | None, expected: dict):
        """(document, None, "") or (None, code, fixed reason token). Never echoes child text."""
        failure = f"invalid_child_output:exit_{code}"
        try:
            doc = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError, RecursionError):
            return None, failure, "not_json"
        try:
            return validate(doc, request_id, code, expected), None, ""
        except Invalid as exc:
            return None, failure, str(exc)

    def _stop(self, proc, containment) -> dict:
        info = {"requested": False, "confirmed": True, "method": None}
        if proc is None:
            return info
        if containment is not None and containment.active(proc) != 0 or proc.poll() is None:
            info["requested"] = True
            info["method"] = "terminate_job" if os.name == "nt" else "killpg_sigkill"
            if containment is not None:
                containment.terminate(proc)
            else:
                proc.kill()
        deadline = time.monotonic() + self.limits.stop_confirm_seconds
        confirmed = False
        while time.monotonic() < deadline:
            exited = proc.poll() is not None
            group_empty = containment is None or containment.active(proc) == 0
            if exited and group_empty:
                confirmed = True
                break
            time.sleep(0.05)
        if "confirm_stop" in self.hooks:
            confirmed = self.hooks["confirm_stop"](confirmed)
        info["confirmed"] = confirmed
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            try:
                if stream and confirmed:
                    stream.close()
            except OSError:
                pass
        return info

    # ---- recovery ------------------------------------------------------------------------------
    def _group_empty(self, pgid: int | None) -> bool | None:
        if os.name == "nt" or pgid is None:
            return True  # Windows: one-process job, killed on close; no group to track
        members = group_members(pgid)
        if members is None:
            return None
        if members:
            return False
        # The scan saw no live member. Confirm at the kernel boundary, after the scan, so a
        # member forked after the listing still counts. A zombie-only group also answers
        # "exists" and is kept conservatively until it is reaped.
        exists = _group_exists(pgid)
        return None if exists is None else not exists

    def _stop_recorded(self, pid: int, identity: str, rec: dict) -> tuple[str, int | None]:
        """Stop a recorded child only when its identity is proven; confirm its group is empty.

        Returns ("stopped_or_gone" | a *_kept reason, pid signalled or None). Never signals a process or group whose
        ownership cannot be proven: an exited leader is not proof that its group is empty.
        """
        terminated = None
        pgid = None if os.name == "nt" else int(rec.get("pgid") or pid)
        if process_identity(pid) == identity:
            # The verified leader is alive. If it is still in the recorded group, that group
            # is ours (its id cannot be reused while the leader exists): stop the group.
            if os.name != "nt" and process_pgid(pid) == pgid:
                kill_group(pgid)
            else:
                kill_pid(pid)
            terminated = pid
            deadline = time.monotonic() + self.limits.stop_confirm_seconds
            while time.monotonic() < deadline and (
                    process_identity(pid) == identity or self._group_empty(pgid) is False):
                time.sleep(0.05)
            if process_identity(pid) == identity:
                return "still_running_kept", terminated
        empty = self._group_empty(pgid)
        if empty is None:
            return "group_state_unknown_kept", terminated
        if not empty:
            return "group_members_alive_kept", terminated
        return "stopped_or_gone", terminated

    def recover(self) -> dict:
        """Re-verify every recorded run; remove only what is proven stopped and owned.

        Temporary records are part of the evidence (review DOC01-8f7bd87): a failed replace
        can leave the only copy of a child's pid in r_<id>.<hex>.tmp. Every pid named by the
        record or a temporary of the same run must be proven stopped before anything is
        removed; an unreadable temporary beside a record keeps the run.
        """
        self.store.verify()
        folder = self.store.root / "recovery"
        report = []
        temporaries: dict[str, list[Path]] = {}
        for path in sorted(folder.glob("r_*.tmp")):
            match = _TMP_RE.match(path.name)
            if match is None:
                report.append({"record": path.name, "result": "invalid_record_kept"})
                continue
            temporaries.setdefault(match.group(1), []).append(path)
        for path in sorted(folder.glob("r_*.json")):
            entry = {"record": path.name}
            try:
                rec = json.loads(path.read_text())
                run_id, nonce = str(rec["run_id"]), str(rec["nonce"])
            except (OSError, ValueError, KeyError):
                entry["result"] = "unreadable_record_kept"
                report.append(entry)
                continue
            if not _RUN_RE.match(run_id) or path.name != f"{run_id}.json":
                entry["result"] = "invalid_record_kept"
                report.append(entry)
                continue
            extra, torn = self._read_temporaries(temporaries.pop(run_id, []), run_id)
            if torn:
                entry["result"] = "temporary_record_unreadable_kept"
                report.append(entry)
                continue
            report.append(self._recover_run(entry, run_id, nonce, [rec, *extra]))
        for run_id, paths in sorted(temporaries.items()):
            entry = {"record": paths[0].name}
            extra, torn = self._read_temporaries(paths, run_id)
            live = [r for r in extra if r.get("pid") is not None]
            run_dir = self.store.root / "runs" / run_id
            if not live and not run_dir.exists():
                # No record, no run dir and no pid: the run was already cleaned up after a
                # confirmed stop (or never spawned); the temporary proves nothing outstanding.
                entry["result"] = ("orphan_temporary_removed" if self._remove_records(run_id)
                                   else "orphan_temporary_kept")
                report.append(entry)
                continue
            if torn or not live:
                entry["result"] = "temporary_record_unreadable_kept"
                report.append(entry)
                continue
            report.append(self._recover_run(entry, run_id, str(live[0].get("nonce", "")),
                                            live))
        return {"records": report}

    def _read_temporaries(self, paths: list[Path], run_id: str) -> tuple[list[dict], bool]:
        records, torn = [], False
        for path in paths:
            try:
                data = json.loads(path.read_text())
                if not isinstance(data, dict) or data.get("run_id") != run_id:
                    raise ValueError
                records.append(data)
            except (OSError, ValueError):
                torn = True
        return records, torn

    def _recover_run(self, entry: dict, run_id: str, nonce: str, records: list[dict]) -> dict:
        seen = set()
        for rec in records:
            pid, identity = rec.get("pid"), rec.get("identity")
            if pid is None or (pid, identity) in seen:
                continue
            seen.add((pid, identity))
            if identity is None:
                entry["result"] = "identity_unknown_kept"  # cannot prove which process it was
                return entry
            outcome, terminated = self._stop_recorded(int(pid), identity, rec)
            if terminated is not None:
                entry["terminated_pid"] = terminated
            if outcome != "stopped_or_gone":
                entry["result"] = outcome  # record and run dir retained (R58)
                return entry
        if not self._remove_run_dir(run_id, nonce):
            entry["result"] = "run_dir_not_owned_kept"
            return entry
        entry["result"] = "recovered" if self._remove_records(run_id) else "record_removal_kept"
        return entry


def file_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


__all__ = ["Supervisor", "StoreError", "default_child_argv", "process_identity"]
