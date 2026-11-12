"""Test-only stand-in children for supervisor lifecycle tests (never used in production).

usage: python fake_child.py MODE [REPORT_FILE]
Reads the framed request header like the real child, then misbehaves according to MODE.
"""
import json
import os
import subprocess
import sys
import time


def report(path, doc):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh)


def main():
    mode = sys.argv[1]
    path = sys.argv[2] if len(sys.argv) > 2 else None
    header = json.loads(sys.stdin.buffer.readline())
    if mode == "slow":
        time.sleep(600)
    elif mode == "spam":
        chunk = b"x" * 65536
        while True:
            sys.stdout.buffer.write(chunk)
    elif mode == "crash":
        os._exit(3)
    elif mode == "garbage":
        sys.stdout.write("not json at all")
        return 0
    elif mode == "wrong_id":
        sys.stdout.write(json.dumps({"protocol": header["protocol"], "request_id": "q_forged",
                                     "status": "complete"}))
        return 0
    elif mode == "alloc":
        target = int(header["limits"]["memory_bytes"]) if os.name == "nt" else \
            int(header["limits"]["posix_address_space_bytes"])
        try:
            blob = bytearray(target + 512 * 1024 * 1024)
            blob[-1] = 1
        except MemoryError:
            os._exit(7)
        os._exit(8)
    elif mode == "spawn":
        try:
            proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
        except OSError as exc:
            report(path, {"spawned": False, "error": type(exc).__name__})
            return 0
        report(path, {"spawned": True, "pid": proc.pid})
        return 0  # exit, leaving the grandchild behind for the supervisor to stop
    elif mode == "guard_probe":
        sys.path[:0] = [p for p in header.get("paths", [])]
        from docworker import guard
        guard.install()
        results = {}

        def attempt(name, fn):
            try:
                fn()
                results[name] = "allowed"
            except PermissionError:
                results[name] = "denied"
            except Exception as exc:  # noqa: BLE001
                results[name] = "other:" + type(exc).__name__

        import socket
        attempt("socket_connect", lambda: socket.create_connection(("198.51.100.7", 80), 1))
        outside = os.path.join(os.path.dirname(os.path.abspath(path)), "canary.txt")
        attempt("read_outside", lambda: open(outside, "rb").read())
        attempt("write_cwd", lambda: open("written.txt", "w").write("x"))
        attempt("subprocess", lambda: subprocess.run([sys.executable, "-c", "pass"]))
        attempt("os_system", lambda: os.system("echo hi"))
        attempt("remove", lambda: os.remove(outside))
        import urllib.request
        attempt("urlopen", lambda: urllib.request.urlopen("http://198.51.100.7/", timeout=1))
        attempt("stdlib_read", lambda: open(os.__file__, "rb").read(10))
        # the report is written by the supervisor-side test via stdout instead of a file
        sys.stdout.write(json.dumps({"protocol": header["protocol"],
                                     "request_id": header["request_id"], "status": "complete",
                                     "probe": results, "guard": guard.summary()}))
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
