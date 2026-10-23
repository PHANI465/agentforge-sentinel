"""Disposable local Postgres clusters for tests and development; no stored credentials.

The cluster uses trust authentication and listens only on 127.0.0.1. It is a development
convenience, never a deployment configuration.
"""
from __future__ import annotations

import glob
import os
import shutil
import socket
import subprocess
from dataclasses import dataclass
from pathlib import Path

USER = "sentinel"


def find_pg_bin() -> Path | None:
    """SENTINEL_PG_BIN, then PATH, then common install locations (newest version first)."""
    configured = os.environ.get("SENTINEL_PG_BIN")
    candidates = [Path(configured)] if configured else []
    on_path = shutil.which("initdb")
    if on_path:
        candidates.append(Path(on_path).parent)
    patterns = ["C:/Program Files/PostgreSQL/*/bin", "/usr/lib/postgresql/*/bin",
                "/opt/homebrew/opt/postgresql*/bin", "/usr/local/opt/postgresql*/bin"]
    for pattern in patterns:
        found = glob.glob(pattern)
        candidates.extend(Path(p) for p in sorted(found, key=_version_key, reverse=True))
    for candidate in candidates:
        if any((candidate / name).exists() for name in ("initdb", "initdb.exe")):
            return candidate
    return None


def _version_key(path: str) -> tuple[int, str]:
    digits = "".join(ch for ch in Path(path).parent.name if ch.isdigit())
    return (int(digits) if digits else 0, path)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@dataclass
class Cluster:
    bin_dir: Path
    data_dir: Path
    port: int

    def url(self, database: str = "postgres") -> str:
        return f"postgresql://{USER}@127.0.0.1:{self.port}/{database}"

    def _run(self, tool: str, *args: str) -> None:
        # No pipes: on Windows the started server inherits them and the call never returns.
        subprocess.run([str(self.bin_dir / tool), *args], check=True,
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=120)

    def init(self) -> None:
        self._run("initdb", "-D", str(self.data_dir), "-U", USER, "-A", "trust",
                  "-E", "UTF8", "--no-locale")

    def start(self) -> None:
        log = self.data_dir.parent / "postgres.log"
        self._run("pg_ctl", "-D", str(self.data_dir), "-l", str(log), "-w",
                  "-o", f"-p {self.port} -c listen_addresses=127.0.0.1", "start")

    def stop(self) -> None:
        self._run("pg_ctl", "-D", str(self.data_dir), "-m", "fast", "-w", "stop")

    def create_database(self, name: str) -> str:
        import psycopg

        if not name.isidentifier() or not name.isascii():
            raise ValueError("database name must be a plain ASCII identifier")
        with psycopg.connect(self.url(), autocommit=True) as conn:
            conn.execute(f'CREATE DATABASE "{name}"')
        return self.url(name)
