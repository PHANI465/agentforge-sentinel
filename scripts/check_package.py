"""Build the wheel and sdist, then verify what ships (C06, refreshed for f38e920).

- Every source migration (src/sentinel/db/migrations/*.sql) is in the wheel and the sdist,
  byte for byte; nothing else under migrations. No caches, secrets or generated data in
  either; no tests or evals in the wheel (setuptools puts tests in the sdist by default).
- The accepted model/data identity assets (MODEL_ASSETS) are in both archives byte for
  byte, and the wheel ships no other non-Python file under ml/ or data_pipeline/.
- The wheel installs (with the lock's ml pins, no other resolution) into a fresh virtual
  environment. Run isolated from a neutral directory, sentinel/ml/data_pipeline import from
  that environment, discover exactly the source migrations, bind the registered scorer and
  load the frozen results.

    uv run --locked python scripts/check_package.py [--keep DIR]
"""
from __future__ import annotations

import argparse
import os
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
WHEEL_FORBIDDEN = FORBIDDEN + ("tests/", "tests_handoff/", "evals/")
# The registered p1 model's identity, artifact and frozen results, plus the C03 reference
# manifest: everything the installed scorer and results route read at runtime.
MODEL_ASSETS = (
    "ml/protocol.json", "ml/runs/p1/selection.json", "ml/runs/p1/select_stats.json",
    "ml/artifacts/p1/manifest.json", "ml/artifacts/p1/model.joblib",
    "ml/results/p1/test_report.json", "ml/results/p1/pr_curve_selected.csv",
    "data_pipeline/manifests/reference-g1-seed7.json",
)
PROBE = (
    "import json, sentinel, ml, data_pipeline\n"
    "from sentinel import db, model_results, scorers\n"
    "m = scorers.ModelScorer(scorers.REGISTRY['hgb_balanced@p1'])\n"
    "print(json.dumps({'files': [sentinel.__file__, ml.__file__, data_pipeline.__file__],\n"
    "    'migrations': sorted(p.name for p in db.MIGRATIONS.glob('[0-9][0-9][0-9][0-9]_*.sql')),\n"
    "    'artifact': m.model.artifact_sha256,\n"
    "    'results': model_results.load('p1')['artifact_sha256']}))\n"
)


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


def check_assets(names: dict[str, bytes], prefix: str, label: str,
                 exclusive: bool) -> list[str]:
    """MODEL_ASSETS byte-identical under prefix; with exclusive, no other non-Python file
    under the shipped ml/ or data_pipeline/ packages."""
    problems = []
    for asset in MODEL_ASSETS:
        shipped = names.get(prefix + asset)
        if shipped is None:
            problems.append(f"{label}: model asset {asset} missing")
        elif shipped != (ROOT / asset).read_bytes():
            problems.append(f"{label}: model asset {asset} differs from source")
    if exclusive:
        extra = sorted(n for n in names if n.startswith(("ml/", "data_pipeline/"))
                       and not n.endswith(".py") and n[len(prefix):] not in MODEL_ASSETS)
        problems += [f"{label}: unexpected file {n}" for n in extra]
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
        problems += check_assets(wheel_files, "", "wheel", exclusive=True)
        problems += check_assets(sdist_files, "", "sdist", exclusive=False)

        venv = work / "venv"
        run("uv", "venv", "--quiet", "--python", sys.executable, str(venv))
        python = venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        pins = work / "requirements-ml.txt"
        run("uv", "export", "--locked", "--extra", "ml", "--no-dev", "--no-emit-project",
            "--no-hashes", "--quiet", "--output-file", str(pins), cwd=ROOT)
        run("uv", "pip", "install", "--quiet", "--no-deps", "--python", str(python),
            "-r", str(pins), str(wheel))
        neutral = work / "neutral"
        neutral.mkdir()
        import json
        found = json.loads(run(str(python), "-I", "-c", PROBE, cwd=neutral).splitlines()[-1])
        root = os.path.normcase(os.path.realpath(venv))
        for location in found["files"]:
            if not os.path.normcase(os.path.realpath(location)).startswith(root):
                problems.append(f"installed import resolved outside the venv: {location}")
        if found["migrations"] != [p.name for p in MIGRATIONS]:
            problems.append(f"installed package discovers {found['migrations']!r}")
        manifest = json.loads((ROOT / "ml/artifacts/p1/manifest.json").read_text("utf-8"))
        if found["artifact"] != manifest["artifact_sha256"] or \
                found["results"] != manifest["artifact_sha256"]:
            problems.append("installed scorer/results do not bind the accepted artifact")
        if args.keep:
            shutil.copytree(dist, args.keep, dirs_exist_ok=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    for problem in problems:
        print(problem)
    if problems:
        return 1
    print(f"Package OK: {wheel.name} and {sdist.name} ship {len(MIGRATIONS)} migrations and "
          f"{len(MODEL_ASSETS)} model/data assets; the installed wheel imports outside the "
          "source tree, discovers the migrations and binds the registered scorer.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
