"""Supervisor-side validation of an untrusted child response (protocol v0.1, review R59).

The child is treated as untrusted output: a document is returned only when its exit code,
envelope, required result fields and status relationships agree with the frozen protocol.
Rejection reasons are fixed tokens naming our own fields; they never echo child text, so
document bytes and driver errors cannot leak through them.
"""

from __future__ import annotations

import re

from . import PROTOCOL
from .normalize import (AMBIGUOUS, FORMULA_NO_VALUE, INVALID, KNOWN, MISSING, PRECISION,
                        UNKNOWN_CURRENCY)

STATUSES = ("complete", "partial", "unsupported", "error")
PROTOCOL_ERROR_CODES = {"bad_header", "bad_options", "input_too_large", "framing_mismatch",
                        "integrity_mismatch"}
UNIT_STATUSES = {"parsed", "partial", "unsupported", "failed", "empty"}
VALUE_STATUSES = {KNOWN, MISSING, AMBIGUOUS, INVALID, UNKNOWN_CURRENCY, PRECISION,
                  FORMULA_NO_VALUE}
RECORD_KINDS = {"transaction", "opening_balance", "closing_balance"}
_CODE = re.compile(r"^[a-z0-9_:.\-]{1,80}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_INT = re.compile(r"^-?[0-9]+$")
MAX_DETAIL = 200


class Invalid(Exception):
    """Carries a fixed reason token only."""


def _need(ok: bool, reason: str) -> None:
    if not ok:
        raise Invalid(reason)


def _errors(doc: dict) -> list[dict]:
    errors = doc.get("errors", [])
    _need(isinstance(errors, list), "errors")
    clean = []
    for err in errors:
        _need(isinstance(err, dict) and isinstance(err.get("code"), str)
              and bool(_CODE.match(err["code"])), "errors.code")
        detail = err.get("detail", "")
        _need(isinstance(detail, str) and len(detail) <= MAX_DETAIL, "errors.detail")
        clean.append({"code": err["code"], "detail": detail})
    return clean


def _value(part, reason: str, numeric: bool) -> None:
    _need(isinstance(part, dict) and part.get("status") in VALUE_STATUSES, reason)
    key = "minor_units" if numeric else "value"
    value = part.get(key)
    _need((part["status"] == KNOWN) == (value is not None), reason + ".known")
    if numeric and value is not None:
        _need(isinstance(value, str) and bool(_INT.match(value)), reason + ".minor_units")
    if not numeric and value is not None:
        _need(isinstance(value, str), reason + ".value")


def _record(rec, sha_prefix: str) -> None:
    _need(isinstance(rec, dict) and rec.get("kind") in RECORD_KINDS, "records.kind")
    _need(isinstance(rec.get("evidence_id"), str)
          and rec["evidence_id"].startswith(sha_prefix), "records.evidence_id")
    _need(isinstance(rec.get("locator"), dict), "records.locator")
    if rec["kind"] == "transaction":
        _value(rec.get("amount"), "records.amount", numeric=True)
    else:
        _need(rec.get("amount") is None, "records.amount")
    _value(rec.get("balance"), "records.balance", numeric=True)
    _value(rec.get("date"), "records.date", numeric=False)
    currency = rec.get("currency")
    _need(isinstance(currency, dict) and currency.get("status") in VALUE_STATUSES,
          "records.currency")
    for name in ("description", "reference"):
        part = rec.get(name)
        _need(isinstance(part, dict) and part.get("status") in (KNOWN, MISSING),
              f"records.{name}")


def _result(doc: dict, status: str, expected: dict) -> None:
    _need(doc.get("format") == expected["format"], "format")
    source = doc.get("source")
    _need(isinstance(source, dict) and source.get("sha256") == expected["sha256"]
          and source.get("size_bytes") == expected["size"], "source")
    parser = doc.get("parser")
    _need(isinstance(parser, dict) and isinstance(parser.get("worker_version"), str)
          and bool(_HEX64.match(str(parser.get("worker_source_sha256", "")))), "parser")
    for key in ("typed", "measures", "coverage"):
        _need(isinstance(doc.get(key), dict), key)
    guard = doc.get("guard")
    _need(isinstance(guard, dict) and guard.get("installed") is True, "guard")
    units = doc.get("units")
    _need(isinstance(units, list) and bool(units), "units")
    for unit in units:
        _need(isinstance(unit, dict) and isinstance(unit.get("locator"), dict)
              and unit.get("status") in UNIT_STATUSES, "units.status")
    records = doc.get("records")
    _need(isinstance(records, list) and len(records) <= expected["max_records"], "records")
    if expected["format"] == "pdf":
        _need(not records, "records.pdf")
    for rec in records:
        _record(rec, expected["sha256"][:12] + ":")
    unparsed, total = doc.get("unparsed"), doc.get("unparsed_total")
    _need(isinstance(unparsed, list) and isinstance(total, int)
          and not isinstance(total, bool) and total >= len(unparsed), "unparsed")
    findings = doc.get("findings")
    _need(isinstance(findings, list), "findings")
    for finding in findings:
        _need(isinstance(finding, dict) and isinstance(finding.get("kind"), str)
              and finding.get("severity") in ("info", "warning")
              and isinstance(finding.get("evidence_ids"), list), "findings.item")
    narrative = doc.get("narrative")
    _need(narrative is None or (isinstance(narrative, dict) and narrative.get("status")
                                in ("ok", "truncated", "failed")), "narrative")
    unit_statuses = {u["status"] for u in units}
    _need(bool(unit_statuses & {"parsed", "partial"}), "status.no_parsed_unit")
    if status == "complete":
        _need(not doc["errors"], "status.complete_with_errors")
        _need(total == 0, "status.complete_with_unparsed")
        _need(unit_statuses <= {"parsed", "empty"}, "status.complete_with_incomplete_unit")
        _need(narrative is None or narrative["status"] == "ok",
              "status.complete_with_incomplete_narrative")


def validate(doc, request_id: str, exit_code: int | None, expected: dict) -> dict:
    """Return the accepted document or raise Invalid(reason).

    expected: {"format", "sha256", "size", "max_records"} from the supervisor's own handle.
    """
    _need(isinstance(doc, dict), "not_object")
    _need(doc.get("protocol") == PROTOCOL, "protocol")
    status = doc.get("status")
    _need(status in STATUSES, "status")
    errors = _errors(doc)
    if exit_code == 2:  # protocol-error document: only the envelope is returned
        _need(status == "error" and bool(errors)
              and all(e["code"] in PROTOCOL_ERROR_CODES for e in errors), "protocol_error")
        _need(doc.get("request_id") == request_id or (
            doc.get("request_id") is None and errors[0]["code"] == "bad_header"),
            "request_id")
        return {"protocol": PROTOCOL, "request_id": request_id, "status": "error",
                "errors": errors}
    _need(exit_code == 0, "nonzero_exit")
    _need(doc.get("request_id") == request_id, "request_id")
    doc = dict(doc, errors=errors)
    if status in ("unsupported", "error"):
        _need(bool(errors), "failure_without_errors")
        _need(not doc.get("records"), "failure_with_records")
        return doc
    _result(doc, status, expected)
    return doc
