"""Imported platform coverage is checked against its CI matrix, not the reader."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from maintainer.tests import test_release_proofs as fixtures


def bind_changed_applicability(record):
    marker = fixtures.applicability.MARKER
    output = record["output"]
    for name in ("stdout", "stderr"):
        output[name] = "\n".join(
            line for line in output[name].splitlines() if not line.startswith(marker)
        ) + "\n"
    output["stderr"] += marker + json.dumps(record["test_applicability"], sort_keys=True) + "\n"
    output["stdout_bytes"] = len(output["stdout"].encode("utf-8"))
    output["stderr_bytes"] = len(output["stderr"].encode("utf-8"))
    output["sha256"] = hashlib.sha256(
        ("stdout\0" + output["stdout"] + "\0stderr\0" + output["stderr"]).encode("utf-8")
    ).hexdigest()


class CIPlatformApplicabilityTests(unittest.TestCase):
    def test_linux_import_rejects_consistent_darwin_applicability(self):
        with tempfile.TemporaryDirectory() as temporary:
            plugin, compatibility, manifest, audit_path = fixtures.make_ci_import_fixture(Path(temporary))
            arguments = (compatibility, plugin, fixtures.SCHEMAS / "ci-run-import.schema.json",
                fixtures.SCHEMAS / "test-attestation.schema.json", manifest)
            failures, _ = fixtures.audit_package.ci_contract_failures(*arguments, release_mode=True)
            self.assertEqual([], failures, failures)
            archive_root = audit_path.parent
            test_path = archive_root / "design-dna-test-attestation.json"
            record = json.loads(test_path.read_text(encoding="utf-8"))
            record["test_applicability"]["platform"] = "Darwin"
            bind_changed_applicability(record)
            test_bytes = (json.dumps(record, indent=2) + "\n").encode("utf-8")
            test_path.write_bytes(test_bytes)
            archive_path = archive_root / "artifact.zip"
            with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(test_path.name, test_bytes)
                archive.writestr(audit_path.name, audit_path.read_bytes())
            payload_path = archive_root / "import.json"
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
            payload["artifact"].update(sha256=digest, service_digest=f"sha256:{digest}", size_bytes=archive_path.stat().st_size)
            payload["evidence"]["unit_tests"].update(sha256=hashlib.sha256(test_bytes).hexdigest(), size_bytes=len(test_bytes))
            payload_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            failures, _ = fixtures.audit_package.ci_contract_failures(*arguments, release_mode=True)
            self.assertTrue(any(finding["code"] == "release-test-applicability-invalid"
                and "host platform" in finding["message"] for finding in failures), failures)

    def test_windows_pass_cannot_hide_native_tests_behind_zero_skips(self):
        with tempfile.TemporaryDirectory() as temporary:
            plugin = fixtures.make_attestation_fixture(Path(temporary))
            with patch.object(fixtures.platform, "system", return_value="Windows"):
                record = fixtures.attest_tests.create_attestation(plugin,
                    runner=lambda _root, command: fixtures.fake_unittest_result(command))
            manifest = {"generated_at": fixtures.after_timestamp(record["completed_at"], seconds=1)}
            record["test_applicability"]["executed_native_test_ids"] = []
            for stream in ("stdout", "stderr"):
                record["output"][stream] = "\n".join(line for line in record["output"][stream].splitlines()
                    if not any(identity in line and not line.startswith(fixtures.applicability.MARKER)
                               for identity in fixtures.applicability.WINDOWS_NATIVE_TEST_IDS)) + "\n"
            bind_changed_applicability(record)
            self.assertEqual(0, record["result"]["skipped"])
            failures = fixtures.audit_package.test_attestation_failures(record, plugin,
                plugin / "maintainer/schemas/test-attestation.schema.json", manifest,
                expected_platform="Windows", require_zero_skips=True)
            self.assertTrue(any(finding["code"] == "release-test-applicability-invalid"
                and "execute all native" in finding["message"] for finding in failures), failures)


if __name__ == "__main__":
    unittest.main()
