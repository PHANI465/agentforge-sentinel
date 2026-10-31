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
- one single-host workflow connection, connect_timeout in whole seconds >= 2;
- the client never waits past a transaction's end for a reply (R34): every statement,
  COMMIT and rollback runs on a short-lived operation thread, and the caller stops waiting
  at the end of its budget whether or not the server, or a cancel request, ever answers.

An operation still unanswered at its budget is abandoned. Its connection is quarantined:
never reused, and closed by the operation thread when that returns. Its socket is shut down
(not closed) so the blocked libpq wait ends promptly, and new workflows are refused while
quarantined operations reach the per-process limit (coordinator.run_workflow).

This bounds elapsed waiting on this process's clock. It does not prove that a COMMIT is
durable within the deadline or that the server notices a timeout instantly.
"""
from __future__ import annotations

import math
import socket
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
# COMMIT's cancel request is sent this long (at most half the COMMIT budget) before the
# client stops waiting, so that a server honouring it can answer inside the budget.
COMMIT_CANCEL_LEAD_MS = 150


def monotonic_ms() -> float:
    return time.monotonic() * 1000


class BudgetExhausted(Exception):
    """No positive budget is left for the next operation (nothing was sent for it), the
    server cancelled an operation at its timeout, or a statement had no reply within its
    budget (COMMIT was never sent). The transaction is known not committed."""


class ConnectionLost(Exception):
    """The connection broke before COMMIT was sent; the transaction is known not committed."""


class CommitUncertain(Exception):
    """COMMIT was sent but no definitive reply arrived: the outcome is unknown."""


class NoReply(Exception):
    """An operation was abandoned at its budget; its connection is quarantined."""


class Quarantine:
    """Abandoned database operations of this process. Each keeps its connection (strongly
    referenced here) until its operation thread returns and closes it, so a quarantined
    connection is never reused, nor closed underneath a running libpq call."""

    def __init__(self):
        self._lock = threading.Lock()
        self._held: dict[int, object] = {}

    def hold(self, conn) -> None:
        with self._lock:
            self._held[id(conn)] = conn

    def release(self, conn) -> None:
        with self._lock:
            if self._held.get(id(conn)) is conn:
                del self._held[id(conn)]

    def holds(self, conn) -> bool:
        with self._lock:
            return self._held.get(id(conn)) is conn

    def count(self) -> int:
        with self._lock:
            return len(self._held)


QUARANTINE = Quarantine()


def usable(conn) -> bool:
    """Open, unbroken, not quarantined and outside any transaction."""
    if conn is None or QUARANTINE.holds(conn) or conn.closed or conn.broken:
        return False
    return conn.info.transaction_status == psycopg.pq.TransactionStatus.IDLE


def discard(conn) -> None:
    """Close a connection the coordinator owns. A quarantined one is left to its operation
    thread, which closes it when the blocked call returns."""
    if conn is None or QUARANTINE.holds(conn):
        return
    try:
        conn.close()
    except Exception:
        pass


def _shutdown_socket(conn) -> None:
    """End a blocked libpq wait without closing, and so without freeing, its descriptor."""
    try:
        sock = socket.socket(fileno=conn.fileno())
    except Exception:
        return
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    finally:
        sock.detach()


def _cancel(conn, timeout_s: float) -> None:
    try:
        conn.cancel_safe(timeout=timeout_s)
    except Exception:  # the outcome is decided by the reply, or its absence, at the budget
        pass


def bounded_call(conn, operation: Callable, wait_ms: float,
                 cancel_after_ms: float | None = None):
    """Run `operation` on its own thread and wait at most `wait_ms` for it.

    With `cancel_after_ms`, a cancel request (itself bounded by the wait left) is sent if the
    operation is still running then; failed or acknowledged, the wait still ends at
    `wait_ms`. Unanswered by then, the operation is abandoned: the connection is quarantined
    and its socket shut down, and NoReply is raised. The operation thread then owns the
    connection and closes it when the call returns."""
    state = {"abandoned": False}
    box: dict = {}
    done = threading.Event()
    lock = threading.Lock()

    def work():
        try:
            box["value"] = operation()
        except BaseException as error:  # handed to the waiting caller
            box["error"] = error
        with lock:
            done.set()
            abandoned = state["abandoned"]
        if abandoned:
            try:
                conn.close()
            except Exception:
                pass
            QUARANTINE.release(conn)

    started = time.monotonic()

    def left_s() -> float:
        return max(wait_ms / 1000 - (time.monotonic() - started), 0.0)

    threading.Thread(target=work, name="sentinel-sql", daemon=True).start()
    if cancel_after_ms is not None and not done.wait(max(cancel_after_ms, 0) / 1000) \
            and left_s() > 0:
        threading.Thread(target=_cancel, args=(conn, left_s()), name="sentinel-sql-cancel",
                         daemon=True).start()
    done.wait(left_s())
    with lock:
        if not done.is_set():
            state["abandoned"] = True
            QUARANTINE.hold(conn)
    if state["abandoned"]:
        _shutdown_socket(conn)
        raise NoReply()
    if "error" in box:
        raise box["error"]
    return box.get("value")


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
    """One owned transaction on an open connection with one combined budget.

    execute() and commit() recompute `remaining = floor(min(tx_end, phase_end) - now)`; below
    MIN_DB_MS the transaction is rolled back (BudgetExhausted). Otherwise statement_timeout
    and lock_timeout are set to `remaining` milliseconds (SET LOCAL semantics) first, and the
    client waits at most `remaining` for each reply (bounded_call). A statement unanswered
    at its budget is BudgetExhausted with the connection quarantined (COMMIT was never sent,
    so nothing committed); an unanswered COMMIT is CommitUncertain."""

    def __init__(self, conn: psycopg.Connection, deadline: Deadline, phase: str, cap_ms: int):
        minimum = MIN_TERMINAL_START_MS if phase == "terminal" else MIN_DB_MS
        budget = deadline.budget_ms(phase, cap_ms, minimum)
        if budget is None:
            raise BudgetExhausted(f"no {phase} budget")
        self.conn, self.deadline, self.phase, self.cap_ms = conn, deadline, phase, cap_ms
        self.tx_end = deadline.clock() + budget
        self.budgets: list[int] = []
        self.done = False

    def remaining_ms(self) -> int:
        return math.floor(min(self.tx_end, self.deadline.end(self.phase))
                          - self.deadline.clock())

    def _call(self, operation):
        try:
            return bounded_call(self.conn, operation, max(self.remaining_ms(), 0))
        except NoReply:
            self.done = True
            raise BudgetExhausted("no reply within the transaction budget") from None

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
            self._call(lambda: self.conn.execute(
                "SELECT set_config('statement_timeout', %s, true),"
                " set_config('lock_timeout', %s, true)", (value, value)))
        except psycopg.Error as error:
            self._failed(error)

    def execute(self, query, params=(), *, cap_ms: int | None = None):
        self._arm(cap_ms)
        try:
            return self._call(lambda: self.conn.execute(query, params))
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
        if self.conn.broken or self.conn.closed:
            self.done = True
            raise ConnectionLost("connection lost before COMMIT")
        self._arm()
        # PostgreSQL disables statement_timeout before commit processing (deferred triggers,
        # the commit record), so COMMIT is bounded on the client: a cancel request goes out
        # shortly before the budget ends, and the wait ends at the budget whatever becomes of
        # that request. A server error reply is a known rollback; no reply is uncertain.
        remaining = max(self.remaining_ms(), 0)
        self.done = True
        try:
            bounded_call(self.conn, self.conn.commit, remaining,
                         remaining - min(COMMIT_CANCEL_LEAD_MS, remaining // 2))
        except NoReply:
            raise CommitUncertain("no COMMIT reply within the budget") from None
        except psycopg.Error as error:
            if error.sqlstate is not None and not self.conn.broken:
                # The server answered COMMIT with an error: definitively rolled back.
                raise BudgetExhausted("COMMIT refused or cancelled by the server") from None
            raise CommitUncertain("no definitive COMMIT reply") from None

    def rollback(self) -> None:
        """Send ROLLBACK, waiting at most the cap and never past the phase end. With no time
        left, or no reply, the connection is closed (or quarantined) instead, which also ends
        the transaction on the server; the coordinator then replaces it (usable() is False)."""
        if self.done:
            return
        self.done = True
        wait_ms = min(self.cap_ms, self.deadline.available_ms(self.phase))
        if wait_ms <= 0:
            discard(self.conn)
            return
        try:
            bounded_call(self.conn, self.conn.rollback, wait_ms)
        except NoReply:
            pass
        except psycopg.Error:
            discard(self.conn)
