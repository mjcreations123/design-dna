"""Real completed-process rejection diagnostics; fixtures are not release proof."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import attest_tests
from test_run_diagnostics import TestRunCapture
import test_release_proofs as fixtures
from directory_link_fixtures import make_directory_link, remove_directory_link


class PostRunDiagnosticsTests(unittest.TestCase):
    def fixture(self, temporary):
        return fixtures.make_attestation_fixture(Path(temporary).resolve())

    def run_cli(self, plugin, output, diagnostic, *, extra_environment=None):
        environment = dict(os.environ)
        environment.update(extra_environment or {})
        command = [sys.executable, "-I", "-S", "-B",
            str(plugin / "maintainer/scripts/attest_tests.py"),
            "--plugin-root", str(plugin), "--output", str(output)]
        if diagnostic is not None:
            command.extend(("--diagnostic-output", str(diagnostic)))
        return subprocess.run(command, cwd=plugin, env=environment,
            capture_output=True, timeout=45, check=False)

    def assert_diagnostic(self, result, output, diagnostic, expected_code):
        self.assertEqual(2, result.returncode, result.stdout.decode(errors="replace") + result.stderr.decode(errors="replace"))
        self.assertFalse(output.exists())
        self.assertTrue(diagnostic.is_file(), result.stdout.decode(errors="replace"))
        payload = json.loads(diagnostic.read_bytes())
        self.assertEqual("design-dna-test-rejection-diagnostic", payload["record_type"])
        self.assertEqual(expected_code, payload["failure_code"])
        self.assertFalse(payload["release_eligible"])
        self.assertFalse(payload["attestation_validated"])
        self.assertIsNone(payload["tests_run"])
        self.assertIn("tests_sha256", payload["source_inputs_before"])
        self.assertTrue(payload["dependencies_before"])
        streams = payload["output"]
        exact = ("stdout\0" + streams["stdout"] + "\0stderr\0" + streams["stderr"]).encode()
        self.assertEqual(hashlib.sha256(exact).hexdigest(), streams["sha256"])
        self.assertEqual(len(streams["stdout"].encode()), streams["stdout_bytes"])
        self.assertEqual(len(streams["stderr"].encode()), streams["stderr_bytes"])
        return payload

    def test_completed_malformed_skip_summary_retains_both_redacted_streams(self):
        with tempfile.TemporaryDirectory(prefix="dna-postrun-") as temporary:
            plugin = self.fixture(temporary)
            output = Path(temporary) / "attestation.json"
            diagnostic = Path(temporary) / "diagnostic.json"
            # A real child exits normally with a deliberately unparseable
            # synthetic release-runner transcript. No successful test claim.
            (plugin / "maintainer/scripts/run_release_tests.py").write_text(
                "import os,sys\n"
                "print('stdout marker: '+os.getcwd(), flush=True)\n"
                "print(os.environ['DIAGNOSTIC_TEST_TOKEN'], flush=True)\n"
                "print('Unowned file: \\\"/unowned/private/location.py\\\"', flush=True)\n"
                "print('Authorization: Bearer never-upload-this-credential', flush=True)\n"
                "print('stderr marker before malformed summary', file=sys.stderr, flush=True)\n"
                "print('Ran 1 test in 0.1s\\n\\nOK (skipped=1)', file=sys.stderr, flush=True)\n",
                encoding="utf-8")
            secret = "retained-diagnostic-secret-792da5"
            result = self.run_cli(plugin, output, diagnostic,
                extra_environment={"DIAGNOSTIC_TEST_TOKEN": secret})
            payload = self.assert_diagnostic(result, output, diagnostic, "test-attestation-skip-identity-incomplete")
            self.assertTrue(payload["execution_completed"])
            self.assertIn("stdout marker:", payload["output"]["stdout"])
            self.assertIn("stderr marker before malformed summary", payload["output"]["stderr"])
            self.assertIn("OK (skipped=1)", payload["output"]["stderr"])
            exported = diagnostic.read_text()
            self.assertNotIn(str(plugin), exported)
            self.assertNotIn(secret, exported + result.stdout.decode())
            self.assertNotIn("/unowned/private/location.py", exported)
            self.assertNotIn("never-upload-this-credential", exported)
            self.assertIn("<REDACTED_SECRET>", exported)
            with self.assertRaises(attest_tests.ToolFailure):
                attest_tests.validate_record(payload, plugin / "maintainer/schemas/test-attestation.schema.json")

    def test_actual_completed_suite_with_ambiguous_applicability_keeps_original_output(self):
        with tempfile.TemporaryDirectory(prefix="dna-postrun-") as temporary:
            plugin = self.fixture(temporary)
            (plugin / "skills/design-dna/tests/test_ambiguous.py").write_text(
                "import unittest\nclass Ambiguous(unittest.TestCase):\n"
                " def test_real_success(self):\n"
                "  print('Original completed test output')\n"
                "  print('DESIGN_DNA_TEST_APPLICABILITY {}')\n",
                encoding="utf-8")
            output, diagnostic = Path(temporary) / "attestation.json", Path(temporary) / "diagnostic.json"
            result = self.run_cli(plugin, output, diagnostic)
            payload = self.assert_diagnostic(result, output, diagnostic, "test-applicability-missing")
            self.assertIn("Original completed test output", payload["output"]["stdout"])
            self.assertIn("test_real_success", payload["output"]["stderr"])

    def test_default_local_command_emits_a_durable_private_diagnostic_path_and_hash(self):
        with tempfile.TemporaryDirectory(prefix="dna-postrun-local-") as temporary:
            plugin = self.fixture(temporary)
            (plugin / "maintainer/scripts/run_release_tests.py").write_text(
                "print('Original completed output without a unittest summary', flush=True)\n",
                encoding="utf-8")
            output = Path(temporary) / "attestation.json"
            result = self.run_cli(plugin, output, None)
            self.assertEqual(2, result.returncode)
            self.assertFalse(output.exists())
            emitted = json.loads(result.stdout)
            descriptor = emitted["rejection_diagnostic"]
            path = Path(descriptor["path"])
            self.assertEqual(Path(tempfile.gettempdir()).resolve(), path.parent.parent.resolve())
            self.assertTrue(path.parent.name.startswith("design-dna-test-rejection-"))
            try:
                data = path.read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), descriptor["sha256"])
                payload = json.loads(data)
                self.assertIn("Original completed output", payload["output"]["stdout"])
                self.assertFalse(payload["release_eligible"])
            finally:
                path.unlink()
                path.parent.rmdir()

    def test_actual_suite_input_mutation_retains_pre_rejection_output(self):
        with tempfile.TemporaryDirectory(prefix="dna-postrun-") as temporary:
            plugin = self.fixture(temporary)
            (plugin / "skills/design-dna/tests/test_mutation.py").write_text(
                "import unittest\nfrom pathlib import Path\nclass Mutation(unittest.TestCase):\n"
                " def test_change_source(self):\n"
                "  print('Executed before input drift rejection')\n"
                "  Path('skills/design-dna/SKILL.md').write_text('mutated fixture')\n",
                encoding="utf-8")
            output, diagnostic = Path(temporary) / "attestation.json", Path(temporary) / "diagnostic.json"
            payload = self.assert_diagnostic(self.run_cli(plugin, output, diagnostic), output, diagnostic, "test-attestation-input-unstable")
            self.assertIn("Executed before input drift rejection", payload["output"]["stdout"])

    def test_post_creation_schema_rejection_also_retains_actual_completed_streams(self):
        with tempfile.TemporaryDirectory(prefix="dna-postrun-") as temporary:
            plugin = self.fixture(temporary)
            (plugin / "maintainer/schemas/test-attestation.schema.json").write_text(
                json.dumps({"not": {"type": "object"}}), encoding="utf-8")
            output, diagnostic = Path(temporary) / "attestation.json", Path(temporary) / "diagnostic.json"
            payload = self.assert_diagnostic(self.run_cli(plugin, output, diagnostic), output, diagnostic, "test-attestation-schema-invalid")
            self.assertIn("Ran ", payload["output"]["stderr"])
            self.assertTrue(payload["execution_completed"])

    def test_success_preserves_the_attestation_and_creates_no_failure_artifact(self):
        with tempfile.TemporaryDirectory(prefix="dna-postrun-") as temporary:
            plugin = self.fixture(temporary)
            output, diagnostic = Path(temporary) / "attestation.json", Path(temporary) / "diagnostic.json"
            result = self.run_cli(plugin, output, diagnostic)
            self.assertEqual(0, result.returncode, result.stdout.decode(errors="replace"))
            self.assertEqual("passed", json.loads(output.read_bytes())["result"]["status"])
            self.assertFalse(diagnostic.exists())

    def test_non_tool_schema_exception_keeps_completed_output_and_nonzero_exit(self):
        with tempfile.TemporaryDirectory(prefix="dna-postrun-") as temporary:
            plugin = self.fixture(temporary)
            (plugin / "maintainer/schemas/test-attestation.schema.json").write_text(
                json.dumps({"type": "not-a-json-schema-type"}), encoding="utf-8")
            output, diagnostic = Path(temporary) / "attestation.json", Path(temporary) / "diagnostic.json"
            result = self.run_cli(plugin, output, diagnostic)
            self.assertEqual(2, result.returncode)
            self.assertFalse(output.exists())
            payload = json.loads(diagnostic.read_bytes())
            self.assertFalse(payload["release_eligible"])
            self.assertEqual("UnknownType", payload["failure_code"])
            self.assertIn("Ran ", payload["output"]["stderr"])

    def test_workflow_names_the_diagnostic_json_and_never_uploads_raw_spools(self):
        import yaml
        plugin = Path(__file__).resolve().parents[2]
        workflow = yaml.safe_load((plugin / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
        steps = workflow["jobs"]["test"]["steps"]
        run = next(step for step in steps if step.get("name") == "Run and attest unit and adversarial tests with zero unwaived skips")
        self.assertIn('--diagnostic-output "${{ runner.temp }}/design-dna-test-diagnostic.json"', run["run"])
        upload = next(step for step in steps if step.get("name") == "Retain matrix test and package-audit evidence")
        self.assertEqual("${{ always() }}", upload["if"])
        self.assertIn("${{ runner.temp }}/design-dna-test-diagnostic.json", upload["with"]["path"].splitlines())
        self.assertNotIn("raw.log", upload["with"]["path"])
        self.assertNotIn("test-run-", upload["with"]["path"])

    def test_short_and_placeholder_collision_secrets_preserve_real_cli_diagnostic_structure(self):
        for secret in ("s", "a", "<REDACTED_SECRET>", "REDACTED", "<HOME>", "E"):
            with self.subTest(secret=secret), tempfile.TemporaryDirectory(prefix="dna-redaction-shape-") as temporary:
                plugin = self.fixture(temporary)
                (plugin / "maintainer/scripts/run_release_tests.py").write_text(
                    "import os\nprint(os.environ['DIAGNOSTIC_TEST_TOKEN'], flush=True)\n"
                    "print('No complete unittest summary follows', flush=True)\n",
                    encoding="utf-8")
                inputs = attest_tests.attested_input_hashes(plugin)
                dependencies = attest_tests.pinned_dependencies(plugin)
                output, diagnostic = Path(temporary) / "attestation.json", Path(temporary) / "diagnostic.json"
                result = self.run_cli(plugin, output, diagnostic,
                    extra_environment={"DIAGNOSTIC_TEST_TOKEN": secret})
                payload = self.assert_diagnostic(result, output, diagnostic, "test-attestation-output-incomplete")
                self.assertEqual("rejected", payload["status"])
                self.assertIs(False, payload["release_eligible"])
                self.assertIs(False, payload["attestation_validated"])
                self.assertEqual(inputs, payload["source_inputs_before"])
                self.assertEqual(dependencies, payload["dependencies_before"])
                command = [sys.executable, *attest_tests.UNITTEST_ARGUMENTS]
                expected_command = hashlib.sha256(json.dumps(command, separators=(",", ":")).encode()).hexdigest()
                self.assertEqual(expected_command, payload["command_sha256"])
                emitted = json.loads(result.stdout)
                self.assertEqual("test-attestation-output-incomplete", emitted["failures"][0]["code"])
                self.assertIn("message", emitted["failures"][0])
                self.assertEqual("rejected", emitted["rejection_diagnostic"]["status"])
                self.assertEqual(hashlib.sha256(diagnostic.read_bytes()).hexdigest(), emitted["rejection_diagnostic"]["sha256"])
                with patch.dict(os.environ, {"DIAGNOSTIC_TEST_TOKEN": secret}):
                    capture = TestRunCapture(plugin,
                        redact_paths=lambda value: attest_tests.redact_known_local_paths(value, plugin),
                        protected=attest_tests.validated_test_execution_inputs(plugin))
                self.assertEqual(capture.placeholder, payload["output"]["stdout"].splitlines()[0])
                self.assertNotIn(secret, payload["output"]["stdout"])
                for stream in ("stdout", "stderr"):
                    redacted = payload["output"][stream]
                    self.assertEqual(redacted, capture.redact(redacted))
                    self.assertEqual(redacted, capture.redact(capture.redact(redacted)))

    def test_repeated_redaction_preserves_masks_but_still_removes_real_credentials(self):
        with tempfile.TemporaryDirectory(prefix="dna-redaction-repeat-") as temporary:
            plugin = self.fixture(temporary)
            for secret in ("s", "a", "<REDACTED_SECRET>", "<MASKED>", "E"):
                with self.subTest(secret=secret), patch.dict(os.environ, {"DIAGNOSTIC_TEST_TOKEN": secret}):
                    capture = TestRunCapture(plugin,
                        redact_paths=lambda value: attest_tests.redact_known_local_paths(value, plugin),
                        protected=attest_tests.validated_test_execution_inputs(plugin))
                    original = (secret + "\nAuthorization: Bearer unregistered-credential-997\n"
                        + str(plugin / "trace.py") + "\n"
                        + "-----BEGIN PRIVATE KEY-----\nprivate-material-997\n-----END PRIVATE KEY-----\n")
                    first = capture.redact(original)
                    self.assertNotIn(secret, first)
                    self.assertNotIn("unregistered-credential-997", first)
                    self.assertNotIn("private-material-997", first)
                    self.assertEqual(first, capture.redact(first))
                    self.assertEqual(first, capture.redact(capture.redact(first)))
                    cleanup = {"attempted": True, "verified": False, "error": secret}
                    sanitized = capture._redact_content(cleanup)
                    self.assertEqual(set(cleanup), set(sanitized))
                    self.assertIs(True, sanitized["attempted"])
                    self.assertIs(False, sanitized["verified"])
                    self.assertEqual(capture.placeholder, sanitized["error"])

    def test_actual_timeout_exports_only_verified_redacted_private_streams(self):
        with tempfile.TemporaryDirectory(prefix="dna-postrun-timeout-") as temporary:
            plugin = self.fixture(temporary)
            diagnostic = Path(temporary) / "diagnostic.json"
            (plugin / "maintainer/scripts/run_release_tests.py").write_text(
                "import sys,time\nprint('timeout stdout marker', flush=True)\n"
                "print('timeout stderr marker', file=sys.stderr, flush=True)\ntime.sleep(5)\n",
                encoding="utf-8")
            with patch.object(attest_tests, "TEST_SUITE_TIMEOUT_SECONDS", 0.5):
                with self.assertRaises(attest_tests.SuiteRunUnavailable) as caught:
                    attest_tests.create_attestation(plugin, diagnostic_output=diagnostic)
            payload = json.loads(diagnostic.read_bytes())
            self.assertFalse(payload["execution_completed"])
            self.assertFalse(payload["release_eligible"])
            self.assertIn("timeout stdout marker", payload["output"]["stdout"])
            self.assertIn("timeout stderr marker", payload["output"]["stderr"])
            self.assertTrue(payload["cleanup"]["verified"])
            self.assertNotIn("raw.log", diagnostic.read_text())
            private = Path(caught.exception.diagnostic["path"]).parent.resolve()
            self.assertEqual(Path(tempfile.gettempdir()).resolve(), private.parent)
            self.assertTrue(private.name.startswith("design-dna-test-run-"))
            for name in ("diagnostic.json", "stdout.redacted.log", "stderr.redacted.log"):
                (private / name).unlink()
            private.rmdir()

    def test_existing_linked_overlapping_or_shared_diagnostic_destination_refuses_before_execution(self):
        with tempfile.TemporaryDirectory(prefix="dna-postrun-") as temporary:
            plugin = self.fixture(temporary)
            output = Path(temporary) / "attestation.json"
            marker = Path(temporary) / "must-not-run.txt"
            (plugin / "maintainer/scripts/run_release_tests.py").write_text(
                "from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('ran')\n", encoding="utf-8")
            existing = Path(temporary) / "existing.json"
            existing.write_text("keep original", encoding="utf-8")
            hardlink = Path(temporary) / "hardlink.json"
            os.link(existing, hardlink)
            destinations = [existing, hardlink, output, plugin / "docs/diagnostic.json"]
            for destination in destinations:
                with self.subTest(destination=destination):
                    result = self.run_cli(plugin, output, destination)
                    self.assertEqual(2, result.returncode)
                    self.assertFalse(marker.exists())
            self.assertEqual("keep original", existing.read_text())
            target = Path(temporary) / "owned-target"
            target.mkdir()
            link = Path(temporary) / "owned-link"
            make_directory_link(link, target)
            try:
                result = self.run_cli(plugin, output, link / "diagnostic.json")
                self.assertEqual(2, result.returncode)
                self.assertFalse(marker.exists())
                self.assertFalse((target / "diagnostic.json").exists())
            finally:
                remove_directory_link(link)


if __name__ == "__main__":
    unittest.main()
