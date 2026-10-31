"""Manual comparator runner for protocol-v1 development cases (G3B). Never run by the gates.

    uv run --locked python scripts/agent_eval.py --database-url URL --comparators C0,C2-det

`--database-url` is an operator (owner) URL of a disposable, migrated database: sessions are
issued with it, and investigations run through the service exactly as the API runs them.
Each case is ingested into a fresh session from its `runtime` section only; evaluator data
is used only to score the result afterwards (case `faults` are test-harness instructions
and are not applied here). Live comparators (C1, C2) call the owner's
local Claude subscription and are refused unless `--allow-live` is given explicitly; this
script never falls back to a paid key. It prints protocol-v1 attempt accounting
(attempts, refused, dispositions, inconclusive by code, pending) as JSON. Development
results only: never a final held-out evaluation.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "support"))

LIVE = {"C1", "C2"}


def comparator(name: str):
    from sentinel import investigators
    from sentinel.agents import coordinator
    if name == "C0":
        return investigators.DeterministicInvestigator()
    if name == "C1":
        return investigators.ClaudeCliInvestigator()
    if name == "C2-det":
        return coordinator.deterministic_workflow()
    if name == "C2":
        return coordinator.claude_cli_workflow()
    raise SystemExit(f"unknown comparator {name}")


def run(database_url: str, names: list[str], case_ids: list[str]) -> dict:
    import agent_cases as ac
    from sentinel.service import Sentinel, ServiceError, utc_now

    report = {}
    for name in names:
        tally, latencies = Counter(), []
        for case_id in case_ids:
            svc = Sentinel(database_url, comparator(name), utc_now)
            ctx = svc.authenticate(svc.create_session(ac.ANALYST)[0])
            case = ac.seed(svc, ctx, case_id, utc_now)["case"]
            tally["attempts"] += 1
            started = time.monotonic()
            try:
                detail = svc.investigate(ctx, case["id"], case["revision"])
                state = detail["case"]["state"]
                tally["dispositions" if state == "awaiting_approval" else "inconclusive"] += 1
            except ServiceError as error:
                key = {"agent_capacity_exhausted": "refused",
                       "investigation_in_progress": "pending",
                       "investigation_outcome_unknown": "pending"}.get(error.code, error.code)
                tally[key] += 1
            latencies.append(round(time.monotonic() - started, 3))
        report[name] = {"counts": dict(tally), "request_latency_s": latencies}
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--comparators", default="C0,C2-det")
    parser.add_argument("--cases", default="dev")
    parser.add_argument("--allow-live", action="store_true")
    args = parser.parse_args()
    names = [n.strip() for n in args.comparators.split(",") if n.strip()]
    if LIVE & set(names) and not args.allow_live:
        print("refused: C1/C2 use the local Claude subscription; pass --allow-live explicitly")
        return 2
    import agent_cases as ac
    case_ids = sorted(ac.CASES) if args.cases == "dev" else args.cases.split(",")
    print(json.dumps(run(args.database_url, names, case_ids), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
