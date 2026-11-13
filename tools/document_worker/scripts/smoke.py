"""Bounded local smoke and measurement over the labelled fixtures (serial, one child at a time).

    uv run --locked python scripts/smoke.py OUT_JSON

For every labelled run it ingests the owned fixture, extracts through the real contained child,
compares with the ground-truth label and records elapsed time, peak child memory, input bytes,
narrative bytes, typed-output bytes, cleanup and guard state. It then checks that the store
holds no run directory or recovery record.

Token savings are NOT measured: no tokenizer/model was specified for Part A, so only byte and
character sizes are reported. Timings are single-run observations on this host, not capacity.
"""

from __future__ import annotations

import json
import platform
import secrets
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from docworker import fidelity  # noqa: E402
from docworker.extract import library_versions, source_identity  # noqa: E402
from docworker.handles import HandleStore  # noqa: E402
from docworker.limits import Limits, Options  # noqa: E402
from docworker.supervisor import Supervisor  # noqa: E402


def _cap_probes(store: HandleStore, sup: Supervisor, session: str) -> list[dict]:
    """Single observations exactly at the row and page caps (synthetic, generated here)."""
    sys.path.insert(0, str(ROOT / "fixtures"))
    import generate
    limits = Limits()
    rows = [["Date", "Description", "Amount", "Currency"]] + [
        [f"2026-01-{1 + i % 28:02d}", f"Synthetic row {i}", f"-{i % 997}.{i % 100:02d}", "USD"]
        for i in range(limits.max_table_rows)]
    pages = [{"lines": [f"Synthetic page {i}"] + [f"Line {j} of page {i}" for j in range(40)]}
             for i in range(limits.max_pdf_pages)]
    # At the row cap the Markdown narrative exceeds max_narrative_chars, so it is truncated
    # and the result is honestly partial even though every typed row was read.
    cases = [("csv_at_row_cap", generate.csv_bytes(rows), "csv", "partial"),
             ("pdf_at_page_cap", generate.pdf_bytes(pages), "pdf", "complete")]
    out = []
    for name, data, fmt, expected in cases:
        handle = store.ingest_bytes(data, fmt, session)
        result = sup.extract(handle["handle_id"], session)
        s = result["supervisor"]
        out.append({"probe": name, "input_bytes": len(data), "status": result["status"],
                    "expected_status": expected,
                    "errors": [e["code"] for e in result.get("errors", [])],
                    "records": len(result.get("records") or []),
                    "narrative_status": (result.get("narrative") or {}).get("status"),
                    "unparsed_total": result.get("unparsed_total"),
                    "units": len(result.get("units") or []),
                    "elapsed_ms_child": s["elapsed_ms"], "peak_memory_bytes":
                    s["peak_memory_bytes"], "stdout_bytes": s["stdout_bytes"],
                    "stop_confirmed": s["stop"]["confirmed"]})
        store.delete(handle["handle_id"], session)
    return out


def main(out_path: str) -> int:
    fixtures = ROOT / "fixtures"
    labels = json.loads((fixtures / "labels.json").read_text(encoding="utf-8"))
    manifest = json.loads((fixtures / "MANIFEST.json").read_text(encoding="utf-8"))
    session = secrets.token_urlsafe(24)
    rows = []
    with tempfile.TemporaryDirectory(prefix="docworker-smoke-") as tmp:
        store = HandleStore(Path(tmp) / "store")
        store.init()
        sup = Supervisor(store)
        for name, label in sorted(labels.items()):
            for index, run in enumerate(label["runs"]):
                handle = store.ingest_file(str(fixtures / name), label["format"], session)
                t0 = time.perf_counter()
                result = sup.extract(handle["handle_id"], session,
                                     Options.from_dict(run["options"]))
                wall = (time.perf_counter() - t0) * 1000
                comp = fidelity.compare(result, run)
                narrative = result.get("narrative") or {}
                typed = {k: result.get(k) for k in ("records", "units", "measures", "findings",
                                                     "unparsed")}
                s = result["supervisor"]
                rows.append({
                    "fixture": name, "run": index, "options": run["options"],
                    "status": result["status"],
                    "errors": [e["code"] for e in result.get("errors", [])],
                    "label_failures": comp["failures"],
                    "field_fidelity": comp["field_fidelity"], "behaviour": comp["behaviour"],
                    "input_bytes": handle["size"],
                    "narrative_utf8_bytes": len((narrative.get("text") or "").encode("utf-8")),
                    "narrative_status": narrative.get("status"),
                    "typed_json_bytes": len(json.dumps(typed, separators=(",", ":"))
                                            .encode("utf-8")),
                    "elapsed_ms_child": s["elapsed_ms"], "elapsed_ms_wall": round(wall, 1),
                    "peak_memory_bytes": s["peak_memory_bytes"],
                    "stop_confirmed": s["stop"]["confirmed"],
                    "run_dir_removed": s["stop"].get("run_dir_removed"),
                    "guard_denied": (result.get("guard") or {}).get("denied_events"),
                })
                store.delete(handle["handle_id"], session)
        probes = _cap_probes(store, sup, session)
        leftovers = {d: sorted(p.name for p in (store.root / d).iterdir())
                     for d in ("handles", "runs", "recovery")}
    ok = all(not r["label_failures"] and r["stop_confirmed"] and r["run_dir_removed"]
             for r in rows) and not any(leftovers.values()) \
        and all(p["status"] == p["expected_status"] and p["stop_confirmed"] for p in probes)
    fid = [r["field_fidelity"] for r in rows]
    beh = [r["behaviour"] for r in rows]
    peaks = [r["peak_memory_bytes"] for r in rows if r["peak_memory_bytes"]]
    report = {
        "kind": "doc01-part-a-smoke", "ok": ok,
        "host": {"platform": platform.platform(), "python": platform.python_version(),
                 "machine": platform.machine()},
        "parser": dict(source_identity(), libraries=library_versions()),
        "limits": Limits().to_dict(), "fixtures_manifest": manifest,
        "summary": {
            "runs": len(rows),
            "field_fidelity": {"passed": sum(f["passed"] for f in fid),
                               "total": sum(f["total"] for f in fid)},
            "behaviour": {"passed": sum(b["passed"] for b in beh),
                          "total": sum(b["total"] for b in beh)},
            "status_counts": {s: sum(1 for r in rows if r["status"] == s)
                              for s in ("complete", "partial", "unsupported", "error")},
            "max_peak_memory_bytes": max(peaks) if peaks else None,
            "max_elapsed_ms_child": max(r["elapsed_ms_child"] for r in rows),
            "leftovers_after_cleanup": leftovers,
            "token_savings": "not measured: no tokenizer/model specified",
        },
        "cap_probes": probes,
        "runs": rows,
    }
    Path(out_path).write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps({"ok": ok, **report["summary"]}, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
