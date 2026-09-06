"""Stored gate flags cannot replace the complete current readiness verifier."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
spec = importlib.util.spec_from_file_location("delivery_status_test", SCRIPTS / "delivery_status.py")
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)


class DeliveryStatusTests(unittest.TestCase):
    def test_missing_gates_are_blocked_without_creating_files(self):
        with tempfile.TemporaryDirectory(prefix="dna-delivery-") as temporary:
            root = Path(temporary)
            result = delivery.status(root)
            self.assertFalse(result["deliverable_link_allowed"])
            self.assertEqual("the gate did not run", result["gate_records"]["final"]["verdict"])
            self.assertEqual([], list(root.iterdir()))

    def test_forged_pass_without_required_readiness_is_blocked(self):
        with tempfile.TemporaryDirectory(prefix="dna-delivery-forged-") as temporary:
            root = Path(temporary)
            evidence = root / ".design-dna/evidence"
            evidence.mkdir(parents=True)
            (evidence / "gate.json").write_text(json.dumps({"tool": "gate.py", "phase": "final",
                "pass": True, "verdict": "GATE PASS invented", "deliverable_link_allowed": True,
                "routes": [{"key": "home", "url": "http://127.0.0.1:3000/"}]}), encoding="utf-8")
            result = delivery.status(root)
            self.assertFalse(result["deliverable_link_allowed"])
            self.assertEqual([], result["routes"])
            self.assertTrue(result["failures"])

    def test_first_screen_or_maintenance_is_never_final_site_approval(self):
        for phase, filename in (("first-screen", "first-screen-gate.json"), ("maintenance", "maintenance-gate.json")):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory(prefix="dna-delivery-scope-") as temporary:
                root = Path(temporary)
                evidence = root / ".design-dna/evidence"
                evidence.mkdir(parents=True)
                (evidence / filename).write_text(json.dumps({"tool": "gate.py", "phase": phase, "pass": True}), encoding="utf-8")
                self.assertFalse(delivery.status(root)["deliverable_link_allowed"])

    def test_reporting_adapter_propagates_full_validator_result_without_claiming_owner_approval(self):
        # Unit-test the reporting adapter, not a substitute readiness fixture.
        with tempfile.TemporaryDirectory(prefix="dna-delivery-adapter-") as temporary:
            root = Path(temporary)
            evidence = root / ".design-dna/evidence"
            evidence.mkdir(parents=True)
            (evidence / "gate.json").write_text(json.dumps({"tool": "gate.py", "phase": "final", "pass": True,
                "deliverable_link_allowed": True, "routes": [{"key": "home", "url": "http://127.0.0.1:3000/"}]}), encoding="utf-8")
            validator = delivery.load_validator()
            with patch.object(delivery, "current_readiness_failures", return_value=[]) as check:
                result = delivery.status(root, validator=validator)
                check.assert_called_once_with(root, validator)
                self.assertTrue(result["deliverable_link_allowed"])
                self.assertEqual("not-verified-by-this-check", result["owner_approval"])
                self.assertFalse(result["automatic_aesthetic_pass"])
            with patch.object(delivery, "current_readiness_failures", return_value=["Current build changed"]):
                result = delivery.status(root, validator=validator)
                self.assertFalse(result["deliverable_link_allowed"])
                self.assertEqual([], result["routes"])

    def test_gate_changed_during_readiness_cannot_supply_new_unverified_pass(self):
        with tempfile.TemporaryDirectory(prefix="dna-delivery-drift-") as temporary:
            root = Path(temporary)
            evidence = root / ".design-dna/evidence"
            evidence.mkdir(parents=True)
            gate = evidence / "gate.json"
            gate.write_text(json.dumps({"tool": "gate.py", "phase": "final", "pass": True}), encoding="utf-8")
            validator = delivery.load_validator()
            def mutate(_project, _validator):
                gate.write_text(json.dumps({"tool": "gate.py", "phase": "final", "pass": True,
                    "deliverable_link_allowed": True, "routes": []}), encoding="utf-8")
                return []
            with patch.object(delivery, "current_readiness_failures", side_effect=mutate):
                result = delivery.status(root, validator=validator)
            self.assertFalse(result["deliverable_link_allowed"])
            self.assertIn("changed during", str(result["failures"]))


if __name__ == "__main__":
    unittest.main()
