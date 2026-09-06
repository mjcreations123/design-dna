"""Real isolated runner regressions; these are not native remote CI evidence."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "maintainer" / "tests"))
import test_release_proofs as fixtures

RUNNER_SOURCE = REPO / "maintainer" / "scripts" / "run_release_tests.py"
LEGACY_STRING = (
    "import unittest\n"
    "def legacy_string(self):\n"
    "    kind = self.__class__\n"
    "    return '%s (%s.%s)' % (self._testMethodName, kind.__module__, kind.__qualname__)\n"
    "unittest.TestCase.__str__ = legacy_string\n"
)


class ReleaseTestIdentityTests(unittest.TestCase):
    def fixture(self, temporary):
        plugin = fixtures.make_attestation_fixture(Path(temporary).resolve())
        (plugin / "maintainer/scripts/run_release_tests.py").write_bytes(
            RUNNER_SOURCE.read_bytes()
        )
        return plugin

    def test_cli_does_not_publish_an_unwaived_skip_as_success(self):
        with tempfile.TemporaryDirectory(prefix="dna-unwaived-cli-") as temporary:
            plugin = self.fixture(temporary)
            (plugin / "skills/design-dna/tests/test_unwaived.py").write_text(
                "import unittest\n"
                "class Unwaived(unittest.TestCase):\n"
                "    @unittest.skip('actual unwaived skip')\n"
                "    def test_skipped(self):\n"
                "        pass\n",
                encoding="utf-8",
            )
            output = Path(temporary) / "attestation.json"
            diagnostic = Path(temporary) / "diagnostic.json"
            result = subprocess.run(
                [sys.executable, "-I", "-S", "-B",
                 str(plugin / "maintainer/scripts/attest_tests.py"),
                 "--plugin-root", str(plugin), "--output", str(output),
                 "--diagnostic-output", str(diagnostic)],
                cwd=plugin, capture_output=True, timeout=45, check=False,
            )
            self.assertEqual(2, result.returncode, result.stdout.decode(errors="replace"))
            self.assertFalse(output.exists())
            rejected = json.loads(diagnostic.read_bytes())
            self.assertEqual("test-skip-waiver-missing", rejected["failure_code"])
            self.assertFalse(rejected["release_eligible"])
            self.assertIn("actual unwaived skip", rejected["output"]["stderr"])

    def test_two_legacy_formatted_skips_keep_distinct_real_method_ids(self):
        with tempfile.TemporaryDirectory(prefix="dna-test-id-") as temporary:
            plugin = self.fixture(temporary)
            (plugin / "skills/design-dna/tests/test_legacy_identity.py").write_text(
                LEGACY_STRING
                + "class LegacySkips(unittest.TestCase):\n"
                "    @unittest.skip('first real skip')\n"
                "    def test_first(self):\n"
                "        '''A docstring cannot replace the identity.'''\n"
                "    @unittest.skip('second real skip')\n"
                "    def test_second(self):\n"
                "        pass\n",
                encoding="utf-8",
            )
            command = [sys.executable, *fixtures.attest_tests.UNITTEST_ARGUMENTS]
            actual = fixtures.attest_tests.run_exact_suite(plugin, command)
            parsed, _, stderr, _ = fixtures.attest_tests.parse_unittest_result(actual)
            expected = [
                "test_legacy_identity.LegacySkips.test_first",
                "test_legacy_identity.LegacySkips.test_second",
            ]
            self.assertEqual(2, parsed["skipped"])
            self.assertEqual(expected, parsed["skipped_test_ids"])
            for identity in expected:
                self.assertIn(f"({identity}) ... skipped", stderr)
            self.assertNotIn("A docstring cannot replace", stderr)
            # Parseable identities do not waive either actual skip.
            record = fixtures.attest_tests.create_attestation(
                plugin, runner=lambda _root, _command: actual
            )
            with self.assertRaises(fixtures.attest_tests.ToolFailure) as caught:
                fixtures.attest_tests.verify_skip_waiver_record(
                    plugin, record["skip_waiver"], record["inputs"], record["result"]
                )
            self.assertEqual("test-skip-waiver-missing", caught.exception.issue.code)

    def test_legacy_case_strings_cannot_hide_native_tracking_ids(self):
        with tempfile.TemporaryDirectory(prefix="dna-test-id-") as temporary:
            plugin = self.fixture(temporary)
            native_fixture = plugin / "maintainer/tests/test_maintainer_tools.py"
            native_fixture.write_text(
                LEGACY_STRING + native_fixture.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            record = fixtures.attest_tests.create_attestation(plugin)
            self.assertEqual("passed", record["result"]["status"])
            self.assertEqual(0, record["result"]["skipped"])
            expected = (
                list(fixtures.applicability.WINDOWS_NATIVE_TEST_IDS)
                if record["test_applicability"]["platform"] == "Windows"
                else []
            )
            self.assertEqual(
                sorted(expected),
                record["test_applicability"]["executed_native_test_ids"],
            )
            for identity in expected:
                self.assertIn(f"({identity}) ... ok", record["output"]["stderr"])

    def test_legacy_failure_keeps_its_real_identity_and_original_error(self):
        with tempfile.TemporaryDirectory(prefix="dna-test-id-") as temporary:
            plugin = self.fixture(temporary)
            (plugin / "skills/design-dna/tests/test_legacy_failure.py").write_text(
                LEGACY_STRING
                + "class LegacyFailure(unittest.TestCase):\n"
                "    def test_actual_failure(self):\n"
                "        self.fail('original failing assertion retained')\n",
                encoding="utf-8",
            )
            record = fixtures.attest_tests.create_attestation(plugin)
            self.assertEqual("failed", record["result"]["status"])
            self.assertEqual(1, record["result"]["failures"])
            self.assertIn(
                "(test_legacy_failure.LegacyFailure.test_actual_failure) ... FAIL",
                record["output"]["stderr"],
            )
            self.assertIn(
                "original failing assertion retained", record["output"]["stderr"]
            )

    def test_class_fixture_errors_remain_errors_not_invented_test_methods(self):
        with tempfile.TemporaryDirectory(prefix="dna-test-id-") as temporary:
            plugin = self.fixture(temporary)
            (plugin / "skills/design-dna/tests/test_setup_error.py").write_text(
                "import unittest\n"
                "class FixtureError(unittest.TestCase):\n"
                "    @classmethod\n"
                "    def setUpClass(cls):\n"
                "        raise RuntimeError('original class fixture failure')\n"
                "    def test_never_entered(self):\n"
                "        raise AssertionError('must not execute')\n",
                encoding="utf-8",
            )
            record = fixtures.attest_tests.create_attestation(plugin)
            self.assertEqual("failed", record["result"]["status"])
            self.assertEqual(1, record["result"]["errors"])
            self.assertIn("original class fixture failure", record["output"]["stderr"])
            self.assertNotIn("test_never_entered) ... ok", record["output"]["stderr"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
