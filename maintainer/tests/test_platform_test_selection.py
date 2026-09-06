"""Platform selection is recorded as non-applicability, never fake native passes."""
import copy
import io
import json
from pathlib import Path
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import test_platform_applicability as policy


class PlatformSelectionTests(unittest.TestCase):
    def run_fixture(self, system, *, ordinary_skip=False):
        executed = []
        class Probe(unittest.TestCase):
            def __init__(self, identity):
                super().__init__("runTest")
                self.identity = identity
            def id(self):
                return self.identity
            def __str__(self):
                return self.identity.rsplit(".", 1)[1] + " (" + self.identity + ")"
            def runTest(self):
                executed.append(self.id())
                if ordinary_skip and self.id() == "fixture.Ordinary.test_case":
                    self.skipTest("An ordinary skip must remain a recorded skip.")
        class Tracking(unittest.TextTestResult):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.native_executed = set()
            def startTest(self, test):
                if test.id() in policy.WINDOWS_NATIVE_TEST_IDS:
                    self.native_executed.add(test.id())
                super().startTest(test)
        suite = unittest.TestSuite([Probe(identity) for identity in [*policy.WINDOWS_NATIVE_TEST_IDS, "fixture.Ordinary.test_case"]])
        selected, discovered, excluded = policy.select_suite(suite, system)
        output = io.StringIO()
        result = unittest.TextTestRunner(stream=output, verbosity=2, descriptions=False, resultclass=Tracking).run(selected)
        report = policy.make_report(system, discovered, excluded, [result])
        stderr = output.getvalue() + policy.MARKER + json.dumps(report) + "\n"
        return executed, result, report, stderr

    def test_linux_and_macos_do_not_execute_or_skip_windows_native_probes(self):
        for system in ("Linux", "Darwin"):
            with self.subTest(system=system):
                executed, result, report, stderr = self.run_fixture(system)
                self.assertEqual(["fixture.Ordinary.test_case"], executed)
                self.assertEqual([], result.skipped)
                self.assertEqual(list(policy.WINDOWS_NATIVE_TEST_IDS), report["not_applicable_test_ids"])
                self.assertEqual([], policy.validate_test_applicability(report, expected_platform=system, tests_run=result.testsRun, passed=True, stderr=stderr))

    def test_windows_selects_and_executes_every_native_probe(self):
        executed, result, report, stderr = self.run_fixture("Windows")
        self.assertEqual(5, len(executed))
        self.assertEqual([], report["not_applicable_test_ids"])
        self.assertEqual(list(policy.WINDOWS_NATIVE_TEST_IDS), report["executed_native_test_ids"])
        self.assertEqual([], policy.validate_test_applicability(report, expected_platform="Windows", tests_run=result.testsRun, passed=True, stderr=stderr))

    def test_ordinary_skip_is_not_reclassified_or_erased(self):
        _executed, result, report, _stderr = self.run_fixture("Linux", ordinary_skip=True)
        self.assertEqual(1, len(result.skipped))
        self.assertEqual("fixture.Ordinary.test_case", result.skipped[0][0].id())
        self.assertNotIn("fixture.Ordinary.test_case", report["not_applicable_test_ids"])

    def test_missing_native_discovery_unknown_platform_and_forged_report_are_rejected(self):
        with self.assertRaises(ValueError):
            policy.select_suite(unittest.TestSuite(), "UnknownOS")
        with self.assertRaisesRegex(ValueError, "exactly once"):
            policy.make_report("Windows", [], [], [])
        _executed, result, report, stderr = self.run_fixture("Windows")
        for mutation in ("native", "platform", "policy", "count"):
            broken = copy.deepcopy(report)
            if mutation == "native": broken["executed_native_test_ids"].pop()
            elif mutation == "platform": broken["platform"] = "Linux"
            elif mutation == "policy": broken["policy_sha256"] = "0" * 64
            else: broken["selected_tests"] += 1
            with self.subTest(mutation=mutation):
                self.assertTrue(policy.validate_test_applicability(broken, expected_platform="Windows", tests_run=result.testsRun, passed=True, stderr=stderr))
        with self.assertRaisesRegex(ValueError, "exactly one"):
            policy.extract_report("", stderr + policy.MARKER + json.dumps(report) + "\n")


if __name__ == "__main__":
    unittest.main()
