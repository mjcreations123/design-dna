"""A failing suite retains diagnostics even when native applicability is unavailable."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import test_release_proofs as fixtures


class FailedDiagnosticAttestationTests(unittest.TestCase):
    def test_native_import_syntax_error_keeps_aggregate_and_failed_attestation(self):
        with tempfile.TemporaryDirectory(prefix="dna-failed-native-import-") as temporary:
            plugin = fixtures.make_attestation_fixture(Path(temporary).resolve())
            (plugin / "maintainer/tests/test_maintainer_tools.py").write_text("def native_import_syntax_error(\n", encoding="utf-8")
            (plugin / "skills/design-dna/tests/test_runtime_probe.py").write_text(
                "import unittest\nclass RuntimeProbe(unittest.TestCase):\n    def test_runtime_still_runs(self):\n        self.assertTrue(True)\n", encoding="utf-8")
            record = fixtures.attest_tests.create_attestation(plugin)
            self.assertEqual("failed", record["result"]["status"])
            self.assertEqual(2, record["result"]["tests_run"])
            self.assertEqual(1, record["result"]["errors"])
            self.assertIsNone(record["test_applicability"])
            self.assertIn("SyntaxError", record["output"]["stderr"])
            self.assertIn("native_import_syntax_error", record["output"]["stderr"])
            self.assertIn("Ran 2 tests", record["output"]["stderr"])
            self.assertIn("test_runtime_still_runs", record["output"]["stderr"])
            fixtures.attest_tests.validate_record(record, plugin / "maintainer/schemas/test-attestation.schema.json")
            fabricated_pass = copy.deepcopy(record)
            fabricated_pass["result"].update(status="passed", return_code=0, errors=0)
            with self.assertRaises(fixtures.attest_tests.ToolFailure):
                fixtures.attest_tests.validate_record(fabricated_pass, plugin / "maintainer/schemas/test-attestation.schema.json")

    def test_nested_captured_marker_in_real_failure_does_not_erase_diagnostics(self):
        with tempfile.TemporaryDirectory(prefix="dna-nested-failed-marker-") as temporary:
            plugin = fixtures.make_attestation_fixture(Path(temporary).resolve())
            captured = fixtures.applicability.MARKER + '{"captured_child_report":"not_the_parent_report"}'
            (plugin / "skills/design-dna/tests/test_nested_failure.py").write_text(
                "import unittest\nclass NestedFailure(unittest.TestCase):\n    def test_captured_child_failure(self):\n        self.fail(" + repr("Original child failure follows:\n" + captured) + ")\n", encoding="utf-8")
            record = fixtures.attest_tests.create_attestation(plugin)
            self.assertEqual("failed", record["result"]["status"])
            self.assertEqual(1, record["result"]["failures"])
            self.assertIsNone(record["test_applicability"])
            self.assertIn("Original child failure follows", record["output"]["stderr"])
            self.assertIn("captured_child_report", record["output"]["stderr"])
            fixtures.attest_tests.validate_record(record, plugin / "maintainer/schemas/test-attestation.schema.json")

    def test_passing_suite_without_one_trusted_applicability_marker_still_refuses(self):
        with tempfile.TemporaryDirectory(prefix="dna-missing-pass-marker-") as temporary:
            plugin = fixtures.make_attestation_fixture(Path(temporary).resolve())
            for marker_case in ("missing", "duplicate", "untrusted"):
                def runner(_root, command):
                    value = fixtures.fake_unittest_result(command)
                    if marker_case == "duplicate":
                        return subprocess.CompletedProcess(command, 0, value.stdout,
                            value.stderr + fixtures.applicability.MARKER.encode() + b'{}\n')
                    clean = b"\n".join(line for line in value.stderr.splitlines() if not line.startswith(fixtures.applicability.MARKER.encode()))
                    if marker_case == "untrusted":
                        clean += b"\n" + fixtures.applicability.MARKER.encode() + b'{}\n'
                    return subprocess.CompletedProcess(command, 0, value.stdout, clean)
                with self.subTest(marker_case=marker_case), self.assertRaises(fixtures.attest_tests.ToolFailure) as caught:
                    fixtures.attest_tests.create_attestation(plugin, runner=runner)
                self.assertEqual("test-applicability-invalid" if marker_case == "untrusted" else "test-applicability-missing", caught.exception.issue.code)


if __name__ == "__main__":
    unittest.main()
