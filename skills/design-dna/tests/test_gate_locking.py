"""Evidence writers share the project mutation lease; lock bytes are not code."""
from __future__ import annotations

import importlib.util
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


class GateLockingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("gate_lock_test", SCRIPTS / "gate.py")
        cls.gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.gate)
        cls.validator = cls.gate.load_validator()

    def test_exact_root_lock_metadata_does_not_change_build_identity(self):
        with tempfile.TemporaryDirectory(prefix="dna-lock-identity-") as temporary:
            root = Path(temporary)
            (root / "index.html").write_text("<main>Bound source</main>", encoding="utf-8")
            initial = self.validator.project_tree_identity(root)
            source = self.validator.construction_source_snapshot(root)
            with self.validator.ProjectMutationLock(root, "regression"):
                self.assertEqual(initial, self.validator.project_tree_identity(root))
                self.assertEqual(source, self.validator.construction_source_snapshot(root))
            self.assertEqual(initial, self.validator.project_tree_identity(root))
            self.assertEqual(source, self.validator.construction_source_snapshot(root))
            nested = root / "nested"
            nested.mkdir()
            (nested / ".design-dna.lock").write_text("ordinary project content", encoding="utf-8")
            self.assertNotEqual(initial, self.validator.project_tree_identity(root))
            self.assertNotEqual(source, self.validator.construction_source_snapshot(root))

    def test_same_project_gate_refuses_before_writing_evidence(self):
        with tempfile.TemporaryDirectory(prefix="dna-gate-lock-") as temporary:
            root = Path(temporary)
            environment = dict(os.environ, DESIGN_DNA_LOCK_TIMEOUT_SECONDS="0.1")
            with self.validator.ProjectMutationLock(root, "competing-authorized-writer"):
                for phase in ("proof-slice", "first-screen", "maintenance"):
                    arguments = [sys.executable, "-B", str(SCRIPTS / "gate.py"),
                        "--project", str(root), "--build-id", "locked-build-0001", "--phase", phase]
                    arguments += ["--proof-slice", ".design-dna/proof-slice.json"] if phase == "proof-slice" else ["--route-manifest", ".design-dna/route-manifest.json"]
                    result = subprocess.run(arguments, capture_output=True, text=True, encoding="utf-8", env=environment, timeout=15)
                    self.assertEqual(1, result.returncode, result.stdout + result.stderr)
                    self.assertIn("project-state-locked", result.stdout)
                    self.assertFalse((root / ".design-dna").exists())

    def test_begin_commands_share_the_same_project_lease(self):
        with tempfile.TemporaryDirectory(prefix="dna-begin-lock-") as temporary:
            root = Path(temporary)
            environment = dict(os.environ, DESIGN_DNA_LOCK_TIMEOUT_SECONDS="0.1")
            with self.validator.ProjectMutationLock(root, "competing-gate"):
                for operation in (["--begin-construction"], ["--begin-maintenance", "missing-plan.json"]):
                    result = subprocess.run([sys.executable, "-B", str(SCRIPTS / "init_project_state.py"),
                        "--project", str(root), "--json", *operation], capture_output=True, text=True,
                        encoding="utf-8", env=environment, timeout=15)
                    self.assertNotEqual(0, result.returncode)
                    self.assertIn("project-state-locked", result.stderr)
                    self.assertFalse((root / ".design-dna").exists())

    def test_repeated_failed_gates_preserve_each_prohibition_bound_run(self):
        with tempfile.TemporaryDirectory(prefix="dna-repeat-gate-") as temporary:
            root = Path(temporary)
            for index in range(2):
                result = subprocess.run([sys.executable, "-B", str(SCRIPTS / "gate.py"),
                    "--project", str(root), "--build-id", f"maintenance-repeat-{index}",
                    "--phase", "maintenance", "--route-manifest", ".design-dna/route-manifest.json"],
                    capture_output=True, text=True, encoding="utf-8", timeout=30)
                self.assertEqual(1, result.returncode, result.stdout + result.stderr)
            prohibitions = list((root / ".design-dna/evidence/implementation-prohibitions").glob("*.json"))
            self.assertEqual(2, len(prohibitions))
            bound_paths = set()
            for path in prohibitions:
                binding = json.loads(path.read_text(encoding="utf-8"))["gate"]
                bound_paths.add(binding["path"])
                self.assertEqual(binding["sha256"], hashlib.sha256((root / binding["path"]).read_bytes()).hexdigest())
            self.assertEqual(2, len(bound_paths))

    def test_bound_project_artifact_refuses_external_hardlink(self):
        with tempfile.TemporaryDirectory(prefix="dna-bound-link-") as temporary:
            outer = Path(temporary)
            external = outer / "external.json"
            external.write_text("{}", encoding="utf-8")
            root = outer / "project"
            root.mkdir()
            os.link(external, root / "evidence.json")
            with self.assertRaises(self.validator.StateError) as caught:
                self.validator.safe_binding_path(root, "evidence.json", record_path=root / "record.md")
            self.assertEqual("record-binding-hardlink-refused", caught.exception.code)

    def test_dry_run_is_read_only_even_when_inputs_are_missing(self):
        with tempfile.TemporaryDirectory(prefix="dna-gate-dry-") as temporary:
            root = Path(temporary)
            for phase in ("proof-slice", "first-screen", "maintenance"):
                arguments = [sys.executable, "-B", str(SCRIPTS / "gate.py"),
                    "--project", str(root), "--build-id", "dry-run-build-0001", "--phase", phase, "--dry-run"]
                arguments += ["--proof-slice", ".design-dna/proof-slice.json"] if phase == "proof-slice" else ["--route-manifest", ".design-dna/route-manifest.json"]
                result = subprocess.run(arguments, capture_output=True, text=True, encoding="utf-8", timeout=30)
                self.assertEqual(1, result.returncode, result.stdout + result.stderr)
                self.assertEqual([], list(root.iterdir()))


if __name__ == "__main__":
    unittest.main()
