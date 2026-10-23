"""Export deterministic draft JSON Schema files, or compare them with --check."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    from sentinel.contracts.v1 import EXPORT_MODELS

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    destination = ROOT / "contracts" / "v1"
    expected = {model.__name__ + ".schema.json":
                json.dumps(model.model_json_schema(mode="serialization"), indent=2,
                           sort_keys=True) + "\n" for model in EXPORT_MODELS}
    stale = []
    for name, content in expected.items():
        path = destination / name
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                stale.append(name)
        else:
            destination.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    if destination.exists():
        extras = {p.name for p in destination.glob("*.schema.json")} - expected.keys()
        stale.extend(sorted(extras))
    if stale:
        print("Contract exports differ: " + ", ".join(stale))
        return 1
    print(f"{'Verified' if args.check else 'Exported'} {len(expected)} draft v1 schemas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
