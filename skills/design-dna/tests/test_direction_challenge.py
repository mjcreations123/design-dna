#!/usr/bin/env python3
"""Focused regression coverage for the Direction Challenge capability."""

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


SKILL_ROOT = Path(__file__).resolve().parents[1]
AUDITOR_PATH = SKILL_ROOT / "scripts" / "direction_challenge_audit.py"
INITIALIZER_PATH = SKILL_ROOT / "scripts" / "init_project_state.py"


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


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def load_auditor():
    specification = importlib.util.spec_from_file_location("direction_challenge_audit_test", AUDITOR_PATH)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


AUDITOR = load_auditor()
RENDER_AUDITOR = AUDITOR.load_render_review_adapter()


def write_schema3_render_review(
    evidence: Path,
    *,
    build_id: str,
    route: str,
    prefix: str,
) -> dict:
    """Write a compact but path-bound schema-3 package for proof tests.

    This deliberately exercises the same marker, frozen-source manifest,
    build, route, and exact PNG capture bindings required from a real renderer
    run. It is not used as a visual-quality fixture.
    """

    evidence.mkdir(parents=True, exist_ok=True)
    report_path = evidence / "render-review.json"
    marker_path = evidence / ".design-dna-render-review.json"
    screenshots_dir = evidence / "screenshots"
    screenshots_dir.mkdir()
    # Each root gets distinct fixture pixels. The audit must reject a later
    # attempt to relabel one root's proof image as another root's evidence.
    seed = sum(prefix.encode("ascii"))
    project_root = evidence.parents[1]
    proof_source = project_root / "proofs" / prefix
    proof_assets = proof_source / "assets"
    proof_assets.mkdir(parents=True, exist_ok=True)
    material_payload = png(
        32,
        32,
        (40 + seed % 160, 70 + seed % 130, 90 + seed % 120, 255),
    )
    material_name = f"{prefix}-material.png"
    material_path = proof_assets / material_name
    material_path.write_bytes(material_payload)
    source_payload = (
        "<!doctype html><title>proof</title>"
        f"<img src=\"assets/{material_name}\" alt=\"Material proof\">\n"
    ).encode("utf-8")
    source_path = proof_source / "index.html"
    source_path.write_bytes(source_payload)
    wide_payload = png(320, 480, (80 + seed % 140, 40 + seed % 120, 35 + seed % 100, 255))
    narrow_payload = png(240, 640, (25 + seed % 100, 85 + seed % 140, 70 + seed % 120, 255))
    wide_name = f"{prefix}-wide.png"
    narrow_name = f"{prefix}-narrow.png"
    (screenshots_dir / wide_name).write_bytes(wide_payload)
    (screenshots_dir / narrow_name).write_bytes(narrow_payload)
    contact_sheet_payload = b"<!doctype html><title>Schema-3 proof fixture</title>\n"
    (evidence / "contact-sheet.html").write_bytes(contact_sheet_payload)
    source_files = [
        {"path": "index.html", "bytes": len(source_payload), "sha256": digest(source_payload)},
        {"path": f"assets/{material_name}", "bytes": len(material_payload), "sha256": digest(material_payload)},
    ]
    manifest_digest = AUDITOR.source_manifest_digest(source_files)
    output_identity = {
        "id": "a" * 64,
        "path_sha256": RENDER_AUDITOR.rendered_output_path_sha256(evidence),
    }
    captures = []
    for capture_id, filename, payload, viewport_width, viewport_height, pixel_width, pixel_height in (
        (f"{prefix}-wide", wide_name, wide_payload, 320, 240, 320, 480),
        (f"{prefix}-narrow", narrow_name, narrow_payload, 240, 320, 240, 640),
    ):
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
            "interaction": {
                "requested_steps": 0,
                "completed_steps": 0,
                "status": "not-requested",
            },
            "screenshot": {
                "path": f"screenshots/{filename}",
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
            "target_input": "local-fixture",
            "target_kind": "local-directory",
        },
        "source_snapshot": {
            "policy": "frozen-deny-by-default-public-root",
            "root_kind": "explicit-target-public-root",
            "entry_path": "index.html",
            "drift_check": "passed-source-and-frozen-snapshot-before-report-and-commit",
            "manifest": {
                "algorithm": "sha256",
                "manifest_sha256": manifest_digest,
                "file_count": len(source_files),
                "total_bytes": sum(item["bytes"] for item in source_files),
                "files": source_files,
                "excluded_counts": {
                    "hidden_or_source_only_path": 0,
                    "sensitive_or_source_config": 0,
                    "extension_not_public_allowlist": 0,
                },
            },
        },
        "capture_contract": {
            "profiles": [{"id": "wide"}, {"id": "narrow"}],
            "scenarios": [{"id": f"{prefix}-default"}],
        },
        "routes": [{"id": "route-01", "requested": route, "url": f"http://127.0.0.1{route}"}],
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
            "capture_bytes": len(wide_payload) + len(narrow_payload),
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
            "tool": {"name": "design-dna-rendered-review", "version": "3.0.0"},
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
        "file": {"path": str(report_path.relative_to(evidence.parents[1])).replace("\\", "/"), "sha256": digest(report_payload)},
        "source_snapshot_manifest_sha256": manifest_digest,
        "wide_capture_id": f"{prefix}-wide",
        "narrow_capture_id": f"{prefix}-narrow",
        "material_evidence": {
            "posture": "asset-led",
            "assets": [{
                "path": material_path.relative_to(project_root).as_posix(),
                "sha256": digest(material_payload),
            }],
            "implementation_sources": [{
                "path": source_path.relative_to(project_root).as_posix(),
                "sha256": digest(source_payload),
            }],
            "rendered_observation": "The bound material image is present in the frozen source and visible as the proof's primary object at both widths.",
        },
    }


def rebind_schema3_report(report_path: Path, report: dict) -> str:
    """Rebuild the path-bound marker after a deliberate report mutation."""

    marker_path = report_path.with_name(".design-dna-render-review.json")
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


def root(root_id: str, *, logic: str, entry: str, operation: str, body: str, agency: str, surface: str) -> dict:
    return {
        "id": root_id,
        "brief_anchor": "A visitor needs to understand a small producer without invented business claims.",
        "organizing_logic": logic,
        "entry_encounter": entry,
        "content_operation": operation,
        "body_progression": body,
        "visitor_agency": agency,
        "surface_consequence": surface,
        "responsive_transformation": "The wide composition becomes a vertical sequence while the primary encounter and visitor operation remain intact.",
        "material": {
            "posture": "asset-led",
            "strategy": "A project-specific material image carries the opening recognition task rather than decorating a text shell.",
            "truth_boundary": "The image may establish material context but may not invent provenance, endorsement, performance, or business facts.",
        },
    }


def matrix_entry(left: dict, right: dict) -> dict:
    fields = ("organizing_logic", "content_operation")
    return {
        "root_a": left["id"],
        "root_b": right["id"],
        "incompatibilities": [
            {
                "field": field,
                "root_a_position": left[field],
                "root_b_position": right[field],
                "why_not_combined": "Combining these propositions would hide which visitor task structures the public encounter.",
            }
            for field in fields
        ],
    }


def prepared_contract(root_path: Path) -> dict:
    evidence = root_path / "evidence"
    evidence.mkdir(parents=True)
    proof_images = {
        "unprimed.md": b"Independent first observation before root labels and selection rationale.\n",
    }
    hashes: dict[str, str] = {}
    for name, payload in proof_images.items():
        (evidence / name).write_bytes(payload)
        hashes[name] = digest(payload)
    artifact_render = write_schema3_render_review(
        evidence / "artifact-render",
        build_id="artifact-proof-v1",
        route="/artifact/",
        prefix="artifact",
    )
    menu_render = write_schema3_render_review(
        evidence / "menu-render",
        build_id="menu-proof-v1",
        route="/menu/",
        prefix="menu",
    )
    artifact = root(
        "artifact-trail",
        logic="The site is an annotated making trail whose evidence accumulates through a single object.",
        entry="A partially resolved object invites inspection before any proposition is stated.",
        operation="Visitors inspect linked material decisions and assemble their own understanding.",
        body="Evidence expands from object detail to process consequence to a restrained next step.",
        agency="Visitors choose which evidence thread to open and compare.",
        surface="Material annotations remain subordinate to the object’s changing state.",
    )
    menu = root(
        "menu-argument",
        logic="The site is a sequence of deliberate choices that makes a producer’s point of view legible.",
        entry="A concise decision invites visitors to take a side before they see the offering.",
        operation="Visitors compare alternatives and trace why each decision matters.",
        body="A compact argument moves from premise to comparison to a practical invitation.",
        agency="Visitors select a competing premise and see its consequence.",
        surface="The argument’s measures clarify contrast without becoming a component gallery.",
    )
    field = root(
        "field-notebook",
        logic="The site behaves as a field notebook that reveals a place through dated observations.",
        entry="A current observation gives a visitor one situated clue rather than a sales claim.",
        operation="Visitors follow observations by time and place to orient themselves.",
        body="Small observations accumulate into a map-like orientation and a practical visit path.",
        agency="Visitors follow their own route across the observation trail.",
        surface="Marks distinguish observed material from the visitor’s current route without pretending to be a dashboard.",
    )
    contract = {
        "schema_version": 1,
        "created_with": "design-dna test",
        "record_status": "reviewed",
        "classification": "internal",
        "scope": {
            "project_id": "direction-challenge-fixture",
            "surface_scope": ["/"],
            "trigger": ["owner-recurrence-requirement"],
            "activation_basis": "The accountable owner explicitly reported that unrelated sites had begun to share one safe visual grammar.",
        },
        "reference_order": {
            "events": [
                {
                    "id": "source-packet",
                    "sequence": 1,
                    "kind": "supplied-source-material",
                    "source": "Owner-supplied brief and factual source packet.",
                    "root_ids": [],
                    "note": "Supplied source material is allowed before roots because it is the current project’s evidence.",
                },
                {
                    "id": "roots-first",
                    "sequence": 2,
                    "kind": "root-recorded",
                    "source": "Brief-native working session.",
                    "root_ids": [artifact["id"], menu["id"], field["id"]],
                    "note": "All three roots were articulated before polished external examples were viewed.",
                },
                {
                    "id": "post-root-reference",
                    "sequence": 3,
                    "kind": "polished-example",
                    "source": "Reference viewed only to test a root, not to supply a house style.",
                    "root_ids": [],
                    "note": "This comparison followed complete root articulation.",
                },
            ]
        },
        "roots": [artifact, menu, field],
        "challenge_matrix": [matrix_entry(artifact, menu), matrix_entry(artifact, field), matrix_entry(menu, field)],
        "proof_slices": [
            {
                "id": "artifact-slice",
                "root_id": artifact["id"],
                "build_id": "artifact-proof-v1",
                "purpose": "Test whether object-led inspection keeps the primary task clear at both proof widths.",
                "render_review": {"file": artifact_render["file"]},
                "source_snapshot_manifest_sha256": artifact_render["source_snapshot_manifest_sha256"],
                "route": "/artifact/",
                "wide_capture_id": artifact_render["wide_capture_id"],
                "narrow_capture_id": artifact_render["narrow_capture_id"],
                "material_evidence": artifact_render["material_evidence"],
            },
            {
                "id": "menu-slice",
                "root_id": menu["id"],
                "build_id": "menu-proof-v1",
                "purpose": "Test whether choice-led comparison holds together before a full page is implemented.",
                "render_review": {"file": menu_render["file"]},
                "source_snapshot_manifest_sha256": menu_render["source_snapshot_manifest_sha256"],
                "route": "/menu/",
                "wide_capture_id": menu_render["wide_capture_id"],
                "narrow_capture_id": menu_render["narrow_capture_id"],
                "material_evidence": menu_render["material_evidence"],
            },
        ],
        "selection": {
            "chosen_root_id": artifact["id"],
            "rejected_root_id": menu["id"],
            "selection_reason": "The artifact trail lets the factual source material carry the visitor’s first task without pretending the fictional producer has unavailable proof.",
            "rejection_reason": "The menu argument was coherent, but it foregrounded a comparative claim that the approved source packet could not support yet.",
            "rationale_recorded_at": "2026-08-12T02:02:00+00:00",
        },
        "implementation_boundary": {"status": "proof-slices", "evidence": "Only the two proof slices exist; broad implementation has not begun."},
        "review": {
            "unprimed": {
                "status": "complete",
                "reviewer_id": "independent-reviewer-01",
                "relationship": "independent-agent",
                "exposure": "unprimed-proof-slices-only",
                "observed_at": "2026-08-12T02:00:00+00:00",
                "frozen_at": "2026-08-12T02:01:00+00:00",
                "evidence": {"path": "evidence/unprimed.md", "sha256": hashes["unprimed.md"]},
                "reviewed_proof_slices": ["artifact-slice", "menu-slice"],
                "first_observation": "The two encounters signal different visitor actions before type, color, or image-specific language is considered.",
                "limitations": "This is an independent capture review, not an owner-acceptance or user-study claim.",
            }
        },
    }
    state = root_path / ".design-dna"
    state.mkdir()
    (state / "direction-challenge.json").write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
    return contract


class DirectionChallengeAuditTests(unittest.TestCase):
    def test_reviewed_contract_binds_schema3_source_build_route_and_pixels_without_aesthetic_score(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = prepared_contract(project)
            report = AUDITOR.audit_payload(project, contract)
            self.assertTrue(report["structural_valid"])
            self.assertTrue(report["ready"])
            self.assertFalse(report["automatic_aesthetic_pass"])
            verified_kinds = [entry["kind"] for entry in report["evidence"]["verified"]]
            self.assertEqual(verified_kinds.count("schema-3-render-review"), 2)
            self.assertEqual(verified_kinds.count("proof-capture"), 4)
            self.assertIn("unprimed-review", verified_kinds)

    def test_missing_second_proof_slice_blocks_proof_ready_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = copy.deepcopy(prepared_contract(project))
            contract["proof_slices"] = contract["proof_slices"][:1]
            errors, _ = AUDITOR.validate_contract_payload(contract)
            self.assertIn("lifecycle-proof-slices-missing", {entry["code"] for entry in errors})

    def test_explicit_template_marker_cannot_be_claimed_as_ready_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = copy.deepcopy(prepared_contract(project))
            contract["created_with"] = "__DESIGN_DNA_VERSION__"
            errors, _ = AUDITOR.validate_contract_payload(contract)
            self.assertIn(
                "unresolved-template-marker", {entry["code"] for entry in errors}
            )
            self.assertFalse(AUDITOR.audit_payload(project, contract)["ready"])

    def test_cosmetic_only_root_difference_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = copy.deepcopy(prepared_contract(project))
            first = contract["roots"][0]
            second = contract["roots"][1]
            for field in ("organizing_logic", "entry_encounter", "content_operation", "body_progression", "visitor_agency"):
                second[field] = first[field]
            for entry in contract["challenge_matrix"]:
                if {entry["root_a"], entry["root_b"]} == {first["id"], second["id"]}:
                    for row in entry["incompatibilities"]:
                        row["root_a_position"] = first[row["field"]]
                        row["root_b_position"] = first[row["field"]]
            errors, _ = AUDITOR.validate_contract_payload(contract)
            codes = {entry["code"] for entry in errors}
            self.assertIn("cosmetic-only-root-difference", codes)
            self.assertIn("cosmetic-only-matrix-row", codes)

    def test_bad_schema3_hash_and_wrong_wide_capture_are_blocking_evidence_findings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = copy.deepcopy(prepared_contract(project))
            contract["proof_slices"][0]["render_review"]["file"]["sha256"] = "0" * 64
            second = contract["proof_slices"][1]
            second["wide_capture_id"], second["narrow_capture_id"] = (
                second["narrow_capture_id"], second["wide_capture_id"]
            )
            report = AUDITOR.audit_payload(project, contract)
            self.assertFalse(report["ready"])
            codes = {entry["code"] for entry in report["findings"]}
            self.assertIn("invalid-proof-slice-evidence", codes)
            messages = " ".join(entry["message"] for entry in report["findings"])
            self.assertIn("SHA-256", messages)
            self.assertIn("not wider", messages)

    def test_tiny_schema3_viewports_cannot_pose_as_rendered_proof_slices(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = copy.deepcopy(prepared_contract(project))
            proof = contract["proof_slices"][0]
            report_path = project / proof["render_review"]["file"]["path"]
            rendered = json.loads(report_path.read_text(encoding="utf-8"))
            for capture in rendered["captures"]:
                capture["viewport"]["width"] = 2
                capture["viewport"]["height"] = 1
            proof["render_review"]["file"]["sha256"] = rebind_schema3_report(
                report_path, rendered
            )
            report = AUDITOR.audit_payload(project, contract)
            self.assertFalse(report["ready"])
            self.assertIn(
                "too small to act as wide/narrow rendered evidence",
                " ".join(entry["message"] for entry in report["findings"]),
            )

    def test_schema3_renderer_floor_rejects_adapter_only_239_pixel_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = copy.deepcopy(prepared_contract(project))
            proof = contract["proof_slices"][0]
            report_path = project / proof["render_review"]["file"]["path"]
            rendered = json.loads(report_path.read_text(encoding="utf-8"))
            for capture in rendered["captures"]:
                capture["viewport"]["width"] = 239
                capture["viewport"]["height"] = 240
            proof["render_review"]["file"]["sha256"] = rebind_schema3_report(
                report_path, rendered
            )
            report = AUDITOR.audit_payload(project, contract)
            self.assertFalse(report["ready"])
            self.assertIn(
                "240 by 240 CSS pixels",
                " ".join(entry["message"] for entry in report["findings"]),
            )

    def test_proof_slice_rejects_a_mismatched_frozen_source_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = copy.deepcopy(prepared_contract(project))
            contract["proof_slices"][0]["source_snapshot_manifest_sha256"] = "0" * 64
            report = AUDITOR.audit_payload(project, contract)
            self.assertFalse(report["ready"])
            messages = " ".join(entry["message"] for entry in report["findings"])
            self.assertIn("manifest digest does not match", messages)

    def test_proof_slice_rejects_wrong_schema3_route_or_capture_id(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = copy.deepcopy(prepared_contract(project))
            contract["proof_slices"][0]["route"] = "/other/"
            contract["proof_slices"][1]["wide_capture_id"] = "missing-capture"
            report = AUDITOR.audit_payload(project, contract)
            self.assertFalse(report["ready"])
            messages = " ".join(entry["message"] for entry in report["findings"])
            self.assertIn("does not match declared route", messages)
            self.assertIn("unknown schema-3 capture", messages)

    def test_proof_slice_cannot_reuse_the_same_schema3_captures_for_two_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = copy.deepcopy(prepared_contract(project))
            first, second = contract["proof_slices"]
            second["build_id"] = first["build_id"]
            second["render_review"] = copy.deepcopy(first["render_review"])
            second["source_snapshot_manifest_sha256"] = first["source_snapshot_manifest_sha256"]
            second["route"] = first["route"]
            second["wide_capture_id"] = first["wide_capture_id"]
            second["narrow_capture_id"] = first["narrow_capture_id"]
            second["material_evidence"] = copy.deepcopy(first["material_evidence"])
            report = AUDITOR.audit_payload(project, contract)
            self.assertFalse(report["ready"])
            messages = " ".join(entry["message"] for entry in report["findings"])
            self.assertIn("reuses schema-3 capture", messages)

    def test_asset_led_proof_rejects_packaged_but_unused_image(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = copy.deepcopy(prepared_contract(project))
            proof = contract["proof_slices"][0]
            source_reference = proof["material_evidence"]["implementation_sources"][0]
            source_path = project / source_reference["path"]
            source_payload = b"<!doctype html><title>proof without material</title>\n"
            source_path.write_bytes(source_payload)
            source_reference["sha256"] = digest(source_payload)

            report_path = project / proof["render_review"]["file"]["path"]
            report = json.loads(report_path.read_text(encoding="utf-8"))
            files = report["source_snapshot"]["manifest"]["files"]
            source_entry = next(item for item in files if item["path"] == "index.html")
            source_entry.update({
                "bytes": len(source_payload),
                "sha256": digest(source_payload),
            })
            manifest = report["source_snapshot"]["manifest"]
            manifest["total_bytes"] = sum(item["bytes"] for item in files)
            manifest["manifest_sha256"] = AUDITOR.source_manifest_digest(files)
            proof["source_snapshot_manifest_sha256"] = manifest["manifest_sha256"]
            proof["render_review"]["file"]["sha256"] = rebind_schema3_report(
                report_path,
                report,
            )

            result = AUDITOR.audit_payload(project, contract)
            self.assertFalse(result["ready"])
            self.assertIn(
                "listing an unused image does not satisfy",
                " ".join(item["message"] for item in result["findings"]),
            )

    def test_two_roots_cannot_relabel_identical_proof_pixels(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = copy.deepcopy(prepared_contract(project))
            first, second = contract["proof_slices"]
            first_report_path = project / first["render_review"]["file"]["path"]
            second_report_path = project / second["render_review"]["file"]["path"]
            first_report = json.loads(first_report_path.read_text(encoding="utf-8"))
            second_report = json.loads(second_report_path.read_text(encoding="utf-8"))
            source_by_id = {capture["id"]: capture for capture in first_report["captures"]}
            target_by_id = {capture["id"]: capture for capture in second_report["captures"]}
            for source_id, target_id in (
                (first["wide_capture_id"], second["wide_capture_id"]),
                (first["narrow_capture_id"], second["narrow_capture_id"]),
            ):
                source = source_by_id[source_id]
                target = target_by_id[target_id]
                source_payload = (first_report_path.parent / source["screenshot"]["path"]).read_bytes()
                target_path = second_report_path.parent / target["screenshot"]["path"]
                target_path.write_bytes(source_payload)
                target["screenshot"].update({
                    "sha256": digest(source_payload),
                    "bytes": len(source_payload),
                    "pixel_width": source["screenshot"]["pixel_width"],
                    "pixel_height": source["screenshot"]["pixel_height"],
                })
            second_report["artifacts"]["capture_bytes"] = sum(
                capture["screenshot"]["bytes"] for capture in second_report["captures"]
            )
            second["render_review"]["file"]["sha256"] = rebind_schema3_report(
                second_report_path, second_report
            )
            report = AUDITOR.audit_payload(project, contract)
            self.assertFalse(report["ready"])
            self.assertIn(
                "independently rendered roots cannot share proof-image bytes",
                " ".join(entry["message"] for entry in report["findings"]),
            )

    def test_reviewed_contract_requires_explicit_unprimed_proof_only_exposure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = copy.deepcopy(prepared_contract(project))
            contract["review"]["unprimed"]["exposure"] = None
            errors, _ = AUDITOR.validate_contract_payload(contract)
            self.assertIn(
                "unprimed-review-exposure-invalid",
                {entry["code"] for entry in errors},
            )

    def test_unprimed_review_freeze_is_ordered_after_observation_and_before_rationale(self) -> None:
        cases = (
            (
                "freeze before observation",
                lambda payload: payload["review"]["unprimed"].__setitem__(
                    "frozen_at", "2026-08-12T01:59:00+00:00"
                ),
                "unprimed-review-freeze-before-observation",
            ),
            (
                "selection rationale at the freeze instant",
                lambda payload: payload["selection"].__setitem__(
                    "rationale_recorded_at", "2026-08-12T02:01:00+00:00"
                ),
                "unprimed-review-freeze-after-selection-rationale",
            ),
        )
        for label, mutate, expected_code in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                project = Path(temporary)
                contract = copy.deepcopy(prepared_contract(project))
                mutate(contract)
                errors, _ = AUDITOR.validate_contract_payload(contract)
                self.assertIn(expected_code, {entry["code"] for entry in errors})

    def test_unprimed_exposure_is_declared_not_inferred_from_review_prose(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = prepared_contract(project)
            artifact = project / "evidence" / "unprimed.md"
            payload = b"Freeform review prose is not parsed as evidence of reviewer exposure.\n"
            artifact.write_bytes(payload)
            contract["review"]["unprimed"]["evidence"]["sha256"] = digest(payload)
            report = AUDITOR.audit_payload(project, contract)
            self.assertTrue(report["ready"])

    def test_draft_template_is_truthfully_unresolved(self) -> None:
        template = json.loads((SKILL_ROOT / "templates" / "direction-challenge-template.json").read_text(encoding="utf-8"))
        template["created_with"] = "design-dna test"
        errors, _ = AUDITOR.validate_contract_payload(template)
        self.assertFalse(errors)
        self.assertEqual(template["record_status"], "draft")
        self.assertEqual(template["roots"], [])
        self.assertNotIn("Replace with", json.dumps(template))

    def test_known_legacy_draft_without_new_review_ordering_fields_remains_valid(self) -> None:
        template = json.loads(
            (SKILL_ROOT / "templates" / "direction-challenge-template.json").read_text(
                encoding="utf-8"
            )
        )
        template["created_with"] = "design-dna test"
        template["selection"].pop("rationale_recorded_at")
        template["review"]["unprimed"].pop("exposure")
        template["review"]["unprimed"].pop("frozen_at")
        errors, _ = AUDITOR.validate_contract_payload(template)
        self.assertFalse(errors)

    def test_runtime_enforces_published_collection_and_matrix_bounds(self) -> None:
        schema = json.loads(
            (SKILL_ROOT / "schemas" / "direction-challenge.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            AUDITOR.MAX_ROOTS, schema["properties"]["roots"]["maxItems"]
        )
        self.assertEqual(
            AUDITOR.MAX_CHALLENGE_MATRIX_ENTRIES,
            schema["properties"]["challenge_matrix"]["maxItems"],
        )
        self.assertEqual(
            AUDITOR.MAX_PROOF_SLICES,
            schema["properties"]["proof_slices"]["maxItems"],
        )
        self.assertEqual(
            AUDITOR.MAX_REFERENCE_EVENTS,
            schema["$defs"]["referenceOrder"]["properties"]["events"][
                "maxItems"
            ],
        )
        self.assertEqual(
            AUDITOR.MIN_MATRIX_INCOMPATIBILITIES,
            schema["$defs"]["matrixEntry"]["properties"]["incompatibilities"][
                "minItems"
            ],
        )
        self.assertEqual(
            AUDITOR.MAX_MATRIX_INCOMPATIBILITIES,
            schema["$defs"]["matrixEntry"]["properties"]["incompatibilities"][
                "maxItems"
            ],
        )
        self.assertEqual(
            AUDITOR.MAX_CREATED_WITH_LENGTH,
            schema["properties"]["created_with"]["maxLength"],
        )
        self.assertEqual(
            AUDITOR.MAX_TEXT_LENGTH,
            schema["$defs"]["nonEmptyString"]["maxLength"],
        )
        self.assertEqual(
            AUDITOR.MAX_FILE_REF_PATH_LENGTH,
            schema["$defs"]["fileRef"]["properties"]["path"]["maxLength"],
        )
        self.assertEqual(
            AUDITOR.MAX_SEQUENCE,
            schema["$defs"]["referenceEvent"]["properties"]["sequence"][
                "maximum"
            ],
        )
        self.assertEqual(
            {
                "id", "root_id", "build_id", "purpose", "render_review",
                "source_snapshot_manifest_sha256", "route", "wide_capture_id",
                "narrow_capture_id", "material_evidence",
            },
            set(schema["$defs"]["proofSlice"]["required"]),
        )
        self.assertEqual(
            {
                "chosen_root_id", "rejected_root_id", "selection_reason",
                "rejection_reason",
            },
            set(schema["$defs"]["selection"]["required"]),
        )
        self.assertEqual(
            {
                "status", "reviewer_id", "relationship", "observed_at", "evidence",
                "reviewed_proof_slices",
                "first_observation", "limitations",
            },
            set(schema["$defs"]["unprimedReview"]["required"]),
        )
        self.assertEqual(
            ["unprimed-proof-slices-only"],
            schema["$defs"]["unprimedReview"]["properties"]["exposure"]["oneOf"][0]["enum"],
        )
        lifecycle_condition = schema["allOf"][0]
        self.assertEqual(
            ["roots-ready", "proof-ready", "reviewed"],
            lifecycle_condition["if"]["properties"]["record_status"]["enum"],
        )
        self.assertEqual(
            ["rationale_recorded_at"],
            lifecycle_condition["then"]["properties"]["selection"]["required"],
        )
        self.assertEqual(
            ["exposure", "frozen_at"],
            lifecycle_condition["then"]["properties"]["review"]["properties"]["unprimed"]["required"],
        )

        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = prepared_contract(project)
            cases = (
                (
                    "roots",
                    "too-many-roots",
                    lambda payload: payload["roots"].extend(
                        copy.deepcopy(payload["roots"][:1])
                        * (AUDITOR.MAX_ROOTS - len(payload["roots"]) + 1)
                    ),
                ),
                (
                    "challenge matrix",
                    "too-many-challenge-matrix-entries",
                    lambda payload: payload["challenge_matrix"].extend(
                        copy.deepcopy(payload["challenge_matrix"][:1])
                        * (
                            AUDITOR.MAX_CHALLENGE_MATRIX_ENTRIES
                            - len(payload["challenge_matrix"])
                            + 1
                        )
                    ),
                ),
                (
                    "proof slices",
                    "too-many-proof-slices",
                    lambda payload: payload["proof_slices"].extend(
                        copy.deepcopy(payload["proof_slices"][:1])
                        * (
                            AUDITOR.MAX_PROOF_SLICES
                            - len(payload["proof_slices"])
                            + 1
                        )
                    ),
                ),
                (
                    "reference events",
                    "too-many-reference-events",
                    lambda payload: payload["reference_order"]["events"].extend(
                        copy.deepcopy(payload["reference_order"]["events"][:1])
                        * (
                            AUDITOR.MAX_REFERENCE_EVENTS
                            - len(payload["reference_order"]["events"])
                            + 1
                        )
                    ),
                ),
            )
            for label, expected_code, mutate in cases:
                with self.subTest(label=label):
                    candidate = copy.deepcopy(contract)
                    mutate(candidate)
                    errors, _ = AUDITOR.validate_contract_payload(candidate)
                    self.assertIn(
                        expected_code,
                        {entry["code"] for entry in errors},
                    )

            too_few_rows = copy.deepcopy(contract)
            too_few_rows["challenge_matrix"][0]["incompatibilities"] = (
                too_few_rows["challenge_matrix"][0]["incompatibilities"][:1]
            )
            errors, _ = AUDITOR.validate_contract_payload(too_few_rows)
            self.assertIn(
                "invalid-matrix-incompatibility-count",
                {entry["code"] for entry in errors},
            )

            too_many_rows = copy.deepcopy(contract)
            first_pair = too_many_rows["challenge_matrix"][0]["incompatibilities"]
            first_pair.extend(
                copy.deepcopy(first_pair[:1])
                * (AUDITOR.MAX_MATRIX_INCOMPATIBILITIES - len(first_pair) + 1)
            )
            errors, _ = AUDITOR.validate_contract_payload(too_many_rows)
            self.assertIn(
                "invalid-matrix-incompatibility-count",
                {entry["code"] for entry in errors},
            )

            scalar_cases = (
                (
                    "created_with",
                    "invalid-created-with",
                    lambda payload: payload.__setitem__(
                        "created_with", "x" * (AUDITOR.MAX_CREATED_WITH_LENGTH + 1)
                    ),
                ),
                (
                    "text",
                    "invalid-text",
                    lambda payload: payload["roots"][0].__setitem__(
                        "brief_anchor", "x" * (AUDITOR.MAX_TEXT_LENGTH + 1)
                    ),
                ),
                (
                    "render-review file path",
                    "invalid-path",
                    lambda payload: payload["proof_slices"][0]["render_review"]["file"].__setitem__(
                        "path", "x" * (AUDITOR.MAX_FILE_REF_PATH_LENGTH + 1)
                    ),
                ),
                (
                    "reference sequence",
                    "invalid-sequence",
                    lambda payload: payload["reference_order"]["events"][0].__setitem__(
                        "sequence", AUDITOR.MAX_SEQUENCE + 1
                    ),
                ),
                (
                    "proof route",
                    "invalid-route",
                    lambda payload: payload["proof_slices"][0].__setitem__(
                        "route", "not-a-route"
                    ),
                ),
            )
            for label, expected_code, mutate in scalar_cases:
                with self.subTest(label=label):
                    candidate = copy.deepcopy(contract)
                    mutate(candidate)
                    errors, _ = AUDITOR.validate_contract_payload(candidate)
                    self.assertIn(
                        expected_code,
                        {entry["code"] for entry in errors},
                    )


class DirectionChallengeInitializerTests(unittest.TestCase):
    def initializer_result(self, root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(INITIALIZER_PATH), "--project", str(root), *arguments, "--json"],
            check=False,
            capture_output=True,
            text=True,
        )

    def run_initializer(self, root: Path, *arguments: str) -> dict:
        result = self.initializer_result(root, *arguments)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_standalone_profile_is_available(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            result = self.run_initializer(project, "--profile", "direction-challenge")
            self.assertIn("direction-challenge", result["records"])
            self.assertIn("direction-challenge", result["assurance_profiles"])
            self.assertIn("direction-challenge", result["evidence_capabilities"])

    def test_first_use_guidance_reserves_challenge_for_explicit_multi_root_work(self) -> None:
        guide = " ".join(
            (
                SKILL_ROOT / "references" / "quality" / "direction-challenge.md"
            ).read_text(encoding="utf-8").split()
        )
        top_level = " ".join(
            (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8").split()
        )
        self.assertIn(
            "multi-root high-ambition greenfield concept challenge",
            guide,
        )
        self.assertIn(
            "A premium or high-ambition website alone selects Showcase, not Direction Challenge.",
            guide,
        )
        self.assertIn(
            "A generic premium or high-ambition website selects Showcase, not Direction Challenge.",
            top_level,
        )

    def test_owner_recurrence_trigger_adds_direction_challenge_alongside_project_contrast(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            result = self.run_initializer(project, "--profile", "showcase", "--trigger", "owner-recurrence-requirement")
            self.assertIn("project-contrast", result["records"])
            self.assertIn("direction-challenge", result["records"])
            self.assertIn("project-contrast", result["evidence_capabilities"])
            self.assertIn("direction-challenge", result["evidence_capabilities"])
            contract = json.loads((project / ".design-dna" / "direction-challenge.json").read_text(encoding="utf-8"))
            self.assertEqual(contract["scope"]["trigger"], ["owner-recurrence-requirement"])

    def test_triggered_recurrence_is_paired_in_state_and_both_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            result = self.run_initializer(
                project,
                "--profile",
                "direction-challenge",
                "--trigger",
                "owner-recurrence-requirement",
            )
            self.assertTrue(
                {"project-contrast", "direction-challenge"}.issubset(
                    result["records"]
                )
            )
            self.assertTrue(
                {"project-contrast", "direction-challenge"}.issubset(
                    result["evidence_capabilities"]
                )
            )
            for filename in ("project-contrast.json", "direction-challenge.json"):
                contract = json.loads(
                    (project / ".design-dna" / filename).read_text(
                        encoding="utf-8"
                    )
                )
                self.assertEqual(
                    contract["scope"]["trigger"],
                    ["owner-recurrence-requirement"],
                )

    def test_add_trigger_requires_an_existing_paired_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            self.run_initializer(project, "--profile", "project-contrast")
            result = self.initializer_result(
                project,
                "--add-trigger",
                "owner-recurrence-requirement",
            )
            self.assertEqual(result.returncode, 2)
            error = json.loads(result.stderr)
            self.assertEqual(error["error"]["code"], "recurrence-records-required")

    def test_state_and_readiness_require_both_recurrence_records_capabilities_and_triggers(self) -> None:
        def checked_failures(project: Path) -> tuple[list[str], list[str]]:
            state_result = self.initializer_result(project, "--check-state")
            ready_result = self.initializer_result(project, "--check-ready")
            self.assertEqual(state_result.returncode, 1)
            self.assertEqual(ready_result.returncode, 1)
            return (
                json.loads(state_result.stdout)["failures"],
                json.loads(ready_result.stdout)["failures"],
            )

        cases = (
            (
                "project-contrast-only trigger",
                lambda state_root: self._remove_recurrence_trigger(
                    state_root / "direction-challenge.json"
                ),
                "inconsistent paired triggers",
            ),
            (
                "direction-challenge-only trigger",
                lambda state_root: self._remove_recurrence_trigger(
                    state_root / "project-contrast.json"
                ),
                "inconsistent paired triggers",
            ),
            (
                "missing paired record",
                self._remove_recurrence_record,
                "both paired records must exist",
            ),
            (
                "missing recurrence capability",
                self._remove_recurrence_capability,
                "both applicable evidence capabilities",
            ),
        )
        for label, mutate, expected in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                project = Path(temporary)
                self.run_initializer(
                    project,
                    "--profile",
                    "showcase",
                    "--trigger",
                    "owner-recurrence-requirement",
                )
                mutate(project / ".design-dna")
                state_failures, ready_failures = checked_failures(project)
                self.assertTrue(
                    any(expected in failure for failure in state_failures),
                    state_failures,
                )
                self.assertTrue(
                    any(expected in failure for failure in ready_failures),
                    ready_failures,
                )

    @staticmethod
    def _remove_recurrence_trigger(path: Path) -> None:
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["scope"]["trigger"] = []
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def _remove_recurrence_record(state_root: Path) -> None:
        payload = json.loads((state_root / "state.json").read_text(encoding="utf-8"))
        payload["records"].remove("direction-challenge")
        (state_root / "direction-challenge.json").unlink()
        (state_root / "state.json").write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )

    @staticmethod
    def _remove_recurrence_capability(state_root: Path) -> None:
        state_path = state_root / "state.json"
        payload = json.loads(state_path.read_text(encoding="utf-8"))
        payload["evidence_contract"]["applicable_capabilities"].remove(
            "direction-challenge"
        )
        state_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def test_check_ready_fails_for_an_unfinished_challenge(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            self.run_initializer(project, "--profile", "direction-challenge")
            result = subprocess.run(
                [sys.executable, str(INITIALIZER_PATH), "--project", str(project), "--check-ready", "--json"],
                check=False,
                capture_output=True,
                text=True,
            )
            payload = json.loads(result.stdout)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(payload["ok"])
            self.assertTrue(any("Direction Challenge evidence remains incomplete" in entry for entry in payload["failures"]))


if __name__ == "__main__":
    unittest.main()
