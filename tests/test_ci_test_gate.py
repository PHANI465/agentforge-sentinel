"""C06 review R25: the CI test gate must fail on any unexpected skip, on a run without
required executed tests, on failures/collection errors, and on a missing or malformed
result report. It passes only when every required test ran and passed and exactly the
opt-in live Claude test was skipped.

The harness runs the workflow's actual "Tests" step script verbatim under bash (GitHub's
`bash -eo pipefail`), with a `uv` shim that maps `uv run ... python ARGS` to this
interpreter, against small throwaway suites with genuinely skipped/failed tests."""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "backend.yml"
LIVE_TEST = '''import os

import pytest


@pytest.mark.skipif(os.environ.get("SENTINEL_LIVE_CLAUDE") != "1",
                    reason="live Claude smoke test uses subscription quota; set "
                           "SENTINEL_LIVE_CLAUDE=1 to run")
def test_live_claude_cli_smoke():
    raise AssertionError("must not run in CI")
'''
SHIM = '''#!/usr/bin/env bash
# Test shim: "uv run [--locked] [--extra X]... python ARGS" -> this interpreter with ARGS.
[ "$1" = run ] || { echo "uv shim: unsupported command $1" >&2; exit 97; }
shift
while [ $# -gt 0 ] && [ "$1" != python ]; do shift; done
[ "$1" = python ] || { echo "uv shim: no python" >&2; exit 97; }
shift
exec "$REAL_PYTHON" "$@"
'''


def bash() -> str:
    """Git for Windows' bash (never WSL's System32 bash.exe); /bin/bash elsewhere."""
    if os.name != "nt":
        return "/bin/bash"
    git = shutil.which("git")
    assert git, "git is required"
    for parent in Path(git).resolve().parents:
        candidate = parent / "bin" / "bash.exe"
        if candidate.is_file():
            return str(candidate)
    raise AssertionError("Git for Windows bash not found")


def step_script(name_prefix: str) -> str:
    """The `run: |` block of the workflow step whose name starts with name_prefix."""
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if re.match(rf"\s*- name: {re.escape(name_prefix)}", line):
            for j in range(i + 1, len(lines)):
                if lines[j].strip() == "run: |":
                    indent = len(lines[j + 1]) - len(lines[j + 1].lstrip())
                    block = []
                    for body in lines[j + 1:]:
                        if body.strip() and len(body) - len(body.lstrip()) < indent:
                            break
                        block.append(body[indent:])
                    return "\n".join(block) + "\n"
                if lines[j].strip().startswith("run:"):
                    return lines[j].split("run:", 1)[1].strip() + "\n"
    raise AssertionError(f"workflow step {name_prefix!r} not found")


def suite(tmp_path: Path, files: dict[str, str]) -> Path:
    project = tmp_path / "project"
    (project / "tests").mkdir(parents=True)
    for name, body in files.items():
        (project / "tests" / name).write_text(body, encoding="utf-8")
    scripts = ROOT / "scripts"
    for helper in ("ci_test_gate.py",):  # the gate the workflow calls, if it exists
        if (scripts / helper).exists():
            (project / "scripts").mkdir(exist_ok=True)
            shutil.copy2(scripts / helper, project / "scripts" / helper)
    shim_dir = tmp_path / "shim"
    shim_dir.mkdir()
    (shim_dir / "uv").write_bytes(SHIM.encode())
    (shim_dir / "uv").chmod(0o755)
    return project


def run_gate(tmp_path: Path, files: dict[str, str]) -> subprocess.CompletedProcess:
    project = suite(tmp_path, files)
    script = tmp_path / "step.sh"
    script.write_bytes(step_script("Tests").encode())
    env = {**os.environ, "SENTINEL_LIVE_CLAUDE": "0", "REAL_PYTHON": Path(
        sys.executable).as_posix(), "PATH": f"{(tmp_path / 'shim').as_posix()}{os.pathsep}"
           f"{os.environ.get('PATH', '')}"}
    if os.name == "nt":  # bash's PATH separator is ':' with POSIX-style directories
        env["PATH"] = f"/{(tmp_path / 'shim').as_posix().replace(':', '', 1)}:" \
                      + os.environ.get("PATH", "").replace("\\", "/")
    env.pop("PYTEST_ADDOPTS", None)
    env.pop("PYTEST_CURRENT_TEST", None)
    return subprocess.run([bash(), "--noprofile", "--norc", "-eo", "pipefail", str(script)],
                          cwd=project, env=env, capture_output=True, text=True, timeout=300)


PASSING = "def test_required():\n    assert True\n"
SKIPPED = ("import pytest\n\n\n@pytest.mark.skip(reason='database prerequisite missing')\n"
           "def test_required():\n    assert True\n")
XFAIL = ("import pytest\n\n\n@pytest.mark.xfail(reason='known broken')\n"
         "def test_required():\n    assert False\n")
FAILING = "def test_required():\n    assert 1 == 2\n"
BROKEN = "def test_required(:\n"


def test_healthy_run_passes(tmp_path):
    done = run_gate(tmp_path, {"test_investigators.py": LIVE_TEST, "test_db.py": PASSING})
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-1500:]


@pytest.mark.parametrize("required", [SKIPPED, XFAIL], ids=["skip", "xfail"])
def test_an_extra_skipped_required_test_fails(tmp_path, required):
    done = run_gate(tmp_path, {"test_investigators.py": LIVE_TEST, "test_db.py": required})
    assert done.returncode != 0, "a skipped required test passed the gate"


def test_a_run_without_required_executed_tests_fails(tmp_path):
    done = run_gate(tmp_path, {"test_investigators.py": LIVE_TEST})
    assert done.returncode != 0, "a run that only skipped the live test passed the gate"


def test_a_failing_test_fails(tmp_path):
    done = run_gate(tmp_path, {"test_investigators.py": LIVE_TEST, "test_db.py": FAILING})
    assert done.returncode != 0


def test_a_collection_error_fails(tmp_path):
    done = run_gate(tmp_path, {"test_investigators.py": LIVE_TEST, "test_db.py": PASSING,
                               "test_broken.py": BROKEN})
    assert done.returncode != 0


def test_a_missing_live_skip_fails(tmp_path):
    done = run_gate(tmp_path, {"test_db.py": PASSING})
    assert done.returncode != 0


# ---- the result validator and exit-code preservation (new mechanism; no old analogue) -----

sys.path.insert(0, str(ROOT / "scripts"))
import ci_test_gate  # noqa: E402

ALLOWED = ('<testcase classname="tests.test_investigators" name="test_live_claude_cli_smoke">'
           '<skipped type="pytest.skip" message="live Claude smoke test uses subscription '
           'quota; set SENTINEL_LIVE_CLAUDE=1 to run"/></testcase>')
GOOD = '<testcase classname="tests.test_db" name="test_required"/>'


def report(tmp_path, body, tests=2, skipped=1, failures=0, errors=0):
    path = tmp_path / "r.xml"
    path.write_text(f'<?xml version="1.0"?><testsuites><testsuite name="pytest" tests="{tests}"'
                    f' skipped="{skipped}" failures="{failures}" errors="{errors}">{body}'
                    '</testsuite></testsuites>', encoding="utf-8")
    return path


def test_validator_accepts_exactly_the_healthy_report(tmp_path):
    assert ci_test_gate.validate(report(tmp_path, ALLOWED + GOOD)) == []


@pytest.mark.parametrize("make, expected", [
    (lambda t: t / "absent.xml", "missing"),
    (lambda t: (t / "bad.xml").write_text("<testsuites><testsuite", encoding="utf-8")
     and t / "bad.xml", "malformed"),
    (lambda t: report(t, ALLOWED + GOOD, tests=3), "disagree"),  # truncated report
    (lambda t: report(t, ALLOWED.replace("live Claude smoke test uses subscription quota",
                                         "something else") + GOOD), "unexpected reason"),
    (lambda t: report(t, ALLOWED, tests=1), "no required test"),
])
def test_validator_rejects_bad_reports(tmp_path, make, expected):
    problems = ci_test_gate.validate(make(tmp_path))
    assert problems and any(expected in p for p in problems), problems


@pytest.mark.parametrize("files, code", [
    ({"test_investigators.py": LIVE_TEST, "test_db.py": FAILING}, 1),
    ({"test_investigators.py": LIVE_TEST, "test_db.py": PASSING, "test_broken.py": BROKEN}, 2),
    ({"test_investigators.py": LIVE_TEST, "test_db.py": SKIPPED}, ci_test_gate.VALIDATION_FAILED),
])
def test_the_gate_preserves_pytest_exit_codes(tmp_path, files, code):
    assert run_gate(tmp_path, files).returncode == code


def test_a_stale_report_is_never_validated(tmp_path):
    project = suite(tmp_path, {"test_db.py": BROKEN})
    stale = project / "pytest-results.xml"
    stale.write_text(report(tmp_path, ALLOWED + GOOD).read_text(encoding="utf-8"),
                     encoding="utf-8")
    done = subprocess.run([sys.executable, "scripts/ci_test_gate.py", "--junit", stale.name],
                          cwd=project, capture_output=True, text=True, timeout=300,
                          env={**os.environ, "SENTINEL_LIVE_CLAUDE": "0"})
    assert done.returncode == 2  # pytest's collection error, not the stale healthy report
