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


def test_generator_unchanged_since_the_capture_commit(tracked):
    commit = tracked[0]["provenance"]["generator_commit"]
    if shutil.which("git") is None or demo._git("cat-file", "-e", commit).returncode != 0:
        pytest.skip("capture commit not available in this checkout")
    changed = demo._git("diff", "--name-only", commit, "HEAD", "--", "src",
                        "scripts/build_recorded_demo.py").stdout.split()
    assert changed == [], "re-run the capture: generator or application changed"


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
