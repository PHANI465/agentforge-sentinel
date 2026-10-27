"""R29/R30: an API process group that cannot be shown empty keeps the browser stack's
recovery state on every retry, including after a fresh manifest load.

R29 - the API leader has exited but a member of its group lives on. A first stop refuses;
a later stop (a new Stack.load, as the CLI does) must not take the leader's disappearance or
a closed port as proof that the group is gone.

R30 - group membership that cannot be read (permission, I/O error, malformed /proc stat) is
unknown, never an empty group; only an entry that really disappeared is skipped.

Processes, signals and the helper-owned state directory are real (native). R30's faults are
injected narrowly: only reads of one live member's /proc stat fail; the stale enumeration
entry is a really exited, reaped process. Each test stops only its own processes, verified
by handle or by pid plus start stamp, in finally."""
import errno
import json
import os
import secrets
import signal
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "support"))

import browser_stack  # noqa: E402
from browser_stack import Stack, process_start_time  # noqa: E402
from sentinel import devdb  # noqa: E402

POSIX = os.name != "nt"
DUMMY_TOKEN = "DUMMY_TOKEN_NOT_REAL_2930"
OWN_GROUP = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" \
    else {"start_new_session": True}
# The leader exits on the graceful request; a member of its group ignores it.
SURVIVOR = textwrap.dedent("""
    import subprocess, sys, time
    member = subprocess.Popen([sys.executable, "-c",
        "import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);"
        "print('ready',flush=True);time.sleep(600)"], stdout=subprocess.PIPE, text=True)
    member.stdout.readline()
    print(member.pid, flush=True)
    print("ready", flush=True)
    time.sleep(600)
""")


def owned_state(parent: Path, api: dict) -> Path:
    """A helper-owned state directory (marker + v2 manifest, no database files, so no
    PostgreSQL command runs) whose recorded API is `api`."""
    directory = Path(os.path.realpath(tempfile.mkdtemp(prefix=browser_stack.PREFIX,
                                                       dir=parent)))
    owner, where = secrets.token_hex(16), browser_stack.canonical(directory)
    (directory / browser_stack.MARKER).write_text(json.dumps({"owner": owner,
                                                              "state_dir": where}))
    manifest = {"version": browser_stack.MANIFEST_VERSION, "app": browser_stack.DEFAULT_APP,
                "owner": owner, "state_dir": where,
                "database": {"port": 1, "name": "browser", "started": False},
                "api": api, "tokens": {"analyst": DUMMY_TOKEN}}
    (directory / "stack.json").write_text(json.dumps(manifest))
    return directory


@pytest.fixture
def group(tmp_path, monkeypatch):
    """A real API-like group (leader + TERM-ignoring member) recorded in owned state; the
    signals the helper sends are recorded (and delivered)."""
    monkeypatch.setattr(browser_stack, "TERM_GRACE_SECONDS", 2)
    leader = subprocess.Popen([sys.executable, "-c", SURVIVOR], stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, text=True, **OWN_GROUP)
    member = int(leader.stdout.readline())
    member_stamp = None
    try:
        assert leader.stdout.readline().strip() == "ready"
        member_stamp = process_start_time(member)
        assert member_stamp
        sent = []
        if POSIX:
            real_killpg = os.killpg
            monkeypatch.setattr(browser_stack.os, "killpg",
                                lambda pgid, sig: sent.append((pgid, sig)) or real_killpg(pgid,
                                                                                          sig))
        canary = tmp_path / "unrelated" / "canary.txt"
        canary.parent.mkdir()
        canary.write_text("must survive")
        directory = owned_state(tmp_path, {"port": devdb.free_port(), "pid": leader.pid,
                                           "start_time": process_start_time(leader.pid)})
        yield {"leader": leader, "member": member, "member_stamp": member_stamp,
               "sent": sent, "dir": directory, "canary": canary}
    finally:  # our own processes: the leader by handle, the member by verified identity
        if leader.poll() is None:
            leader.kill()
        leader.wait(30)
        release(member, member_stamp)


def stamp_of(pid: int):
    """The test's own view of a start stamp, read with plain open() so that R30's injected
    Path.read_text fault never hides the member from the test itself."""
    if not POSIX:
        return process_start_time(pid)
    try:
        with open(f"/proc/{pid}/stat") as stat:
            fields = stat.read().rsplit(")", 1)[1].split()
    except FileNotFoundError:
        return None
    return None if fields[0] in ("Z", "X") else int(fields[19])


def release(member: int, stamp) -> None:
    """Stop the test's own member, only while its pid still carries its start stamp."""
    if stamp and stamp_of(member) == stamp:
        if POSIX:
            os.kill(member, signal.SIGKILL)
        else:
            subprocess.run(["taskkill", "/PID", str(member), "/F"], capture_output=True)
    assert browser_stack.wait_until(lambda: stamp_of(member) != stamp, 15)


def stop_fresh(directory: Path) -> dict:
    return Stack.load(directory / "stack.json").stop()  # a new load, as the CLI does


def assert_kept(g: dict, result: dict, capsys) -> None:
    """Refused safely: recovery state intact and loadable, member untouched, no leak."""
    assert result["ok"] is False and result["api_stopped"] is False
    assert result["state_removed"] is False
    again = Stack.load(g["dir"] / "stack.json")
    assert (g["dir"] / browser_stack.MARKER).is_file()
    assert again.manifest["tokens"] == {"analyst": DUMMY_TOKEN}
    assert again.manifest["api"]["pid"] == g["leader"].pid
    assert stamp_of(g["member"]) == g["member_stamp"]
    assert DUMMY_TOKEN not in json.dumps(result) and DUMMY_TOKEN not in capsys.readouterr().out


def assert_finished(g: dict, capsys) -> None:
    result = stop_fresh(g["dir"])
    assert result == {"ok": True, "api_stopped": True, "database_stopped": True,
                      "state_removed": True, "errors": []}
    assert not g["dir"].exists() and g["canary"].read_text() == "must survive"
    assert DUMMY_TOKEN not in capsys.readouterr().out


# ---- R29 -----------------------------------------------------------------------------------

@pytest.mark.parametrize("start", ["stop-ends-leader", "leader-already-exited"])
def test_r29_unresolved_group_survives_fresh_reload_retries(group, capsys, start):
    g = group
    if start == "leader-already-exited":  # no live handle and no stop involved: it just died
        g["leader"].terminate()
        g["leader"].wait(15)
    first = stop_fresh(g["dir"])
    if not POSIX:  # the forced tree kill takes leader and member together
        if start == "stop-ends-leader":
            assert first["ok"] is True and not g["dir"].exists()
            assert browser_stack.wait_until(lambda: process_start_time(g["member"]) is None, 15)
        assert first["state_removed"] is (not g["dir"].exists())
        return
    assert_kept(g, first, capsys)
    assert any("group" in e for e in first["errors"])
    signalled = list(g["sent"])
    assert signalled == ([(g["leader"].pid, signal.SIGTERM)] if start == "stop-ends-leader"
                         else [])
    for _ in range(2):  # fresh-load retries keep refusing and send nothing
        assert_kept(g, stop_fresh(g["dir"]), capsys)
        assert g["sent"] == signalled
    release(g["member"], g["member_stamp"])  # the test resolves only its own member
    assert_finished(g, capsys)
    assert g["sent"] == signalled


# ---- R30 -----------------------------------------------------------------------------------

@pytest.mark.parametrize("fault", ["permission", "io-error", "malformed"])
def test_r30_unreadable_member_is_unknown_not_an_empty_group(group, capsys, monkeypatch,
                                                             fault):
    g = group
    member_stat = f"/proc/{g['member']}/stat"
    active = {"on": True}
    real_read_text = Path.read_text

    def read_text(self, *args, **kwargs):  # injected: only this live member's stat read
        if active["on"] and str(self) == member_stat:
            if fault == "permission":
                raise PermissionError(errno.EACCES, "injected", member_stat)
            if fault == "io-error":
                raise OSError(errno.EIO, "injected", member_stat)
            return "garbage"
        return real_read_text(self, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", read_text)
    first = stop_fresh(g["dir"])
    if not POSIX:  # no /proc on Windows: the forced tree kill is unaffected
        assert first["ok"] is True and not g["dir"].exists()
        return
    assert_kept(g, first, capsys)
    signalled = list(g["sent"])
    assert signalled == [(g["leader"].pid, signal.SIGTERM)]  # no escalation onto unknown
    for _ in range(2):
        assert_kept(g, stop_fresh(g["dir"]), capsys)
        assert g["sent"] == signalled
    active["on"] = False  # inspection works again, but the member really is alive
    assert_kept(g, stop_fresh(g["dir"]), capsys)
    release(g["member"], g["member_stamp"])
    assert_finished(g, capsys)
    assert g["sent"] == signalled


def test_r30_a_really_disappeared_entry_does_not_strand_cleanup(tmp_path, monkeypatch, capsys):
    """An enumerated /proc entry whose process is really gone (here: an exited, reaped
    child) is skipped, so ordinary cleanup of a cooperative API still completes."""
    gone = subprocess.Popen([sys.executable, "-c", "pass"])
    gone.wait(30)
    if POSIX:
        assert not Path(f"/proc/{gone.pid}").exists()
        real_iterdir = Path.iterdir

        def iterdir(self):
            entries = list(real_iterdir(self))
            if str(self) == "/proc":  # injected: the listing still names the gone process
                entries.append(Path(f"/proc/{gone.pid}"))
            return iter(entries)
        monkeypatch.setattr(Path, "iterdir", iterdir)
    api = subprocess.Popen([sys.executable, "-c",
                            "import time;print('ready',flush=True);time.sleep(600)"],
                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, text=True,
                           **OWN_GROUP)
    try:
        assert api.stdout.readline().strip() == "ready"
        directory = owned_state(tmp_path, {"port": devdb.free_port(), "pid": api.pid,
                                           "start_time": process_start_time(api.pid)})
        result = stop_fresh(directory)
        assert result["ok"] is True and not directory.exists()
        assert api.wait(15) == (-signal.SIGTERM if POSIX else 1)
    finally:
        if api.poll() is None:
            api.kill()
        api.wait(30)
