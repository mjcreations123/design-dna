"""Generated authorization updates its exact dossier digest without changing intent."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

TESTS = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("activation_construction_fixture", TESTS / "test_construction_fidelity.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
INIT = fixture.load_initializer()


class BindingActivationTests(unittest.TestCase):
    def prepare(self, root):
        return fixture.ConstructionJournalTests().base(root)

    def begin(self, root, manifest, dossier, visible, payload):
        with INIT.ProjectMutationLock(root, "activation-test"):
            return INIT.begin_construction_journal(root, manifest_path=manifest, dossier_path=dossier,
                                                   visible_path=visible, visible_payload=payload)

    def test_begin_updates_digest_and_preserves_the_frozen_dossier_core(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, dossier, visible, payload = self.prepare(root)
            old_core = INIT.dossier_core_sha256(dossier)
            old_bytes = dossier.read_bytes()
            result = self.begin(root, manifest, dossier, visible, payload)
            digest = hashlib.sha256(visible.read_bytes()).hexdigest()
            self.assertEqual("began-construction", result["action"])
            self.assertIn(".design-dna/visible-decision-sources.json plus sha256:" + digest, dossier.read_text(encoding="utf-8"))
            self.assertEqual(old_core, INIT.dossier_core_sha256(dossier))
            self.assertNotEqual(old_bytes, dossier.read_bytes())
            current = json.loads(visible.read_text(encoding="utf-8"))
            with self.assertRaises(INIT.StateError) as error:
                self.begin(root, manifest, dossier, visible, current)
            self.assertEqual("construction-journal-already-begun", error.exception.code)

    def test_second_write_failure_rolls_back_both_files_and_recovers_existing_journal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, dossier, visible, payload = self.prepare(root)
            original = (visible.read_bytes(), dossier.read_bytes())
            replace = INIT.atomic_replace_bytes
            def fail_dossier(path, content, **options):
                if path == dossier:
                    raise OSError("simulated write denial")
                return replace(path, content, **options)
            with patch.object(INIT, "atomic_replace_bytes", side_effect=fail_dossier):
                with self.assertRaises(OSError):
                    self.begin(root, manifest, dossier, visible, payload)
            self.assertEqual(original, (visible.read_bytes(), dossier.read_bytes()))
            journal = list((root / ".design-dna/evidence/construction-journal").glob("*.json"))
            self.assertEqual(1, len(journal))
            recovered = self.begin(root, manifest, dossier, visible, payload)
            self.assertEqual("recovered-construction-authorization", recovered["action"])
            self.assertEqual(journal, list(journal[0].parent.glob("*.json")))
            self.assertIn(hashlib.sha256(visible.read_bytes()).hexdigest(), dossier.read_text(encoding="utf-8"))

    def test_process_crash_after_map_replace_recovers_digest_without_new_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, dossier, visible, payload = self.prepare(root)
            old_core, old_dossier = INIT.dossier_core_sha256(dossier), dossier.read_bytes()
            replace = INIT.atomic_replace_bytes
            def crash_dossier(path, content, **options):
                if path == dossier:
                    raise KeyboardInterrupt("simulated process interruption")
                return replace(path, content, **options)
            with patch.object(INIT, "atomic_replace_bytes", side_effect=crash_dossier):
                with self.assertRaises(KeyboardInterrupt):
                    self.begin(root, manifest, dossier, visible, payload)
            self.assertEqual(old_dossier, dossier.read_bytes())
            current = json.loads(visible.read_text(encoding="utf-8"))
            auth = current["construction_authorization"]
            recovered = self.begin(root, manifest, dossier, visible, current)
            self.assertEqual("recovered-construction-authorization", recovered["action"])
            self.assertEqual(auth, json.loads(visible.read_text(encoding="utf-8"))["construction_authorization"])
            self.assertEqual(old_core, INIT.dossier_core_sha256(dossier))
            self.assertIn(hashlib.sha256(visible.read_bytes()).hexdigest(), dossier.read_text(encoding="utf-8"))

    def test_duplicate_wrong_path_and_missing_binding_fail_before_creating_journal(self):
        for defect in ("duplicate", "wrong-path", "missing"):
            with self.subTest(defect=defect), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                manifest, dossier, visible, payload = self.prepare(root)
                body = dossier.read_text(encoding="utf-8")
                if defect == "duplicate": body += body.splitlines()[-1] + "\n"
                elif defect == "wrong-path": body = body.replace(".design-dna/visible-decision-sources.json", ".design-dna/alternate.json")
                else: body = "# Dossier without binding\n"
                dossier.write_text(body, encoding="utf-8")
                before = visible.read_bytes()
                with self.assertRaises(INIT.StateError):
                    self.begin(root, manifest, dossier, visible, payload)
                self.assertEqual(before, visible.read_bytes())
                self.assertFalse((root / ".design-dna/evidence/construction-journal").exists())

    def test_hardlinked_authority_target_is_rejected_without_touching_its_peer(self):
        for target_name in ("map", "dossier"):
            with self.subTest(target=target_name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / "project"
                root.mkdir()
                manifest, dossier, visible, payload = self.prepare(root)
                target = visible if target_name == "map" else dossier
                peer = Path(directory) / "external-authority"
                os.link(target, peer)
                before = peer.read_bytes()
                with self.assertRaises(INIT.StateError) as error:
                    self.begin(root, manifest, dossier, visible, payload)
                self.assertEqual("construction-activation-target-unsafe", error.exception.code)
                self.assertEqual(before, peer.read_bytes())

    def test_generated_digest_edit_preserves_crlf_and_nonbinding_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _manifest, dossier, visible, payload = self.prepare(root)
            dossier.write_bytes(dossier.read_bytes().replace(b"\n", b"\r\n"))
            old = dossier.read_bytes()
            payload["construction_authorization"]["journal_id"] = "generated-test-token"
            with INIT.ProjectMutationLock(root, "activation-test"):
                INIT.activate_construction_binding(root, visible_path=visible, dossier_path=dossier, payload=payload)
            updated = dossier.read_bytes()
            self.assertEqual(old.count(b"\r\n"), updated.count(b"\r\n"))
            self.assertEqual(len(old), len(updated))
            old_digest = old.split(b"sha256:")[-1].split()[0]
            new_digest = hashlib.sha256(visible.read_bytes()).hexdigest().encode()
            self.assertEqual(old.replace(old_digest, new_digest), updated)

    def test_maintenance_activates_digest_and_recovers_both_interruption_points(self):
        spec = importlib.util.spec_from_file_location("activation_maintenance_fixture", TESTS / "test_legacy_maintenance.py")
        legacy_fixtures = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(legacy_fixtures)
        spec = importlib.util.spec_from_file_location("activation_maintenance_workflow", TESTS.parent / "scripts/maintenance_workflow.py")
        workflow = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(workflow)
        # These synthetic scanner envelopes test transaction activation; the
        # source/census policy is independently covered by its strict suites.
        for interrupted in (None, "before-map", "before-dossier"):
            with self.subTest(interrupted=interrupted):
                context = legacy_fixtures.LegacyMaintenanceTests()
                context.setUp()
                try:
                    root, visible = context.project, context.current_map_path
                    dossier = root / ".design-dna/reference-dossier.md"
                    dossier.write_text("# Scoped source research\n- Visible decision source manifest: .design-dna/visible-decision-sources.json plus sha256:" +
                                       hashlib.sha256(visible.read_bytes()).hexdigest() + "\n", encoding="utf-8")
                    plan = root / ".design-dna/maintenance-plan.json"
                    plan.write_text(json.dumps({"schema_version": 1, "planned_source_map": context.planned_path.relative_to(root).as_posix(),
                        "baseline_census": context.old_scan_path.relative_to(root).as_posix(), "planned_changes": context.changes}), encoding="utf-8")
                    core = INIT.dossier_core_sha256(dossier)
                    with patch.object(workflow, "_context", return_value=(context.manifest_path, dossier, context.map_validator, context.scan_validator)):
                        if interrupted:
                            replace = INIT.atomic_replace_bytes
                            def interrupt(path, content, **options):
                                if path == (visible if interrupted == "before-map" else dossier):
                                    raise KeyboardInterrupt("simulated process interruption")
                                return replace(path, content, **options)
                            with INIT.ProjectMutationLock(root, "activation-maintenance-test"), patch.object(INIT, "atomic_replace_bytes", side_effect=interrupt):
                                with self.assertRaises(KeyboardInterrupt): workflow.begin(root, plan, INIT)
                        with INIT.ProjectMutationLock(root, "activation-maintenance-test"):
                            result = workflow.begin(root, plan, INIT)
                    self.assertEqual("recovered-scoped-maintenance" if interrupted else "began-scoped-maintenance", result["action"])
                    self.assertEqual(core, INIT.dossier_core_sha256(dossier))
                    self.assertIn(hashlib.sha256(visible.read_bytes()).hexdigest(), dossier.read_text(encoding="utf-8"))
                    self.assertEqual(1, len(list((root / ".design-dna/evidence/legacy-maintenance").glob("legacy-*.json"))))
                    self.assertEqual("existing-history-unverified", result["history_status"])
                    self.assertFalse(result["public_readiness"])
                finally:
                    context.doCleanups()


if __name__ == "__main__": unittest.main()
