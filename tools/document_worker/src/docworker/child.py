"""Parser child: ``python -I -m docworker.child``. Never given a path, URI or handle.

stdin : one UTF-8 JSON header line (<= 64 KiB), then exactly ``size`` raw document bytes.
stdout: exactly one UTF-8 JSON result document.
exit  : 0 when a result document was written (any extraction status); 2 on a protocol error
        (an error document is still written when possible).

Order: read and verify the bytes (stdlib only) -> import parser libraries -> install the
audit-hook guard -> parse. The supervisor writes the request only after the OS bounds are in
place, so no document byte is parsed before the child is contained.
"""

from __future__ import annotations

import hashlib
import json
import sys

from . import PROTOCOL

MAX_HEADER = 64 * 1024


def _emit(doc: dict) -> None:
    payload = json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    sys.stdout.buffer.write(payload)
    sys.stdout.buffer.flush()


def _protocol_error(code: str, request_id=None) -> int:
    _emit({"protocol": PROTOCOL, "request_id": request_id, "status": "error",
           "errors": [{"code": code, "detail": ""}]})
    return 2


def _read_exact(stream, size: int) -> bytes:
    chunks, remaining = [], size
    while remaining:
        chunk = stream.read(min(remaining, 1 << 20))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def main() -> int:
    stdin = sys.stdin.buffer
    line = stdin.readline(MAX_HEADER + 1)
    if not line.endswith(b"\n") or len(line) > MAX_HEADER:
        return _protocol_error("bad_header")
    try:
        header = json.loads(line)
        request_id = str(header["request_id"])
        size = int(header["size"])
        fmt = str(header["format"])
        expected = str(header["sha256"])
        if header.get("protocol") != PROTOCOL or size < 0:
            raise ValueError
    except (ValueError, KeyError, TypeError):
        return _protocol_error("bad_header")
    from .limits import Limits, Options
    try:
        limits = Limits.from_dict(header.get("limits") or {})
        options = Options.from_dict(header.get("options") or {})
    except (ValueError, TypeError):
        return _protocol_error("bad_options", request_id)
    if size > limits.max_input_bytes:
        return _protocol_error("input_too_large", request_id)
    data = _read_exact(stdin, size)
    if len(data) != size or stdin.read(1):
        return _protocol_error("framing_mismatch", request_id)
    sha = hashlib.sha256(data).hexdigest()
    if sha != expected:
        return _protocol_error("integrity_mismatch", request_id)

    from . import extract  # heavy parser imports happen here, before the guard
    import markitdown.converters  # noqa: F401  (force import before the guard)
    import openpyxl  # noqa: F401
    import pdfminer.high_level  # noqa: F401
    import pdfplumber  # noqa: F401
    import pandas  # noqa: F401
    from . import guard
    versions = extract.library_versions()
    identity = extract.source_identity()
    guard.install()
    try:
        result = extract.run(data, fmt, sha, limits, options,
                             with_narrative=bool(header.get("narrative", True)))
    except MemoryError:
        result = {"protocol": PROTOCOL, "status": "error",
                  "errors": [{"code": "memory_exhausted", "detail": ""}]}
    except Exception as exc:  # never a traceback with document content on stdout
        result = {"protocol": PROTOCOL, "status": "error",
                  "errors": [{"code": "parser_exception", "detail": type(exc).__name__}]}
    result["request_id"] = request_id
    result.setdefault("parser", dict(identity, libraries=versions))
    result["guard"] = guard.summary()
    _emit(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
