"""C03: deterministic generation, tracked fixtures, quality checks and reconciliation."""
import json
from dataclasses import replace
from datetime import timedelta

from data_pipeline import fixtures, manifest
from data_pipeline.features import ts
from data_pipeline.generator import (
    FRAUD_SCENARIOS, LEGIT_MATURITY, LOOKALIKE_SCENARIOS, GeneratorConfig, generate,
)

SMALL = GeneratorConfig(seed=3, accounts=60, days=8)


def test_same_config_gives_identical_bytes_and_seed_changes_them():
    a, b = generate(SMALL), generate(SMALL)
    assert manifest.jsonl(a.transactions) == manifest.jsonl(b.transactions)
    assert manifest.jsonl(a.labels) == manifest.jsonl(b.labels)
    other = generate(replace(SMALL, seed=4))
    assert manifest.jsonl(other.transactions) != manifest.jsonl(a.transactions)


def test_tracked_reference_manifest_reproduces():
    assert fixtures.REFERENCE_MANIFEST.read_bytes() == fixtures.manifest_bytes(fixtures.REFERENCE), (
        "run: python -m data_pipeline refresh-fixtures")


def test_tracked_tiny_fixture_reproduces(tmp_path):
    manifest.write(generate(fixtures.TINY), tmp_path)
    for name in (*manifest.FILES, "manifest.json"):
        assert (tmp_path / name).read_bytes() == (fixtures.TINY_DIR / name).read_bytes(), name
    assert manifest.verify(fixtures.TINY_DIR) == []


def test_reference_has_imbalance_and_every_scenario():
    m = json.loads(fixtures.REFERENCE_MANIFEST.read_text())
    assert 2_000 <= m["labels"]["fraud_rate_ppm"] <= 30_000  # 0.2%..3%: realistic imbalance
    assert set(m["labels"]["by_scenario"]) == {"normal", *FRAUD_SCENARIOS, *LOOKALIKE_SCENARIOS}
    assert m["truncated_by_max_rows"] is False
    assert set(m["currencies"]) == {"USD", "GBP", "INR", "JPY"}


def test_decision_time_rows_are_contract_valid_and_label_free():
    data = generate(SMALL)
    assert manifest.quality_problems(data.accounts, data.transactions, data.labels) == []
    for txn in data.transactions:
        assert set(txn) == {"external_id", "account_id", "amount", "direction", "occurred_at",
                            "ingested_at"}


def test_label_timing_is_delayed_and_legit_labels_mature():
    data = generate(SMALL)
    occurred = {t["external_id"]: ts(t["occurred_at"]) for t in data.transactions}
    for label in data.labels:
        t = occurred[label["external_id"]]
        if label["is_fraud"]:
            assert label["label_available_at"] is None or ts(label["label_available_at"]) >= \
                t + timedelta(days=1)
        else:
            assert ts(label["label_available_at"]) == t + LEGIT_MATURITY


def test_quality_checks_catch_leaks_and_bad_rows():
    data = generate(SMALL)
    leaked = [dict(data.transactions[0], is_fraud=False), *data.transactions[1:]]
    assert any("hidden label" in p for p in
               manifest.quality_problems(data.accounts, leaked, data.labels))
    early = [dict(data.transactions[0], ingested_at="2026-08-01T00:00:00.000000Z"),
             *data.transactions[1:]]
    assert any("ingested before" in p for p in
               manifest.quality_problems(data.accounts, early, data.labels))
    bad = [dict(data.transactions[0], amount={**data.transactions[0]["amount"],
                                               "currency_exponent": 0 if data.transactions[0]
                                               ["amount"]["currency"] != "JPY" else 2}),
           *data.transactions[1:]]
    assert any("contract violation" in p for p in
               manifest.quality_problems(data.accounts, bad, data.labels))


def test_reconciliation_detects_tampering(tmp_path):
    manifest.write(generate(SMALL), tmp_path)
    assert manifest.verify(tmp_path) == []
    rows = (tmp_path / "transactions.jsonl").read_text().splitlines()
    first = json.loads(rows[0])
    first["amount"]["minor_units"] += 1
    rows[0] = manifest.line(first).decode().rstrip("\n")
    (tmp_path / "transactions.jsonl").write_text("\n".join(rows) + "\n")
    problems = manifest.verify(tmp_path)
    assert "transactions.jsonl: sha256 mismatch" in problems
    assert "per-currency totals do not reconcile" in problems


def test_per_currency_totals_never_mix_currencies():
    data = generate(SMALL)
    totals = manifest.currency_totals(data.transactions)
    for currency, entry in totals.items():
        rows = [t for t in data.transactions if t["amount"]["currency"] == currency]
        assert entry["count"] == len(rows)
        assert entry["debit_minor"] + entry["credit_minor"] == sum(
            t["amount"]["minor_units"] for t in rows)


def test_row_limit_truncates_honestly():
    data = generate(replace(SMALL, max_rows=100))
    assert len(data.transactions) == 100 and data.truncated
    assert [t["occurred_at"] for t in data.transactions] == sorted(
        t["occurred_at"] for t in data.transactions)
