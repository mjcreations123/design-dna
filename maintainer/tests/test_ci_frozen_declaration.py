"""Frozen CI declarations and derived imports; all provider records are synthetic."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "maintainer/tests"))
sys.path.insert(0, str(REPO / "maintainer/scripts"))
import test_release_proofs as fixtures
from directory_link_fixtures import make_directory_link, remove_directory_link
import audit_package as audit_under_test

# Import the actual package consumer normally; do not reconstruct its code.
staged_ci_contract = audit_under_test.ci_contract_failures


def repack(plugin, imported, attestation):
    root = plugin / Path(imported["evidence"]["unit_tests"]["path"]).parent
    test_bytes = (json.dumps(attestation, indent=2) + "\n").encode()
    test = root / "design-dna-test-attestation.json"
    test.write_bytes(test_bytes)
    imported["evidence"]["unit_tests"]["size_bytes"] = len(test_bytes)
    imported["evidence"]["unit_tests"]["sha256"] = hashlib.sha256(test_bytes).hexdigest()
    artifact = plugin / imported["artifact"]["path"]
    with zipfile.ZipFile(artifact, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for binding in imported["evidence"].values():
            archive.writestr(binding["archive_member"], (plugin / binding["path"]).read_bytes())
    blob = artifact.read_bytes()
    digest = hashlib.sha256(blob).hexdigest()
    imported["artifact"].update(size_bytes=len(blob), sha256=digest, service_digest="sha256:" + digest)
    (root / "import.json").write_text(json.dumps(imported, indent=2) + "\n", encoding="utf-8")


def candidate_fixture(temporary):
    plugin, promoted, _, audit_path = fixtures.make_ci_import_fixture(Path(temporary))
    candidate = copy.deepcopy(promoted)
    env = candidate["environments"][0]
    env["checks"]["unit_tests"] = "declared_not_observed"
    env["checks"]["package_audit"] = "declared_not_observed"
    env["evidence"] = [".github/workflows/ci.yml"]
    env["notes"] = ["Synthetic frozen candidate declaration; no real remote run asserted."]
    promoted["environments"][0]["notes"] = list(env["notes"])
    matrix = plugin / "maintainer/compatibility/matrix.yml"
    matrix.write_text(json.dumps(candidate, indent=2) + "\n", encoding="utf-8")
    with patch.object(fixtures.attest_tests.platform, "system", return_value="Linux"):
        attestation = fixtures.attest_tests.create_attestation(plugin,
            runner=lambda selected, command: fixtures.fake_unittest_result(command))
    import_path = audit_path.parent / "import.json"
    imported = json.loads(import_path.read_text())
    imported["source"]["started_at"] = fixtures.after_timestamp(attestation["started_at"], seconds=-1)
    imported["source"]["completed_at"] = fixtures.after_timestamp(attestation["completed_at"], seconds=1)
    imported["imported_at"] = fixtures.after_timestamp(imported["source"]["completed_at"], seconds=1)
    promoted["environments"][0]["checked_at"] = imported["imported_at"]
    repack(plugin, imported, attestation)
    manifest = {"generated_at": fixtures.after_timestamp(imported["imported_at"], seconds=1)}
    return plugin, candidate, promoted, imported, attestation, manifest


def check(function, plugin, compatibility, manifest, release=True):
    return function(compatibility, plugin,
        plugin / "maintainer/schemas/ci-run-import.schema.json",
        plugin / "maintainer/schemas/test-attestation.schema.json",
        manifest, release_mode=release)


class FrozenCiDeclarationTests(unittest.TestCase):
    def test_documented_on_disk_promotion_reproduces_original_input_drift(self):
        with tempfile.TemporaryDirectory(prefix="dna-ci-promotion-") as temporary:
            plugin, candidate, promoted, imported, attestation, manifest = candidate_fixture(temporary)
            # Existing fixture-style in-memory promotion appears to pass.
            self.assertEqual([], check(fixtures.audit_package.ci_contract_failures, plugin, promoted, manifest)[0])
            matrix = plugin / "maintainer/compatibility/matrix.yml"
            matrix.write_text(json.dumps(promoted, indent=2) + "\n", encoding="utf-8")
            failures, details = check(fixtures.audit_package.ci_contract_failures, plugin, promoted, manifest)
            self.assertIn("release-test-attestation-input-drift", {row["code"] for row in failures})
            self.assertEqual(0, details["passed_entries"])

    def test_verified_import_derives_pass_without_any_candidate_matrix_edit(self):
        with tempfile.TemporaryDirectory(prefix="dna-ci-promotion-") as temporary:
            plugin, candidate, _, _, attestation, manifest = candidate_fixture(temporary)
            matrix = plugin / "maintainer/compatibility/matrix.yml"
            before = matrix.read_bytes()
            failures, details = check(staged_ci_contract, plugin, candidate, manifest)
            self.assertEqual([], failures)
            self.assertEqual(1, details["passed_entries"])
            self.assertEqual(1, details["verified_imports"])
            self.assertEqual(0, details["status_passed_entries"])
            self.assertEqual(before, matrix.read_bytes())
            self.assertEqual(attestation["inputs"], fixtures.attest_tests.attested_input_hashes(plugin))
            self.assertEqual("declared_not_observed", candidate["environments"][0]["checks"]["unit_tests"])
            development_failures, development = check(
                staged_ci_contract, plugin, candidate, manifest, release=False)
            self.assertEqual([], development_failures)
            self.assertEqual(1, development["passed_entries"])
            self.assertEqual(before, matrix.read_bytes())

    def test_missing_import_is_unobserved_not_a_pass(self):
        with tempfile.TemporaryDirectory(prefix="dna-ci-promotion-") as temporary:
            plugin, candidate, _, imported, _, manifest = candidate_fixture(temporary)
            import_path = plugin / Path(imported["artifact"]["path"]).parent / "import.json"
            import_path.rename(import_path.with_name("not-the-canonical-import.json"))
            failures, details = check(staged_ci_contract, plugin, candidate, manifest)
            self.assertIn("release-ci-matrix-entry-unobserved", {row["code"] for row in failures})
            self.assertEqual(0, details["passed_entries"])
            development, _ = check(staged_ci_contract, plugin, candidate, manifest, release=False)
            self.assertEqual([], development)

    def test_source_and_policy_drift_are_never_exempted(self):
        for relative, suffix in (("skills/design-dna/SKILL.md", "\nchanged runtime\n"),
                ("maintainer/compatibility/matrix.yml", "\n# candidate policy byte drift\n"),
                ("maintainer/scripts/common.py", "\n# tooling drift\n"),
                (".github/workflows/ci.yml", "\n# workflow drift\n")):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory(prefix="dna-ci-promotion-") as temporary:
                plugin, candidate, _, _, _, manifest = candidate_fixture(temporary)
                path = plugin / relative
                path.write_text(path.read_text(encoding="utf-8") + suffix, encoding="utf-8")
                failures, details = check(staged_ci_contract, plugin, candidate, manifest)
                self.assertIn("release-test-attestation-input-drift", {row["code"] for row in failures})
                self.assertEqual(0, details["passed_entries"])

    def test_untrusted_or_mismatched_imports_cannot_derive_passes(self):
        mutations = {
            "artifact_digest": lambda record: record["artifact"].update(service_digest="sha256:" + "0" * 64),
            "unauthenticated": lambda record: record["artifact"].update(authenticated_download=False),
            "matrix": lambda record: record["source"]["matrix"].update(os="windows-latest"),
            "commit": lambda record: record["source"].update(commit_sha="not-a-commit"),
            "run": lambda record: record["source"].update(run_id="not-a-run"),
            "job_window": lambda record: record["source"].update(completed_at=record["source"]["started_at"]),
            "conclusion": lambda record: record["source"].update(conclusion="failure"),
            "extra_claim": lambda record: record["passed_checks"].append("behavioral_eval"),
            "duplicate_claim": lambda record: record["passed_checks"].append("unit_tests"),
            "environment_id": lambda record: record.update(environment_id="../outside"),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory(prefix="dna-ci-promotion-") as temporary:
                plugin, candidate, _, imported, _, manifest = candidate_fixture(temporary)
                mutate(imported)
                import_path = plugin / Path(imported["artifact"]["path"]).parent / "import.json"
                import_path.write_text(json.dumps(imported) + "\n", encoding="utf-8")
                failures, details = check(staged_ci_contract, plugin, candidate, manifest)
                self.assertTrue(failures)
                self.assertEqual(0, details["passed_entries"])

    def test_attested_platform_or_failed_result_stays_invalid_with_correct_zip_bindings(self):
        for mutation in ("platform", "failed", "skip"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory(prefix="dna-ci-promotion-") as temporary:
                plugin, candidate, _, imported, attestation, manifest = candidate_fixture(temporary)
                if mutation == "platform":
                    attestation["test_applicability"]["platform"] = "Windows"
                elif mutation == "failed":
                    attestation["result"].update(status="failed", return_code=1, failures=1)
                else:
                    attestation["result"].update(skipped=1, skipped_test_ids=["synthetic.skipped"])
                repack(plugin, imported, attestation)
                failures, details = check(staged_ci_contract, plugin, candidate, manifest)
                self.assertTrue(failures)
                self.assertEqual(0, details["passed_entries"])

    def test_explicit_source_pass_claim_is_not_silently_repaired(self):
        with tempfile.TemporaryDirectory(prefix="dna-ci-promotion-") as temporary:
            plugin, candidate, _, _, _, manifest = candidate_fixture(temporary)
            candidate["environments"][0]["checks"]["unit_tests"] = "passed"
            failures, details = check(staged_ci_contract, plugin, candidate, manifest)
            self.assertIn("ci-import-record-missing", {row["code"] for row in failures})
            self.assertEqual(0, details["passed_entries"])

    def test_partial_valid_import_cannot_satisfy_the_required_pair(self):
        with tempfile.TemporaryDirectory(prefix="dna-ci-promotion-") as temporary:
            plugin, candidate, _, imported, _, manifest = candidate_fixture(temporary)
            imported["passed_checks"] = ["unit_tests"]
            import_path = plugin / Path(imported["artifact"]["path"]).parent / "import.json"
            import_path.write_text(json.dumps(imported) + "\n", encoding="utf-8")
            failures, details = check(staged_ci_contract, plugin, candidate, manifest)
            self.assertEqual(1, details["verified_imports"])
            self.assertEqual(0, details["passed_entries"])
            self.assertIn("release-ci-matrix-entry-unobserved", {row["code"] for row in failures})
            self.assertIn("package_audit", json.dumps(failures))

    def test_previous_explicit_import_validation_remains_covered(self):
        suite = unittest.TestSuite([
            fixtures.AuditProofModeTests("test_ci_import_binds_provider_artifact_and_extracted_proofs"),
            fixtures.AuditProofModeTests("test_current_unobserved_ci_matrix_blocks_strict_release"),
        ])
        result = unittest.TestResult()
        with patch.object(fixtures.audit_package, "ci_contract_failures", staged_ci_contract):
            suite.run(result)
        self.assertEqual(2, result.testsRun)
        self.assertEqual([], result.failures + result.errors)

    def test_malformed_or_nonobject_canonical_import_blocks_without_a_crash(self):
        for contents in ("{", "[]", '"not an import"', "null"):
            with self.subTest(contents=contents), tempfile.TemporaryDirectory(prefix="dna-ci-promotion-") as temporary:
                plugin, candidate, _, imported, _, manifest = candidate_fixture(temporary)
                import_path = plugin / Path(imported["artifact"]["path"]).parent / "import.json"
                import_path.write_text(contents, encoding="utf-8")
                failures, details = check(staged_ci_contract, plugin, candidate, manifest)
                self.assertTrue(failures)
                self.assertEqual(0, details["passed_entries"])

    def test_unsafe_source_environment_identifier_is_refused_before_any_import_load(self):
        for identifier in ("../outside", "a/b", "", None, "x" * 97):
            with self.subTest(identifier=identifier), tempfile.TemporaryDirectory(prefix="dna-ci-promotion-") as temporary:
                plugin, candidate, _, _, _, manifest = candidate_fixture(temporary)
                candidate["environments"][0]["id"] = identifier
                with patch.object(audit_under_test, "load_json", side_effect=AssertionError("An unsafe identifier reached import loading")):
                    failures, details = check(staged_ci_contract, plugin, candidate, manifest)
                self.assertIn("ci-import-environment-id-unsafe", {row["code"] for row in failures})
                self.assertEqual(0, details["passed_entries"])

    def test_linked_canonical_import_ancestor_is_refused_before_any_import_load(self):
        with tempfile.TemporaryDirectory(prefix="dna-ci-promotion-") as temporary:
            plugin, candidate, _, imported, _, manifest = candidate_fixture(temporary)
            canonical_root = plugin / Path(imported["artifact"]["path"]).parent
            actual_root = canonical_root.with_name("owned-link-fixture-target")
            canonical_root.rename(actual_root)
            make_directory_link(canonical_root, actual_root)
            try:
                with patch.object(audit_under_test, "load_json", side_effect=AssertionError("A linked path reached import loading")):
                    failures, details = check(staged_ci_contract, plugin, candidate, manifest)
                self.assertIn("reparse-point-refused", {row["code"] for row in failures})
                self.assertEqual(0, details["passed_entries"])
            finally:
                remove_directory_link(canonical_root)

    def test_explicit_pass_timestamp_rule_is_not_repaired_from_the_import(self):
        with tempfile.TemporaryDirectory(prefix="dna-ci-promotion-") as temporary:
            plugin, _, promoted, _, _, manifest = candidate_fixture(temporary)
            promoted["environments"][0]["checked_at"] = "2020-01-01T00:00:00Z"
            failures, details = check(staged_ci_contract, plugin, promoted, manifest)
            self.assertIn("ci-import-time-invalid", {row["code"] for row in failures})
            self.assertEqual(0, details["passed_entries"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
