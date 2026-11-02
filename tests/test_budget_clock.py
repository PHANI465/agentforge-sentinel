"""G3C native diagnosis: bounded_call's limits are measured on the monotonic clock.

On CPython builds without sem_clockwait (for example the portable interpreters uv installs on
Linux), a timed threading wait (Event.wait, Condition.wait, Lock.acquire with a timeout)
expires on CLOCK_REALTIME. On the WSL2 host used for the native gates, CLOCK_REALTIME steps
by about 2.5 s (mostly backwards, sometimes forwards; docs/agents/G3C-native-clock-diagnosis.md).
A backward step made a 2 s COMMIT bound take 3.46 s; a forward step cancels a COMMIT early.

These tests reproduce such a host deterministically, without touching the system clock: only
the `threading` that budget.py sees is replaced, by one whose timed waits are skewed as a
stepping CLOCK_REALTIME would skew them. Every other thread and wait is the real one.
"""
import threading
import time
import types

import psycopg
import pytest

from sentinel.agents import budget
from sentinel.contracts.agents import WorkflowLimits

STEP_S = 1.5  # a realtime step during the wait (the observed host steps are about 2.5 s)


def skewed_threading(direction: str):
    """`threading` as budget.py sees it on a host whose realtime clock steps during a timed
    wait: backwards, a timed wait overruns by STEP_S; forwards, it ends STEP_S early."""

    def timed(wait):
        def call(self, timeout=None):
            if timeout is None:
                return wait(self)
            if direction == "backward":
                return wait(self, timeout + STEP_S)
            return wait(self, max(timeout - STEP_S, 0))
        return call

    class Event(threading.Event):
        wait = timed(threading.Event.wait)

    class Condition(threading.Condition):
        wait = timed(threading.Condition.wait)

    return types.SimpleNamespace(Thread=threading.Thread, Lock=threading.Lock,
                                 RLock=threading.RLock, Event=Event, Condition=Condition)


class Stalled:
    """A connection whose COMMIT or statement is answered after `reply_s` (never, if None)."""
    broken = closed = False

    def __init__(self, reply_s=None, stall="commit"):
        self.reply_s, self.stall = reply_s, stall
        self.release, self.cancelled, self.closed_by = (threading.Event(), threading.Event(),
                                                        threading.Event())

    def _answer(self):
        if self.reply_s is None:
            self.release.wait(30)
            raise psycopg.OperationalError("test-owned unanswered operation")
        self.release.wait(self.reply_s)

    def execute(self, query, params=()):
        if self.stall == "statement" and "set_config" not in query:
            self._answer()

    def commit(self):
        if self.stall == "commit":
            self._answer()

    def rollback(self):
        pass

    def cancel_safe(self, timeout):
        self.cancelled.set()

    def close(self):
        self.closed = True
        self.closed_by.set()


def transaction(conn, budget_ms):
    deadline = budget.Deadline(WorkflowLimits(), total_ms=budget_ms + 4000, reserve_ms=0)
    return budget.BoundedTransaction(conn, deadline, "terminal", budget_ms)


@pytest.fixture
def stepping(monkeypatch):
    def install(direction):
        monkeypatch.setattr(budget, "threading", skewed_threading(direction))
    return install


@pytest.mark.parametrize("stall", ["commit", "statement"])
def test_a_backward_realtime_step_does_not_stretch_the_budget(stepping, stall):
    """Native failure 1 (the 2 s terminal COMMIT bound took 2.95 s) and the 1 s statement
    bound that took 3.6 s: an unanswered operation still ends at its monotonic budget."""
    stepping("backward")
    conn = Stalled(stall=stall)
    tx = transaction(conn, 1000)
    started = time.monotonic()
    try:
        expected = budget.CommitUncertain if stall == "commit" else budget.BudgetExhausted
        with pytest.raises(expected):
            tx.commit() if stall == "commit" else tx.execute("SELECT 1")
        assert time.monotonic() - started < 1.2  # the same bound as the existing tests
        assert budget.QUARANTINE.holds(conn)
    finally:
        conn.release.set()
    assert conn.closed_by.wait(5)


def test_a_forward_realtime_step_does_not_cancel_a_commit_early(stepping):
    """Native failure 2's mechanism: recovery's COMMIT (3 s of deferred work, 5 s budget,
    cancel at about 4 s) was cancelled early and became a known rollback ("conflict")."""
    stepping("forward")
    conn = Stalled(reply_s=0.6)  # COMMIT answers after 0.6 s; the cancel is due at 1.0 s
    tx = transaction(conn, 2000)
    tx.commit()  # committed, not cancelled
    assert not conn.cancelled.is_set()
    assert not budget.QUARANTINE.holds(conn)


def test_a_forward_realtime_step_does_not_end_the_wait_early(stepping):
    """A forward step must not make an answered-in-time operation look unanswered."""
    stepping("forward")
    conn = Stalled(reply_s=0.4, stall="statement")
    tx = transaction(conn, 1500)
    started = time.monotonic()
    tx.execute("SELECT 1")  # answered at 0.4 s, inside the 1.5 s budget
    assert 0.35 <= time.monotonic() - started < 1.0
    assert not budget.QUARANTINE.holds(conn)


def test_waits_still_end_promptly_when_answered():
    """The monotonic wait adds no material latency to a quick reply (real threading)."""
    conn = Stalled(reply_s=0.0, stall="statement")
    tx = transaction(conn, 1000)
    started = time.monotonic()
    for _ in range(50):
        tx.execute("SELECT 1")
    assert (time.monotonic() - started) / 50 < 0.02
