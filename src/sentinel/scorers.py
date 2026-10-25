"""Scorer configuration (C07): the explicit rule baseline (default) or an accepted trained
model from a fixed registry. Chosen once by the operator (SENTINEL_SCORER) at startup;
no request, visitor or model output can select an artifact or path. There is no fallback:
a configured model that fails its identity binding makes startup fail.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from sentinel import scoring
from sentinel.contracts.v1 import ArtifactRef, ModelProvenance, canonical_digest

RULE = "rule"


class ScorerError(RuntimeError):
    """The configured scorer cannot be used. The message names fields, never file contents."""


@dataclass(frozen=True)
class AcceptedModel:
    """The identity Codex accepted for C04 (09b5378). Every field is checked before load."""
    key: str
    results_id: str
    protocol_version: str
    protocol_sha256: str
    selection_sha256: str
    candidate: str
    artifact_sha256: str
    models_code_sha256: str
    feature_version: str
    threshold: float


REGISTRY = {
    "hgb_balanced@p1": AcceptedModel(
        key="hgb_balanced@p1", results_id="p1", protocol_version="p1",
        protocol_sha256="bed52b8108bd855f4fa467c2e992e5e33c9a37871dec7664129d58b0dba561e9",
        selection_sha256="940e85502435426861537aff20074249b8ea6c30193f57309b15b3610e09293b",
        candidate="hgb_balanced",
        artifact_sha256="6c2982d1df12184f704bc45dbc5882d8f85dba16c50bd9829dda9e674602575b",
        models_code_sha256="3a3f27bfa845367c0b5e323347be8ce7ed4584a24781fa0b9de8f80212e9aba6",
        feature_version="f1", threshold=4.0295386895426815e-06),
}


def ml_root() -> Path:
    """The installed (or source) `ml` package directory: the only trusted model location."""
    import ml
    return Path(ml.__file__).resolve().parent


class RuleScorer:
    mode = RULE
    scoring_kind = "rule"
    score_semantics = "heuristic"
    scorer = scoring.SCORER
    features = scoring.FEATURES
    threshold_policy = scoring.THRESHOLD_POLICY
    threshold = scoring.THRESHOLD
    model = None
    results_id = None

    def info(self) -> dict:
        return _info(self, ["Rule heuristic r1 (velocity and amount); not a probability."])


class ModelScorer:
    mode = "model"
    scoring_kind = "model"
    score_semantics = "uncalibrated_score"

    def __init__(self, accepted: AcceptedModel, root: Path | None = None):
        self.accepted = accepted
        self.pipeline, self.protocol = bind_and_load(accepted, root or ml_root())
        self.threshold = accepted.threshold
        self.results_id = accepted.results_id
        self.scorer = ArtifactRef(name=accepted.candidate, version=accepted.protocol_version,
                                  sha256=accepted.artifact_sha256)
        self.features = ArtifactRef(
            name="sentinel-features", version=accepted.feature_version,
            sha256=canonical_digest("sentinel.feature-schema.v1", {
                "feature_version": accepted.feature_version,
                "features": list(self.protocol["features"]),
                "categorical_features": self.protocol["categorical_features"]}))
        self.threshold_policy = ArtifactRef(
            name="c04-frozen-threshold", version=accepted.protocol_version,
            sha256=canonical_digest("sentinel.threshold.v1", {
                "threshold": accepted.threshold, "selection_sha256": accepted.selection_sha256,
                "review_policy": self.protocol["review_policy"]}))
        self.model = ModelProvenance(
            protocol_version=accepted.protocol_version,
            protocol_sha256=accepted.protocol_sha256,
            selection_sha256=accepted.selection_sha256, candidate=accepted.candidate,
            artifact_sha256=accepted.artifact_sha256,
            feature_version=accepted.feature_version,
            threshold_source="validation_frozen_threshold", results_id=accepted.results_id)

    def info(self) -> dict:
        return _info(self, [
            "Uncalibrated model score in [0, 1] used for ranking; not a fraud probability.",
            "Alerts use the frozen validation threshold (score >= threshold), not the "
            "offline daily top-k batch policy.",
            "Trained and evaluated on synthetic data only."])


def _info(scorer, notes: list[str]) -> dict:
    return {"mode": scorer.mode, "scoring_kind": scorer.scoring_kind,
            "score_semantics": scorer.score_semantics,
            "scorer": scorer.scorer.model_dump(mode="json"),
            "features": scorer.features.model_dump(mode="json"),
            "threshold_policy": scorer.threshold_policy.model_dump(mode="json"),
            "threshold": scorer.threshold, "alert_rule": "score >= threshold",
            "model": scorer.model.model_dump(mode="json") if scorer.model else None,
            "results_id": scorer.results_id, "notes": notes}


def _json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ScorerError(f"cannot read {path.name}") from None


def bind_and_load(accepted: AcceptedModel, root: Path):
    """Bind manifest, protocol and selection to the accepted identity, then (and only then)
    hand the artifact to the C04 trusted loader. Returns (pipeline, protocol)."""
    from ml import artifact
    from ml import protocol as proto

    protocol = _json(root / "protocol.json")
    selection = _json(root / "runs" / accepted.protocol_version / "selection.json")
    manifest_path = root / "artifacts" / accepted.protocol_version / artifact.MANIFEST_FILE
    manifest = _json(manifest_path)
    found = {
        "protocol_sha256": proto.digest(protocol),
        "protocol_version": protocol.get("protocol_version"),
        "selection_sha256": proto.digest(selection),
        "selection.protocol_sha256": selection.get("protocol_sha256"),
        "selection.selected": selection.get("selected"),
        "selection.artifact_sha256": selection.get("artifact_sha256"),
        "selection.frozen_threshold": selection.get("frozen_threshold"),
        "manifest.protocol_sha256": manifest.get("protocol_sha256"),
        "manifest.candidate": (manifest.get("candidate") or {}).get("name"),
        "manifest.artifact_sha256": manifest.get("artifact_sha256"),
        "manifest.frozen_threshold": manifest.get("frozen_threshold"),
        "manifest.review_policy": manifest.get("review_policy"),
        "manifest.feature_version": manifest.get("feature_version"),
        "manifest.models_code_sha256": manifest.get("models_code_sha256"),
    }
    expected = {
        "protocol_sha256": accepted.protocol_sha256,
        "protocol_version": accepted.protocol_version,
        "selection_sha256": accepted.selection_sha256,
        "selection.protocol_sha256": accepted.protocol_sha256,
        "selection.selected": accepted.candidate,
        "selection.artifact_sha256": accepted.artifact_sha256,
        "selection.frozen_threshold": accepted.threshold,
        "manifest.protocol_sha256": accepted.protocol_sha256,
        "manifest.candidate": accepted.candidate,
        "manifest.artifact_sha256": accepted.artifact_sha256,
        "manifest.frozen_threshold": accepted.threshold,
        "manifest.review_policy": protocol.get("review_policy"),
        "manifest.feature_version": accepted.feature_version,
        "manifest.models_code_sha256": accepted.models_code_sha256,
    }
    mismatched = sorted(k for k in expected if found[k] != expected[k])
    if mismatched:
        raise ScorerError(f"model identity binding failed: {mismatched}")
    try:
        pipeline, _ = artifact.load_trusted(manifest_path, root / "artifacts", protocol)
    except artifact.ArtifactError as error:
        raise ScorerError(f"trusted artifact refused: {error}") from None
    return pipeline, protocol


def from_environment():
    choice = os.environ.get("SENTINEL_SCORER", RULE)
    if choice == RULE:
        return RuleScorer()
    if choice.startswith("model:") and choice[len("model:"):] in REGISTRY:
        return ModelScorer(REGISTRY[choice[len("model:"):]])
    raise ScorerError("SENTINEL_SCORER must be 'rule' or 'model:<accepted key>' "
                      f"(accepted: {sorted(REGISTRY)})")
