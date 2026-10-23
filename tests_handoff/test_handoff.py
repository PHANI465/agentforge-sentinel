"""Regression tests: temporary repositories, isolated Git config, no network/hooks."""
from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SOURCE_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SOURCE_SCRIPTS))
import agent_check
import agent_common
import agent_status


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="handoff-regression-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repo"
        self.root.mkdir()
        template = Path(self.temp.name) / "empty-template"
        template.mkdir()
        self.env_patch = mock.patch.dict(os.environ, {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TEMPLATE_DIR": str(template),
            "GIT_TERMINAL_PROMPT": "0",
            "PYTHONDONTWRITEBYTECODE": "1",
            "AGENT_STATUS_GH": "0",
        })
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_CONFIG_COUNT",
                     "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES"):
            os.environ.pop(name, None)
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Handoff Regression")
        self.git("config", "user.email", "handoff-regression@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "core.hooksPath", str(template))
        (self.root / ".gitignore").write_text(".agent/\n__pycache__/\n", encoding="utf-8")
        (self.root / "tracked.txt").write_text("initial\n", encoding="utf-8")
        shutil.copytree(SOURCE_SCRIPTS, self.root / "scripts",
                        ignore=shutil.ignore_patterns("__pycache__"))
        self.git("add", ".gitignore", "tracked.txt", "scripts")
        self.git("commit", "-m", "test fixture")
        self.head = self.git("rev-parse", "HEAD")

    def git(self, *args):
        proc = subprocess.run(["git", *args], cwd=self.root, capture_output=True,
                              text=True, encoding="utf-8", errors="replace", check=True)
        return proc.stdout.strip()

    def run_check(self, code="pass", timeout=5, checks=None):
        checks = [[sys.executable, "-B", "-c", code]] if checks is None else checks
        with contextlib.redirect_stdout(io.StringIO()):
            result = agent_check.run_checks(self.root, checks, timeout)
        report = json.loads((self.root / agent_common.CHECK_FILE).read_text(encoding="utf-8"))
        return result, report

    def save_report(self, report):
        (self.root / agent_common.CHECK_FILE).write_text(json.dumps(report), encoding="utf-8")

    def cli(self, *args):
        return subprocess.run([sys.executable, "-B", str(self.root / "scripts/agent_status.py"), *args],
                              cwd=self.temp.name, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", check=True)

    def test_success_records_full_equal_clean_snapshot(self):
        result, report = self.run_check()
        self.assertEqual(result, 0)
        self.assertTrue(agent_common.valid_success(report))
        self.assertEqual(report["commit"], self.head)
        self.assertEqual(report["before"], report["after"])
        self.assertFalse(report["after"]["dirty"])
        self.assertIn("PASSED", agent_status.check_state(self.root, self.head, False, "main"))

    def test_empty_checks_invalidate_old_success(self):
        self.run_check()
        result, report = self.run_check(checks=[])
        self.assertNotEqual(result, 0)
        self.assertEqual(report["state"], "not_configured")
        self.assertFalse(agent_common.valid_success(report))
        self.assertIn("NOT CONFIGURED", agent_status.check_state(self.root, self.head, False))

    def test_project_configuration_uses_explicit_argv_commands(self):
        self.assertTrue(agent_check.CHECKS)
        self.assertTrue(agent_check.valid_checks(
            agent_check.CHECKS, agent_check.CHECK_TIMEOUT_SECONDS))
        self.assertGreater(agent_check.CHECK_TIMEOUT_SECONDS, 0)

    def test_dirty_start_does_not_execute_commands(self):
        (self.root / "tracked.txt").write_text("dirty", encoding="utf-8")
        result, report = self.run_check("from pathlib import Path; Path('.agent/executed').touch()")
        self.assertNotEqual(result, 0)
        self.assertEqual(report["state"], "dirty")
        self.assertEqual(report["results"], [])
        self.assertFalse((self.root / ".agent/executed").exists())

    def test_untracked_source_is_dirty(self):
        (self.root / "untracked.py").write_text("pass\n", encoding="utf-8")
        self.assertEqual(self.run_check()[1]["state"], "dirty")

    def test_tree_change_during_check_cannot_pass(self):
        result, report = self.run_check("from pathlib import Path; Path('tracked.txt').write_text('changed')")
        self.assertNotEqual(result, 0)
        self.assertEqual(report["state"], "changed")
        self.assertEqual(report["before"]["commit"], report["after"]["commit"])
        self.assertTrue(report["after"]["dirty"])

    def test_new_commit_during_check_cannot_pass_even_when_clean(self):
        code = ("from pathlib import Path; import subprocess; "
                "Path('tracked.txt').write_text('changed'); "
                "subprocess.run(['git','add','tracked.txt'],check=True); "
                "subprocess.run(['git','commit','-m','inside check'],check=True,stdout=subprocess.DEVNULL)")
        result, report = self.run_check(code)
        self.assertNotEqual(result, 0)
        self.assertEqual(report["state"], "changed")
        self.assertNotEqual(report["before"]["commit"], report["after"]["commit"])
        self.assertNotEqual(report["before"]["tree"], report["after"]["tree"])
        self.assertFalse(report["after"]["dirty"])

    def test_branch_switch_same_commit_invalidates_check(self):
        result, report = self.run_check(
            "import subprocess; subprocess.run(['git','switch','-c','task/other'],check=True,"
            "stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)")
        self.assertNotEqual(result, 0)
        self.assertEqual(report["state"], "changed")
        self.assertEqual(report["before"]["commit"], report["after"]["commit"])
        self.assertNotEqual(report["before"]["branch"], report["after"]["branch"])

    def test_running_marker_replaces_old_pass_before_execution(self):
        self.run_check()
        code = ("import json; from pathlib import Path; "
                "r=json.loads(Path('.agent/last-check.json').read_text()); "
                "assert r['state']=='running' and r['passed'] is False")
        self.assertEqual(self.run_check(code)[0], 0)

    def test_output_and_arguments_are_not_persisted(self):
        token = "DUMMY_NOT_A_REAL_SECRET_573819"
        _, report = self.run_check(f"print({token!r})")
        serialized = json.dumps(report)
        self.assertNotIn(token, serialized)
        self.assertNotIn("stdout", serialized)
        self.assertNotIn("stderr", serialized)
        self.assertNotIn("argv", serialized)
        self.assertNotIn("tail", serialized)

    def test_timeout_and_missing_command_are_not_success(self):
        result, report = self.run_check("import time; time.sleep(30)", timeout=0.05)
        self.assertNotEqual(result, 0)
        self.assertEqual(report["results"][0]["state"], "timeout")
        result, report = self.run_check(checks=[["definitely-no-such-handoff-command"]])
        self.assertNotEqual(result, 0)
        self.assertEqual(report["results"][0]["state"], "launch_error")

    def test_nonzero_exit_and_bad_configuration(self):
        result, report = self.run_check("raise SystemExit(7)")
        self.assertNotEqual(result, 0)
        self.assertEqual(report["results"][0]["exit"], 7)
        result, report = self.run_check(checks=["echo unsafe shell syntax"])
        self.assertNotEqual(result, 0)
        self.assertEqual(report["state"], "invalid_configuration")

    def test_git_failure_is_not_treated_as_clean(self):
        with mock.patch.object(agent_check, "snapshot", side_effect=agent_common.GitError("fixture")):
            result, report = self.run_check()
        self.assertNotEqual(result, 0)
        self.assertEqual(report["state"], "git_error")
        self.assertNotIn("PASSED", agent_status.check_state(self.root, self.head, False))

    def test_full_hash_comparison_not_nine_character_prefix(self):
        _, report = self.run_check()
        fake = self.head[:9] + ("a" if self.head[9] != "a" else "b") + self.head[10:]
        report["commit"] = fake
        report["before"]["commit"] = fake
        report["after"]["commit"] = fake
        self.save_report(report)
        self.assertTrue(agent_common.valid_success(report))
        self.assertIn("STALE", agent_status.check_state(self.root, self.head, False))

    def test_empty_or_malformed_evidence_never_says_passed(self):
        _, good = self.run_check()
        variants = [[], {"passed": True, "commit": self.head, "results": []}]
        empty = copy.deepcopy(good)
        empty.update(results=[], check_count=0)
        variants.append(empty)
        wrong_type = copy.deepcopy(good)
        wrong_type["results"][0]["exit"] = False
        variants.append(wrong_type)
        dirty = copy.deepcopy(good)
        dirty["before"]["dirty"] = True
        dirty["after"]["dirty"] = True
        variants.append(dirty)
        for bad in variants:
            with self.subTest(report=bad):
                self.save_report(bad)
                self.assertNotIn("PASSED", agent_status.check_state(self.root, self.head, False))

    def test_changed_current_tree_or_branch_makes_prior_report_stale(self):
        self.run_check()
        self.assertIn("STALE", agent_status.check_state(self.root, self.head, True))
        self.assertIn("STALE", agent_status.check_state(self.root, self.head, False, "other"))

    def test_branch_slash_and_collision_safe_windows_names(self):
        self.git("update-ref", "refs/remotes/origin/release/stable", self.head)
        self.git("symbolic-ref", "refs/remotes/origin/HEAD",
                 "refs/remotes/origin/release/stable")
        self.assertEqual(agent_status.default_branch(self.root), "release/stable")
        names = [agent_common.note_name(x) for x in
                 ("feat/x", "feat__x", "feat/X", "CON", "unicode/\u03bb")]
        self.assertEqual(len(set(n.casefold() for n in names)), len(names))
        self.assertTrue(all(n.startswith("branch-") for n in names))
        self.assertTrue(all(not any(c in n for c in '/\\:*?"<>|') for n in names))

    def test_status_cli_json_and_note_path_from_other_cwd(self):
        report = json.loads(self.cli("--cursor-json").stdout)
        self.assertIn("=== STATUS BRIEFING", report["additional_context"])
        self.assertIn("NOT VERIFIED", report["additional_context"])
        expected = f"docs/handoff/{agent_common.note_name('main')}"
        self.assertEqual(self.cli("--note-path").stdout.strip(), expected)
        explicit = f"docs/handoff/{agent_common.note_name('feat/x')}"
        self.assertEqual(self.cli("--note-path", "feat/x").stdout.strip(), explicit)

    def test_full_output_really_includes_full_note(self):
        notes = self.root / "docs/handoff"
        notes.mkdir(parents=True)
        text = "line\n" * 3000 + "UNIQUE_END_OF_HANDOFF"
        (notes / agent_common.note_name("main")).write_text(text, encoding="utf-8")
        self.assertNotIn("UNIQUE_END_OF_HANDOFF", agent_status.briefing(self.root))
        self.assertIn("UNIQUE_END_OF_HANDOFF", agent_status.briefing(self.root, full=True))
        self.assertGreater(len(agent_status.briefing(self.root, full=True)), 9000)

    def test_network_is_off_without_explicit_opt_in(self):
        with mock.patch.dict(os.environ, {"AGENT_STATUS_GH": "0"}):
            with mock.patch.object(agent_status.subprocess, "run") as run:
                self.assertEqual(agent_status.github_issues(self.root), "")
                run.assert_not_called()

    def test_other_branch_notes_support_current_and_legacy_next_heading(self):
        for heading, branch, token in (("Next action", "task/current", "CURRENT_NEXT_ACTION"),
                                       ("Next step", "task/legacy", "LEGACY_NEXT_STEP")):
            self.git("switch", "-c", branch)
            notes = self.root / "docs/handoff"
            notes.mkdir(parents=True, exist_ok=True)
            relative = f"docs/handoff/{agent_common.note_name(branch)}"
            (self.root / relative).write_text(
                f"- State: in progress\n\n## {heading}\n\n{token}\n", encoding="utf-8")
            self.git("add", relative)
            self.git("commit", "-m", "isolated handoff fixture")
            self.git("switch", "main")
        briefing = agent_status.briefing(self.root)
        self.assertIn("CURRENT_NEXT_ACTION", briefing)
        self.assertIn("LEGACY_NEXT_STEP", briefing)


if __name__ == "__main__":
    unittest.main()
