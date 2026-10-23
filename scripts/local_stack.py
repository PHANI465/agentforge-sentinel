"""Local API + Postgres stack for operators (C08). Everything lives under .agent/stack/
(git-ignored): cluster data, API log, pid file and the dev session token. The token is
never printed; `smoke` reads it from the file.

    uv run --locked python scripts/local_stack.py up        # cluster, migrate, session, API
    uv run --locked python scripts/local_stack.py status
    uv run --locked python scripts/local_stack.py smoke [--restart-api]
    uv run --locked python scripts/local_stack.py backup    # pg_dump -Fc to .agent/backups/
    uv run --locked python scripts/local_stack.py restore FILE --database NAME
    uv run --locked python scripts/local_stack.py down

The investigator is deterministic unless --investigator claude-cli is given (local only).
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
STACK = ROOT / ".agent" / "stack"
BACKUPS = ROOT / ".agent" / "backups"
DATABASE = "sentinel"


def cluster(db_port: int):
    from sentinel import devdb

    bin_dir = devdb.find_pg_bin()
    if bin_dir is None:
        sys.exit("Postgres initdb not found; set SENTINEL_PG_BIN.")
    return devdb.Cluster(bin_dir, STACK / "pg" / "data", db_port)


def state() -> dict:
    path = STACK / "state.json"
    return json.loads(path.read_text()) if path.exists() else {}


def save_state(**values) -> None:
    STACK.mkdir(parents=True, exist_ok=True)
    (STACK / "state.json").write_text(json.dumps({**state(), **values}, indent=2) + "\n")


def healthy(port: int) -> dict | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=2) as response:
            return json.loads(response.read())
    except OSError:
        return None


def database_up(c) -> bool:
    import psycopg

    try:
        with psycopg.connect(c.url(), connect_timeout=2):
            return True
    except psycopg.OperationalError:
        return False


def ensure_database(c) -> str:
    import psycopg

    with psycopg.connect(c.url(), autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s",
                              (DATABASE,)).fetchone()
        if not exists:
            conn.execute(f'CREATE DATABASE "{DATABASE}"')
    return c.url(DATABASE)


def ensure_session(url: str) -> None:
    """Reuse a stored dev token while valid; otherwise issue one. Never printed."""
    from sentinel.investigators import DeterministicInvestigator
    from sentinel.service import Sentinel

    path = STACK / "session.json"
    if path.exists():
        stored = json.loads(path.read_text())
        if datetime.fromisoformat(stored["expires_at"]) > datetime.now(timezone.utc):
            return
    token, ctx = Sentinel(url, DeterministicInvestigator()).create_session(
        frozenset({"ingest_transaction", "read_case", "approve_action",
                   "execute_simulated_action"}), ttl=timedelta(hours=8))
    path.write_text(json.dumps({"token": token, "tenant_id": str(ctx.scope.tenant_id),
                                "session_id": str(ctx.scope.session_id),
                                "expires_at": (datetime.now(timezone.utc)
                                               + timedelta(hours=8)).isoformat()}))
    try:
        path.chmod(0o600)
    except OSError:
        pass


def start_api(url: str, port: int, investigator: str) -> None:
    env = {**os.environ, "SENTINEL_DATABASE_URL": url, "SENTINEL_INVESTIGATOR": investigator,
           "SENTINEL_MODE": "local"}
    log = open(STACK / "api.log", "ab")
    flags = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" \
        else {"start_new_session": True}
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "sentinel.api:create_app", "--factory",
         "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log, **flags)
    save_state(api_pid=process.pid, api_port=port, investigator=investigator)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if healthy(port):
            return
        if process.poll() is not None:
            sys.exit(f"API exited with {process.returncode}; see {STACK / 'api.log'}")
        time.sleep(0.3)
    sys.exit("API did not become healthy within 30 s")


def stop_api() -> None:
    pid = state().get("api_pid")
    if not pid:
        return
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
        else:
            os.killpg(pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass
    port = state().get("api_port")
    deadline = time.monotonic() + 10
    while port and healthy(port) and time.monotonic() < deadline:
        time.sleep(0.2)
    save_state(api_pid=None)


def up(args) -> None:
    from sentinel import db

    c = cluster(args.db_port)
    if not c.data_dir.exists():
        c.init()
    if not database_up(c):
        c.start()
    url = ensure_database(c)
    applied = db.migrate(url)
    print("migrations applied: " + (", ".join(applied) or "none pending"))
    ensure_session(url)
    save_state(db_port=args.db_port, database_url=url)
    if healthy(args.port):
        print(f"API already healthy on port {args.port}")
    else:
        start_api(url, args.port, args.investigator)
    print(f"API http://127.0.0.1:{args.port} ({healthy(args.port)['investigator']}); "
          f"token in {STACK / 'session.json'}")


def down(args) -> None:
    stop_api()
    s = state()
    c = cluster(s.get("db_port", args.db_port))
    if database_up(c):
        c.stop()
    print("stack stopped (data kept under .agent/stack)")


def status(args) -> int:
    s = state()
    api = healthy(s.get("api_port", args.port))
    c = cluster(s.get("db_port", args.db_port))
    print(f"database: {'up' if database_up(c) else 'down'}; "
          f"api: {api['investigator'] if api else 'down'}")
    return 0 if api and database_up(c) else 1


def smoke(args) -> None:
    s = state()
    token = json.loads((STACK / "session.json").read_text())["token"]
    base = f"http://127.0.0.1:{s['api_port']}"
    env = {**os.environ, "SENTINEL_TOKEN": token}
    script = [sys.executable, str(ROOT / "scripts" / "smoke_thin_path.py"), "--base-url", base]
    first = subprocess.run([*script, "investigate"], env=env, capture_output=True, text=True,
                           check=True).stdout
    print(first.strip())
    case_id = first.rsplit("CASE_ID=", 1)[1].strip()
    if args.restart_api:
        stop_api()
        print(f"api stopped; healthy={bool(healthy(s['api_port']))}")
        start_api(s["database_url"], s["api_port"], s.get("investigator", "deterministic"))
        print("api restarted (new process)")
    print(subprocess.run([*script, "execute", case_id], env=env, capture_output=True,
                         text=True, check=True).stdout.strip())


def backup(args) -> None:
    s = state()
    c = cluster(s["db_port"])
    BACKUPS.mkdir(parents=True, exist_ok=True)
    out = args.out or BACKUPS / f"sentinel-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.dump"
    subprocess.run([str(c.bin_dir / "pg_dump"), "--format=custom", "--no-owner",
                    f"--file={out}", s["database_url"]], check=True)
    print(f"backup written: {out}")


def restore(args) -> None:
    import psycopg

    s = state()
    c = cluster(s["db_port"])
    if not args.database.isidentifier():
        sys.exit("database must be a plain identifier")
    with psycopg.connect(c.url(), autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{args.database}"')
    subprocess.run([str(c.bin_dir / "pg_restore"), "--no-owner", "--exit-on-error",
                    f"--dbname={c.url(args.database)}", str(args.file)], check=True)
    print(f"restored {args.file} into {args.database}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db-port", type=int, default=55433)
    sub = parser.add_subparsers(dest="command", required=True)
    up_cmd = sub.add_parser("up")
    up_cmd.add_argument("--investigator", choices=("deterministic", "claude-cli"),
                        default="deterministic")
    sub.add_parser("down")
    sub.add_parser("status")
    sub.add_parser("smoke").add_argument("--restart-api", action="store_true")
    sub.add_parser("backup").add_argument("--out", type=Path)
    restore_cmd = sub.add_parser("restore")
    restore_cmd.add_argument("file", type=Path)
    restore_cmd.add_argument("--database", required=True)
    args = parser.parse_args()
    result = {"up": up, "down": down, "status": status, "smoke": smoke, "backup": backup,
              "restore": restore}[args.command](args)
    return result or 0


if __name__ == "__main__":
    raise SystemExit(main())
