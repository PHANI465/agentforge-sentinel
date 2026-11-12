"""In-process audit-hook guard for the parser child (PEP 578).

Installed after the parser libraries are imported and before any untrusted byte is parsed. It
denies Python-level socket use, HTTP/URL requests, process creation, file writes/renames/
deletes and file reads outside the interpreter/library installation.

This is defense in depth, NOT an operating-system sandbox: native code can bypass audit hooks,
and hooks cannot be removed or audited by the OS. No network-isolation claim follows from it.
OS-level bounds (job object / rlimits, deadline, output cap) are enforced by the supervisor.
"""

from __future__ import annotations

import os
import site
import sys
import sysconfig

_DENY_PREFIXES = ("socket.", "subprocess.", "os.exec", "os.spawn", "os.posix_spawn",
                  "shutil.", "ctypes.dlopen", "winreg.", "ftplib.", "smtplib.", "poplib.",
                  "imaplib.", "nntplib.", "telnetlib.")
_DENY_EVENTS = {
    "os.system", "os.startfile", "os.fork", "os.forkpty", "pty.spawn", "urllib.Request",
    "http.client.connect", "http.client.send", "webbrowser.open", "os.remove", "os.rename",
    "os.rmdir", "os.mkdir", "os.chmod", "os.chown", "os.symlink", "os.link", "os.truncate",
    "os.putenv", "os.unsetenv", "os.kill", "os.killpg", "signal.pthread_kill",
    "_winapi.CreateProcess", "_winapi.CreateNamedPipe", "_winapi.CreateFile",
    "os.utime", "os.chflags", "os.lchmod", "os.lchown",
}
_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND

denied: dict[str, int] = {}
_installed = False


class GuardDenied(PermissionError):
    pass


def _roots() -> tuple[str, ...]:
    candidates = {sys.prefix, sys.base_prefix, sys.exec_prefix, sys.base_exec_prefix,
                  sysconfig.get_paths().get("stdlib", ""), sysconfig.get_paths().get("purelib", ""),
                  sysconfig.get_paths().get("platlib", "")}
    try:
        candidates.update(site.getsitepackages())
    except AttributeError:
        pass
    candidates.add(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    # The child is launched with an explicit import path (src + the worker's site-packages);
    # only absolute existing directories count, never "" or the working directory.
    candidates.update(p for p in sys.path
                      if p and os.path.isabs(p) and os.path.isdir(p)
                      and os.path.realpath(p) != os.path.realpath(os.getcwd()))
    return tuple(sorted(os.path.normcase(os.path.realpath(p)) + os.sep
                        for p in candidates if p))


def _deny(event: str) -> None:
    denied[event] = denied.get(event, 0) + 1
    raise GuardDenied(f"blocked by document-worker guard: {event}")


def install() -> None:
    global _installed
    if _installed:
        return
    roots = _roots()

    def hook(event: str, args: tuple) -> None:
        if event in _DENY_EVENTS or event.startswith(_DENY_PREFIXES):
            _deny(event)
        if event == "open":
            path, mode, flags = (tuple(args) + (None, None, None))[:3]
            if isinstance(path, int):
                return  # an already-open descriptor (our stdin/stdout)
            if isinstance(mode, str) and any(m in mode for m in "wax+"):
                _deny("open:write")
            if isinstance(flags, int) and flags & _WRITE_FLAGS:
                _deny("open:write")
            try:
                real = os.path.normcase(os.path.realpath(os.fsdecode(path)))
            except (TypeError, ValueError):
                _deny("open:unresolvable")
            if not real.startswith(roots):
                _deny("open:outside_installation")
        elif event in ("os.listdir", "os.scandir") and args and args[0] not in (None, "."):
            try:
                real = os.path.normcase(os.path.realpath(os.fsdecode(args[0]))) + os.sep
            except (TypeError, ValueError):
                _deny(event)
            if not real.startswith(roots):
                _deny(event)

    sys.addaudithook(hook)
    _installed = True


def summary() -> dict:
    return {"kind": "python_audit_hook", "installed": _installed,
            "denied_events": dict(sorted(denied.items())),
            "claim": "in-process defense in depth; not OS network or filesystem isolation"}
