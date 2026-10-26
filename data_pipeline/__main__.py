"""Command line: generate, verify and featurize synthetic datasets.

    uv run --locked python -m data_pipeline generate --out data/generated/ref [--seed 7 ...]
    uv run --locked python -m data_pipeline verify data/generated/ref
    uv run --locked python -m data_pipeline features data/generated/ref
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import tracemalloc
from pathlib import Path

from data_pipeline import features, manifest
from data_pipeline.generator import GeneratorConfig, generate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="data_pipeline", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    gen = commands.add_parser("generate")
    gen.add_argument("--out", type=Path, required=True)
    defaults = GeneratorConfig()
    for name in ("seed", "accounts", "days", "max_rows"):
        gen.add_argument(f"--{name.replace('_', '-')}", type=int, default=getattr(defaults, name))
    for name in ("verify", "features"):
        commands.add_parser(name).add_argument("path", type=Path)
    commands.add_parser("refresh-fixtures", help="rewrite tracked manifest and tiny fixture")
    args = parser.parse_args(argv)

    if args.command == "refresh-fixtures":
        from data_pipeline import fixtures
        fixtures.refresh()
        print(f"refreshed {fixtures.REFERENCE_MANIFEST.name} and {fixtures.TINY_DIR}")
        return 0

    if args.command == "generate":
        config = GeneratorConfig(seed=args.seed, accounts=args.accounts, days=args.days,
                                 max_rows=args.max_rows)
        tracemalloc.start()
        started = time.perf_counter()
        dataset = generate(config)
        result = manifest.write(dataset, args.out)
        elapsed = time.perf_counter() - started
        peak = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
        stats = {"generate_seconds": round(elapsed, 3), "python_peak_mib": round(peak / 2**20, 1),
                 "note": "tracemalloc measures Python allocations, not process RSS"}
        (args.out / "run_stats.json").write_text(json.dumps(stats, indent=2) + "\n")
        print(f"wrote {result['rows']['transactions']} transactions to {args.out} "
              f"({stats['generate_seconds']} s, peak {stats['python_peak_mib']} MiB)")
        return 0
    if args.command == "verify":
        problems = manifest.verify(args.path)
        for problem in problems[:50]:
            print(problem)
        print("verified" if not problems else f"{len(problems)} problem(s)")
        return 0 if not problems else 1
    accounts, transactions, labels = manifest.read(args.path)
    started = time.perf_counter()
    rows = features.batch_features(transactions, accounts, labels)
    out = args.path / f"features.{features.FEATURE_VERSION}.jsonl"
    out.write_bytes(manifest.jsonl(rows))
    print(f"wrote {len(rows)} feature rows to {out} ({time.perf_counter() - started:.2f} s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
