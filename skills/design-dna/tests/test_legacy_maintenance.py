"""Existing-site maintenance cannot rewrite history or expand its frozen delta."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
SPEC = importlib.util.spec_from_file_location("legacy_maintenance", SCRIPTS / "legacy_maintenance.py")
legacy = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(legacy)


def write(path: Path, value: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    return path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class LegacyMaintenanceTests(unittest.TestCase):
    """Synthetic scanner envelopes test this boundary, not a real source/site pass."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="design-dna-maintenance-")
        self.addCleanup(self.temporary.cleanup)
        self.project = Path(self.temporary.name)
        (self.project / "site.html").write_text("<h1>Existing source-bound heading</h1>", encoding="utf-8")
        (self.project / "footer.css").write_text("footer { padding: 20px }", encoding="utf-8")
        self.manifest_path = write(self.project / ".design-dna/route-manifest.json", {
            "schema_version": 2, "manifest_id": "existing-route-family",
            "routes": [{"key": "home", "states": [{"id": "rest"}]}],
            "viewports": [{"name": "wide"}, {"name": "narrow"}],
        })
        self.old_map = {
            "schema_version": 2, "record_type": "design-dna-visible-decision-source-manifest",
            "route_manifest": {"path": ".design-dna/route-manifest.json", "sha256": digest(self.manifest_path)},
            "construction_authorization": {"journal_id": None, "entry_path": None, "entry_sha256": None},
            "decisions": [
                {"decision_id": "heading-type", "component_id": "hero-heading", "measured_size": 32},
                {"decision_id": "footer-spacing", "component_id": "site-footer", "measured_padding": 20},
            ],
        }
        self.current_map_path = write(self.project / ".design-dna/visible-decision-sources.json", self.old_map)
        self.planned = copy.deepcopy(self.old_map)
        self.planned["decisions"][0]["measured_size"] = 40
        self.planned_path = write(self.project / ".design-dna/planned-maintenance-map.json", self.planned)
        self.old_scan_path = self.make_scan(self.old_map, "baseline-scan.json", "2026-09-04T01:00:00Z")
        self.changes = [{"path": "site.html", "operation": "modify", "component_ids": ["hero-heading"]}]

    def make_scan(self, mapping: dict, name: str, at: str) -> Path:
        inventory = legacy.implementation_snapshot(self.project)
        reconciliation = {
            "complete": True, "manifest_sha256": digest(self.current_map_path),
            "implemented_decision_ids": [row["decision_id"] for row in mapping["decisions"]],
            **{field: [] for field in ("missing_decision_ids", "unsourced_visible_decisions", "wrapper_inheritance_findings",
                "binding_cell_findings", "asset_role_findings", "construction_findings", "scaffold_findings",
                "fallback_findings", "placeholder_findings")},
        }
        return write(self.project / ".design-dna/evidence" / name, {
            "tool": "scan_build_components.mjs", "schema_version": 3,
            "producer_script_sha256": digest(SCRIPTS / "scan_build_components.mjs"),
            "first_screen_only": False, "pass": True, "scanned_at": at,
            "manifest_sha256": digest(self.manifest_path),
            "checks": [{"route_key": "home", "viewport": profile, "state_id": "rest", "pass": True} for profile in ("wide", "narrow")],
            "visible_decision_reconciliation": reconciliation,
            "implementation_snapshot": {"algorithm": "sha256-files-v1", "files": inventory, "sha256": legacy._digest(inventory)},
        })

    @staticmethod
    def map_validator(mapping: dict) -> list[str]:
        return ["required source observation incomplete"] if mapping.get("blocked") else []

    @staticmethod
    def scan_validator(scan: dict, _mapping: dict) -> list[str]:
        return ["rendered media/focus evidence incomplete"] if scan.get("blocked") else []

    def begin(self, **overrides) -> dict:
        return legacy.begin_legacy_maintenance(self.project, **{
            "planned_source_map": self.planned_path, "baseline_scan": self.old_scan_path,
            "planned_changes": self.changes, "validate_mapping": self.map_validator,
            "validate_scan": self.scan_validator, **overrides,
        })

    def check(self, authorization: dict, **overrides) -> list[str]:
        return legacy.legacy_maintenance_failures(self.project, authorization, self.planned, **{
            "validate_mapping": self.map_validator, "validate_scan": self.scan_validator, **overrides,
        })

    def edit_and_scan(self, authorization: dict) -> Path:
        self.planned["construction_authorization"] = authorization
        write(self.current_map_path, self.planned)
        (self.project / "site.html").write_text("<h1>Measured new source heading arrangement</h1>", encoding="utf-8")
        return self.make_scan(self.planned, "final-scan.json", "2026-09-04T02:00:00Z")

    def test_compliant_existing_baseline_and_scoped_delta_preserve_honest_history(self) -> None:
        authorization = self.begin()
        record_path = self.project / authorization["entry_path"]
        baseline_bytes = record_path.read_bytes()
        self.assertEqual([], self.check(authorization))
        final_scan = self.edit_and_scan(authorization)
        self.assertEqual([], self.check(authorization, current_scan=final_scan, require_complete_delta=True))
        self.assertEqual(baseline_bytes, record_path.read_bytes())
        record = json.loads(baseline_bytes)
        self.assertEqual("existing-history-unverified", record["history_status"])
        self.assertFalse(record["retroactive_precode_claim"])
        self.assertFalse(record["owner_approved"])
        self.assertFalse(record["public_readiness"])

    def test_incomplete_existing_mapping_cannot_be_blessed_by_baseline(self) -> None:
        self.old_map["blocked"] = True
        write(self.current_map_path, self.old_map)
        with self.assertRaisesRegex(legacy.MaintenanceError, "source observation incomplete"):
            self.begin()

    def test_validator_callbacks_are_required_not_boolean(self) -> None:
        with self.assertRaisesRegex(legacy.MaintenanceError, "boolean"):
            self.begin(validate_mapping=True)

    def test_partial_scan_and_unmapped_decision_cannot_authorize(self) -> None:
        data = json.loads(self.old_scan_path.read_text())
        data["checks"] = data["checks"][:1]
        write(self.old_scan_path, data)
        with self.assertRaisesRegex(legacy.MaintenanceError, "full-route"):
            self.begin()

    def test_mutable_standard_gate_census_cannot_be_a_maintenance_baseline(self) -> None:
        canonical = self.project / ".design-dna/evidence/component-census.json"
        canonical.write_bytes(self.old_scan_path.read_bytes())
        with self.assertRaisesRegex(legacy.MaintenanceError, "maintenance-baselines/<unique-id>"):
            self.begin(baseline_scan=canonical)

    def test_source_changed_after_old_browser_scan_is_rejected(self) -> None:
        (self.project / "footer.css").write_text("footer { padding: 999px }", encoding="utf-8")
        with self.assertRaisesRegex(legacy.MaintenanceError, "implementation file snapshot"):
            self.begin()

    def test_extra_file_addition_is_rejected_even_inside_declared_parent(self) -> None:
        authorization = self.begin()
        (self.project / "extra.html").write_text("<section>Unplanned page</section>", encoding="utf-8")
        self.assertIn("extra.html", " ".join(self.check(authorization)))

    def test_undeclared_existing_file_edit_is_rejected(self) -> None:
        authorization = self.begin()
        (self.project / "footer.css").write_text("footer { padding: 1px }", encoding="utf-8")
        self.assertIn("footer.css", " ".join(self.check(authorization)))

    def test_changed_component_outside_declared_touch_scope_is_rejected(self) -> None:
        self.planned["decisions"][1]["measured_padding"] = 50
        write(self.planned_path, self.planned)
        with self.assertRaisesRegex(legacy.MaintenanceError, "undeclared component"):
            self.begin()

    def test_allowed_file_cannot_hide_unplanned_source_map_revision(self) -> None:
        authorization = self.begin()
        self.planned["decisions"][0]["measured_size"] = 80
        self.assertIn("frozen before editing", " ".join(self.check(authorization)))

    def test_route_expansion_is_not_scoped_maintenance(self) -> None:
        self.planned["route_manifest"]["sha256"] = "a" * 64
        write(self.planned_path, self.planned)
        with self.assertRaisesRegex(legacy.MaintenanceError, "route manifest"):
            self.begin()

    def test_bad_file_scope_and_operation_fail_before_editing(self) -> None:
        for path, operation in (("../outside.css", "add"), (".", "add"), ("*.html", "modify"), (".design-dna/audit.json", "add"), ("site.html", "add")):
            with self.subTest(path=path, operation=operation), self.assertRaises(legacy.MaintenanceError):
                self.begin(planned_changes=[{"path": path, "operation": operation, "component_ids": ["hero-heading"]}])

    def test_baseline_create_only_and_drift_detection(self) -> None:
        fixed = self.project / ".design-dna/evidence/legacy-maintenance/fixed.json"
        authorization = self.begin(output_path=fixed)
        with self.assertRaises(FileExistsError):
            self.begin(output_path=fixed)
        data = json.loads(fixed.read_text())
        data["history_status"] = "fresh-precode"
        write(fixed, data)
        self.assertIn("baseline bytes drifted", " ".join(self.check(authorization)))

    def test_scope_check_cannot_be_reported_as_final_without_new_full_scan(self) -> None:
        authorization = self.begin()
        self.edit_and_scan(authorization)
        self.assertIn("fresh full rendered", " ".join(self.check(authorization, require_complete_delta=True)))

    def test_baseline_scan_cannot_be_reused_as_final_scan(self) -> None:
        authorization = self.begin()
        self.edit_and_scan(authorization)
        self.assertIn("reuse its old rendered census", " ".join(self.check(authorization, current_scan=self.old_scan_path, require_complete_delta=True)))

    def test_final_scan_does_not_cover_post_scan_edits(self) -> None:
        authorization = self.begin()
        final_scan = self.edit_and_scan(authorization)
        (self.project / "site.html").write_text("<h1>Edited after rendered audit</h1>", encoding="utf-8")
        self.assertIn("implementation file snapshot", " ".join(self.check(authorization, current_scan=final_scan, require_complete_delta=True)))

    def test_rendered_failure_callback_is_not_overridden_by_pass_flag(self) -> None:
        data = json.loads(self.old_scan_path.read_text())
        data["blocked"] = True
        write(self.old_scan_path, data)
        with self.assertRaisesRegex(legacy.MaintenanceError, "media/focus evidence incomplete"):
            self.begin()

    def test_final_audit_must_follow_existing_baseline_audit(self) -> None:
        authorization = self.begin()
        final_scan = self.edit_and_scan(authorization)
        data = json.loads(final_scan.read_text())
        data["scanned_at"] = "2026-09-04T00:00:00Z"
        write(final_scan, data)
        self.assertIn("does not follow", " ".join(self.check(authorization, current_scan=final_scan, require_complete_delta=True)))

    def test_javascript_and_python_file_snapshots_match_including_unicode_and_compiled_files(self) -> None:
        for relative in ("dist/index.html", "nested/אב.html", "nested/\U0001f680.html", "nested/\ue000.html"):
            file = self.project / relative
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text("source bytes " + relative, encoding="utf-8")
        ignored = self.project / "node_modules/package/index.js"
        ignored.parent.mkdir(parents=True)
        ignored.write_text("dependency", encoding="utf-8")
        python_files = legacy.implementation_snapshot(self.project)
        code = "import {snapshotImplementation} from " + json.dumps((SCRIPTS / "implementation_snapshot.mjs").as_uri()) + "; console.log(JSON.stringify(snapshotImplementation(process.argv[1])));"
        completed = subprocess.run(["node", "--input-type=module", "-e", code, str(self.project)], capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual(0, completed.returncode, completed.stderr)
        javascript = json.loads(completed.stdout)
        self.assertEqual({"algorithm": "sha256-files-v1", "files": python_files, "sha256": legacy._digest(python_files)}, javascript)

    def test_malformed_scan_time_cannot_look_newer_lexicographically(self) -> None:
        authorization = self.begin()
        final_scan = self.edit_and_scan(authorization)
        data = json.loads(final_scan.read_text())
        data["scanned_at"] = "zzzz"
        write(final_scan, data)
        self.assertIn("timezone-aware", " ".join(self.check(authorization, current_scan=final_scan, require_complete_delta=True)))

    def test_root_project_lock_does_not_change_python_or_javascript_inventory(self) -> None:
        spec = importlib.util.spec_from_file_location("maintenance_lock_validator", SCRIPTS / "init_project_state.py")
        validator = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = validator
        self.addCleanup(sys.modules.pop, spec.name, None)
        spec.loader.exec_module(validator)
        nested = self.project / "nested/.design-dna.lock"
        nested.parent.mkdir()
        nested.write_text("A nested name remains ordinary source data.", encoding="utf-8")
        before = legacy.implementation_snapshot(self.project)
        code = "import {snapshotImplementation} from " + json.dumps((SCRIPTS / "implementation_snapshot.mjs").as_uri()) + "; console.log(JSON.stringify(snapshotImplementation(process.argv[1])));"
        def assert_parity():
            python_files = legacy.implementation_snapshot(self.project)
            self.assertEqual(before, python_files)
            completed = subprocess.run(["node", "--input-type=module", "-e", code, str(self.project)], capture_output=True, text=True, encoding="utf-8", timeout=30)
            self.assertEqual(0, completed.returncode, completed.stderr)
            javascript = json.loads(completed.stdout)
            self.assertEqual({"algorithm": "sha256-files-v1", "files": before, "sha256": legacy._digest(before)}, javascript)
            self.assertIn("nested/.design-dna.lock", [item["path"] for item in before])
            self.assertNotIn(".design-dna.lock", [item["path"] for item in before])
        with validator.ProjectMutationLock(self.project, "maintenance-snapshot-test", timeout=1):
            assert_parity()
        assert_parity()

    def test_cloud_hydration_tags_match_runtime_without_allowing_name_surrogates(self) -> None:
        spec = importlib.util.spec_from_file_location("maintenance_reparse_validator", SCRIPTS / "init_project_state.py")
        validator = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = validator
        self.addCleanup(sys.modules.pop, spec.name, None)
        spec.loader.exec_module(validator)
        for tag, blocked in ((0x9000001A, False), (0x9000101A, False), (0xA0000003, True), (0xA000000C, True), (0, True)):
            info = SimpleNamespace(st_mode=stat.S_IFREG | 0o644, st_file_attributes=0x400, st_reparse_tag=tag)
            with self.subTest(tag=hex(tag)), patch.object(Path, "lstat", return_value=info):
                self.assertEqual(blocked, legacy._reparse(self.project / "source.html"))
                self.assertEqual(blocked, validator.is_reparse(self.project / "source.html"))

    def test_hardlinked_artifacts_cannot_alias_external_mutable_bytes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="dna-maintenance-external-") as external:
            outside = Path(external) / "source.css"
            outside.write_text("outside mutable source", encoding="utf-8")
            linked = self.project / "linked.css"
            os.link(outside, linked)
            with self.assertRaisesRegex(legacy.MaintenanceError, "hardlink"):
                legacy._binding(self.project, linked)
            with self.assertRaisesRegex(legacy.MaintenanceError, "hardlink"):
                legacy.implementation_snapshot(self.project)
            code = "import {snapshotImplementation} from " + json.dumps((SCRIPTS / "implementation_snapshot.mjs").as_uri()) + "; snapshotImplementation(process.argv[1]);"
            completed = subprocess.run(["node", "--input-type=module", "-e", code, str(self.project)], capture_output=True, text=True, encoding="utf-8", timeout=30)
            self.assertNotEqual(0, completed.returncode)
            self.assertIn("hardlink", completed.stderr.lower())

    def test_scan_time_compares_actual_instants_across_offset_representations(self) -> None:
        authorization = self.begin()
        final_scan = self.edit_and_scan(authorization)
        data = json.loads(final_scan.read_text())
        # 00:30 at UTC-02 is 02:30Z, after the 01:00Z baseline.
        data["scanned_at"] = "2026-09-04T00:30:00-02:00"
        write(final_scan, data)
        self.assertEqual([], self.check(authorization, current_scan=final_scan, require_complete_delta=True))
        # 02:00 at UTC+02 is 00:00Z, before that baseline despite its text.
        data["scanned_at"] = "2026-09-04T02:00:00+02:00"
        write(final_scan, data)
        self.assertIn("does not follow", " ".join(self.check(authorization, current_scan=final_scan, require_complete_delta=True)))


if __name__ == "__main__":
    unittest.main()
