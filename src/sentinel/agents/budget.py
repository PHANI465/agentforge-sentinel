"""One absolute monotonic deadline and finite database budgets (G3A-design section 3.2).

Rules, from the accepted specification docs/agents/deadline_budget.py:
- the deadline is read before the claim; the working phase ends `terminal_reserve` before
  it; only the terminal transaction is measured to the deadline itself;
- every budget is an integer number of milliseconds, min(cap, floor(end - now)), and a
  budget below its minimum is a refusal, never 0 or a negative value (PostgreSQL treats a
  zero statement_timeout/lock_timeout as "no timeout", libpq a zero connect_timeout as
  "wait forever");
- a transaction has one combined budget; statement_timeout and lock_timeout are recomputed
  from the clock before every statement and before COMMIT;
- one single-host workflow connection, connect_timeout in whole seconds >= 2.

This bounds elapsed waiting on this process's clock. It does not prove that a COMMIT is
durable within the deadline or that the server notices a timeout instantly.
"""
from __future__ import annotations

import math
import threading
import time
from typing import Callable

import psycopg
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row

from sentinel.contracts.agents import WorkflowLimits

MIN_DB_MS = 100
MIN_TERMINAL_START_MS = 1000
LIBPQ_MIN_EFFECTIVE_S = 2


def monotonic_ms() -> float:
    return time.monotonic() * 1000


class BudgetExhausted(Exception):
    """No positive budget is left for the next operation (nothing was sent for it), or the
    server cancelled an operation at its timeout. The transaction is known not committed."""


class ConnectionLost(Exception):
    """The connection broke before COMMIT was sent; the transaction is known not committed."""


class CommitUncertain(Exception):
    """COMMIT was sent but no definitive reply arrived: the outcome is unknown."""


class Deadline:
    def __init__(self, limits: WorkflowLimits, clock: Callable[[], float] = monotonic_ms,
                 *, total_ms: int | None = None, reserve_ms: int | None = None):
        self.clock = clock
        self.t0_ms = clock()
        self.total_ms = limits.workflow_deadline_seconds * 1000 if total_ms is None else total_ms
        self.reserve_ms = limits.terminal_reserve_seconds * 1000 if reserve_ms is None \
            else reserve_ms

    @property
    def deadline_ms(self) -> float:
        return self.t0_ms + self.total_ms

    @property
    def work_end_ms(self) -> float:
        return self.deadline_ms - self.reserve_ms

    def end(self, phase: str) -> float:
        if phase not in ("working", "terminal"):
            raise ValueError(phase)
        return self.work_end_ms if phase == "working" else self.deadline_ms

    def available_ms(self, phase: str) -> int:
        return math.floor(self.end(phase) - self.clock())

    def elapsed_ms(self) -> int:
        return max(0, math.floor(self.clock() - self.t0_ms))

    def budget_ms(self, phase: str, cap_ms: int, minimum_ms: int = MIN_DB_MS) -> int | None:
        value = min(cap_ms, self.available_ms(phase))
        return value if value >= minimum_ms else None


def connect_timeout_s(available_ms: int, cap_s: int) -> int | None:
    seconds = min(cap_s, available_ms // 1000)
    return seconds if seconds >= LIBPQ_MIN_EFFECTIVE_S else None


def single_host(url: str) -> bool:
    params = conninfo_to_dict(url)
    hosts = [h for h in (params.get("host") or "").split(",") if h]
    addresses = [h for h in (params.get("hostaddr") or "").split(",") if h]
    return len(hosts) <= 1 and len(addresses) <= 1


def open_connection(url: str, deadline: Deadline, phase: str,
                    limits: WorkflowLimits) -> psycopg.Connection:
    """The workflow connection. Refused (BudgetExhausted) when a whole-second connect timeout
    of at least 2 s does not fit; in the terminal phase the worst case must also leave the
    terminal start budget. Multi-host connection strings are refused outright."""
    if not single_host(url):
        raise ValueError("the workflow connection must name a single host")
    available = deadline.available_ms(phase)
    if phase == "terminal":
        available -= MIN_TERMINAL_START_MS
    seconds = connect_timeout_s(available, limits.db_wait_seconds)
    if seconds is None:
        raise BudgetExhausted("no time for a bounded connection")
    try:
        return psycopg.connect(url, row_factory=dict_row, autocommit=False,
                               connect_timeout=seconds)
    except psycopg.OperationalError:
        raise ConnectionLost("connection failed") from None


class BoundedTransaction:
    """One transaction on an open connection with one combined budget.

    execute() and commit() recompute `remaining = floor(min(tx_end, phase_end) - now)`; below
    MIN_DB_MS the transaction is rolled back (BudgetExhausted). Otherwise statement_timeout
    and lock_timeout are set to `remaining` milliseconds (SET LOCAL semantics) first.

    `owned=False` wraps a transaction someone else opened and will commit (the lazy
    recovery inside begin_investigation): statements are bounded the same way, commit and
    rollback are left to the owner."""

    def __init__(self, conn: psycopg.Connection, deadline: Deadline, phase: str, cap_ms: int,
                 *, owned: bool = True):
        minimum = MIN_TERMINAL_START_MS if phase == "terminal" else MIN_DB_MS
        budget = deadline.budget_ms(phase, cap_ms, minimum)
        if budget is None:
            raise BudgetExhausted(f"no {phase} budget")
        self.conn, self.deadline, self.phase, self.owned = conn, deadline, phase, owned
        self.tx_end = deadline.clock() + budget
        self.budgets: list[int] = []
        self.done = False

    def remaining_ms(self) -> int:
        return math.floor(min(self.tx_end, self.deadline.end(self.phase))
                          - self.deadline.clock())

    def _arm(self, cap_ms: int | None = None) -> None:
        remaining = self.remaining_ms()
        if cap_ms is not None:
            remaining = min(remaining, cap_ms)
        if remaining < MIN_DB_MS:
            self.rollback()
            raise BudgetExhausted("transaction budget spent")
        self.budgets.append(remaining)
        value = str(remaining)
        try:
            self.conn.execute("SELECT set_config('statement_timeout', %s, true),"
                              " set_config('lock_timeout', %s, true)", (value, value))
        except psycopg.Error as error:
            self._failed(error)

    def execute(self, query, params=(), *, cap_ms: int | None = None):
        self._arm(cap_ms)
        try:
            return self.conn.execute(query, params)
        except psycopg.Error as error:
            self._failed(error)

    def _failed(self, error: psycopg.Error):
        if self.conn.broken or self.conn.closed:
            self.done = True
            raise ConnectionLost("connection lost") from None
        self.rollback()
        if isinstance(error, (psycopg.errors.QueryCanceled, psycopg.errors.LockNotAvailable)):
            raise BudgetExhausted("statement or lock timeout") from None
        raise error

    def commit(self) -> None:
        if not self.owned:
            raise RuntimeError("an unowned transaction is committed by its owner")
        if self.conn.broken or self.conn.closed:
            self.done = True
            raise ConnectionLost("connection lost before COMMIT")
        self._arm()
        # PostgreSQL disables statement_timeout before commit processing (deferred triggers,
        # the commit record), so COMMIT itself is bounded by a client-side cancel request
        # sent when the remaining budget runs out. A cancel that arrives first makes the
        # server answer with an error (a known rollback); if the commit already completed,
        # the cancel has no effect and the reply is success.
        watchdog = threading.Timer(max(self.remaining_ms(), 0) / 1000, self._cancel)
        watchdog.daemon = True
        watchdog.start()
        try:
            self.conn.commit()
        except psycopg.Error as error:
            self.done = True
            if error.sqlstate is not None and not self.conn.broken:
                # The server answered COMMIT with an error: definitively rolled back.
                raise BudgetExhausted("COMMIT refused or cancelled by the server") from None
            raise CommitUncertain("no definitive COMMIT reply") from None
        finally:
            watchdog.cancel()
        self.done = True

    def _cancel(self) -> None:
        try:
            self.conn.cancel_safe(timeout=1.0)
        except Exception:  # the outcome is then decided by the COMMIT reply (or its absence)
            pass

    def rollback(self) -> None:
        if self.done or not self.owned:
            return
        self.done = True
        try:
            self.conn.rollback()
        except psycopg.Error:
            pass
