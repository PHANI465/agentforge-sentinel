"""Waits bounded on the monotonic clock (G3C native diagnosis; R40).

A bound in this service is never a positive timed threading or Future wait. On the observed
uv CPython 3.11.14 build (HAVE_SEM_CLOCKWAIT = 0), those expire on CLOCK_REALTIME, which
host time sync stepped by about 2.5 s mid-wait: a backward step overran a bound and a forward
one ended a wait early (docs/agents/G3C-native-clock-diagnosis.md). time.sleep waits on the
monotonic clock (CLOCK_MONOTONIC clock_nanosleep on that build). Readiness is checked at
least every POLL_MAX_S; that is the polling interval, not a guaranteed observed latency under
OS scheduling.
"""
from __future__ import annotations

import time
from concurrent import futures
from typing import Callable

POLL_MIN_S, POLL_MAX_S = 0.0002, 0.005


def wait_until(ready: Callable[[], bool], left_s: Callable[[], float]) -> bool:
    """Wait until ready() or until left_s() reaches 0; True if ready."""
    pause = POLL_MIN_S
    while not ready():
        remaining = left_s()
        if remaining <= 0:
            return ready()
        time.sleep(min(pause, remaining))
        pause = min(pause * 2, POLL_MAX_S)
    return True


def wait_future(future: futures.Future, timeout_s: float) -> bool:
    """Wait at most `timeout_s` of monotonic time for `future` to finish; True if it did.
    Collect a finished future with future.result(timeout=0), which does not wait."""
    end = time.monotonic() + max(timeout_s, 0)
    return wait_until(future.done, lambda: end - time.monotonic())
