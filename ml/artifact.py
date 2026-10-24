"""Trusted local model artifacts (C04).

joblib/pickle executes code on load, so only artifacts this project produced locally are
ever loaded: the manifest must sit inside an explicitly trusted root (no links), the artifact
bytes must match the manifest's SHA-256, and the format, feature schema, scikit-learn
version and the models code it references must all match. Anything else is refused before
deserialization. Never load a visitor-supplied model, a remote path or an untrusted blob.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
from pathlib import Path

import joblib
import numpy
import sklearn

from ml import protocol as proto

FORMAT = "sentinel.c04.model.v1"
MODEL_FILE = "model.joblib"
MANIFEST_FILE = "manifest.json"
MODELS_CODE = proto.ROOT / "ml" / "models.py"


class ArtifactError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def environment() -> dict:
    return {"python": platform.python_version(), "scikit_learn": sklearn.__version__,
            "numpy": numpy.__version__, "joblib": joblib.__version__}


def save(directory: Path, model, manifest: dict) -> dict:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, directory / MODEL_FILE, compress=3)
    full = {**manifest, "format": FORMAT, "environment": environment(),
            "models_code_sha256": sha256(MODELS_CODE),
            "artifact_file": MODEL_FILE, "artifact_sha256": sha256(directory / MODEL_FILE)}
    (directory / MANIFEST_FILE).write_text(json.dumps(full, indent=2, sort_keys=True) + "\n",
                                           encoding="utf-8")
    return full


def _within(path: Path, root: Path) -> bool:
    try:
        Path(os.path.realpath(path)).relative_to(os.path.realpath(root))
        return True
    except ValueError:
        return False


def load_trusted(manifest_path: Path, trusted_root: Path, protocol: dict):
    """Return (model, manifest) or raise ArtifactError without deserializing anything."""
    manifest_path, trusted_root = Path(manifest_path), Path(trusted_root)
    directory = manifest_path.parent
    for path in (manifest_path, directory, directory / MODEL_FILE):
        if os.path.islink(path) or not _within(path, trusted_root):
            raise ArtifactError("artifact is outside the trusted root or is a link")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ArtifactError("manifest is unreadable") from None
    checks = {
        "format": (manifest.get("format"), FORMAT),
        "artifact_file": (manifest.get("artifact_file"), MODEL_FILE),
        "feature_version": (manifest.get("feature_version"), protocol["feature_version"]),
        "features": (manifest.get("features"), list(protocol["features"])),
        "categorical_features": (manifest.get("categorical_features"),
                                 protocol["categorical_features"]),
        "scikit_learn": (manifest.get("environment", {}).get("scikit_learn"),
                         sklearn.__version__),
        "models_code_sha256": (manifest.get("models_code_sha256"), sha256(MODELS_CODE)),
    }
    for name, (found, expected) in checks.items():
        if found != expected:
            raise ArtifactError(f"artifact {name} does not match this environment/protocol")
    model_path = directory / MODEL_FILE
    if not model_path.is_file() or sha256(model_path) != manifest.get("artifact_sha256"):
        raise ArtifactError("artifact bytes do not match the manifest hash")
    return joblib.load(model_path), manifest
