"""DOC01 Part C browser fixtures: opt-in document sessions and casework counts.

    uv run --locked python tests/support/doc01_browser.py sessions --manifest P
    uv run --locked python tests/support/doc01_browser.py counts --manifest P

Both commands read the browser Stack's private manifest (ownership-checked by Stack.load)
and never write to it or to the Stack's directory. They add no HTTP route and change no
production code:

- `sessions` issues three sessions as the operator, exactly as `sentinel create-session`
  does: `doc_analyst` (the four default grants plus the opt-in `analyze_document`),
  `doc_other` (the same grants in a different tenant) and `doc_plain` (default grants only).
  The tokens go to stdout for the test process to keep in memory. Nothing else prints them.
- `counts` reads row counts of the casework tables as the operator (read-only), so the suite
  can prove the document routes create no transaction, case, approval or action.

A failure prints {"error": code} only, never a token, connection string or exception text.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import timedelta
from pathlib import Path

SUPPORT = Path(__file__).resolve().parent
ROOT = SUPPORT.parents[1]
for path in (str(SUPPORT), str(ROOT / "src")):
    if path not in sys.path:
        sys.path.insert(0, path)

from sentinel import db  # noqa: E402
from sentinel.investigators import DeterministicInvestigator  # noqa: E402
from sentinel.service import Sentinel  # noqa: E402

from browser_stack import Stack  # noqa: E402

DEFAULT_GRANTS = frozenset({"ingest_transaction", "read_case", "approve_action",
                            "execute_simulated_action"})
DOCUMENT_GRANTS = DEFAULT_GRANTS | {"analyze_document"}
CASEWORK_TABLES = ("transactions", "scoring_outcomes", "alerts", "cases", "evidence_items",
                   "agent_runs", "agent_workflows", "action_intents", "approvals",
                   "simulated_actions", "audit_events")


def _operator_url(manifest_path: str) -> str:
    stack = Stack.load(Path(manifest_path))  # refuses an unowned or redirected state dir
    url = stack.manifest.get("database_url")
    if not isinstance(url, str) or not url:
        raise LookupError("database_unrecorded")
    return url


def sessions(manifest_path: str) -> dict:
    service = Sentinel(_operator_url(manifest_path), DeterministicInvestigator())
    ttl = timedelta(hours=4)
    analyst = service.create_session(DOCUMENT_GRANTS, ttl=ttl)[0]
    other = service.create_session(DOCUMENT_GRANTS, ttl=ttl)[0]  # a different tenant
    plain = service.create_session(DEFAULT_GRANTS, ttl=ttl)[0]
    return {"doc_analyst": analyst, "doc_other": other, "doc_plain": plain}


def counts(manifest_path: str) -> dict:
    with db.connect(_operator_url(manifest_path)) as conn:
        return {table: conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]
                for table in CASEWORK_TABLES}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="doc01_browser")
    parser.add_argument("command", choices=("sessions", "counts"))
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args(argv)
    try:
        result = sessions(args.manifest) if args.command == "sessions" else counts(args.manifest)
    except Exception as error:  # noqa: BLE001 - reported as a fixed code only
        print(json.dumps({"error": type(error).__name__}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
