"""Local operator commands. The bearer token is printed once and never stored in clear."""
from __future__ import annotations

import argparse
import os
import sys
from datetime import timedelta
from pathlib import Path

from sentinel import db, devdb
from sentinel.investigators import from_environment
from sentinel.service import Sentinel

ALL_CAPABILITIES = ("ingest_transaction", "read_case", "approve_action",
                    "execute_simulated_action")
DEV_DIR = Path(".agent/devdb")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sentinel", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("migrate", help="apply pending migrations to SENTINEL_DATABASE_URL")
    session = commands.add_parser("create-session", help="issue a local analyst bearer token")
    session.add_argument("--capability", action="append", choices=ALL_CAPABILITIES,
                         help="repeatable; defaults to all analyst capabilities")
    session.add_argument("--hours", type=int, default=8)
    grant = commands.add_parser("grant-runtime", help="create/refresh the least-privilege "
                                "API role (run as the schema owner)")
    grant.add_argument("--role", default="sentinel_runtime")
    dev = commands.add_parser("devdb", help="disposable local Postgres under .agent/devdb")
    dev.add_argument("action", choices=("start", "stop"))
    dev.add_argument("--port", type=int, default=55432)
    args = parser.parse_args(argv)

    if args.command == "devdb":
        return _devdb(args.action, args.port)
    url = os.environ.get("SENTINEL_DATABASE_URL")
    if not url:
        print("Set SENTINEL_DATABASE_URL first.", file=sys.stderr)
        return 2
    if args.command == "grant-runtime":
        from sentinel.db import roles
        # A password, if wanted, comes from the environment, never the command line.
        roles.grant_runtime(url, args.role, os.environ.get("SENTINEL_RUNTIME_PASSWORD"))
        print(f"runtime role {args.role} granted")
        return 0
    if args.command == "migrate":
        applied = db.migrate(url)
        print("Applied: " + (", ".join(applied) if applied else "nothing pending"))
        return 0
    service = Sentinel(url, from_environment())
    token, ctx = service.create_session(frozenset(args.capability or ALL_CAPABILITIES),
                                        ttl=timedelta(hours=args.hours))
    print(f"tenant={ctx.scope.tenant_id} session={ctx.scope.session_id} actor={ctx.actor_id}")
    print(f"token={token}")
    return 0


def _devdb(action: str, port: int) -> int:
    bin_dir = devdb.find_pg_bin()
    if bin_dir is None:
        print("Postgres initdb not found; set SENTINEL_PG_BIN.", file=sys.stderr)
        return 2
    cluster = devdb.Cluster(bin_dir, DEV_DIR.resolve() / "data", port)
    if action == "stop":
        cluster.stop()
        return 0
    if not cluster.data_dir.exists():
        cluster.init()
    cluster.start()
    print(f"SENTINEL_DATABASE_URL={cluster.url()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
