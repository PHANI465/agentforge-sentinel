"""CI test gate (C06, review R25): run pytest with a JUnit report and accept the run only if

- pytest itself exited 0 (its nonzero code is returned unchanged: failures, collection
  errors, interrupted or empty runs);
- the report exists, parses, and its per-suite totals agree with its test cases;
- no test failed or errored, and at least one required test was executed and passed;
- the skipped set is exactly ALLOWED_SKIPS (node id and reason), so any other skip or
  xfail, or a missing expected skip, fails the gate.

    uv run --locked python scripts/ci_test_gate.py [--junit PATH] [-- PYTEST_ARGS...]
    uv run --locked python scripts/ci_test_gate.py --validate-only PATH
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# The only test CI may skip: the opt-in live Claude smoke test (it needs a subscription
# login and quota). Keyed by JUnit classname::name; the value must start the skip message.
ALLOWED_SKIPS = {
    "tests.test_investigators::test_live_claude_cli_smoke":
        "live Claude smoke test uses subscription quota",
}
VALIDATION_FAILED = 3  # distinct from pytest's own codes 1, 2, 4 and 5


def validate(report: Path, allowed: dict[str, str] = ALLOWED_SKIPS) -> list[str]:
    try:
        root = ET.parse(report).getroot()
    except FileNotFoundError:
        return [f"result report {report} is missing"]
    except (ET.ParseError, OSError) as error:
        return [f"result report {report} is malformed: {type(error).__name__}"]
    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
    if root.tag not in ("testsuite", "testsuites") or not suites:
        return ["result report has no test suite"]
    problems, passed, skipped = [], 0, {}
    for suite in suites:
        cases = suite.findall("testcase")
        counts = {"failures": 0, "errors": 0, "skipped": 0}
        for case in cases:
            node = f"{case.get('classname', '')}::{case.get('name', '')}"
            failed = case.find("failure") is not None or case.find("error") is not None
            skip = case.find("skipped")
            if case.find("failure") is not None:
                counts["failures"] += 1
            if case.find("error") is not None:
                counts["errors"] += 1
            if failed:
                problems.append(f"failed: {node}")
            elif skip is not None:
                counts["skipped"] += 1
                skipped[node] = skip.get("message", "") or (skip.text or "")
            else:
                passed += 1
        try:
            declared = {k: int(suite.get(k, "0")) for k in ("tests", "failures", "errors",
                                                             "skipped")}
        except ValueError:
            return ["result report totals are not integers"]
        if declared["tests"] != len(cases) or any(declared[k] != counts[k] for k in counts):
            problems.append(f"result report totals {declared} disagree with its "
                            f"{len(cases)} test cases {counts}")
    for node, message in sorted(skipped.items()):
        reason = allowed.get(node)
        if reason is None:
            problems.append(f"unexpected skip: {node} ({message[:120]})")
        elif reason not in message:
            problems.append(f"allowed skip {node} has an unexpected reason ({message[:120]})")
    for node in sorted(set(allowed) - set(skipped)):
        problems.append(f"expected skip missing (not collected or ran): {node}")
    if passed == 0:
        problems.append("no required test was executed and passed")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--junit", type=Path, default=Path("pytest-results.xml"))
    parser.add_argument("--validate-only", type=Path, metavar="PATH")
    parser.add_argument("pytest_args", nargs="*")
    args = parser.parse_args(argv)
    if args.validate_only is not None:
        problems = validate(args.validate_only)
        for problem in problems:
            print(f"test gate: {problem}")
        return VALIDATION_FAILED if problems else 0
    args.junit.unlink(missing_ok=True)  # never validate a stale report
    code = subprocess.run([sys.executable, "-m", "pytest", "-q", "-rs",
                           f"--junitxml={args.junit}", *args.pytest_args]).returncode
    problems = validate(args.junit)
    for problem in problems:
        print(f"test gate: {problem}")
    if code != 0:
        print(f"test gate: pytest exited {code}")
        return code
    if problems:
        return VALIDATION_FAILED
    print("test gate: passed (all required tests ran and passed; only the allowed skip)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
