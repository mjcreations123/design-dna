"""Owned allocator aliases do not relax caller-supplied path safety."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "maintainer/tests"))
import test_release_proofs as fixtures
from directory_link_fixtures import make_directory_link, remove_directory_link


class ReleaseTemporaryPathTests(unittest.TestCase):
    def test_real_runner_allocates_under_the_canonical_owned_temp_root(self):
        with tempfile.TemporaryDirectory(prefix="dna-temp-root-") as temporary:
            base = Path(temporary).resolve()
            actual = base / "actual-temp"
            actual.mkdir()
            alias = base / "temp-alias"
            make_directory_link(alias, actual)
            try:
                source = (
                    "import tempfile, unittest\nfrom pathlib import Path\n"
                    "class TempRoot(unittest.TestCase):\n"
                    "    def test_owned_temp_is_canonical(self):\n"
                    "        with tempfile.TemporaryDirectory() as created:\n"
                    f"            self.assertEqual(Path(created).parent, Path({str(actual)!r}))\n"
                    "            self.assertEqual(Path(created), Path(created).resolve())\n"
                )
                plugin = fixtures.make_release_runner_fixture(base / "fixture", source)
                result = fixtures.run_release_runner(
                    plugin,
                    environment_overrides={key: str(alias) for key in ("TMPDIR", "TMP", "TEMP")},
                )
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                self.assertIn("test_owned_temp_is_canonical", result.stderr)
            finally:
                remove_directory_link(alias)

    def test_explicit_project_alias_still_fails_without_writing_state(self):
        with tempfile.TemporaryDirectory(prefix="dna-project-alias-") as temporary:
            base = Path(temporary).resolve()
            actual = base / "actual-project"
            actual.mkdir()
            alias = base / "project-alias"
            make_directory_link(alias, actual)
            try:
                result = subprocess.run(
                    [sys.executable, "-B", str(ROOT / "skills/design-dna/scripts/init_project_state.py"),
                     "--project", str(alias), "--profile", "standard", "--json"],
                    capture_output=True, text=True, encoding="utf-8", timeout=30, check=False,
                )
                self.assertEqual(2, result.returncode, result.stdout + result.stderr)
                self.assertIn("reparse-point-refused", result.stdout + result.stderr)
                self.assertFalse((actual / ".design-dna").exists())
            finally:
                remove_directory_link(alias)


if __name__ == "__main__":
    unittest.main(verbosity=2)
