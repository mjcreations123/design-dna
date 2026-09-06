"""Offline compatibility checks against retained primary PyPI release facts."""
from __future__ import annotations

import copy
import importlib.metadata
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml
from packaging.specifiers import SpecifierSet
from packaging.utils import parse_wheel_filename


PLUGIN = Path(__file__).resolve().parents[2]
SCRIPTS = PLUGIN / "maintainer/scripts"
sys.path.insert(0, str(SCRIPTS))
try:
    import attest_tests
    import build_manifest
    import python_dependency_lock as dependency_lock
finally:
    sys.path.remove(str(SCRIPTS))

REQUIREMENTS = PLUGIN / "maintainer/requirements-dev.txt"
LOCK = PLUGIN / "maintainer/requirements-dev.lock"
METADATA = PLUGIN / "maintainer/dependencies/python-release-metadata.json"


class PythonDependencyCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.pins = dependency_lock.parse_pins(REQUIREMENTS.read_text(encoding="utf-8"))
        self.metadata = json.loads(METADATA.read_text(encoding="utf-8"))

    def test_complete_locked_closure_accepts_every_declared_python_version(self):
        self.assertEqual("3.10", dependency_lock.PYTHON_FLOOR)
        self.assertEqual(attest_tests.SUPPORTED_PYTHON_VERSIONS, dependency_lock.SUPPORTED_PYTHON_MINORS)
        workflow = yaml.safe_load((PLUGIN / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
        matrix = set(workflow["jobs"]["test"]["strategy"]["matrix"]["python"])
        self.assertIn("3.10", matrix)
        self.assertTrue(matrix.issubset(set(dependency_lock.SUPPORTED_PYTHON_MINORS)))
        self.assertEqual([], dependency_lock.validate_metadata(self.pins, self.metadata))
        self.assertEqual("0.30.0", self.pins["rpds-py"])

    def test_a_newer_local_interpreter_cannot_hide_any_package_floor_regression(self):
        for index, package in enumerate(self.metadata["packages"]):
            with self.subTest(package=package["name"]):
                changed = copy.deepcopy(self.metadata)
                changed["packages"][index]["requires_python"] = ">=3.11"
                issues = dependency_lock.validate_metadata(self.pins, changed)
                self.assertTrue(any("excludes supported Python 3.10" in issue for issue in issues), issues)
                with self.assertRaises(ValueError):
                    dependency_lock.render_lock(self.pins, changed)

    def test_hash_lock_contains_every_exact_retained_release_artifact(self):
        self.assertEqual(LOCK.read_text(encoding="utf-8").replace("\r\n", "\n"), dependency_lock.render_lock(self.pins, self.metadata))
        hashes = set(re.findall(r"--hash=sha256:([0-9a-f]{64})", LOCK.read_text(encoding="utf-8")))
        self.assertEqual({artifact["sha256"] for package in self.metadata["packages"] for artifact in package["artifacts"]}, hashes)

    def test_rpds_native_wheels_cover_supported_python_and_ci_architectures(self):
        package = next(item for item in self.metadata["packages"] if item["name"] == "rpds-py")
        tags = set()
        for artifact in package["artifacts"]:
            if artifact["packagetype"] == "bdist_wheel" and not artifact["yanked"]:
                tags.update(parse_wheel_filename(artifact["filename"])[3])
        platforms = {
            "Windows AMD64": lambda value: value == "win_amd64",
            "Linux x86_64": lambda value: value.startswith("manylinux") and value.endswith("_x86_64"),
            "macOS Intel": lambda value: value.startswith("macosx") and value.endswith(("_x86_64", "_universal2")),
            "macOS ARM64": lambda value: value.startswith("macosx") and value.endswith(("_arm64", "_universal2")),
        }
        for python in dependency_lock.SUPPORTED_PYTHON_MINORS:
            interpreter = "cp" + python.replace(".", "")
            for platform, matches in platforms.items():
                with self.subTest(python=python, platform=platform):
                    self.assertTrue(any(tag.interpreter == interpreter and tag.abi == interpreter and matches(tag.platform) for tag in tags))

    def test_installed_distribution_python_metadata_matches_retained_release(self):
        for package in self.metadata["packages"]:
            with self.subTest(package=package["name"]):
                self.assertEqual(package["version"], importlib.metadata.version(package["name"]))
                installed = importlib.metadata.metadata(package["name"]).get("Requires-Python")
                self.assertEqual(SpecifierSet(package["requires_python"]), SpecifierSet(installed))

    def test_attester_rejects_incompatible_installed_metadata_before_running_tests(self):
        original = importlib.metadata.metadata

        def changed_metadata(distribution):
            if dependency_lock.normalized_name(distribution) == "rpds-py":
                return {"Requires-Python": ">=3.11"}
            return original(distribution)

        with patch.object(attest_tests.importlib.metadata, "metadata", side_effect=changed_metadata):
            with self.assertRaises(attest_tests.ToolFailure) as failure:
                attest_tests.pinned_dependencies(PLUGIN)
        self.assertEqual("test-attestation-dependency-python-incompatible", failure.exception.issue.code)

    def test_retained_metadata_is_in_attestation_and_release_identity_inputs(self):
        self.assertIn(("python_release_metadata", "maintainer/dependencies", "directory"), attest_tests.TEST_EXECUTION_INPUT_MANIFEST)
        self.assertIn(("python_release_metadata_file", "maintainer/dependencies/python-release-metadata.json", "file"), attest_tests.TEST_EXECUTION_INPUT_MANIFEST)
        self.assertIn("maintainer/dependencies", build_manifest.IDENTITY_GROUPS["maintainer_tooling"])
        for derived in attest_tests.DERIVED_EXECUTION_OUTPUT_PATHS:
            self.assertFalse(attest_tests._execution_input_paths_overlap("maintainer/dependencies", derived))

    def test_offline_guard_refuses_missing_hashes_and_can_reproduce_the_lock(self):
        with tempfile.TemporaryDirectory(prefix="dna dependency lock ") as temporary:
            path = Path(temporary) / "requirements.lock"
            path.write_text("attrs==26.1.0 --hash=sha256:" + "a" * 64 + "\n", encoding="utf-8")
            command = [sys.executable, "-B", str(SCRIPTS / "python_dependency_lock.py"), "--lock", str(path)]
            refused = subprocess.run(command, text=True, encoding="utf-8", capture_output=True, timeout=30)
            self.assertEqual(1, refused.returncode, refused.stdout + refused.stderr)
            self.assertIn("hash lock differs", json.loads(refused.stdout)["error"])
            generated = subprocess.run(command + ["--write"], text=True, encoding="utf-8", capture_output=True, timeout=30)
            self.assertEqual(0, generated.returncode, generated.stdout + generated.stderr)
            self.assertFalse(json.loads(generated.stdout)["network_used"])
            self.assertEqual(LOCK.read_bytes(), path.read_bytes())

    def test_transitive_constraint_or_wrong_artifact_release_cannot_be_laundered(self):
        changed = copy.deepcopy(self.metadata)
        package = next(item for item in changed["packages"] if item["name"] == "jsonschema")
        package["requires_dist"].append("rpds-py>=999")
        issues = dependency_lock.validate_metadata(self.pins, changed)
        self.assertTrue(any("pinned closure does not satisfy" in issue for issue in issues), issues)
        with self.assertRaises(ValueError):
            dependency_lock.render_lock(self.pins, changed)
        changed = copy.deepcopy(self.metadata)
        package = changed["packages"][0]
        artifact = package["artifacts"][0]
        artifact["filename"] = artifact["filename"].replace(package["version"], "999.0.0")
        artifact["url"] = artifact["url"].rsplit("/", 1)[0] + "/" + artifact["filename"]
        self.assertTrue(any("different exact distribution" in issue for issue in dependency_lock.validate_metadata(self.pins, changed)))


if __name__ == "__main__":
    unittest.main()
