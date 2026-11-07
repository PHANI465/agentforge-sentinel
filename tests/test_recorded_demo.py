"""DEMO01 recorded replay: the tracked fixture, its validator's negative controls, the
secret scan, the static page's local-only boundary, and one real capture through the
production HTTP app on disposable PostgreSQL as the restricted runtime role (no provider).
"""
import copy
import json
import re
import shutil
import subprocess
import sys
import uuid
from datetime import timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_recorded_demo as demo  # noqa: E402

DEMO = ROOT / "demo"


@pytest.fixture(scope="module")
def tracked():
    fixture, payload = demo.load_fixture(demo.DATA_FILE)
    return fixture, payload


def problems_after(fixture, change):
    altered = copy.deepcopy(fixture)
    change(altered)
    return demo.validate(altered)


# ---- the tracked fixture --------------------------------------------------------------------

def test_tracked_fixture_is_valid_and_matches_its_manifest(tracked):
    fixture, payload = tracked
    assert demo.validate(fixture) == []
    manifest = json.loads(demo.MANIFEST_FILE.read_text(encoding="utf-8"))
    assert manifest["sha256"] == demo.sha256(payload)
    assert manifest["bytes"] == len(payload)
    assert manifest["generator_commit"] == fixture["provenance"]["generator_commit"]
    assert payload == demo.serialize(fixture)  # canonical bytes, LF only
    assert b"\r" not in payload


def test_tracked_fixture_provenance_is_honest(tracked):
    prov = tracked[0]["provenance"]
    assert prov["generator_tree_clean"] is True
    assert prov["src_identical_to_tested_application"] is True
    assert prov["tested_application_reference"] == demo.TESTED_APPLICATION
    assert prov["scorer"]["mode"] == "rule"
    assert prov["workflow"]["live"] is False
    assert prov["runtime_role"]["session_issuance_refused"] is True
    assert len(prov["scripted_steps"]) == 2 and "scripted" in tracked[0]["notice"].lower()
    assert re.fullmatch(r"[0-9a-f]{40}", prov["generator_commit"])


# ---- capture freshness: recorded content identity vs the actual checkout bytes ------------
# History-independent (R48): no Git call, no capture-commit lookup and no skip. The recorded
# generator_commit stays as provenance only; freshness is the bytes of this checkout.

def _no_git(monkeypatch):
    """Simulate a checkout without Git, or without the capture commit's history."""
    def missing(*args):
        return subprocess.CompletedProcess(["git", *args], 128, "", "fatal: bad object")
    real_run = subprocess.run

    def no_git_run(cmd, *a, **k):
        if cmd and Path(str(cmd[0])).name.lower().startswith("git"):
            raise FileNotFoundError("git is not available in this simulated checkout")
        return real_run(cmd, *a, **k)
    monkeypatch.setattr(demo, "_git", missing)
    monkeypatch.setattr(demo.subprocess, "run", no_git_run)
    monkeypatch.setattr(demo.shutil, "which", lambda *a, **k: None)


def test_content_identity_passes_the_projection_key_allowlist():
    """Recapture 1 on 2bcc03d failed safely: the identity's own `scope` key is a forbidden
    (identity-scope) key. The projection check stays; the identity must not use that key."""
    identity = demo.content_identity()
    assert demo.forbidden_keys(identity) == set()
    assert demo.forbidden_keys({"provenance": {"content_identity": identity}}) == set()


def test_capture_content_identity_matches_this_checkout(tracked):
    identity = tracked[0]["provenance"]["content_identity"]
    assert identity["inputs"] == list(demo.CONTENT_SCOPE)
    assert identity["canonicalization"] == demo.CANONICALIZATION
    assert "scripts/build_recorded_demo.py" in identity["files"]
    assert any(name.startswith("src/sentinel/") for name in identity["files"])
    assert demo.freshness_problems(tracked[0]) == [], \
        "re-run the capture: generator or application content changed"


def test_freshness_needs_no_git_history(tracked, monkeypatch):
    _no_git(monkeypatch)
    assert demo.freshness_problems(tracked[0]) == []
    assert demo.content_identity() == tracked[0]["provenance"]["content_identity"]


def _copy_inputs(dest: Path) -> Path:
    (dest / "scripts").mkdir(parents=True)
    shutil.copy2(demo.ROOT / "scripts" / "build_recorded_demo.py", dest / "scripts")
    shutil.copytree(demo.ROOT / "src", dest / "src",
                    ignore=shutil.ignore_patterns("__pycache__", "*.egg-info", "*.pyc"))
    return dest


def test_tracked_identity_detects_changed_bytes_in_a_copied_checkout(tracked, tmp_path,
                                                                     monkeypatch):
    _no_git(monkeypatch)
    root = _copy_inputs(tmp_path / "checkout")
    assert demo.freshness_problems(tracked[0], root=root) == []
    # a CRLF checkout of the same content (Windows autocrlf) has the same identity
    api = root / "src" / "sentinel" / "api.py"
    original = api.read_bytes()
    api.write_bytes(original.replace(b"\n", b"\r\n"))
    assert demo.freshness_problems(tracked[0], root=root) == []
    # changed application input
    api.write_bytes(original + b"# changed\n")
    problems = demo.freshness_problems(tracked[0], root=root)
    assert any("src/sentinel/api.py" in p and "changed" in p for p in problems), problems
    api.write_bytes(original)
    assert demo.freshness_problems(tracked[0], root=root) == []
    # changed generator
    gen = root / "scripts" / "build_recorded_demo.py"
    gen.write_bytes(gen.read_bytes().replace(b"TESTED_APPLICATION", b"TESTED_APPLICATIOM", 1))
    problems = demo.freshness_problems(tracked[0], root=root)
    assert any("scripts/build_recorded_demo.py" in p for p in problems), problems


def _mini_root(tmp_path: Path) -> Path:
    root = tmp_path / "mini"
    (root / "scripts").mkdir(parents=True)
    (root / "src" / "pkg" / "__pycache__").mkdir(parents=True)
    (root / "src" / "pkg.egg-info").mkdir(parents=True)
    (root / "scripts" / "build_recorded_demo.py").write_bytes(b"GEN = 1\n")
    (root / "src" / "pkg" / "a.py").write_bytes(b"A = 1\n")
    (root / "src" / "pkg" / "schema.sql").write_bytes(b"select 1;\n")
    (root / "src" / "pkg" / "__pycache__" / "a.cpython-312.pyc").write_bytes(b"\0junk")
    (root / "src" / "pkg.egg-info" / "PKG-INFO").write_bytes(b"Name: pkg\n")
    return root


def _fixture_for(root: Path) -> dict:
    return {"provenance": {"generator_commit": "0" * 40,
                           "content_identity": demo.content_identity(root)}}


def test_unchanged_content_passes_and_build_artifacts_are_ignored(tmp_path, monkeypatch):
    _no_git(monkeypatch)
    root = _mini_root(tmp_path)
    fx = _fixture_for(root)
    assert sorted(fx["provenance"]["content_identity"]["files"]) == [
        "scripts/build_recorded_demo.py", "src/pkg/a.py", "src/pkg/schema.sql"]
    assert demo.freshness_problems(fx, root=root) == []
    (root / "src" / "pkg" / "__pycache__" / "a.cpython-312.pyc").write_bytes(b"other")
    (root / "src" / "pkg.egg-info" / "PKG-INFO").write_bytes(b"Name: other\n")
    assert demo.freshness_problems(fx, root=root) == []


def test_changed_added_and_removed_inputs_fail(tmp_path, monkeypatch):
    _no_git(monkeypatch)
    root = _mini_root(tmp_path)
    fx = _fixture_for(root)
    gen, a = root / "scripts" / "build_recorded_demo.py", root / "src" / "pkg" / "a.py"
    gen.write_bytes(b"GEN = 2\n")
    assert any("scripts/build_recorded_demo.py" in p and "changed" in p
               for p in demo.freshness_problems(fx, root=root))
    gen.write_bytes(b"GEN = 1\n")
    a.write_bytes(b"A = 2\n")
    assert any("src/pkg/a.py" in p and "changed" in p
               for p in demo.freshness_problems(fx, root=root))
    a.write_bytes(b"A = 1\n")
    (root / "src" / "pkg" / "b.py").write_bytes(b"B = 1\n")
    assert any("src/pkg/b.py" in p and "added" in p
               for p in demo.freshness_problems(fx, root=root))
    (root / "src" / "pkg" / "b.py").unlink()
    (root / "src" / "pkg" / "schema.sql").unlink()
    assert any("src/pkg/schema.sql" in p and "missing" in p
               for p in demo.freshness_problems(fx, root=root))
    shutil.rmtree(root / "src")
    assert demo.freshness_problems(fx, root=root)
    gen.unlink()
    assert demo.freshness_problems(fx, root=root)


def test_missing_provenance_fails_with_a_useful_message(tracked, tmp_path):
    root = _mini_root(tmp_path)
    for fx in ({}, {"provenance": {}}, {"provenance": {"generator_commit": "0" * 40}},
               {"provenance": None}, []):
        problems = demo.freshness_problems(fx, root=root)
        assert problems and "content_identity" in problems[0] and "capture" in problems[0]
    stripped = copy.deepcopy(tracked[0])
    del stripped["provenance"]["content_identity"]
    assert any("content_identity" in p for p in demo.validate(stripped))
    assert any("content_identity" in p for p in demo.freshness_problems(stripped))


@pytest.mark.parametrize("corrupt", [
    lambda c: c.update(files=["scripts/build_recorded_demo.py"]),
    lambda c: c.update(files={}),
    lambda c: c["files"].update({"src/pkg/a.py": "not-a-digest"}),
    lambda c: c["files"].update({"../outside.py": "0" * 64}),
    lambda c: c["files"].update({"src\\pkg\\a.py": "0" * 64}),
    lambda c: c.update(sha256="0" * 64),
    lambda c: c.pop("sha256"),
    lambda c: c.update(inputs=["src"]),
    lambda c: c.update(canonicalization="raw bytes"),
    lambda c: c.clear(),
], ids=["files-list", "files-empty", "bad-digest", "escaping-path", "backslash-path",
        "aggregate-mismatch", "no-aggregate", "wrong-inputs", "wrong-canonicalization",
        "empty"])
def test_malformed_content_identity_fails_without_crashing(tmp_path, corrupt):
    root = _mini_root(tmp_path)
    fx = _fixture_for(root)
    corrupt(fx["provenance"]["content_identity"])
    problems = demo.freshness_problems(fx, root=root)
    assert problems and all(isinstance(p, str) for p in problems)
    assert any("content_identity" in p for p in problems)
    assert any("content_identity" in p for p in demo.identity_shape_problems(
        fx["provenance"]["content_identity"]))


def test_validator_cli_reports_stale_content(tmp_path, monkeypatch, capsys):
    root = _copy_inputs(tmp_path / "checkout")
    api = root / "src" / "sentinel" / "api.py"
    api.write_bytes(api.read_bytes() + b"# changed\n")
    monkeypatch.setattr(demo, "ROOT", root)
    assert demo.main(["validate"]) == 1
    out = capsys.readouterr().out
    assert "FAIL" in out and "src/sentinel/api.py" in out and "re-run the capture" in out


def test_tracked_fixture_has_no_forbidden_keys_or_local_paths(tracked):
    assert demo.forbidden_keys(tracked[0]) == set()
    assert demo.scan(demo.public_files(), demo.path_variants()) == []


@pytest.mark.parametrize("user", ["sentinel", "Sentinel", "demo", "replay", "root"])
def test_account_named_like_a_product_word_is_not_a_false_positive(user):
    """Native Ubuntu preview 82316a5 ran as account "sentinel": the bare name matched the
    product name in every public file. Only path contexts identify an account."""
    linux = demo.path_variants(root=f"/home/{user}/preview-native", home=f"/home/{user}",
                               user=user)
    windows = demo.path_variants(root=f"C:\\Users\\{user}\\sentinel-wt\\demo01",
                                 home=f"C:\\Users\\{user}", user=user)
    assert user not in linux and user not in windows
    assert demo.scan(demo.public_files(), linux) == []
    assert demo.scan(demo.public_files(), windows) == []


def test_planted_home_and_user_paths_are_still_caught(tmp_path):
    user = "sentinel"
    needles = sorted(set(
        demo.path_variants(root=f"/home/{user}/preview-native", home=f"/home/{user}",
                           user=user)
        + demo.path_variants(root="E:\\work\\checkout", home=f"C:\\Users\\{user}", user=user)))
    benign = tmp_path / "benign.md"
    benign.write_text("Sentinel recorded replay; SENTINEL_DATABASE_URL; /home/ and Users/.",
                      encoding="utf-8")
    assert demo.scan([benign], needles) == []
    planted = {
        "linux_home.txt": "log at /home/sentinel/.cache/x",
        "linux_checkout.txt": "ran in /home/sentinel/preview-native/demo",
        "win_users.txt": "C:\\Users\\Sentinel\\AppData",
        "win_forward.txt": "c:/users/sentinel/Desktop",
        "json_escaped.json": json.dumps({"p": "C:\\Users\\sentinel\\x"}),
        "checkout_forward.txt": "E:/work/checkout/demo/index.html",
        "checkout_json.json": json.dumps({"p": "E:\\work\\checkout\\x"}),
        "mac_users.txt": "/Users/sentinel/Library",
    }
    files = []
    for name, text in planted.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
        files.append(tmp_path / name)
    assert sorted(demo.scan(files, needles)) == sorted(planted)


# ---- negative controls ------------------------------------------------------------------------

def test_action_before_the_approval_frame_is_detected(tracked):
    def early_action(fx):
        fx["observations"]["after_investigation"]["simulated_actions"] = 1
    assert any("before the approval frame" in p for p in problems_after(tracked[0], early_action))

    def early_approval(fx):
        fx["observations"]["case_opened"]["approvals"] = 1
    assert any("before the approval frame" in p
               for p in problems_after(tracked[0], early_approval))


def test_action_timed_before_its_approval_is_detected(tracked):
    def backdate(fx):
        decided = demo._t(fx["records"]["approval"]["decided_at"])
        fx["records"]["execution"]["action"]["created_at"] = (
            decided - timedelta(seconds=1)).isoformat()
    assert "action not inside the approval window" in problems_after(tracked[0], backdate)


def test_broken_evidence_reference_is_detected(tracked):
    def break_claim(fx):
        analyst = fx["records"]["attempts"][0]
        analyst["output"]["claims"][0]["cite"]["id"] = str(uuid.uuid4())
    assert "claim cites a missing record" in problems_after(tracked[0], break_claim)

    def break_tool(fx):
        tool = next(t for t in fx["records"]["tool_results"] if t["evidence_ids"])
        tool["evidence_ids"][0] = str(uuid.uuid4())
    assert "tool result cites missing evidence" in problems_after(tracked[0], break_tool)


def test_replay_that_creates_a_second_action_is_detected(tracked):
    def second(fx):
        fx["records"]["replay"]["action"]["id"] = str(uuid.uuid4())
        fx["observations"]["after_replay"]["simulated_actions"] = 2
    problems = problems_after(tracked[0], second)
    assert "replay returned a different action" in problems
    assert any("exactly one simulated action" in p for p in problems)


def test_future_event_time_and_reordered_frames_are_detected(tracked):
    def future(fx):
        fx["records"]["ingests"][0]["transaction"]["occurred_at"] = (
            fx["provenance"]["capture_finished_at"])
    assert "event time does not precede the recording" in problems_after(tracked[0], future)

    def reorder(fx):
        fx["frames"][6], fx["frames"][7] = fx["frames"][7], fx["frames"][6]
    assert "frame stages/order" in problems_after(tracked[0], reorder)


def test_identity_material_and_unlabelled_actors_are_detected(tracked):
    def leak(fx):
        fx["records"]["approval"]["session_id"] = str(uuid.uuid4())
    assert any("forbidden keys" in p for p in problems_after(tracked[0], leak))

    def relabel(fx):
        fx["records"]["audit"][0]["actor"] = str(uuid.uuid4())
    assert "audit actor labels" in problems_after(tracked[0], relabel)


def test_malformed_fixture_is_a_problem_not_a_crash(tracked):
    assert demo.validate({"schema": demo.SCHEMA})[0].startswith("malformed fixture")


def test_scan_finds_a_token_and_refuses_an_empty_source(tmp_path):
    token = "SYNTHETIC-scan-control-" + uuid.uuid4().hex
    leaked = tmp_path / "leaked.json"
    leaked.write_text(json.dumps({"x": token.upper()}), encoding="utf-8")
    clean = tmp_path / "clean.json"
    clean.write_text("{}", encoding="utf-8")
    assert demo.scan([leaked, clean], [token]) == ["leaked.json"]
    with pytest.raises(demo.DemoError):
        demo.scan([clean], [])
    with pytest.raises(demo.DemoError):
        demo.scan([clean], [token, ""])


# ---- the static page stays local and read-only --------------------------------------------

def test_static_page_is_local_only_and_renders_text_safely():
    html = (DEMO / "index.html").read_text(encoding="utf-8")
    js = (DEMO / "replay.js").read_text(encoding="utf-8")
    css = (DEMO / "replay.css").read_text(encoding="utf-8")
    for text in (html, js, css):
        assert not re.search(r"(?i)\b(?:https?|wss?)://", text)
        assert "healthz" not in text and "@import" not in text
    assert "/v1" not in html and "<script>" not in html  # no inline script
    assert not re.search(r"[\"'`]/", js)  # no absolute-path string: no /v1 or other route
    assert "Content-Security-Policy" in html and "default-src 'none'" in html
    assert "connect-src 'self'" in html and "form-action 'none'" in html
    for tag in ("<form", "<input", "<textarea", "<iframe", "<object", "<embed"):
        assert tag not in html.lower()
    for label in demo.LABELS:
        assert label.lower() in html.lower()
    for ref in re.findall(r'(?:src|href)="([^"#][^"]*)"', html):
        assert ref.startswith("data:") or (DEMO / ref).is_file(), ref
    for sink in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(",
                 "new Function", "setAttribute(\"href", "WebSocket", "EventSource",
                 "XMLHttpRequest", "sendBeacon", "localStorage"):
        assert sink not in js, sink
    assert re.findall(r"fetch\((\w+)", js) == ["DATA_URL", "MANIFEST_URL"]
    assert 'DATA_URL = "data/recorded-case.json"' in js
    assert 'MANIFEST_URL = "data/manifest.json"' in js
    assert re.findall(r'method:\s*"(\w+)"', js) == []  # GET only
    assert js.count("link.href = ") == 1 and '"#rec-" + id' in js


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_javascript_parses():
    for script in (DEMO / "replay.js", DEMO / "tests" / "browser_qa.mjs"):
        subprocess.run(["node", "--check", str(script)], check=True, timeout=60)


# ---- one real capture ---------------------------------------------------------------------

def test_real_capture_is_valid_scans_clean_and_matches_the_tracked_shape(database_url,
                                                                         tracked, tmp_path):
    cap = demo.capture_case(database_url, f"demo01_rt_{uuid.uuid4().hex[:10]}")
    assert len(cap.token) >= 32 and cap.token in cap.secrets
    fixture = demo.project(cap.raw, demo.provenance_for(
        cap.raw, {"commit": "0" * 40, "clean": True, "src_identical": True}))
    assert demo.validate(fixture) == []
    out = tmp_path / "recorded-case.json"
    out.write_bytes(demo.serialize(fixture))
    raw = tmp_path / "raw.json"
    raw.write_text(json.dumps(cap.raw), encoding="utf-8")
    log = tmp_path / "capture.log"
    log.write_text("\n".join(cap.log_lines), encoding="utf-8")
    assert demo.scan([out], cap.secrets) == []
    assert demo.scan([raw, log], cap.secrets[:4]) == []  # token, digest and both DSNs
    control = tmp_path / "control.json"
    control.write_text(out.read_text(encoding="utf-8") + cap.token, encoding="utf-8")
    assert demo.scan([control], cap.secrets) == ["control.json"]

    want, got = tracked[0], fixture
    assert [f["stage"] for f in got["frames"]] == [f["stage"] for f in want["frames"]]
    assert [e["event_type"] for e in got["records"]["audit"]] == list(demo.AUDIT_SEQUENCE)
    shape = lambda fx: (  # noqa: E731
        fx["records"]["workflow"]["disposition"]["operation"],
        fx["records"]["workflow"]["disposition"]["reason_code"],
        [(s["kind"], s["state"], s["tool"]) for s in fx["records"]["steps"]],
        [(t["tool"], t["window"], t["status"]) for t in fx["records"]["tool_results"]],
        [i["scoring"]["score"] for i in fx["records"]["ingests"]],
        {k: v for k, v in fx["records"]["case_opened"]["pins"].items()
         if k != "evidence_snapshot_sha256"})
    assert shape(got) == shape(want)
