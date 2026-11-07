"""PERF01: the bounded local capacity benchmark (scripts/benchmark_local.py).

Arithmetic, outcome accounting and caps use hand-computed samples, fake clocks and fake
senders; the whole command runs against an in-memory fake API through httpx's mock
transport, so nothing is started. One refusal test runs the real accepted helper, which
refuses before any database or API exists. The single end-to-end test starts a fresh owned
stack on free ports through the helper and leaves both ports free.
"""
import json
import os
import socket
import sys
import threading
import uuid
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import benchmark_local as bench  # noqa: E402
import local_stack  # noqa: E402
from sentinel import devdb  # noqa: E402

needs_pg = pytest.mark.skipif(devdb.find_pg_bin() is None, reason="needs PostgreSQL binaries")
TOKEN = "perf01-test-token-" + uuid.uuid4().hex


class FakeClock:
    """Monotonic seconds advanced only by the fake sender."""

    def __init__(self):
        self.now, self.lock = 100.0, threading.Lock()

    def __call__(self):
        with self.lock:
            return self.now

    def advance(self, seconds):
        with self.lock:
            self.now += seconds


def planned(i, expected=200, timeout=1.0):
    return bench.Planned("read", "GET", f"/x/{i}", None, expected, timeout=timeout)


def sender(script, clock=None, step=0.0):
    """Answers request i with script[i % len(script)]: a (status, body) or an exception."""
    calls = []
    lock = threading.Lock()

    def send(item):
        with lock:
            calls.append(item.path)
            answer = script[(len(calls) - 1) % len(script)]
        if clock is not None:
            clock.advance(step)
        if isinstance(answer, BaseException):
            raise answer
        return answer
    return send, calls


# ---- statistics on hand-computed samples ----------------------------------------------------

def test_nearest_rank_quantiles_on_hand_computed_samples():
    five = [0.5, 0.1, 0.3, 0.2, 0.4]
    assert bench.nearest_rank(five, 0.50) == 0.3  # rank ceil(2.5) = 3
    assert bench.nearest_rank(five, 0.95) == 0.5  # rank ceil(4.75) = 5
    twenty = [float(v) for v in range(20, 0, -1)]
    assert bench.nearest_rank(twenty, 0.50) == 10.0  # rank 10
    assert bench.nearest_rank(twenty, 0.95) == 19.0  # rank 19, not interpolated
    assert bench.nearest_rank([7.0], 0.95) == 7.0
    assert bench.nearest_rank([], 0.5) is None
    assert bench.latency_summary(five) == {"n": 5, "p50_s": 0.3, "p95_s": 0.5, "max_s": 0.5}
    assert bench.latency_summary([]) == {"n": 0, "p50_s": "n/a", "p95_s": "n/a",
                                         "max_s": "n/a"}


def test_empty_denominators_are_not_applicable_never_zero_or_one_hundred_percent():
    assert bench.rate(5, None) == "n/a" and bench.rate(5, 0.0) == "n/a"
    assert bench.rate(0, 2.0) == 0.0 and bench.rate(6, 4.0) == 1.5
    assert bench.fraction(0, 0) == "n/a" and bench.fraction(3, 4) == 0.75


# ---- outcome accounting ---------------------------------------------------------------------

def test_every_started_request_is_counted_once_with_its_observed_result():
    script = [
        (200, {"ok": True}),
        (409, {"error": "agent_capacity_exhausted"}),
        (500, {"error": "internal"}),
        httpx.ReadTimeout("timed out"),
        httpx.ConnectError("refused"),
        (409, {"error": "investigation_outcome_unknown"}),
        (200, "not a dict"),
        httpx.RemoteProtocolError("closed"),
        (502, None),
    ]
    item_check = lambda body: body["ok"] is True  # noqa: E731
    items = [bench.Planned("investigate", "POST", f"/c/{i}", {}, 200, item_check, timeout=1)
             for i in range(len(script))]
    send, calls = sender(script)
    budget = bench.Budget(100, 60, bench.time.monotonic)
    cell = bench.run_cell("investigate", items, 1, budget, send)
    observed = [(r.outcome, r.code, r.status) for r in cell["records"]]
    assert observed == [
        ("success", None, 200),
        ("refused", "agent_capacity_exhausted", 409),  # expected refusal, never a success
        ("failed", "internal", 500),
        ("unknown", "client:ReadTimeout", None),  # may have written: not a failure
        ("failed", "not_sent:ConnectError", None),
        ("unknown", "investigation_outcome_unknown", 409),
        ("failed", "unexpected_body", 200),
        ("unknown", "client:RemoteProtocolError", None),
        ("failed", "http_502", 502),
    ]
    assert len(calls) == len(script)  # one attempt each: no hidden retry
    summary = bench.cell_summary(cell)
    assert summary["started"] == 9 and summary["not_started"] == 0
    assert summary["outcomes"] == {"success": 1, "refused": 1, "failed": 4, "unknown": 3}
    assert summary["status_codes"] == {"200": 2, "409": 2, "500": 1, "502": 1, "none": 3}
    assert summary["service_codes"]["agent_capacity_exhausted"] == 1
    assert summary["latency_all_attempts"]["n"] == 9 and summary["latency_success"]["n"] == 1


def test_latency_window_and_throughput_units_on_a_fake_monotonic_clock():
    clock = FakeClock()
    send, _ = sender([(200, {}), (200, {}), (409, {"error": "conflict"}), (200, {})],
                     clock, step=0.25)
    cell = bench.run_cell("read", [planned(i) for i in range(4)], 1,
                          bench.Budget(100, 60, clock), send, clock)
    summary = bench.cell_summary(cell)
    assert [r.latency_s for r in cell["records"]] == [0.25] * 4
    assert summary["window_s"] == 1.0  # first start (100.0) to last end (101.0)
    assert summary["throughput_attempted_per_s"] == 4.0
    assert summary["throughput_success_per_s"] == 3.0
    assert summary["latency_success"] == {"n": 3, "p50_s": 0.25, "p95_s": 0.25, "max_s": 0.25}
    assert summary["success_fraction"] == 0.75


def test_a_cell_with_no_success_or_no_start_reports_not_applicable():
    send, _ = sender([(409, {"error": "agent_capacity_exhausted"})])
    refused = bench.cell_summary(bench.run_cell(
        "investigate", [planned(i) for i in range(3)], 2, bench.Budget(100, 60,
                                                                       bench.time.monotonic),
        send))
    assert refused["outcomes"]["refused"] == 3 and refused["latency_success"]["n"] == 0
    assert refused["latency_success"]["p50_s"] == "n/a"
    assert refused["throughput_success_per_s"] in (0.0, "n/a")
    exhausted = bench.Budget(0, 60, bench.time.monotonic)
    empty = bench.cell_summary(bench.run_cell("read", [planned(0)], 1, exhausted, send))
    assert empty["started"] == 0 and empty["not_started"] == 1
    assert empty["window_s"] == "n/a" and empty["throughput_attempted_per_s"] == "n/a"
    assert empty["success_fraction"] == "n/a" and empty["stop_reason"] == "request_cap"


# ---- caps stop new work ---------------------------------------------------------------------

def test_the_request_cap_stops_new_work_across_cells():
    send, calls = sender([(200, {})])
    budget = bench.Budget(5, 60, bench.time.monotonic)
    first = bench.run_cell("read", [planned(i) for i in range(4)], 2, budget, send)
    second = bench.run_cell("read", [planned(i) for i in range(4)], 4, budget, send)
    third = bench.run_cell("read", [planned(i) for i in range(4)], 1, budget, send)
    assert [len(c["records"]) for c in (first, second, third)] == [4, 1, 0]
    assert len(calls) == 5 and budget.started == 5
    assert (second["stop_reason"], third["stop_reason"]) == ("request_cap", "request_cap")


def test_the_duration_cap_stops_new_work_and_lets_in_flight_finish():
    clock = FakeClock()
    send, calls = sender([(200, {})], clock, step=1.0)
    budget = bench.Budget(100, 3.5, clock)
    cell = bench.run_cell("read", [planned(i) for i in range(10)], 1, budget, send, clock)
    # Starts at 100, 101, 102 and 103 (< 103.5); the fourth finishes at 104, after the cap.
    assert len(cell["records"]) == 4 and len(calls) == 4
    assert cell["records"][-1].end_s == 104.0 and cell["records"][-1].outcome == "success"
    assert cell["stop_reason"] == "duration_cap"
    later = bench.run_cell("read", [planned(0)], 1, budget, send, clock)
    assert later["records"] == [] and later["stop_reason"] == "duration_cap"


def test_a_request_still_in_flight_after_the_bounded_wait_stays_unknown():
    release = threading.Event()

    def send(item):
        release.wait(30)
        return 200, {}
    budget = bench.Budget(10, 0.05, bench.time.monotonic)
    try:
        cell = bench.run_cell("investigate", [planned(0, timeout=0.05)], 1, budget, send,
                              join_margin=0.05)
    finally:
        release.set()
    (record,) = cell["records"]
    assert (record.outcome, record.code, record.end_s) == ("unknown", "client_wait_exceeded",
                                                            None)
    summary = bench.cell_summary(cell)
    assert summary["outcomes"]["unknown"] == 1 and summary["latency_unfinished"] == 1
    assert summary["abandoned_workers"] == 1


@pytest.mark.parametrize("argv", [
    ["--requests", "51"], ["--requests", "0"], ["--concurrency", "8"],
    ["--concurrency", "1,1"], ["--max-requests", "201"], ["--max-seconds", "601"],
    ["--warmup", "6"], ["--workloads", "approve"], ["--investigator", "claude-cli"],
    ["--base-url", "http://example.com"], ["--target", "remote"], ["--port", "80"],
], ids=lambda argv: " ".join(argv))
def test_the_command_line_refuses_oversized_plans_and_any_target(argv, capsys):
    with pytest.raises(SystemExit) as raised:
        bench.parse_args(argv)
    assert raised.value.code == 2


def test_defaults_match_the_bounded_plan():
    args = bench.parse_args([])
    assert (args.requests, args.concurrency, args.workloads) == (
        12, [1, 2, 4], ["ingest", "read", "investigate"])
    assert (args.max_requests, args.max_seconds, args.investigator) == (108, 300.0,
                                                                         "three-role")
    assert bench.planned_setup_requests(args) == 3 + 6 + 12 + 38


# ---- isolation from providers, targets and secrets ------------------------------------------

def test_the_helper_environment_cannot_select_a_provider(tmp_path, monkeypatch):
    for key, value in {"SENTINEL_AGENT_ADAPTER": "claude-cli", "SENTINEL_INVESTIGATOR":
                       "claude-cli", "SENTINEL_CLAUDE_MODEL": "opus", "ANTHROPIC_API_KEY": "k",
                       "PYTHONPATH": "elsewhere", "SENTINEL_TOKEN": "t",
                       "SENTINEL_DATABASE_URL": "postgresql://x"}.items():
        monkeypatch.setenv(key, value)
    env = bench.child_environment(tmp_path)
    for key in ("SENTINEL_AGENT_ADAPTER", "SENTINEL_INVESTIGATOR", "SENTINEL_CLAUDE_MODEL",
                "ANTHROPIC_API_KEY", "PYTHONPATH", "SENTINEL_TOKEN", "SENTINEL_DATABASE_URL"):
        assert key not in env
    assert env["SENTINEL_LIVE_CLAUDE"] == "0"
    assert not Path(env["SENTINEL_CLAUDE_EXECUTABLE"]).exists()


def test_the_client_targets_only_owned_loopback_and_ignores_proxies(monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.invalid:9")
    client = bench.http_client(18080, TOKEN, 4)
    try:
        assert (client.base_url.host, client.base_url.port) == ("127.0.0.1", 18080)
        assert client.trust_env is False
    finally:
        client.close()


def test_provenance_holds_no_host_user_path_or_environment():
    facts = bench.provenance()
    text = json.dumps(facts)
    for private in (socket.gethostname(), os.environ.get("USERNAME"), os.environ.get("USER"),
                    str(ROOT), str(Path.home())):
        if private and len(private) > 2:
            assert private not in text
    assert set(facts) == {"source_commit", "tracked_changes", "python", "implementation",
                          "os", "os_release", "machine", "processor", "logical_cpus",
                          "total_physical_gib", "available_at_start_gib", "postgres", "clock"}


# ---- resident memory only on verified owned processes ----------------------------------------

def test_resident_memory_is_read_only_while_the_identity_matches():
    me = local_stack.identity(os.getpid())
    assert bench.resident_bytes(me, read=lambda pid: 1234) == 1234
    assert bench.resident_bytes({**me, "start": me["start"] + 1}, read=lambda pid: 1) is None
    flips = iter([me, {**me, "exe": "other"}])  # reused between the checks
    assert bench.resident_bytes(me, identify=lambda pid: next(flips),
                                read=lambda pid: 1) is None
    real = bench.resident_bytes(me)
    assert real is None or real > 1_000_000  # this interpreter: unknown, or plausibly sized


def test_the_sampler_counts_unreadable_reads_instead_of_guessing():
    members = [{"pid": 1}, {"pid": 2}, {"pid": 3}]
    values = {1: 100, 2: None, 3: 50}
    sampler = bench.Sampler({"api": lambda: members, "postgres": lambda: []}, 0.1,
                            reader=lambda identity: values[identity["pid"]])
    sampler.sample()
    values[3] = 500
    sampler.sample()
    stats = sampler.stats
    assert stats["api"] == {"samples": 2, "peak_sum_bytes": 600, "max_processes": 2,
                            "unreadable_reads": 2}
    assert stats["postgres"]["samples"] == 0 and stats["postgres"]["peak_sum_bytes"] is None
    report = sampler.stop()
    assert report["scopes"]["postgres"]["peak_sum_mib"] == "unknown"


# ---- the whole command against a fake API ----------------------------------------------------

class FakeAPI:
    """Just enough of the HTTP contract. Investigations are admitted one at a time
    (like max_live_workflows_per_process=1); a second concurrent one is refused."""

    def __init__(self, investigator="three-role-workflow", timeout_case_index=None):
        self.investigator, self.timeout_case_index = investigator, timeout_case_index
        self.cases, self.transactions, self.lock = {}, 0, threading.Lock()
        self.active, self.investigations, self.approvals = 0, 0, 0
        self.auth = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.auth.append(request.headers.get("authorization"))
        method, path = request.method, request.url.path
        body = json.loads(request.content) if request.content else None
        if path == "/healthz":
            return httpx.Response(200, json={"status": "ok", "investigator": self.investigator})
        if path == "/v1/scoring":
            return httpx.Response(200, json={"mode": "rule"})
        if path == "/v1/session":
            return httpx.Response(200, json={"capabilities": []})
        if path == "/v1/overview":
            states = {}
            for case in self.cases.values():
                states[case["state"]] = states.get(case["state"], 0) + 1
            return httpx.Response(200, json={"cases_by_state": states, "alerts": len(self.cases),
                                             "transactions": self.transactions,
                                             "simulated_actions": 0})
        if path == "/v1/transactions" and method == "POST":
            with self.lock:
                self.transactions += 1
                case = None
                if body["amount"]["minor_units"] >= 100_000:
                    case = {"id": str(uuid.uuid4()), "revision": 1, "state": "open"}
                    self.cases[case["id"]] = case
            return httpx.Response(201, json={"transaction": {"external_id": body["external_id"]},
                                             "replayed": False, "case": case})
        if path == "/v1/cases":
            return httpx.Response(200, json={"items": [{"id": c} for c in self.cases],
                                             "next_cursor": None, "limit": 100})
        parts = path.split("/")
        case = self.cases.get(parts[3]) if len(parts) > 3 else None
        if case is None:
            return httpx.Response(404, json={"error": "not_found"})
        if method == "GET":
            return httpx.Response(200, json=self.detail(case))
        with self.lock:
            self.investigations += 1
            index = self.investigations
            if self.active:
                return httpx.Response(409, json={"error": "agent_capacity_exhausted"})
            self.active += 1
        try:
            if index == self.timeout_case_index:
                raise httpx.ReadTimeout("simulated client timeout", request=request)
            threading.Event().wait(0.02)
            case.update(state="awaiting_approval", revision=case["revision"] + 1)
            return httpx.Response(200, json=self.detail(case))
        finally:
            with self.lock:
                self.active -= 1

    @staticmethod
    def detail(case):
        return {"case": dict(case), "agent_runs": [], "action_intents": [
            {"intent": {}, "approval": None, "action": None}]}


class FakeStack:
    def __init__(self, run_dir, port, db_port, investigator, verified=True):
        self.run_dir, self.port, self.state = run_dir, port, run_dir / "stack"
        self.api_record = {"investigator": investigator, "scorer": "rule", "claude_model": None,
                           "adapter": "deterministic" if investigator == "three-role" else None}
        self.postmaster, self.log, self.verified, self.downs = None, [], verified, 0

    def up(self):
        return 0

    def token(self):
        return TOKEN

    def api_members(self):
        return []

    def down(self):
        self.downs += 1
        return {"verified": self.verified}


def run_fake(tmp_path, monkeypatch, capsys, argv, api, verified=True):
    stacks = []

    def factory(*args):
        stacks.append(FakeStack(*args, verified=verified))
        return stacks[-1]

    def client(port, token, concurrency):
        return httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False,
                            transport=httpx.MockTransport(api.handle),
                            headers={"Authorization": f"Bearer {token}"})
    monkeypatch.setattr(bench, "http_client", client)
    run_dir = tmp_path / "run"
    code = bench.main(["--run-dir", str(run_dir), "--rss-interval", "0.1", *argv],
                      stack_factory=factory)
    out = capsys.readouterr()
    return code, json.loads(out.out), out, run_dir, stacks[0]


def test_the_command_accounts_for_setup_measurement_and_verification(tmp_path, monkeypatch,
                                                                     capsys):
    api = FakeAPI()
    code, summary, out, run_dir, stack = run_fake(
        tmp_path, monkeypatch, capsys,
        ["--requests", "3", "--concurrency", "1,2", "--warmup", "1"], api)
    assert code == 0 and summary["error"] is None and stack.downs == 1
    cells = {(c["workload"], c["concurrency"]): c for c in summary["measurement"]["cells"]}
    assert set(cells) == {(w, c) for w in ("ingest", "read", "investigate") for c in (1, 2)}
    for key in [("ingest", 1), ("ingest", 2), ("read", 1), ("read", 2), ("investigate", 1)]:
        assert cells[key]["outcomes"] == {"success": 3, "refused": 0, "failed": 0,
                                          "unknown": 0}, key
    contended = cells[("investigate", 2)]
    assert contended["started"] == 3
    assert sum(contended["outcomes"].values()) == 3 and contended["outcomes"]["success"] >= 1
    assert set(contended["service_codes"]) <= {"agent_capacity_exhausted"}
    assert contended["outcomes"]["refused"] == contended["service_codes"].get(
        "agent_capacity_exhausted", 0)
    measurement = summary["measurement"]
    assert (measurement["started"], measurement["not_started"]) == (18, 0)
    # Setup: health, scorer, session, 3 read cases, 3 * 2 + 1 investigate cases; warm-up 3.
    assert summary["setup"]["requests"] == 3 + 3 + 7
    assert summary["setup"]["outcomes"]["success"] == 13
    assert summary["warmup"]["requests"] == 3
    verification = summary["verification"]
    assert (verification["approvals"], verification["simulated_actions_on_cases"],
            verification["simulated_actions_overview"]) == (0, 0, 0)
    assert verification["scoped_cases"] == 10 and verification["requests"] == 1 + 10 + 1
    assert verification["ingest_reconciliation"]["unaccounted_written"] == 0
    assert summary["config"]["retries"] == 0
    assert summary["config"]["target"] == "owned loopback API only"
    # The token reached the API, and nowhere else.
    assert all(a == f"Bearer {TOKEN}" for a in api.auth)
    for text in (out.out, out.err, *(p.read_text() for p in run_dir.glob("*.json"))):
        assert TOKEN not in text and "postgresql://" not in text
        assert "password" not in text.lower() and "authorization" not in text.lower()
    assert {p.name for p in run_dir.iterdir()} == {"records.json", "summary.json"}


def test_an_unknown_investigation_is_reconciled_but_stays_unknown(tmp_path, monkeypatch,
                                                                  capsys):
    api = FakeAPI(timeout_case_index=2)
    code, summary, *_ = run_fake(tmp_path, monkeypatch, capsys,
                                 ["--requests", "2", "--concurrency", "1", "--warmup", "0",
                                  "--workloads", "investigate"], api)
    (cell,) = summary["measurement"]["cells"]
    assert cell["outcomes"] == {"success": 1, "refused": 0, "failed": 0, "unknown": 1}
    (reconciled,) = summary["verification"]["unknown_reconciliation"]
    assert reconciled["outcome"] == "unknown (kept)"
    assert reconciled["observed_case_state"] == "open"  # this fake wrote nothing
    assert code == 0


def test_a_wrong_investigator_is_refused_before_measurement(tmp_path, monkeypatch, capsys):
    api = FakeAPI(investigator="claude-cli-investigator")
    code, summary, *_ = run_fake(tmp_path, monkeypatch, capsys, ["--requests", "1"], api)
    assert code == 1 and "requested investigator" in summary["error"]
    assert summary["measurement"]["started"] == 0 and api.investigations == 0


def test_unverified_cleanup_is_reported_with_recovery_and_nothing_removed(tmp_path,
                                                                          monkeypatch, capsys):
    code, summary, out, run_dir, stack = run_fake(
        tmp_path, monkeypatch, capsys, ["--requests", "1", "--concurrency", "1",
                                        "--workloads", "read"], FakeAPI(), verified=False)
    assert code == 2 and stack.downs == 1
    assert "cleanup could not be verified" in out.err and " down" in out.err
    assert run_dir.is_dir()


def test_an_existing_run_directory_is_refused_and_left_untouched(tmp_path, capsys):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "someone-elses.txt").write_text("keep")
    started = []
    code = bench.main(["--run-dir", str(run_dir)], stack_factory=lambda *a: started.append(a))
    assert code == 3 and started == []
    assert "already exists" in capsys.readouterr().err
    assert [p.name for p in run_dir.iterdir()] == ["someone-elses.txt"]


def test_a_foreign_listener_is_refused_by_the_helper_and_preserved(tmp_path, capsys):
    """The real helper refuses before creating a database or API; the foreign socket keeps
    listening, nothing is killed, and cleanup is verified without touching it."""
    foreign = socket.socket()
    foreign.bind(("127.0.0.1", 0))
    foreign.listen()
    port = foreign.getsockname()[1]
    try:
        run_dir = tmp_path / "run"
        code = bench.main(["--run-dir", str(run_dir), "--port", str(port),
                           "--requests", "1"])
        out = capsys.readouterr()
        summary = json.loads(out.out)
        assert code == 1 and summary["stack"]["helper_up_exit"] == 1
        assert summary["cleanup"]["verified"] is True
        assert summary["cleanup"]["ports_before"]["api_port"] == "foreign"
        assert summary["cleanup"]["api_port"] == "foreign"  # still the foreign listener
        assert "measurement" not in summary
        probe = socket.create_connection(("127.0.0.1", port), timeout=5)
        probe.close()
        raw = json.loads((run_dir / "records.json").read_text())
        assert "in use by another process; refused" in raw["helper"][0]["output_tail"]
        assert not (run_dir / "stack" / "pg").exists()  # no cluster was created
    finally:
        foreign.close()


# ---- one small real run on a fresh owned stack ------------------------------------------------

@needs_pg
def test_a_small_real_run_on_a_fresh_owned_stack_cleans_up(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("SENTINEL_AGENT_ADAPTER", "claude-cli")  # hostile and ignored
    monkeypatch.setenv("SENTINEL_CLAUDE_MODEL", "opus")
    run_dir = tmp_path / "run"
    code = bench.main(["--run-dir", str(run_dir), "--requests", "2", "--concurrency", "1,2",
                       "--warmup", "1", "--max-seconds", "120"])
    out = capsys.readouterr()
    summary = json.loads(out.out)
    assert code == 0, (summary.get("error"), out.err[-2000:])
    assert summary["stack"]["investigator"] == "three-role"
    assert (summary["stack"]["adapter"], summary["stack"]["claude_model"]) == (
        "deterministic", None)
    cells = {(c["workload"], c["concurrency"]): c for c in summary["measurement"]["cells"]}
    for key in [("ingest", 1), ("ingest", 2), ("read", 1), ("read", 2), ("investigate", 1)]:
        assert cells[key]["outcomes"]["success"] == 2, (key, cells[key])
    contended = cells[("investigate", 2)]
    assert contended["started"] == 2 and contended["outcomes"]["success"] >= 1
    assert set(contended["service_codes"]) <= {"agent_capacity_exhausted"}
    verification = summary["verification"]
    assert (verification["approvals"], verification["simulated_actions_on_cases"],
            verification["simulated_actions_overview"]) == (0, 0, 0)
    assert verification["ingest_reconciliation"]["unaccounted_written"] == 0
    cleanup = summary["cleanup"]
    assert cleanup["verified"] is True and cleanup["helper_down_exit"] == 0
    assert (cleanup["api_port"], cleanup["db_port"]) == ("free", "free")
    assert cleanup["postmaster"] == "gone" and set(cleanup["api_processes"]) == {"gone"}
    token = json.loads((run_dir / "stack" / "session.json").read_text())["token"]
    log = (run_dir / "stack" / "api.log").read_text(encoding="utf-8", errors="replace")
    for text in (out.out, out.err, log, *(p.read_text() for p in run_dir.glob("*.json"))):
        assert token not in text and "postgresql://" not in text
    memory = summary["resident_memory"]["scopes"]
    assert memory["api"]["samples"] >= 1 or memory["api"]["unreadable_reads"] >= 1
    assert local_stack.Stack(run_dir / "stack").load()["api"] is None


def test_namespace_helper_for_setup_counts():
    args = SimpleNamespace(requests=2, concurrency=[1], warmup=0, workloads=["read"])
    assert bench.planned_setup_requests(args) == 3 + 2
