"""Bounded, validated C04 data snapshot built with the accepted C03 code (g1/f1/s1).

Generation is bounded up front by the protocol's accounts/days (max_rows only truncates
after generation, so truncation is rejected rather than accepted). The snapshot recomputes
every count and summary it relies on from the rows themselves instead of trusting
manifest.verify alone (whose derived-summary coverage is partial; C03 review).
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from data_pipeline import features as f1
from data_pipeline import manifest
from data_pipeline.generator import GENERATOR_VERSION, generate

from ml import protocol as proto


class SnapshotError(RuntimeError):
    pass


def peak_rss_mib() -> float | None:
    """Process peak resident memory (Windows working set / POSIX ru_maxrss)."""
    try:
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            class Counters(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                            ("PeakWorkingSetSize", ctypes.c_size_t),
                            ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                            ("PagefileUsage", ctypes.c_size_t),
                            ("PeakPagefileUsage", ctypes.c_size_t)]
            counters = Counters()
            counters.cb = ctypes.sizeof(Counters)
            # Explicit types: the pseudo-handle is 64-bit and would be truncated as an int.
            ctypes.windll.kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            query = ctypes.windll.psapi.GetProcessMemoryInfo
            query.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
            process = ctypes.windll.kernel32.GetCurrentProcess()
            if query(process, ctypes.byref(counters), counters.cb):
                return round(counters.PeakWorkingSetSize / 2**20, 1)
            return None
        import resource
        return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
    except Exception:  # measurement only; never fail the run on it
        return None


@dataclass
class Snapshot:
    accounts: list[dict]
    transactions: list[dict]
    labels: list[dict]
    features: list[dict]
    summary: dict


def recomputed_summary(accounts, transactions, labels) -> dict:
    fraud = [label for label in labels if label["is_fraud"]]
    return {
        "accounts": len(accounts), "transactions": len(transactions), "labels": len(labels),
        "fraud_rows": len(fraud),
        "fraud_never_disclosed": sum(1 for f in fraud if f["label_available_at"] is None),
        "by_scenario": dict(sorted(Counter(label["scenario"] for label in labels).items())),
        "currencies": manifest.currency_totals(transactions),
        "distinct_accounts_in_transactions": len({t["account_id"] for t in transactions}),
    }


def check(snapshot_manifest: dict, summary: dict) -> list[str]:
    """Every manifest summary the ML run relies on must equal the row-level recomputation."""
    problems = []
    expected = {
        "accounts": snapshot_manifest["rows"]["accounts"],
        "transactions": snapshot_manifest["rows"]["transactions"],
        "labels": snapshot_manifest["rows"]["labels"],
        "fraud_rows": snapshot_manifest["labels"]["fraud_rows"],
        "fraud_never_disclosed": snapshot_manifest["labels"]["fraud_never_disclosed"],
        "by_scenario": snapshot_manifest["labels"]["by_scenario"],
        "currencies": snapshot_manifest["currencies"],
    }
    for key, value in expected.items():
        if summary[key] != value:
            problems.append(f"manifest {key} disagrees with the rows")
    if summary["labels"] != summary["transactions"]:
        problems.append("labels are not 1:1 with transactions")
    if summary["distinct_accounts_in_transactions"] > summary["accounts"]:
        problems.append("transactions reference unknown accounts")
    if summary["fraud_rows"] == 0 or summary["fraud_rows"] == summary["labels"]:
        problems.append("one-class dataset")
    return problems


def build(protocol: dict, out: Path) -> tuple[Snapshot, dict]:
    """Generate, write, verify and featurize. Returns (snapshot, provenance)."""
    config = proto.generator_config(protocol)
    if protocol["generator_version"] != GENERATOR_VERSION:
        raise SnapshotError("generator version differs from the protocol")
    if protocol["feature_version"] != f1.FEATURE_VERSION:
        raise SnapshotError("feature version differs from the protocol")
    if list(protocol["features"]) != list(f1.FEATURE_NAMES):
        raise SnapshotError("feature schema differs from the accepted f1 feature set")
    started = time.perf_counter()
    dataset = generate(config)
    if dataset.truncated:
        raise SnapshotError("generation exceeded max_rows; refusing a silently truncated dataset")
    written = manifest.write(dataset, out)
    generate_seconds = time.perf_counter() - started
    problems = manifest.verify(out)
    accounts, transactions, labels = manifest.read(out)
    summary = recomputed_summary(accounts, transactions, labels)
    problems += check(written, summary)
    if problems:
        raise SnapshotError("snapshot validation failed: " + "; ".join(problems[:10]))
    started = time.perf_counter()
    rows = f1.batch_features(transactions, accounts, labels)
    feature_seconds = time.perf_counter() - started
    feature_bytes = manifest.jsonl(rows)
    (out / f"features.{f1.FEATURE_VERSION}.jsonl").write_bytes(feature_bytes)
    provenance = {
        "generator_version": GENERATOR_VERSION, "feature_version": f1.FEATURE_VERSION,
        "dataset_sha256": written["sha256"],
        "features_sha256": hashlib.sha256(feature_bytes).hexdigest(),
        "manifest_sha256": hashlib.sha256((out / "manifest.json").read_bytes()).hexdigest(),
        "summary": summary,
        "runtime": {"generate_seconds": round(generate_seconds, 2),
                    "feature_seconds": round(feature_seconds, 2),
                    "peak_rss_mib": peak_rss_mib()},
    }
    return Snapshot(accounts, transactions, labels, rows, summary), provenance


def load(out: Path, provenance: dict) -> Snapshot:
    """Reload a written snapshot, refusing any hash or summary mismatch with provenance."""
    if manifest.verify(out):
        raise SnapshotError("snapshot files fail C03 verification")
    snapshot_manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    if snapshot_manifest["sha256"] != provenance["dataset_sha256"]:
        raise SnapshotError("dataset hashes differ from the recorded provenance")
    feature_path = out / f"features.{provenance['feature_version']}.jsonl"
    if hashlib.sha256(feature_path.read_bytes()).hexdigest() != provenance["features_sha256"]:
        raise SnapshotError("feature file hash differs from the recorded provenance")
    accounts, transactions, labels = manifest.read(out)
    summary = recomputed_summary(accounts, transactions, labels)
    problems = check(snapshot_manifest, summary)
    if problems or summary != provenance["summary"]:
        raise SnapshotError("snapshot summary differs from the recorded provenance")
    rows = [json.loads(line) for line in feature_path.read_text(encoding="utf-8").splitlines()]
    return Snapshot(accounts, transactions, labels, rows, summary)
