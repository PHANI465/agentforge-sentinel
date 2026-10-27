"""N5/N6: the browser stack stops only its own API, completely, and sees exited processes.

N5 - a recorded API whose identity still matches gets a graceful termination request; if it
does not exit within a bound (a uvicorn factory blocked after its TERM handler is installed),
the same identity-verified, separately launched process group is killed. A changed or missing
identity, or a group that is not the API's own, is refused with recovery kept.

N6 - an exited child that its parent has not yet waited for (Linux /proc state Z; on Windows
an exited process whose handle is still open) is not a running API.

Stand-ins are real test-owned processes. They print "ready" once their handlers are
installed and "term" when a termination request arrives, so the path taken is shown by what
the process saw and how it ended, not only by elapsed time. Every stand-in is stopped by its
own handle in a finally block."""
import contextlib
import os
import signal
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "support"))

import browser_stack  # noqa: E402
from browser_stack import Stack, StackError, process_start_time  # noqa: E402

POSIX = os.name != "nt"
COOPERATIVE = "import time;print('ready',flush=True);time.sleep(600)"
# Like uvicorn blocked in an app factory: its TERM handler only records the request.
RESISTANT = textwrap.dedent("""
    import signal, sys, time
    def on_term(*_):
        print("term", flush=True)
    signal.signal(signal.SIGTERM, on_term)
    print("ready", flush=True)
    while True:
        time.sleep(600)
""")
OWN_GROUP = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" \
    else {"start_new_session": True}


@contextlib.contextmanager
def stand_in(code: str, own_group: bool = True):
    process = subprocess.Popen([sys.executable, "-c", code], stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, text=True,
                               **(OWN_GROUP if own_group else {}))
    try:
        assert process.stdout.readline().strip() == "ready"
        yield process
    finally:  # our own child, by handle
        if process.poll() is None:
            process.kill()
        process.wait(30)


def recorded(tmp_path: Path, process: subprocess.Popen) -> Stack:
    """A stack whose recorded API is `process`, as a later `stop`/`restart-api` sees it."""
    stack = Stack(tmp_path / f"{browser_stack.PREFIX}lifecycle", {"api": {
        "pid": process.pid, "start_time": process_start_time(process.pid), "port": None}})
    assert stack.manifest["api"]["start_time"] is not None
    return stack


def gone(process: subprocess.Popen) -> bool:
    return process_start_time(process.pid) is None


@pytest.fixture
def fast(monkeypatch):
    monkeypatch.setattr(browser_stack, "TERM_GRACE_SECONDS", 2, raising=False)


# ---- N5 ----------------------------------------------------------------------------------

def test_cooperative_api_exits_on_the_graceful_request(tmp_path, fast):
    with stand_in(COOPERATIVE) as process:
        stack = recorded(tmp_path, process)
        stack.stop_api()
        assert gone(process) and stack.manifest["api"]["pid"] is None
        assert process.wait(10) == (-signal.SIGTERM if POSIX else 1)  # not escalated


def test_term_resistant_api_is_escalated_and_verified_stopped(tmp_path, fast):
    with stand_in(RESISTANT) as process:
        stack = recorded(tmp_path, process)
        stack.stop_api()
        assert gone(process) and stack.manifest["api"]["pid"] is None
        if POSIX:  # it received and survived the request, then was killed
            assert process.stdout.readline().strip() == "term"
            assert process.wait(10) == -signal.SIGKILL
        else:  # taskkill /F terminates at once
            assert process.wait(10) == 1


def test_identity_change_before_escalation_is_refused(tmp_path, fast, monkeypatch):
    sent = []
    real_killpg = getattr(os, "killpg", None)

    def recording_killpg(pgid, sig):
        sent.append(sig)
        if sig != signal.SIGTERM:
            raise AssertionError("no escalation after the identity changed")
        real_killpg(pgid, sig)
    if POSIX:
        monkeypatch.setattr(browser_stack.os, "killpg", recording_killpg)
    else:
        monkeypatch.setattr(browser_stack.subprocess, "run",
                            lambda *a, **k: sent.append(a) or pytest.fail("no taskkill"))
    with stand_in(RESISTANT) as process:
        stack = recorded(tmp_path, process)
        real_stamp = browser_stack.process_start_time
        checks = []

        def stamp(pid):
            # The PID shows another identity at the next signalling boundary: POSIX once the
            # graceful request was sent; Windows (one forced step) right after the caller's
            # check, at the helper's own re-check before taskkill.
            if pid == process.pid:
                checks.append(pid)
                if sent if POSIX else len(checks) > 1:
                    return stack.manifest["api"]["start_time"] + 1
            return real_stamp(pid)
        monkeypatch.setattr(browser_stack, "process_start_time", stamp)
        with pytest.raises(StackError, match="identity"):
            stack.stop_api()
        assert stack.manifest["api"]["pid"] == process.pid  # recovery record kept
        assert sent == ([signal.SIGTERM] if POSIX else [])
        assert process.poll() is None  # nothing destructive reached it


@pytest.mark.parametrize("case", ["missing-identity", "foreign-group"])
def test_unverifiable_identity_or_group_is_refused_without_signals(tmp_path, fast, monkeypatch,
                                                                   case):
    sent = []
    monkeypatch.setattr(browser_stack.os, "killpg", lambda *a: sent.append(a), raising=False)
    monkeypatch.setattr(browser_stack.subprocess, "run", lambda *a, **k: sent.append(a))
    own_group = case != "foreign-group" or not POSIX  # POSIX: shares the test's own group
    with stand_in(RESISTANT, own_group=own_group) as process:
        stack = recorded(tmp_path, process)
        stack._process = process  # even the launching handle does not override identity
        if case == "missing-identity" or not POSIX:
            stack.manifest["api"]["start_time"] = None
        with pytest.raises(StackError):
            stack.stop_api()
        assert sent == [] and process.poll() is None
        assert stack.manifest["api"]["pid"] == process.pid


# ---- N6 ----------------------------------------------------------------------------------

def test_an_exited_unreaped_child_is_not_running():
    process = subprocess.Popen([sys.executable, "-c", "pass"])
    try:
        stamp = None
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:  # observe, never wait: the child stays unreaped
            if POSIX:
                try:
                    stat = Path(f"/proc/{process.pid}/stat").read_text()
                except OSError:
                    break
                if stat.rsplit(")", 1)[1].split()[0] == "Z":
                    stamp = "Z"
                    break
            else:
                import ctypes
                handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, process.pid)
                code = ctypes.c_ulong()
                ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
                ctypes.windll.kernel32.CloseHandle(handle)
                if code.value != 259:
                    stamp = "exited"
                    break
            time.sleep(0.05)
        assert stamp is not None, "the child never reached the exited-but-unreaped state"
        assert process.returncode is None  # not waited for yet
        assert process_start_time(process.pid) is None
    finally:
        process.wait(30)


def test_running_and_disappeared_processes_keep_their_identity_semantics():
    with stand_in(COOPERATIVE) as process:
        stamp = process_start_time(process.pid)
        assert isinstance(stamp, int) and process_start_time(process.pid) == stamp
    assert process_start_time(process.pid) is None  # reaped: gone
