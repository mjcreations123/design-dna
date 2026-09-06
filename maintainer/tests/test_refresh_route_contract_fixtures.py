"""The fixture pin updater cannot modify real observations or partial trees."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "maintainer/scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("synthetic_fixture_refresh_test", SCRIPTS / "refresh_route_contract_fixtures.py")
UPDATER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(UPDATER)


class SyntheticFixtureRefreshTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="dna-synthetic-refresh-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "package"
        for name in UPDATER.FIXTURE_NAMES:
            source = ROOT / UPDATER.INPUTS / name / ".design-dna"
            shutil.copytree(source, self.root / UPDATER.INPUTS / name / ".design-dna")
        for relative in [Path(".codex-plugin/plugin.json"), *(Path("skills/design-dna/scripts") / name for name in UPDATER.DEPENDENCIES)]:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)

    def snapshot(self):
        return {file.relative_to(self.root).as_posix(): file.read_bytes() for file in self.root.rglob("*") if file.is_file()}

    def test_refresh_is_exact_synthetic_scope_idempotent_and_dry_check_is_read_only(self):
        before = self.snapshot()
        preview = UPDATER.refresh(self.root)
        self.assertEqual(before, self.snapshot())
        report = UPDATER.refresh(self.root, write=True)
        self.assertTrue(report["ok"])
        self.assertFalse(report["public_evidence_generated"])
        self.assertEqual(preview["changed"], report["changed"])
        self.assertEqual([], UPDATER.refresh(self.root)["changed"])
        allowed = {str((UPDATER.INPUTS / name / suffix).as_posix()) for name in UPDATER.FIXTURE_NAMES
            for suffix in (UPDATER.OBSERVATION, ".design-dna/route-manifest.json", ".design-dna/route-family.json")}
        self.assertTrue(set(report["changed"]).issubset(allowed))
        for name in UPDATER.FIXTURE_NAMES:
            observation = self.root / UPDATER.INPUTS / name / UPDATER.OBSERVATION
            payload = json.loads(observation.read_text(encoding="utf-8"))
            self.assertEqual(UPDATER.SYNTHETIC_SCOPE, payload["fixture_scope"])
            self.assertEqual("synthetic-contract-fixture", payload["source_kind"])
            self.assertNotIn("source_study", payload)
            self.assertNotIn("recording", payload)
            self.assertEqual(set(UPDATER.DEPENDENCIES), set(payload["runtime_identity"]))

    def test_real_url_in_last_fixture_refuses_entire_refresh_without_writes(self):
        file = self.root / UPDATER.INPUTS / UPDATER.FIXTURE_NAMES[-1] / UPDATER.OBSERVATION
        payload = json.loads(file.read_text(encoding="utf-8"))
        payload["url"] = "https://example.com/real-source"
        file.write_text(json.dumps(payload), encoding="utf-8")
        before = self.snapshot()
        with self.assertRaisesRegex(UPDATER.ToolFailure, "real or expanded"):
            UPDATER.refresh(self.root, write=True)
        self.assertEqual(before, self.snapshot())

    def test_unknown_observation_tree_refuses_without_partial_refresh(self):
        added = self.root / UPDATER.INPUTS / "unreviewed-reference/.design-dna/references/strong-1-observation.json"
        added.parent.mkdir(parents=True)
        added.write_text("{}", encoding="utf-8")
        before = self.snapshot()
        with self.assertRaisesRegex(UPDATER.ToolFailure, "four explicit observation paths"):
            UPDATER.refresh(self.root, write=True)
        self.assertEqual(before, self.snapshot())

    def test_wrong_root_and_conflicting_dependent_hash_refuse_without_writes(self):
        before = self.snapshot()
        with self.assertRaises(UPDATER.ToolFailure):
            UPDATER.refresh(self.root / UPDATER.INPUTS / UPDATER.FIXTURE_NAMES[0], write=True)
        self.assertEqual(before, self.snapshot())
        file = self.root / UPDATER.INPUTS / UPDATER.FIXTURE_NAMES[-1] / ".design-dna/route-family.json"
        payload = json.loads(file.read_text(encoding="utf-8"))
        payload["routes"][0]["source_mapping"]["sha256"] = "0" * 64
        file.write_text(json.dumps(payload), encoding="utf-8")
        before = self.snapshot()
        with self.assertRaisesRegex(UPDATER.ToolFailure, "exact original synthetic"):
            UPDATER.refresh(self.root, write=True)
        self.assertEqual(before, self.snapshot())

    def test_hardlink_to_external_evidence_is_refused_before_writes(self):
        file = self.root / UPDATER.INPUTS / UPDATER.FIXTURE_NAMES[-1] / UPDATER.OBSERVATION
        alias = self.root.parent / "external-alias.json"
        os.link(file, alias)
        before = self.snapshot()
        with self.assertRaisesRegex(UPDATER.ToolFailure, "independent ordinary"):
            UPDATER.refresh(self.root, write=True)
        self.assertEqual(before, self.snapshot())

    def test_write_failure_rolls_back_previously_replaced_files(self):
        # Guarantee a stale code pin even when the checked-in fixtures are current.
        runtime = self.root / "skills/design-dna/scripts/observe_reference.mjs"
        runtime.write_bytes(runtime.read_bytes() + b"\n// Synthetic updater rollback regression.\n")
        before = self.snapshot()
        actual_replace = os.replace
        calls = 0
        def fail_once(source, destination):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected fixture replacement failure")
            return actual_replace(source, destination)
        with patch.object(UPDATER.os, "replace", side_effect=fail_once), self.assertRaisesRegex(OSError, "injected"):
            UPDATER.refresh(self.root, write=True)
        self.assertEqual(before, self.snapshot())


if __name__ == "__main__":
    unittest.main()
