"""Regressions for Codex re-review 66214bb: nested-path redirection before PostgreSQL
commands (R11), recoverable partial removal and unknown database status (R12).

Process-free by construction: every subprocess call (pg_ctl, taskkill, uvicorn) and the
API health probe are intercepted and recorded, so no real database or API is started,
stopped or queried. Owned trees are built by hand in fresh tmp_path subtrees; junctions are
removed in finally blocks; outside canaries must survive."""
import json
import os
import secrets
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "support"))

import browser_stack  # noqa: E402
from browser_stack import Stack, StackError  # noqa: E402
from sentinel import devdb  # noqa: E402

pytestmark = pytest.mark.skipif(devdb.find_pg_bin() is None, reason="needs PostgreSQL binaries")
DUMMY_TOKEN = "DUMMY_TOKEN_NOT_REAL_5150"


class Processes:
    """Records every process call; pg_ctl status returns `status_rc` (or raises)."""

    def __init__(self):
        self.calls: list[list[str]] = []
        self.status_rc: int | Exception = 3
        self.stop_error: Exception | None = None

    def run(self, args, *pos, **kw):
        args = [str(a) for a in args]
        self.calls.append(args)
        if "status" in args:
            if isinstance(self.status_rc, Exception):
                raise self.status_rc
            return subprocess.CompletedProcess(args, self.status_rc, "", "")
        if "stop" in args and self.stop_error is not None:
            raise self.stop_error
        return subprocess.CompletedProcess(args, 0, "", "")

    def popen(self, args, *pos, **kw):
        self.calls.append([str(a) for a in args])
        raise AssertionError("no process may be launched in these tests")

    def touching(self, path: Path) -> list[list[str]]:
        target = os.path.normcase(os.path.realpath(path))
        return [c for c in self.calls if any(target in os.path.normcase(os.path.realpath(a))
                                             for a in c if os.sep in a or "/" in a)]


@pytest.fixture
def procs(monkeypatch):
    recorder = Processes()
    monkeypatch.setattr(browser_stack.subprocess, "run", recorder.run)
    monkeypatch.setattr(devdb.subprocess, "run", recorder.run)
    monkeypatch.setattr(browser_stack.subprocess, "Popen", recorder.popen)
    monkeypatch.setattr(browser_stack, "healthy", lambda port: None)
    return recorder


def owned_tree(parent: Path, *, data: bool = True, initialized: bool = True,
               started: bool = True) -> Path:
    """A correctly owned, process-free stack directory in the manifest v2 format."""
    directory = Path(os.path.realpath(tempfile.mkdtemp(prefix=browser_stack.PREFIX,
                                                       dir=parent)))
    owner, where = secrets.token_hex(16), browser_stack.canonical(directory)
    (directory / browser_stack.MARKER).write_text(json.dumps({"owner": owner,
                                                              "state_dir": where}))
    manifest = {"version": browser_stack.MANIFEST_VERSION, "app": browser_stack.DEFAULT_APP,
                "owner": owner, "state_dir": where,
                "database": {"port": 1, "name": "browser", "started": started},
                "api": {"port": 1, "pid": None, "start_time": None},
                "tokens": {"analyst": DUMMY_TOKEN}}
    (directory / "stack.json").write_text(json.dumps(manifest))
    if data:
        (directory / "pg" / "data").mkdir(parents=True)
        if initialized:
            (directory / "pg" / "data" / "PG_VERSION").write_text("14\n")
    return directory


def junction(link: Path, target: Path) -> None:
    if os.name == "nt":  # no subprocess: process calls are intercepted in these tests
        import _winapi
        _winapi.CreateJunction(str(target), str(link))
    else:
        link.symlink_to(target, target_is_directory=True)


def unlink_junction(link: Path) -> None:
    if os.path.lexists(link):
        os.rmdir(link) if os.name == "nt" else link.unlink()


def outside(tmp_path: Path) -> tuple[Path, Path]:
    foreign = tmp_path / "foreign-cluster"
    (foreign / "data").mkdir(parents=True)
    (foreign / "data" / "PG_VERSION").write_text("14\n")
    keep = foreign / "data" / "canary.txt"
    keep.write_text("must survive")
    return foreign, keep


# ---- R11: nested redirection is refused before any PostgreSQL command ---------------------

@pytest.mark.parametrize("variant", ["pg", "pg/data"])
def test_r11_load_rejects_nested_redirect(tmp_path, procs, variant):
    foreign, keep = outside(tmp_path)
    directory = owned_tree(tmp_path, data=False)
    link = directory / "pg" if variant == "pg" else directory / "pg" / "data"
    if variant == "pg/data":
        (directory / "pg").mkdir()
    junction(link, foreign if variant == "pg" else foreign / "data")
    try:
        with pytest.raises(StackError):
            Stack.load(directory / "stack.json")
        assert procs.calls == []
        assert keep.read_text() == "must survive"
    finally:
        unlink_junction(link)


@pytest.mark.parametrize("variant", ["pg", "pg/data"])
def test_r11_operation_boundary_rechecks_paths(tmp_path, procs, variant):
    foreign, keep = outside(tmp_path)
    directory = owned_tree(tmp_path, data=False)
    stack = Stack.load(directory / "stack.json")  # valid when loaded
    link = directory / "pg" if variant == "pg" else directory / "pg" / "data"
    if variant == "pg/data":
        (directory / "pg").mkdir()
    junction(link, foreign if variant == "pg" else foreign / "data")  # redirected afterwards
    try:
        result = stack.stop()
        assert result["ok"] is False and result["state_removed"] is False
        assert any("redirect" in e for e in result["errors"])
        with pytest.raises(StackError):
            stack.status()
        with pytest.raises(StackError):
            stack.restart_db()
        assert procs.calls == []  # zero PostgreSQL (or any) process operations
        assert keep.read_text() == "must survive"
        assert (directory / "stack.json").exists()
    finally:
        unlink_junction(link)


def test_r11_redirected_api_log_is_refused_before_launch(tmp_path, procs):
    foreign, keep = outside(tmp_path)
    directory = owned_tree(tmp_path)
    stack = Stack.load(directory / "stack.json")
    stack.manifest["database_url"] = "postgresql://unused"
    junction(directory / "api.log", foreign)
    try:
        with pytest.raises(StackError):
            stack.restart_api(timeout=1)
        assert procs.calls == [] and keep.exists()
    finally:
        unlink_junction(directory / "api.log")


# ---- R12: partial removal stays recoverable ----------------------------------------------

@pytest.mark.skipif(os.name != "nt", reason="Windows sharing-violation lock")
@pytest.mark.parametrize("locked", ["api.log", "pg/data/locked.bin"])
def test_r12_locked_file_keeps_state_loadable_and_retry_completes(tmp_path, procs, locked,
                                                                  capsys):
    directory = owned_tree(tmp_path, initialized=False, started=False)
    target = directory / locked
    target.write_bytes(b"x")
    handle = open(target, "rb")  # without FILE_SHARE_DELETE: deletion is refused
    try:
        result = Stack.load(directory / "stack.json").stop()
        assert result["ok"] is False and result["state_removed"] is False
        again = Stack.load(directory / "stack.json")  # still owned and loadable
        assert (directory / browser_stack.MARKER).exists()
    finally:
        handle.close()
    assert again.stop()["ok"] is True
    assert not directory.exists()
    assert DUMMY_TOKEN not in capsys.readouterr().out


def test_r12_injected_partial_removal_keeps_ownership(tmp_path, procs, monkeypatch):
    directory = owned_tree(tmp_path, initialized=False, started=False)
    (directory / "api.log").write_text("log")
    real_rmtree = browser_stack.shutil.rmtree

    def rmtree_then_fail(path, *args, **kwargs):
        # Simulate traversal deleting entries in name order (the marker sorts first), then
        # hitting an undeletable file.
        for entry in sorted(Path(path).iterdir()):
            if entry.is_file():
                entry.unlink()
                break
        raise PermissionError("injected: file in use")

    monkeypatch.setattr(browser_stack.shutil, "rmtree", rmtree_then_fail)
    result = Stack.load(directory / "stack.json").stop()
    assert result["ok"] is False
    monkeypatch.setattr(browser_stack.shutil, "rmtree", real_rmtree)
    assert Stack.load(directory / "stack.json").stop()["ok"] is True
    assert not directory.exists()


def test_r12_marker_only_leftover_is_finished_by_stop_retry(tmp_path, procs, monkeypatch):
    directory = owned_tree(tmp_path, data=False, started=False)
    marker = directory / browser_stack.MARKER
    real_unlink = Path.unlink

    def unlink_marker_fails(self, *args, **kwargs):
        if self == marker:
            raise PermissionError("injected: marker in use")
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", unlink_marker_fails)
    result = Stack.load(directory / "stack.json").stop()
    assert result["ok"] is False and "marker" in " ".join(result["errors"])
    assert not (directory / "stack.json").exists()  # the token-bearing manifest is gone
    monkeypatch.setattr(Path, "unlink", real_unlink)
    assert browser_stack.main(["stop", "--manifest", str(directory / "stack.json")]) == 0
    assert not directory.exists()


def test_r12_marker_only_finish_refuses_unowned_directories(tmp_path, procs):
    stranger = tmp_path / "sentinel-browser-stranger"
    stranger.mkdir()
    (stranger / browser_stack.MARKER).write_text(json.dumps(
        {"owner": "x", "state_dir": browser_stack.canonical(tmp_path / "elsewhere")}))
    assert browser_stack.main(["stop", "--manifest", str(stranger / "stack.json")]) == 1
    assert (stranger / browser_stack.MARKER).exists()
    plain = tmp_path / "not-a-stack"
    keep = plain / "notes.txt"
    plain.mkdir()
    keep.write_text("keep")
    assert browser_stack.main(["stop", "--manifest", str(plain / "stack.json")]) == 1
    assert keep.exists()


# ---- R12: unknown database status is never treated as stopped ----------------------------

@pytest.mark.parametrize("status", [1, 4, 0, OSError("pg_ctl unavailable"),
                                    subprocess.TimeoutExpired("pg_ctl", 30)],
                         ids=["rc1", "rc4-inaccessible", "rc0-still-running", "oserror",
                              "timeout"])
def test_r12_unknown_or_running_status_keeps_state(tmp_path, procs, status):
    directory = owned_tree(tmp_path)
    procs.stop_error = subprocess.CalledProcessError(1, "pg_ctl stop (injected)")
    procs.status_rc = status
    result = Stack.load(directory / "stack.json").stop()
    assert result["ok"] is False and result["database_stopped"] is False
    assert result["state_removed"] is False
    assert (directory / "pg" / "data" / "PG_VERSION").exists()
    assert Stack.load(directory / "stack.json")  # recovery record intact


def test_r12_status_three_is_stopped_and_cleanup_completes(tmp_path, procs):
    directory = owned_tree(tmp_path)
    procs.status_rc = 3
    result = Stack.load(directory / "stack.json").stop()
    assert result["ok"] is True and result["database_stopped"] is True
    assert not directory.exists()
    assert all(directory.name in " ".join(c) for c in procs.calls)  # only our own data dir


def test_r12_uninitialized_data_needs_no_pg_ctl(tmp_path, procs):
    for kwargs in ({"data": False}, {"initialized": False}):
        directory = owned_tree(tmp_path, **kwargs)
        result = Stack.load(directory / "stack.json").stop()
        assert result["ok"] is True and not directory.exists()
    assert procs.calls == []
