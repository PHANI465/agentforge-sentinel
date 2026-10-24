"""C04 trusted artifact: round trip and fail-closed refusal before deserialization."""
import json
import shutil

import numpy as np
import pytest

from ml import artifact, models
from ml import protocol as proto

PROTOCOL, DIGEST = proto.load()


@pytest.fixture
def saved(tmp_path):
    rng = np.random.default_rng(1)
    n = len(PROTOCOL["features"])
    X = np.empty((120, n + 1), dtype=object)
    X[:, :n] = rng.integers(0, 500, size=(120, n))
    X[:, n] = rng.choice(["USD", "GBP", "INR", "JPY"], size=120)
    y = np.array([0, 0, 1] * 40)
    model = models.build(PROTOCOL, PROTOCOL["candidates"][1]).fit(X, y)
    root = tmp_path / "trusted"
    manifest = artifact.save(root / "m", model, {
        "feature_version": PROTOCOL["feature_version"], "features": list(PROTOCOL["features"]),
        "categorical_features": PROTOCOL["categorical_features"], "protocol_sha256": DIGEST})
    return root, model, X, manifest


def test_round_trip_predictions_are_identical(saved):
    root, model, X, _ = saved
    loaded, manifest = artifact.load_trusted(root / "m" / "manifest.json", root, PROTOCOL)
    assert np.array_equal(models.scores(loaded, X), models.scores(model, X))
    assert manifest["artifact_sha256"] == artifact.sha256(root / "m" / "model.joblib")


def test_tampered_bytes_are_refused(saved):
    root, *_ = saved
    path = root / "m" / "model.joblib"
    path.write_bytes(path.read_bytes() + b"\x00")
    with pytest.raises(artifact.ArtifactError, match="hash"):
        artifact.load_trusted(root / "m" / "manifest.json", root, PROTOCOL)


@pytest.mark.parametrize("field, value", [
    ("features", ["amount_minor"]), ("feature_version", "f2"), ("format", "other"),
    ("models_code_sha256", "0" * 64)])
def test_schema_or_version_mismatch_is_refused(saved, field, value):
    root, *_ = saved
    path = root / "m" / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest[field] = value
    path.write_text(json.dumps(manifest))
    with pytest.raises(artifact.ArtifactError, match=field):
        artifact.load_trusted(path, root, PROTOCOL)


def test_library_version_mismatch_is_refused(saved):
    root, *_ = saved
    path = root / "m" / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["environment"]["scikit_learn"] = "0.0.1"
    path.write_text(json.dumps(manifest))
    with pytest.raises(artifact.ArtifactError, match="scikit_learn"):
        artifact.load_trusted(path, root, PROTOCOL)


def test_artifact_outside_the_trusted_root_is_refused(saved, tmp_path):
    root, *_ = saved
    elsewhere = tmp_path / "untrusted"
    shutil.copytree(root / "m", elsewhere / "m")
    with pytest.raises(artifact.ArtifactError, match="trusted root"):
        artifact.load_trusted(elsewhere / "m" / "manifest.json", root, PROTOCOL)
