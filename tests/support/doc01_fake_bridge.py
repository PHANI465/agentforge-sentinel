"""A stand-in for the registered document-worker bridge (sentinel.doc01.bridge/0.1).

Launched exactly like the real bridge: a fresh `-I` process per request, with
`--store DIR`, one JSON header line on stdin and one JSON answer on stdout. It replays
answers recorded from the real worker (tests/fixtures/doc01/bridge_recorded.json), so the app
gate and the contract exporter need no worker environment.

Behaviour is set by DIR/fake.json, written by the test:
  {"recorded": path, "now": epoch seconds, "modes": {op: mode}, "recover_kept": int}
Modes: hang, crash, garbage, two_lines, flood, stop_unconfirmed, invalid_shape, wrong_protocol.
Per-call evidence (op, environment keys, owner presence) is appended to DIR/calls.jsonl.
Standard library only; it never imports the application or the worker.
"""
import hashlib
import json
import os
import sys
import time
from pathlib import Path

PROTOCOL = "sentinel.doc01.bridge/0.1"
TTL = 3600


def main() -> int:
    store = Path(sys.argv[sys.argv.index("--store") + 1])
    config = json.loads((store / "fake.json").read_text(encoding="utf-8"))
    recorded = json.loads(Path(config["recorded"]).read_text(encoding="utf-8"))
    line = sys.stdin.buffer.readline(65537)
    header = json.loads(line.decode("utf-8"))
    op = header.get("op")
    owner = os.environ.get("SENTINEL_DOC_SESSION")
    with open(store / "calls.jsonl", "a", encoding="utf-8") as log:
        log.write(json.dumps({"op": op, "pid": os.getpid(), "ppid": os.getppid(),
                              "env": sorted(os.environ),
                              "owner": owner is not None,
                              "cwd_is_store": Path.cwd().resolve() == store.resolve()}) + "\n")
    mode = (config.get("modes") or {}).get(op)
    if mode == "hang":
        time.sleep(600)
    if mode == "crash":
        sys.stderr.write("Traceback: simulated crash with C:\\secret\\path\n")
        return 3
    if mode == "garbage":
        sys.stdout.write("not json at all\n")
        return 0
    if mode == "two_lines":
        sys.stdout.write(json.dumps({"protocol": PROTOCOL, "ok": True}) + "\n{}\n")
        return 0
    if mode == "flood":
        sys.stdout.write("x" * (9 * 1024 * 1024))
        return 0
    if mode == "wrong_protocol":
        sys.stdout.write(json.dumps({"protocol": "other/1", "ok": True}) + "\n")
        return 0
    # Identity of "this worker" (R63): the recorded worker unless the test simulates a
    # changed worker on disk. Every answer carries it; a mismatched expectation is refused
    # before any operation runs, as the real bridge does.
    identity = {"worker_protocol": recorded["status"]["worker_protocol"],
                "worker_source_sha256": recorded["status"]["worker_source_sha256"]}
    identity.update({k: v for k, v in (config.get("status_override") or {}).items()
                     if k in identity})
    expected = header.get("expect_source_sha256")
    if expected is not None and expected != identity["worker_source_sha256"]:
        answer = {"ok": False, "code": "identity_mismatch"}
    else:
        answer = handle(op, header, store, config, recorded, owner, mode)
    if mode == "omit_identity":
        identity = {}
    sys.stdout.write(json.dumps({"protocol": PROTOCOL, **answer, **identity},
                                ensure_ascii=False) + "\n")
    return 0


def _state(store: Path) -> dict:
    path = store / "state.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {
        "next": 1, "handles": {}}


def _save(store: Path, state: dict) -> None:
    tmp = store / "state.json.tmp"
    tmp.write_text(json.dumps(state), encoding="utf-8")
    os.replace(tmp, store / "state.json")


def _by_sha(recorded: dict) -> dict:
    return {e["analyze"]["analysis"]["source"]["sha256"]: name
            for name, e in recorded["fixtures"].items()}


def handle(op, header, store, config, recorded, owner, mode) -> dict:
    now = config.get("now", time.time())
    if op == "status":
        status = dict(recorded["status"])
        status.update(config.get("status_override") or {})
        return {k: v for k, v in status.items() if k != "protocol"}
    if op == "recover":
        kept = int(config.get("recover_kept", 0))
        return {"ok": True, "recovery": {"results": {"recovered": 0} if not kept else
                                         {"group_members_alive_kept": kept}, "kept": kept},
                "purged": {"removed": 0, "kept": 0}}
    if not owner:
        return {"ok": False, "code": "invalid_session"}
    state = _state(store)
    owner_hash = hashlib.sha256(owner.encode()).hexdigest()
    if op == "ingest":
        size = header.get("size")
        data = sys.stdin.buffer.read(size + 1)
        if len(data) != size:
            return {"ok": False, "code": "framing_mismatch"}
        sha = hashlib.sha256(data).hexdigest()
        for name, refusal in recorded.get("ingest_refusals", {}).items():
            fixture = Path(config["fixtures"]) / name
            if fixture.exists() and hashlib.sha256(fixture.read_bytes()).hexdigest() == sha:
                return {k: v for k, v in refusal.items() if k != "protocol"}
        handle_id = "h_" + str(state["next"]).rjust(22, "0")
        state["next"] += 1
        state["handles"][handle_id] = {"owner": owner_hash, "sha": sha, "size": size,
                                       "format": header.get("format"),
                                       "expires": now + TTL, "analyzed": False}
        _save(store, state)
        return {"ok": True, "handle": {"handle_id": handle_id, "format": header.get("format"),
                                       "sha256": sha, "size": size, "expires_at": now + TTL}}
    entry = state["handles"].get(header.get("handle"))
    if entry is None or entry["owner"] != owner_hash or now >= entry["expires"]:
        return {"ok": False, "code": "not_found"}
    fixture = _by_sha(recorded).get(entry["sha"], "csv_statement_usd.csv")
    if op == "delete":
        del state["handles"][header["handle"]]
        _save(store, state)
        return {"ok": True, "deleted": True}
    if op == "analyze":
        options = header.get("options") or {}
        if options.get("decimal_style", "unspecified") not in ("unspecified", "dot", "comma") \
                or options.get("date_order", "iso_only") not in ("iso_only", "dmy", "mdy"):
            return {"ok": False, "code": "invalid_option"}
        analysis = json.loads(json.dumps(recorded["fixtures"][fixture]["analyze"]["analysis"]))
        if fixture not in _by_sha(recorded).values() or entry["sha"] not in _by_sha(recorded):
            analysis["source"] = {"sha256": entry["sha"], "size_bytes": entry["size"]}
        if mode == "stop_unconfirmed":
            analysis["status"] = "error"
            analysis["supervisor"]["stop"]["confirmed"] = False
            analysis["errors"] = [{"code": "stop_unconfirmed", "detail": "recovery record "
                                   "retained; run `recover` to re-verify"}]
        if mode == "invalid_shape":
            analysis["records_page"]["records"][0]["amount"]["minor_units"] = "12.5"
        if mode == "drop_totals":  # R61: counts missing from an otherwise valid answer
            del analysis["records_page"]["total"]
            del analysis["unparsed_total"]
        if mode == "zero_total":
            analysis["records_page"]["total"] = 0
        if mode == "parser_digest_changed":  # R63: the run reports another worker source
            analysis["parser"]["worker_source_sha256"] = "1" * 64
        entry["analyzed"] = True
        _save(store, state)
        return {"ok": True, "analysis": analysis}
    if op == "records":
        if not entry["analyzed"]:
            return {"ok": False, "code": "analysis_not_found"}
        rec = recorded["fixtures"][fixture]
        offset, limit = header.get("offset"), header.get("limit")
        if "records" in rec and offset == rec["records"]["records_page"]["offset"]:
            page = dict(rec["records"]["records_page"], limit=limit)
        else:
            first = rec["analyze"]["analysis"]["records_page"]
            records = first["records"] if offset == 0 else []
            page = {"offset": offset, "limit": limit, "total": first["total"],
                    "records": records[:limit], "next_offset": None}
        if mode == "bad_page":  # R61: more records than the stated total
            page = dict(page, total=0)
        return {"ok": True, "records_page": page, "status": rec["analyze"]["analysis"]["status"],
                "source": {"sha256": entry["sha"], "size_bytes": entry["size"]}}
    return {"ok": False, "code": "bad_header"}


if __name__ == "__main__":
    sys.exit(main())
