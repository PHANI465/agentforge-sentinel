"""G3B review fix R37: one owner for a connection's whole lifetime during a bounded call.

The SQL worker, a COMMIT cancel helper and the caller's socket shutdown all use the same
connection. It must not be handed back for reuse, closed, or released from the quarantine
until every one of them has finished. Shutdown must only ever reach the connection's own
socket, never a descriptor that was closed and reused.

Connections here are test-owned stand-ins; the descriptor case uses real test-owned
socket pairs. Every ordering is forced with events, and every thread and socket is
released.
"""
import os
import socket
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "support"))

from sentinel.agents import budget  # noqa: E402
from sentinel.contracts.agents import WorkflowLimits  # noqa: E402


def until(condition, seconds=10.0):
    """Wait for a condition on test-owned state, checking every 20 ms, for a bounded time."""
    end = time.monotonic() + seconds
    while not condition():
        if time.monotonic() > end:
            return False
        threading.Event().wait(0.02)
    return True


class Conn:
    """A stand-in connection. Its COMMIT and cancel request are each held by an event;
    close() records how often it ran and whether a cancel request was still active."""
    broken = False

    def __init__(self):
        self.closed = False
        self.closes = 0
        self.active = "COMMIT"
        self.affected = []
        self.commit_gate, self.cancel_gate = threading.Event(), threading.Event()
        self.cancel_started, self.cancel_done = threading.Event(), threading.Event()
        self.commit_returned, self.closed_event = threading.Event(), threading.Event()
        self.cancel_active = False
        self.closed_during_cancel = False
        self.hold_cancel_until_close = False

    def execute(self, query, params=()):
        return None

    def commit(self):
        try:
            assert self.commit_gate.wait(10)
            return None
        finally:
            self.commit_returned.set()

    def rollback(self):
        return None

    def cancel_safe(self, timeout):
        self.cancel_active = True
        self.cancel_started.set()
        try:
            assert self.cancel_gate.wait(10)
            if self.hold_cancel_until_close:
                self.closed_event.wait(2)  # a close now would be under an active cancel
            self.affected.append(self.active)
        finally:
            self.cancel_active = False
            self.cancel_done.set()

    def close(self):
        self.closes += 1
        self.closed_during_cancel |= self.cancel_active
        self.closed = True
        self.closed_event.set()


def transaction(conn, budget_ms=1000):
    deadline = budget.Deadline(WorkflowLimits(), total_ms=budget_ms + 4000, reserve_ms=0)
    return budget.BoundedTransaction(conn, deadline, "terminal", budget_ms)


def release(conn):
    conn.commit_gate.set()
    conn.cancel_gate.set()


def test_a_confirmed_commit_is_handed_back_only_after_its_canceller_finished():
    """Positive safe reuse: the COMMIT reply arrives while its cancel request is under
    way; the call waits for that helper, then returns the confirmed result on a connection
    nothing else can still act on."""
    conn = Conn()

    def commit_once_cancel_started():
        assert conn.cancel_started.wait(10)
        conn.cancel_gate.set()  # the helper may finish now; the reply is confirmed
        return "COMMIT confirmed"
    try:
        result = budget.bounded_call(conn, commit_once_cancel_started, 2000, 50)
        assert result == "COMMIT confirmed"
        assert conn.cancel_done.is_set()  # no helper outlives the hand-back
        assert not budget.QUARANTINE.holds(conn) and conn.closes == 0  # safe to reuse
        conn.active = "next statement"
        assert conn.affected == ["COMMIT"]  # the cancel only ever met its own COMMIT
    finally:
        release(conn)


def test_a_canceller_outliving_the_budget_retires_the_connection():
    """The COMMIT is confirmed, but its cancel request is still held at the budget: the
    confirmed meaning stands, the connection is retired (quarantined, not reusable) and
    closed exactly once when the helper finally leaves."""
    conn = Conn()
    tx = transaction(conn)

    def confirm_after_cancel_started():
        assert conn.cancel_started.wait(10)
        conn.commit_gate.set()
    conn.commit = lambda: (confirm_after_cancel_started(), Conn.commit(conn))[1]
    started = time.monotonic()
    try:
        tx.commit()  # a confirmed COMMIT: no CommitUncertain, no BudgetExhausted
        assert time.monotonic() - started < 1.3  # finite: the helper was not awaited
        assert not conn.cancel_done.is_set()
        assert budget.QUARANTINE.holds(conn)  # retired: never handed out for reuse
        assert not budget.usable(conn)  # so Run.connection() replaces it
        assert conn.closes == 0  # nobody closes it under the active cancel request
        if budget.usable(conn):  # the coordinator's reuse rule (the review's probe A)
            conn.active = "next statement"
    finally:
        release(conn)
    assert conn.cancel_done.wait(10)
    assert conn.affected == ["COMMIT"]  # the late cancel never met a later statement
    assert until(lambda: conn.closes == 1 and not budget.QUARANTINE.holds(conn))
    assert not conn.closed_during_cancel
    budget.discard(conn)  # the coordinator's own cleanup never closes it twice
    assert conn.closes == 1


def test_an_abandoned_commit_closes_once_after_its_last_helper():
    """No reply and a cancel request still active: the SQL worker returning first must not
    close the connection while the cancel request can still act on it."""
    conn = Conn()
    conn.hold_cancel_until_close = True
    tx = transaction(conn)
    try:
        with pytest.raises(budget.CommitUncertain):
            tx.commit()
        assert budget.QUARANTINE.holds(conn) and conn.cancel_started.is_set()
        conn.commit_gate.set()  # the late SQL worker returns first ...
        assert conn.commit_returned.wait(10)
        conn.cancel_gate.set()  # ... then the cancel request finishes
        assert conn.cancel_done.wait(10)
    finally:
        release(conn)
    assert until(lambda: conn.closes == 1 and not budget.QUARANTINE.holds(conn))
    assert not conn.closed_during_cancel  # closed only after its last helper left
    budget.discard(conn)
    assert conn.closes == 1


def test_shutdown_reaches_only_its_own_socket_never_a_reused_descriptor(monkeypatch):
    """The late SQL worker closes the connection and its descriptor is reused before the
    caller's shutdown runs. Shutdown must still reach the original socket, never the
    descriptor's new owner. POSIX reuses the descriptor for real (os.dup2 of a test-owned
    socket); elsewhere the reuse is intercepted: no socket object may be built on the
    original descriptor after it was closed."""
    local, local_peer = socket.socketpair()
    foreign, foreign_peer = socket.socketpair()
    descriptor = local.fileno()
    real_reuse = os.name == "posix"
    operation_started, operation_gate = threading.Event(), threading.Event()
    reused, closes = threading.Event(), []
    built_on_closed_descriptor = []
    original_socket = socket.socket

    class SocketConn:
        broken = closed = False

        def fileno(self):
            return descriptor

        def close(self):
            closes.append(1)
            self.closed = True
            local.close()
            if real_reuse:  # only our own foreign socket takes the freed descriptor
                os.dup2(foreign.fileno(), descriptor)
            reused.set()

    def gated_socket(*args, **kwargs):
        fileno = kwargs.get("fileno", args[3] if len(args) > 3 else None)
        if operation_started.is_set():  # a shutdown after the call was abandoned
            operation_gate.set()  # let the late worker return, close and reuse ...
            assert reused.wait(10)  # ... before this socket object is built
        if reused.is_set() and fileno == descriptor:
            built_on_closed_descriptor.append(fileno)
        return original_socket(*args, **kwargs)
    monkeypatch.setattr(budget.socket, "socket", gated_socket)
    conn = SocketConn()

    def late_operation():
        operation_started.set()
        assert operation_gate.wait(10)
        return "late result"
    try:
        with pytest.raises(budget.NoReply):
            budget.bounded_call(conn, late_operation, 50)
        operation_gate.set()
        assert reused.wait(10)
        foreign_peer.settimeout(0.2)
        try:
            foreign_eof = foreign_peer.recv(1) == b""
        except socket.timeout:
            foreign_eof = False
        local_peer.settimeout(5)
        local_eof = local_peer.recv(1) == b""
    finally:
        monkeypatch.undo()
        operation_gate.set()
        reused.wait(10)
        if real_reuse and closes:
            os.close(descriptor)
        for sock in (local, local_peer, foreign, foreign_peer):
            sock.close()
    assert not foreign_eof  # the descriptor's new owner was never shut down
    assert not built_on_closed_descriptor
    assert local_eof  # the shutdown did reach the connection's own socket
    assert until(lambda: not budget.QUARANTINE.holds(conn)) and closes == [1]
