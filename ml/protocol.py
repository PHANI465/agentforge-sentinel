"""The frozen C04 evaluation protocol (ml/protocol.json) and its digest.

Everything that shapes model selection or test metrics lives in the protocol and is fixed
before any test score is computed: data config, decision-time windows, label views, feature
schema, the candidate budget, the review-capacity/tie/threshold policy and the bootstrap.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

from data_pipeline.generator import EPOCH, GeneratorConfig

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "ml" / "protocol.json"


def canonical(document: dict) -> bytes:
    return json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(document: dict) -> str:
    return hashlib.sha256(canonical(document)).hexdigest()


def load(path: Path = PROTOCOL_PATH) -> tuple[dict, str]:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    return document, digest(document)


def generator_config(protocol: dict) -> GeneratorConfig:
    values = dict(protocol["generator"])
    values["daily_rate_range"] = tuple(values["daily_rate_range"])
    return GeneratorConfig(**values)


def day(protocol: dict, offset_days: float) -> datetime:
    """Protocol day offsets are measured from the generator epoch (UTC midnight)."""
    return EPOCH + timedelta(days=offset_days)


def window(protocol: dict, name: str) -> tuple[datetime, datetime]:
    start, end = protocol["windows"][name]
    return day(protocol, start), day(protocol, end)
