import json
import sys
import sysconfig
from pathlib import Path

import pytest

from docworker.handles import HandleStore
from docworker.limits import Limits
from docworker.supervisor import Supervisor

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "fixtures"
HELPER = Path(__file__).resolve().parent / "helpers" / "fake_child.py"
SESSION = "test-session-token-0123456789"
OTHER_SESSION = "other-session-token-9876543210"


def label_runs():
    labels = json.loads((FIXTURES / "labels.json").read_text(encoding="utf-8"))
    for name, label in sorted(labels.items()):
        for index, run in enumerate(label["runs"]):
            yield pytest.param(name, label["format"], run, id=f"{name}#{index}")


def fake_argv(mode: str, report: str | None = None) -> list[str]:
    base = getattr(sys, "_base_executable", None) or sys.executable
    paths = [str(ROOT / "src"), sysconfig.get_paths()["purelib"]]
    argv = [str(HELPER), mode] + ([report] if report else [])
    boot = (f"import sys, runpy; sys.path[:0] = {paths!r}; sys.argv = {argv!r}; "
            f"runpy.run_path({str(HELPER)!r}, run_name='__main__')")
    return [base, "-I", "-c", boot]


@pytest.fixture
def store(tmp_path):
    s = HandleStore(tmp_path / "store")
    s.init()
    return s


@pytest.fixture
def ingest(store):
    def _ingest(name_or_bytes, fmt=None):
        if isinstance(name_or_bytes, bytes):
            return store.ingest_bytes(name_or_bytes, fmt, SESSION)["handle_id"]
        path = FIXTURES / name_or_bytes
        return store.ingest_file(str(path), fmt or path.suffix[1:], SESSION)["handle_id"]
    return _ingest


def leftovers(store: HandleStore) -> dict:
    return {"runs": sorted(p.name for p in (store.root / "runs").iterdir()),
            "recovery": sorted(p.name for p in (store.root / "recovery").iterdir())}


@pytest.fixture
def make_supervisor(store):
    def _make(limits: Limits | None = None, **kw):
        return Supervisor(store, limits=limits, **kw)
    return _make
