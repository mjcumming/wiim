"""Release preflight must only reuse a successful check of the same clean tree."""

import importlib.util
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "prepare_release.py"
SPEC = importlib.util.spec_from_file_location("prepare_release", SCRIPT)
assert SPEC and SPEC.loader
preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preflight)


class ReleasePreflightTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        self.repo = self.base / "repo"
        self.repo.mkdir()
        self.run_git("init", "-q")
        (self.repo / "candidate.txt").write_text("first\n", encoding="utf-8")
        self.commit()
        self.environment = mock.patch.dict(
            os.environ,
            {"LOCALAPPDATA": str(self.base / "cache"), "XDG_CACHE_HOME": str(self.base / "cache")},
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def run_git(self, *args):
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=Preflight Test",
                "-c",
                "user.email=preflight@example.invalid",
                "-c",
                "commit.gpgsign=false",
                "-c",
                f"core.hooksPath={self.base / 'no-hooks'}",
                "-C",
                str(self.repo),
                *args,
            ],
            check=True,
            capture_output=True,
        )

    def commit(self):
        self.run_git("add", "candidate.txt")
        self.run_git("commit", "-q", "-m", "candidate")

    def test_success_is_reused_only_for_the_same_tree(self):
        with mock.patch.object(preflight, "run_checks") as checks:
            self.assertTrue(preflight.prepare(self.repo))
            self.assertFalse(preflight.prepare(self.repo))
            self.assertEqual(checks.call_count, 1)

            (self.repo / "candidate.txt").write_text("second\n", encoding="utf-8")
            self.commit()
            self.assertTrue(preflight.prepare(self.repo))
            self.assertEqual(checks.call_count, 2)

    def test_dirty_and_untracked_changes_are_rejected(self):
        candidate = self.repo / "candidate.txt"
        with mock.patch.object(preflight, "run_checks") as checks:
            candidate.write_text("dirty\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "tracked or untracked"):
                preflight.prepare(self.repo)
            candidate.write_text("first\n", encoding="utf-8")
            (self.repo / "untracked.txt").write_text("untracked\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "tracked or untracked"):
                preflight.prepare(self.repo)
            checks.assert_not_called()

    def test_failure_and_failed_forced_rerun_are_not_cached(self):
        with mock.patch.object(preflight, "run_checks") as checks:
            checks.side_effect = RuntimeError("failed check")
            with self.assertRaisesRegex(RuntimeError, "failed check"):
                preflight.prepare(self.repo)
            checks.side_effect = None
            self.assertTrue(preflight.prepare(self.repo))
            self.assertFalse(preflight.prepare(self.repo))

            checks.side_effect = RuntimeError("failed forced check")
            with self.assertRaisesRegex(RuntimeError, "failed forced check"):
                preflight.prepare(self.repo, force=True)
            checks.side_effect = None
            self.assertTrue(preflight.prepare(self.repo))
            self.assertEqual(checks.call_count, 4)

    def test_changed_candidate_is_not_cached(self):
        original_tree = preflight.clean_tree(self.repo)

        def change_candidate(*_args):
            (self.repo / "candidate.txt").write_text("new tree\n", encoding="utf-8")
            self.commit()

        with mock.patch.object(preflight, "run_checks", side_effect=change_candidate):
            with self.assertRaisesRegex(RuntimeError, "candidate changed"):
                preflight.prepare(self.repo)
        self.assertFalse(preflight.cache_file(original_tree).exists())
        with mock.patch.object(preflight, "run_checks") as checks:
            self.assertTrue(preflight.prepare(self.repo))
            checks.assert_called_once()


if __name__ == "__main__":
    unittest.main()
