#!/usr/bin/env python3
"""Focused regression coverage for the Project Contrast capability."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills" / "design-dna"
AUDITOR_PATH = SKILL_ROOT / "scripts" / "project_contrast_audit.py"
INITIALIZER_PATH = SKILL_ROOT / "scripts" / "init_project_state.py"
FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "project-contrast" / "ready-contract.json"


def png(width: int, height: int, rgba: tuple[int, int, int, int]) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    raw = b"".join(b"\x00" + bytes(rgba) * width for _ in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


WIDE_PNG = png(320, 480, (176, 88, 42, 255))
NARROW_PNG = png(240, 640, (32, 112, 144, 255))
COMPARATOR_PNG = png(320, 480, (14, 16, 20, 255))


def load_auditor():
    specification = importlib.util.spec_from_file_location("project_contrast_audit_test", AUDITOR_PATH)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


AUDITOR = load_auditor()


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def source_snapshot(files: dict[str, bytes], *, entry_path: str) -> dict:
    """Produce the renderer's immutable local-source snapshot shape."""

    manifest_files = [
        {"path": path, "bytes": len(payload), "sha256": digest(payload)}
        for path, payload in sorted(files.items())
    ]
    manifest_payload = json.dumps(
        manifest_files, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return {
        "policy": "frozen-deny-by-default-public-root",
        "root_kind": "explicit-build-root",
        "entry_path": entry_path,
        "drift_check": "passed-source-and-frozen-snapshot-before-report-and-commit",
        "manifest": {
            "algorithm": "sha256",
            "manifest_sha256": digest(manifest_payload),
            "file_count": len(manifest_files),
            "total_bytes": sum(entry["bytes"] for entry in manifest_files),
            "files": manifest_files,
            "excluded_counts": {
                "hidden_or_source_only_path": 0,
                "sensitive_or_source_config": 0,
                "extension_not_public_allowlist": 0,
            },
        },
    }


def write_schema3_render_review(
    evidence: Path,
    *,
    build_id: str,
    route: str = "/",
    wide_interaction: bool = False,
) -> dict[str, str]:
    """Write a path-bound schema-3 package with default-state full-page PNGs.

    The Project Contrast auditor intentionally rechecks this report and its
    marker rather than accepting a standalone hash-bound JSON note. The test
    fixture keeps its image dimensions small enough for fast stdlib-only runs
    while preserving the browser-viewport/full-page distinction.
    """

    report_path = evidence / "render-review.json"
    marker_path = evidence / ".design-dna-render-review.json"
    contact_sheet_payload = b"<!doctype html><title>Rendered review fixture</title>\n"
    contact_sheet_path = evidence / "contact-sheet.html"
    contact_sheet_path.write_bytes(contact_sheet_payload)
    frozen_source = {"index.html": b"<!doctype html><title>fixture build</title>\n"}
    output_identity = {
        "id": "a" * 64,
        "path_sha256": AUDITOR.rendered_output_path_sha256(evidence),
    }
    screenshots = {
        "home-wide": ("wide.png", WIDE_PNG, 320, 240, 320, 480),
        "home-narrow": ("narrow.png", NARROW_PNG, 240, 320, 240, 640),
    }
    captures = []
    for capture_id, (path, payload, viewport_width, viewport_height, pixel_width, pixel_height) in screenshots.items():
        interaction = (
            {
                "requested_steps": 1,
                "completed_steps": 1,
                "status": "complete",
            }
            if capture_id == "home-wide" and wide_interaction
            else {
                "requested_steps": 0,
                "completed_steps": 0,
                "status": "not-requested",
            }
        )
        captures.append({
            "id": capture_id,
            "route_id": "route-01",
            "capture_status": "complete",
            "final_url": f"http://127.0.0.1{route}",
            "viewport": {
                "width": viewport_width,
                "height": viewport_height,
                "device_scale_factor": 1,
            },
            "interaction": interaction,
            "screenshot": {
                "path": path,
                "sha256": digest(payload),
                "media_type": "image/png",
                "bytes": len(payload),
                "pixel_width": pixel_width,
                "pixel_height": pixel_height,
            },
        })
    report = {
        "schema_version": 3,
        "tool": {
            "name": "design-dna-rendered-review",
            "version": "3.0.0",
            "report_schema": "render-review.schema.json",
        },
        "output_identity": output_identity,
        "execution_ok": True,
        "review_required": True,
        "automatic_visual_quality_pass": False,
        "quality_status": "manual-review-required",
        "execution": {},
        "privacy": {},
        "build": {
            "id": build_id,
            "target_input": "fixture",
            "target_kind": "local-directory",
        },
        "source_snapshot": source_snapshot(frozen_source, entry_path="index.html"),
        "capture_contract": {
            "profiles": [{"id": "wide"}, {"id": "narrow"}],
            "scenarios": [{"id": "home-default"}],
        },
        "routes": [{
            "id": "route-01",
            "requested": route,
            "url": "http://127.0.0.1/",
        }],
        "captures": captures,
        "artifacts": {
            "contact_sheet": {
                "path": "contact-sheet.html",
                "sha256": digest(contact_sheet_payload),
                "media_type": "text/html",
                "bytes": len(contact_sheet_payload),
            },
            "report": {"path": "render-review.json", "bytes": 0},
            "marker": {"path": ".design-dna-render-review.json", "bytes": 0},
            "capture_bytes": len(WIDE_PNG) + len(NARROW_PNG),
            "total_bytes": 0,
        },
        "manual_review": {},
    }
    marker_bytes = 0
    report_payload = b""
    for _ in range(8):
        report["artifacts"]["marker"]["bytes"] = marker_bytes
        report_payload = (json.dumps(report, indent=2) + "\n").encode("utf-8")
        report["artifacts"]["report"]["bytes"] = len(report_payload)
        report_payload = (json.dumps(report, indent=2) + "\n").encode("utf-8")
        marker = {
            "schema_version": 3,
            "marker_type": "design-dna-render-review-output",
            "tool": {
                "name": "design-dna-rendered-review",
                "version": "3.0.0",
            },
            "output_identity": output_identity,
            "report": {
                "path": "render-review.json",
                "sha256": digest(report_payload),
                "bytes": len(report_payload),
            },
            "created_at": "2026-08-12T12:00:00+00:00",
            "build_id_sha256": digest(build_id.encode("utf-8")),
        }
        marker_payload = (json.dumps(marker, indent=2) + "\n").encode("utf-8")
        if len(marker_payload) == marker_bytes:
            break
        marker_bytes = len(marker_payload)
    else:
        raise AssertionError("schema-3 marker byte count did not stabilize")
    report["artifacts"]["marker"]["bytes"] = marker_bytes
    report_payload = (json.dumps(report, indent=2) + "\n").encode("utf-8")
    marker["report"]["sha256"] = digest(report_payload)
    marker["report"]["bytes"] = len(report_payload)
    marker_payload = (json.dumps(marker, indent=2) + "\n").encode("utf-8")
    assert len(marker_payload) == marker_bytes
    report_path.write_bytes(report_payload)
    marker_path.write_bytes(marker_payload)
    return {
        "report": digest(report_payload),
        "marker": digest(marker_payload),
    }


def rebind_schema3_package(evidence: Path, report: dict) -> str:
    """Rewrite a deliberately mutated schema-3 test package and its marker."""

    report_path = evidence / "render-review.json"
    marker_path = evidence / ".design-dna-render-review.json"
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    marker_bytes = report["artifacts"]["marker"]["bytes"]
    for _ in range(12):
        report["artifacts"]["marker"]["bytes"] = marker_bytes
        report_payload = (json.dumps(report, indent=2) + "\n").encode("utf-8")
        report["artifacts"]["report"]["bytes"] = len(report_payload)
        report_payload = (json.dumps(report, indent=2) + "\n").encode("utf-8")
        marker["report"]["sha256"] = digest(report_payload)
        marker["report"]["bytes"] = len(report_payload)
        marker_payload = (json.dumps(marker, indent=2) + "\n").encode("utf-8")
        if len(marker_payload) == marker_bytes:
            break
        marker_bytes = len(marker_payload)
    else:
        raise AssertionError("mutated schema-3 marker byte count did not stabilize")
    report["artifacts"]["marker"]["bytes"] = marker_bytes
    report_payload = (json.dumps(report, indent=2) + "\n").encode("utf-8")
    marker["report"]["sha256"] = digest(report_payload)
    marker["report"]["bytes"] = len(report_payload)
    marker_payload = (json.dumps(marker, indent=2) + "\n").encode("utf-8")
    assert len(marker_payload) == marker_bytes
    report_path.write_bytes(report_payload)
    marker_path.write_bytes(marker_payload)
    return digest(report_payload)


def prepared_contract(
    root: Path,
    *,
    render_route: str = "/",
    wide_interaction: bool = False,
) -> dict:
    evidence = root / "evidence"
    evidence.mkdir(parents=True)
    files = {
        "build.txt": b"candidate-build-v1\n",
        "wide.png": WIDE_PNG,
        "narrow.png": NARROW_PNG,
        "comparator.png": COMPARATOR_PNG,
        "nearest-approved-build.txt": b"nearest-approved-build-v1\n",
        "closest-sibling-selection.md": b"Owner-authorized ledger snapshot selected the nearest approved public encounter.\n",
        "public-system-approval.md": b"Owner approved the visible navigation and identity shell within the stated scope.\n",
        "unprimed.md": b"Unprimed reviewer observation.\n",
        "paired.md": b"Paired comparison observation.\n",
        "owner-review.md": b"Accountable owner acceptance.\n",
    }
    hashes: dict[str, str] = {}
    for name, payload in files.items():
        (evidence / name).write_bytes(payload)
        hashes[name] = digest(payload)
    render_review_hashes = write_schema3_render_review(
        evidence,
        build_id="candidate-v1",
        route=render_route,
        wide_interaction=wide_interaction,
    )
    raw = FIXTURE_PATH.read_text(encoding="utf-8")
    replacements = {
        "__BUILD_SHA256__": hashes["build.txt"],
        "__RENDER_REVIEW_SHA256__": render_review_hashes["report"],
        "__WIDE_SHA256__": hashes["wide.png"],
        "__NARROW_SHA256__": hashes["narrow.png"],
        "__COMPARATOR_SHA256__": hashes["comparator.png"],
        "__NEAREST_APPROVED_BUILD_SHA256__": hashes["nearest-approved-build.txt"],
        "__CLOSEST_SIBLING_SELECTION_SHA256__": hashes["closest-sibling-selection.md"],
        "__PUBLIC_SYSTEM_APPROVAL_SHA256__": hashes["public-system-approval.md"],
        "__UNPRIMED_SHA256__": hashes["unprimed.md"],
        "__PAIRED_SHA256__": hashes["paired.md"],
        "__OWNER_REVIEW_SHA256__": hashes["owner-review.md"],
    }
    for token, value in replacements.items():
        raw = raw.replace(token, value)
    contract = json.loads(raw)
    state = root / ".design-dna"
    state.mkdir()
    (state / "project-contrast.json").write_text(
        json.dumps(contract, indent=2) + "\n", encoding="utf-8"
    )
    return contract


def legacy_placeholder_contract() -> dict:
    return {
        "schema_version": 1,
        "created_with": "design-dna 5.2.0",
        "classification": "internal",
        "scope": {
            "project_id": "replace-with-project-safe-id",
            "surface_scope": ["/"],
            "trigger": ["owner-recurrence-requirement"],
            "comparison_authority": {
                "status": "not-authorized",
                "basis": "No cross-project material may be compared until an accountable owner authorizes a minimized comparison.",
            },
        },
        "source_to_encounter": {
            "visitor_occasion": "Replace with why this visitor arrives now.",
        },
        "selected_direction": {
            "organizing_answer": "Replace with the project-specific organizing answer, not a style name.",
        },
        "comparison": {},
    }


class ProjectContrastAuditTests(unittest.TestCase):
    def test_ready_owner_authorized_contract_has_no_automatic_aesthetic_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = prepared_contract(root)
            report = AUDITOR.audit_payload(root, contract)
            self.assertTrue(report["structural_valid"])
            self.assertTrue(report["ready"])
            self.assertFalse(report["automatic_aesthetic_pass"])
            self.assertTrue(report["comparison"]["accepted_structural_difference"])

    def test_closest_sibling_selection_needs_hash_bound_owner_authorized_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            contract["comparison"]["closest_sibling_selection"]["evidence"] = None
            report = AUDITOR.audit_payload(root, contract)
            self.assertFalse(report["ready"])
            self.assertIn(
                "closest-sibling-selection-evidence-unverified",
                {entry["code"] for entry in report["gaps"]},
            )

    def test_image_comparator_needs_whole_route_source_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            del contract["comparison"]["comparators"][0]["evidence"]["image_source"]
            report = AUDITOR.audit_payload(root, contract)
            self.assertFalse(report["ready"])
            self.assertIn(
                "comparator-image-source-metadata-missing",
                {entry["code"] for entry in report["gaps"]},
            )

    def test_tiny_or_misdeclared_image_comparator_cannot_pose_as_whole_route_proof(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            comparator_path = root / "evidence" / "comparator.png"
            comparator_path.write_bytes(png(1, 1, (14, 16, 20, 255)))
            contract["comparison"]["comparators"][0]["evidence"]["file"]["sha256"] = digest(
                comparator_path.read_bytes()
            )
            report = AUDITOR.audit_payload(root, contract)
            self.assertFalse(report["ready"])
            self.assertIn(
                "comparator-image-extent-mismatch",
                {entry["code"] for entry in report["findings"]},
            )

    def test_structural_abstract_cannot_clear_visible_surface_difference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            abstract = b"A privacy-proportionate structural comparison only.\n"
            abstract_path = root / "evidence" / "comparator-abstract.md"
            abstract_path.write_bytes(abstract)
            comparator = contract["comparison"]["comparators"][0]["evidence"]
            comparator["kind"] = "structural-abstract"
            comparator["file"] = {
                "path": "evidence/comparator-abstract.md",
                "sha256": digest(abstract),
            }
            del comparator["image_source"]
            report = AUDITOR.audit_payload(root, contract)
            self.assertFalse(report["ready"])
            self.assertIn(
                "structural-abstract-cannot-support-surface-difference",
                {entry["code"] for entry in report["findings"]},
            )

    def test_complete_review_exposure_needs_declared_wide_and_narrow_captures(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            contract["review"]["paired"]["reviewed_capture_ids"] = ["capture-wide"]
            report = AUDITOR.audit_payload(root, contract)
            self.assertFalse(report["ready"])
            self.assertIn(
                "review-wide-narrow-exposure-incomplete",
                {entry["code"] for entry in report["findings"]},
            )

    def test_paired_still_too_close_blocks_even_if_a_disposition_is_written(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            contract["review"]["paired_outcome"]["result"] = "still-too-close"
            contract["review"]["paired_outcome"]["earliest_reopen_decision"] = "Reopen the opening encounter before changing surface treatments."
            contract["review"]["disposition"] = "accepted"
            report = AUDITOR.audit_payload(root, contract)
            self.assertFalse(report["ready"])
            self.assertIn(
                "paired-review-still-too-close",
                {entry["code"] for entry in report["gaps"]},
            )

    def test_owner_acceptance_binds_exact_build_and_full_capture_set(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            contract["review"]["owner_review"]["candidate_build_id"] = "other-build"
            contract["review"]["owner_review"]["reviewed_capture_ids"] = ["capture-wide"]
            report = AUDITOR.audit_payload(root, contract)
            self.assertFalse(report["ready"])
            codes = {entry["code"] for entry in report["findings"]}
            self.assertIn("owner-acceptance-candidate-build-unbound", codes)
            self.assertIn("owner-acceptance-wide-narrow-exposure-incomplete", codes)

    def test_pending_owner_review_is_separate_from_candidate_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            contract["review"]["owner_review"] = {
                "status": "pending",
                "reviewer_id": None,
                "relationship": None,
                "observed_at": None,
                "evidence": None,
                "limitations": "The candidate is ready for the owner's later decision.",
                "candidate_build_id": None,
                "reviewed_capture_ids": [],
            }
            report = AUDITOR.audit_payload(root, contract)
            self.assertTrue(report["ready"], report)
            self.assertEqual(report["owner_acceptance"]["status"], "pending")
            self.assertFalse(report["owner_acceptance"]["complete"])
            self.assertFalse(report["owner_acceptance"]["blocks_candidate_readiness"])

    def test_owner_rejection_still_blocks_candidate_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            contract["review"]["owner_review"]["status"] = "rejected"
            report = AUDITOR.audit_payload(root, contract)
            self.assertFalse(report["ready"], report)
            self.assertTrue(report["owner_acceptance"]["blocks_candidate_readiness"])
            self.assertIn(
                "owner-review-rejected",
                {entry["code"] for entry in report["findings"]},
            )

    def test_approved_public_system_needs_scoped_hash_bound_owner_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            contract["comparison"]["shared_public_shell"]["approval"] = None
            report = AUDITOR.audit_payload(root, contract)
            self.assertFalse(report["ready"])
            self.assertIn(
                "approved-public-system-owner-approval-missing",
                {entry["code"] for entry in report["gaps"]},
            )

    def test_project_defined_signature_axis_can_use_a_new_material_identifier(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            surface_axis = contract["design_signature"]["axes"][1]
            surface_axis["axis"] = "repair-annotation-language"
            contract["comparison"]["surface_grammar_observations"][0]["selected_signature_axis_refs"] = [
                "repair-annotation-language"
            ]
            report = AUDITOR.audit_payload(root, contract)
            self.assertTrue(report["ready"])
            self.assertIn(
                "repair-annotation-language",
                report["design_signature"]["selected_surface_axes"],
            )

    def test_selected_signature_axis_needs_a_project_chosen_group(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            del contract["design_signature"]["axes"][0]["group"]
            errors, _ = AUDITOR.validate_contract_payload(contract)
            self.assertIn(
                "lifecycle-signature-axis-group-missing",
                {entry["code"] for entry in errors},
            )

    def test_different_comparator_cannot_reuse_candidate_capture_pixels(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            comparator_path = root / "evidence" / "comparator.png"
            comparator_path.write_bytes(WIDE_PNG)
            contract["comparison"]["comparators"][0]["evidence"]["file"]["sha256"] = digest(WIDE_PNG)
            report = AUDITOR.audit_payload(root, contract)
            self.assertFalse(report["ready"])
            self.assertIn(
                "comparison-different-reuses-candidate-pixels",
                {entry["code"] for entry in report["findings"]},
            )

    def test_owner_recurrence_must_compare_the_actual_closest_sibling(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            artifact = b"A minimized, authorized abstract of another historical pattern.\n"
            (root / "evidence" / "known-template.md").write_bytes(artifact)
            contract["comparison"]["comparators"].append({
                "id": "known-template",
                "relationship": "known-template",
                "evidence": {
                    "kind": "structural-abstract",
                    "file": {
                        "path": "evidence/known-template.md",
                        "sha256": digest(artifact),
                    },
                    "access": "Owner-authorized minimized abstract for a secondary diagnostic.",
                    "retention": "Delete after the approved review window.",
                    "purpose": "Compare a non-nearest historical pattern without replacing the closest-sibling review.",
                },
            })
            contract["comparison"]["contrast_claims"][0]["evidence"]["comparator_ids"] = ["known-template"]
            contract["comparison"]["surface_grammar_observations"][0]["evidence"]["comparator_ids"] = ["known-template"]
            contract["review"]["paired"]["reviewed_comparator_ids"] = ["known-template"]
            report = AUDITOR.audit_payload(root, contract)
            self.assertFalse(report["ready"])
            gap_codes = {entry["code"] for entry in report["gaps"]}
            self.assertIn("closest-sibling-structural-evidence-missing", gap_codes)
            self.assertIn("surface-grammar-evidence-missing", gap_codes)
            self.assertIn("closest-sibling-paired-review-missing", gap_codes)

    def test_same_project_rejection_cannot_impersonate_cross_project_closest_sibling(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            contract["comparison"]["comparators"][0]["project_id"] = contract["scope"]["project_id"]
            report = AUDITOR.audit_payload(root, contract)
            self.assertFalse(report["ready"])
            self.assertIn(
                "closest-sibling-cross-project-missing",
                {entry["code"] for entry in report["gaps"]},
            )

    def test_same_project_rejected_relationship_remains_valid_diagnostic_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            comparator = contract["comparison"]["comparators"][0]
            comparator["project_id"] = contract["scope"]["project_id"]
            comparator["relationship"] = "same-project-rejected"
            errors, _ = AUDITOR.validate_contract_payload(contract)
            self.assertNotIn(
                "invalid-enum",
                {entry["code"] for entry in errors},
            )

    def test_different_project_id_cannot_launder_the_same_comparator_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            alias = copy.deepcopy(contract["comparison"]["comparators"][0])
            alias["id"] = "current-project-rejection"
            alias["project_id"] = contract["scope"]["project_id"]
            alias["relationship"] = "same-project-rejected"
            contract["comparison"]["comparators"].append(alias)
            report = AUDITOR.audit_payload(root, contract)
            self.assertFalse(report["ready"])
            self.assertIn(
                "closest-sibling-artifact-identity-collision",
                {entry["code"] for entry in report["findings"]},
            )

    def test_owner_recurrence_requires_a_real_counter_answer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            contract["exploration"]["challenge_method"] = "not-needed"
            contract["exploration"]["challenging_answer"] = "No alternate organizing answer was created."
            errors, _ = AUDITOR.validate_contract_payload(contract)
            self.assertIn(
                "lifecycle-owner-recurrence-counter-answer-required",
                {entry["code"] for entry in errors},
            )

    def test_owner_recurrence_rejects_a_verbatim_selected_answer_as_its_counter_answer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            contract["exploration"]["challenging_answer"] = contract["selected_direction"]["organizing_answer"]
            errors, _ = AUDITOR.validate_contract_payload(contract)
            self.assertIn(
                "lifecycle-owner-recurrence-counter-answer-collides",
                {entry["code"] for entry in errors},
            )

    def test_owner_recurrence_counterfactual_cannot_claim_a_result_without_a_swap(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            contract["comparison"]["counterfactual_swap_test"]["removed_or_swapped"] = []
            errors, _ = AUDITOR.validate_contract_payload(contract)
            self.assertIn(
                "lifecycle-counterfactual-items-required",
                {entry["code"] for entry in errors},
            )

    def test_owner_recurrence_needs_one_observed_or_revised_prediction(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            contract["selected_direction"]["observable_predictions"][0]["status"] = "not-applicable"
            errors, _ = AUDITOR.validate_contract_payload(contract)
            self.assertIn(
                "lifecycle-observable-prediction-unverified",
                {entry["code"] for entry in errors},
            )

    def test_hash_bound_arbitrary_json_cannot_impersonate_a_schema3_render_review(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            fake = b'{"artifact":"rendered-review"}\n'
            path = root / "evidence" / "render-review.json"
            path.write_bytes(fake)
            contract["evidence"]["render_reviews"][0]["file"]["sha256"] = digest(fake)
            report = AUDITOR.audit_payload(root, contract)
            finding_codes = {entry["code"] for entry in report["findings"]}
            self.assertFalse(report["ready"])
            self.assertIn("render-review-schema-invalid", finding_codes)

    def test_schema3_local_build_requires_its_frozen_source_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            evidence = root / "evidence"
            report_path = evidence / "render-review.json"
            rendered = json.loads(report_path.read_text(encoding="utf-8"))
            rendered["source_snapshot"] = None
            contract["evidence"]["render_reviews"][0]["file"]["sha256"] = (
                rebind_schema3_package(evidence, rendered)
            )
            report = AUDITOR.audit_payload(root, contract)
            self.assertFalse(report["ready"])
            self.assertIn(
                "render-review-source-snapshot-invalid",
                {entry["code"] for entry in report["findings"]},
            )

    def test_wrong_render_capture_binding_is_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            wide = contract["evidence"]["captures"][0]
            wide["file"] = copy.deepcopy(contract["evidence"]["captures"][1]["file"])
            report = AUDITOR.audit_payload(root, contract)
            finding_codes = {entry["code"] for entry in report["findings"]}
            self.assertFalse(report["ready"])
            self.assertIn("capture-render-screenshot-mismatch", finding_codes)

    def test_wrong_render_route_binding_is_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = prepared_contract(root, render_route="/wrong-route")
            report = AUDITOR.audit_payload(root, contract)
            finding_codes = {entry["code"] for entry in report["findings"]}
            self.assertFalse(report["ready"])
            self.assertIn("capture-render-route-mismatch", finding_codes)

    def test_full_page_interaction_capture_can_bind_its_interaction_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = prepared_contract(root, wide_interaction=True)
            wide = contract["evidence"]["captures"][0]
            wide["capture_state"] = "interaction"
            report = AUDITOR.audit_payload(root, contract)
            self.assertTrue(report["ready"])
            self.assertEqual(wide["capture_mode"], "full-page")
            self.assertGreater(
                AUDITOR.image_dimensions(
                    (root / wide["file"]["path"]).read_bytes(),
                    "png",
                    "test capture",
                )[1],
                wide["viewport"]["height"],
            )

    def test_whitespace_only_lifecycle_prose_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            contract["source_to_encounter"]["visitor_occasion"] = " \t\n "
            contract["review"]["unprimed"]["first_observation"] = "\t"
            errors, _ = AUDITOR.validate_contract_payload(contract)
            self.assertIn("invalid-string", {entry["code"] for entry in errors})
            self.assertFalse(AUDITOR.audit_payload(root, contract)["ready"])

    def test_schema_rejects_blank_created_with_to_match_runtime(self) -> None:
        schema = json.loads(
            (SKILL_ROOT / "schemas" / "project-contrast.schema.json").read_text(
                encoding="utf-8"
            )
        )
        created_with = schema["properties"]["created_with"]
        self.assertEqual(created_with["pattern"], ".*\\S.*")
        self.assertEqual(created_with["maxLength"], 200)
        self.assertEqual(AUDITOR.runtime_schema_errors(), [])

    def test_tiny_viewport_cannot_pose_as_rendered_wide_narrow_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            for capture in contract["evidence"]["captures"]:
                capture["viewport"]["width"] = 1
                capture["viewport"]["height"] = 1
            errors, _ = AUDITOR.validate_contract_payload(contract)
            self.assertIn("invalid-dimension", {entry["code"] for entry in errors})
            self.assertFalse(AUDITOR.audit_payload(root, contract)["ready"])

    def test_project_contrast_viewport_floor_matches_schema3_renderer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            for capture in contract["evidence"]["captures"]:
                capture["viewport"]["width"] = 239
                capture["viewport"]["height"] = 240
            errors, _ = AUDITOR.validate_contract_payload(contract)
            self.assertIn("invalid-dimension", {entry["code"] for entry in errors})
        schema = json.loads(
            (SKILL_ROOT / "schemas" / "project-contrast.schema.json").read_text(
                encoding="utf-8"
            )
        )
        viewport = schema["$defs"]["viewport"]["properties"]
        self.assertEqual(viewport["width"]["minimum"], 240)
        self.assertEqual(viewport["height"]["minimum"], 240)
        self.assertEqual(AUDITOR.runtime_schema_errors(), [])

    def test_schema3_local_build_rejects_unrelated_capture_origin(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            evidence = root / "evidence"
            report_path = evidence / "render-review.json"
            rendered = json.loads(report_path.read_text(encoding="utf-8"))
            for capture in rendered["captures"]:
                capture["final_url"] = "https://unrelated.example/"
            contract["evidence"]["render_reviews"][0]["file"]["sha256"] = (
                rebind_schema3_package(evidence, rendered)
            )
            report = AUDITOR.audit_payload(root, contract)
            self.assertFalse(report["ready"])
            self.assertIn(
                "render-review-origin-mismatch",
                {entry["code"] for entry in report["findings"]},
            )

    def test_wide_label_requires_a_wider_bound_viewport_than_narrow(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            wide, narrow = contract["evidence"]["captures"]
            wide["viewport"]["viewport_class"] = "narrow"
            narrow["viewport"]["viewport_class"] = "wide"
            report = AUDITOR.audit_payload(root, contract)
            self.assertFalse(report["ready"])
            self.assertIn(
                "wide-narrow-viewport-order-invalid",
                {entry["code"] for entry in report["findings"]},
            )

    def test_surface_only_difference_does_not_close_owner_recurrence_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = prepared_contract(root)
            contract = copy.deepcopy(contract)
            contract["comparison"]["contrast_claims"][0]["level"] = "type-behavior"
            report = AUDITOR.audit_payload(root, contract)
            gap_codes = {entry["code"] for entry in report["gaps"]}
            self.assertFalse(report["ready"])
            self.assertIn("structural-contrast-unproven", gap_codes)

    def test_accepted_structural_claim_rejects_arbitrary_prose_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            contract["comparison"]["contrast_claims"][0]["evidence"] = (
                "The reviewer says the body progression differs."
            )
            errors, _ = AUDITOR.validate_contract_payload(contract)
            self.assertIn("invalid-object", {entry["code"] for entry in errors})

    def test_mobile_structural_claim_needs_bound_narrow_capture(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            claim = contract["comparison"]["contrast_claims"][0]
            claim["level"] = "mobile-encounter"
            claim["evidence"]["capture_ids"] = ["capture-wide"]
            report = AUDITOR.audit_payload(root, contract)
            self.assertFalse(report["ready"])
            gap_codes = {entry["code"] for entry in report["gaps"]}
            self.assertIn("public-grammar-required-viewport-missing", gap_codes)
            self.assertIn("structural-contrast-unproven", gap_codes)

    def test_self_review_is_retained_but_cannot_close_unprimed_independence_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            contract["review"]["unprimed"]["relationship"] = "self-review"
            report = AUDITOR.audit_payload(root, contract)
            self.assertFalse(report["ready"])
            self.assertIn(
                "unprimed-review-not-independent",
                {entry["code"] for entry in report["gaps"]},
            )

    def test_unprimed_review_needs_first_observation_and_verified_candidate_exposure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            contract["review"]["unprimed"]["first_observation"] = None
            contract["review"]["unprimed"]["reviewed_capture_ids"] = []
            report = AUDITOR.audit_payload(root, contract)
            finding_codes = {entry["code"] for entry in report["findings"]}
            self.assertFalse(report["ready"])
            self.assertIn("unprimed-first-observation-missing", finding_codes)
            self.assertIn("review-candidate-captures-missing", finding_codes)

    def test_paired_review_needs_authorized_comparator_exposure_after_unprimed_freeze(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            contract["review"]["paired"]["reviewed_comparator_ids"] = []
            contract["review"]["paired"]["observed_at"] = "2026-08-11T12:05:00-04:00"
            report = AUDITOR.audit_payload(root, contract)
            finding_codes = {entry["code"] for entry in report["findings"]}
            self.assertFalse(report["ready"])
            self.assertIn("review-comparator-evidence-missing", finding_codes)
            self.assertIn("paired-observation-before-unprimed-freeze", finding_codes)

    def test_paired_review_timestamp_must_be_strictly_after_unprimed_freeze(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            contract["review"]["paired"]["observed_at"] = contract["review"]["unprimed"]["frozen_at"]
            report = AUDITOR.audit_payload(root, contract)
            self.assertFalse(report["ready"])
            self.assertIn(
                "paired-observation-before-unprimed-freeze",
                {entry["code"] for entry in report["findings"]},
            )

    def test_owner_acceptance_must_follow_paired_review_freeze(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            contract["review"]["owner_review"]["observed_at"] = "2026-08-11T12:20:00-04:00"
            report = AUDITOR.audit_payload(root, contract)
            self.assertFalse(report["ready"])
            self.assertIn(
                "owner-acceptance-before-paired-freeze",
                {entry["code"] for entry in report["findings"]},
            )

    def test_unauthorized_comparator_is_blocking_not_a_style_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = prepared_contract(root)
            contract = copy.deepcopy(contract)
            contract["scope"]["comparison_authority"]["status"] = "not-authorized"
            report = AUDITOR.audit_payload(root, contract)
            finding_codes = {entry["code"] for entry in report["findings"]}
            self.assertFalse(report["ready"])
            self.assertIn("unauthorized-comparator", finding_codes)

    def test_contract_rejects_score_like_unsupported_properties(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = prepared_contract(root)
            contract = copy.deepcopy(contract)
            contract["ai_score"] = 99
            errors, _ = AUDITOR.validate_contract_payload(contract)
            self.assertTrue(errors)
            self.assertIn("invalid-properties", {entry["code"] for entry in errors})

    def test_owner_recurrence_requires_encounter_and_surface_axis_sets(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            contract["design_signature"]["axes"] = [
                contract["design_signature"]["axes"][0]
            ]
            errors, _ = AUDITOR.validate_contract_payload(contract)
            codes = {entry["code"] for entry in errors}
            self.assertIn("lifecycle-surface-axis-missing", codes)
            self.assertNotIn("font-required", codes)

    def test_owner_recurrence_rejects_selected_surface_axis_without_observed_bound_comparison(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            contract["comparison"]["surface_grammar_observations"] = []
            report = AUDITOR.audit_payload(root, contract)
            gap_codes = {entry["code"] for entry in report["gaps"]}
            self.assertFalse(report["ready"])
            self.assertIn("surface-grammar-evidence-missing", gap_codes)
            self.assertNotIn("font-required", gap_codes)

    def test_not_comparable_surface_observation_cannot_clear_selected_surface_axis(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            observation = contract["comparison"]["surface_grammar_observations"][0]
            observation["relationship"] = "not-comparable"
            observation["evidence"]["comparator_ids"] = []
            report = AUDITOR.audit_payload(root, contract)
            gap_codes = {entry["code"] for entry in report["gaps"]}
            self.assertFalse(report["ready"])
            self.assertIn("surface-grammar-evidence-missing", gap_codes)

    def test_candidate_public_shell_needs_semantic_bound_collision_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            shell = contract["comparison"]["shared_public_shell"]
            shell["classification"] = "candidate-public-shell"
            claim = {
                "id": "shell-001",
                "domain": "persistent public chrome",
                "level": "public-shell",
                "candidate_observation": "The candidate has a visible route frame.",
                "comparator_observation": "The sibling has a visible route frame.",
                "relationship": "not-comparable",
                "subject_cause": "The public frame needs review rather than a technical label.",
                "evidence": {
                    "capture_ids": ["capture-wide"],
                    "comparator_ids": ["nearest-approved-surface"],
                    "note": "Bound artifacts exist, but the relationship is honestly not comparable.",
                },
                "status": "accepted",
            }
            contract["comparison"]["contrast_claims"].append(claim)
            report = AUDITOR.audit_payload(root, contract)
            gap_codes = {entry["code"] for entry in report["gaps"]}
            self.assertFalse(report["ready"])
            self.assertIn("public-shell-collision-unresolved", gap_codes)

    def test_candidate_public_shell_rejects_arbitrary_prose_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            shell = contract["comparison"]["shared_public_shell"]
            shell["classification"] = "candidate-public-shell"
            claim = {
                "id": "shell-001",
                "domain": "persistent public chrome",
                "level": "public-shell",
                "candidate_observation": "The candidate has a visible route frame.",
                "comparator_observation": "The sibling has a visible route frame.",
                "relationship": "different",
                "subject_cause": "The public frame needs review rather than a technical label.",
                "evidence": "A reviewer says these public shells differ.",
                "status": "accepted",
            }
            contract["comparison"]["contrast_claims"].append(claim)
            errors, _ = AUDITOR.validate_contract_payload(contract)
            self.assertIn("invalid-object", {entry["code"] for entry in errors})

    def test_candidate_public_shell_semantic_bound_claim_can_clear_collision_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            shell = contract["comparison"]["shared_public_shell"]
            shell["classification"] = "candidate-public-shell"
            contract["comparison"]["contrast_claims"].append({
                "id": "shell-001",
                "domain": "persistent public chrome",
                "level": "public-shell",
                "candidate_observation": "The candidate exposes the repair sequence directly below a restrained route frame.",
                "comparator_observation": "The sibling uses persistent inventory filters as its dominant public frame.",
                "relationship": "different",
                "subject_cause": "The repair task needs a temporary orientation frame instead of persistent browse controls.",
                "evidence": {
                    "capture_ids": ["capture-wide", "capture-narrow"],
                    "comparator_ids": ["nearest-approved-surface"],
                    "note": "The bound candidate captures and authorized comparator support a public-shell relationship review.",
                },
                "status": "accepted",
            })
            report = AUDITOR.audit_payload(root, contract)
            self.assertTrue(report["ready"])

    def test_justified_bright_hard_edge_surface_register_can_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            observation = contract["comparison"]["surface_grammar_observations"][0]
            observation.update({
                "project_defined_label": "bright hard-edge wayfinding register",
                "candidate_observation": "A bright hard-edge route marker follows the supplied public workshop safety signage rather than a decorative campaign pattern.",
                "comparator_observation": "The sibling's muted inventory surface has no equivalent public safety-signage register.",
                "project_cause": "The approved workshop materials use high-visibility hard-edge markings to distinguish live repair zones.",
                "source": "Approved workshop safety-signage packet, candidate captures, and owner-authorized comparator.",
            })
            report = AUDITOR.audit_payload(root, contract)
            self.assertTrue(report["ready"])
            self.assertFalse(report["automatic_aesthetic_pass"])

    def test_shared_with_reason_surface_register_can_pass_when_bound(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            observation = contract["comparison"]["surface_grammar_observations"][0]
            observation.update({
                "relationship": "shared-with-reason",
                "candidate_observation": "The candidate retains a highly legible annotation hierarchy.",
                "comparator_observation": "The approved sibling retains the same hierarchy for established accessibility and maintenance reasons.",
                "project_cause": "The owner-approved public system requires the hierarchy for cross-project access and maintenance continuity.",
                "source": "Approved public-system specification, candidate captures, and owner-authorized comparator.",
            })
            report = AUDITOR.audit_payload(root, contract)
            self.assertTrue(report["ready"])
            self.assertIn("type-role-behavior", report["design_signature"]["observed_surface_axes"])

    def test_visible_public_shell_cannot_be_labeled_technical_foundation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            shell = contract["comparison"]["shared_public_shell"]
            shell["classification"] = "technical-foundation"
            errors, _ = AUDITOR.validate_contract_payload(contract)
            codes = {entry["code"] for entry in errors}
            self.assertIn("technical-foundation-has-public-shell", codes)

    def test_rendered_public_shell_evidence_cannot_be_labeled_technical_foundation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            shell = contract["comparison"]["shared_public_shell"]
            shell["classification"] = "technical-foundation"
            shell["public_observation"] = None
            errors, _ = AUDITOR.validate_contract_payload(contract)
            codes = {entry["code"] for entry in errors}
            self.assertIn("technical-foundation-has-public-evidence", codes)

    def test_seven_static_routes_reject_root_only_representative_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            site = root / "site"
            site.mkdir()
            (site / "index.html").write_text("<!doctype html><title>root</title>", encoding="utf-8")
            for name in ("about", "visit", "work", "notes", "contact", "archive"):
                page = site / name
                page.mkdir()
                (page / "index.html").write_text(f"<!doctype html><title>{name}</title>", encoding="utf-8")
            contract["scope"]["route_coverage"] = {
                "mode": "representative",
                "rationale": "Root was selected before the route family was reviewed.",
            }
            report = AUDITOR.audit_payload(root, contract)
            gap_codes = {entry["code"] for entry in report["gaps"]}
            self.assertFalse(report["ready"])
            self.assertIn("route-coverage-representative-too-narrow", gap_codes)

    def test_static_route_coverage_requires_each_discovered_route_to_be_captured_or_represented(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            site = root / "site"
            site.mkdir()
            (site / "index.html").write_text("<!doctype html><title>root</title>", encoding="utf-8")
            for name in ("about", "contact"):
                page = site / name
                page.mkdir()
                (page / "index.html").write_text(f"<!doctype html><title>{name}</title>", encoding="utf-8")
            contract["scope"]["route_coverage"] = {
                "mode": "representative",
                "rationale": "The documented repair-intake route represents equivalent information-only public routes.",
                "discovered_route_map": [
                    {
                        "route": "/",
                        "coverage": "captured",
                        "representative_route": None,
                        "equivalence_rationale": "The root route is directly reviewed at wide and narrow conditions.",
                    },
                    {
                        "route": "/about/",
                        "coverage": "represented",
                        "representative_route": "/",
                        "equivalence_rationale": "About uses the same informational route job, reading order, public shell, and responsive system as the reviewed root route.",
                    },
                ],
            }
            report = AUDITOR.audit_payload(root, contract)
            self.assertFalse(report["ready"])
            self.assertIn(
                "route-coverage-map-missing-discovered-routes",
                {entry["code"] for entry in report["gaps"]},
            )

    def test_static_route_mapping_can_use_one_directly_reviewed_equivalent_representative(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            contract = copy.deepcopy(prepared_contract(root))
            site = root / "site"
            site.mkdir()
            (site / "index.html").write_text("<!doctype html><title>root</title>", encoding="utf-8")
            for name in ("about", "contact"):
                page = site / name
                page.mkdir()
                (page / "index.html").write_text(f"<!doctype html><title>{name}</title>", encoding="utf-8")
            contract["scope"]["route_coverage"] = {
                "mode": "representative",
                "rationale": "One complete route is a reviewed representative for equivalent information-only public routes.",
                "discovered_route_map": [
                    {
                        "route": "/",
                        "coverage": "captured",
                        "representative_route": None,
                        "equivalence_rationale": "The root route is directly reviewed at wide and narrow conditions.",
                    },
                    {
                        "route": "/about/",
                        "coverage": "represented",
                        "representative_route": "/",
                        "equivalence_rationale": "About has the same direct-entry information job, responsive body system, and persistent public shell as the reviewed root route.",
                    },
                    {
                        "route": "/contact/",
                        "coverage": "represented",
                        "representative_route": "/",
                        "equivalence_rationale": "Contact has the same informational route job, responsive reading sequence, and public system as the reviewed root route in this static prototype.",
                    },
                ],
            }
            report = AUDITOR.audit_payload(root, contract)
            self.assertTrue(report["ready"])

    def test_direction_ready_lifecycle_rejects_unresolved_draft_values(self) -> None:
        template = json.loads(
            (SKILL_ROOT / "templates" / "project-contrast-template.json").read_text(encoding="utf-8")
        )
        template["record_status"] = "direction-ready"
        errors, _ = AUDITOR.validate_contract_payload(template)
        codes = {entry["code"] for entry in errors}
        self.assertIn("lifecycle-field-unresolved", codes)
        self.assertIn("lifecycle-evidence-unresolved", codes)

    def test_draft_template_is_explicitly_unresolved_without_placeholder_prose(self) -> None:
        template = json.loads(
            (SKILL_ROOT / "templates" / "project-contrast-template.json").read_text(encoding="utf-8")
        )
        template["created_with"] = "design-dna test"
        errors, _ = AUDITOR.validate_contract_payload(template)
        self.assertFalse(errors)
        self.assertEqual(template["record_status"], "draft")
        self.assertIsNone(template["scope"]["project_id"])
        self.assertIsNone(template["selected_direction"]["organizing_answer"])
        self.assertNotIn("Replace with", json.dumps(template))

    def test_cli_writes_a_hash_bound_ready_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepared_contract(root)
            result = subprocess.run(
                [
                    sys.executable,
                    str(AUDITOR_PATH),
                    str(root),
                    "--require-ready",
                    "--stdout",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            report = json.loads(result.stdout)
            self.assertTrue(report["ready"])
            self.assertFalse(report["automatic_aesthetic_pass"])
            self.assertTrue((root / ".design-dna" / "project-contrast-audit.json").is_file())


class ProjectContrastInitializerTests(unittest.TestCase):
    def run_initializer(self, root: Path, *arguments: str) -> dict:
        result = subprocess.run(
            [sys.executable, str(INITIALIZER_PATH), "--project", str(root), *arguments, "--json"],
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(result.stdout)

    def test_project_contrast_profile_selects_record_and_capability(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = self.run_initializer(root, "--profile", "project-contrast")
            self.assertIn("project-contrast", result["records"])
            self.assertIn("project-contrast", result["assurance_profiles"])
            self.assertIn("project-contrast", result["evidence_capabilities"])
            state = json.loads((root / ".design-dna" / "state.json").read_text(encoding="utf-8"))
            self.assertIn("project-contrast", state["records"])

    def test_check_state_warns_when_project_contrast_is_an_unresolved_draft(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.run_initializer(root, "--profile", "project-contrast")
            result = self.run_initializer(root, "--check-state")
            self.assertTrue(result["ok"])
            self.assertTrue(any("project-contrast.json remains draft" in warning for warning in result["warnings"]))

    def test_showcase_owner_recurrence_trigger_installs_bound_capability(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = self.run_initializer(
                root,
                "--profile", "showcase",
                "--trigger", "owner-recurrence-requirement",
            )
            self.assertEqual(result["triggers"], ["owner-recurrence-requirement"])
            self.assertIn("project-contrast", result["records"])
            self.assertIn("project-contrast", result["evidence_capabilities"])
            contract = json.loads((root / ".design-dna" / "project-contrast.json").read_text(encoding="utf-8"))
            self.assertEqual(contract["scope"]["trigger"], ["owner-recurrence-requirement"])

    def test_check_state_fails_when_active_owner_recurrence_remains_draft(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.run_initializer(
                root,
                "--profile", "showcase",
                "--trigger", "owner-recurrence-requirement",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(INITIALIZER_PATH),
                    "--project", str(root),
                    "--check-state",
                    "--json",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            payload = json.loads(result.stdout)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(payload["ok"])
            self.assertTrue(any("Active owner-recurrence-requirement" in failure for failure in payload["failures"]))

    def test_migrate_replaces_only_known_legacy_placeholder_record_with_explicit_draft(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.run_initializer(
                root,
                "--profile", "showcase",
                "--trigger", "owner-recurrence-requirement",
            )
            path = root / ".design-dna" / "project-contrast.json"
            path.write_text(json.dumps(legacy_placeholder_contract(), indent=2) + "\n", encoding="utf-8")
            before_migration = subprocess.run(
                [
                    sys.executable,
                    str(INITIALIZER_PATH),
                    "--project", str(root),
                    "--check-state",
                    "--json",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            before_payload = json.loads(before_migration.stdout)
            self.assertNotEqual(before_migration.returncode, 0)
            self.assertTrue(any("Active owner-recurrence-requirement" in failure for failure in before_payload["failures"]))
            result = self.run_initializer(root, "--migrate")
            self.assertTrue(result["ok"])
            migrated = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(migrated["record_status"], "draft")
            self.assertEqual(migrated["scope"]["trigger"], ["owner-recurrence-requirement"])
            self.assertIsNone(migrated["scope"]["project_id"])
            report = json.loads((root / ".design-dna" / "migration-report.json").read_text(encoding="utf-8"))
            self.assertEqual(
                report["project_contrast_migrations"][0]["disposition"],
                "known-placeholder-record-reset-to-explicit-draft",
            )
            repeated = self.run_initializer(root, "--migrate")
            self.assertEqual(repeated["actions"][0]["action"], "migration-not-needed")

    def test_owner_recurrence_trigger_refuses_a_non_showcase_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = subprocess.run(
                [
                    sys.executable,
                    str(INITIALIZER_PATH),
                    "--project", str(root),
                    "--profile", "standard",
                    "--trigger", "owner-recurrence-requirement",
                    "--json",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("trigger-profile-mismatch", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
