"""Real validator regressions: a ready profile is not a complete final gate."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
SPEC = importlib.util.spec_from_file_location("delivery_bypass_regression", SCRIPTS / "delivery_status.py")
DELIVERY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DELIVERY)


class DeliveryBypassTests(unittest.TestCase):
    def test_quick_empty_record_profile_cannot_launder_a_forged_final_gate(self):
        with tempfile.TemporaryDirectory(prefix="dna-delivery-profile-bypass-") as temporary:
            project = Path(temporary)
            state = project / ".design-dna"
            evidence = state / "evidence"
            evidence.mkdir(parents=True)
            validator = DELIVERY.load_validator()
            (state / "state.json").write_text(validator.state_manifest("12.0.0-test", (), ("quick",)), encoding="utf-8")
            (evidence / "gate.json").write_text(json.dumps({"tool": "gate.py", "phase": "final", "pass": True,
                "deliverable_link_allowed": True, "verdict": "GATE PASS fabricated by test",
                "routes": [{"key": "home", "url": "http://127.0.0.1:3000/"}]}), encoding="utf-8")
            result = DELIVERY.status(project)
            self.assertFalse(result["deliverable_link_allowed"], result)
            self.assertEqual([], result["routes"])
            self.assertTrue(result["failures"])


if __name__ == "__main__":
    unittest.main()
