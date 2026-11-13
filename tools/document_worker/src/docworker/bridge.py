"""Application bridge (DOC01 Part B): one bounded request per process over stdin/stdout.

The Sentinel API never imports this package. An operator registers this worker's own
environment; the API launches `<worker python> -I -m docworker.bridge --store DIR` with the
session owner key in SENTINEL_DOC_SESSION (never argv) and one JSON header line on stdin,
followed for `ingest` by exactly `size` raw bytes. It answers with one JSON object on stdout.

The bridge adds no parsing of its own: `analyze` runs the accepted Part A supervisor and its
bounded child, persists the full validated result beside the handle (same session owner) and
returns a *compact* view. In that view records are paged, page text and narrative text are
omitted (counts kept), and long evidence lists are capped with their totals. Codes are fixed
tokens; document bytes are never echoed in an error.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import PROTOCOL
from .extract import sniff, source_identity
from .handles import HandleStore, StoreError
from .limits import Limits, Options
from .supervisor import Supervisor

BRIDGE_PROTOCOL = "sentinel.doc01.bridge/0.1"
SESSION_ENV = "SENTINEL_DOC_SESSION"
MAX_HEADER_BYTES = 64 * 1024
MAX_PAGE_RECORDS = 500
MAX_PAGE_BYTES = 2 * 1024 * 1024
MAX_EVIDENCE_IDS = 50
MAX_UNPARSED_SHOWN = 100
MAX_GROUPS_SHOWN = 100
OPS = ("status", "ingest", "analyze", "records", "delete", "recover")
EXPECTED_CONTENT = {"pdf": "pdf", "xlsx": "zip", "csv": "text"}


class Refused(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _cap_ids(item: dict, key: str = "evidence_ids") -> dict:
    ids = item.get(key) or []
    out = dict(item)
    out[key] = ids[:MAX_EVIDENCE_IDS]
    out[f"{key}_total"] = len(ids)
    return out


def page(records: list[dict], offset: int, limit: int) -> dict:
    """Records [offset, offset+limit) stopping early at MAX_PAGE_BYTES of JSON."""
    limit = max(1, min(int(limit), MAX_PAGE_RECORDS))
    offset = max(0, int(offset))
    chosen, size = [], 0
    for rec in records[offset:offset + limit]:
        # +2 per record covers the list's brackets and ", " separators, so the serialised
        # page as a whole stays within the bound.
        encoded = len(json.dumps(rec, ensure_ascii=False).encode("utf-8")) + 2
        if chosen and size + encoded > MAX_PAGE_BYTES:
            break
        chosen.append(rec)
        size += encoded
    end = offset + len(chosen)
    return {"offset": offset, "limit": limit, "total": len(records), "records": chosen,
            "next_offset": end if end < len(records) else None}


def compact(doc: dict, page_limit: int) -> dict:
    out = {k: v for k, v in doc.items() if k != "records"}
    out["records_page"] = page(doc.get("records") or [], 0, page_limit)
    out["units"] = [{k: v for k, v in u.items() if k != "text"} for u in doc.get("units") or []]
    narrative = doc.get("narrative")
    out["narrative"] = None if narrative is None else {
        "status": narrative.get("status"), "chars": narrative.get("chars", 0),
        "truncated": bool(narrative.get("truncated"))}
    unparsed = doc.get("unparsed") or []
    out["unparsed"] = unparsed[:MAX_UNPARSED_SHOWN]
    out["findings"] = [_cap_ids(f) for f in doc.get("findings") or []]
    measures = doc.get("measures")
    if isinstance(measures, dict):
        measures = dict(measures)
        dup = measures.get("duplicates")
        if isinstance(dup, dict):
            groups = dup.get("groups") or []
            measures["duplicates"] = dict(dup, groups=[_cap_ids(g) for g in
                                                       groups[:MAX_GROUPS_SHOWN]],
                                          groups_total=len(groups))
        rb = measures.get("running_balance")
        if isinstance(rb, dict):
            mismatches = rb.get("mismatches") or []
            measures["running_balance"] = dict(rb, mismatches=mismatches[:MAX_GROUPS_SHOWN],
                                               mismatches_total=len(mismatches))
        out["measures"] = measures
    return out


def _read_header(stream) -> dict:
    line = stream.readline(MAX_HEADER_BYTES + 1)
    if len(line) > MAX_HEADER_BYTES or not line.endswith(b"\n"):
        raise Refused("bad_header")
    try:
        header = json.loads(line.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise Refused("bad_header") from None
    if not isinstance(header, dict) or header.get("protocol") != BRIDGE_PROTOCOL \
            or header.get("op") not in OPS:
        raise Refused("bad_header")
    return header


def _int(header: dict, key: str, low: int, high: int) -> int:
    value = header.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise Refused("bad_header")
    return value


def handle(header: dict, stream, store: HandleStore, session: str | None) -> dict:
    op = header["op"]
    if op == "status":
        store.verify()
        return dict(source_identity(), worker_protocol=PROTOCOL, store="ready",
                    max_input_bytes=store.limits.max_input_bytes)
    if op == "recover":
        report = Supervisor(store).recover()["records"]
        results: dict[str, int] = {}
        for entry in report:
            results[entry["result"]] = results.get(entry["result"], 0) + 1
        kept = sum(n for r, n in results.items() if r != "recovered"
                   and r != "orphan_temporary_removed")
        return {"recovery": {"results": dict(sorted(results.items())), "kept": kept},
                "purged": store.purge_expired()}
    if not session:
        raise Refused("invalid_session")
    if op == "ingest":
        fmt = header.get("format")
        if fmt not in EXPECTED_CONTENT:
            raise Refused("format_not_supported")
        size = _int(header, "size", 1, store.limits.max_input_bytes)
        data = stream.read(size + 1)
        if len(data) != size:
            raise Refused("framing_mismatch")
        detected = sniff(data)
        if detected != EXPECTED_CONTENT[fmt]:
            raise Refused("unsupported_container" if detected == "ole" else "format_mismatch")
        return {"handle": store.ingest_bytes(data, fmt, session)}
    handle_id = header.get("handle")
    if not isinstance(handle_id, str):
        raise Refused("not_found")
    if op == "analyze":
        try:
            options = Options.from_dict(header.get("options") or {})
        except (TypeError, ValueError):
            raise Refused("invalid_option") from None
        limit = _int(header, "page_limit", 1, MAX_PAGE_RECORDS)
        result = Supervisor(store).extract(handle_id, session, options, narrative=False)
        store.save_analysis(handle_id, session, result)
        return {"analysis": compact(result, limit)}
    if op == "records":
        offset = _int(header, "offset", 0, 10_000_000)
        limit = _int(header, "limit", 1, MAX_PAGE_RECORDS)
        doc = store.load_analysis(handle_id, session)
        if doc is None:
            raise Refused("analysis_not_found")
        return {"records_page": page(doc.get("records") or [], offset, limit),
                "source": doc.get("source"), "status": doc.get("status")}
    return {"deleted": store.delete(handle_id, session)["deleted"]}  # op == "delete"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="docworker.bridge")
    parser.add_argument("--store", required=True)
    args = parser.parse_args(argv)
    store = HandleStore(Path(args.store), Limits())
    stdin = sys.stdin.buffer
    try:
        header = _read_header(stdin)
        body = handle(header, stdin, store, os.environ.get(SESSION_ENV) or None)
        response = {"protocol": BRIDGE_PROTOCOL, "ok": True, **body}
    except Refused as exc:
        response = {"protocol": BRIDGE_PROTOCOL, "ok": False, "code": exc.code}
    except StoreError as exc:
        response = {"protocol": BRIDGE_PROTOCOL, "ok": False, "code": exc.code}
    sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
