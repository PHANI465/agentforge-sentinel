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
            # Byte comparison: CRLF drift (e.g. a Windows text-mode write) is a difference.
            if not path.exists() or path.read_bytes() != content.encode("utf-8"):
                stale.append(name)
        else:
            destination.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content.encode("utf-8"))
    if destination.exists():
        extras = {p.name for p in destination.glob("*.schema.json")} - expected.keys()
        stale.extend(sorted(extras))
    agents = export_agents(args.check)
    stale.extend(agents["stale"])
    if stale:
        print("Contract exports differ: " + ", ".join(stale))
        return 1
    print(f"{'Verified' if args.check else 'Exported'} {len(expected)} draft v1 schemas.")
    print(f"{'Verified' if args.check else 'Exported'} {agents['count']} agents 1.0 schemas"
          f" ({agents['examples']} examples behave as labelled).")
    return 0


def export_agents(check: bool) -> dict:
    """Additive G3B namespace: contracts/agents/<Model>.schema.json. The examples under
    contracts/agents/examples/{valid,invalid} must validate or be rejected as labelled."""
    from pydantic import TypeAdapter, ValidationError

    from sentinel.contracts.agents import EXPORTS

    destination = ROOT / "contracts" / "agents"
    expected = {name + ".schema.json":
                json.dumps(TypeAdapter(model).json_schema(mode="serialization"), indent=2,
                           sort_keys=True) + "\n" for name, model in EXPORTS.items()}
    stale = []
    for name, content in expected.items():
        path = destination / name
        if check:
            if not path.exists() or path.read_bytes() != content.encode("utf-8"):
                stale.append(f"agents/{name}")
        else:
            destination.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content.encode("utf-8"))
    if destination.exists():
        extras = {p.name for p in destination.glob("*.schema.json")} - expected.keys()
        stale.extend(f"agents/{name}" for name in sorted(extras))
    examples = 0
    for label in ("valid", "invalid"):
        for path in sorted((destination / "examples" / label).glob("*.json")):
            model = EXPORTS.get(path.name.split(".", 1)[0])
            try:
                TypeAdapter(model).validate_json(path.read_bytes()) if model else None
                accepted = model is not None
            except ValidationError:
                accepted = False
            if model is None or accepted != (label == "valid"):
                stale.append(f"agents/examples/{label}/{path.name}")
            examples += 1
    return {"stale": stale, "count": len(expected), "examples": examples}


if __name__ == "__main__":
    raise SystemExit(main())
