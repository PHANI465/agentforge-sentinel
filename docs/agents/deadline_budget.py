"""G3A deadline and transaction-budget specification (design check, not a runtime).

    uv run --locked python docs/agents/deadline_budget.py

Pure functions that define how the coordinator turns one absolute monotonic deadline into
finite, positive waiting budgets (G3A-design section 3.2), plus the checks Codex asked for:
the old formula's counterexamples, working versus terminal budgets at/inside the reserve,
sub-second boundaries, exhausted budgets, libpq connection granularity, sequential waits,
and the pending/uncertain terminal outcomes that fall back to recovery. Nothing here talks
to PostgreSQL or a provider; G3B implements and tests the runtime separately.

Units: every budget is an integer number of milliseconds, derived by rounding *down*
(never up). A budget smaller than its stated minimum is a refusal (None), never 0 or a
negative number: PostgreSQL treats statement_timeout = 0 and lock_timeout = 0 as "no
timeout", and libpq treats connect_timeout = 0 as "wait indefinitely".
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "contracts-draft"))
from g3a_models import WorkflowLimits  # noqa: E402  (the pinned draft limits)

LIMITS = WorkflowLimits()
DEADLINE_MS = LIMITS.workflow_deadline_seconds * 1000        # 150 000
RESERVE_MS = LIMITS.terminal_reserve_seconds * 1000          # 5 000
DB_WAIT_CAP_MS = LIMITS.db_wait_seconds * 1000               # 5 000 (per transaction)
TOOL_STATEMENT_CAP_MS = LIMITS.tool_statement_timeout_ms     # 2 000
ROLE_CALL_MS = (LIMITS.role_timeout_seconds + LIMITS.role_grace_seconds) * 1000  # 47 000
# Specification constants (not schema fields): the smallest timeout the coordinator will
# ever set, and the least terminal budget with which it will begin a terminal transaction.
MIN_DB_MS = 100
MIN_TERMINAL_START_MS = 1000
# libpq: connect_timeout is whole seconds, 0 waits forever, and a value of 1 is treated as
# 2; the limit applies to each host tried. The workflow connection must use one host.
LIBPQ_MIN_EFFECTIVE_S = 2


@dataclass(frozen=True)
class Clock:
    """The coordinator's absolute deadlines on a monotonic clock, in milliseconds.

    t0 is read before the claim transaction starts, so the monotonic deadline never falls
    after the persisted wall-clock deadline_at (started_at, written inside the claim, is
    not earlier). Recovery acts only after deadline_at + RECOVERY_GRACE, so a live
    coordinator and recovery never overlap."""
    t0_ms: int

    @property
    def deadline_ms(self) -> int:
        return self.t0_ms + DEADLINE_MS

    @property
    def work_end_ms(self) -> int:
        return self.deadline_ms - RESERVE_MS

    def available_ms(self, now_ms: float, phase: str) -> int:
        end = self.work_end_ms if phase == "working" else self.deadline_ms
        return math.floor(end - now_ms)  # round down; may be <= 0 (exhausted)


def budget_ms(clock: Clock, now_ms: float, phase: str, cap_ms: int,
              minimum_ms: int = MIN_DB_MS) -> int | None:
    """A finite positive budget for one operation, or None (refuse the operation)."""
    if phase not in ("working", "terminal"):
        raise ValueError(phase)
    value = min(cap_ms, clock.available_ms(now_ms, phase))
    return value if value >= minimum_ms else None


def connect_timeout_s(available_ms: int, cap_s: int = LIMITS.db_wait_seconds,
                      hosts: int = 1) -> int | None:
    """libpq connect_timeout for a new connection, or None (do not connect). Whole seconds,
    rounded down; refused below libpq's effective minimum (1 means 2, 0 means forever) and
    for multi-host connection strings, whose limit applies per host."""
    if hosts != 1:
        return None
    seconds = min(cap_s, available_ms // 1000)
    return seconds if seconds >= LIBPQ_MIN_EFFECTIVE_S else None


def terminal_reconnect_timeout_s(available_ms: int) -> int | None:
    """A replacement connection in the terminal phase: its worst case (the chosen whole-second
    timeout) must still leave the terminal start budget afterwards."""
    return connect_timeout_s(available_ms - MIN_TERMINAL_START_MS)


def old_formula_s(remaining_s: float) -> float:
    """06a7c0c/feb80d1: min(db_wait_seconds, remaining - terminal_reserve)."""
    return min(LIMITS.db_wait_seconds, remaining_s - LIMITS.terminal_reserve_seconds)


def run_transaction(clock: Clock, start_ms: float, phase: str, durations_ms: list[float],
                    commit_reply: str = "ok") -> tuple[str, float, list[int]]:
    """Model of one bounded transaction: statements run one after another, each with
    statement_timeout = lock_timeout = the remaining transaction budget, recomputed from
    the clock before every statement and before COMMIT.

    durations_ms are how long each statement would take if unbounded. Returns (outcome,
    end time, budgets set). Outcomes: committed; refused (not started); rolled_back
    (known not written: a budget ran out, or a statement hit its timeout); uncertain
    (COMMIT was sent but no definitive reply arrived)."""
    if phase == "terminal":
        start = budget_ms(clock, start_ms, phase, DB_WAIT_CAP_MS, MIN_TERMINAL_START_MS)
    else:
        start = budget_ms(clock, start_ms, phase, DB_WAIT_CAP_MS)
    if start is None:
        return "refused", start_ms, []
    tx_end = start_ms + start
    now, budgets = start_ms, []
    for duration in durations_ms + [None]:  # None stands for COMMIT
        remaining = math.floor(min(tx_end, clock.deadline_ms if phase == "terminal"
                                   else clock.work_end_ms) - now)
        if remaining < MIN_DB_MS:
            return "rolled_back", now, budgets
        budgets.append(remaining)
        if duration is None:
            return ("committed" if commit_reply == "ok" else "uncertain"), now, budgets
        if duration >= remaining:  # the server cancels it at the timeout
            return "rolled_back", now + remaining, budgets
        now += duration
    raise AssertionError("unreachable")


# Terminal outcome -> (HTTP result, durable state) (G3A-design section 6.1).
OUTCOMES = {
    "committed": ("200 CaseDetail, read inside the terminal transaction before COMMIT",
                  "workflow terminal; case open or awaiting_approval"),
    "refused": ("409 investigation_in_progress",
                "workflow still running; recovery after deadline_at + 30 s"),
    "rolled_back": ("409 investigation_in_progress",
                    "workflow still running; recovery after deadline_at + 30 s"),
    "uncertain": ("409 investigation_outcome_unknown; the client re-reads",
                  "terminal or still running; if still running, recovery closes it"),
}


def checks() -> list[str]:
    problems: list[str] = []

    def expect(label, actual, wanted):
        if actual != wanted:
            problems.append(f"{label}: got {actual!r}, expected {wanted!r}")

    # 1. The reviewed counterexamples: the old formula yields disabling/negative timeouts.
    for remaining, wanted in ((6, 1), (5, 0), (4, -1), (0, -5)):
        expect(f"old formula at {remaining} s", old_formula_s(remaining), wanted)

    c = Clock(t0_ms=1_000_000)
    at = lambda remaining_ms: c.deadline_ms - remaining_ms  # noqa: E731

    # 2. Working phase: subtracts the reserve; refuses at and inside it.
    expect("working, 6 s left", budget_ms(c, at(6000), "working", DB_WAIT_CAP_MS), 1000)
    expect("working, 20 s left (capped)", budget_ms(c, at(20000), "working", DB_WAIT_CAP_MS),
           5000)
    expect("working, exactly at the reserve", budget_ms(c, at(5000), "working",
                                                        DB_WAIT_CAP_MS), None)
    expect("working, inside the reserve", budget_ms(c, at(4000), "working", DB_WAIT_CAP_MS),
           None)
    expect("working, tool cap", budget_ms(c, at(60000), "working", TOOL_STATEMENT_CAP_MS),
           2000)
    expect("role call needs the full call outside the reserve",
           budget_ms(c, at(5000 + ROLE_CALL_MS - 1), "working", ROLE_CALL_MS, ROLE_CALL_MS),
           None)
    expect("role call fits exactly",
           budget_ms(c, at(5000 + ROLE_CALL_MS), "working", ROLE_CALL_MS, ROLE_CALL_MS),
           ROLE_CALL_MS)

    # 3. Terminal phase: does not subtract its own reserve; a valid budget exists inside it.
    expect("terminal, exactly 5 s left", budget_ms(c, at(5000), "terminal", DB_WAIT_CAP_MS),
           5000)
    expect("terminal, 4 s left", budget_ms(c, at(4000), "terminal", DB_WAIT_CAP_MS), 4000)
    expect("terminal, 0.1 s left", budget_ms(c, at(100), "terminal", DB_WAIT_CAP_MS), 100)

    # 4. Sub-second boundaries round down and never reach a disabling zero.
    expect("working, 5.0999 s left", budget_ms(c, at(5099.9), "working", DB_WAIT_CAP_MS),
           None)  # 99 ms < minimum
    expect("working, 5.1009 s left", budget_ms(c, at(5100.9), "working", DB_WAIT_CAP_MS), 100)
    expect("terminal, 0.0999 s left", budget_ms(c, at(99.9), "terminal", DB_WAIT_CAP_MS),
           None)
    expect("terminal, 0.5 ms left", budget_ms(c, at(0.5), "terminal", DB_WAIT_CAP_MS), None)

    # 5. Exhausted and expired: refusals, never 0 or negative values.
    for label, remaining in (("zero", 0), ("expired 1 s", -1000), ("expired 0.3 ms", -0.3)):
        for phase in ("working", "terminal"):
            value = budget_ms(c, at(remaining), phase, DB_WAIT_CAP_MS)
            if value is not None:
                problems.append(f"{phase} {label}: budget {value} instead of refusal")
    every = [budget_ms(c, at(r / 10), p, cap)
             for r in range(-20000, 200000, 7) for p in ("working", "terminal")
             for cap in (DB_WAIT_CAP_MS, TOOL_STATEMENT_CAP_MS)]
    if any(v is not None and (v < MIN_DB_MS or v > DB_WAIT_CAP_MS) for v in every):
        problems.append("a budget outside [MIN_DB_MS, cap] was produced")

    # 6. libpq connection granularity: whole seconds, at least 2, single host only.
    expect("connect, 2.5 s available", connect_timeout_s(2500), 2)
    expect("connect, 1.9 s available (1 would mean 2)", connect_timeout_s(1900), None)
    expect("connect, 0.9 s available (0 means forever)", connect_timeout_s(900), None)
    expect("connect, 30 s available (capped)", connect_timeout_s(30000), 5)
    expect("connect, two hosts", connect_timeout_s(30000, hosts=2), None)
    expect("terminal reconnect, 4 s left: 3 s connect still leaves 1 s",
           terminal_reconnect_timeout_s(4000), 3)
    expect("terminal reconnect, 3 s left: 2 s connect leaves exactly 1 s",
           terminal_reconnect_timeout_s(3000), 2)
    expect("terminal reconnect, 2.9 s left: refused", terminal_reconnect_timeout_s(2900), None)
    for available in range(0, 5001, 10):
        chosen = terminal_reconnect_timeout_s(available)
        if chosen is not None and available - chosen * 1000 < MIN_TERMINAL_START_MS:
            problems.append(f"terminal reconnect at {available} ms leaves too little")

    # 7. Sequential waits consume one transaction budget; the total never exceeds it.
    outcome, end, budgets = run_transaction(c, at(5000), "terminal", [1500, 1500, 1500])
    expect("terminal, three 1.5 s statements", (outcome, budgets), ("committed",
                                                                    [5000, 3500, 2000, 500]))
    if end > c.deadline_ms:
        problems.append("a terminal transaction ended after the deadline")
    outcome, end, budgets = run_transaction(c, at(5000), "terminal", [3000, 2500])
    expect("terminal, second statement hits its timeout", (outcome, budgets),
           ("rolled_back", [5000, 2000]))
    expect("rolled back at the deadline, not after", end, c.deadline_ms)
    outcome, _, budgets = run_transaction(c, at(5000), "terminal", [4950])
    expect("terminal, no time left for COMMIT", (outcome, budgets), ("rolled_back", [5000]))
    outcome, _, _ = run_transaction(c, at(60000), "working", [10, 10])
    expect("working transaction well before the reserve", outcome, "committed")
    outcome, end, _ = run_transaction(c, at(5500), "working", [300, 300])
    expect("working transaction cannot run into the reserve", outcome, "rolled_back")
    if end > c.work_end_ms:
        problems.append("a working transaction ran into the terminal reserve")

    # 8. No safe terminal start, or an uncertain COMMIT: never reported as completion.
    expect("terminal start with 0.9 s left", run_transaction(c, at(900), "terminal", [10])[0],
           "refused")
    expect("terminal with a lost COMMIT reply",
           run_transaction(c, at(5000), "terminal", [10], commit_reply="lost")[0], "uncertain")
    for outcome in ("refused", "rolled_back", "uncertain"):
        if OUTCOMES[outcome][0].startswith("200"):
            problems.append(f"{outcome} reported as a successful completion")
    if not OUTCOMES["committed"][0].startswith("200"):
        problems.append("a committed terminal transaction must return CaseDetail")

    return problems


def main() -> int:
    problems = checks()
    for problem in problems:
        print(problem)
    if not problems:
        print("deadline budget specification consistent: old formula gives 1/0/-1/-5 s at "
              "6/5/4/0 s; working and terminal budgets finite and positive or refused; "
              "a valid terminal budget exists inside the reserve; sequential waits, libpq "
              "granularity and pending/uncertain outcomes checked")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
