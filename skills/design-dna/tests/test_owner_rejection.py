#!/usr/bin/env python3
"""Regression tests for the packaged owner-rejection evidence contract."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SKILL = Path(__file__).resolve().parents[1]
AUDITOR_PATH = SKILL / "scripts" / "owner_rejection_audit.py"
SCHEMA_PATH = SKILL / "schemas" / "owner-rejection.schema.json"
TEMPLATE_PATH = SKILL / "templates" / "owner-rejection-template.json"


def load_auditor():
    specification = importlib.util.spec_from_file_location(
        "design_dna_owner_rejection_audit",
        AUDITOR_PATH,
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


AUDITOR = load_auditor()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rejection_fixture(project: Path) -> dict:
    public = project / "site"
    evidence = project / ".design-dna" / "owner-evidence"
    public.mkdir(parents=True)
    (public / "assets").mkdir()
    evidence.mkdir(parents=True)
    (public / "index.html").write_text(
        "<!doctype html><title>Rejected candidate</title>\n",
        encoding="utf-8",
    )
    (public / "assets" / "styles.css").write_text(
        "body { color: #111; }\n",
        encoding="utf-8",
    )
    excerpt = (
        "Same boring website, same fonts, same shapes, same effects, "
        "same shadows, same everything. Also, there are no photos on the website."
    )
    decision = evidence / "owner-rejection.txt"
    decision.write_text(
        "First-party owner decision\n\n" + excerpt + "\n",
        encoding="utf-8",
    )
    entries, _ = AUDITOR.public_tree_manifest(public)
    manifest_sha256 = AUDITOR.manifest_digest(entries)
    return {
        "schema_version": 1,
        "created_with": "design-dna-test",
        "classification": "internal",
        "status": "active-reopen",
        "recorded_at": "2026-08-23T12:00:00-04:00",
        "accountable_owner": {
            "id": "motty-mjs-studio",
            "display_name": "Motty (MJ's Studio)",
            "authority_basis": "Owner commissioning and accepting the public website candidate.",
        },
        "candidate": {
            "project_relative_root": "site",
            "manifest_algorithm": "sha256-tab-lf-v1",
            "manifest_sha256": manifest_sha256,
            "files": entries,
        },
        "owner_evidence": {
            "file": {
                "path": ".design-dna/owner-evidence/owner-rejection.txt",
                "sha256": digest(decision),
            },
            "authority": {
                "accountable_owner_id": "motty-mjs-studio",
                "relationship": "accountable-owner",
                "first_party": True,
                "decision_kind": "candidate-rejection",
            },
            "verbatim_excerpt": excerpt,
            "scope": "The visual premise and its propagation across the exact rejected public candidate.",
            "acceptance_status": "rejected",
        },
        "rejected_relationship_cluster": {
            "scope": "Only the public relationship cluster in the candidate bound by this manifest.",
            "applies_to_candidate_manifest_sha256": manifest_sha256,
            "observations": {
                "type_posture": "Huge compressed display type supplies nearly all hierarchy and drama in this candidate.",
                "cta_grammar": "Square black action blocks repeat across the candidate routes.",
                "material_and_media": "The physical product subject has no photography in this candidate.",
            },
        },
        "protected_foundations": [
            "Truthful OTC and Drug Facts guidance",
            "Accessible labels and keyboard behavior",
        ],
        "reopened_decisions": [
            "Material and photography strategy",
            "Typography posture and hierarchy",
        ],
        "replacement_constraints": {
            "asset_led_required": True,
            "photo_free_exception_available": False,
            "minimum_evidence": "Two materially incompatible wide and narrow proof directions plus an independent unprimed review.",
            "closure": "The record remains active until the accountable owner accepts a different hash-bound replacement.",
        },
        "resolution": {
            "status": "pending",
            "resolved_at": None,
            "replacement_candidate_manifest_sha256": None,
            "owner_evidence": None,
        },
    }


def codes(report: dict) -> set[str]:
    return {entry["code"] for entry in report["findings"]}


class OwnerRejectionAuditTests(unittest.TestCase):
    def test_packaged_schema_and_truthful_template_are_aligned(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        template = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            "https://json-schema.org/draft/2020-12/schema",
            schema["$schema"],
        )
        self.assertEqual(AUDITOR.ROOT_FIELDS, set(schema["required"]))
        self.assertEqual([], AUDITOR.runtime_schema_errors())
        with tempfile.TemporaryDirectory() as temporary:
            report = AUDITOR.audit_payload(Path(temporary), template)
        self.assertTrue(report["structural_valid"], report)
        self.assertFalse(report["ready"])
        self.assertEqual("draft", report["lifecycle"]["status"])
        self.assertEqual(["truthful-draft"], [gap["code"] for gap in report["gaps"]])
        self.assertIsNone(template["owner_evidence"]["file"])
        self.assertIsNone(template["replacement_constraints"]["asset_led_required"])

    def test_canonical_manifest_algorithm_is_stable_and_explicit(self) -> None:
        entries = [
            {"path": "b.txt", "sha256": "b" * 64},
            {"path": "a.txt", "sha256": "a" * 64},
        ]
        canonical = (
            "a.txt\t" + "a" * 64 + "\n"
            "b.txt\t" + "b" * 64 + "\n"
        ).encode("utf-8")
        self.assertEqual(canonical, AUDITOR.canonical_manifest_bytes(entries))
        self.assertEqual(hashlib.sha256(canonical).hexdigest(), AUDITOR.manifest_digest(entries))

    def test_active_reopen_record_verifies_exact_tree_and_first_party_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = rejection_fixture(project)
            report = AUDITOR.audit_payload(project, contract)
        self.assertTrue(report["structural_valid"], report)
        self.assertTrue(report["ready"], report)
        self.assertEqual([], report["findings"])
        self.assertEqual(
            ["rejected-public-tree", "owner-rejection"],
            [entry["kind"] for entry in report["evidence"]["verified"]],
        )

    def test_manifest_digest_is_recomputed_from_declared_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = rejection_fixture(project)
            contract["candidate"]["manifest_sha256"] = "0" * 64
            contract["rejected_relationship_cluster"]["applies_to_candidate_manifest_sha256"] = "0" * 64
            report = AUDITOR.audit_payload(project, contract)
        self.assertFalse(report["ready"])
        self.assertIn("manifest-digest-mismatch", codes(report))

    def test_changed_public_file_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = rejection_fixture(project)
            (project / "site" / "index.html").write_text(
                "<!doctype html><title>Tampered</title>\n",
                encoding="utf-8",
            )
            report = AUDITOR.audit_payload(project, contract)
        self.assertFalse(report["ready"])
        self.assertIn("public-tree-hash-mismatch", codes(report))

    def test_unlisted_public_file_fails_exact_tree_check(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = rejection_fixture(project)
            (project / "site" / "unlisted.html").write_text(
                "unlisted\n",
                encoding="utf-8",
            )
            report = AUDITOR.audit_payload(project, contract)
        self.assertFalse(report["ready"])
        self.assertIn("public-tree-entry-mismatch", codes(report))

    def test_tampered_owner_evidence_hash_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = rejection_fixture(project)
            evidence = project / contract["owner_evidence"]["file"]["path"]
            evidence.write_text("rewritten decision\n", encoding="utf-8")
            report = AUDITOR.audit_payload(project, contract)
        self.assertFalse(report["ready"])
        self.assertIn("owner-evidence-hash-mismatch", codes(report))

    def test_excerpt_must_be_verbatim_in_hash_bound_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = rejection_fixture(project)
            contract["owner_evidence"]["verbatim_excerpt"] = "A paraphrase that is not in the source."
            report = AUDITOR.audit_payload(project, contract)
        self.assertFalse(report["ready"])
        self.assertIn("owner-excerpt-not-found", codes(report))

    def test_owner_authority_must_be_first_party_and_match_accountable_owner(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = rejection_fixture(project)
            contract["owner_evidence"]["authority"]["first_party"] = False
            contract["owner_evidence"]["authority"]["accountable_owner_id"] = "another-person"
            report = AUDITOR.audit_payload(project, contract)
        self.assertFalse(report["structural_valid"])
        self.assertFalse(report["ready"])
        self.assertIn("not-first-party", codes(report))
        self.assertIn("owner-mismatch", codes(report))

    def test_relationship_observation_cannot_become_a_global_style_ban(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = rejection_fixture(project)
            contract["rejected_relationship_cluster"]["observations"]["type_posture"] = (
                "Never use serif fonts on any future website."
            )
            report = AUDITOR.audit_payload(project, contract)
        self.assertFalse(report["structural_valid"])
        self.assertFalse(report["ready"])
        self.assertIn("global-style-ban", codes(report))

    def test_unknown_axis_or_top_level_field_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = rejection_fixture(project)
            contract["global_style_bans"] = ["serif"]
            report = AUDITOR.audit_payload(project, contract)
            self.assertFalse(report["structural_valid"])
            self.assertIn("unknown-field", codes(report))

            del contract["global_style_bans"]
            contract["rejected_relationship_cluster"]["observations"]["font_ban"] = "Serif"
            axis_report = AUDITOR.audit_payload(project, contract)
        self.assertFalse(axis_report["structural_valid"])
        self.assertIn("unknown-axis", codes(axis_report))

    def test_replacement_media_constraints_are_nested_and_typed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = rejection_fixture(project)
            contract["replacement_constraints"]["asset_led_required"] = "yes"
            contract["replacement_constraints"]["photo_free_exception_available"] = 0
            report = AUDITOR.audit_payload(project, contract)
        self.assertFalse(report["structural_valid"])
        self.assertGreaterEqual(sum(1 for entry in report["findings"] if entry["code"] == "wrong-type"), 2)

    def test_resolved_lifecycle_requires_separate_owner_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = rejection_fixture(project)
            contract["status"] = "resolved"
            report = AUDITOR.audit_payload(project, contract)
        self.assertFalse(report["structural_valid"])
        self.assertFalse(report["ready"])
        self.assertIn("lifecycle-mismatch", codes(report))

    def test_resolved_lifecycle_accepts_hash_bound_owner_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = rejection_fixture(project)
            acceptance_excerpt = "I accept replacement build gallery-v2 as the replacement for the rejected candidate."
            acceptance = project / ".design-dna" / "owner-evidence" / "replacement-acceptance.txt"
            acceptance.write_text(acceptance_excerpt + "\n", encoding="utf-8")
            contract["status"] = "resolved"
            contract["resolution"] = {
                "status": "owner-confirmed",
                "resolved_at": "2026-08-24T09:30:00-04:00",
                "replacement_candidate_manifest_sha256": "f" * 64,
                "owner_evidence": {
                    "file": {
                        "path": ".design-dna/owner-evidence/replacement-acceptance.txt",
                        "sha256": digest(acceptance),
                    },
                    "authority": {
                        "accountable_owner_id": "motty-mjs-studio",
                        "relationship": "accountable-owner",
                        "first_party": True,
                        "decision_kind": "replacement-acceptance",
                    },
                    "verbatim_excerpt": acceptance_excerpt,
                    "scope": "The rendered replacement candidate identified by the replacement manifest.",
                    "acceptance_status": "accepted-replacement",
                },
            }
            report = AUDITOR.audit_payload(project, contract)
        self.assertTrue(report["structural_valid"], report)
        self.assertTrue(report["ready"], report)
        self.assertEqual(
            ["rejected-public-tree", "owner-rejection", "replacement-acceptance"],
            [entry["kind"] for entry in report["evidence"]["verified"]],
        )

    def test_current_good_measure_shape_is_a_migration_source_not_sufficient_evidence(self) -> None:
        """The legacy ad-hoc shape cannot silently claim contract readiness."""

        legacy = {
            "schema_version": 1,
            "classification": "internal",
            "status": "active-reopen",
            "recorded_at": "2026-08-23",
            "accountable_owner": "Motty (MJ's Studio)",
            "candidate": {
                "project_relative_root": "site",
                "manifest_algorithm": "sorted project-relative path plus lowercase file SHA-256",
                "manifest_sha256": "0" * 64,
                "files": [],
            },
            "owner_evidence": {
                "verbatim_excerpt": "Same boring website.",
                "scope": "candidate",
                "acceptance_status": "rejected",
            },
            "rejected_relationship_cluster": {"type_posture": "oversized"},
            "protected_foundations": ["Truth"],
            "reopened_decisions": ["Typography"],
            "replacement_constraints": {
                "asset_led_required": True,
                "photo_free_exception_available": False,
                "minimum_evidence": "proofs",
                "closure": "owner decision",
            },
        }
        with tempfile.TemporaryDirectory() as temporary:
            report = AUDITOR.audit_payload(Path(temporary), legacy)
        self.assertFalse(report["structural_valid"])
        self.assertFalse(report["ready"])
        self.assertIn("missing-field", codes(report))

    def test_unsorted_or_duplicate_manifest_entries_fail_before_io(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = rejection_fixture(project)
            entries = contract["candidate"]["files"]
            entries.reverse()
            entries.append(copy.deepcopy(entries[0]))
            report = AUDITOR.audit_payload(project, contract)
        self.assertFalse(report["structural_valid"])
        self.assertIn("unsorted-manifest", codes(report))
        self.assertIn("duplicate-path", codes(report))


if __name__ == "__main__":
    unittest.main()
