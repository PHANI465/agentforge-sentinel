"""Owned file handles: the only way a document reaches the extractor.

A handle is an opaque random id issued by this store when it copies bytes in. Resolving it
requires the same session token (only its SHA-256 is stored), an unexpired lease and an
unchanged content hash. Callers can never supply a path, URI or directory. Missing, foreign,
expired and malformed handles are indistinguishable ("not_found").

The store directory carries an ownership marker (as in the accepted local-stack lifecycle):
a directory without our marker is never adopted, and cleanup only removes what the marker
proves we created.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import stat
import time
from dataclasses import dataclass
from pathlib import Path

from .limits import Limits

MARKER = ".docworker-store"
_HANDLE_RE = re.compile(r"^h_[A-Za-z0-9_-]{22}$")
FORMAT_EXTENSIONS = {"pdf": {".pdf"}, "csv": {".csv"}, "xlsx": {".xlsx"}}


class StoreError(Exception):
    """Refusal with a stable code; the message never echoes document bytes."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


@dataclass(frozen=True)
class Resolved:
    handle_id: str
    format: str
    sha256: str
    size: int
    blob: Path


def _token_hash(session_token: str) -> str:
    if not isinstance(session_token, str) or len(session_token) < 16:
        raise StoreError("invalid_session", "session token must be at least 16 characters")
    return hashlib.sha256(session_token.encode("utf-8")).hexdigest()


class HandleStore:
    def __init__(self, root: Path, limits: Limits | None = None, clock=time.time):
        self.root = Path(root)
        self.limits = limits or Limits()
        self.clock = clock

    # ---- ownership ---------------------------------------------------------------------------
    def canonical(self) -> str:
        return os.path.normcase(os.path.realpath(self.root))

    def init(self) -> None:
        if self.root.exists():
            if os.path.islink(self.root):
                raise StoreError("not_owned", "store path is a link")
            if any(self.root.iterdir()):
                self.verify()
                return
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / MARKER).write_text(json.dumps(
            {"owner": secrets.token_hex(16), "dir": self.canonical(), "version": 1}))
        for sub in ("handles", "runs", "recovery"):
            (self.root / sub).mkdir(exist_ok=True)

    def verify(self) -> dict:
        marker = self.root / MARKER
        if os.path.islink(self.root) or not marker.is_file():
            raise StoreError("not_owned", "directory has no store ownership marker")
        try:
            data = json.loads(marker.read_text())
        except (OSError, ValueError):
            raise StoreError("not_owned", "unreadable marker") from None
        if data.get("version") != 1 or data.get("dir") != self.canonical():
            raise StoreError("not_owned", "marker does not match this directory")
        return data

    def owner(self) -> str:
        return str(self.verify()["owner"])

    def _inside(self, path: Path, sub: str) -> bool:
        base = os.path.normcase(os.path.realpath(self.root / sub)) + os.sep
        return os.path.normcase(os.path.realpath(path)).startswith(base) \
            and not os.path.islink(path)

    # ---- ingest ------------------------------------------------------------------------------
    def ingest_file(self, source: str, fmt: str, session_token: str) -> dict:
        """Owner-side local copy-in (stands in for a browser upload in Part A)."""
        if not isinstance(source, str) or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", source) \
                or source.startswith("\\\\"):
            raise StoreError("not_a_local_file", "URIs and UNC paths are refused")
        path = Path(source)
        try:
            st = os.lstat(path)
        except OSError:
            raise StoreError("not_a_local_file", "file not found") from None
        if not stat.S_ISREG(st.st_mode):
            raise StoreError("not_a_local_file", "only a regular, non-link file is accepted")
        if fmt not in FORMAT_EXTENSIONS or path.suffix.lower() not in FORMAT_EXTENSIONS[fmt]:
            raise StoreError("format_mismatch", "extension does not match the declared format")
        if st.st_size > self.limits.max_input_bytes:
            raise StoreError("too_large", f"limit {self.limits.max_input_bytes} bytes")
        with open(path, "rb") as fh:
            opened = os.fstat(fh.fileno())
            if (opened.st_dev, opened.st_ino) != (st.st_dev, st.st_ino):
                raise StoreError("not_a_local_file", "file changed while being opened")
            data = fh.read(self.limits.max_input_bytes + 1)
        return self.ingest_bytes(data, fmt, session_token)

    def ingest_bytes(self, data: bytes, fmt: str, session_token: str) -> dict:
        self.verify()
        token_hash = _token_hash(session_token)
        if fmt not in FORMAT_EXTENSIONS:
            raise StoreError("format_not_supported")
        if len(data) > self.limits.max_input_bytes:
            raise StoreError("too_large", f"limit {self.limits.max_input_bytes} bytes")
        handle_id = "h_" + secrets.token_urlsafe(16)
        folder = self.root / "handles" / handle_id
        folder.mkdir()
        sha = hashlib.sha256(data).hexdigest()
        now = self.clock()
        (folder / "blob").write_bytes(data)
        meta = {"handle_id": handle_id, "session_sha256": token_hash, "format": fmt,
                "sha256": sha, "size": len(data), "created_at": now,
                "expires_at": now + self.limits.handle_ttl_seconds}
        (folder / "meta.json").write_text(json.dumps(meta))
        return {"handle_id": handle_id, "format": fmt, "sha256": sha, "size": len(data),
                "expires_at": meta["expires_at"]}

    # ---- resolve / delete --------------------------------------------------------------------
    def _load(self, handle_id: str, session_token: str) -> tuple[Path, dict]:
        self.verify()
        token_hash = _token_hash(session_token)
        if not isinstance(handle_id, str) or not _HANDLE_RE.match(handle_id):
            raise StoreError("not_found")
        folder = self.root / "handles" / handle_id
        if not folder.is_dir() or not self._inside(folder, "handles"):
            raise StoreError("not_found")
        try:
            meta = json.loads((folder / "meta.json").read_text())
        except (OSError, ValueError):
            raise StoreError("not_found") from None
        if not secrets.compare_digest(str(meta.get("session_sha256")), token_hash):
            raise StoreError("not_found")
        if self.clock() >= float(meta.get("expires_at", 0)):
            raise StoreError("not_found")
        return folder, meta

    def resolve(self, handle_id: str, session_token: str) -> Resolved:
        folder, meta = self._load(handle_id, session_token)
        blob = folder / "blob"
        if not blob.is_file() or not self._inside(blob, "handles"):
            raise StoreError("not_found")
        return Resolved(handle_id, meta["format"], meta["sha256"], int(meta["size"]), blob)

    def read_verified(self, resolved: Resolved) -> bytes:
        with open(resolved.blob, "rb") as fh:
            data = fh.read(self.limits.max_input_bytes + 1)
        if len(data) != resolved.size or hashlib.sha256(data).hexdigest() != resolved.sha256:
            raise StoreError("integrity_mismatch", "stored bytes changed after ingest")
        return data

    def delete(self, handle_id: str, session_token: str) -> dict:
        folder, _meta = self._load(handle_id, session_token)
        shutil.rmtree(folder)
        return {"handle_id": handle_id, "deleted": not folder.exists()}

    def purge_expired(self) -> dict:
        self.verify()
        removed, kept = 0, 0
        for folder in (self.root / "handles").iterdir():
            if not _HANDLE_RE.match(folder.name) or not self._inside(folder, "handles"):
                kept += 1
                continue
            try:
                meta = json.loads((folder / "meta.json").read_text())
                expired = self.clock() >= float(meta.get("expires_at", 0))
            except (OSError, ValueError):
                expired = True
            if expired:
                shutil.rmtree(folder)
                removed += 1
            else:
                kept += 1
        return {"removed": removed, "kept": kept}
