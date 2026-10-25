"""C04 command line (needs: uv sync --locked --extra dev --extra ml).

    uv run --locked python -m ml select              # train + validation only; freezes selection
    uv run --locked python -m ml test                # the single frozen test evaluation
    uv run --locked python -m ml test --reproduce    # recompute and compare; writes nothing
"""
from __future__ import annotations

import argparse
import json
import sys

from ml import run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ml", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("select")
    test = sub.add_parser("test")
    test.add_argument("--reproduce", action="store_true")
    args = parser.parse_args(argv)
    paths = run.Paths.default()
    try:
        if args.command == "select":
            selection = run.select(paths)
            print(json.dumps({"selected": selection["selected"],
                              "frozen_threshold": selection["frozen_threshold"],
                              "splits": selection["splits"]}, indent=2))
        else:
            result = run.test(paths, reproduce=args.reproduce)
            if args.reproduce:
                print(json.dumps(result))
                return 0 if result["reproduced"] else 1
            print(json.dumps({"selected": result["selected"],
                              "selected_policy": result["selected_policy"]}, indent=2))
        return 0
    except run.StageError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
