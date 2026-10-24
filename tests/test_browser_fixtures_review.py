"""Regressions for Codex review c3fd83d: R11 (state ownership before mutation/deletion),
R12 (keep recovery state until API and DB shutdowns are both verified) and R13 (fixture
expectations match the accepted API). Only fresh pytest tmp_path subtrees are used; every
deletion target is asserted to lie inside them."""
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "support"))

import browser_stack  # noqa: E402
from browser_stack import Stack, StackError, process_start_time, terminate_tree  # noqa: E402
from sentinel import devdb  # noqa: E402
from test_browser_fixtures import http  # noqa: E402

pytestmark = pytest.mark.skipif(devdb.find_pg_bin() is None, reason="needs PostgreSQL binaries")


def canary(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "unrelated-canary.txt"
    path.write_text("must survive")
    return path


def inside(child: Path, parent: Path) -> bool:
    return Path(os.path.realpath(child)).is_relative_to(Path(os.path.realpath(parent)))


def link_dir(link: Path, target: Path) -> None:
    if os.name == "nt":  # a junction needs no special privilege
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], check=True,
                       capture_output=True)
    else:
        link.symlink_to(target, target_is_directory=True)


def kill_if_ours(pid, stamp):
    if pid and stamp is not None and process_start_time(pid) == stamp:
        terminate_tree(pid)


@pytest.fixture
def owned(tmp_path):
    """A real stack whose state lives under this test's tmp_path; always cleaned up."""
    stack = Stack.start(tmp_path)
    pid, stamp = stack.manifest["api"]["pid"], stack.manifest["api"]["start_time"]
    assert inside(stack.state_dir, tmp_path)
    try:
        yield stack
    finally:
        kill_if_ours(pid, stamp)
        if stack.state_dir.exists() and inside(stack.state_dir, tmp_path):
            cluster = devdb.Cluster(devdb.find_pg_bin(), stack.state_dir / "pg" / "data", 0)
            if browser_stack._cluster_running(cluster):
                subprocess.run([str(cluster.bin_dir / "pg_ctl"), "-D", str(cluster.data_dir),
                                "-m", "fast", "-w", "stop"], capture_output=True)


# ---- R11 ---------------------------------------------------------------------------------

def test_r11_start_never_takes_over_an_existing_directory(tmp_path):
    keep = canary(tmp_path / "populated")
    stack = Stack.start(tmp_path / "populated")
    try:
        assert stack.state_dir != (tmp_path / "populated")  # a fresh private child instead
        assert inside(stack.state_dir, tmp_path / "populated")
    finally:
        result = stack.stop()
    assert result["state_removed"] is True
    assert keep.read_text() == "must survive"
    assert (tmp_path / "populated").is_dir()


def test_r11_load_rejects_a_copied_manifest(owned, tmp_path):
    keep = canary(tmp_path / "elsewhere")
    copy = tmp_path / "elsewhere" / "stack.json"
    shutil.copy2(owned.path, copy)
    with pytest.raises(StackError):
        Stack.load(copy)
    assert keep.exists()


def test_r11_load_rejects_missing_or_forged_marker(owned, tmp_path):
    forged = tmp_path / "sentinel-browser-forged"
    keep = canary(forged)
    manifest = json.loads(owned.path.read_text())
    manifest["state_dir"] = str(Path(os.path.realpath(forged)))
    (forged / "stack.json").write_text(json.dumps(manifest))
    with pytest.raises(StackError):
        Stack.load(forged / "stack.json")  # no ownership marker
    (forged / ".sentinel-browser-stack").write_text(json.dumps({"owner": "not-the-nonce"}))
    with pytest.raises(StackError):
        Stack.load(forged / "stack.json")  # marker does not match the manifest
    assert keep.exists()


def test_r11_load_rejects_redirected_paths(owned, tmp_path):
    link = tmp_path / "sentinel-browser-link"
    link_dir(link, owned.state_dir)
    try:
        with pytest.raises(StackError):
            Stack.load(link / "stack.json")
        assert owned.path.exists()
    finally:
        os.rmdir(link) if os.name == "nt" else link.unlink()  # removes the link, not the target
    assert owned.path.exists()


def test_r11_unexpected_contents_block_deletion(owned):
    extra = owned.state_dir / "user-notes.txt"
    extra.write_text("not the helper's")
    result = owned.stop()
    assert result["api_stopped"] and result["database_stopped"]
    assert result["state_removed"] is False and result["ok"] is False
    assert extra.exists() and owned.path.exists()
    extra.unlink()
    assert Stack.load(owned.path).stop()["state_removed"] is True


# ---- R12 ---------------------------------------------------------------------------------

def test_r12_api_stop_failure_keeps_recovery_state_and_retry_completes(owned, monkeypatch):
    def failing_stop_api():
        raise StackError("injected API stop failure")

    monkeypatch.setattr(owned, "stop_api", failing_stop_api)
    result = owned.stop()
    assert result["ok"] is False and result["api_stopped"] is False
    assert result["state_removed"] is False
    assert owned.path.exists()  # recovery metadata (pid, start time, tokens) retained
    monkeypatch.undo()
    retry = Stack.load(owned.path).stop()
    assert retry == {"ok": True, "api_stopped": True, "database_stopped": True,
                     "state_removed": True, "errors": []}


def test_r12_db_stop_failure_keeps_recovery_state_and_retry_completes(owned, monkeypatch):
    def failing_stop(self):
        raise subprocess.CalledProcessError(1, "pg_ctl stop (injected)")

    monkeypatch.setattr(devdb.Cluster, "stop", failing_stop)
    result = owned.stop()
    assert result["ok"] is False and result["database_stopped"] is False
    assert result["api_stopped"] is True and result["state_removed"] is False
    assert owned.path.exists()
    monkeypatch.undo()
    retry = Stack.load(owned.path).stop()
    assert retry["ok"] is True and retry["state_removed"] is True


def test_r12_failed_start_keeps_recovery_manifest_when_cleanup_fails(tmp_path, monkeypatch):
    def failing_stop(self):
        raise subprocess.CalledProcessError(1, "pg_ctl stop (injected)")

    monkeypatch.setattr(devdb.Cluster, "stop", failing_stop)
    with pytest.raises(StackError, match="recovery manifest kept"):
        Stack.start(tmp_path, app="fixture_app:create_app_never_ready", timeout=4)
    monkeypatch.undo()
    manifests = list(tmp_path.glob("sentinel-browser-*/stack.json"))
    assert len(manifests) == 1 and inside(manifests[0], tmp_path)
    assert Stack.load(manifests[0]).stop()["ok"] is True
    assert not list(tmp_path.glob("sentinel-browser-*"))


# ---- R13 ---------------------------------------------------------------------------------

def test_r13_rejected_intent_reapproval_is_stale_case_revision(owned):
    record = owned.manifest["scenarios"]["rejected"]
    assert http(owned, "POST", "/v1/approvals", "analyst", {
        "action_intent_id": record["intent_id"], "decision": "approved"}) == (
        409, {"error": "stale_case_revision"})
    assert "stale_case_revision" in record["next"] and "approval_exists" not in record["next"]


def test_r13_only_denied_executions_are_audited(owned):
    record = owned.manifest["scenarios"]["limited_capabilities"]
    pending = owned.manifest["scenarios"]["awaiting_approval"]["intent_id"]
    assert http(owned, "POST", "/v1/approvals", "read_only", {
        "action_intent_id": pending, "decision": "approved"})[0] == 403
    audit = http(owned, "GET", f"/v1/cases/{owned.manifest['scenarios']['awaiting_approval']['case_id']}/audit",
                 "analyst")[1]
    assert "action_denied" not in [e["event_type"] for e in audit]  # approvals are not audited
    assert "all audited" not in record["next"]
    assert http(owned, "POST", "/v1/actions", "second_actor", {
        "approval_id": record["approval_id"], "idempotency_key": str(uuid.uuid4())})[0] == 403
