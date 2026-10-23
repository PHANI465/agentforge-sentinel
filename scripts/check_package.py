"""Build the wheel and sdist, then verify what ships (C06).

- Every source migration (src/sentinel/db/migrations/*.sql) is in the wheel and the sdist,
  byte for byte; nothing else under migrations. No caches, secrets or generated data in
  either; no tests in the wheel (setuptools puts test files in the sdist by default).
- The wheel installs into a fresh virtual environment, and the installed package
  discovers exactly the source migrations from its own location.

    uv run --locked python scripts/check_package.py [--keep DIR]
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = sorted((ROOT / "src" / "sentinel" / "db" / "migrations").glob("*.sql"))
# Never shipped anywhere; the wheel (what gets installed) also excludes tests.
FORBIDDEN = ("__pycache__", ".env", ".pem", ".key", "data/generated", ".agent/")
WHEEL_FORBIDDEN = FORBIDDEN + ("tests/", "tests_handoff/")


def run(*cmd: str, cwd: Path | None = None) -> str:
    done = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if done.returncode != 0:
        sys.exit(f"command failed ({done.returncode}): {' '.join(cmd)}\n{done.stderr[-2000:]}")
    return done.stdout


def check_archive(names: dict[str, bytes], prefix: str, label: str,
                  forbidden: tuple[str, ...]) -> list[str]:
    problems = []
    shipped = {n[len(prefix):]: data for n, data in names.items() if n.startswith(prefix)
               and n.endswith(".sql")}
    expected = {p.name: p.read_bytes() for p in MIGRATIONS}
    if set(shipped) != set(expected):
        problems.append(f"{label}: migrations {sorted(shipped)} != source {sorted(expected)}")
    problems += [f"{label}: {name} differs from source" for name in expected
                 if name in shipped and shipped[name] != expected[name]]
    problems += [f"{label}: forbidden path {n}" for n in names if any(f in n for f in forbidden)]
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--keep", type=Path, help="keep build output here")
    args = parser.parse_args()
    if not MIGRATIONS:
        sys.exit("no source migrations found")
    work = Path(tempfile.mkdtemp(prefix="sentinel-pkg-"))
    try:
        # Build from a clean copy of tracked + non-ignored files, like a CI checkout. Building
        # in place can silently reuse a stale *.egg-info/SOURCES.txt or build/ directory.
        tree = work / "tree"
        listed = run("git", "ls-files", "-z", "--cached", "--others", "--exclude-standard",
                     cwd=ROOT)
        for name in filter(None, listed.split("\0")):
            if (ROOT / name).is_file():
                (tree / name).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / name, tree / name)
        dist = work / "dist"
        run("uv", "build", "--out-dir", str(dist), cwd=tree)
        wheel = next(dist.glob("*.whl"))
        sdist = next(dist.glob("*.tar.gz"))
        with zipfile.ZipFile(wheel) as zf:
            wheel_files = {n: zf.read(n) for n in zf.namelist() if not n.endswith("/")}
        with tarfile.open(sdist) as tf:
            members = [m for m in tf.getmembers() if m.isfile()]
            sdist_files = {m.name.split("/", 1)[1]: tf.extractfile(m).read() for m in members}
        problems = check_archive(wheel_files, "sentinel/db/migrations/", "wheel", WHEEL_FORBIDDEN)
        problems += check_archive(sdist_files, "src/sentinel/db/migrations/", "sdist", FORBIDDEN)
        if "sentinel/contracts/v1.py" not in wheel_files:
            problems.append("wheel: sentinel/contracts/v1.py missing")

        venv = work / "venv"
        run("uv", "venv", "--quiet", "--python", sys.executable, str(venv))
        python = venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        run("uv", "pip", "install", "--quiet", "--python", str(python), str(wheel))
        probe = ("from sentinel import db; import sentinel; "
                 "print(sentinel.__file__); print('|'.join(sorted(p.name for p in "
                 "db.MIGRATIONS.glob('[0-9][0-9][0-9][0-9]_*.sql'))))")
        location, found = run(str(python), "-I", "-c", probe, cwd=work).splitlines()[-2:]
        if str(ROOT / "src") in location:
            problems.append(f"installed import resolved to the source tree: {location}")
        if found.split("|") != [p.name for p in MIGRATIONS]:
            problems.append(f"installed package discovers {found!r}")
        if args.keep:
            shutil.copytree(dist, args.keep, dirs_exist_ok=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    for problem in problems:
        print(problem)
    if problems:
        return 1
    print(f"Package OK: {wheel.name} and {sdist.name} ship {len(MIGRATIONS)} migrations; "
          "installed wheel discovers them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
