"""Asset generation follows source evidence without requiring future build bytes."""
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
SPEC = importlib.util.spec_from_file_location("asset_source_plan_test", SCRIPTS / "asset_source_plan.py")
PLAN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PLAN)

class AssetSourcePlanTests(unittest.TestCase):
    def fixture(self, root):
        refs = root / ".design-dna/references"
        refs.mkdir(parents=True)
        observation = refs / "strong-1-observation.json"
        observation.write_text(json.dumps({"tool": "observe_reference.mjs", "id": "strong-1",
            "producer_script_sha256": PLAN.sha(SCRIPTS / "observe_reference.mjs"),
            "observed_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
            "source_study": {"source_status": "complete", "eligible_for_source_selection": True}}), encoding="utf-8")
        styles = refs / "strong-1-styles.json"
        styles.write_text(json.dumps({"tool": "extract_reference_styles.mjs", "id": "strong-1",
            "producer_script_sha256": PLAN.sha(SCRIPTS / "extract_reference_styles.mjs"),
            "component_styles": [{"profile": profile, "state_id": "rest", "selector": "#source-media", "media": {"source_url": "https://source.test/photo.jpg"},
                "geometry": {"width": width, "height": 300}} for profile, width in (("wide", 800), ("narrow", 390))]}), encoding="utf-8")
        bound = PLAN.prepare_source_plan(root, asset_id="ASSET-001", observation=observation, styles=styles,
            selector="#source-media", state_id="rest", role="Dominant opening subject image")
        asset = {"id": "ASSET-001", "generated": {"authorization_basis": bound["path"] + " plus sha256:" + bound["sha256"],
            "generated_at": datetime.now(timezone.utc).isoformat()}}
        mapping = {"source_observations": [{"id": "strong-1", "path": observation.relative_to(root).as_posix(), "sha256": PLAN.sha(observation)}],
            "decisions": [{"source_mapping": {"id": "strong-1", "source_selector": "#source-media"},
                "asset_role_binding": {"asset_id": "ASSET-001", "role": "Dominant opening subject image"}}]}
        return asset, mapping, bound

    def test_source_relationship_can_authorize_generation_before_visible_build(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            asset, mapping, _bound = self.fixture(root)
            self.assertEqual([], PLAN.generated_asset_source_plan_failures(root, asset, mapping))
            self.assertFalse((root / "index.html").exists())

    def test_generation_before_source_plan_and_role_reassignment_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            asset, mapping, _bound = self.fixture(root)
            asset["generated"]["generated_at"] = "2001-01-01T00:00:00Z"
            self.assertTrue(any("after generation" in row for row in PLAN.generated_asset_source_plan_failures(root, asset, mapping)))
            asset["generated"]["generated_at"] = datetime.now(timezone.utc).isoformat()
            mapping["decisions"][0]["asset_role_binding"]["role"] = "Invented unrelated footer visual"
            self.assertTrue(any("different media role" in row for row in PLAN.generated_asset_source_plan_failures(root, asset, mapping)))

    def test_tampered_source_plan_is_not_generation_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            asset, mapping, bound = self.fixture(root)
            (root / bound["path"]).write_text("{}", encoding="utf-8")
            self.assertTrue(PLAN.generated_asset_source_plan_failures(root, asset, mapping))

if __name__ == "__main__":
    unittest.main()
