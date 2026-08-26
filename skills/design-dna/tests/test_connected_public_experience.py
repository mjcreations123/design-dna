#!/usr/bin/env python3
"""Focused regressions for the opt-in Connected Public Experience contract."""

from __future__ import annotations

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


SKILL = Path(__file__).resolve().parents[1]
INITIALIZER_PATH = SKILL / "scripts" / "init_project_state.py"
AUDITOR_PATH = SKILL / "scripts" / "connected_public_experience_audit.py"


def load_module(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


INITIALIZER = load_module("design_dna_connected_initializer", INITIALIZER_PATH)
AUDITOR = load_module("design_dna_connected_auditor", AUDITOR_PATH)


def text(value: str) -> str:
    return value + " enough detail to be an accountable project record."


def write_evidence(project: Path, relative: str, payload: bytes) -> dict[str, str]:
    path = project / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return {
        "path": relative,
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


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
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def source_snapshot(files: dict[str, bytes], *, entry_path: str) -> dict:
    entries = [
        {"path": path, "bytes": len(payload), "sha256": digest(payload)}
        for path, payload in sorted(files.items())
    ]
    manifest = json.dumps(entries, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return {
        "policy": "frozen-deny-by-default-public-root",
        "root_kind": "explicit-build-root",
        "entry_path": entry_path,
        "drift_check": "passed-source-and-frozen-snapshot-before-report-and-commit",
        "manifest": {
            "algorithm": "sha256",
            "manifest_sha256": digest(manifest),
            "file_count": len(entries),
            "total_bytes": sum(entry["bytes"] for entry in entries),
            "files": entries,
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
    route: str,
) -> dict[str, dict[str, str] | str]:
    """Write a compact path-bound schema-3 capture package for CPE regressions."""

    evidence.mkdir(parents=True, exist_ok=True)
    wide_payload = png(320, 480, (176, 88, 42, 255))
    narrow_payload = png(240, 640, (32, 112, 144, 255))
    (evidence / "wide.png").write_bytes(wide_payload)
    (evidence / "narrow.png").write_bytes(narrow_payload)
    contact_sheet = b"<!doctype html><title>Rendered review fixture</title>\n"
    (evidence / "contact-sheet.html").write_bytes(contact_sheet)
    output_identity = {
        "id": "a" * 64,
        "path_sha256": AUDITOR.load_render_review_adapter().rendered_output_path_sha256(evidence),
    }
    captures = []
    for capture_id, filename, payload, width, height, pixel_width, pixel_height in (
        ("home-wide", "wide.png", wide_payload, 320, 240, 320, 480),
        ("home-narrow", "narrow.png", narrow_payload, 240, 320, 240, 640),
    ):
        captures.append({
            "id": capture_id,
            "route_id": "route-01",
            "capture_status": "complete",
            "final_url": f"http://127.0.0.1{route}",
            "viewport": {"width": width, "height": height, "device_scale_factor": 1},
            "interaction": {"requested_steps": 0, "completed_steps": 0, "status": "not-requested"},
            "screenshot": {
                "path": filename,
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
        "build": {"id": build_id, "target_input": "fixture", "target_kind": "local-directory"},
        "source_snapshot": source_snapshot(
            {"index.html": b"<!doctype html><title>fixture build</title>\n"},
            entry_path="index.html",
        ),
        "capture_contract": {
            "profiles": [{"id": "wide"}, {"id": "narrow"}],
            "scenarios": [{"id": "default"}],
        },
        "routes": [{"id": "route-01", "requested": route, "url": f"http://127.0.0.1{route}"}],
        "captures": captures,
        "artifacts": {
            "contact_sheet": {
                "path": "contact-sheet.html",
                "sha256": digest(contact_sheet),
                "media_type": "text/html",
                "bytes": len(contact_sheet),
            },
            "report": {"path": "render-review.json", "bytes": 0},
            "marker": {"path": ".design-dna-render-review.json", "bytes": 0},
            "capture_bytes": len(wide_payload) + len(narrow_payload),
            "total_bytes": 0,
        },
        "manual_review": {},
    }
    marker_bytes = 0
    marker: dict = {}
    report_payload = b""
    for _ in range(12):
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
    (evidence / "render-review.json").write_bytes(report_payload)
    (evidence / ".design-dna-render-review.json").write_bytes(marker_payload)
    return {
        "report": {
            "path": str((evidence / "render-review.json").relative_to(evidence.parents[1])).replace("\\", "/"),
            "sha256": digest(report_payload),
        },
        "wide": {
            "path": str((evidence / "wide.png").relative_to(evidence.parents[1])).replace("\\", "/"),
            "sha256": digest(wide_payload),
        },
        "narrow": {
            "path": str((evidence / "narrow.png").relative_to(evidence.parents[1])).replace("\\", "/"),
            "sha256": digest(narrow_payload),
        },
    }


def rebind_schema3_package(evidence: Path, report: dict) -> str:
    """Rewrite a deliberately mutated schema-3 report and its path-bound marker."""

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


def functional_attestation(build_id: str, route: str, route_or_state: str) -> dict:
    return {
        "reviewer_id": "qa-reviewer-7",
        "reviewer_role": "implementation QA reviewer",
        "observed_at": "2026-08-12T12:00:00+00:00",
        "build_id": build_id,
        "route": route,
        "route_or_state": text(route_or_state),
        "state_conditions": [text("local demo fixture with saved selection state available")],
        "steps": [text("Open direct entry, save the selected record, confirm the outcome, then clear or continue")],
        "result": "passed",
        "limitations": text("This is a local recorded-review observation and not a live or independently verified service result"),
        "verification_class": "recorded-review",
    }


def ready_contract(project: Path, *, staff: bool = False) -> dict:
    build_id = "candidate-build-7"
    direct = write_schema3_render_review(
        project / "evidence" / "direct",
        build_id=build_id,
        route="/catalog",
    )
    contract = {
        "schema_version": 1,
        "created_with": "design-dna test-fixture",
        "record_status": "reviewed",
        "classification": "internal",
        "applicability": {
            "status": "applicable",
            "reason": text("The public visitor moves from a catalog decision to a local saved request"),
            "blocking_dependency": None,
            "next_action": None,
        },
        "pre_direction_constraints": {
            "direct_entry_questions": [
                {"entry": text("/catalog direct entry"), "question": text("Which approved item can I compare or save from this entry")}
            ],
            "truth_and_entity_constraints": [
                {"subject": text("seasonal item records"), "constraint": text("Only the approved scenario fixture may be shown as available"), "authority": text("fixture owner and project claim ledger")}
            ],
        },
        "selected_root_continuity": {
            "selected_root_id": "catalog-object-path",
            "continuity_model": text("A selected object carries into the request worksheet while direct entry starts from a clear empty selection"),
            "handoffs_or_resets": [
                {"from": text("catalog item"), "to": text("request worksheet"), "carry_or_reset": text("Carry the selected object and reset unselected optional fields"), "visitor_reason": text("The visitor keeps the decision that matters without inheriting accidental form state")}
            ],
            "meaningful_path": {
                "arrival": text("A direct visitor lands on an approved catalog object"),
                "decision": text("The visitor decides to add the object to a request"),
                "action": text("The visitor saves the selection in the local worksheet"),
                "outcome": text("The local worksheet confirms the saved selection and next step"),
                "recovery_or_continuation": text("The visitor can clear the selection or continue to a related object"),
            },
            "state_authority_crosswalk": [
                {"subject": text("catalog description"), "delivery": "demo", "content": "approved", "behavior": "illustrative", "authority": text("approved fixture packet")},
                {"subject": text("saved request selection"), "delivery": "demo", "content": "scenario", "behavior": "local-only", "authority": text("local interaction implementation")},
            ],
            "proof_plan": {
                "rendered": [{
                    "id": "render-direct",
                    "purpose": text("Observe subject and useful next move on direct entry"),
                    "final_disposition": "final-bound",
                    "superseded_reason": None,
                }],
                "functional": [{
                    "id": "path-run",
                    "purpose": text("Exercise save outcome and clear or continuation behavior"),
                    "final_disposition": "final-bound",
                    "superseded_reason": None,
                }],
            },
        },
        "root_variation": {
            "strategy": "not-required",
            "detail": None,
            "entries": [],
            "project_contrast_mapping": None,
        },
        "staff_admin_split": {
            "status": "not-requested",
            "public_boundary": None,
            "back_office_boundary": None,
            "operate_mode": "not-required",
            "fixture": {"status": "none", "authority": None, "content_or_state": None, "boundary": None, "descriptor": None},
        },
        "final_closure": {
            "status": "complete",
            "reviewed_build_id": build_id,
            "rendered_evidence": [
                {
                    "id": "render-direct",
                    "route_or_state": text("/catalog direct entry default"),
                    "route": "/catalog",
                    "coverage": ["direct-entry"],
                    "file": direct["wide"],
                    "render_review": {"file": direct["report"], "capture_id": "home-wide"},
                    "observation": text("The subject and next move are visible before the local demo boundary"),
                }
            ],
            "functional_path_evidence": [
                {
                    "id": "path-run",
                    "coverage": ["action", "outcome", "recovery-or-continuation"],
                    "result": "passed",
                    "artifact": None,
                    "recorded_result": text("Direct entry, save outcome, and clear continuation were exercised in the exact reviewed build"),
                    "attestation": functional_attestation(build_id, "/catalog", "/catalog local saved-selection path"),
                }
            ],
            "proof_coverage": {"direct_entry_evidence_ids": ["render-direct"], "recovery_or_continuation_evidence_ids": ["path-run"]},
            "conclusion": text("The catalog-to-request continuity is coherent within its clearly local demo boundary"),
            "limitations": text("No live inventory, payment, account, or staff operation was verified in this local demo"),
        },
    }
    if staff:
        staff_render = write_schema3_render_review(
            project / "evidence" / "staff",
            build_id=build_id,
            route="/staff/requests",
        )
        fixture_authority = text("approved local fixture owner")
        fixture_state = text("one synthetic request is awaiting a clearly named staff review decision")
        fixture_boundary = text("local fixture only; no customer or production data is present")
        descriptor = write_evidence(
            project,
            "evidence/staff-fixture-descriptor.json",
            (json.dumps({
                "schema_version": 1,
                "privacy_classification": "synthetic",
                "contains_personal_data": False,
                "meaningful_state": fixture_state,
                "record_count": 1,
                "authority": fixture_authority,
                "boundary": fixture_boundary,
            }, indent=2) + "\n").encode("utf-8"),
        )
        contract["staff_admin_split"] = {
            "status": "requested",
            "public_boundary": text("Public visitors can prepare a request but cannot access staff record controls"),
            "back_office_boundary": text("Staff route is a local fixture for reviewing request status and only uses Operate mode"),
            "operate_mode": "operate",
            "final_evidence": {
                "rendered_evidence_id": "render-staff",
                "functional_evidence_id": "staff-run",
            },
            "fixture": {
                "status": "local-fixture",
                "authority": fixture_authority,
                "content_or_state": fixture_state,
                "boundary": fixture_boundary,
                "descriptor": descriptor,
            },
        }
        contract["final_closure"]["rendered_evidence"].append({
            "id": "render-staff",
            "route_or_state": text("/staff/requests local non-empty review state"),
            "route": "/staff/requests",
            "coverage": ["staff-back-office"],
            "file": staff_render["wide"],
            "render_review": {"file": staff_render["report"], "capture_id": "home-wide"},
            "observation": text("The staff route exposes a meaningful local fixture state while preserving its back-office boundary"),
        })
        contract["selected_root_continuity"]["proof_plan"]["rendered"].append({
            "id": "render-staff",
            "purpose": text("Observe the requested staff branch with non-empty local fixture state"),
            "final_disposition": "final-bound",
            "superseded_reason": None,
        })
        contract["final_closure"]["functional_path_evidence"].append({
            "id": "staff-run",
            "coverage": ["staff-back-office"],
            "result": "passed",
            "artifact": None,
            "recorded_result": text("The local staff fixture opened, exposed its named review state, and returned to the public boundary without a live action"),
            "attestation": functional_attestation(build_id, "/staff/requests", "/staff/requests local review state"),
        })
        contract["selected_root_continuity"]["proof_plan"]["functional"].append({
            "id": "staff-run",
            "purpose": text("Exercise the requested staff branch and verify its non-empty local fixture boundary"),
            "final_disposition": "final-bound",
            "superseded_reason": None,
        })
    return contract


def mark_not_applicable(contract: dict) -> dict:
    """Apply the canonical reviewed CPE non-applicability closure in tests."""

    contract["applicability"] = {
        "status": "not-applicable",
        "reason": text("This is a bounded single-screen editorial notice with no linked content or carrying state"),
        "blocking_dependency": None,
        "next_action": None,
    }
    contract["record_status"] = "reviewed"
    contract["final_closure"] = {
        "status": "not-applicable",
        "reviewed_build_id": None,
        "rendered_evidence": [],
        "functional_path_evidence": [],
        "proof_coverage": {
            "direct_entry_evidence_ids": [],
            "recovery_or_continuation_evidence_ids": [],
        },
        "conclusion": None,
        "limitations": None,
    }
    return contract


def mark_direction_ready(contract: dict) -> dict:
    """Keep the resolved plan while returning final closure to prebuild state."""

    contract["record_status"] = "direction-ready"
    for kind in ("rendered", "functional"):
        for item in contract["selected_root_continuity"]["proof_plan"][kind]:
            item["final_disposition"] = "planned"
            item["superseded_reason"] = None
    contract["final_closure"] = {
        "status": "draft",
        "reviewed_build_id": None,
        "rendered_evidence": [],
        "functional_path_evidence": [],
        "proof_coverage": {
            "direct_entry_evidence_ids": [],
            "recovery_or_continuation_evidence_ids": [],
        },
        "conclusion": None,
        "limitations": None,
    }
    if contract["staff_admin_split"].get("status") == "requested":
        contract["staff_admin_split"]["final_evidence"] = None
    return contract


class ConnectedPublicExperienceTests(unittest.TestCase):
    def test_non_selected_standard_remains_non_connected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            state = project / ".design-dna"
            version = INITIALIZER.release_version(SKILL)
            profiles = INITIALIZER.assurance_profiles_for_request(
                "standard", INITIALIZER.PROFILES["standard"],
            )
            INITIALIZER.render_new_state(
                SKILL, state, version, INITIALIZER.PROFILES["standard"], profiles,
            )
            payload = json.loads((state / "state.json").read_text(encoding="utf-8"))
            self.assertNotIn("connected-public-experience", payload["records"])
            self.assertNotIn(
                "connected-public-experience",
                payload["evidence_contract"]["applicable_capabilities"],
            )
            failures, _warnings = INITIALIZER.validate_state(project, version)
            self.assertEqual([], failures)

    def test_explicit_capability_creates_its_canonical_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            result = subprocess.run(
                [
                    sys.executable,
                    str(INITIALIZER_PATH),
                    "--project", str(project),
                    "--profile", "standard",
                    "--evidence-capability", "connected-public-experience",
                    "--json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            payload = json.loads(result.stdout)
            self.assertIn("connected-public-experience", payload["records"])
            self.assertIn("connected-public-experience", payload["evidence_capabilities"])
            self.assertTrue((project / ".design-dna" / "connected-public-experience.json").is_file())

    def test_full_profile_carries_the_explicit_connected_capability(self) -> None:
        profiles = INITIALIZER.assurance_profiles_for_request(
            "full", INITIALIZER.PROFILES["full"],
        )
        self.assertIn("connected-public-experience", profiles)
        self.assertIn(
            "connected-public-experience",
            INITIALIZER.inferred_evidence_capabilities(profiles),
        )
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            version = INITIALIZER.release_version(SKILL)
            INITIALIZER.render_new_state(
                SKILL, project / ".design-dna", version,
                INITIALIZER.PROFILES["full"], profiles,
            )
            failures, _warnings = INITIALIZER.validate_state(project, version)
            self.assertEqual([], failures)

    def test_selected_empty_record_fails_readiness_with_continuity_gaps(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            state = project / ".design-dna"
            version = INITIALIZER.release_version(SKILL)
            records = INITIALIZER.PROFILES["connected-public-experience"]
            profiles = INITIALIZER.assurance_profiles_for_request(
                "connected-public-experience", records,
            )
            INITIALIZER.render_new_state(SKILL, state, version, records, profiles)
            contract_path = state / "connected-public-experience.json"
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            contract["applicability"] = {
                "status": "applicable",
                "reason": text("The selected capability is deliberately empty after an applicable request"),
                "blocking_dependency": None,
                "next_action": None,
            }
            contract_path.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
            failures = INITIALIZER.readiness_failures(project)
            self.assertTrue(any("direct-entry-questions-missing" in item for item in failures), failures)
            self.assertTrue(any("final-closure-incomplete" in item for item in failures), failures)

    def test_direction_ready_plan_passes_no_write_prebuild_but_not_final_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = mark_direction_ready(ready_contract(project))
            before = sorted(
                str(path.relative_to(project)).replace("\\", "/")
                for path in project.rglob("*")
                if path.is_file()
            )

            prebuild = AUDITOR.audit_prebuild_payload(
                project,
                contract,
                {"connected-public-experience"},
            )

            after = sorted(
                str(path.relative_to(project)).replace("\\", "/")
                for path in project.rglob("*")
                if path.is_file()
            )
            self.assertTrue(prebuild["structural_valid"], prebuild)
            self.assertTrue(prebuild["ready"], prebuild)
            self.assertTrue(prebuild["implementation_authorized"], prebuild)
            self.assertEqual("prebuild", prebuild["phase"])
            self.assertEqual(before, after, "The exported prebuild helper must not write an audit artifact.")

            final = AUDITOR.audit_payload(
                project,
                contract,
                {"connected-public-experience"},
            )
            self.assertFalse(final["ready"], final)
            final_codes = {entry["code"] for entry in final["gaps"]}
            self.assertIn("record-not-reviewed", final_codes)
            self.assertIn("final-closure-incomplete", final_codes)

    def test_draft_or_blocked_lifecycle_cannot_bypass_prebuild(self) -> None:
        for lifecycle, expected_code in (
            ("draft", "record-not-direction-ready"),
            ("blocked", "record-blocked"),
        ):
            with self.subTest(lifecycle=lifecycle):
                with tempfile.TemporaryDirectory() as temporary:
                    project = Path(temporary)
                    contract = mark_direction_ready(ready_contract(project))
                    contract["record_status"] = lifecycle
                    report = AUDITOR.audit_prebuild_payload(
                        project,
                        contract,
                        {"connected-public-experience"},
                    )
                    self.assertFalse(report["ready"], report)
                    self.assertFalse(report["implementation_authorized"], report)
                    self.assertIn(
                        expected_code,
                        {entry["code"] for entry in report["gaps"]},
                    )

    def test_prebuild_rejects_missing_continuity_parts_and_duplicate_proof_ids(self) -> None:
        mutations = (
            (
                "direct entry questions",
                lambda contract: contract["pre_direction_constraints"].update(
                    {"direct_entry_questions": []}
                ),
                "direct-entry-questions-missing",
            ),
            (
                "truth constraints",
                lambda contract: contract["pre_direction_constraints"].update(
                    {"truth_and_entity_constraints": []}
                ),
                "truth-entity-constraints-missing",
            ),
            (
                "selected root continuity",
                lambda contract: contract["selected_root_continuity"].update(
                    {"selected_root_id": None, "continuity_model": None}
                ),
                "selected-root-model-missing",
            ),
            (
                "handoff or reset",
                lambda contract: contract["selected_root_continuity"].update(
                    {"handoffs_or_resets": []}
                ),
                "handoff-reset-missing",
            ),
            (
                "meaningful path",
                lambda contract: contract["selected_root_continuity"][
                    "meaningful_path"
                ].update({"outcome": None}),
                "meaningful-path-missing",
            ),
            (
                "state authority crosswalk",
                lambda contract: contract["selected_root_continuity"].update(
                    {"state_authority_crosswalk": []}
                ),
                "status-crosswalk-missing",
            ),
            (
                "rendered proof plan",
                lambda contract: contract["selected_root_continuity"][
                    "proof_plan"
                ].update({"rendered": []}),
                "proof-plan-missing",
            ),
            (
                "functional proof plan",
                lambda contract: contract["selected_root_continuity"][
                    "proof_plan"
                ].update({"functional": []}),
                "proof-plan-missing",
            ),
            (
                "ambiguous proof identity",
                lambda contract: contract["selected_root_continuity"][
                    "proof_plan"
                ]["functional"][0].update({"id": "render-direct"}),
                "duplicate-proof-plan-id",
            ),
        )
        for name, mutate, expected_code in mutations:
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory() as temporary:
                    project = Path(temporary)
                    contract = mark_direction_ready(ready_contract(project))
                    mutate(contract)
                    report = AUDITOR.audit_prebuild_payload(
                        project,
                        contract,
                        {"connected-public-experience"},
                    )
                    self.assertFalse(report["ready"], report)
                    self.assertIn(
                        expected_code,
                        {entry["code"] for entry in report["gaps"]},
                    )

    def test_prebuild_requires_resolved_applicability_and_honest_not_applicable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            blocked = mark_direction_ready(ready_contract(project))
            blocked["applicability"] = {
                "status": "blocked",
                "reason": text("The named public-state authority has not resolved the service boundary"),
                "blocking_dependency": text("Approved public-state and content authority"),
                "next_action": text("Obtain the named authority before implementing the connected path"),
            }
            blocked_report = AUDITOR.audit_prebuild_payload(
                project,
                blocked,
                {"connected-public-experience"},
            )
            self.assertFalse(blocked_report["ready"], blocked_report)
            self.assertIn(
                "connected-public-experience-blocked",
                {entry["code"] for entry in blocked_report["gaps"]},
            )

            not_applicable = mark_direction_ready(ready_contract(project))
            not_applicable["applicability"] = {
                "status": "not-applicable",
                "reason": text("This is one bounded editorial notice with no linked path or carried public state"),
                "blocking_dependency": None,
                "next_action": None,
            }
            not_applicable_report = AUDITOR.audit_prebuild_payload(
                project,
                not_applicable,
                {"connected-public-experience"},
            )
            self.assertTrue(not_applicable_report["ready"], not_applicable_report)

            not_applicable["applicability"]["blocking_dependency"] = text(
                "The owner still needs to decide whether a connected path exists"
            )
            dishonest_report = AUDITOR.audit_prebuild_payload(
                project,
                not_applicable,
                {"connected-public-experience"},
            )
            self.assertFalse(dishonest_report["ready"], dishonest_report)
            self.assertIn(
                "resolved-applicability-retains-blocker",
                {entry["code"] for entry in dishonest_report["gaps"]},
            )

    def test_requested_staff_branch_cannot_bypass_prebuild_fixture_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = mark_direction_ready(ready_contract(project, staff=True))
            ready_report = AUDITOR.audit_prebuild_payload(
                project,
                contract,
                {"connected-public-experience"},
            )
            self.assertTrue(ready_report["ready"], ready_report)

            contract["staff_admin_split"]["fixture"] = {
                "status": "none",
                "authority": None,
                "content_or_state": None,
                "boundary": None,
                "descriptor": None,
            }
            bypass = AUDITOR.audit_prebuild_payload(
                project,
                contract,
                {"connected-public-experience"},
            )
            self.assertFalse(bypass["ready"], bypass)
            self.assertIn(
                "staff-admin-fixture-missing",
                {entry["code"] for entry in bypass["gaps"]},
            )

    def test_missing_direct_entry_recovery_or_functional_proof_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = ready_contract(project)
            contract["final_closure"]["proof_coverage"]["direct_entry_evidence_ids"] = []
            contract["final_closure"]["proof_coverage"]["recovery_or_continuation_evidence_ids"] = []
            contract["final_closure"]["functional_path_evidence"] = []
            report = AUDITOR.audit_payload(project, contract, {"connected-public-experience"})
            codes = {entry["code"] for entry in report["gaps"]}
            self.assertIn("direct_entry_evidence_ids-missing", codes)
            self.assertIn("recovery_or_continuation_evidence_ids-missing", codes)
            self.assertIn("functional-path-evidence-missing", codes)
            self.assertFalse(report["ready"])

    def test_justified_not_applicable_passes_and_blocked_stays_honest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            not_applicable = mark_not_applicable(ready_contract(project))
            report = AUDITOR.audit_payload(project, not_applicable, {"connected-public-experience"})
            self.assertTrue(report["structural_valid"], report)
            self.assertTrue(report["ready"], report)
            blocked = ready_contract(project)
            blocked["applicability"] = {
                "status": "blocked",
                "reason": text("The accountable owner has not approved the public state and service boundaries"),
                "blocking_dependency": text("approved public-service and content authority"),
                "next_action": text("obtain the named authority before defining a continuity plan"),
            }
            blocked["record_status"] = "blocked"
            blocked_report = AUDITOR.audit_payload(project, blocked, {"connected-public-experience"})
            self.assertFalse(blocked_report["ready"])
            self.assertIn("connected-public-experience-blocked", {entry["code"] for entry in blocked_report["gaps"]})

    def test_reviewed_not_applicable_cannot_bypass_requested_staff_admin_work(self) -> None:
        """Regression: the early N/A return must not waive a requested staff branch."""

        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            reviewed_not_applicable = mark_not_applicable(
                ready_contract(project, staff=True)
            )
            report = AUDITOR.audit_payload(
                project,
                reviewed_not_applicable,
                {"connected-public-experience"},
            )
            self.assertFalse(report["structural_valid"], report)
            self.assertFalse(report["ready"], report)
            self.assertIn(
                "not-applicable-staff-admin-incompatible",
                {entry["code"] for entry in report["findings"]},
            )

    def test_not_applicable_rejects_blocked_or_residual_staff_material(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            blocked_staff = mark_not_applicable(ready_contract(project))
            blocked_staff["staff_admin_split"]["status"] = "blocked"
            blocked_staff["staff_admin_split"]["operate_mode"] = "blocked"
            blocked_report = AUDITOR.audit_payload(
                project,
                blocked_staff,
                {"connected-public-experience"},
            )
            self.assertFalse(blocked_report["ready"], blocked_report)
            self.assertIn(
                "not-applicable-staff-admin-incompatible",
                {entry["code"] for entry in blocked_report["findings"]},
            )

            residual_fixture = mark_not_applicable(ready_contract(project))
            residual_fixture["staff_admin_split"]["fixture"] = {
                "status": "local-fixture",
                "authority": text("a local fixture owner"),
                "content_or_state": text("one non-empty internal staff record"),
                "boundary": text("local-only staff review state"),
                "descriptor": None,
            }
            residual_fixture["staff_admin_split"]["final_evidence"] = {
                "rendered_evidence_id": "staff-render",
                "functional_evidence_id": "staff-run",
            }
            residual_report = AUDITOR.audit_payload(
                project,
                residual_fixture,
                {"connected-public-experience"},
            )
            self.assertFalse(residual_report["ready"], residual_report)
            self.assertIn(
                "not-applicable-staff-admin-incompatible",
                {entry["code"] for entry in residual_report["findings"]},
            )

    def test_requested_staff_proof_cannot_be_relabelled_not_requested(self) -> None:
        """A complete staff branch cannot become nonstaff by changing one label."""

        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            relabelled = ready_contract(project, staff=True)
            relabelled["staff_admin_split"]["status"] = "not-requested"
            report = AUDITOR.audit_payload(
                project,
                relabelled,
                {"connected-public-experience"},
            )
            self.assertFalse(report["structural_valid"], report)
            self.assertFalse(report["ready"], report)
            self.assertIn(
                "staff-admin-not-requested-incoherent",
                {entry["code"] for entry in report["findings"]},
            )

    def test_blocked_staff_branch_is_never_ready_without_cpe_blocking_detail(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            blocked_staff = ready_contract(project)
            blocked_staff["staff_admin_split"]["status"] = "blocked"
            blocked_staff["staff_admin_split"]["operate_mode"] = "blocked"
            report = AUDITOR.audit_payload(
                project,
                blocked_staff,
                {"connected-public-experience"},
            )
            self.assertTrue(report["structural_valid"], report)
            self.assertFalse(report["ready"], report)
            self.assertIn(
                "staff-admin-blocked",
                {entry["code"] for entry in report["gaps"]},
            )

    def test_direction_roots_and_staff_admin_have_a_positive_routed_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            state = project / ".design-dna"
            state.mkdir()
            (state / "direction-challenge.json").write_text(
                json.dumps({
                    "roots": [{"id": "root-a"}, {"id": "root-b"}],
                    "selection": {"chosen_root_id": "root-a"},
                }),
                encoding="utf-8",
            )
            contract = ready_contract(project, staff=True)
            contract["selected_root_continuity"]["selected_root_id"] = "root-a"
            contract["root_variation"] = {
                "strategy": "each-root-model",
                "detail": text("Each candidate keeps its own route-state relationship before a direction is chosen"),
                "entries": [
                    {"root_id": "root-a", "continuity_model": text("Root A carries an object into a local request"), "named_invariant": None},
                    {"root_id": "root-b", "continuity_model": text("Root B starts a fresh comparison and links its own continuation"), "named_invariant": None},
                ],
                "project_contrast_mapping": {
                    "status": "mapped",
                    "selected_root_id": "root-a",
                    "counter_root_id": "root-b",
                    "not_applicable_reason": None,
                },
            }
            report = AUDITOR.audit_payload(
                project,
                contract,
                {"connected-public-experience", "project-contrast", "direction-challenge"},
            )
            self.assertTrue(report["ready"], report)
            router_text = (SKILL / "references" / "router.md").read_text(encoding="utf-8")
            reference_text = (SKILL / "references" / "quality" / "connected-public-experience.md").read_text(encoding="utf-8")
            self.assertIn("Requested staff/admin back office", router_text)
            self.assertIn("Operate mode", reference_text)

    def test_final_rendering_rejects_hash_bound_arbitrary_non_png_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = ready_contract(project)
            evidence = project / "evidence" / "direct"
            report_path = evidence / "render-review.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            arbitrary = b"this is deliberately not a PNG image"
            (evidence / "wide.png").write_bytes(arbitrary)
            report["captures"][0]["screenshot"]["sha256"] = digest(arbitrary)
            report["captures"][0]["screenshot"]["bytes"] = len(arbitrary)
            report_sha = rebind_schema3_package(evidence, report)
            rendered = contract["final_closure"]["rendered_evidence"][0]
            rendered["file"]["sha256"] = digest(arbitrary)
            rendered["render_review"]["file"]["sha256"] = report_sha
            audit = AUDITOR.audit_payload(project, contract, {"connected-public-experience"})
            self.assertFalse(audit["ready"], audit)
            self.assertIn(
                "final-rendered-schema3-invalid",
                {entry["code"] for entry in audit["gaps"]},
            )

    def test_final_rendering_rejects_wrong_schema3_build_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = ready_contract(project)
            contract["final_closure"]["reviewed_build_id"] = "candidate-build-8"
            contract["final_closure"]["functional_path_evidence"][0]["attestation"]["build_id"] = "candidate-build-8"
            audit = AUDITOR.audit_payload(project, contract, {"connected-public-experience"})
            self.assertFalse(audit["ready"], audit)
            self.assertIn(
                "final-rendered-build-mismatch",
                {entry["code"] for entry in audit["gaps"]},
            )

    def test_artifact_free_functional_result_requires_structured_attestation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = ready_contract(project)
            contract["final_closure"]["functional_path_evidence"][0]["attestation"] = None
            audit = AUDITOR.audit_payload(project, contract, {"connected-public-experience"})
            self.assertFalse(audit["ready"], audit)
            self.assertIn(
                "functional-attestation-missing",
                {entry["code"] for entry in audit["gaps"]},
            )

    def test_requested_staff_branch_needs_fixture_descriptor_capture_and_own_attestation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = ready_contract(project, staff=True)
            contract["staff_admin_split"]["fixture"]["descriptor"] = None
            contract["final_closure"]["functional_path_evidence"][-1]["attestation"] = None
            audit = AUDITOR.audit_payload(project, contract, {"connected-public-experience"})
            self.assertFalse(audit["ready"], audit)
            codes = {entry["code"] for entry in audit["gaps"]}
            self.assertIn("staff-admin-fixture-descriptor-missing", codes)
            self.assertIn("staff-admin-functional-attestation-missing", codes)

    def test_requested_staff_fixture_descriptor_semantically_binds_to_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            audit = AUDITOR.audit_payload(
                project,
                ready_contract(project, staff=True),
                {"connected-public-experience"},
            )
            self.assertTrue(audit["ready"], audit)
            self.assertNotIn(
                "staff-admin-fixture-descriptor-semantic-mismatch",
                {entry["code"] for entry in audit["gaps"]},
            )

    def test_requested_staff_fixture_descriptor_accepts_each_safe_status_binding(self) -> None:
        for fixture_status, classification in (
            ("approved", "sanitized-approved"),
            ("sandbox", "sandbox"),
            ("local-fixture", "synthetic"),
        ):
            with self.subTest(fixture_status=fixture_status):
                with tempfile.TemporaryDirectory() as temporary:
                    project = Path(temporary)
                    contract = ready_contract(project, staff=True)
                    fixture = contract["staff_admin_split"]["fixture"]
                    fixture["status"] = fixture_status
                    descriptor_ref = fixture["descriptor"]
                    assert isinstance(descriptor_ref, dict)
                    descriptor_path = project / descriptor_ref["path"]
                    descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
                    descriptor["privacy_classification"] = classification
                    payload = (json.dumps(descriptor, indent=2) + "\n").encode("utf-8")
                    descriptor_path.write_bytes(payload)
                    descriptor_ref["sha256"] = digest(payload)

                    audit = AUDITOR.audit_payload(
                        project,
                        contract,
                        {"connected-public-experience"},
                    )

                    self.assertTrue(audit["ready"], audit)

    def test_rehashed_staff_fixture_descriptor_semantic_mismatch_stays_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = ready_contract(project, staff=True)
            descriptor_ref = contract["staff_admin_split"]["fixture"]["descriptor"]
            assert isinstance(descriptor_ref, dict)
            descriptor_path = project / descriptor_ref["path"]
            descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
            descriptor["privacy_classification"] = "sandbox"
            descriptor["meaningful_state"] = text("an unrelated dashboard queue has a different operational status")
            descriptor["authority"] = text("a different administrator owns this unrelated test scenario")
            descriptor["boundary"] = text("a different sandbox boundary with no relation to the declared local fixture")
            payload = (json.dumps(descriptor, indent=2) + "\n").encode("utf-8")
            descriptor_path.write_bytes(payload)
            descriptor_ref["sha256"] = digest(payload)

            audit = AUDITOR.audit_payload(project, contract, {"connected-public-experience"})

            self.assertFalse(audit["ready"], audit)
            self.assertIn(
                "staff-admin-fixture-descriptor-semantic-mismatch",
                {entry["code"] for entry in audit["gaps"]},
            )

    def test_generic_public_functional_row_cannot_impersonate_staff_attestation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = ready_contract(project, staff=True)
            public_path = contract["final_closure"]["functional_path_evidence"][0]
            public_path["coverage"].append("staff-back-office")
            contract["staff_admin_split"]["final_evidence"]["functional_evidence_id"] = "path-run"
            audit = AUDITOR.audit_payload(project, contract, {"connected-public-experience"})
            self.assertFalse(audit["ready"], audit)
            self.assertIn(
                "staff-admin-functional-route-mismatch",
                {entry["code"] for entry in audit["gaps"]},
            )

    def test_direction_challenge_selected_root_must_link_to_cpe_selected_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            state = project / ".design-dna"
            state.mkdir()
            (state / "direction-challenge.json").write_text(
                json.dumps({
                    "roots": [{"id": "root-a"}, {"id": "root-b"}],
                    "selection": {"chosen_root_id": "root-a"},
                }),
                encoding="utf-8",
            )
            contract = ready_contract(project)
            contract["root_variation"] = {
                "strategy": "each-root-model",
                "detail": text("Each root retains a viable continuity model while its proof is reviewed"),
                "entries": [
                    {"root_id": "root-a", "continuity_model": text("Root A preserves an object selection"), "named_invariant": None},
                    {"root_id": "root-b", "continuity_model": text("Root B starts a clear comparison path"), "named_invariant": None},
                ],
                "project_contrast_mapping": None,
            }
            audit = AUDITOR.audit_payload(
                project,
                contract,
                {"connected-public-experience", "direction-challenge"},
            )
            self.assertFalse(audit["ready"], audit)
            self.assertIn(
                "direction-challenge-selected-root-mismatch",
                {entry["code"] for entry in audit["gaps"]},
            )

    def test_project_contrast_needs_mapping_or_substantive_no_root_applicability(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = ready_contract(project)
            contract["root_variation"] = {
                "strategy": "each-root-model",
                "detail": text("The selected and counter directions each expose their own viable continuity"),
                "entries": [
                    {"root_id": "catalog-object-path", "continuity_model": text("Selected root carries the chosen object"), "named_invariant": None},
                    {"root_id": "counter-root", "continuity_model": text("Counter root keeps a distinct continuation model"), "named_invariant": None},
                ],
                "project_contrast_mapping": None,
            }
            audit = AUDITOR.audit_payload(
                project,
                contract,
                {"connected-public-experience", "project-contrast"},
            )
            self.assertFalse(audit["ready"], audit)
            self.assertIn(
                "project-contrast-root-mapping-missing",
                {entry["code"] for entry in audit["gaps"]},
            )
            contract["root_variation"] = {
                "strategy": "not-required",
                "detail": None,
                "entries": [],
                "project_contrast_mapping": {
                    "status": "not-applicable",
                    "selected_root_id": None,
                    "counter_root_id": None,
                    "not_applicable_reason": text("The active contrast record compares one public encounter rather than separate CPE root models"),
                },
            }
            no_root = AUDITOR.audit_payload(
                project,
                contract,
                {"connected-public-experience", "project-contrast"},
            )
            self.assertTrue(no_root["ready"], no_root)

    def test_every_proof_plan_id_must_bind_or_be_explicitly_superseded(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = ready_contract(project)
            stale = {
                "id": "discarded-render",
                "purpose": text("Observe a superseded direct-entry arrangement before final selection"),
                "final_disposition": "planned",
                "superseded_reason": None,
            }
            contract["selected_root_continuity"]["proof_plan"]["rendered"].append(stale)
            audit = AUDITOR.audit_payload(project, contract, {"connected-public-experience"})
            self.assertFalse(audit["ready"], audit)
            self.assertIn("proof-plan-unresolved", {entry["code"] for entry in audit["gaps"]})
            stale["final_disposition"] = "superseded"
            stale["superseded_reason"] = text("The final route structure made this early proof redundant after the direct-entry capture was bound")
            repaired = AUDITOR.audit_payload(project, contract, {"connected-public-experience"})
            self.assertTrue(repaired["ready"], repaired)

    def test_cli_requires_safe_capability_context_and_derives_direction_challenge(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            state = project / ".design-dna"
            state.mkdir()
            (state / "connected-public-experience.json").write_text(
                json.dumps(ready_contract(project), indent=2) + "\n",
                encoding="utf-8",
            )
            missing_context = subprocess.run(
                [sys.executable, str(AUDITOR_PATH), str(project), "--stdout"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(1, missing_context.returncode, missing_context.stderr)
            missing_report = json.loads(missing_context.stdout)
            self.assertFalse(missing_report["ready"], missing_report)
            self.assertIn("active-capability-context-missing", {entry["code"] for entry in missing_report["gaps"]})
            explicit = subprocess.run(
                [
                    sys.executable,
                    str(AUDITOR_PATH),
                    str(project),
                    "--active-capability", "connected-public-experience",
                    "--stdout",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(0, explicit.returncode, explicit.stderr)
            self.assertTrue(json.loads(explicit.stdout)["ready"])

            (state / "state.json").write_text(
                json.dumps({
                    "records": ["connected-public-experience", "direction-challenge"],
                    "evidence_contract": {
                        "applicable_capabilities": [
                            "connected-public-experience", "direction-challenge",
                        ],
                    },
                }),
                encoding="utf-8",
            )
            (state / "direction-challenge.json").write_text(
                json.dumps({
                    "roots": [{"id": "root-a"}, {"id": "root-b"}],
                    "selection": {"chosen_root_id": "root-a"},
                }),
                encoding="utf-8",
            )
            mismatch = ready_contract(project)
            mismatch["root_variation"] = {
                "strategy": "each-root-model",
                "detail": text("Each Direction Challenge root has a separately reviewable continuity model"),
                "entries": [
                    {"root_id": "root-a", "continuity_model": text("Root A carries a selected object"), "named_invariant": None},
                    {"root_id": "root-b", "continuity_model": text("Root B starts a comparison anew"), "named_invariant": None},
                ],
                "project_contrast_mapping": None,
            }
            (state / "connected-public-experience.json").write_text(
                json.dumps(mismatch, indent=2) + "\n",
                encoding="utf-8",
            )
            derived = subprocess.run(
                [sys.executable, str(AUDITOR_PATH), str(project), "--stdout"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(1, derived.returncode, derived.stderr)
            derived_report = json.loads(derived.stdout)
            self.assertIn("direction-challenge-selected-root-mismatch", {entry["code"] for entry in derived_report["gaps"]})
            override = subprocess.run(
                [
                    sys.executable,
                    str(AUDITOR_PATH),
                    str(project),
                    "--active-capability", "connected-public-experience",
                    "--stdout",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(1, override.returncode, override.stderr)
            self.assertIn(
                "active-capability-context-mismatch",
                {entry["code"] for entry in json.loads(override.stdout)["gaps"]},
            )

    def test_cli_rejects_unsafe_output_before_mkdir(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            state = project / ".design-dna"
            state.mkdir()
            (state / "state.json").write_text(
                json.dumps({
                    "records": ["connected-public-experience"],
                    "evidence_contract": {"applicable_capabilities": ["connected-public-experience"]},
                }),
                encoding="utf-8",
            )
            (state / "connected-public-experience.json").write_text(
                json.dumps(ready_contract(project), indent=2) + "\n",
                encoding="utf-8",
            )
            for output in ("../escaped.json", "./relative.json", "nested/../escaped.json", "nested\\escaped.json", "/absolute.json"):
                result = subprocess.run(
                    [sys.executable, str(AUDITOR_PATH), str(project), "--output", output],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(2, result.returncode, (output, result.stdout, result.stderr))
            self.assertFalse((project.parent / "escaped.json").exists())
            self.assertFalse((project / "nested").exists())

    def test_auditor_cli_writes_a_ready_bound_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            state = project / ".design-dna"
            state.mkdir()
            (state / "state.json").write_text(
                json.dumps({
                    "records": ["connected-public-experience"],
                    "evidence_contract": {
                        "applicable_capabilities": ["connected-public-experience"],
                    },
                }),
                encoding="utf-8",
            )
            (state / "connected-public-experience.json").write_text(
                json.dumps(ready_contract(project), indent=2) + "\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(AUDITOR_PATH), str(project), "--stdout"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            report = json.loads(result.stdout)
            self.assertTrue(report["ready"], report)
            self.assertEqual(
                "design-dna-connected-public-experience-audit",
                report["artifact_type"],
            )
            self.assertTrue(
                (state / "evidence" / "connected-public-experience-audit.json").is_file()
            )


if __name__ == "__main__":
    unittest.main()
