"""Process-local admission and provider-call leases (G3A-design section 3.1).

- Workflow slot (max_live_workflows_per_process): taken non-blocking before the claim; the
  request owns it and releases it in `finally` on every path.
- Call slot (max_outstanding_calls_per_process): taken non-blocking immediately before a
  live role call is submitted; owned by the worker's future and released by a done-callback
  when the worker thread actually returns, never when the coordinator stops waiting. A
  timed-out (late) worker therefore keeps its slot.

Every workflow takes the workflow slot (G3A-design section 3: at most one admitted workflow
per process). Deterministic adapters take no call slots (no provider, no late worker), so
only a live workflow also needs a free call slot to be admitted. Nothing here cancels provider work or persists anything; leases
vanish with the process, together with its worker threads.
"""
from __future__ import annotations

import logging
import threading
from concurrent import futures
from typing import Callable

from sentinel.observability import emit

LOG = logging.getLogger("sentinel.agents")


class CapacityExhausted(Exception):
    """Admission or a call slot is unavailable; nothing was started."""


class AgentCapacity:
    def __init__(self, max_workflows: int, max_calls: int):
        if max_calls < max_workflows or max_workflows < 1:
            raise ValueError("every admitted workflow needs at least one call slot")
        self.max_workflows, self.max_calls = max_workflows, max_calls
        self._lock = threading.Lock()
        self._workflows = 0
        self._calls = 0
        self.peak_calls = 0

    def snapshot(self) -> dict:
        with self._lock:
            return {"workflows": self._workflows, "calls": self._calls,
                    "peak_calls": self.peak_calls}

    def admit(self, live: bool) -> "Admission":
        """A workflow slot, plus at least one free call slot for a live workflow."""
        with self._lock:
            if self._workflows >= self.max_workflows or (live and self._calls >= self.max_calls):
                raise CapacityExhausted("agent capacity exhausted")
            self._workflows += 1
        return Admission(self, held=True)

    def _release_workflow(self) -> None:
        with self._lock:
            self._workflows -= 1

    def reserve_call(self) -> "CallSlot":
        """Take a call slot (non-blocking) before the role run is recorded; CapacityExhausted
        if every slot is held (possibly by late workers of other workflows)."""
        with self._lock:
            if self._calls >= self.max_calls:
                raise CapacityExhausted("no call slot")
            self._calls += 1
            self.peak_calls = max(self.peak_calls, self._calls)
        return CallSlot(self)

    def _release_call(self) -> None:
        with self._lock:
            self._calls -= 1


class CallSlot:
    """Released exactly once: by cancel() if no worker was started, otherwise by the worker
    future's done-callback when the thread actually returns."""

    def __init__(self, capacity: AgentCapacity):
        self.capacity = capacity
        self._state = "reserved"

    def cancel(self) -> None:
        if self._state == "reserved":
            self._state = "released"
            self.capacity._release_call()

    def start(self, fn: Callable, *args,
              on_return: Callable[[futures.Future], None] | None = None) -> futures.Future:
        if self._state != "reserved":
            raise RuntimeError("call slot already used")
        pool = futures.ThreadPoolExecutor(1, thread_name_prefix="agent-role")
        try:
            future = pool.submit(fn, *args)
        except BaseException:
            self.cancel()
            raise
        finally:
            pool.shutdown(wait=False)
        self._state = "running"

        def returned(done: futures.Future) -> None:
            self._state = "released"
            self.capacity._release_call()
            if on_return is not None:
                on_return(done)
        future.add_done_callback(returned)
        return future


class Admission:
    def __init__(self, capacity: AgentCapacity, held: bool):
        self.capacity, self.held = capacity, held

    def release(self) -> None:
        if self.held:
            self.held = False
            self.capacity._release_workflow()


def late_worker_event(workflow_id: str, role: str, attempt: int, seconds: float) -> None:
    emit(LOG, "agent_worker_returned", logging.INFO, workflow_id=workflow_id, role=role,
         attempt=attempt, seconds=round(seconds, 3))
