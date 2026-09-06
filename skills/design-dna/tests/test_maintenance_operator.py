"""Operator boundaries cannot authorize an existing site without real evidence."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


class MaintenanceOperatorTests(unittest.TestCase):
    def test_begin_missing_evidence_blocks_without_rewriting_the_existing_site(self):
        with tempfile.TemporaryDirectory(prefix="dna-maintenance-cli-") as temporary:
            root = Path(temporary)
            site = root / "site.html"
            site.write_text("<main>Existing working page</main>", encoding="utf-8")
            state = root / ".design-dna"
            state.mkdir()
            plan = state / "maintenance-plan.json"
            plan.write_text(json.dumps({"schema_version": 1,
                "planned_source_map": ".design-dna/planned-map.json",
                "baseline_census": ".design-dna/evidence/baseline.json",
                "planned_changes": [{"path": "site.html", "operation": "modify", "component_ids": ["opening"]}]}), encoding="utf-8")
            run = subprocess.run([sys.executable, "-B", str(SCRIPTS / "init_project_state.py"),
                "--project", str(root), "--begin-maintenance", str(plan), "--json"],
                capture_output=True, text=True, encoding="utf-8", timeout=30)
            self.assertNotEqual(0, run.returncode, run.stdout)
            payload = json.loads(run.stderr)
            self.assertFalse(payload["ok"])
            self.assertIn("missing", str(payload).lower())
            self.assertEqual("<main>Existing working page</main>", site.read_text(encoding="utf-8"))
            self.assertFalse((state / "evidence" / "legacy-maintenance").exists())

    def test_maintenance_gate_without_baseline_is_blocked_and_preserves_final_gate(self):
        with tempfile.TemporaryDirectory(prefix="dna-maintenance-gate-") as temporary:
            root = Path(temporary)
            evidence = root / ".design-dna" / "evidence"
            evidence.mkdir(parents=True)
            final = evidence / "gate.json"
            final.write_text("existing historical gate", encoding="utf-8")
            run = subprocess.run([sys.executable, "-B", str(SCRIPTS / "gate.py"),
                "--project", str(root), "--build-id", "maintenance-test-0001",
                "--route-manifest", ".design-dna/route-manifest.json", "--phase", "maintenance"],
                capture_output=True, text=True, encoding="utf-8", timeout=30)
            self.assertNotEqual(0, run.returncode, run.stdout)
            self.assertIn("GATE FAIL", run.stdout)
            gate = json.loads((evidence / "maintenance-gate.json").read_text(encoding="utf-8"))
            self.assertFalse(gate["pass"])
            self.assertFalse(gate["deliverable_link_allowed"])
            self.assertFalse(gate["scoped_change_verified"])
            self.assertEqual("blocked", gate["delivery_status"])
            self.assertTrue(gate["failures"])
            self.assertEqual("existing historical gate", final.read_text(encoding="utf-8"))

    def test_first_screen_authorization_cannot_be_used_as_maintenance_shortcut(self):
        with tempfile.TemporaryDirectory(prefix="dna-maintenance-phase-") as temporary:
            run = subprocess.run([sys.executable, "-B", str(SCRIPTS / "gate.py"),
                "--project", temporary, "--build-id", "maintenance-test-0002",
                "--route-manifest", ".design-dna/route-manifest.json", "--phase", "maintenance",
                "--prebuild-authorization", ".design-dna/evidence/fake.json"],
                capture_output=True, text=True, encoding="utf-8", timeout=30)
            self.assertEqual(2, run.returncode)
            self.assertIn("valid only with --phase final", run.stderr)


if __name__ == "__main__":
    unittest.main()
