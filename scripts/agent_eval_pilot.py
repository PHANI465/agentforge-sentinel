"""Development pilot supervisor (G3D-P4a): a seeded schedule, owned database lifecycle,
reservation accounting and post-run checks around scripts/agent_eval.py.

    uv run --locked python scripts/agent_eval_pilot.py plan --root DIR [--seed N]
    uv run --locked python scripts/agent_eval_pilot.py run --root DIR --pair P00-det
    uv run --locked python scripts/agent_eval_pilot.py run --root DIR --pair L01-C2-D03 --allow-live
    uv run --locked python scripts/agent_eval_pilot.py status --root DIR
    uv run --locked python scripts/agent_eval_pilot.py cleanup --root DIR [--drop]

`plan` creates a NEW pilot root (an existing non-empty directory is never adopted). The
schedule is the deterministic preflight P00-det (C0 and C2-det on D01-D04 and D11, one
fresh database) and, for later, one live pair per (comparator, case) in a seeded order.
`run` runs exactly one pair, the next planned one, on its own fresh database in a
database-only cluster owned through scripts/local_stack.py's Stack and its identity
checks. A live pair needs --allow-live, the completed preflight and the full reservation
(C1 1, C2 5, of 30); nothing chains a preflight into live calls and there is no fallback.
Connection strings go to the runner through its environment, never argv or the console.
Outcomes are kept as recorded: a setup failure, refusal, typed request failure or a wrong
hold stops the pass (incomplete; later pairs not attempted). The cluster is stopped after
each run and kept for private scoring until `cleanup --drop` drops only this pilot's
databases. Development tooling only: no final cases, no quality claim.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import secrets
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import local_stack  # noqa: E402
from agent_eval_support import artifact, catalog  # noqa: E402

CASES = ("D01", "D02", "D03", "D04", "D11")
ALLOWANCE = 30
RUNTIME_ROLE = "sentinel_eval_rt"
MARKER = ".sentinel-eval-pilot"
MANIFEST = "pilot.json"
RUNNER = ROOT / "scripts" / "agent_eval.py"


class PilotError(RuntimeError):
    """Refused or failed; state is kept. Messages never contain secrets."""


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---- the owned pilot root ------------------------------------------------------------------

def canonical(path: Path) -> str:
    return os.path.normcase(os.path.realpath(path))


def save(root: Path, manifest: dict) -> None:
    temp = root / (MANIFEST + ".tmp")
    temp.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, root / MANIFEST)
    try:
        (root / MANIFEST).chmod(0o600)
    except OSError:
        pass


def load(root: Path) -> dict:
    """The verified manifest; anything not provably this pilot's is refused."""
    root = Path(root)
    marker, path = root / MARKER, root / MANIFEST
    if os.path.islink(root) or not marker.is_file() or not path.is_file():
        raise PilotError(f"{root} is not an owned pilot root (refused)")
    try:
        owner = json.loads(marker.read_text(encoding="utf-8"))
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise PilotError("pilot state is unreadable (refused)") from None
    if not (manifest.get("version") == artifact.PILOT_VERSION
            and secrets.compare_digest(str(owner.get("owner")), str(manifest.get("owner")))
            and owner.get("root") == manifest.get("root") == canonical(root)):
        raise PilotError("pilot marker does not match its manifest (refused)")
    return manifest


def schedule(cases: list[str], seed: int) -> list[dict]:
    """P00-det, then one live pair per (comparator, case): case order shuffled with the
    seed, and a seeded coin flip per case for which live comparator runs first."""
    rng = random.Random(seed)
    order = list(cases)
    rng.shuffle(order)
    pairs = [{"pair_id": "P00-det", "comparators": ["C0", "C2-det"], "cases": list(cases),
              "live": False, "reservation": 0, "status": "planned"}]
    for case in order:
        first = rng.choice(["C1", "C2"])
        for name in (first, "C2" if first == "C1" else "C1"):
            pairs.append({"pair_id": f"L{len(pairs):02d}-{name}-{case}", "comparators": [name],
                          "cases": [case], "live": True,
                          "reservation": artifact.RESERVATIONS[name], "status": "planned"})
    return pairs


def plan(root: Path, seed: int) -> dict:
    root = Path(root)
    if root.exists() and (not root.is_dir() or any(root.iterdir())):
        raise PilotError(f"{root} exists and is not empty; a pilot root is never adopted")
    root.mkdir(parents=True, exist_ok=True)
    owner = secrets.token_hex(16)
    (root / MARKER).write_text(json.dumps({"owner": owner, "root": canonical(root)}),
                               encoding="utf-8")
    manifest = {"version": artifact.PILOT_VERSION, "owner": owner, "root": canonical(root),
                "created_at": now(), "seed": seed, "cases": list(CASES),
                "allowance": ALLOWANCE, "reserved": 0, "status": "planned", "stopped": None,
                "not_attempted": [], "db_port": None, "runtime_role": RUNTIME_ROLE,
                "databases": {}, "dropped": [], "pairs": schedule(list(CASES), seed),
                "kind": "development pilot (not a held-out evaluation)"}
    save(root, manifest)
    return manifest


# ---- the owned database-only cluster --------------------------------------------------------

def stack_of(root: Path, manifest: dict, create: bool = False):
    stack = local_stack.Stack(Path(root) / "stack")
    try:
        data = stack.load(create=create)
    except local_stack.StackError as error:
        raise PilotError(f"pilot cluster state refused: {error}") from None
    if data.get("api"):
        raise PilotError("the pilot cluster records an API process; refused")
    return stack, data


def start(root: Path, manifest: dict, create: bool = False):
    stack, data = stack_of(root, manifest, create=create)
    if manifest["db_port"] is None:
        from sentinel import devdb
        manifest["db_port"] = devdb.free_port()
        save(root, manifest)
    try:
        local_stack.start_database(stack, data, manifest["db_port"])
    except local_stack.StackError as error:
        raise PilotError(f"pilot database not started: {error}") from None
    return stack, data


def stop(stack, data) -> None:
    try:
        local_stack.stop_database(stack, data)
    except local_stack.StackError as error:
        raise PilotError(f"pilot database stop not confirmed ({error}); state kept") from None


def database_name(manifest: dict, pair_id: str) -> str:
    return f"p4a_{manifest['owner'][:8]}_{pair_id.lower().replace('-', '_')}"


def urls(stack, data, database: str) -> tuple[str, str]:
    from psycopg.conninfo import make_conninfo
    owner = local_stack.owner_url(stack, data, database)
    return owner, make_conninfo(owner, user=RUNTIME_ROLE)


def provision(stack, data, manifest: dict, root: Path, pair_id: str) -> str:
    """A fresh database for this pair, migrated, with the runtime role granted."""
    import psycopg
    from psycopg import sql

    from sentinel import db
    from sentinel.db import roles
    name = database_name(manifest, pair_id)
    with psycopg.connect(local_stack.owner_url(stack, data), autocommit=True) as conn:
        if conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone():
            raise PilotError(f"database {name} already exists; a fresh database is required")
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    manifest["databases"][pair_id] = name
    save(root, manifest)
    owner, _runtime = urls(stack, data, name)
    db.migrate(owner)
    roles.grant_runtime(owner, RUNTIME_ROLE)
    return name


# ---- running one pair -----------------------------------------------------------------------

def invoke_runner(argv: list[str], env: dict) -> tuple[int, str, str]:
    """The accepted runner as a subprocess (tests intercept this for live pairs)."""
    done = subprocess.run(argv, env=env, capture_output=True, text=True, encoding="utf-8",
                          timeout=3600, cwd=ROOT)
    return done.returncode, done.stdout, done.stderr


def assess(pair: dict, code: int, stdout: str) -> tuple[str, str | None, dict | None]:
    """(pair status, stop reason or None, artifact or None). Outcomes are never rewritten."""
    try:
        doc = artifact.validate_run(json.loads(stdout))
    except (ValueError, artifact.ArtifactError):
        return "failed", f"runner exit {code}: no valid run artifact (refused or failed)", None
    record = doc["record"]
    if code not in (0, 3) or record.get("authorities", {}).get("runtime_verified") is not True:
        return "failed", f"runner exit {code} or runtime authority not verified", doc
    if code == 3 or record.get("status") != "complete":
        return "incomplete", f"setup failure stopped the run ({record.get('stopped')})", doc
    typed = [row["attempt_id"] for result in doc["comparators"].values()
             for row in result["attempts"] if row["outcome"] in ("refused", "pending", "error")]
    if typed:
        return "complete", "typed request failure: " + ", ".join(typed), doc
    holds = [row["attempt_id"] for result in doc["comparators"].values()
             for row in result["attempts"]
             if row["outcome"] == "disposition" and catalog.wrong_hold(row["case"],
                                                                      row.get("disposition"))]
    if holds:  # completed, unacceptable dispositions: kept and scored 0/1, then review
        return "complete", "quality review: wrong hold scored unacceptable: " + \
            ", ".join(holds), doc
    if not pair["live"]:
        short = [name for name, result in doc["comparators"].items()
                 if result["counts"].get("dispositions", 0) != len(pair["cases"])]
        if short:
            return "complete", "preflight did not reach all dispositions: " + \
                ", ".join(short), doc
    return "complete", None, doc


def run_pair(root: Path, pair_id: str, allow_live: bool = False) -> dict:
    root = Path(root)
    manifest = load(root)
    if manifest["status"] in ("incomplete", "complete", "running"):
        raise PilotError(f"the pass is {manifest['status']}; no pair is started")
    planned = [p for p in manifest["pairs"] if p["status"] == "planned"]
    pair = next((p for p in manifest["pairs"] if p["pair_id"] == pair_id), None)
    if pair is None:
        raise PilotError(f"unknown pair {pair_id}")
    if not planned or planned[0]["pair_id"] != pair_id:
        raise PilotError(f"pairs run in the recorded order; next is "
                         f"{planned[0]['pair_id'] if planned else 'none'} (no rerun)")
    if pair["live"]:
        if not allow_live:
            raise PilotError("live pair refused: pass --allow-live explicitly (the owner's "
                             "go-ahead); the preflight never chains into live calls")
        need = pair["reservation"]
        if manifest["allowance"] - manifest["reserved"] < need:
            raise PilotError(f"live pair refused: {need} reservations needed, "
                             f"{manifest['allowance'] - manifest['reserved']} left")
        manifest["reserved"] += need  # reserved before anything starts; never returned
        pair["reserved"] = need
    pair["status"], pair["started_at"] = "running", now()
    manifest["status"] = "running"
    save(root, manifest)
    stack = data = None
    try:
        stack, data = start(root, manifest, create=True)
        name = provision(stack, data, manifest, root, pair_id)
        owner, runtime = urls(stack, data, name)
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("SENTINEL_EVAL_") and k != "SENTINEL_TEST_DATABASE_URL"}
        env.update(SENTINEL_EVAL_OPERATOR_URL=owner, SENTINEL_EVAL_RUNTIME_URL=runtime)
        argv = [sys.executable, str(RUNNER), "--comparators", ",".join(pair["comparators"]),
                "--cases", ",".join(pair["cases"])] + (["--allow-live"] if pair["live"] else [])
        code, stdout, stderr = invoke_runner(argv, env)
        runs = root / "runs"
        runs.mkdir(exist_ok=True)
        (runs / f"{pair_id}.json").write_text(stdout, encoding="utf-8")
        (runs / f"{pair_id}.stderr.txt").write_text(stderr, encoding="utf-8")
        status, reason, _doc = assess(pair, code, stdout)
        pair.update(status=status, exit_code=code, finished_at=now(),
                    run_file=f"runs/{pair_id}.json", stop_reason=reason)
        if reason is not None:
            stop_pass(manifest, pair_id, reason)
        elif all(p["status"] == "complete" for p in manifest["pairs"]):
            manifest["status"] = "complete"
        else:
            manifest["status"] = "planned"
    except Exception as error:
        detail = str(error) if isinstance(error, PilotError) else type(error).__name__
        pair.update(status="failed", finished_at=now(),
                    stop_reason=f"supervisor failure ({detail})")
        stop_pass(manifest, pair_id, pair["stop_reason"])
        raise PilotError(f"pair {pair_id} failed ({detail}); pass stopped, state kept")             from None
    finally:
        save(root, manifest)
        if stack is not None:
            stop(stack, data)
    return pair


def stop_pass(manifest: dict, pair_id: str, reason: str) -> None:
    manifest["status"] = "incomplete"
    manifest["stopped"] = {"pair": pair_id, "reason": reason, "at": now()}
    manifest["not_attempted"] = [p["pair_id"] for p in manifest["pairs"]
                                 if p["status"] == "planned"]


# ---- cleanup --------------------------------------------------------------------------------

def cleanup(root: Path, drop: bool) -> list[str]:
    """Stop the pilot cluster; with drop, first drop only this pilot's recorded databases."""
    import psycopg
    from psycopg import sql
    root = Path(root)
    manifest = load(root)
    if manifest["status"] == "running":
        raise PilotError("a pair is recorded as running; inspect before cleanup (refused)")
    if not (root / "stack").exists():
        return []
    stack, data = stack_of(root, manifest)
    if not drop:
        stop(stack, data)
        return []
    stack, data = start(root, manifest)
    dropped = []
    try:
        prefix = f"p4a_{manifest['owner'][:8]}_"
        with psycopg.connect(local_stack.owner_url(stack, data), autocommit=True) as conn:
            for pair_id, name in manifest["databases"].items():
                if name != database_name(manifest, pair_id) or not name.startswith(prefix):
                    raise PilotError(f"recorded database {name!r} is not this pilot's (refused)")
                conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                    sql.Identifier(name)))
                dropped.append(name)
        manifest["dropped"] = sorted(set(manifest["dropped"]) | set(dropped))
        save(root, manifest)
    finally:
        stop(stack, data)
    return dropped


def status(root: Path) -> dict:
    manifest = load(root)
    return {"status": manifest["status"], "reserved": manifest["reserved"],
            "allowance": manifest["allowance"], "stopped": manifest["stopped"],
            "not_attempted": manifest["not_attempted"],
            "pairs": [{k: p.get(k) for k in ("pair_id", "status", "live", "reservation",
                                              "stop_reason")} for p in manifest["pairs"]],
            "databases_kept": sorted(set(manifest["databases"].values())
                                     - set(manifest["dropped"]))}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "run", "status", "cleanup"):
        command = sub.add_parser(name)
        command.add_argument("--root", type=Path, required=True)
        if name == "plan":
            command.add_argument("--seed", type=int, default=20261106)
        if name == "run":
            command.add_argument("--pair", required=True)
            command.add_argument("--allow-live", action="store_true")
        if name == "cleanup":
            command.add_argument("--drop", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            result = {"planned": [p["pair_id"] for p in plan(args.root, args.seed)["pairs"]]}
        elif args.command == "run":
            pair = run_pair(args.root, args.pair, args.allow_live)
            result = {k: pair.get(k) for k in ("pair_id", "status", "exit_code",
                                               "stop_reason", "run_file")}
        elif args.command == "status":
            result = status(args.root)
        else:
            result = {"dropped": cleanup(args.root, args.drop)}
    except PilotError as error:
        print(f"refused: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
