"""Build an auditable Vercel package from one clean Git revision."""

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[2]
HOSTED = ("app.py", "guard.py", "iaf.py", "iaf-knowledge.json", "vercel.json")
SOURCE = (
    "src/sentinel", "ml", "data_pipeline", "public_site/static",
    "web/index.html", "web/package.json", "web/package-lock.json", "web/src",
    "web/postcss.config.mjs", "web/tsconfig.json", "web/vite.config.ts",
    "pyproject.toml", "uv.lock", *(f"hosting/vercel/{name}" for name in HOSTED),
)
STATIC_SUFFIXES = {
    ".bcmap", ".css", ".docx", ".html", ".js", ".json", ".mjs", ".pdf",
    ".svg", ".txt", ".woff2", ".xlsx", ".zip",
}
STATIC_EXTENSIONLESS = {"LICENSE", "LICENSE-Geist"}
PRIVATE_NAME = re.compile(r"(^[.]env(?:[.]|$)|[.](?:pem|key|pfx|p12|map)$)", re.I)
SECRET = re.compile(
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|"
    rb"\b(?:sk-(?:proj-|ant-)?|ghp_|github_pat_)[A-Za-z0-9_-]{35,}|"
    rb"postgres(?:ql)?://[^\s:/]+:[^\s@]+@"
)


def git(*args: str) -> bytes:
    return subprocess.check_output(("git", *args), cwd=ROOT)


def clean_commit() -> str:
    if git("status", "--porcelain=v1", "--untracked-files=all"):
        raise ValueError("Commit release inputs first. The checkout has changes.")
    return git("rev-parse", "HEAD").decode().strip()


def extract_commit(commit: str, root: Path) -> None:
    with tarfile.open(fileobj=io.BytesIO(git("archive", commit, "--", *SOURCE))) as archive:
        for member in archive.getmembers():
            target = root / member.name
            if not target.resolve().is_relative_to(root) or not (member.isdir() or member.isfile()):
                raise ValueError("Release sources must be ordinary files inside the snapshot.")
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as source, target.open("xb") as output:
                shutil.copyfileobj(source, output)


def scan_files(directory: Path) -> dict[str, str]:
    files = {}
    for path in sorted(directory.rglob("*")):
        relative = path.relative_to(directory).as_posix()
        if path.is_symlink() or PRIVATE_NAME.search(path.name):
            raise ValueError(f"Prohibited release path: {relative}")
        if not path.is_file():
            continue
        content = path.read_bytes()
        # Binary assets are checked by provenance and exact bytes. Search text for key patterns.
        if b"\x00" not in content and SECRET.search(content):
            raise ValueError(f"Credential pattern in release file: {relative}")
        files[relative] = hashlib.sha256(content).hexdigest()
    return files


def package(destination: Path) -> str:
    commit = clean_commit()
    destination = destination.resolve()
    if destination.is_relative_to(ROOT) or destination.exists():
        raise ValueError("Choose a fresh staging directory outside the checkout.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="sentinel-build-", dir=destination.parent) as work:
        snapshot = Path(work)
        extract_commit(commit, snapshot)
        static = snapshot / "public_site/static"
        for path in static.rglob("*"):
            if path.is_file() and (
                path.suffix not in STATIC_SUFFIXES
                and path.name not in STATIC_EXTENSIONLESS | {".gitattributes"}
            ):
                raise ValueError(f"Unexpected public asset: {path.relative_to(static)}")

        web = snapshot / "web"
        environment = {name: value for name, value in os.environ.items()
                       if not name.upper().startswith(("VITE_", "NODE_OPTIONS"))}
        environment["VITE_SENTINEL_HOSTED_DEMO"] = "1"
        npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
        if npm is None:
            raise ValueError("npm is required to package the release.")
        subprocess.run([npm, "ci", "--ignore-scripts", "--no-audit", "--no-fund"],
                       cwd=web, env=environment, check=True)
        subprocess.run(["node", "node_modules/vite/bin/vite.js", "build", "--base", "/workbench/"],
                       cwd=web, env=environment, check=True)

        stage = snapshot / "package"
        stage.mkdir()
        for name, source in (("sentinel", "src/sentinel"), ("ml", "ml"),
                             ("data_pipeline", "data_pipeline"), ("public", "public_site/static")):
            shutil.copytree(snapshot / source, stage / name, ignore=shutil.ignore_patterns(".gitattributes"))
        shutil.copytree(web / "dist", stage / "public/workbench")
        for name in HOSTED:
            shutil.copyfile(snapshot / "hosting/vercel" / name, stage / name)
        (stage / ".python-version").write_bytes(b"3.12\n")
        subprocess.run([
            "uv", "export", "--locked", "--no-dev", "--no-hashes", "--no-header",
            "--no-emit-project", "--output-file", str(stage / "requirements.txt"), "--quiet",
        ], cwd=snapshot, check=True)
        manifest = {"source_commit": commit, "sha256": scan_files(stage)}
        # Keep the package manifest alongside the staging directory, outside the upload root.
        manifest_path = destination.with_name(destination.name + "-manifest.json")
        with manifest_path.open("x", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2)
            handle.write("\n")
        stage.rename(destination)
    return commit


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    try:
        print(f"Packaged source {package(parser.parse_args().destination)}")
    except (ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Release refused: {error}\n")
