"""Deterministic feedback measures over typed records.

Counts keep their population; every ratio is a numerator/denominator pair (0/0 is shown by the
consumer as n/a). Unknown values are never treated as zero, and currencies are never merged.
"""

from __future__ import annotations

from collections import defaultdict

from . import normalize as nz

FIELDS = ("date", "description", "amount", "currency", "balance", "reference")


def _ratio(n: int, d: int) -> dict:
    return {"numerator": n, "denominator": d}


def missingness(records: list[dict]) -> dict:
    txns = [r for r in records if r["kind"] == "transaction"]
    result = {}
    for name in FIELDS:
        counts = {"known": 0, "missing": 0, "unknown": 0}
        present = 0
        for r in txns:
            part = r.get(name)
            if part is None:
                continue
            present += 1
            status = part["status"]
            counts["known" if status == nz.KNOWN else "missing" if status == nz.MISSING
                   else "unknown"] += 1
        result[name] = dict(counts, population=present,
                            missing_ratio=_ratio(counts["missing"], present),
                            unknown_ratio=_ratio(counts["unknown"], present))
    return {"population": "transaction records", "count": len(txns), "fields": result}


def duplicates(records: list[dict]) -> dict:
    groups: dict[tuple, list[str]] = defaultdict(list)
    not_checkable = 0
    txns = [r for r in records if r["kind"] == "transaction"]
    for r in txns:
        if r["date"]["status"] != nz.KNOWN or r["amount"]["status"] != nz.KNOWN \
                or r["currency"]["status"] != nz.KNOWN:
            not_checkable += 1
            continue
        key = (r["date"]["value"], r["amount"]["minor_units"], r["currency"]["value"],
               " ".join((r["description"]["raw"] or "").lower().split()),
               (r["reference"]["raw"] or "").strip())
        groups[key].append(r["evidence_id"])
    dup = [{"evidence_ids": ids, "count": len(ids)} for ids in groups.values() if len(ids) > 1]
    return {"rule": "identical date, minor-unit amount, currency, whitespace/case-normalised "
                    "description and reference",
            "checked_records": len(txns) - not_checkable, "not_checkable_records": not_checkable,
            "groups": dup, "rows_in_duplicate_groups": sum(g["count"] for g in dup),
            "interpretation": "possible duplicate rows; not evidence of fraud"}


def reconciliation(records: list[dict]) -> dict:
    """Per currency: opening + credits − debits − closing (signed amounts, minor units)."""
    by_ccy: dict[str, dict] = {}
    unknown_currency_rows: list[str] = []

    def bucket(code: str) -> dict:
        return by_ccy.setdefault(code, {"openings": [], "closings": [], "credits": 0,
                                        "debits": 0, "transactions": 0, "unknown_amounts": [],
                                        "exponent": nz.CURRENCY_EXPONENTS.get(code)})

    for r in records:
        ccy = r["currency"]
        if ccy["status"] != nz.KNOWN:
            unknown_currency_rows.append(r["evidence_id"])
            continue
        b = bucket(ccy["value"])
        if r["kind"] == "transaction":
            b["transactions"] += 1
            amt = r["amount"]
            if amt["status"] != nz.KNOWN:
                b["unknown_amounts"].append(r["evidence_id"])
                continue
            minor = int(amt["minor_units"])
            if minor >= 0:
                b["credits"] += minor
            else:
                b["debits"] += -minor
        else:
            bal = r["balance"]
            target = b["openings"] if r["kind"] == "opening_balance" else b["closings"]
            target.append((bal["minor_units"] if bal["status"] == nz.KNOWN else None,
                           r["evidence_id"]))
    out = []
    for code in sorted(by_ccy):
        b = by_ccy[code]
        entry = {"currency": code, "exponent": b["exponent"],
                 "transaction_count": b["transactions"],
                 "credits_minor": str(b["credits"]), "debits_minor": str(b["debits"]),
                 "unknown_amount_count": len(b["unknown_amounts"]),
                 "unknown_amount_evidence_ids": b["unknown_amounts"][:50],
                 "opening": None, "closing": None, "difference_minor": None,
                 "sign_convention": "credits positive, debits negative"}
        reason = None
        for label, items in (("opening", b["openings"]), ("closing", b["closings"])):
            values = {v for v, _e in items}
            if not items:
                reason = reason or f"{label}_balance_absent"
            elif len(items) > 1 and len(values) > 1:
                reason = reason or f"conflicting_{label}_balances"
            elif None in values:
                reason = reason or f"{label}_balance_unknown"
            else:
                entry[label] = {"minor_units": items[0][0],
                                "evidence_ids": [e for _v, e in items]}
        if reason is None and b["unknown_amounts"]:
            reason = "unknown_transaction_amounts"
        if reason is None:
            diff = int(entry["opening"]["minor_units"]) + b["credits"] - b["debits"] \
                - int(entry["closing"]["minor_units"])
            entry["difference_minor"] = str(diff)
            entry["status"] = "reconciled" if diff == 0 else "difference"
        else:
            entry["status"] = "not_checkable"
            entry["reason"] = reason
        out.append(entry)
    return {"currencies": out, "unknown_currency_records": len(unknown_currency_rows),
            "unknown_currency_evidence_ids": unknown_currency_rows[:50],
            "rule": "opening + credits - debits - closing, per currency; currencies are never "
                    "merged; any unknown amount makes the currency not checkable"}


def running_balance(records: list[dict]) -> dict:
    """Consecutive transaction rows with known balances: previous balance + amount = balance."""
    mismatches, checked = [], 0
    last: dict[str, tuple[int, str]] = {}
    for r in records:
        ccy = r["currency"]
        if ccy["status"] != nz.KNOWN:
            continue
        code = ccy["value"]
        bal = r["balance"]
        if r["kind"] == "opening_balance":
            last[code] = (int(bal["minor_units"]), r["evidence_id"]) \
                if bal["status"] == nz.KNOWN else None
            continue
        if r["kind"] != "transaction":
            continue
        if bal["status"] != nz.KNOWN:
            last.pop(code, None)  # unknown breaks the chain; never bridged by assumption
            continue
        if last.get(code) is not None and r["amount"]["status"] == nz.KNOWN:
            checked += 1
            expected = last[code][0] + int(r["amount"]["minor_units"])
            if expected != int(bal["minor_units"]):
                mismatches.append({"evidence_ids": [last[code][1], r["evidence_id"]],
                                   "currency": code, "expected_minor": str(expected),
                                   "stated_minor": bal["minor_units"]})
        last[code] = (int(bal["minor_units"]), r["evidence_id"])
    return {"checked_transitions": checked, "mismatches": mismatches}


def table_coverage(units: list[dict], records: list[dict], unparsed_total: int) -> dict:
    statuses = defaultdict(int)
    for u in units:
        statuses[u["status"]] += 1
    return {"unit": "sheet_or_file", "units_total": len(units), "unit_status_counts":
            dict(sorted(statuses.items())), "records_typed": len(records),
            "rows_unparsed": unparsed_total,
            "note": "coverage counts what was read; it is not a calibrated confidence"}


def compute(records: list[dict]) -> dict:
    return {"missingness": missingness(records), "duplicates": duplicates(records),
            "reconciliation": reconciliation(records),
            "running_balance": running_balance(records)}
