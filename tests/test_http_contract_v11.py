"""C07 contract candidate: explicit HTTP v1.1 revision, frozen legacy v1 compatibility,
scorer identity binding and frozen offline results."""
import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from sentinel import model_results, scorers
from sentinel.contracts import http_v1
from sentinel.contracts.v1 import ScoringOutcome

ROOT = Path(__file__).resolve().parents[1]
HTTP = ROOT / "contracts" / "http"
spec = importlib.util.spec_from_file_location("export_http_contract",
                                              ROOT / "scripts" / "export_http_contract.py")
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)
LEGACY = json.loads((HTTP / "openapi.v1.json").read_text(encoding="utf-8"))
ACTIVE = json.loads((HTTP / "openapi.v1.1.json").read_text(encoding="utf-8"))


# ---- legacy v1 stays frozen and v1.1 is a compatible superset ---------------------------

def test_legacy_v1_snapshot_is_frozen():
    digest = hashlib.sha256((HTTP / "openapi.v1.json").read_bytes()).hexdigest()
    assert digest == exporter.LEGACY_V1_SHA256
    assert LEGACY["info"]["version"] == "1.0.0" and ACTIVE["info"]["version"] == "1.1.0"


def test_active_snapshot_matches_code():
    assert (HTTP / "openapi.v1.1.json").read_bytes() == exporter.dumps(exporter.openapi())


def test_every_v1_operation_survives_unchanged_in_v11():
    for path, operations in LEGACY["paths"].items():
        assert path in ACTIVE["paths"], path
        for method, operation in operations.items():
            new = ACTIVE["paths"][path][method]
            assert new.get("requestBody") == operation.get("requestBody"), (path, method)
            assert new["responses"].keys() >= operation["responses"].keys(), (path, method)
            for status, response in operation["responses"].items():
                assert new["responses"][status] == response, (path, method, status)
            assert new.get("security") == operation.get("security")
    assert set(ACTIVE["paths"]) - set(LEGACY["paths"]) == {"/v1/scoring",
                                                           "/v1/model-results/{results_id}"}


def _enums(node, path=()):
    if isinstance(node, dict):
        if "enum" in node:
            yield path, set(node["enum"])
        for key, value in node.items():
            yield from _enums(value, (*path, key))
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from _enums(value, (*path, i))


def test_v1_component_schemas_only_widen():
    old, new = LEGACY["components"]["schemas"], ACTIVE["components"]["schemas"]
    for name, schema in old.items():
        assert name in new, name
        widened = new[name]
        assert set(schema.get("properties", {})) <= set(widened.get("properties", {})), name
        assert set(widened.get("required", [])) == set(schema.get("required", [])), name
        new_enums = dict(_enums(widened))
        for path, values in _enums(schema):
            assert values <= new_enums.get(path, set()), (name, path)


def test_v1_examples_still_validate():
    for path in sorted((HTTP / "examples").glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if record["status"] >= 400 or path.stem not in exporter.EXAMPLE_MODELS:
            continue
        name = exporter.EXAMPLE_MODELS[path.stem]
        model = getattr(http_v1, name, None)
        if model is not None:
            model.model_validate(record["response"])


# ---- v1.1 examples and semantics ---------------------------------------------------------

def v11(name):
    return json.loads((HTTP / "examples-v1.1" / f"{name}.json").read_text(encoding="utf-8"))


def test_v11_examples_validate_and_label_semantics():
    rule, model = v11("scorer_rule_mode")["response"], v11("scorer_model_mode")["response"]
    http_v1.ScorerInfo.model_validate(rule)
    http_v1.ScorerInfo.model_validate(model)
    assert (rule["scoring_kind"], rule["score_semantics"], rule["model"]) == (
        "rule", "heuristic", None)
    assert (model["scoring_kind"], model["score_semantics"]) == ("model", "uncalibrated_score")
    assert model["threshold"] == scorers.REGISTRY["hgb_balanced@p1"].threshold
    assert model["model"]["results_id"] == "p1"
    assert v11("error_model_results_not_found") ["response"] == {"error": "not_found"}
    assert v11("error_model_results_permission")["status"] == 403


def test_model_results_match_the_frozen_c04_report():
    body = v11("model_results_p1")["response"]
    http_v1.ModelResults.model_validate(body)
    report = json.loads((ROOT / "evals" / "ml" / "p1" / "test_report.json").read_text())
    assert body["label"] == "offline synthetic benchmark" and body["synthetic"] is True
    assert body["selected"] == report["selected"] == "hgb_balanced"
    assert {c["name"]: c["test_average_precision"] for c in body["candidates"]} == {
        c["name"]: c["test"]["average_precision"] for c in report["candidates"]}
    assert body["selected_policy"]["daily_top_k"] == report["selected_policy"]["daily_top_k"]
    assert body["slices"] == report["slices_daily_top_k"]
    assert body["splits"]["test"] == report["split"]


def test_packaged_results_are_byte_copies_of_the_frozen_report():
    for name in ("test_report.json", "pr_curve_selected.csv"):
        packaged = ROOT / "ml" / "results" / "p1" / name
        assert packaged.read_bytes() == (ROOT / "evals" / "ml" / "p1" / name).read_bytes()


def test_unknown_or_path_like_results_ids_are_not_found():
    for results_id in ("p2", "../p1", "..\\p1", "", "p1/../p1"):
        assert model_results.load(results_id) is None


# ---- domain contract: rule outcomes unchanged, model outcomes fully attributed -----------

def rule_outcome(**changes):
    sample = json.loads((HTTP / "examples" / "ingest_alert.json").read_text())
    return {**sample["response"]["scoring"], **changes}


def test_rule_outcome_serializes_exactly_as_v1():
    body = rule_outcome()
    assert ScoringOutcome.model_validate(body).model_dump(mode="json") == body
    assert "model" not in ScoringOutcome.model_validate(body).model_dump(mode="json")


@pytest.mark.parametrize("changes", [
    {"score_semantics": "uncalibrated_score"},  # a rule is never an uncalibrated model score
    {"scoring_kind": "model", "score_semantics": "heuristic"},
    {"scoring_kind": "model", "score_semantics": "uncalibrated_score"},  # no provenance
])
def test_semantics_and_provenance_are_enforced(changes):
    with pytest.raises(ValidationError):
        ScoringOutcome.model_validate(rule_outcome(**changes))


# ---- scorer identity binding: refused before deserialization -------------------------------

@pytest.fixture
def ml_copy(tmp_path, monkeypatch):
    root = tmp_path / "ml"
    source = scorers.ml_root()
    shutil.copytree(source, root, ignore=shutil.ignore_patterns("__pycache__"))
    return root


def edit(path, change):
    document = json.loads(path.read_text(encoding="utf-8"))
    change(document)
    path.write_text(json.dumps(document), encoding="utf-8")


def test_intact_copy_binds_and_loads(ml_copy):
    pipeline, protocol = scorers.bind_and_load(scorers.REGISTRY["hgb_balanced@p1"], ml_copy)
    assert protocol["protocol_version"] == "p1" and hasattr(pipeline, "predict_proba")


@pytest.mark.parametrize("target, change, field", [
    ("protocol.json", lambda d: d["review_policy"].update(k_per_day=16), "protocol_sha256"),
    ("runs/p1/selection.json", lambda d: d.update(frozen_threshold=0.5), "selection_sha256"),
    ("runs/p1/selection.json", lambda d: d.update(selected="logreg_unweighted"),
     "selection.selected"),
    ("artifacts/p1/manifest.json", lambda d: d["candidate"].update(name="hgb_unweighted"),
     "manifest.candidate"),
    ("artifacts/p1/manifest.json", lambda d: d.update(frozen_threshold=0.1),
     "manifest.frozen_threshold"),
    ("artifacts/p1/manifest.json", lambda d: d.update(artifact_sha256="0" * 64),
     "manifest.artifact_sha256"),
    ("artifacts/p1/manifest.json", lambda d: d.update(models_code_sha256="1" * 64),
     "manifest.models_code_sha256"),
    ("artifacts/p1/manifest.json", lambda d: d.update(protocol_sha256="2" * 64),
     "manifest.protocol_sha256"),
])
def test_identity_mismatch_is_refused_before_loading(ml_copy, monkeypatch, target, change,
                                                     field):
    import ml.artifact
    monkeypatch.setattr(ml.artifact, "load_trusted",
                        lambda *a, **k: pytest.fail("deserialization was attempted"))
    edit(ml_copy / target, change)
    with pytest.raises(scorers.ScorerError, match=field.replace(".", r"\.")):
        scorers.bind_and_load(scorers.REGISTRY["hgb_balanced@p1"], ml_copy)


def test_tampered_artifact_bytes_are_refused(ml_copy):
    model = ml_copy / "artifacts" / "p1" / "model.joblib"
    model.write_bytes(model.read_bytes() + b"\x00")
    with pytest.raises(scorers.ScorerError, match="trusted artifact refused"):
        scorers.bind_and_load(scorers.REGISTRY["hgb_balanced@p1"], ml_copy)


@pytest.mark.parametrize("value", ["model:../../tmp/x", "model:hgb_balanced", "auto",
                                   "model:hgb_balanced@p2", ""])
def test_only_registered_scorers_can_be_configured(monkeypatch, value):
    monkeypatch.setenv("SENTINEL_SCORER", value)
    with pytest.raises(scorers.ScorerError):
        scorers.from_environment()


def test_default_scorer_is_the_rule(monkeypatch):
    monkeypatch.delenv("SENTINEL_SCORER", raising=False)
    assert isinstance(scorers.from_environment(), scorers.RuleScorer)
