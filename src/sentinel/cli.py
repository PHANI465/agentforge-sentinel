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
# Opt-in only (DOC01 Part B): never part of the default grant above.
DOCUMENT_CAPABILITY = "analyze_document"
DEV_DIR = Path(".agent/devdb")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sentinel", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("migrate", help="apply pending migrations to SENTINEL_DATABASE_URL")
    session = commands.add_parser("create-session", help="issue a local analyst bearer token")
    session.add_argument("--capability", action="append", choices=ALL_CAPABILITIES,
                         help="repeatable; defaults to all analyst capabilities")
    session.add_argument("--with-document-analysis", action="store_true",
                         help="also grant the opt-in analyze_document capability (local "
                              "synthetic/public files only; needs a registered worker)")
    session.add_argument("--hours", type=int, default=8)
    grant = commands.add_parser("grant-runtime", help="create/refresh the least-privilege "
                                "API role (run as the schema owner)")
    grant.add_argument("--role", default="sentinel_runtime")
    for name, help_text in (("provision-accounts", "load account profiles (JSONL: account_id, "
                                                   "home_currency, opened_at) for one scope"),
                            ("record-disclosures", "load fraud disclosures (JSONL: external_id, "
                                                   "account_id, is_fraud, disclosed_at)")):
        loader = commands.add_parser(name, help=help_text)
        loader.add_argument("--tenant", required=True)
        loader.add_argument("--session", required=True)
        loader.add_argument("--file", required=True, type=Path)
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
    if args.command in ("provision-accounts", "record-disclosures"):
        # Operator-only (runtime role has SELECT only); there is no HTTP route for this.
        import json
        rows = [json.loads(line) for line in args.file.read_text(encoding="utf-8").splitlines()
                if line.strip()]
        from sentinel.service import MAX_LOCKED_ACCOUNTS
        service = Sentinel(url, from_environment())
        load = (service.provision_accounts if args.command == "provision-accounts"
                else service.record_disclosures)
        # Each chunk is one transaction under its accounts' decision locks; a failure leaves
        # earlier chunks committed (reported), so loads are rerunnable per chunk.
        loaded = 0
        for start in range(0, len(rows), MAX_LOCKED_ACCOUNTS):
            loaded += load(args.tenant, args.session, rows[start:start + MAX_LOCKED_ACCOUNTS])
            print(f"{args.command}: {loaded}/{len(rows)} rows committed")
        return 0
    if args.command == "migrate":
        applied = db.migrate(url)
        print("Applied: " + (", ".join(applied) if applied else "nothing pending"))
        return 0
    service = Sentinel(url, from_environment())
    grants = set(args.capability or ALL_CAPABILITIES)
    if args.with_document_analysis:
        grants.add(DOCUMENT_CAPABILITY)
    token, ctx = service.create_session(frozenset(grants), ttl=timedelta(hours=args.hours))
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
