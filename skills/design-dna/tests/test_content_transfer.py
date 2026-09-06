"""Truthful copy adaptation and source section connections remain pre-code authority."""
import hashlib
import importlib.util
import json
import os
import subprocess
import stat
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
SPEC = importlib.util.spec_from_file_location("content_transfer_test_module", SCRIPTS / "content_transfer.py")
CONTENT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTENT)

def write(project, relative, payload):
    file = project / relative
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(payload), encoding="utf-8")
    return {"path": relative, "sha256": hashlib.sha256(file.read_bytes()).hexdigest()}

class ContentTransferTests(unittest.TestCase):
    def test_cloud_hydration_does_not_bypass_or_impersonate_a_redirecting_reparse_tag(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            file = project / "brief.md"
            file.write_text("Current authority", encoding="utf-8")
            binding = {"path": "brief.md", "sha256": hashlib.sha256(file.read_bytes()).hexdigest()}
            for tag, blocked in ((0x9000001A, False), (0x9000101A, False), (0xA0000003, True), (0xA000000C, True), (0, True)):
                info = SimpleNamespace(st_mode=stat.S_IFREG | 0o644, st_file_attributes=0x400, st_reparse_tag=tag)
                with self.subTest(tag=hex(tag)), patch.object(Path, "lstat", return_value=info):
                    if blocked:
                        with self.assertRaises(ValueError): CONTENT.read_bound(project, binding)
                    else:
                        self.assertEqual(file, CONTENT.read_bound(project, binding))

    def test_bound_content_rejects_hardlink_to_external_mutable_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            project.mkdir()
            external = root / "external.md"
            external.write_text("External mutable authority", encoding="utf-8")
            os.link(external, project / "linked.md")
            binding = {"path": "linked.md", "sha256": hashlib.sha256(external.read_bytes()).hexdigest()}
            with self.assertRaisesRegex(ValueError, "hardlinks"):
                CONTENT.read_bound(project, binding)

    def test_bound_content_rejects_linked_ancestor_before_resolving_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "project"
            project.mkdir()
            external = root / "external"
            external.mkdir()
            file = external / "brief.md"
            file.write_text("Private external authority", encoding="utf-8")
            try:
                os.symlink(external, project / "linked", target_is_directory=True)
            except OSError as exc:
                if os.name != "nt":
                    raise
                environment = dict(os.environ, DNA_TEST_JUNCTION_LINK=str(project / "linked"), DNA_TEST_JUNCTION_TARGET=str(external))
                made = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                    "New-Item -ItemType Junction -Path $env:DNA_TEST_JUNCTION_LINK -Target $env:DNA_TEST_JUNCTION_TARGET"],
                    env=environment, capture_output=True, text=True, timeout=15)
                self.assertEqual(0, made.returncode, f"Cannot create linked-ancestor fixture: {exc}; {made.stderr}")
            with self.assertRaisesRegex(ValueError, "symlink/reparse"):
                CONTENT.read_bound(project, {"path": "linked/brief.md", "sha256": hashlib.sha256(file.read_bytes()).hexdigest()})

    def test_bound_content_rejects_absolute_and_parent_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            file = project / "brief.md"
            file.write_text("Current authority", encoding="utf-8")
            for path in (str(file), "../brief.md", "./brief.md", "C:brief.md", "C:/brief.md"):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    CONTENT.read_bound(project, {"path": path, "sha256": hashlib.sha256(file.read_bytes()).hexdigest()})

    def fixture(self, project):
        authority = project / ".design-dna" / "brief.md"
        authority.parent.mkdir()
        authority.write_text("Approved public heading: Welcome to our neighborhood", encoding="utf-8")
        authority_binding = {"path": ".design-dna/brief.md", "sha256": hashlib.sha256(authority.read_bytes()).hexdigest()}
        styles = write(project, ".design-dna/references/strong-1-styles.json", {"component_styles": [{
            "selector": "#opening-title", "component_key": "id:opening-title", "profile": profile, "state_id": "rest",
            "content_facts": {"text": "A different source organization", "tag": "h1", "role": None, "line_count": lines,
                              "parent_selector": "body", "parent_tag": "body", "previous_selector": None},
        } for profile, lines in (("wide", 1), ("narrow", 2))]})
        mapping = {"decisions": [{"decision_id": "heading", "component_id": "heading",
            "source_mapping": {"id": "strong-1", "source_selector": "#opening-title"},
            "style_provenance": {"record": styles}, "bindings": [{"route_key": "home", "viewport": profile,
                "state_id": "rest", "source_state": {"id": "rest"}} for profile in ("wide", "narrow")]}]}
        plan = {"schema_version": 1, "record_type": "design-dna-content-transfer", "decisions": [{
            "decision_id": "heading", "target_text": "Welcome to our neighborhood", "authority": authority_binding,
            "parent_decision_id": None, "previous_decision_id": None, "arrangement_source": None}]}
        mapping["content_transfer"] = write(project, ".design-dna/content-transfer.json", plan)
        census = {"checks": [{"route_key": "home", "viewport": profile, "state_id": "rest", "decision_roots": [{
            "decision_id": "heading", "roots": [{"content_facts": {"text": "Welcome to our neighborhood", "tag": "h1", "role": None,
                "line_count": lines, "parent_component": None, "previous_component": None}}]}]} for profile, lines in (("wide", 1), ("narrow", 2))]}
        return mapping, plan, census

    def test_different_truthful_words_can_preserve_source_copy_role_and_rhythm(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            mapping, _plan, census = self.fixture(project)
            self.assertEqual([], CONTENT.content_transfer_failures(project, mapping))
            self.assertEqual([], CONTENT.content_transfer_failures(project, mapping, census))

    def test_unapproved_copy_and_new_heading_level_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            mapping, plan, census = self.fixture(project)
            plan["decisions"][0]["target_text"] = "We are the largest organization in America"
            mapping["content_transfer"] = write(project, ".design-dna/content-transfer.json", plan)
            findings = CONTENT.content_transfer_failures(project, mapping, census)
            self.assertTrue(any("absent from the current project authority" in value for value in findings), findings)
            census["checks"][0]["decision_roots"][0]["roots"][0]["content_facts"]["tag"] = "h2"
            findings = CONTENT.content_transfer_failures(project, mapping, census)
            self.assertTrue(any("semantic role" in value for value in findings), findings)

    def test_unplanned_section_connection_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            mapping, _plan, census = self.fixture(project)
            census["checks"][0]["decision_roots"][0]["roots"][0]["content_facts"]["previous_component"] = "invented-promo-band"
            findings = CONTENT.content_transfer_failures(project, mapping, census)
            self.assertTrue(any("previous_decision_id" in value for value in findings), findings)

    def test_later_sidecar_edits_cannot_change_frozen_intent(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            mapping, plan, _census = self.fixture(project)
            plan["decisions"][0]["target_text"] = "Post-hoc rewrite"
            write(project, ".design-dna/content-transfer.json", plan)
            self.assertTrue(any("changed" in value for value in CONTENT.content_transfer_failures(project, mapping)))

    def test_source_facts_and_missing_sidecar_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            mapping, _plan, _census = self.fixture(project)
            mapping.pop("content_transfer")
            self.assertTrue(any("missing or invalid" in value for value in CONTENT.content_transfer_failures(project, mapping)))

    def test_immutable_content_plans_can_coexist_before_maintenance(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            mapping, plan, census = self.fixture(project)
            file = project / mapping["content_transfer"]["path"]
            immutable = project / ".design-dna/content-transfers" / (mapping["content_transfer"]["sha256"] + ".json")
            immutable.parent.mkdir()
            immutable.write_bytes(file.read_bytes())
            mapping["content_transfer"]["path"] = immutable.relative_to(project).as_posix()
            write(project, ".design-dna/content-transfer.json", {**plan, "decisions": []})
            self.assertEqual([], CONTENT.content_transfer_failures(project, mapping, census))

if __name__ == "__main__":
    unittest.main()
