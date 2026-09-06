"""Maintenance orchestration with the actual strict packaged validator callbacks.

The source/census records here are explicitly synthetic contract fixtures,
not claims of a public reference study or a browser-tested website. This test
proves the operator's before/after integration without replacing any callback
with an unconditional pass.
"""
from __future__ import annotations

import hashlib
from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import test_reference_dossier as source_fixture


INITIALIZER = source_fixture.INITIALIZER
SCRIPTS = source_fixture.SKILL / "scripts"
WORKFLOW = INITIALIZER.load_bundled_source_module("maintenance_integration_workflow", SCRIPTS / "maintenance_workflow.py")
LEGACY = INITIALIZER.load_bundled_source_module("maintenance_integration_legacy", SCRIPTS / "legacy_maintenance.py")


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def direction_fixture(project: Path) -> None:
    state = project / ".design-dna"
    binding = state / "brief.md"
    sections = INITIALIZER.REQUIRED_RECORD_SECTIONS["direction"] | INITIALIZER.REFERENCE_SOURCED_DIRECTION_SECTIONS
    values = {
        "Identity and intent": "This contract fixture maintains the existing home comparison route and its truthful product information without adding route scope.",
        "Truth and provenance": "Current fixture facts come from the bound brief. The source observations and rendered records are synthetic test evidence, not a client website.",
        "Responsive, accessible, and functional behavior": "Preserve the existing wide and narrow rest, primary hover and keyboard focus states and their exact source relationships.",
        "Owner and release state": "This is an isolated maintenance integration test with no owner acceptance, live deployment, or claim of public-site readiness.",
        "Reference-sourced organizing logic": "- Project evidence: The bound fixture brief establishes the comparison information and preserved home route.\n- Organizing logic: Selected ranks 1 and 2 supply the measured comparison arrangement and compatible supporting controls.",
        "Observable consequential design decisions": "| Decision | Selected source rank and project-fit reason | Observable consequence | Verification |\n| --- | --- | --- | --- |\n| Preserve comparison arrangement | Rank 1 measured source arrangement supports the existing comparison job. | The home arrangement keeps the direct source-bound component in both viewports. | Compare exact generated census component roots with the frozen source map. |",
        "Material, media, and public-copy boundary": "\n".join([
            "- Physical or sensory subject: no",
            "- Explicit owner request for photos or rich media: no",
            "- Material and media posture: inherited-system",
            "- Project-specific basis: This isolated contract test preserves an existing source-bound system with no new material media decision.",
            "- Media roles and truth boundary: Synthetic contract records are not photographs or evidence of an actual public source.",
            "- Asset manifest and readiness: Not applicable because this scoped fixture changes no visible asset bytes.",
            "- Deliberately media-light rationale: Not applicable because the existing source system is inherited without a media change.",
            "- Media-light exception basis: Not applicable because no physical subject or requested-media exception applies.",
            "- Media-light exception approval: Not applicable because no owner media exception is used.",
            "- Media-light exception evidence: Not applicable because no owner media exception is used.",
            "- Owner-rejection disposition: not-applicable; no owner-rejected candidate exists in this isolated contract test.",
            "- Protected facts and functions: Preserve all fixture comparison information and the existing hover and keyboard focus states.",
            "- Public-copy boundary: Keep source attribution, internal maintenance status and fixture vocabulary out of visitor copy.",
        ]),
    }
    body = "<!-- proportional-evidence-v1 -->\n\n" + "\n\n".join("## " + heading + "\n\n" + values.get(heading, "This contract fixture preserves the existing scoped comparison relationship with no additional public claims.") for heading in sorted(sections)) + "\n"
    metadata = {"schema_version": "1", "evidence_contract": INITIALIZER.PROPORTIONAL_EVIDENCE_CONTRACT,
        "record_status": "complete", "record_body_sha256": INITIALIZER.body_sha256(body),
        "binding_kind": "artifact", "binding_id": "maintenance-test-current-brief",
        "binding_path": ".design-dna/brief.md", "binding_sha256": hashlib.sha256(binding.read_bytes()).hexdigest(),
        "completion_owner": "synthetic-contract-test-producer", "completed_at": "2026-09-04T14:00:00Z",
        "unresolved_high": "0", "unresolved_medium": "0", "limitations": "Contract integration only; no public study, actual browser result, aesthetic judgment or owner approval."}
    (state / "direction.md").write_text("---\n" + "\n".join(f"{key}: {json.dumps(value)}" for key, value in metadata.items()) + "\n---\n" + body, encoding="utf-8")
    (state / "state.json").write_text(INITIALIZER.state_manifest("12.0.0-test", ("direction",), ("standard",)), encoding="utf-8")


def prepare_asset_replacement(fixture, mapping):
    """Prepare both immutable asset IDs before freezing existing-site history."""
    decision = mapping["decisions"][0]
    records = []
    bindings = []
    for number, color in ((1, (31, 61, 91)), (2, (51, 81, 111))):
        file = fixture.project / f"assets/source-{number}.png"
        source_fixture.write_png(file, width=120, height=80, rgb=color)
        digest = source_fixture.sha256_of(file)
        size = file.stat().st_size
        records.append("\n".join([
            f"  - id: ASSET-00{number}", f"    source_path: assets/source-{number}.png",
            f"    source_sha256: {digest}", "    source_mapping:",
            f"      source_id: {decision['source_mapping']['id']}",
            f"      observation: {decision['source_mapping']['observation']}",
            f"      observation_sha256: {decision['source_mapping']['sha256']}",
            "    runtime_output:", f"      output_path: /assets/source-{number}.png",
            f"      output_sha256: {digest}", f"      output_bytes: {size}",
            "      derivation: direct-copy", "      transformation_record: ''", "      transformation_record_sha256: ''",
        ]))
        bindings.append({"asset_id": f"ASSET-00{number}", "asset_manifest": ".design-dna/assets.yml",
            "asset_manifest_sha256": None, "rendered_media_kind": "image", "source_media_kind": "image",
            "role": "Opening source compositional image", "rendered_url": f"http://127.0.0.1:4960/assets/source-{number}.png",
            "rendered_sha256": digest, "rendered_bytes": size, "resource_type": "image", "temporal_mode": "still",
            "crop_by_viewport": {profile: {"width": width, "height": 80, "object_fit": "cover", "object_position": "50% 50%"} for profile, width in (("wide", 120), ("narrow", 100))}})
    manifest = fixture.state / "assets.yml"
    manifest.write_text("schema_version: 2\nassets:\n" + "\n".join(records) + "\n", encoding="utf-8")
    for binding in bindings:
        binding["asset_manifest_sha256"] = source_fixture.sha256_of(manifest)
    decision["asset_role_binding"] = bindings[0]
    planned = deepcopy(mapping)
    planned["decisions"][0]["asset_role_binding"] = bindings[1]
    return planned


def bind_asset_census(scan, mapping):
    decision = mapping["decisions"][0]
    asset = decision["asset_role_binding"]
    for check in scan["checks"]:
        if decision["decision_id"] not in check["visible_decision_ids"]:
            continue
        crop = asset["crop_by_viewport"][check["viewport"]]
        check["media_inventory"] = [{"decision_id": decision["decision_id"], "asset_id": asset["asset_id"],
            "component_key": "component:" + decision["component_id"], "media_kind": "image",
            "source": asset["rendered_url"], "rendered_url": asset["rendered_url"], "poster": None,
            "object_fit": crop["object_fit"], "object_position": crop["object_position"],
            "box": {"width": crop["width"], "height": crop["height"]}, "temporal": None,
            "resource": {"sha256": asset["rendered_sha256"], "bytes": asset["rendered_bytes"], "resource_type": "image"}}]


class MaintenanceIntegrationTests(unittest.TestCase):
    def test_full_callbacks_accept_baseline_then_exact_scoped_current_snapshot(self):
        self.maxDiff = None
        with tempfile.TemporaryDirectory(prefix="dna-maintenance-integrated-") as temporary:
            fixture = source_fixture.DossierProject(temporary)
            sources = [source_fixture.DEFAULT_SOURCES[0], source_fixture.DEFAULT_SOURCES[2]]
            strong = [fixture.strong_row(rank, source=sources[rank - 1]) for rank in (1, 2)]
            compared = [fixture.candidate_row(rank, source=sources[rank - 1], selected=True) for rank in (1, 2)]
            compared.append(fixture.candidate_row(3, source=source_fixture.DEFAULT_SOURCES[4], selected=False, host="rejected-three.example.test"))
            components = []
            for name in source_fixture.REQUIRED_COMPONENTS:
                rank = 1 if name in {"first screen", "display typeface"} or name in source_fixture.BEHAVIOUR_COMPONENTS else 2
                frame = source_fixture.SHEET_FRAME_CELL if name in source_fixture.BEHAVIOUR_COMPONENTS else f"strong-{rank}-frames/strong-{rank}-001-rest.png"
                components.append(f"| {name} | {rank} | {frame} | {source_fixture.STRUCTURE_CELL} | {source_fixture.VALUES_CELL} | the primary route |")
            body = fixture.body(selected="1, 2", strong_rows=strong, candidate_rows=compared, component_rows=components)
            fixture.record_path.write_text(body, encoding="utf-8")
            direction_fixture(fixture.project)
            self.assertEqual([], INITIALIZER.prebuild_failures(fixture.project, require_first_screen=False, require_construction=False))
            current = fixture.state / "visible-decision-sources.json"
            mapping = json.loads(current.read_text(encoding="utf-8"))
            planned = prepare_asset_replacement(fixture, mapping)
            write_json(current, mapping)
            proposed = fixture.state / "maintenance-planned-map.json"
            write_json(proposed, planned)
            site = fixture.project / "existing-site.html"
            site.write_text("<!-- Existing source-bound implementation fixture. -->", encoding="utf-8")
            fixture_census = fixture.state / "evidence/component-census.json"
            baseline = fixture.state / "evidence/maintenance-baselines/baseline-0001/component-census.json"
            baseline.parent.mkdir(parents=True)
            scan = json.loads(fixture_census.read_text(encoding="utf-8"))
            scan["visible_decision_reconciliation"]["manifest_sha256"] = source_fixture.sha256_of(current)
            bind_asset_census(scan, mapping)
            for field in ("interaction_frame_directory", "interaction_video_directory"):
                shutil.copytree(fixture_census.parent / scan[field], baseline.parent / scan[field])
            snapshot = LEGACY.implementation_snapshot(fixture.project)
            scan["implementation_snapshot"] = {"algorithm": "sha256-files-v1", "files": snapshot, "sha256": LEGACY._digest(snapshot)}
            write_json(baseline, scan)
            plan = fixture.state / "maintenance-plan.json"
            write_json(plan, {"schema_version": 1, "planned_source_map": proposed.relative_to(fixture.project).as_posix(),
                "baseline_census": baseline.relative_to(fixture.project).as_posix(),
                "planned_changes": [{"path": "existing-site.html", "operation": "modify", "component_ids": [mapping["decisions"][0]["component_id"]]}]})
            result = WORKFLOW.begin(fixture.project, plan, INITIALIZER)
            self.assertFalse(result["public_readiness"])
            active = json.loads(current.read_text(encoding="utf-8"))
            self.assertEqual([], WORKFLOW.check(fixture.project, active, INITIALIZER))
            site.write_text("<!-- Existing source-bound implementation fixture; documented nonvisual maintenance. -->", encoding="utf-8")
            updated = json.loads(json.dumps(scan))
            snapshot = LEGACY.implementation_snapshot(fixture.project)
            updated["implementation_snapshot"] = {"algorithm": "sha256-files-v1", "files": snapshot, "sha256": LEGACY._digest(snapshot)}
            updated["scanned_at"] = "2026-09-04T15:00:00Z"
            updated["visible_decision_reconciliation"]["manifest_sha256"] = source_fixture.sha256_of(current)
            bind_asset_census(updated, active)
            # Generated media directories are derived from the output stem.
            # Keep the exact stem under a new parent so baseline and current
            # evidence are independent ordinary files with unchanged bindings.
            after = fixture.state / "evidence/maintenance-current/component-census.json"
            after.parent.mkdir(parents=True)
            for field in ("interaction_frame_directory", "interaction_video_directory"):
                shutil.copytree(baseline.parent / scan[field], after.parent / scan[field])
            write_json(after, updated)
            self.assertEqual([], WORKFLOW.check(fixture.project, active, INITIALIZER, current_scan=after, final=True))
            # Updating a permitted file after the new audit must not preserve
            # the full-callback pass, even though its scope remains permitted.
            site.write_text("<!-- Mutation after current rendered contract snapshot. -->", encoding="utf-8")
            self.assertIn("implementation file snapshot", " | ".join(WORKFLOW.check(fixture.project, active, INITIALIZER, current_scan=after, final=True)))


if __name__ == "__main__":
    unittest.main()
