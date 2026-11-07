"""AN01-M1: staged report-query measurement controller (prototype; decisions r3.2 section 8).

    uv run --locked python scripts/benchmark_reports.py plan [--profile tiny|full]
    uv run --locked python scripts/benchmark_reports.py init --run-dir DIR --profile tiny
    uv run --locked python scripts/benchmark_reports.py stage --run-dir DIR --stage S1
        [--selection FILE] [--authorized-full-size]
    uv run --locked python scripts/benchmark_reports.py select --rule common-index|n-star
        --record FILE --record FILE --out FILE
    uv run --locked python scripts/benchmark_reports.py report --record FILE... --out FILE
    uv run --locked python scripts/benchmark_reports.py recover --run-dir DIR
    uv run --locked python scripts/benchmark_reports.py cleanup --run-dir DIR
        [--delete-owned-data]

What this is: the full pre-registered AN01-M1 grid (phases A, B, B-guard, C, D, E; stages
S1-S9; rules 1-7) coded once, executable on a `tiny` synthetic profile for plumbing proof.
The `full` profile is defined but refuses to run without --authorized-full-size, which no
current assignment grants. Tiny results are plumbing evidence only, never a limit.

Each platform stage is one command supervised by THIS process on one monotonic clock from
command start (accepted constants, decisions section 8.4): no new work after 2300 s, an
independent whole-stage work/wait deadline at 2350 s that also covers blocked connection,
COPY, index builds and EXPLAIN, a 300 s cleanup reserve to a controller deadline of 2650 s,
inside the unchanged 2700 s outer command cap. The worker is a separate process; at the
deadline it is stopped only if its recorded identity (pid, creation time, executable; the
accepted scripts/local_stack.py mechanism) still matches, and clusters are stopped only when
local_stack.database_state verifies them as this run's. A bounded wait is never reported as
proof that something stopped: unconfirmed cleanup exits nonzero, keeps the recovery state and
the run lock, and refuses further stages until `recover` confirms.

Ownership: the run directory carries a marker; each cluster is a local_stack-owned
directory inside it. The schema owner only provisions data, schema, index variants and
data scopes; report SQL and EXPLAIN run as a least-privilege runtime role (roles.grant_runtime)
in REPEATABLE READ READ ONLY transactions that always end with ROLLBACK. No api_sessions row,
capability, route or HTTP call is created; HTTP outcomes are prototype classifications.

Checkpoints record every statement, setup and source digest at `init`; a stage refuses to
start if any changed (no statement may change after its measured digest is recorded). There
is no automatic resume and no retry: a stage runs once, a started cell is never re-run, and
unstarted cells are listed as not run. Public records hold no DSN, token, user name, local
path, raw driver exception or model data; private logs stay in the run directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import secrets
import shutil
import statistics
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import local_stack  # noqa: E402  (accepted, unchanged: identity, ownership, cluster state)
import report_benchmark_support as rb  # noqa: E402

UTC = timezone.utc
SCHEMA = 1
MARKER = ".an01-m1-run"
RUNTIME_ROLE = "an01_m1_runtime"
SHADOW_ROLE = "an01_m1_shadow_reader"
DATABASE = "sentinel"
SOURCES = ("scripts/benchmark_reports.py", "scripts/report_benchmark_support.py",
           "docs/analytics/AN01-zone-table.json")
EXPLAIN_PREFIX = "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) "
EXIT = {"ok": 0, "failed": 1, "refused": 2, "incomplete": 3, "unconfirmed": 4}


# ---- supervisor budgets ---------------------------------------------------------------------

@dataclass(frozen=True)
class SupervisorBudget:
    no_new_work_s: float
    work_deadline_s: float
    cleanup_reserve_s: float
    controller_deadline_s: float
    outer_cap_s: float
    label: str

    def check(self) -> None:
        if not (0 < self.no_new_work_s < self.work_deadline_s
                and abs(self.work_deadline_s + self.cleanup_reserve_s
                        - self.controller_deadline_s) < 1e-9
                and self.controller_deadline_s < self.outer_cap_s):
            raise ValueError("supervisor budget invariants do not hold")


ACCEPTED_BUDGET = SupervisorBudget(2300, 2350, 300, 2650, 2700, "accepted")
ACCEPTED_BUDGET.check()
SETUP_DEADLINE_S = 900          # accepted: setup counts toward the same stage clock


def smaller_budget(values: list[float], label: str) -> SupervisorBudget:
    """An explicitly labelled SMALLER test/smoke budget; never larger than accepted."""
    budget = SupervisorBudget(*values, label=label)
    budget.check()
    accepted = asdict(ACCEPTED_BUDGET)
    for key, value in asdict(budget).items():
        if key != "label" and value > accepted[key]:
            raise ValueError(f"{key} exceeds the accepted value")
    return budget


TINY_BUDGET = smaller_budget([240, 270, 60, 330, 340], "tiny-smoke (smaller than accepted)")


# ---- profiles and the pre-registered grid --------------------------------------------------

@dataclass(frozen=True)
class Profile:
    name: str
    sizes: tuple[int, ...]
    cap: int
    phase_a_size: int
    background_tenants: int
    background_rows: int
    seed: int
    min_free_bytes: int
    max_cluster_bytes: int
    budget: SupervisorBudget

    @property
    def guard_size(self) -> int:
        return self.cap + 1

    def d1_rows(self) -> int:
        return sum(self.sizes) + self.guard_size

    def d2_rows(self) -> int:
        return self.d1_rows() + self.background_rows


GB = 1_000_000_000
PROFILES = {
    "full": Profile("full", (10_000, 50_000, 100_000, 200_000), 200_000, 200_000, 8, 800_000,
                    20261107, 8 * GB, 4 * GB, ACCEPTED_BUDGET),
    "tiny": Profile("tiny", (20, 40, 60, 80), 80, 80, 8, 160, 20261107, 200_000_000,
                    300_000_000, TINY_BUDGET),
}
VARIANTS = ("A", "B", "C")
FILTERS = ("base", "asof90", "single_currency")
C_BUDGETS = {"C1": ((300, 5), (349, 5)), "C2": ((400, 5), (700, 5), (1250, 5)),
             "C3": ((400, 3), (700, 3), (1250, 3)), "C4": ((1250, 3),)}
STAGES = ("S1", "S2", "S3", "S4", "S5a", "S5b", "S6", "S7", "S8", "S9")
PLATFORM_STAGES = ("S1", "S2", "S4", "S5a", "S5b", "S6", "S8")
OFFLINE_STAGES = ("S3", "S7", "S9")


@dataclass(frozen=True)
class Cell:
    id: str
    phase: str
    stage: str
    dataset: str
    op: str
    size: int
    filter: str = "base"
    variant: str | None = None
    warmup: int = 1
    timed: int = 5
    explain: bool = True
    budget_ms: int = rb.MEASUREMENT_B_MS
    expect: str = "ok"
    mandatory: bool = True


def grid(profile: Profile, n_star: int | None = None) -> list[Cell]:
    cells = []
    for variant in VARIANTS:
        for op in rb.OPERATIONS:
            cells.append(Cell(f"A:{variant}:{op}", "A", "S2", "D2", op, profile.phase_a_size,
                              variant=variant))
    for stage, dataset in (("S5a", "D1"), ("S5b", "D2")):
        for size in profile.sizes:
            for op in rb.OPERATIONS:
                for filt in (FILTERS if op != "workload" else ("base",)):
                    cells.append(Cell(f"B:{dataset}:{size}:{op}:{filt}", "B", stage, dataset,
                                      op, size, filt))
    for op in rb.TRANSACTION_OPS:
        cells.append(Cell(f"BG:{op}", "BG", "S5b", "D2", op, profile.guard_size, warmup=0,
                          explain=False, expect="too_large"))
    for control, budgets in C_BUDGETS.items():
        for budget_ms, runs in budgets:
            cells.append(Cell(f"{control}:{budget_ms}", "C", "S6", "D2", "totals",
                              profile.phase_a_size, warmup=0, timed=runs, explain=False,
                              budget_ms=budget_ms, expect=control))
    cells.append(Cell("C5", "C", "S6", "D2", "totals", profile.phase_a_size, warmup=0,
                      timed=4, explain=False, expect="C5"))
    cells.append(Cell("D", "D", "S6", "D2", "quality+drill_first", profile.phase_a_size,
                      warmup=0, timed=20, explain=False, mandatory=False))
    for design in ("json", "cols"):
        for op in rb.SHADOW_REGISTRY_OPS:
            cells.append(Cell(f"E:{design}:{op}", "E", "S8", "D2",
                              op if design == "json" else op + "_cols",
                              n_star or 0, mandatory=False))
    return cells


def grid_totals(cells: list[Cell]) -> dict:
    out = {}
    for c in cells:
        p = out.setdefault(c.phase, {"cells": 0, "operation_runs": 0, "explain_passes": 0})
        p["cells"] += 1
        p["operation_runs"] += c.warmup + c.timed
        p["explain_passes"] += int(c.explain)
    return out


# ---- identity and digests -------------------------------------------------------------------

def file_sha(rel: str) -> str:
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def identities() -> dict:
    return {"registry_sha256": rb.REGISTRY["sha256"],
            "shadow_registry_sha256": rb.shadow_registry()["sha256"],
            "setup_sha256": rb.sha(json.dumps(rb.setup_registry(), sort_keys=True)),
            "explain_prefix_sha256": rb.sha(EXPLAIN_PREFIX),
            "zone_sha256": rb.ZONE_DIGEST,
            "operations": {k: v["sha256"] for k, v in rb.REGISTRY["operations"].items()},
            "statements": {k: v["sha256"] for k, v in rb.REGISTRY["statements"].items()},
            "sources": {rel: file_sha(rel) for rel in SOURCES}}


def platform_label() -> str:
    return "windows" if os.name == "nt" else "linux"


def is_wsl() -> bool:
    try:
        return "microsoft" in Path("/proc/sys/kernel/osrelease").read_text().lower()
    except OSError:
        return False


# ---- the owned run directory ----------------------------------------------------------------

class RunError(RuntimeError):
    """Refused; nothing outside the run directory was touched. Messages carry no secrets."""


class Run:
    def __init__(self, directory: Path):
        self.dir = Path(directory)
        self.state_path = self.dir / "state.json"
        self.checkpoint_path = self.dir / "checkpoint.json"
        self.datasets_path = self.dir / "datasets.json"   # written only by stage workers
        self.lock_path = self.dir / "run.lock"

    def canonical(self) -> str:
        return os.path.normcase(os.path.realpath(self.dir))

    @classmethod
    def create(cls, directory: Path, profile: Profile) -> "Run":
        run = cls(directory)
        if run.dir.exists() and any(run.dir.iterdir()):
            raise RunError("run directory exists and is not empty (refused)")
        run.dir.mkdir(parents=True, exist_ok=True)
        (run.dir / "private").mkdir()
        (run.dir / "public").mkdir()
        owner = secrets.token_hex(16)
        (run.dir / MARKER).write_text(json.dumps({"owner": owner, "dir": run.canonical()}))
        run._write(run.state_path, {
            "schema": SCHEMA, "owner": owner, "dir": run.canonical(), "profile": profile.name,
            "platform": platform_label(), "stages": {}, "worker": None, "blocked": None,
            "selection": {}})
        run._write(run.datasets_path, {})
        run._write(run.checkpoint_path, {"schema": SCHEMA, "identities": identities(),
                                         "cells": {}})
        return run

    def load(self) -> dict:
        marker = self.dir / MARKER
        if os.path.islink(self.dir) or not marker.is_file() or not self.state_path.is_file():
            raise RunError("not an owned AN01-M1 run directory (refused)")
        try:
            owned = json.loads(marker.read_text())
            state = json.loads(self.state_path.read_text())
        except (OSError, ValueError):
            raise RunError("run state is unreadable (refused)") from None
        if not (state.get("schema") == SCHEMA
                and secrets.compare_digest(str(owned.get("owner")), str(state.get("owner")))
                and owned.get("dir") == state.get("dir") == self.canonical()):
            raise RunError("ownership marker does not match the run state (refused)")
        return state

    def save(self, state: dict) -> None:
        self._write(self.state_path, state)

    def checkpoint(self) -> dict:
        return json.loads(self.checkpoint_path.read_text())

    def save_checkpoint(self, data: dict) -> None:
        self._write(self.checkpoint_path, data)

    def datasets(self) -> dict:
        return json.loads(self.datasets_path.read_text())

    def save_datasets(self, data: dict) -> None:
        self._write(self.datasets_path, data)

    def cluster_names(self) -> list[str]:
        root = self.dir / "clusters"
        return sorted(p.name for p in root.iterdir() if (p / local_stack.MARKER).is_file()) \
            if root.is_dir() else []

    def verify_identities(self) -> None:
        recorded = self.checkpoint()["identities"]
        current = identities()
        changed = sorted(k for k in current if recorded.get(k) != current[k])
        if changed:
            raise RunError(f"recorded digests changed ({', '.join(changed)}); a measured "
                           "statement or source may not change: start a new run directory")

    @staticmethod
    def _write(path: Path, data: dict) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=1, sort_keys=True, default=str) + "\n",
                       encoding="utf-8")
        os.replace(tmp, path)

    # The run lock is the stage slot: present while a stage runs or recovery is pending.
    def acquire_lock(self, holder: dict) -> None:
        try:
            fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            raise RunError("run lock held (a stage is running or recovery is pending)") from None
        with os.fdopen(fd, "w") as handle:
            json.dump(holder, handle)

    def release_lock(self) -> None:
        self.lock_path.unlink(missing_ok=True)

    def cluster(self, name: str, create: bool = False) -> tuple[local_stack.Stack, dict]:
        """A local_stack-owned cluster directory inside the run (marker verified)."""
        if name not in ("D1", "D2"):
            raise RunError("unknown cluster")
        stack = local_stack.Stack(self.dir / "clusters" / name)
        try:
            return stack, stack.load(create=create)
        except local_stack.StackError as error:
            raise RunError(f"cluster {name}: {error}") from None


# ---- public records: allow-listed and checked ----------------------------------------------

def forbidden_strings(run: Run | None) -> list[str]:
    items = ["postgresql://", "password", "host=", "Traceback", "token"]
    for value in (str(Path.home()), os.environ.get("USERNAME"), os.environ.get("USER"),
                  str(ROOT), run.canonical() if run else None, str(run.dir) if run else None):
        if value and len(value) > 2:
            items.append(value)
    return items


def write_public(run: Run | None, path: Path, data: dict) -> None:
    text = json.dumps(data, indent=1, sort_keys=True, default=str) + "\n"
    lowered = text.lower()
    for item in forbidden_strings(run):
        for form in (item, json.dumps(item)[1:-1]):
            if form.lower() in lowered:
                raise RunError("a public record would contain a forbidden value (refused)")
    path.write_text(text, encoding="utf-8")


# ---- resource preflight ---------------------------------------------------------------------

# Planning estimate per transaction row: the first tiny smoke measured average row data
# (pg_column_size) of about 936 B per transaction plus 1,087 B per outcome, and the expected
# 2% case/alert and 0.5% action rows add about 80 B; about 25% is added for tuple headers,
# page fill and four btree entries. Not a measured full-size volume.
BYTES_PER_ROW_ESTIMATE = 2_600
CLUSTER_BASE_BYTES = 64_000_000
WAL_ALLOWANCE_BYTES = 1_100_000_000  # default max_wal_size (1 GB) plus a margin, per cluster


def target_bytes(profile: Profile, stage: str, with_wal: bool = True) -> int:
    """Planning estimate of the clusters' size after `stage` (both clusters exist from S4;
    S8 adds the shadow copy of D2). With `with_wal`, each cluster's WAL allowance is added
    (needed free space); without it, the data estimate checked against the cluster cap."""
    clusters = []
    if stage in ("S1", "S2"):
        clusters = [profile.d2_rows()]
    elif stage in ("S4", "S5a", "S5b", "S6", "S8"):
        clusters = [profile.d1_rows(), profile.d2_rows() * (2 if stage == "S8" else 1)]
    wal = (WAL_ALLOWANCE_BYTES if profile.name == "full" else 50_000_000) if with_wal else 0
    return sum(rows * BYTES_PER_ROW_ESTIMATE + CLUSTER_BASE_BYTES + wal for rows in clusters)


def preflight(run_dir: Path, profile: Profile, stage: str, wsl_host_path: str | None) -> dict:
    """Free-space and volume checks only. Nothing is deleted, installed, resized or changed."""
    probe = run_dir if run_dir.exists() else run_dir.parent
    free = shutil.disk_usage(probe).free
    need, data_bytes = target_bytes(profile, stage), target_bytes(profile, stage, False)
    result = {"stage": stage, "profile": profile.name, "free_bytes": free,
              "target_bytes_estimate": need, "cluster_data_estimate": data_bytes,
              "min_free_bytes": profile.min_free_bytes,
              "max_cluster_bytes": profile.max_cluster_bytes, "estimate_basis":
              f"{BYTES_PER_ROW_ESTIMATE} B/row planning estimate + base + WAL allowance",
              "wsl": is_wsl(), "problems": []}
    if free < profile.min_free_bytes:
        result["problems"].append("free space below the profile minimum")
    if free < need:
        result["problems"].append("free space below the target volume estimate")
    if data_bytes > profile.max_cluster_bytes:
        result["problems"].append("estimated clusters exceed the profile maximum")
    if result["wsl"]:
        # The WSL ext4 disk grows inside a host file: its own free space can overstate what
        # the host can back. Check the host drive too; unknown backing space fails closed.
        host = wsl_host_path or "/mnt/c"
        try:
            host_free = shutil.disk_usage(host).free
            result["wsl_host_free_bytes"] = host_free
            if host_free < max(need, profile.min_free_bytes):
                result["problems"].append("WSL host backing space below the requirement")
        except OSError:
            result["problems"].append("WSL host backing space unknown (refused)")
    result["ok"] = not result["problems"]
    return result


# ---- cluster lifecycle (owned, verified) ---------------------------------------------------

def owner_url(stack: local_stack.Stack, data: dict) -> str:
    return local_stack.owner_url(stack, data, DATABASE)


def stop_cluster(stack: local_stack.Stack, data: dict, until: float) -> str:
    """Stop only a verified owned cluster, waiting no longer than `until` (monotonic).
    Returns stopped | already-stopped | unconfirmed:<state>."""
    state = local_stack.database_state(stack, data)
    if state in ("absent", "stopped"):
        return "already-stopped"
    if state != "owned":
        return f"unconfirmed:{state}"
    c = local_stack.cluster(stack, data["database"]["port"])
    left = until - time.monotonic()
    if left <= 1:
        return "unconfirmed:no-time"
    try:
        subprocess.run([str(c.bin_dir / "pg_ctl"), "-D", str(c.data_dir), "-m", "fast", "-w",
                        "-t", str(max(1, int(left) - 1)), "stop"], stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=left)
    except (OSError, subprocess.SubprocessError):
        pass
    if local_stack.wait_until(lambda: local_stack.database_state(stack, data) == "stopped",
                              max(0.0, until - time.monotonic())):
        return "stopped"
    return f"unconfirmed:{local_stack.database_state(stack, data)}"


def start_cluster(run: Run, name: str) -> tuple[local_stack.Stack, dict]:
    """Start (initializing once) this run's own cluster; refused unless verified ours."""
    from sentinel import devdb
    stack, data = run.cluster(name, create=True)
    port = data["database"].get("port") or devdb.free_port()
    try:
        local_stack.start_database(stack, data, port)
    except local_stack.StackError as error:
        raise RunError(f"cluster {name}: {error}") from None
    stack.save(data)
    return stack, data


# ---- worker processes: identity, launch, stop ----------------------------------------------

def terminate_owned(record: dict, until: float) -> str:
    """Stop a worker only when its recorded identity still matches. The termination request
    is bounded by `until`; success is reported only after the process and its tree are gone."""
    kind = local_stack.classify(record)
    if kind == "gone":
        return "gone" if not local_stack.tree_alive(record["pid"]) else "unconfirmed:child-alive"
    if kind != "owned":
        return f"unconfirmed:{kind}"
    left = until - time.monotonic()
    if left <= 0:
        return "unconfirmed:no-time"
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(record["pid"]), "/T", "/F"],
                           capture_output=True, timeout=left)
        else:
            import signal
            os.killpg(record["pid"], signal.SIGTERM)
    except (OSError, subprocess.SubprocessError):
        pass
    gone = local_stack.wait_until(
        lambda: local_stack.classify(record) == "gone"
        and not local_stack.tree_alive(record["pid"]), max(0.0, until - time.monotonic()))
    return "stopped" if gone else "unconfirmed:still-running"


def launch_worker(run: Run, state: dict, stage: str, argv: list[str], log) -> subprocess.Popen:
    state["worker"] = {"pending": True, "stage": stage}   # recorded BEFORE launch
    run.save(state)
    flags = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" \
        else {"start_new_session": True}
    proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "_worker", *argv],
                            stdin=subprocess.DEVNULL, stdout=log, stderr=log, cwd=str(ROOT),
                            **flags)
    record = {"pending": True, "stage": stage, "pid": proc.pid}
    state["worker"] = record
    run.save(state)
    try:
        ident = local_stack.identity(proc.pid)
        if ident is not None:
            state["worker"] = {**ident, "pending": False, "stage": stage}
            run.save(state)
    except local_stack.StackError:
        pass  # stays pending: never killed by pid; resolved only once it is provably gone
    return proc


def worker_resolved(record: dict | None) -> bool:
    """True only when the recorded worker is provably gone (with no surviving child that
    the platform still links to it). A pending launch without a pid is never resolved."""
    if not record:
        return True
    pid = record.get("pid")
    if not isinstance(pid, int):
        return False
    if record.get("pending"):
        try:
            alive = local_stack.identity(pid) is not None
        except local_stack.StackError:
            return False
        return not alive and not local_stack.tree_alive(pid)
    kind = local_stack.classify(record)
    if kind == "reused":
        return True                    # our process is gone; the pid now names another
    return kind == "gone" and not local_stack.tree_alive(pid)


# ---- the stage controller (supervisor) ------------------------------------------------------

def stage_command(args, budget: SupervisorBudget | None = None,
                  terminate=terminate_owned) -> int:
    t0 = time.monotonic()
    run = Run(Path(args.run_dir))
    state = run.load()
    profile = PROFILES[state["profile"]]
    budget = budget or profile.budget
    budget.check()
    if args.stage not in PLATFORM_STAGES:
        raise RunError(f"{args.stage} is not a platform stage")
    if profile.name == "full" and not args.authorized_full_size:
        raise RunError("the full-size grid needs a separate explicit authorization (refused)")
    run.verify_identities()
    if state.get("blocked"):
        raise RunError("recovery is pending for this run; run `recover` (refused)")
    if args.stage in state["stages"]:
        raise RunError(f"{args.stage} already ran in this run directory; there is no "
                       "automatic resume or retry (refused)")
    if args.fault and profile.name != "tiny":
        raise RunError("fault injection is allowed only on the tiny profile")
    _require_selection(state, args)
    run.acquire_lock({"pid": os.getpid(), "stage": args.stage})
    pre = preflight(run.dir, profile, args.stage, args.wsl_host_path)
    record = {"stage": args.stage, "platform": state["platform"], "profile": profile.name,
              "budget": asdict(budget), "preflight": pre, "fault_injection": args.fault,
              "status": "refused" if not pre["ok"] else "running"}
    state["stages"][args.stage] = record
    run.save(state)
    if not pre["ok"]:
        run.release_lock()
        _publish_stage(run, state, args.stage, t0)
        return EXIT["refused"]
    worker_argv = ["--run-dir", str(run.dir), "--stage", args.stage,
                   "--no-new-work-at", repr(t0 + budget.no_new_work_s),
                   "--setup-deadline-at", repr(t0 + min(SETUP_DEADLINE_S,
                                                        budget.no_new_work_s))]
    if args.fault:
        worker_argv += ["--fault", args.fault]
    log = open(run.dir / "private" / f"{args.stage}.log", "ab")
    try:
        proc = launch_worker(run, state, args.stage, worker_argv, log)
        work_end, controller_end = t0 + budget.work_deadline_s, t0 + budget.controller_deadline_s
        while proc.poll() is None and time.monotonic() < work_end:
            time.sleep(0.2)
        exited = proc.poll()
    finally:
        log.close()
    state = run.load()
    rec = state["stages"][args.stage]
    rec["worker_exit"] = exited
    cleanup = {}
    if exited is None:
        rec["deadline"] = "whole-stage work/wait deadline reached; worker stop requested"
        cleanup["worker"] = terminate(state["worker"], controller_end) \
            if not state["worker"].get("pending") else "unconfirmed:identity-not-established"
    else:
        cleanup["worker"] = "exited" if worker_resolved(state["worker"]) else \
            "unconfirmed:child-alive"
    for name in run.cluster_names():
        stack, data = run.cluster(name)
        cleanup[f"cluster:{name}"] = stop_cluster(stack, data, controller_end)
    rec["cleanup"] = cleanup
    rec["elapsed_s"] = round(time.monotonic() - t0, 3)
    confirmed = all(not str(v).startswith("unconfirmed") for v in cleanup.values())
    cells = _stage_cells(run, state, args.stage)
    rec["cells"] = {k: v["status"] for k, v in cells.items()}
    incomplete = [k for k, v in cells.items() if v["status"] != "complete"]
    if not confirmed:
        rec["status"] = "cleanup-unconfirmed"
        state["blocked"] = {"stage": args.stage, "cleanup": cleanup,
                            "recovery": "benchmark_reports.py recover --run-dir <run>"}
        run.save(state)
        _publish_stage(run, state, args.stage, t0)
        print("cleanup NOT confirmed; recovery state and run lock kept; no further stage "
              "may start until `recover` confirms", file=sys.stderr)
        return EXIT["unconfirmed"]
    state["worker"] = None
    if exited is None:
        rec["status"] = "deadline"
    elif exited != 0 or any(cells[k]["status"] == "failed" for k in cells):
        rec["status"] = "failed" if exited not in (0, 3) else "incomplete"
    else:
        rec["status"] = "complete" if not incomplete else "incomplete"
    run.save(state)
    run.release_lock()
    _publish_stage(run, state, args.stage, t0)
    return EXIT["ok"] if rec["status"] == "complete" else (
        EXIT["incomplete"] if rec["status"] in ("incomplete", "deadline") else EXIT["failed"])


def _require_selection(state: dict, args) -> None:
    needs = {"S4": "common-index", "S5a": "common-index", "S5b": "common-index",
             "S6": "common-index", "S8": "n-star"}.get(args.stage)
    if needs is None:
        return
    if args.selection:
        data = json.loads(Path(args.selection).read_text())
        if data.get("rule") != needs:
            raise RunError(f"{args.stage} needs a {needs} selection")
        digest = rb.sha(json.dumps(data, sort_keys=True))
        recorded = state["selection"].get(needs)
        if recorded and recorded["sha256"] != digest:
            raise RunError("a different selection was already recorded for this run (refused)")
        state["selection"][needs] = {"sha256": digest, "value": data["value"]}
    if needs not in state["selection"]:
        raise RunError(f"{args.stage} needs --selection from the offline {needs} rule")


def _stage_cells(run: Run, state: dict, stage: str) -> dict:
    profile = PROFILES[state["profile"]]
    n_star = state["selection"].get("n-star", {}).get("value", {}).get("n_star")
    recorded = run.checkpoint()["cells"]
    out = {}
    for cell in grid(profile, n_star):
        if cell.stage != stage:
            continue
        rec = recorded.get(cell.id)
        if rec is None:
            out[cell.id] = {"status": "not_run"}
        elif rec.get("status") == "started":
            out[cell.id] = {**rec, "status": "interrupted (outcome unknown)"}
        else:
            out[cell.id] = rec
    if stage in ("S1", "S4"):
        prep = run.datasets()
        for name in (("D2",) if stage == "S1" else ("D1",)):
            out[f"prepare:{name}"] = {"status": prep.get(name, {}).get("status", "not_run")}
    return out


def _publish_stage(run: Run, state: dict, stage: str, t0: float) -> None:
    rec = dict(state["stages"][stage])
    cells = _stage_cells(run, state, stage)
    public = {"schema": SCHEMA, "kind": "an01-m1-stage-record", "stage": stage,
              "platform": state["platform"], "profile": state["profile"],
              "label": "tiny plumbing evidence only" if state["profile"] == "tiny"
              else "measured on one laptop, warm cache, synthetic distribution",
              "identities": run.checkpoint()["identities"], "record": rec,
              "datasets": {k: {x: v[x] for x in ("status", "rows", "digest", "bytes",
                                                 "load_s", "postgres", "variant",
                                                 "index_build_s", "tuple_bytes", "phase_e_indexes")
                                 if x in v}
                           for k, v in run.datasets().items()},
              "selection": state.get("selection"), "cells": cells,
              "environment": {"os": platform.system(), "python": platform.python_version(),
                              "wsl": is_wsl(), "report_clock": "perf_counter",
                              "report_clock_resolution_s":
                              time.get_clock_info("perf_counter").resolution,
                              "monotonic_resolution_s":
                              time.get_clock_info("monotonic").resolution}}
    write_public(run, run.dir / "public" / f"{stage}-{state['platform']}.json", public)


# ---- the worker (one stage, inside the supervisor's deadline) ------------------------------

class Worker:
    def __init__(self, run: Run, stage: str, no_new_work_at: float, setup_deadline_at: float,
                 fault: str | None):
        self.run, self.stage, self.fault = run, stage, fault
        self.no_new_work_at, self.setup_deadline_at = no_new_work_at, setup_deadline_at
        self.state = run.load()
        self.profile = PROFILES[self.state["profile"]]
        self.zones = rb.ZoneTable()
        self.resources = rb.Resources(rb.PROVISIONAL_M, rb.PROVISIONAL_Q)
        self.quarantine = rb.ReportQuarantine()
        self.started: dict[str, tuple] = {}

    # -- checkpointed cells
    def may_start(self) -> bool:
        return time.monotonic() < self.no_new_work_at

    def mark(self, cell_id: str, record: dict) -> None:
        cp = self.run.checkpoint()
        cp["cells"][cell_id] = record
        self.run.save_checkpoint(cp)

    def run_cell(self, cell: Cell, body) -> None:
        cp = self.run.checkpoint()
        if cell.id in cp["cells"]:
            return  # first result kept; never re-run
        if not self.may_start():
            return  # listed as not run
        self.mark(cell.id, {"status": "started", "platform": self.state["platform"]})
        t0 = time.monotonic()
        try:
            record = body(cell)
        except Exception as error:  # recorded, not retried; detail stays private
            print(f"cell {cell.id} failed: {type(error).__name__}", file=sys.stderr)
            record = {"status": "failed", "error_class": type(error).__name__}
        record.update({"platform": self.state["platform"], "cell": asdict(cell),
                       "cell_s": round(time.monotonic() - t0, 3)})
        self.mark(cell.id, record)

    # -- clusters and roles
    def cluster(self, name: str):
        stack, data = start_cluster(self.run, name)
        return stack, data, owner_url(stack, data)

    def runtime_url(self, owner: str, role: str = RUNTIME_ROLE) -> str:
        from psycopg.conninfo import make_conninfo
        return make_conninfo(owner, user=role, password=self._password(role))

    def _password(self, role: str) -> str:
        path = self.run.dir / "private" / f"{role}.secret"
        if not path.exists():
            path.write_text(secrets.token_urlsafe(24))
            try:
                path.chmod(0o600)
            except OSError:
                pass
        return path.read_text()

    # -- S1 / S4: prepare a dataset
    def prepare(self, name: str) -> None:
        import psycopg
        from sentinel import db
        from sentinel.db import roles
        t0 = time.monotonic()
        datasets = self.run.datasets()
        datasets[name] = {"status": "started"}
        self.run.save_datasets(datasets)
        stack, data, admin = self.cluster(name)
        admin_url = local_stack.owner_url(stack, data)
        with psycopg.connect(admin_url, autocommit=True, connect_timeout=10) as conn:
            if not conn.execute("SELECT 1 FROM pg_database WHERE datname = %s",
                                (DATABASE,)).fetchone():
                conn.execute(f'CREATE DATABASE "{DATABASE}"')
        db.migrate(admin)
        roles.grant_runtime(admin, RUNTIME_ROLE, self._password(RUNTIME_ROLE))
        if self.fault == "stall-setup":
            threading.Event().wait()           # test fault: a setup step that never returns
        builder, scopes = rb.FixtureBuilder(), {}
        tenant = uuid.uuid5(uuid.NAMESPACE_URL, f"an01-m1:{self.profile.seed}:tenant")
        for size in (*self.profile.sizes, self.profile.guard_size):
            session = uuid.uuid5(tenant, f"session:{size}")
            rb.generate(builder, self.profile.seed, tenant, session, size, f"s{size}")
            scopes[str(size)] = [str(tenant), str(session)]
        if name == "D2":
            per = self.profile.background_rows // self.profile.background_tenants
            for i in range(self.profile.background_tenants):
                bt = uuid.uuid5(uuid.NAMESPACE_URL, f"an01-m1:{self.profile.seed}:bg{i}")
                rb.generate(builder, self.profile.seed, bt, uuid.uuid5(bt, "session"), per,
                            f"bg{i}")
        counts = rb.copy_rows(admin, builder)
        with psycopg.connect(admin, autocommit=True, connect_timeout=10) as conn:
            conn.execute("ANALYZE")
            size_bytes = conn.execute("SELECT pg_database_size(current_database())"
                                      ).fetchone()[0]
            version = conn.execute("SHOW server_version").fetchone()[0]
            tuple_bytes = {table: conn.execute(
                f"SELECT avg(pg_column_size(x.*))::int FROM {table} x").fetchone()[0]
                for table in rb.LOAD_ORDER}
        datasets = self.run.datasets()
        datasets[name] = {
            "status": "complete" if time.monotonic() <= self.setup_deadline_at
            else "complete-after-setup-deadline",
            "rows": counts, "digest": rb.dataset_digest(builder), "bytes": size_bytes,
            "load_s": round(time.monotonic() - t0, 3), "postgres": version,
            "sessions": scopes, "variant": "A", "tuple_bytes": tuple_bytes}
        self.run.save_datasets(datasets)

    def scope(self, dataset: str, size: int) -> tuple:
        tenant, session = self.run.datasets()[dataset]["sessions"][str(size)]
        return uuid.UUID(tenant), uuid.UUID(session)

    # -- requests for the grid
    def request(self, op: str, scope: tuple, filt: str, owner: str, cap: int):
        base = op.removesuffix("_cols")
        report_id = {"totals": "transactions.currency_totals",
                     "daily_utc": "transactions.daily", "daily_ny": "transactions.daily",
                     "workload": "cases.workload", "quality": "data_quality.checks",
                     "drill_first": "rows.transactions",
                     "drill_cursor": "rows.transactions"}[base]
        read_at = datetime.now(UTC)
        start = rb.FIXTURE_START
        kwargs = {"from_": start, "to": start + timedelta(days=rb.FIXTURE_DAYS),
                  "tz": "America/New_York" if base == "daily_ny" else "UTC",
                  "read_at": read_at}
        if filt == "asof90":
            kwargs["as_of"] = start + timedelta(days=rb.FIXTURE_DAYS * 0.1)
        if filt == "single_currency":
            kwargs["currencies"] = ("USD",)
        if report_id == "rows.transactions":
            kwargs["limit"] = rb.DEFAULT_LIMIT
        request = rb.normalize(self.zones, report_id, cap=cap, **kwargs)
        if base == "drill_cursor":
            request = self._mid_cursor(request, scope, owner, cap, kwargs)
        params = rb.parameters(request, scope, self.zones, cap)
        registry = rb.shadow_registry() if op.endswith("_cols") else rb.REGISTRY
        return rb.operation_sequence(op, params, registry), params

    def _mid_cursor(self, request, scope, owner, cap, kwargs):
        """A cursor at the middle of the matching set (owner reads, not timed)."""
        import psycopg
        from psycopg.rows import dict_row
        params = rb.parameters(request, scope, self.zones, cap)
        pair = rb.REGISTRY["statements"]["drill_first:P"]["text"]
        with psycopg.connect(owner, row_factory=dict_row, connect_timeout=10) as conn:
            counts = conn.execute(pair, params).fetchone()
            mid = conn.execute("SELECT t.occurred_at, t.id FROM transactions t WHERE "
                               + rb._FILTER + " ORDER BY t.occurred_at, t.id OFFSET %(off)s"
                               " LIMIT 1", {**params, "off": counts["matching"] // 2}
                               ).fetchone()
            conn.rollback()
        cursor = rb.encode_cursor(request, mid["occurred_at"], mid["id"],
                                  issued_pair(counts["matching"], counts["with_outcome"], cap))
        return rb.normalize(self.zones, "rows.transactions", cap=cap, cursor=cursor, **kwargs)

    def runtime(self, url: str, total_ms: int = rb.MEASUREMENT_B_MS, **kw) -> rb.Runtime:
        connect = rb.runtime_connect(url)
        if self.fault == "stall-connect":
            def connect():                     # test fault: acquisition that never returns
                threading.Event().wait()
        return rb.Runtime(connect=connect, resources=self.resources,
                          quarantine=self.quarantine, total_ms=total_ms, **kw)

    def measure(self, cell: Cell, url: str, owner: str, scope: tuple, cap: int) -> dict:
        sequence, params = self.request(cell.op, scope, cell.filter, owner, cap)
        guard = rb.guard_for(cap)
        rt = self.runtime(url)
        warm = [rb.run_statements(rt, sequence, guard).public() for _ in range(cell.warmup)]
        timed = [rb.run_statements(rt, sequence, guard).public() for _ in range(cell.timed)]
        explain = []
        if cell.explain:
            for key, text, p in sequence:
                out = rb.run_statements(rt, [(key, EXPLAIN_PREFIX + text, p)])
                plan = out.results.get(key, [{}])[0].get("QUERY PLAN") if out.kind == "ok" \
                    else None
                explain.append({"statement": key, "outcome": out.public(),
                                "plan": summarize_plan(plan)})
        ok = all(t["kind"] == cell.expect for t in timed) and \
            all(e["outcome"]["kind"] == "ok" for e in explain)
        return {"status": "complete" if ok else "failed", "warmup": warm, "timed": timed,
                "explain": explain,
                "median_ms": statistics.median(t["elapsed_ms"] for t in timed)
                if timed and all(t["elapsed_ms"] is not None for t in timed) else None}

    # -- stage bodies
    def S1(self):
        self.prepare("D2")

    def S2(self):
        _, data, owner = self.cluster("D2")
        url = self.runtime_url(owner)
        scope = self.scope("D2", self.profile.phase_a_size)
        builds = {}
        for variant in VARIANTS:
            if not self.may_start():
                break
            builds[variant] = rb.apply_variant(owner, variant)
            self._note_variant("D2", variant, builds[variant])
            for cell in grid(self.profile):
                if cell.phase == "A" and cell.variant == variant:
                    self.run_cell(cell, lambda c: self.measure(c, url, owner, scope,
                                                               self.profile.cap))

    def _note_variant(self, dataset, variant, builds):
        datasets = self.run.datasets()
        entry = datasets[dataset]
        entry["variant"] = variant
        entry.setdefault("index_build_s", {})[variant] = builds
        self.run.save_datasets(datasets)

    def S4(self):
        self.prepare("D1")
        variant = self.run.load()["selection"]["common-index"]["value"]["variant"]
        for name in ("D1", "D2"):
            _, _, owner = self.cluster(name)
            self._note_variant(name, variant, rb.apply_variant(owner, variant))

    def _phase_b(self, dataset):
        _, _, owner = self.cluster(dataset)
        url = self.runtime_url(owner)
        for cell in grid(self.profile):
            if cell.phase == "B" and cell.dataset == dataset:
                scope = self.scope(dataset, cell.size)
                self.run_cell(cell, lambda c, s=scope: self.measure(c, url, owner, s,
                                                                    self.profile.cap))

    def S5a(self):
        self._phase_b("D1")

    def S5b(self):
        self._phase_b("D2")
        _, _, owner = self.cluster("D2")
        url = self.runtime_url(owner)
        scope = self.scope("D2", self.profile.guard_size)
        for cell in grid(self.profile):
            if cell.phase == "BG":
                self.run_cell(cell, lambda c: self.measure(c, url, owner, scope,
                                                           self.profile.cap))

    def S6(self):
        _, data, owner = self.cluster("D2")
        url = self.runtime_url(owner)
        scope = self.scope("D2", self.profile.phase_a_size)
        cap = self.profile.cap
        for cell in grid(self.profile):
            if cell.phase == "C":
                self.run_cell(cell, lambda c: self.control(c, url, owner, scope, cap,
                                                           data["database"]["port"]))
        for cell in grid(self.profile):
            if cell.phase == "D":
                self.run_cell(cell, lambda c: self.two_clients(c, url, owner, scope, cap))

    def control(self, cell: Cell, url, owner, scope, cap, port) -> dict:
        import psycopg
        name = cell.expect
        sequence, _ = self.request("totals", scope, "base", owner, cap)
        runs = []
        if name == "C5":
            return self._c5(url, owner, scope, cap, port)
        for _ in range(cell.timed):
            if name in ("C1", "C2", "C3"):
                observer = rb.Observer(owner)

                def on_connect(conn, o=observer):
                    o.watch(conn.info.backend_pid)
                    time.sleep(0.05)
                rt = self.runtime(url, cell.budget_ms, on_connect=on_connect)
                seq = [("C2", rb.CONTROL_SQL["C2"], {})] if name == "C2" else sequence
                holder = None
                if name == "C3":
                    holder = psycopg.connect(owner, connect_timeout=10)
                    holder.execute("LOCK TABLE transactions IN ACCESS EXCLUSIVE MODE")
                try:
                    out = rb.run_statements(rt, seq)
                finally:
                    if holder is not None:
                        holder.rollback()
                        holder.close()
                seen = observer.stop()
                entry = out.public()
                entry["observer"] = sorted({(s["tag"], s["state"], s["wait"]) for s in seen},
                                           key=str)
                entry["rollback_ms"] = None
                expected = {"C1": ("refused_before_submission",),
                            "C2": ("server_cancelled",),
                            "C3": ("lock_timeout", "server_cancelled")}[name]
                proof = {"C1": not seen and out.submitted == 0,
                         "C2": any(s["state"] == "active" for s in seen),
                         "C3": any(s["wait"] == "Lock" for s in seen)}[name]
                entry["proved"] = out.kind in expected and proof
                runs.append(entry)
            else:  # C4: the relay withholds the reply of the tagged statement
                relay = rb.WithholdingRelay(port, b"an01-m1:totals:G")
                try:
                    from psycopg.conninfo import make_conninfo
                    rt = self.runtime(make_conninfo(url, port=str(relay.port),
                                                    sslmode="disable", gssencmode="disable"),
                                      cell.budget_ms)
                    out = rb.run_statements(rt, sequence)
                    t_drain = time.monotonic()
                    drained = local_stack.wait_until(
                        lambda: self.resources.counts() == (0, 0)
                        and self.quarantine.count() == 0, 10)
                    entry = out.public()
                    entry.update({"relay_saw_statement": bool(relay.sightings),
                                  "drained": drained,
                                  "drain_s": round(time.monotonic() - t_drain, 3),
                                  "events": out.connection.events if out.connection else []})
                    entry["proved"] = out.kind == "no_reply" and bool(relay.sightings) \
                        and drained
                    runs.append(entry)
                finally:
                    relay.close()
                if not entry["drained"]:
                    break  # not drained: the remaining runs are not run
        complete = len(runs) == cell.timed and all(r["proved"] for r in runs)
        return {"status": "complete" if complete else "failed", "timed": runs}

    def _c5(self, url, owner, scope, cap, port) -> dict:
        from psycopg.conninfo import make_conninfo
        sequence, _ = self.request("totals", scope, "base", owner, cap)
        relay = rb.WithholdingRelay(port, b"an01-m1:totals:G")
        gate = threading.Event()
        connects = {"direct": 0}
        direct = rb.runtime_connect(url)

        def counted():
            connects["direct"] += 1
            return direct()
        holders = rb.Runtime(connect=rb.runtime_connect(make_conninfo(
            url, port=str(relay.port), sslmode="disable", gssencmode="disable")),
            resources=self.resources, quarantine=self.quarantine, total_ms=1250,
            final_close_gate=lambda: gate.wait(20))
        fresh = rb.Runtime(connect=counted, resources=self.resources,
                           quarantine=self.quarantine)
        events = []
        try:
            held = [rb.run_statements(holders, sequence) for _ in range(2)]
            events.append({"holders": [h.kind for h in held]})
            local_stack.wait_until(lambda: all(h.connection and h.connection.users == set()
                                               for h in held), 10)
            events.append({"counts_held": self.resources.counts(),
                           "quarantined": self.quarantine.count()})
            refused = rb.run_statements(fresh, sequence)
            events.append({"third": refused.kind, "connect_calls": connects["direct"]})
            gate.set()
            drained = local_stack.wait_until(lambda: self.resources.counts() == (0, 0)
                                             and self.quarantine.count() == 0, 10)
            events.append({"drained": drained,
                           "close_calls": [h.connection.close_calls for h in held]})
            after = rb.run_statements(fresh, sequence)
            events.append({"fresh": after.kind, "connect_calls": connects["direct"]})
            proved = ([h.kind for h in held] == ["no_reply", "no_reply"]
                      and events[1] == {"counts_held": (0, 2), "quarantined": 2}
                      and refused.kind == "admission_refused" and events[2]["connect_calls"] == 0
                      and drained and after.kind == "ok")
        finally:
            gate.set()
            relay.close()
        return {"status": "complete" if proved else "failed", "label":
                "fault injection: delayed final close (not cancellation latency)",
                "timed": events}

    def two_clients(self, cell: Cell, url, owner, scope, cap) -> dict:
        rt = self.runtime(url)
        jobs = [self.request(op, scope, "base", owner, cap)[0]
                for op in ("quality", "drill_first")]
        results, lock = [], threading.Lock()

        def client(i):
            for n in range(cell.timed // 2):
                out = rb.run_statements(rt, jobs[(i + n) % 2], rb.guard_for(cap)).public()
                with lock:
                    results.append(out)
        threads = [threading.Thread(target=client, args=(i,)) for i in range(2)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        ok = len(results) == cell.timed and all(r["kind"] == "ok" for r in results)
        return {"status": "complete" if ok else "failed", "timed": results,
                "max_ms": max((r["elapsed_ms"] or 0) for r in results) if results else None}

    def S8(self):
        import psycopg
        n_star = self.run.load()["selection"]["n-star"]["value"].get("n_star")
        if not n_star:
            return  # no N*: phase E is not run, and says so
        _, _, owner = self.cluster("D2")
        with psycopg.connect(owner, autocommit=True, connect_timeout=10) as conn:
            exists = conn.execute("SELECT to_regclass(%s)",
                                  (f"{rb.SHADOW_SCHEMA}.transactions",)).fetchone()[0]
            variant = self.run.datasets()["D2"]["variant"]
            if not exists:
                for ddl in rb.shadow_ddl(variant):
                    conn.execute(ddl)
                from psycopg import sql
                conn.execute(sql.SQL("CREATE ROLE {} LOGIN NOINHERIT PASSWORD {}").format(
                    sql.Identifier(SHADOW_ROLE), sql.Literal(self._password(SHADOW_ROLE))))
                conn.execute(f"GRANT USAGE ON SCHEMA {rb.SHADOW_SCHEMA} TO {SHADOW_ROLE}")
                conn.execute(f"GRANT SELECT ON {rb.SHADOW_SCHEMA}.transactions,"
                             f" public.scoring_outcomes TO {SHADOW_ROLE}")
                conn.execute("ANALYZE")
            indexes = {schema: sorted(r[0] for r in conn.execute(
                "SELECT indexdef FROM pg_indexes WHERE schemaname = %s"
                " AND tablename = 'transactions'", (schema,)))
                for schema in ("public", rb.SHADOW_SCHEMA)}
        datasets = self.run.datasets()
        datasets["D2"]["phase_e_indexes"] = {"variant": variant, **indexes}
        self.run.save_datasets(datasets)
        json_url, cols_url = self.runtime_url(owner), self.runtime_url(owner, SHADOW_ROLE)
        scope = self.scope("D2", n_star)
        for cell in grid(self.profile, n_star):
            if cell.phase == "E":
                url = cols_url if cell.op.endswith("_cols") else json_url
                self.run_cell(cell, lambda c, u=url: self.measure(c, u, owner, scope,
                                                                  self.profile.cap))

    def execute(self) -> int:
        try:
            getattr(self, self.stage)()
        finally:
            for name in self.run.cluster_names():
                stack, data = self.run.cluster(name)
                stop_cluster(stack, data, time.monotonic() + 60)
        cells = _stage_cells(self.run, self.run.load(), self.stage)
        return 0 if all(v["status"] == "complete" for v in cells.values()) else 3


def issued_pair(matching: int, with_outcome: int, cap: int) -> tuple[int, int]:
    """The consistency pair a cursor can legitimately carry: one issued by a page 1 that was
    served, so at most the cap. A B-guard set (cap + 1 rows) is reached by drill_cursor only
    through such an earlier cursor; a cursor claiming more than the cap is invalid_cursor
    (first tiny smoke: BG:drill_cursor failed with InvalidCursor; the rule is kept)."""
    first = min(matching, cap)
    return first, min(with_outcome, first)


def summarize_plan(plan) -> dict | None:
    """Diagnostics only: scan node types per relation, temp blocks, execution time."""
    if not plan:
        return None
    root = plan[0]
    scans, temp = [], 0

    def walk(node):
        nonlocal temp
        if "Relation Name" in node:
            scans.append((node["Relation Name"], node["Node Type"]))
        temp += node.get("Temp Written Blocks", 0) + node.get("Temp Read Blocks", 0)
        for child in node.get("Plans", []):
            walk(child)
    walk(root["Plan"])
    return {"execution_ms": root.get("Execution Time"), "planning_ms": root.get("Planning Time"),
            "scans": sorted(set(scans)), "temp_blocks": temp}


# ---- offline rules (pre-registered; decisions section 8.4) ---------------------------------

def load_records(paths: list[str]) -> dict:
    """{platform: {cell_id: record}} from public stage records."""
    out: dict = {}
    for path in paths:
        data = json.loads(Path(path).read_text())
        if data.get("kind") != "an01-m1-stage-record":
            raise RunError("not an AN01-M1 stage record")
        out.setdefault(data["platform"], {}).update(data["cells"])
    return out


def _medians(cells: dict, prefix: str) -> dict:
    return {k.split(":")[-1]: v.get("median_ms") for k, v in cells.items()
            if k.startswith(prefix) and v.get("status") == "complete"}


def _seq_scan(cells: dict, variant: str) -> set:
    found = set()
    for k, v in cells.items():
        if k.startswith(f"A:{variant}:") and k.split(":")[-1] in rb.TRANSACTION_OPS:
            for e in v.get("explain", []):
                for rel, node in (e.get("plan") or {}).get("scans", []):
                    if rel == "transactions" and node == "Seq Scan":
                        found.add(k.split(":")[-1])
    return found


def rule_common_index(records: dict, budget_ms: int = rb.PROVISIONAL_B_MS) -> dict:
    """Rule 1. One configuration for both platforms; an unmeasured variant is never chosen."""
    if len(records) != 2:
        return {"rule": "common-index", "value": {"variant": "A", "demonstrated": False},
                "reason": "both platforms' phase A records are required"}
    ops = list(rb.OPERATIONS)
    med = {p: {v: _medians(c, f"A:{v}:") for v in VARIANTS} for p, c in records.items()}
    complete = {p: {v: len(med[p][v]) == len(ops) and None not in med[p][v].values()
                    for v in VARIANTS} for p in records}

    def no_regression(p, v):
        return all(med[p][v][o] <= 1.10 * med[p]["A"][o] for o in ops)

    def improves_b(p):
        plan = bool(_seq_scan(records[p], "A") - _seq_scan(records[p], "B"))
        halves = any(med[p]["B"][o] <= 0.5 * med[p]["A"][o] for o in rb.TRANSACTION_OPS)
        return plan or halves
    platforms = sorted(records)
    if not all(complete[p]["A"] for p in platforms):
        return {"rule": "common-index", "value": {"variant": "A", "demonstrated": False},
                "reason": "variant A (baseline) cells incomplete"}
    variant, reason = "A", "B did not meet the two-platform condition"
    if all(complete[p]["B"] for p in platforms) and any(
            improves_b(p) and no_regression(q, "B")
            for p in platforms for q in platforms if q != p):
        variant, reason = "B", "B improved on one platform without >10% regression on the other"
        if all(complete[p]["C"] for p in platforms) and any(
                med[p]["C"]["workload"] <= med[p]["B"]["workload"] - 0.10 * budget_ms
                and no_regression(q, "C") for p in platforms for q in platforms if q != p):
            variant, reason = "C", "C improved workload by >= 10% of B on one platform"
    return {"rule": "common-index", "value": {"variant": variant, "demonstrated": True},
            "reason": reason, "medians_ms": med}


def rule_n_star(records: dict, sizes: tuple[int, ...], budget_ms: int = rb.PROVISIONAL_B_MS
                ) -> dict:
    """Rule 2 (with rule 6): the largest size whose every phase B cell, at it and every
    smaller size, on both platforms and datasets, is present with all 5 complete-operation
    times <= 40% of B and no timeout; and every B-guard cell returns 413 within B."""
    limit = 0.40 * budget_ms
    if len(records) != 2:
        return {"rule": "n-star", "value": {"n_star": None, "demonstrated": False},
                "reason": "both platforms are required"}
    guard_ok = all(v.get("status") == "complete" and all(
        t["kind"] == "too_large" and (t["elapsed_ms"] or 1e18) <= budget_ms
        for t in v.get("timed", []))
        for c in records.values() for k, v in c.items() if k.startswith("BG:"))
    guard_present = all(sum(k.startswith("BG:") for k in c) == len(rb.TRANSACTION_OPS)
                        for c in records.values())
    n_star, failures = None, []
    for size in sorted(sizes):
        good = True
        for p, cells in records.items():
            for dataset in ("D1", "D2"):
                for op in rb.OPERATIONS:
                    for filt in (FILTERS if op != "workload" else ("base",)):
                        rec = cells.get(f"B:{dataset}:{size}:{op}:{filt}")
                        if rec is None or rec.get("status") != "complete" or not all(
                                t["kind"] == "ok" and t["elapsed_ms"] <= limit
                                for t in rec.get("timed", [])) or len(rec["timed"]) != 5:
                            good = False
                            failures.append(f"{p}:{dataset}:{size}:{op}:{filt}")
        if not good:
            break
        n_star = size
    value = {"n_star": n_star if guard_ok and guard_present else None,
             "demonstrated": bool(n_star) and guard_ok and guard_present}
    proposal = ("propose a design change instead of a cap" if n_star is None
                else f"propose N* = {n_star}" if n_star < max(sizes)
                else f"the largest measured size {n_star} qualifies")
    return {"rule": "n-star", "value": value, "proposal": proposal,
            "guard_ok": guard_ok and guard_present, "first_failures": failures[:10]}


def rule_controls(records: dict, budget_ms: int = rb.PROVISIONAL_B_MS,
                  reserve_ms: int = rb.PROVISIONAL_R_MS) -> dict:
    """Rule 3: triggers only open a re-review; no number changes here."""
    triggers, missing = [], []
    for p, cells in records.items():
        for cid in [f"{k}:{b}" for k, v in C_BUDGETS.items() for b, _ in v] + ["C5"]:
            rec = cells.get(cid)
            if rec is None or rec.get("status") != "complete":
                missing.append(f"{p}:{cid}")
        for k, rec in cells.items():
            if k.split(":")[0] in ("C2", "C3") and rec.get("timed"):
                cell_budget = int(k.split(":")[1])
                lat = [t["deadline_to_error_ms"] for t in rec["timed"]
                       if t.get("deadline_to_error_ms") is not None]
                if lat and statistics.median(lat) > 0.10 * cell_budget:
                    triggers.append(f"{p}:{k}: median deadline-to-error over 10% of budget")
        d = cells.get("D")
        if d and d.get("max_ms") is not None and d["max_ms"] > budget_ms - reserve_ms:
            triggers.append(f"{p}:D maximum exceeds B - R")
    return {"rule": "controls", "triggers": triggers, "missing": missing,
            "demonstrated": not missing}


def rule_spills(records: dict, n_star: int | None) -> dict:
    spills = sorted({f"{p}:{k}" for p, cells in records.items() for k, v in cells.items()
                     if n_star and k.startswith("B:") and k.split(":")[2] == str(n_star)
                     for e in v.get("explain", []) if (e.get("plan") or {}).get("temp_blocks")})
    return {"rule": "spills", "spills": spills,
            "work_mem_statement_required": bool(spills)}


def rule_design_comparison(records: dict) -> dict:
    out, opens = {}, len(records) == 2
    for p, cells in records.items():
        for op in rb.SHADOW_REGISTRY_OPS:
            j, c = cells.get(f"E:json:{op}"), cells.get(f"E:cols:{op}")
            if not (j and c and j.get("median_ms") and c.get("median_ms")):
                opens = False
                out[f"{p}:{op}"] = "not run"
                continue
            ratio = c["median_ms"] / j["median_ms"]
            out[f"{p}:{op}"] = round(ratio, 3)
            opens = opens and ratio <= 0.5
    return {"rule": "design-comparison", "columns_over_json_median": out,
            "opens_generated_columns_review": opens,
            "note": "difference between two designs; no causal share is assigned to JSON"}


def final_report(records: dict, profile: Profile) -> dict:
    index = rule_common_index(records)
    n_star = rule_n_star(records, profile.sizes)
    mandatory = {}
    for p in sorted(records) or ["(none)"]:
        cells = records.get(p, {})
        for cell in grid(profile):
            if cell.mandatory and cell.phase in ("A", "BG", "C"):
                st = cells.get(cell.id, {}).get("status", "not_run")
                if st != "complete":
                    mandatory.setdefault(p, []).append(f"{cell.id}={st}")
    return {"kind": "an01-m1-final-report", "profile": profile.name,
            "label": "tiny plumbing evidence only (no limit is qualified)"
            if profile.name == "tiny" else
            "measured on one laptop, warm cache, synthetic distribution",
            "platforms": sorted(records), "rule1_common_index": index,
            "rule2_n_star": n_star, "rule3_controls": rule_controls(records),
            "rule4_spills": rule_spills(records, n_star["value"]["n_star"]),
            "rule5_design_comparison": rule_design_comparison(records),
            "rule6_missing_mandatory": mandatory,
            "rule6_status": "not demonstrated" if mandatory or not records else
            "mandatory evidence present",
            "provisional_until_accepted": ["cap 200000", "B 5000 ms", "R 250 ms", "M/Q 2/2"]}


# ---- recover and cleanup ---------------------------------------------------------------------

def recover_command(args) -> int:
    run = Run(Path(args.run_dir))
    state = run.load()
    until = time.monotonic() + 120
    kept, done = [], []
    worker = state.get("worker")
    if worker:
        if worker.get("pending"):
            if worker_resolved(worker):
                done.append("pending worker launch is provably gone")
                state["worker"] = None
            else:
                kept.append("pending worker launch unresolved (never killed by pid)")
        else:
            result = terminate_owned(worker, until)
            if result in ("gone", "stopped") or local_stack.classify(worker) == "reused":
                done.append(f"worker {result}")
                state["worker"] = None
            else:
                kept.append(f"worker {result}")
    for name in run.cluster_names():
        stack, data = run.cluster(name)
        result = stop_cluster(stack, data, until)
        (kept if result.startswith("unconfirmed") else done).append(f"cluster {name}: {result}")
    if not kept:
        state["blocked"] = None
        run.save(state)
        run.release_lock()
    else:
        run.save(state)
    print(json.dumps({"recovered": done, "kept": kept}, indent=1))
    return 0 if not kept else EXIT["unconfirmed"]


def cleanup_command(args) -> int:
    run = Run(Path(args.run_dir))
    state = run.load()
    if state.get("blocked") or run.lock_path.exists():
        raise RunError("recovery pending or a stage holds the run lock (refused)")
    until = time.monotonic() + 120
    report = {}
    for name in run.cluster_names():
        stack, data = run.cluster(name)
        result = stop_cluster(stack, data, until)
        report[name] = result
        if args.delete_owned_data and result in ("stopped", "already-stopped"):
            if local_stack.database_state(stack, data) in ("stopped", "absent"):
                stack.load()   # re-verifies the cluster's own ownership marker
                shutil.rmtree(stack.dir / "pg")
                report[name] += "; owned data directory deleted"
    print(json.dumps(report, indent=1))
    return 0 if all(not v.startswith("unconfirmed") for v in report.values()) else 4


# ---- CLI ---------------------------------------------------------------------------------------

def plan_document(profile: Profile) -> dict:
    cells = grid(profile)
    return {"profile": asdict(profile), "stages": STAGES, "platform_stages": PLATFORM_STAGES,
            "offline_stages": OFFLINE_STAGES, "phases": grid_totals(cells),
            "cell_count": len(cells), "identities": identities(),
            "statements": {k: v["text"] for k, v in rb.REGISTRY["statements"].items()},
            "controls": rb.REGISTRY["controls"], "control_sql": rb.REGISTRY["control_sql"],
            "setup": rb.setup_registry(),
            "preflight_estimates": {s: {"free_needed": target_bytes(profile, s),
                                        "cluster_data": target_bytes(profile, s, False)}
                                    for s in PLATFORM_STAGES}}


def parse_args(argv):
    parser = argparse.ArgumentParser(description="AN01-M1 report measurement prototype")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--profile", choices=PROFILES, default="tiny")
    p = sub.add_parser("init")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--profile", choices=PROFILES, default="tiny")
    p = sub.add_parser("stage")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--stage", required=True, choices=PLATFORM_STAGES)
    p.add_argument("--selection")
    p.add_argument("--authorized-full-size", action="store_true")
    p.add_argument("--fault", choices=("stall-connect", "stall-setup"))
    p.add_argument("--wsl-host-path")
    p = sub.add_parser("select")
    p.add_argument("--rule", required=True, choices=("common-index", "n-star"))
    p.add_argument("--profile", choices=PROFILES, default="tiny")
    p.add_argument("--record", action="append", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser("report")
    p.add_argument("--profile", choices=PROFILES, default="tiny")
    p.add_argument("--record", action="append", required=True)
    p.add_argument("--out", required=True)
    for name in ("recover", "cleanup"):
        p = sub.add_parser(name)
        p.add_argument("--run-dir", required=True)
        if name == "cleanup":
            p.add_argument("--delete-owned-data", action="store_true")
    p = sub.add_parser("_worker")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--stage", required=True)
    p.add_argument("--no-new-work-at", type=float, required=True)
    p.add_argument("--setup-deadline-at", type=float, required=True)
    p.add_argument("--fault")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "plan":
            print(json.dumps(plan_document(PROFILES[args.profile]), indent=1, default=str))
            return 0
        if args.command == "init":
            Run.create(Path(args.run_dir), PROFILES[args.profile])
            print("run directory initialized")
            return 0
        if args.command == "stage":
            return stage_command(args)
        if args.command in ("select", "report"):
            records = load_records(args.record)
            profile = PROFILES[args.profile]
            if args.command == "select":
                result = rule_common_index(records) if args.rule == "common-index" \
                    else rule_n_star(records, profile.sizes)
            else:
                result = final_report(records, profile)
            write_public(None, Path(args.out), result)
            print(json.dumps(result.get("value", result.get("rule6_status")), default=str))
            return 0
        if args.command == "recover":
            return recover_command(args)
        if args.command == "cleanup":
            return cleanup_command(args)
        if args.command == "_worker":
            run = Run(Path(args.run_dir))
            run.verify_identities()
            if args.no_new_work_at - time.monotonic() > ACCEPTED_BUDGET.no_new_work_s + 5:
                raise RunError("implausible stage deadline (clock mismatch); refused")
            return Worker(run, args.stage, args.no_new_work_at, args.setup_deadline_at,
                          args.fault).execute()
    except RunError as error:
        print(f"refused: {error}", file=sys.stderr)
        return EXIT["refused"]
    return EXIT["failed"]


if __name__ == "__main__":
    raise SystemExit(main())
