"""Local CLI prototype (Part A). Not an HTTP endpoint and not a browser upload.

The session token is read from the environment variable SENTINEL_DOC_SESSION (never argv),
mirroring memory-only bearer tokens; the store keeps only its SHA-256.

  sentinel-docworker init    --store DIR
  sentinel-docworker ingest  --store DIR --format csv|xlsx|pdf --file LOCAL_FILE
  sentinel-docworker extract --store DIR --handle H [--decimal-style ...] [--date-order ...]
                             [--default-currency XXX] [--no-narrative]
  sentinel-docworker delete  --store DIR --handle H
  sentinel-docworker purge-expired --store DIR
  sentinel-docworker recover --store DIR
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .handles import HandleStore, StoreError
from .limits import DATE_ORDERS, DECIMAL_STYLES, Options
from .supervisor import Supervisor

SESSION_ENV = "SENTINEL_DOC_SESSION"


def _print(doc: dict) -> None:
    sys.stdout.write(json.dumps(doc, ensure_ascii=False, indent=2) + "\n")


def _session() -> str:
    token = os.environ.get(SESSION_ENV, "")
    if not token:
        raise StoreError("invalid_session", f"set {SESSION_ENV}")
    return token


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sentinel-docworker")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "ingest", "extract", "delete", "purge-expired", "recover"):
        p = sub.add_parser(name)
        p.add_argument("--store", required=True)
        if name == "ingest":
            p.add_argument("--file", required=True)
            p.add_argument("--format", required=True, choices=("csv", "xlsx", "pdf"))
        if name in ("extract", "delete"):
            p.add_argument("--handle", required=True)
        if name == "extract":
            p.add_argument("--decimal-style", choices=DECIMAL_STYLES, default="unspecified")
            p.add_argument("--date-order", choices=DATE_ORDERS, default="iso_only")
            p.add_argument("--default-currency", default=None)
            p.add_argument("--no-narrative", action="store_true")
    args = parser.parse_args(argv)
    store = HandleStore(Path(args.store))
    try:
        if args.command == "init":
            store.init()
            _print({"store": "ready"})
        elif args.command == "ingest":
            _print(store.ingest_file(args.file, args.format, _session()))
        elif args.command == "extract":
            options = Options(args.decimal_style, args.date_order, args.default_currency)
            result = Supervisor(store).extract(args.handle, _session(), options,
                                               narrative=not args.no_narrative)
            _print(result)
            return 0 if result.get("status") in ("complete", "partial") else 3
        elif args.command == "delete":
            _print(store.delete(args.handle, _session()))
        elif args.command == "purge-expired":
            _print(store.purge_expired())
        elif args.command == "recover":
            _print(Supervisor(store).recover())
    except StoreError as exc:
        _print({"status": "refused", "code": exc.code})
        return 4
    except ValueError as exc:
        _print({"status": "refused", "code": "invalid_option", "detail": str(exc)})
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
