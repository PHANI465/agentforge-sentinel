"""Dataset files, manifests, quality checks and reconciliation.

A manifest is deterministic for a given config (no timings), so it can be tracked and
compared. Runtime and memory measurements go to a separate, untracked run_stats.json.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from pydantic import ValidationError

from data_pipeline.generator import GENERATOR_VERSION, Dataset
from sentinel.contracts.v1 import TransactionInput

FILES = ("accounts.jsonl", "transactions.jsonl", "labels.jsonl")
LABEL_FIELDS = {"is_fraud", "scenario", "label_available_at"}


def line(row: dict) -> bytes:
    return (json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def jsonl(rows: list[dict]) -> bytes:
    return b"".join(line(r) for r in rows)


def currency_totals(transactions: list[dict]) -> dict:
    """Per currency and direction: count and total minor units. Currencies never mix."""
    totals: dict[str, dict] = defaultdict(lambda: {"count": 0, "debit_minor": 0,
                                                   "credit_minor": 0})
    for txn in transactions:
        entry = totals[txn["amount"]["currency"]]
        entry["count"] += 1
        entry[f"{txn['direction']}_minor"] += txn["amount"]["minor_units"]
    return dict(sorted(totals.items()))


def build_manifest(dataset: Dataset) -> dict:
    labels = dataset.labels
    fraud = [label for label in labels if label["is_fraud"]]
    content = {"accounts.jsonl": jsonl(dataset.accounts),
               "transactions.jsonl": jsonl(dataset.transactions),
               "labels.jsonl": jsonl(labels)}
    times = [t["occurred_at"] for t in dataset.transactions]
    return {
        "generator_version": GENERATOR_VERSION,
        "config": dataset.config.to_dict(),
        "truncated_by_max_rows": dataset.truncated,
        "rows": {"accounts": len(dataset.accounts), "transactions": len(dataset.transactions),
                 "labels": len(labels)},
        "sha256": {name: hashlib.sha256(data).hexdigest() for name, data in content.items()},
        "occurred_range": [min(times), max(times)] if times else None,
        "currencies": currency_totals(dataset.transactions),
        "labels": {
            "fraud_rows": len(fraud),
            "fraud_rate_ppm": round(1_000_000 * len(fraud) / len(labels)) if labels else 0,
            "fraud_never_disclosed": sum(1 for f in fraud if f["label_available_at"] is None),
            "by_scenario": dict(sorted(Counter(label["scenario"] for label in labels).items())),
        },
    }


def write(dataset: Dataset, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    (out / "accounts.jsonl").write_bytes(jsonl(dataset.accounts))
    (out / "transactions.jsonl").write_bytes(jsonl(dataset.transactions))
    (out / "labels.jsonl").write_bytes(jsonl(dataset.labels))
    manifest = build_manifest(dataset)
    (out / "manifest.json").write_bytes(
        (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    return manifest


def read(path: Path) -> tuple[list[dict], list[dict], list[dict]]:
    def rows(name):
        return [json.loads(x) for x in (path / name).read_text(encoding="utf-8").splitlines()]
    return rows("accounts.jsonl"), rows("transactions.jsonl"), rows("labels.jsonl")


def quality_problems(accounts: list[dict], transactions: list[dict],
                     labels: list[dict]) -> list[str]:
    """Empty list means the dataset passes schema and integrity checks."""
    problems = []
    account_ids = {a["account_id"] for a in accounts}
    ids = [t["external_id"] for t in transactions]
    if len(set(ids)) != len(ids):
        problems.append("duplicate external_id")
    if [label["external_id"] for label in labels] != ids:
        problems.append("labels are not 1:1 and aligned with transactions")
    for txn in transactions:
        if LABEL_FIELDS & txn.keys():
            problems.append(f"{txn['external_id']}: hidden label field in decision-time row")
        if txn["account_id"] not in account_ids:
            problems.append(f"{txn['external_id']}: unknown account")
        if txn["ingested_at"] < txn["occurred_at"]:
            problems.append(f"{txn['external_id']}: ingested before it occurred")
        try:
            TransactionInput.model_validate({k: v for k, v in txn.items() if k != "ingested_at"})
        except ValidationError as error:
            codes = sorted({e["type"] for e in error.errors(include_input=False)})
            problems.append(f"{txn['external_id']}: contract violation {codes}")
    for label in labels:
        at = label["label_available_at"]
        if at is None and not label["is_fraud"]:
            problems.append(f"{label['external_id']}: legitimate rows always mature")
    return problems


def verify(path: Path) -> list[str]:
    """Hashes, row counts and per-currency totals recomputed from the files."""
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    problems = []
    for name in FILES:
        digest = hashlib.sha256((path / name).read_bytes()).hexdigest()
        if digest != manifest["sha256"][name]:
            problems.append(f"{name}: sha256 mismatch")
    accounts, transactions, labels = read(path)
    if currency_totals(transactions) != manifest["currencies"]:
        problems.append("per-currency totals do not reconcile")
    if len(transactions) != manifest["rows"]["transactions"]:
        problems.append("row count mismatch")
    return problems + quality_problems(accounts, transactions, labels)
