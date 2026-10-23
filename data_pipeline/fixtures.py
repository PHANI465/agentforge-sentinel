"""Tracked fixtures: the reference manifest (data stays ignored) and a tiny reviewable dataset.

Regenerate both with `python -m data_pipeline refresh-fixtures`; tests fail on drift.
"""
from __future__ import annotations

import json
from pathlib import Path

from data_pipeline import manifest
from data_pipeline.generator import GeneratorConfig, generate

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = GeneratorConfig()
REFERENCE_MANIFEST = ROOT / "data_pipeline" / "manifests" / "reference-g1-seed7.json"
# Small but scenario-rich: high episode rates so every scenario appears in a few hundred rows.
TINY = GeneratorConfig(seed=11, accounts=24, days=6, fraud_account_rate=0.4,
                       lookalike_account_rate=0.4)
TINY_DIR = ROOT / "tests" / "data" / "fixtures" / "tiny"


def manifest_bytes(config: GeneratorConfig) -> bytes:
    data = manifest.build_manifest(generate(config))
    return (json.dumps(data, indent=2, sort_keys=True) + "\n").encode("utf-8")


def refresh() -> None:
    REFERENCE_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    REFERENCE_MANIFEST.write_bytes(manifest_bytes(REFERENCE))
    manifest.write(generate(TINY), TINY_DIR)
