"""Fixture/label/manifest hashes, application isolation and the CLI prototype."""
import hashlib
import json
import os
import subprocess
import sys
import tomllib

from conftest import FIXTURES, ROOT, SESSION

sys.path.insert(0, str(FIXTURES))
import generate  # noqa: E402


def test_committed_fixtures_match_generator_and_manifest(tmp_path):
    manifest = json.loads((FIXTURES / "MANIFEST.json").read_text(encoding="utf-8"))
    generate.write(tmp_path)
    regenerated = json.loads((tmp_path / "MANIFEST.json").read_text(encoding="utf-8"))
    assert regenerated == manifest
    for name, meta in manifest["fixtures"].items():
        data = (FIXTURES / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == meta["sha256"], name
        assert (tmp_path / name).read_bytes() == data, name
    labels = (FIXTURES / "labels.json").read_bytes()
    assert hashlib.sha256(labels).hexdigest() == manifest["labels_sha256"]


def test_worker_is_separately_locked_with_reviewed_security_updates():
    worker = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert worker["project"]["dependencies"] == ["markitdown[pdf,xlsx]==0.1.8"]
    assert worker["project"]["requires-python"] == ">=3.11.5,<3.13"
    assert worker["tool"]["uv"]["exclude-newer"] == "2026-10-29T00:00:00Z"
    assert set(worker["tool"]["uv"]["exclude-newer-package"]) == {"certifi", "soupsieve", "pytest"}
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    assert {(p["name"], p["version"]) for p in lock["package"]} >= {
        ("markitdown", "0.1.8"), ("certifi", "2026.10.23"), ("soupsieve", "4.0"), ("pytest", "9.2.0"),
    }
    app_root = ROOT.parent.parent
    app = (app_root / "pyproject.toml").read_text(encoding="utf-8")
    assert "markitdown" not in app
    assert "markitdown" not in (app_root / "uv.lock").read_text(encoding="utf-8")


def _cli(store, *args, session=SESSION):
    env = dict(os.environ)
    env.pop("SENTINEL_DOC_SESSION", None)
    if session:
        env["SENTINEL_DOC_SESSION"] = session
    proc = subprocess.run([sys.executable, "-m", "docworker", *args, "--store", str(store)],
                          capture_output=True, text=True, env=env, timeout=120,
                          encoding="utf-8")
    return proc.returncode, json.loads(proc.stdout)


def test_cli_end_to_end(tmp_path):
    store = tmp_path / "store"
    assert _cli(store, "init") == (0, {"store": "ready"})
    code, handle = _cli(store, "ingest", "--format", "csv", "--file",
                        str(FIXTURES / "csv_comma_decimal.csv"))
    assert code == 0 and handle["handle_id"].startswith("h_")
    code, result = _cli(store, "extract", "--handle", handle["handle_id"],
                        "--decimal-style", "comma", "--date-order", "dmy", "--no-narrative")
    assert code == 0 and result["status"] == "partial"
    recon = result["measures"]["reconciliation"]["currencies"][0]
    assert (recon["currency"], recon["status"]) == ("EUR", "reconciled")
    assert _cli(store, "extract", "--handle", handle["handle_id"],
                session="another-session-token-000")[1] == {"status": "refused",
                                                            "code": "not_found"}
    assert _cli(store, "extract", "--handle", handle["handle_id"], session=None)[0] == 4
    assert _cli(store, "recover") == (0, {"records": []})
    assert _cli(store, "delete", "--handle", handle["handle_id"])[1]["deleted"] is True
    code, refused = _cli(store, "ingest", "--format", "csv", "--file", "http://198.51.100.7/a")
    assert code == 4 and refused["code"] == "not_a_local_file"
