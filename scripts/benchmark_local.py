"""PERF01: one bounded, deterministic local capacity measurement (not an optimization tool).

    uv run --locked python scripts/benchmark_local.py [--requests 12] [--concurrency 1,2,4]
        [--workloads ingest,read,investigate] [--max-requests 108] [--max-seconds 300]
        [--warmup 2] [--seed N] [--investigator three-role|deterministic] [--run-dir DIR]

What it does, in order, and nothing else:

1. Starts a FRESH test-owned stack with the accepted helper `scripts/local_stack.py`
   (unchanged; its ownership marker, identity checks and recovery) in a new run directory:
   rule scorer, the deterministic three-role investigator by default (adapter always
   deterministic), loopback API connecting as the runtime role. There is no target option:
   the only target is http://127.0.0.1:<the owned API port>. No provider, credential or
   remote call is possible: the inherited live/adapter settings are removed, the Claude
   executable points at a path that does not exist and the HTTP client ignores proxies.
2. Setup (counted separately): health/scorer checks, synthetic alert cases for the read and
   investigate workloads, then a few sequential warm-up requests per workload.
3. Measurement: workloads `ingest` (unique non-alerting synthetic transactions), `read`
   (GET existing scoped cases) and `investigate` (one independent fresh alert case per
   request) at each requested concurrency, closed loop. Hard caps on measured requests and
   on active measurement time stop NEW work; in-flight requests finish within their client
   timeout. There are no retries, no sweep and no server limit changes.
4. Verification (counted separately): every scoped case is read back; approvals and
   simulated actions must be 0. Unknown outcomes are reconciled from that read, and stay
   reported as unknown.
5. The helper's own `down`. Cleanup is reported only when the recorded processes are gone
   and both ports are free; otherwise the state is kept and a recovery command is printed.

Outcomes: success (expected status and body), refused (any 4xx, its service code kept; an
expected 409 agent_capacity_exhausted is refused, never a success), failed (5xx, unexpected
body, or a request that provably never reached the server) and unknown (client timeout,
broken connection after sending, investigation_outcome_unknown, or a request still in flight
when the bounded wait ended). Latency is monotonic seconds; quantiles are nearest-rank.

Private raw records stay in the run directory (default .agent/perf01/, git-ignored). The
token never leaves memory; reports contain no URL, host name, user, command line or
environment. Resident memory is sampled only on verified owned processes (see `Sampler`).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import platform
import random
import subprocess
import sys
import threading
import time
import uuid
from collections import Counter
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import local_stack  # noqa: E402  (reused unchanged; it also puts ROOT/src on sys.path)

SCHEMA = 1
DEFAULT_RUN_ROOT = ROOT / ".agent" / "perf01"
WORKLOADS = ("ingest", "read", "investigate")
INVESTIGATORS = ("three-role", "deterministic")
HEALTH_NAME = {"three-role": "three-role-workflow", "deterministic": "deterministic-investigator"}
# Hard ceilings: options may lower the defaults, never exceed these.
MAX_REQUESTS_PER_CELL = 50
MAX_CONCURRENCY = 4
MAX_MEASURED_REQUESTS = 200
MAX_MEASURE_SECONDS = 600
MAX_WARMUP = 5
MAX_SETUP_REQUESTS = 300
MAX_VERIFY_REQUESTS = 400
# Client timeouts (seconds). Investigation's exceeds the server's 150 s workflow deadline so
# a slow but bounded workflow is observed, not turned into an artificial unknown.
TIMEOUT = {"ingest": 30.0, "read": 30.0, "investigate": 175.0, "setup": 30.0, "verify": 30.0}
JOIN_MARGIN_SECONDS = 10.0
NOT_NEEDED = "not needed (no stack state was created)"
STACK_UP_SECONDS = 600
STACK_DOWN_SECONDS = 180
SMALL_MINOR, ALERT_MINOR = 1_500, 250_000  # rule scorer: 0.0 (no alert) and 0.6 (alert)
# Inherited settings that could select another configuration or reach a provider.
DROP_ENV = ("PYTHONPATH", "VIRTUAL_ENV", "SENTINEL_TEST_DATABASE_URL", "SENTINEL_DATABASE_URL",
            "SENTINEL_INVESTIGATOR", "SENTINEL_AGENT_ADAPTER", "SENTINEL_CLAUDE_MODEL",
            "SENTINEL_SCORER", "SENTINEL_TOKEN")
DROP_ENV_PARTS = ("ANTHROPIC", "OPENAI", "API_KEY", "CLAUDE_CODE")
LIMITATIONS = [
    "One laptop, one run, small n; nearest-rank quantiles on so few samples are unstable.",
    "No confidence interval and no production, hosted or bank capacity claim.",
    "Deterministic adapters only: no provider latency is included in investigate.",
    "Client and server share the machine; the client's own CPU use is included.",
    "Resident memory is sampled, so short peaks between samples can be missed.",
]


# ---- statistics -----------------------------------------------------------------------------

def nearest_rank(values: list[float], q: float) -> float | None:
    """The nearest-rank q-quantile (rank ceil(q*n), 1-based) of values; None when empty."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(q * len(ordered)))
    return ordered[rank - 1]


def latency_summary(values: list[float]) -> dict:
    """n, p50, p95 and max in seconds; an empty sample is n/a, not 0."""
    if not values:
        return {"n": 0, "p50_s": "n/a", "p95_s": "n/a", "max_s": "n/a"}
    return {"n": len(values), "p50_s": round(nearest_rank(values, 0.50), 6),
            "p95_s": round(nearest_rank(values, 0.95), 6), "max_s": round(max(values), 6)}


def rate(count: int, seconds: float | None) -> float | str:
    """count per second over a window; n/a when the window is empty or absent."""
    if seconds is None or seconds <= 0:
        return "n/a"
    return round(count / seconds, 4)


def fraction(part: int, whole: int) -> float | str:
    return "n/a" if whole == 0 else round(part / whole, 4)


# ---- requests and outcomes ------------------------------------------------------------------

@dataclass
class Planned:
    """One request to make. `check` validates an expected-status body."""
    workload: str
    method: str
    path: str
    body: dict | None
    expected: int
    check: Callable[[object], bool] = field(repr=False, default=lambda body: True)
    target: str | None = None  # a case id, kept in private records only
    timeout: float = 30.0


@dataclass
class Record:
    phase: str
    workload: str
    concurrency: int
    index: int
    start_s: float
    end_s: float | None = None
    latency_s: float | None = None
    outcome: str = "unknown"
    code: str | None = "in_flight"
    status: int | None = None
    target: str | None = None
    detail: str | None = None


def classify_response(planned: Planned, status: int, body) -> tuple[str, str | None]:
    if status == planned.expected:
        try:
            ok = bool(planned.check(body))
        except (KeyError, TypeError, AttributeError, IndexError):
            ok = False
        return ("success", None) if ok else ("failed", "unexpected_body")
    code = body.get("error") if isinstance(body, dict) else None
    code = code if isinstance(code, str) else f"http_{status}"
    if code == "investigation_outcome_unknown":  # the server itself does not know
        return "unknown", code
    if 400 <= status < 500:
        return "refused", code
    return "failed", code


def classify_exception(error: BaseException) -> tuple[str, str]:
    """A request that provably never reached the server failed; anything after sending (a
    timeout, a broken connection or an unexpected error) is unknown: it may have written."""
    import httpx
    not_sent = (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout,
                httpx.UnsupportedProtocol)
    if isinstance(error, not_sent):
        return "failed", f"not_sent:{type(error).__name__}"
    return "unknown", f"client:{type(error).__name__}"


def perform(planned: Planned, record: Record, send, clock) -> None:
    """Make exactly one attempt (never a retry) and complete its record."""
    try:
        status, body = send(planned)
    except Exception as error:  # noqa: BLE001 - classified by type only, message dropped
        record.outcome, record.code = classify_exception(error)
    else:
        record.status = status
        record.outcome, record.code = classify_response(planned, status, body)
        if record.outcome == "success" and isinstance(body, dict):
            case = body.get("case")
            if isinstance(case, dict) and isinstance(case.get("state"), str):
                record.detail = case["state"]
    record.end_s = clock()
    record.latency_s = record.end_s - record.start_s


class Budget:
    """Shared hard caps for the measurement phase: a request count and a monotonic deadline.
    Only the start of new work is refused; nothing in flight is interrupted."""

    def __init__(self, max_requests: int, max_seconds: float, clock):
        self.max_requests, self.max_seconds, self.clock = max_requests, max_seconds, clock
        self.started = 0
        self.deadline: float | None = None
        self.lock = threading.Lock()

    def open(self) -> None:
        if self.deadline is None:
            self.deadline = self.clock() + self.max_seconds

    def try_start(self) -> str | None:
        """None when a request may start (and counts it); otherwise the cap reason."""
        with self.lock:
            self.open()
            if self.started >= self.max_requests:
                return "request_cap"
            if self.clock() >= self.deadline:
                return "duration_cap"
            self.started += 1
            return None

    def remaining(self) -> float:
        self.open()
        return max(0.0, self.deadline - self.clock())


def run_cell(workload: str, planned: list[Planned], concurrency: int, budget: Budget, send,
             clock=time.monotonic, phase: str = "measure",
             join_margin: float = JOIN_MARGIN_SECONDS) -> dict:
    """A closed loop of `concurrency` workers over `planned`. Every started request is kept,
    including one still in flight when the bounded wait ends (it stays unknown)."""
    records: list[Record] = []
    lock = threading.Lock()
    cursor = iter(range(len(planned)))
    stop: list[str] = []

    def worker() -> None:
        while True:
            with lock:
                index = next(cursor, None)
                if index is None:
                    return
                reason = budget.try_start()
                if reason is not None:
                    stop.append(reason)
                    return
                record = Record(phase, workload, concurrency, index, clock(),
                                target=planned[index].target)
                records.append(record)
            perform(planned[index], record, send, clock)

    threads = [threading.Thread(target=worker, daemon=True, name=f"perf01-{workload}-{i}")
               for i in range(concurrency)]
    for thread in threads:
        thread.start()
    timeout = max(p.timeout for p in planned) if planned else 0.0
    wait_until = time.monotonic() + budget.remaining() + timeout + join_margin
    for thread in threads:
        thread.join(max(0.0, wait_until - time.monotonic()))
    abandoned = sum(thread.is_alive() for thread in threads)
    with lock:  # a worker past the wait cannot start more: the cursor is closed here
        cursor = iter(())
        # A copy, so a worker that returns after the wait cannot change what is reported.
        snapshot = [r if r.end_s is not None else replace(r, code="client_wait_exceeded")
                    for r in records]
    ends = [r.end_s if r.end_s is not None else clock() for r in snapshot]
    window = (max(ends) - min(r.start_s for r in snapshot)) if snapshot else None
    reason = stop[0] if stop else ("completed" if len(snapshot) == len(planned) else "stopped")
    return {"workload": workload, "concurrency": concurrency, "planned": len(planned),
            "records": snapshot, "window_s": window, "stop_reason": reason,
            "abandoned_workers": abandoned}


def cell_summary(cell: dict) -> dict:
    records: list[Record] = cell["records"]
    outcomes = Counter(r.outcome for r in records)
    success = [r.latency_s for r in records if r.outcome == "success"]
    every = [r.latency_s for r in records if r.latency_s is not None]
    window = cell["window_s"]
    return {
        "workload": cell["workload"], "concurrency": cell["concurrency"],
        "planned": cell["planned"], "started": len(records),
        "not_started": cell["planned"] - len(records), "stop_reason": cell["stop_reason"],
        "outcomes": {k: outcomes.get(k, 0) for k in ("success", "refused", "failed", "unknown")},
        "status_codes": dict(sorted(Counter(str(r.status) if r.status is not None else "none"
                                            for r in records).items())),
        "service_codes": dict(sorted(Counter(r.code for r in records if r.code).items())),
        "latency_all_attempts": latency_summary(every),
        "latency_unfinished": sum(r.latency_s is None for r in records),
        "latency_success": latency_summary(success),
        "window_s": round(window, 6) if window is not None else "n/a",
        "throughput_attempted_per_s": rate(len(records), window),
        "throughput_success_per_s": rate(len(success), window),
        "success_fraction": fraction(len(success), len(records)),
        "abandoned_workers": cell["abandoned_workers"],
    }


def phase_summary(records: list[Record]) -> dict:
    outcomes = Counter(r.outcome for r in records)
    return {"requests": len(records),
            "outcomes": {k: outcomes.get(k, 0) for k in ("success", "refused", "failed",
                                                          "unknown")},
            "status_codes": dict(sorted(Counter(str(r.status) if r.status is not None
                                                else "none" for r in records).items())),
            "service_codes": dict(sorted(Counter(r.code for r in records if r.code).items())),
            "latency_all_attempts": latency_summary(
                [r.latency_s for r in records if r.latency_s is not None])}


# ---- the synthetic plan ---------------------------------------------------------------------

class Plan:
    """Deterministic identifiers from the seed; only occurred_at follows the wall clock (it
    must not be in the server's future)."""

    def __init__(self, seed: int):
        self.seed, self.rng, self.count = seed, random.Random(seed), 0

    def account(self) -> str:
        return str(uuid.UUID(int=self.rng.getrandbits(128), version=4))

    def transaction(self, label: str, minor: int) -> dict:
        self.count += 1
        occurred = datetime.now(timezone.utc) - timedelta(minutes=5)
        return {"external_id": f"perf01-{self.seed}-{label}-{self.count}",
                "account_id": self.account(), "direction": "debit",
                "amount": {"currency": "USD", "minor_units": minor, "currency_exponent": 2},
                "occurred_at": occurred.isoformat()}


def ingest_request(plan: Plan, label: str, workload: str = "ingest") -> Planned:
    body = plan.transaction(label, SMALL_MINOR)
    return Planned(workload, "POST", "/v1/transactions", body, 201,
                   lambda b, ext=body["external_id"]: b["transaction"]["external_id"] == ext
                   and b["replayed"] is False, timeout=TIMEOUT["ingest"])


def alert_request(plan: Plan, label: str) -> Planned:
    body = plan.transaction(label, ALERT_MINOR)
    return Planned("setup", "POST", "/v1/transactions", body, 201,
                   lambda b: b["case"]["id"] is not None and b["replayed"] is False,
                   timeout=TIMEOUT["setup"])


def read_request(case: dict) -> Planned:
    return Planned("read", "GET", f"/v1/cases/{case['id']}", None, 200,
                   lambda b, c=case["id"]: b["case"]["id"] == c, target=case["id"],
                   timeout=TIMEOUT["read"])


def investigate_request(case: dict) -> Planned:
    return Planned("investigate", "POST", f"/v1/cases/{case['id']}/investigations",
                   {"expected_revision": case["revision"]}, 200,
                   lambda b, c=case["id"]: b["case"]["id"] == c, target=case["id"],
                   timeout=TIMEOUT["investigate"])


def planned_setup_requests(args) -> int:
    """Health, session and scorer checks, alert cases and warm-ups."""
    n, cells = args.requests, len(args.concurrency)
    count = 3 + args.warmup * len(args.workloads)
    if "read" in args.workloads:
        count += max(1, n)
    if "investigate" in args.workloads:
        count += n * cells + args.warmup
    return count


# ---- resident memory on verified owned processes ---------------------------------------------

def _windows_resident(pid: int) -> int | None:
    import ctypes
    from ctypes import wintypes

    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                    *[(name, ctypes.c_size_t) for name in (
                        "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                        "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                        "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]]
    k32 = ctypes.windll.kernel32
    k32.OpenProcess.restype = wintypes.HANDLE
    handle = k32.OpenProcess(0x1000 | 0x0010, False, pid) or k32.OpenProcess(0x1000, False, pid)
    if not handle:
        return None
    try:
        counters = Counters()
        counters.cb = ctypes.sizeof(Counters)
        if not k32.K32GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            return None
        return int(counters.WorkingSetSize)
    finally:
        k32.CloseHandle(handle)


def _posix_resident(pid: int) -> int | None:
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        return None
    return None


def resident_bytes(expected: dict, identify=None, read=None) -> int | None:
    """Resident bytes of exactly the process `expected` names (pid, start, exe), read only
    while its identity matches before and after the read; otherwise None (unknown)."""
    identify = identify or local_stack.identity
    read = read or (_windows_resident if os.name == "nt" else _posix_resident)
    try:
        if identify(expected["pid"]) != expected:
            return None
        value = read(expected["pid"])
        if identify(expected["pid"]) != expected:
            return None
    except local_stack.StackError:
        return None
    return value


class Sampler:
    """Samples resident memory (Windows working set; Linux VmRSS) at a fixed interval for:
    `api` - the recorded API launcher and listener identities; `postgres` - the verified
    postmaster plus descendants created no earlier than it. Sums double-count shared pages;
    nothing else on the machine is sampled. Unreadable processes are counted, not guessed."""

    def __init__(self, scopes: dict[str, Callable[[], list[dict]]], interval: float,
                 reader=resident_bytes):
        self.scopes, self.interval, self.reader = scopes, interval, reader
        self.stats = {name: {"samples": 0, "peak_sum_bytes": None, "max_processes": 0,
                             "unreadable_reads": 0} for name in scopes}
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.loop, daemon=True, name="perf01-rss")

    def sample(self) -> None:
        for name, members in self.scopes.items():
            stats = self.stats[name]
            try:
                identities = members()
            except local_stack.StackError:
                identities = []
            values = [self.reader(identity) for identity in identities]
            readable = [v for v in values if v is not None]
            stats["unreadable_reads"] += len(values) - len(readable)
            if readable:
                stats["samples"] += 1
                stats["max_processes"] = max(stats["max_processes"], len(readable))
                total = sum(readable)
                if stats["peak_sum_bytes"] is None or total > stats["peak_sum_bytes"]:
                    stats["peak_sum_bytes"] = total

    def loop(self) -> None:
        while not self.stop_event.is_set():
            self.sample()
            self.stop_event.wait(self.interval)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> dict:
        self.stop_event.set()
        if self.thread.ident is not None:  # started
            self.thread.join(self.interval + 30)
        return {"metric": "Windows working set" if os.name == "nt" else "Linux VmRSS",
                "interval_s": self.interval, "window": "measurement phase only",
                "scopes": {name: {**s, "peak_sum_mib": round(s["peak_sum_bytes"] / 2**20, 1)
                                  if s["peak_sum_bytes"] is not None else "unknown"}
                           for name, s in self.stats.items()}}


def postgres_members(root: dict) -> Callable[[], list[dict]]:
    def members() -> list[dict]:
        found = [root]
        for pid in sorted(local_stack.descendants(root["pid"])):
            try:
                child = local_stack.identity(pid)
            except local_stack.StackError:
                child = {"pid": pid, "start": None, "exe": None}  # counted as unreadable
            if child and (child["start"] is None or child["start"] >= root["start"]):
                found.append(child)
        return found
    return members


# ---- provenance (non-secret only) ------------------------------------------------------------

def _memory_total() -> dict:
    if os.name == "nt":
        import ctypes

        class Status(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        *[(n, ctypes.c_ulonglong) for n in (
                            "ullTotalPhys", "ullAvailPhys", "ullTotalPageFile",
                            "ullAvailPageFile", "ullTotalVirtual", "ullAvailVirtual",
                            "ullAvailExtendedVirtual")]]
        status = Status()
        status.dwLength = ctypes.sizeof(Status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return {"total_physical_gib": round(status.ullTotalPhys / 2**30, 1),
                    "available_at_start_gib": round(status.ullAvailPhys / 2**30, 1)}
        return {"total_physical_gib": "unknown", "available_at_start_gib": "unknown"}
    try:
        info = {line.split(":")[0]: int(line.split()[1]) for line in
                Path("/proc/meminfo").read_text().splitlines() if line.split()[1:2]}
        return {"total_physical_gib": round(info["MemTotal"] / 2**20, 1),
                "available_at_start_gib": round(info["MemAvailable"] / 2**20, 1)}
    except (OSError, KeyError, ValueError, IndexError):
        return {"total_physical_gib": "unknown", "available_at_start_gib": "unknown"}


def _run_quiet(argv: list[str]) -> str | None:
    try:
        done = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, timeout=30,
                              stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def provenance() -> dict:
    """Source, platform and resource facts. No host name, user, path, command line,
    environment or URL."""
    from sentinel import devdb
    status = _run_quiet(["git", "status", "--porcelain", "--untracked-files=no"])
    pg_bin = devdb.find_pg_bin()
    pg = _run_quiet([str(pg_bin / "postgres"), "-V"]) if pg_bin else None
    return {
        "source_commit": _run_quiet(["git", "rev-parse", "HEAD"]) or "unknown",
        "tracked_changes": "unknown" if status is None else bool(status),
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "os": platform.system(), "os_release": platform.release(),
        "machine": platform.machine(), "processor": platform.processor() or "unknown",
        "logical_cpus": os.cpu_count() or "unknown", **_memory_total(),
        "postgres": pg or "unknown",
        "clock": "time.monotonic (seconds)",
    }


# ---- the owned stack -------------------------------------------------------------------------

def child_environment(run_dir: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in DROP_ENV
           and not any(part in k.upper() for part in DROP_ENV_PARTS)}
    env.update(SENTINEL_LIVE_CLAUDE="0",
               SENTINEL_CLAUDE_EXECUTABLE=str(run_dir / "no-such-claude"))
    return env


class OwnedStack:
    """The accepted helper as a subprocess on this run's own state directory and ports."""

    def __init__(self, run_dir: Path, port: int, db_port: int, investigator: str,
                 runner=subprocess.run):
        self.run_dir, self.state = run_dir, run_dir / "stack"
        self.port, self.db_port, self.investigator = port, db_port, investigator
        self.env, self.runner = child_environment(run_dir), runner
        self.log: list[dict] = []  # private: return codes and output tails
        self.api_record: dict | None = None
        self.postmaster: dict | None = None
        # Port states before anything starts: a listener that was already foreign belongs to
        # someone else and is left alone; it is never mistaken for one of ours.
        self.ports_before = {"api_port": local_stack.port_state(port, None),
                             "db_port": local_stack.port_state(db_port, None)}

    def helper(self, *argv: str, timeout: float) -> int:
        command = [sys.executable, str(ROOT / "scripts" / "local_stack.py"), "--state-dir",
                   str(self.state), "--port", str(self.port), "--db-port", str(self.db_port),
                   *argv]
        try:
            done = self.runner(command, cwd=ROOT, env=self.env, capture_output=True,
                               text=True, timeout=timeout, stdin=subprocess.DEVNULL)
            code, out = done.returncode, (done.stdout or "") + (done.stderr or "")
        except subprocess.TimeoutExpired:
            code, out = -1, "helper timed out (its own recovery state is kept)"
        self.log.append({"command": argv[0], "returncode": code, "output_tail": out[-1500:]})
        return code

    def up(self) -> int:
        argv = ["up", "--investigator", self.investigator, "--scorer", "rule"]
        if self.investigator == "three-role":
            argv += ["--agent-adapter", "deterministic"]
        code = self.helper(*argv, timeout=STACK_UP_SECONDS)
        if code == 0:
            stack = local_stack.Stack(self.state)
            data = stack.load()
            self.api_record = data["api"]
            if local_stack.database_state(stack, data) == "owned":
                cluster = local_stack.cluster(stack, data["database"]["port"])
                pid = int((cluster.data_dir / "postmaster.pid").read_text().splitlines()[0])
                self.postmaster = local_stack.identity(pid)
        return code

    def token(self) -> str:
        return json.loads((self.state / "session.json").read_text())["token"]

    def api_members(self) -> list[dict]:
        record = self.api_record or {}
        found = [{k: record[k] for k in ("pid", "start", "exe")}] if record.get("pid") else []
        listener = record.get("listener")
        if listener and listener.get("pid") != record.get("pid"):
            found.append({k: listener[k] for k in ("pid", "start", "exe")})
        return found

    def down(self) -> dict:
        """The helper's own down, then independent evidence that our processes are gone and
        each port is free, or still held by the foreign listener that held it before we
        started. Never kills anything itself; any doubt is reported as unverified."""
        try:
            code = self.helper("down", timeout=STACK_DOWN_SECONDS) \
                if (self.state / local_stack.MARKER).exists() else NOT_NEEDED
            api = [local_stack.classify(m) for m in self.api_members()]
            postmaster = local_stack.classify(self.postmaster) if self.postmaster else "none"
            ports = {"api_port": local_stack.port_state(self.port, None),
                     "db_port": local_stack.port_state(self.db_port, None)}
        except Exception as error:  # noqa: BLE001 - reported, never resolved by force
            return {"verified": False, "error": type(error).__name__}
        released = all(state == "free" or state == self.ports_before[name] == "foreign"
                       for name, state in ports.items())
        verified = code in (0, NOT_NEEDED) and all(state == "gone" for state in api) and \
            postmaster in ("gone", "none") and released
        return {"verified": verified, "helper_down_exit": code, "api_processes": api,
                "postmaster": postmaster, **ports, "ports_before": self.ports_before}


def http_client(port: int, token: str, concurrency: int):
    import httpx
    return httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False,
                        headers={"Authorization": f"Bearer {token}"},
                        limits=httpx.Limits(max_connections=max(4, concurrency)))


def http_sender(client) -> Callable[[Planned], tuple[int, object]]:
    def send(planned: Planned) -> tuple[int, object]:
        response = client.request(planned.method, planned.path, json=planned.body,
                                  timeout=planned.timeout)
        try:
            body = response.json()
        except ValueError:
            body = None
        return response.status_code, body
    return send


# ---- phases ----------------------------------------------------------------------------------

class SetupFailed(RuntimeError):
    pass


def sequential(phase: str, workload: str, planned: list[Planned], send, records: list,
               cap: int, clock=time.monotonic) -> list[Record]:
    """Setup/verification requests: one at a time, each counted, hard-capped."""
    done = []
    for index, item in enumerate(planned):
        if len(records) >= cap:
            raise SetupFailed(f"{phase} request cap {cap} reached")
        record = Record(phase, workload, 1, index, clock(), target=item.target)
        records.append(record)
        perform(item, record, send, clock)
        done.append(record)
    return done


def fetch(send, records: list, phase: str, path: str, cap: int, clock=time.monotonic):
    """One counted GET whose body is needed (setup checks and verification)."""
    if len(records) >= cap:
        raise SetupFailed(f"{phase} request cap {cap} reached")
    holder: dict = {}

    def capture(planned):
        status, body = send(planned)
        holder["body"] = body
        return status, body
    record = Record(phase, phase, 1, len(records), clock())
    records.append(record)
    perform(Planned(phase, "GET", path, None, 200, timeout=TIMEOUT[phase]), record, capture,
            clock)
    if record.outcome != "success":
        raise SetupFailed(f"{phase} GET failed ({record.outcome} {record.code})")
    return holder["body"]


def create_cases(plan: Plan, label: str, count: int, send, records: list) -> list[dict]:
    holder: list[dict] = []

    def capture(planned):
        status, body = send(planned)
        if status == 201 and isinstance(body, dict) and isinstance(body.get("case"), dict):
            holder.append({"id": body["case"]["id"], "revision": body["case"]["revision"]})
        return status, body
    done = sequential("setup", "alert-case", [alert_request(plan, label) for _ in range(count)],
                      capture, records, MAX_SETUP_REQUESTS)
    if any(r.outcome != "success" for r in done) or len(holder) != count:
        raise SetupFailed("alert case preparation did not succeed for every request")
    return holder


def verify(send, measured: list[Record], counted: list[Record]) -> dict:
    """Read back every scoped case; approvals and simulated actions must stay 0."""
    cases, cursor = [], None
    for _ in range(10):
        path = "/v1/cases?limit=100" + (f"&cursor={quote(cursor, safe='')}" if cursor else "")
        page = fetch(send, counted, "verify", path, MAX_VERIFY_REQUESTS)
        cases += [item["id"] for item in page["items"]]
        cursor = page.get("next_cursor")
        if not cursor:
            break
    details = {case: fetch(send, counted, "verify", f"/v1/cases/{case}", MAX_VERIFY_REQUESTS)
               for case in cases}
    overview = fetch(send, counted, "verify", "/v1/overview", MAX_VERIFY_REQUESTS)
    intents = [i for d in details.values() for i in d["action_intents"]]
    unknown = [r for r in measured if r.outcome == "unknown"]
    reconciled = []
    for record in unknown:
        if record.workload == "investigate" and record.target in details:
            detail = details[record.target]
            reconciled.append({"workload": "investigate", "outcome": "unknown (kept)",
                               "observed_case_state": detail["case"]["state"],
                               "observed_agent_runs": len(detail["agent_runs"])})
        else:
            reconciled.append({"workload": record.workload, "outcome": "unknown (kept)",
                               "observed": "not reconcilable per request with read-only API"})
    return {"scoped_cases": len(cases), "cases_listing_complete": cursor is None,
            "cases_by_state": overview["cases_by_state"],
            "transactions": overview["transactions"], "alerts": overview["alerts"],
            "approvals": sum(i.get("approval") is not None for i in intents),
            "simulated_actions_on_cases": sum(i.get("action") is not None for i in intents),
            "simulated_actions_overview": overview["simulated_actions"],
            "unknown_reconciliation": reconciled}


def new_result() -> dict:
    """Filled as the run proceeds, so a failure keeps every record made before it."""
    return {"setup": [], "warmup": [], "verification": [], "cells": [], "measurement_s": None,
            "budget": None, "memory": None, "checked": None}


def benchmark(args, stack: OwnedStack, result: dict, clock=time.monotonic,
              sender=None) -> None:
    """Setup, measurement and verification against the already started owned stack.
    `sender` replaces the HTTP client in tests only."""
    setup, warmup = result["setup"], result["warmup"]
    plan = Plan(args.seed)
    client = None if sender else http_client(stack.port, stack.token(), max(args.concurrency))
    try:
        send = sender or http_sender(client)
        health = fetch(send, setup, "setup", "/healthz", MAX_SETUP_REQUESTS)
        if health.get("investigator") != HEALTH_NAME[args.investigator]:
            raise SetupFailed("the API does not report the requested investigator")
        scoring = fetch(send, setup, "setup", "/v1/scoring", MAX_SETUP_REQUESTS)
        if scoring.get("mode") != "rule":
            raise SetupFailed("the API is not in rule scoring mode")
        fetch(send, setup, "setup", "/v1/session", MAX_SETUP_REQUESTS)
        n, cells = args.requests, args.concurrency
        read_cases = create_cases(plan, "read-case", max(1, n), send, setup) \
            if "read" in args.workloads else []
        fresh = create_cases(plan, "investigate-case", n * len(cells) + args.warmup, send,
                             setup) if "investigate" in args.workloads else []
        warm_cases, fresh = fresh[:args.warmup], fresh[args.warmup:]
        for workload in args.workloads:
            if workload == "ingest":
                items = [ingest_request(plan, "warmup") for _ in range(args.warmup)]
            elif workload == "read":
                items = [read_request(read_cases[i % len(read_cases)])
                         for i in range(args.warmup)]
            else:
                items = [investigate_request(c) for c in warm_cases]
            sequential("warmup", workload, items, send, warmup, MAX_SETUP_REQUESTS)

        budget = result["budget"] = Budget(args.max_requests, args.max_seconds, clock)
        sampler = Sampler({"api": stack.api_members,
                           **({"postgres": postgres_members(stack.postmaster)}
                              if stack.postmaster else {})}, args.rss_interval)
        sampler.start()
        phase_start = clock()
        try:
            for workload in args.workloads:
                for position, concurrency in enumerate(cells):
                    if workload == "ingest":
                        items = [ingest_request(plan, f"c{concurrency}") for _ in range(n)]
                    elif workload == "read":
                        items = [read_request(read_cases[i % len(read_cases)])
                                 for i in range(n)]
                    else:
                        items = [investigate_request(c)
                                 for c in fresh[position * n:(position + 1) * n]]
                    result["cells"].append(run_cell(workload, items, concurrency, budget,
                                                    send, clock))
        finally:
            result["measurement_s"] = clock() - phase_start
            result["memory"] = sampler.stop()
        measured = [r for cell in result["cells"] for r in cell["records"]]
        checked = result["checked"] = verify(send, measured, result["verification"])
    finally:
        if client is not None:
            client.close()
    known = sum(r.outcome == "success" and r.workload == "alert-case" for r in setup) + \
        sum(r.outcome == "success" and r.workload == "ingest" for r in warmup + measured)
    checked["ingest_reconciliation"] = {
        "known_written": known, "overview_transactions": checked["transactions"],
        "unknown_ingest_requests": sum(r.outcome == "unknown" and r.workload == "ingest"
                                       for r in warmup + measured),
        "unaccounted_written": checked["transactions"] - known}


# ---- command line ----------------------------------------------------------------------------

def bounded_int(low: int, high: int):
    def parse(text: str) -> int:
        value = int(text)
        if not low <= value <= high:
            raise argparse.ArgumentTypeError(f"must be between {low} and {high}")
        return value
    return parse


def bounded_float(low: float, high: float):
    def parse(text: str) -> float:
        value = float(text)
        if not low <= value <= high:
            raise argparse.ArgumentTypeError(f"must be between {low} and {high}")
        return value
    return parse


def concurrency_list(text: str) -> list[int]:
    values = [int(part) for part in text.split(",") if part.strip()]
    if not values or len(set(values)) != len(values) or \
            any(not 1 <= v <= MAX_CONCURRENCY for v in values):
        raise argparse.ArgumentTypeError(f"distinct values between 1 and {MAX_CONCURRENCY}")
    return values


def workload_list(text: str) -> list[str]:
    values = [part.strip() for part in text.split(",") if part.strip()]
    if not values or len(set(values)) != len(values) or any(v not in WORKLOADS for v in values):
        raise argparse.ArgumentTypeError(f"distinct values from {', '.join(WORKLOADS)}")
    return values


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--requests", type=bounded_int(1, MAX_REQUESTS_PER_CELL), default=12,
                        help="measured requests per workload and concurrency")
    parser.add_argument("--concurrency", type=concurrency_list, default=[1, 2, 4])
    parser.add_argument("--workloads", type=workload_list, default=list(WORKLOADS))
    parser.add_argument("--max-requests", type=bounded_int(1, MAX_MEASURED_REQUESTS),
                        default=108, help="hard cap on measured requests (all cells)")
    parser.add_argument("--max-seconds", type=bounded_float(1, MAX_MEASURE_SECONDS),
                        default=300.0, help="hard cap on active measurement time")
    parser.add_argument("--warmup", type=bounded_int(0, MAX_WARMUP), default=2)
    parser.add_argument("--seed", type=int, default=20261106)
    parser.add_argument("--investigator", choices=INVESTIGATORS, default="three-role",
                        help="adapter is always deterministic")
    parser.add_argument("--rss-interval", type=bounded_float(0.1, 5.0), default=0.5)
    parser.add_argument("--run-dir", type=Path, default=None,
                        help="a NEW directory (default .agent/perf01/<timestamp>)")
    parser.add_argument("--port", type=bounded_int(1024, 65535), default=None,
                        help="loopback API port (default: a free one)")
    parser.add_argument("--db-port", type=bounded_int(1024, 65535), default=None)
    args = parser.parse_args(argv)
    if planned_setup_requests(args) > MAX_SETUP_REQUESTS:
        parser.error(f"the plan needs more than {MAX_SETUP_REQUESTS} setup requests")
    return args


def relative(path: Path) -> str:
    try:
        return Path(os.path.relpath(path.resolve(), ROOT)).as_posix() \
            if path.resolve().is_relative_to(ROOT) else "(outside the repository)"
    except ValueError:
        return "(outside the repository)"


def summarize(args, result: dict | None, stack_info: dict, cleanup: dict, run_dir: Path,
              error: str | None) -> dict:
    planned_measured = len(args.workloads) * len(args.concurrency) * args.requests
    summary = {
        "benchmark": "PERF01 local capacity", "schema": SCHEMA, "error": error,
        "config": {"workloads": args.workloads, "concurrency": args.concurrency,
                   "requests_per_cell": args.requests, "warmup_per_workload": args.warmup,
                   "seed": args.seed, "scorer": "rule", "investigator": args.investigator,
                   "agent_adapter": "deterministic" if args.investigator == "three-role"
                   else None, "planned_measured_requests": planned_measured,
                   "cap_measured_requests": args.max_requests,
                   "cap_measurement_seconds": args.max_seconds,
                   "client_timeouts_s": TIMEOUT, "retries": 0, "server_limits": "unchanged",
                   "target": "owned loopback API only", "run_dir": relative(run_dir)},
        "provenance": provenance(),
        "stack": stack_info,
        "definitions": {
            "latency": "monotonic seconds from just before the request is sent until its "
                       "response is classified; all-attempt includes refused/failed/unknown",
            "quantile": "nearest-rank: value at rank ceil(q*n) of the sorted sample",
            "cell_window": "first request start to last request end in the cell (monotonic)",
            "throughput": "started (attempted) or successful requests / cell window",
            "empty": "n/a when the denominator or sample is empty"},
        "limitations": LIMITATIONS, "cleanup": cleanup,
    }
    if result is not None:
        started = result["budget"].started if result["budget"] else 0
        seconds = result["measurement_s"]
        summary.update({
            "setup": phase_summary(result["setup"]), "warmup": phase_summary(result["warmup"]),
            "measurement": {"active_seconds": round(seconds, 6) if seconds is not None
                            else "n/a", "started": started,
                            "not_started": planned_measured - started,
                            "cells": [cell_summary(cell) for cell in result["cells"]]},
            "verification": {**phase_summary(result["verification"]),
                             **(result["checked"] or {"completed": False})},
            "resident_memory": result["memory"] or "not sampled"})
    return summary


def write_private(run_dir: Path, summary: dict, result: dict | None, stack: OwnedStack) -> None:
    raw = {"helper": stack.log}
    if result is not None:
        raw.update({phase: [asdict(r) for r in result[phase]]
                    for phase in ("setup", "warmup", "verification")})
        raw["measure"] = [asdict(r) for cell in result["cells"] for r in cell["records"]]
    for name, document in (("records.json", raw), ("summary.json", summary)):
        (run_dir / name).write_text(json.dumps(document, indent=2, sort_keys=True,
                                               default=str) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None, stack_factory=OwnedStack) -> int:
    args = parse_args(argv)
    import sentinel
    if not Path(sentinel.__file__).resolve().is_relative_to(ROOT / "src"):
        print("error: sentinel is not imported from this checkout; refused", file=sys.stderr)
        return 3
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.run_dir or DEFAULT_RUN_ROOT / f"{stamp}-{args.seed}"
    if run_dir.exists():  # a fresh, test-owned directory only; nothing existing is touched
        print("error: the run directory already exists; refused (nothing was changed)",
              file=sys.stderr)
        return 3
    run_dir.mkdir(parents=True)
    from sentinel import devdb
    stack = stack_factory(run_dir, args.port or devdb.free_port(),
                          args.db_port or devdb.free_port(), args.investigator)
    result, error, stack_info = None, None, {}
    try:  # every exit path below reaches the helper's own down
        started = time.monotonic()
        code = stack.up()
        stack_info = {"helper_up_exit": code,
                      "helper_up_seconds": round(time.monotonic() - started, 3)}
        if code != 0:
            error = "the owned stack did not start (the helper refused or failed)"
        else:
            record = stack.api_record or {}
            stack_info.update({"investigator": record.get("investigator"),
                               "adapter": record.get("adapter"),
                               "claude_model": record.get("claude_model"),
                               "scorer": record.get("scorer"),
                               "postmaster_verified": stack.postmaster is not None})
            if record.get("claude_model") or record.get("adapter") == "claude-cli":
                error = "the stack reports a live configuration; refused"
            elif (record.get("investigator"), record.get("adapter")) != (
                    args.investigator, "deterministic" if args.investigator == "three-role"
                    else None):
                error = "the stack does not report the requested configuration; refused"
            else:
                result = new_result()
                benchmark(args, stack, result)
                checked = result["checked"]
                if checked["approvals"] or checked["simulated_actions_on_cases"] or \
                        checked["simulated_actions_overview"]:
                    error = "approvals or simulated actions were observed (expected 0)"
    except SetupFailed as failure:
        error = f"setup or verification failed: {failure}"
    except KeyboardInterrupt:
        error = "interrupted"
    except Exception as failure:  # noqa: BLE001 - type only; a message may carry a URL
        error = f"unexpected {type(failure).__name__}"
    finally:
        cleanup = stack.down()
    summary = summarize(args, result, stack_info, cleanup, run_dir, error)
    write_private(run_dir, summary, result, stack)
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not cleanup["verified"]:
        print("error: cleanup could not be verified; the helper's recovery state is kept. "
              "Retry: uv run --locked python scripts/local_stack.py --state-dir "
              f"{relative(stack.state)} down", file=sys.stderr)
        return 2
    return 1 if error else 0


if __name__ == "__main__":
    raise SystemExit(main())
