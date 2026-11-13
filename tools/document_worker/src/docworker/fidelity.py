"""Compare an extraction result with a ground-truth fixture label.

Reports two things separately: record-field fidelity (exact typed date/amount/currency values
and statuses against the label) and behavioural checks (status, findings, reconciliation,
pages, guard). Nothing here is a calibrated confidence.
"""

from __future__ import annotations


def _find_record(result: dict, label: dict) -> dict | None:
    for rec in result.get("records") or []:
        loc = rec["locator"]
        if rec["kind"] == "transaction" and loc.get("row") == label["row"] \
                and loc.get("sheet") == label.get("sheet"):
            return rec
    return None


def compare(result: dict, run: dict) -> dict:
    field_checks: list[tuple[str, bool]] = []
    checks: list[tuple[str, bool]] = []

    def check(name: str, ok: bool, bucket=checks) -> None:
        bucket.append((name, bool(ok)))

    if "status" in run:
        check(f"status={run['status']} (got {result.get('status')})",
              result.get("status") == run["status"])
    if "status_in" in run:
        check(f"status in {run['status_in']} (got {result.get('status')})",
              result.get("status") in run["status_in"])
    codes = [e.get("code") for e in result.get("errors") or []]
    if "error" in run:
        check(f"error={run['error']} (got {codes})", run["error"] in codes)
    if "records" in run:
        txns = [r for r in result.get("records") or [] if r["kind"] == "transaction"]
        check(f"transaction count={len(run['records'])} (got {len(txns)})",
              len(txns) == len(run["records"]))
        for lab in run["records"]:
            where = f"{lab.get('sheet', '')}!row{lab['row']}"
            rec = _find_record(result, lab)
            check(f"{where} present", rec is not None, field_checks)
            if rec is None:
                continue
            check(f"{where} amount_status", rec["amount"]["status"] == lab["amount_status"],
                  field_checks)
            check(f"{where} amount_minor", rec["amount"]["minor_units"] == lab["amount_minor"],
                  field_checks)
            check(f"{where} currency", rec["currency"]["value"] == lab["currency"], field_checks)
            check(f"{where} date", rec["date"]["value"] == lab["date"], field_checks)
            if "date_status" in lab:
                check(f"{where} date_status", rec["date"]["status"] == lab["date_status"],
                      field_checks)
    recon = (result.get("measures") or {}).get("reconciliation") or {}
    by_ccy = {c["currency"]: c for c in recon.get("currencies", [])}
    for ccy, expected in (run.get("reconciliation") or {}).items():
        got = by_ccy.get(ccy)
        check(f"reconciliation {ccy} present", got is not None)
        if got is None:
            continue
        for key, value in expected.items():
            actual = got.get(key)
            if key in ("opening", "closing"):
                actual = (actual or {}).get("minor_units")
            check(f"reconciliation {ccy}.{key}={value} (got {actual})", actual == value)
    if "reconciliation_status" in run:
        check("reconciliation status", recon.get("status") == run["reconciliation_status"])
    if "reconciliation_unknown_currency_records" in run:
        check("unknown-currency records", recon.get("unknown_currency_records")
              == run["reconciliation_unknown_currency_records"])
    kinds = {f["kind"] for f in result.get("findings") or []}
    for kind in run.get("findings", []):
        check(f"finding {kind}", kind in kinds)
    measures = result.get("measures") or {}
    if "duplicates" in run:
        groups = (measures.get("duplicates") or {}).get("groups", [])
        check(f"duplicate groups={run['duplicates']} (got {len(groups)})",
              len(groups) == run["duplicates"])
    if "running_balance_mismatches" in run:
        mism = (measures.get("running_balance") or {}).get("mismatches", [])
        check("running balance mismatches", len(mism) == run["running_balance_mismatches"])
    for fname, expected in (run.get("missingness") or {}).items():
        got = ((measures.get("missingness") or {}).get("fields") or {}).get(fname, {})
        for key, value in expected.items():
            check(f"missingness {fname}.{key}={value} (got {got.get(key)})",
                  got.get(key) == value)
    pages = {str(u["locator"].get("page")): u for u in result.get("units") or []
             if "page" in u.get("locator", {})}
    for page, status in (run.get("pages") or {}).items():
        check(f"page {page} {status}", pages.get(page, {}).get("status") == status)
    for page, needles in (run.get("page_text_contains") or {}).items():
        text = pages.get(page, {}).get("text") or ""
        for needle in needles:
            check(f"page {page} contains {needle!r}", needle in text, field_checks)
    reasons = {u["reason"] for u in result.get("unparsed") or []}
    for reason in run.get("unparsed_reasons", []):
        check(f"unparsed {reason}", reason in reasons)
    sheets = {u["locator"].get("sheet"): u["status"] for u in result.get("units") or []
              if "sheet" in u.get("locator", {})}
    for sheet, status in (run.get("units") or {}).items():
        check(f"sheet {sheet} {status}", sheets.get(sheet) == status)
    if "guard_denied_events" in run:
        check("guard denied events", (result.get("guard") or {}).get("denied_events")
              == run["guard_denied_events"])
    for key, value in (run.get("decimal_style") or {}).items():
        got = ((result.get("typed") or {}).get("decimal_style") or {}).get(key)
        check(f"decimal_style.{key}={value} (got {got})", got == value)
    return {
        "field_fidelity": {"passed": sum(ok for _n, ok in field_checks),
                           "total": len(field_checks)},
        "behaviour": {"passed": sum(ok for _n, ok in checks), "total": len(checks)},
        "failures": [n for n, ok in field_checks + checks if not ok],
    }
