#!/usr/bin/env python3
"""Focused regressions for final Design DNA state/readiness evidence gates."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SKILL = Path(__file__).resolve().parents[1]
INITIALIZER_PATH = SKILL / "scripts" / "init_project_state.py"


def load_initializer():
    specification = importlib.util.spec_from_file_location(
        "design_dna_state_gate_hardening",
        INITIALIZER_PATH,
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


INITIALIZER = load_initializer()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def schema3_fixture(project: Path) -> tuple[dict, Path]:
    specification = importlib.util.spec_from_file_location(
        "design_dna_state_gate_schema3_fixture",
        SKILL / "tests" / "test_direction_challenge.py",
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    evidence = project / "evidence" / "render-review"
    info = module.write_schema3_render_review(
        evidence,
        build_id="candidate-final",
        route="/",
        prefix="candidate",
    )
    report_path = evidence / "render-review.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["capture_contract"]["contract_mode"] = "capture-manifest-v1"
    report_digest = module.rebind_schema3_report(report_path, report)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["_test_report_digest"] = report_digest
    report["_test_source_digest"] = info["source_snapshot_manifest_sha256"]
    return report, report_path


def minimal_final_review() -> str:
    return "\n".join((
        "<!-- proportional-evidence-v1 -->",
        "## Rendered review",
        "- Build or artifact ID: final-build-7",
        "- Final implementation reviewed: yes",
        "- Reviewer relationship: producer-self",
        "",
        "| Route/state | Viewport/context | Rendered PNG path and SHA-256 | Observation |",
        "| --- | --- | --- | --- |",
        "| /; default | 390x844 | evidence/raw.png plus sha256:" + ("0" * 64) + " | Raw evidence exists but is not a renderer report. |",
        "",
        "## Review scope and capture rationale",
        "| Route/state or reviewed body | Material review risk or not-applicable reason | Wide capture ID | Narrow capture ID | Disposition |",
        "| --- | --- | --- | --- | --- |",
        "| /; default body | The public entry needs wide and narrow review rather than inferred responsive behavior. | wide-one | narrow-one | applicable |",
        "",
        "## First-impression and surface-fidelity review",
        "| Review focus | Applicability or disposition | Rendered PNG path and SHA-256 | Observation or limitation |",
        "| --- | --- | --- | --- |",
        "| First impression and surface fidelity | applicable | evidence/raw.png plus sha256:" + ("0" * 64) + " | The evidence is deliberately raw for this negative test. |",
        "",
        "## Preship and specificity closure",
        "| Closure | Applicability or disposition | Rendered PNG path and SHA-256 | Result or limitation |",
        "| --- | --- | --- | --- |",
        "| Adversarial specificity review | applicable | evidence/raw.png plus sha256:" + ("0" * 64) + " | A raw image must not close the final review. |",
        "| Preship gate | applicable | evidence/raw.png plus sha256:" + ("0" * 64) + " | A raw image must not close the final review. |",
        "",
        "## Findings",
        "| Severity | Confidence | Evidence | User/release impact | Cause | Fix or disposition | Rerun verification | Status | Owner |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        "| low | high | raw.png | Bounded negative test. | Raw evidence only. | Requires schema-3 render report. | Not rerun. | verified | reviewer-7 |",
        "",
        "## Owner and release state",
        "- Reviewer conclusion: self-reviewed candidate",
        "- Owner disposition: pending",
        "- Release blockers: none within the reviewed scope",
        "",
    ))


class StateGateHardeningTests(unittest.TestCase):
    def test_supplemental_records_do_not_infer_high_risk(self) -> None:
        """Only an explicit profile may turn evidence into a risk declaration."""

        for records in (
            ("claims",),
            ("user-validation",),
            ("claims", "user-validation"),
        ):
            with self.subTest(records=records):
                self.assertEqual(
                    ("standard",),
                    INITIALIZER.infer_assurance_profiles(records),
                )
        self.assertEqual(
            ("standard",),
            INITIALIZER.assurance_profiles_for_request(
                "validation",
                INITIALIZER.PROFILES["validation"],
            ),
        )
        high_risk = INITIALIZER.assurance_profiles_for_request(
            "high-risk",
            INITIALIZER.PROFILES["high-risk"],
        )
        self.assertEqual(("high-risk",), high_risk)
        self.assertEqual(
            {"direction", "visual-review", "claims", "user-validation"},
            INITIALIZER.CAPABILITY_REQUIRED_RECORDS["high-risk"],
        )
        self.assertIn(
            "high-risk",
            INITIALIZER.inferred_evidence_capabilities(high_risk),
        )

    def test_high_risk_capability_requires_profile_and_full_record_boundary(self) -> None:
        """The gate cannot be added to an otherwise Standard contract."""

        with self.assertRaisesRegex(
            INITIALIZER.StateError,
            "requires the high-risk assurance profile",
        ):
            INITIALIZER.evidence_contract_payload(
                ("standard",),
                ("high-risk",),
            )

        contract = INITIALIZER.evidence_contract_payload(("high-risk",))
        self.assertEqual(
            ["high-risk"],
            contract["applicable_capabilities"],
        )
        self.assertEqual(
            (),
            INITIALIZER.missing_capability_records(
                "high-risk",
                INITIALIZER.PROFILES["high-risk"],
            ),
        )

    def test_migration_preserves_incomplete_persisted_high_risk_profile(self) -> None:
        """Migration reopens evidence instead of guessing a weaker risk level."""

        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            state = project / ".design-dna"
            INITIALIZER.render_new_state(
                SKILL,
                state,
                "test-fixture",
                ("claims",),
                ("high-risk",),
            )
            state_path = state / "state.json"
            source = json.loads(state_path.read_text(encoding="utf-8"))
            source["schema_version"] = 1
            source.pop("evidence_contract")
            state_path.write_text(
                json.dumps(source, indent=2) + "\n",
                encoding="utf-8",
            )

            updated = INITIALIZER.migrate_staged_state(state, "test-fixture")

            migrated = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(["high-risk"], migrated["assurance_profiles"])
            self.assertEqual(
                ["high-risk"],
                migrated["evidence_contract"]["applicable_capabilities"],
            )
            self.assertTrue(
                set(INITIALIZER.PROFILES["high-risk"]).issubset(
                    migrated["records"]
                )
            )
            self.assertTrue(
                {"direction", "visual-review", "user-validation"}.issubset(
                    updated
                )
            )
            for record in INITIALIZER.PROFILES["high-risk"]:
                path = state / INITIALIZER.RECORD_TEMPLATES[record][0]
                self.assertTrue(path.is_file(), path)
                if path.suffix == ".md":
                    self.assertEqual(
                        "draft",
                        INITIALIZER.parse_frontmatter(path)["record_status"],
                    )
            report = json.loads(
                (state / "migration-report.json").read_text(encoding="utf-8")
            )
            self.assertIn(
                "does not infer completion or downgrade",
                report["assurance_transitions"][-1]["reason"],
            )

    def test_migration_aligns_persisted_high_risk_capability_to_profile(self) -> None:
        """A malformed older contract is repaired toward, never away from, risk."""

        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            state = project / ".design-dna"
            INITIALIZER.render_new_state(
                SKILL,
                state,
                "test-fixture",
                ("claims", "user-validation"),
                ("standard",),
            )
            state_path = state / "state.json"
            source = json.loads(state_path.read_text(encoding="utf-8"))
            source["evidence_contract"]["applicable_capabilities"].append(
                "high-risk"
            )
            state_path.write_text(
                json.dumps(source, indent=2) + "\n",
                encoding="utf-8",
            )

            INITIALIZER.migrate_staged_state(state, "test-fixture")

            migrated = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(["high-risk"], migrated["assurance_profiles"])
            self.assertEqual(
                ["high-risk"],
                migrated["evidence_contract"]["applicable_capabilities"],
            )
            self.assertTrue(
                set(INITIALIZER.PROFILES["high-risk"]).issubset(
                    migrated["records"]
                )
            )

    def test_schema3_capture_pair_binds_final_review_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            state = project / ".design-dna"
            state.mkdir()
            report, report_path = schema3_fixture(project)
            captures = {capture["id"]: capture for capture in report["captures"]}
            wide = captures["candidate-wide"]
            narrow = captures["candidate-narrow"]
            wide_path = report_path.parent / wide["screenshot"]["path"]
            narrow_path = report_path.parent / narrow["screenshot"]["path"]
            source_digest = report["_test_source_digest"]
            report_digest = report["_test_report_digest"]
            contact_path = report_path.parent / "contact-sheet.html"
            relative_report = report_path.relative_to(project).as_posix()
            body = "\n".join((
                "<!-- proportional-evidence-v1 -->",
                "## Rendered review",
                "- Build or artifact ID: candidate-final",
                "- Source/workspace identity and SHA-256: frozen source snapshot plus sha256:" + source_digest,
                "- Rendered-review report path, hash, contract, and execution result: " + relative_report + " plus sha256:" + report_digest + "; build=candidate-final; source_snapshot_sha256=" + source_digest + "; contract_mode=capture-manifest-v1; execution_ok=true",
                "- Coverage contact sheet or artifact index: " + contact_path.relative_to(project).as_posix() + " plus sha256:" + sha256(contact_path),
                "- Final implementation reviewed: yes",
                "- Reviewer relationship: producer-self",
                "| Route/state | Viewport/context | Rendered PNG path and SHA-256 | Observation |",
                "| --- | --- | --- | --- |",
                "| /; default | wide | " + wide_path.relative_to(project).as_posix() + " plus sha256:" + sha256(wide_path) + " | The final public opening was reviewed as rendered. |",
                "",
                "## Review scope and capture rationale",
                "| Route/state or reviewed body | Material review risk or not-applicable reason | Wide capture ID | Narrow capture ID | Disposition |",
                "| --- | --- | --- | --- | --- |",
                "| /; default body | The public entry needs a real wide and narrow pair before responsive character can be considered reviewed. | candidate-wide | candidate-narrow | applicable |",
                "",
                "## First-impression and surface-fidelity review",
                "| Review focus | Applicability or disposition | Rendered PNG path and SHA-256 | Observation or limitation |",
                "| --- | --- | --- | --- |",
                "| First impression and surface fidelity | applicable | " + wide_path.relative_to(project).as_posix() + " plus sha256:" + sha256(wide_path) + " | The first encounter was observed before diagnostic language; producer-self remains the limitation. |",
                "",
                "## Preship and specificity closure",
                "| Closure | Applicability or disposition | Rendered PNG path and SHA-256 | Result or limitation |",
                "| --- | --- | --- | --- |",
                "| Adversarial specificity review | applicable | " + wide_path.relative_to(project).as_posix() + " plus sha256:" + sha256(wide_path) + " | The bounded review records the project-specific encounter and remaining producer-self limitation. |",
                "| Preship gate | applicable | " + narrow_path.relative_to(project).as_posix() + " plus sha256:" + sha256(narrow_path) + " | The final narrow capture was reviewed at the selected responsive risk condition. |",
                "",
                "## Findings",
                "| Severity | Confidence | Evidence | User/release impact | Cause | Fix or disposition | Rerun verification | Status | Owner |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
                "| low | high | final render | No unresolved issue in this bounded review. | Scope was limited. | Scope documented. | Rechecked candidate-final. | verified | reviewer-7 |",
                "",
                "## Owner and release state",
                "- Reviewer conclusion: self-reviewed candidate",
                "- Owner disposition: pending",
                "- Release blockers: none within the reviewed scope",
                "",
            ))
            failures = INITIALIZER.substantive_body_failures(
                "visual-review",
                body,
                project=project,
                record_path=state / "visual-review.md",
                required_assurance_profiles={"standard"},
                evidence_contract=INITIALIZER.PROPORTIONAL_EVIDENCE_CONTRACT,
                enforce_final_visual_binding=True,
            )
            self.assertEqual([], failures)

    def test_final_standard_review_rejects_raw_png_without_schema3_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            state = project / ".design-dna"
            evidence = project / "evidence"
            state.mkdir()
            evidence.mkdir()
            raw = evidence / "raw.png"
            raw.write_bytes(b"not an image")
            body = minimal_final_review().replace("0" * 64, sha256(raw))
            failures = INITIALIZER.substantive_body_failures(
                "visual-review",
                body,
                project=project,
                record_path=state / "visual-review.md",
                required_assurance_profiles={"standard"},
                evidence_contract=INITIALIZER.PROPORTIONAL_EVIDENCE_CONTRACT,
                enforce_final_visual_binding=True,
            )
            self.assertTrue(
                any("schema-3" in failure.casefold() for failure in failures),
                failures,
            )

    def test_quick_review_keeps_a_truthful_direct_png_path(self) -> None:
        """Quick remains a smaller review, not a disguised Standard gate."""

        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            state = project / ".design-dna"
            state.mkdir()
            report, report_path = schema3_fixture(project)
            wide = next(
                capture for capture in report["captures"]
                if capture["id"] == "candidate-wide"
            )
            source_png = report_path.parent / wide["screenshot"]["path"]
            direct_png = project / "evidence" / "raw.png"
            direct_png.write_bytes(source_png.read_bytes())
            body = minimal_final_review().replace("0" * 64, sha256(direct_png))
            failures = INITIALIZER.substantive_body_failures(
                "visual-review",
                body,
                project=project,
                record_path=state / "visual-review.md",
                required_assurance_profiles={"quick"},
                evidence_contract=INITIALIZER.PROPORTIONAL_EVIDENCE_CONTRACT,
                enforce_final_visual_binding=True,
            )
            self.assertEqual([], failures)

    def test_final_standard_review_cannot_drop_surface_or_preship_closure(self) -> None:
        body = minimal_final_review()
        body = body.replace(
            "## First-impression and surface-fidelity review\n"
            "| Review focus | Applicability or disposition | Rendered PNG path and SHA-256 | Observation or limitation |\n"
            "| --- | --- | --- | --- |\n"
            "| First impression and surface fidelity | applicable | evidence/raw.png plus sha256:" + ("0" * 64) + " | The evidence is deliberately raw for this negative test. |\n\n",
            "",
        )
        failures = INITIALIZER.substantive_body_failures(
            "visual-review",
            body,
            required_assurance_profiles={"standard"},
            evidence_contract=INITIALIZER.PROPORTIONAL_EVIDENCE_CONTRACT,
            enforce_final_visual_binding=True,
        )
        self.assertIn(
            "missing required sections: First-impression and surface-fidelity review",
            failures,
        )

    def test_showcase_taste_calibration_requires_recurrence_disposition(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            state = project / ".design-dna"
            state.mkdir()
            selected = project / "selected.txt"
            counter = project / "counter.txt"
            selected.write_text("selected proof", encoding="utf-8")
            counter.write_text("counter proof", encoding="utf-8")
            body = "\n".join((
                "<!-- proportional-evidence-v1 -->",
                "## Record lifecycle and evidence boundary",
                "- Current status: proof-ready",
                "- Activation basis and applicable scope: Public Showcase direction needs a reviewable counter-answer before broad implementation.",
                "- Candidate/build under review: concept-build-4",
                "- Reviewer relationship and date: producer-self; 2026-08-12",
                "- Authoritative Project Contrast record path and current status, if active: not applicable because no comparison was authorized.",
                "- Authoritative Direction Challenge record path and current status, if active: not applicable for this bounded Showcase direction.",
                "- Direct reviewable artifacts currently bound: The selected and counter artifacts below are hash-bound.",
                "- Missing evidence, explicit inability, and next decision: Owner review remains pending after final rendering.",
                "",
                "## Public encounter and project read",
                "The public surface helps a visitor understand the product concept and choose a real next path.",
                "",
                "## Reference dossier",
                "| Source and retrieval date | Viewer-facing problem or role | Transferable relationship | Non-copying boundary |",
                "| --- | --- | --- | --- |",
                "| Project material, 2026-08-12 | Explain the concept without invented claims. | Keep the task next to its honest limit. | Do not copy another brand, layout, or identity. |",
                "",
                "## Direction proof",
                "- Selected-direction proof evidence: selected.txt plus sha256:" + sha256(selected),
                "- Counter-direction proof evidence: counter.txt plus sha256:" + sha256(counter),
                "- Project material used in the proof: Sparse approved project material and a factual fixture boundary.",
                "- Organizing answer being tested: Let the product task lead before supporting background detail.",
                "- Consequential observable decision(s): The visitor can find a product path without crossing a generic promotional shell.",
                "- What would make this direction lose: The counter proof better supports the same task at the tested conditions.",
                "",
                "## First-impression and surface-fidelity response",
                "Producer-self response is provisional and records the public encounter to revisit after rendering.",
                "",
                "## Disposition",
                "- Current disposition: revise; owner review will compare the final rendered candidate with the counter direction.",
                "- Protected facts, tasks, and accepted decisions: Do not invent certification, availability, or business claims.",
                "- Root decision to change, if reopened: The entry encounter and product-task relationship.",
                "- Exact next render or owner review: Render both directions at wide and narrow conditions before broad implementation.",
                "",
            ))
            failures = INITIALIZER.substantive_body_failures(
                "taste-calibration",
                body,
                project=project,
                record_path=state / "taste-calibration.md",
                required_assurance_profiles={"showcase"},
                evidence_contract=INITIALIZER.PROPORTIONAL_EVIDENCE_CONTRACT,
            )
            self.assertTrue(
                any("recurrence risk" in failure.casefold() for failure in failures),
                failures,
            )
            self.assertFalse(
                any("retrieval date" in failure.casefold() for failure in failures),
                failures,
            )
            self.assertFalse(
                any("proof evidence" in failure.casefold() for failure in failures),
                failures,
            )
            not_applicable_body = body.replace(
                "## Disposition",
                "- Recurrence-risk disposition: not-applicable; reason=No authorized sibling or studio-history scope exists for this project, so a comparator gate cannot apply.\n\n"
                "## Disposition",
            )
            not_applicable_failures = INITIALIZER.substantive_body_failures(
                "taste-calibration",
                not_applicable_body,
                project=project,
                record_path=state / "taste-calibration.md",
                required_assurance_profiles={"showcase"},
                evidence_contract=INITIALIZER.PROPORTIONAL_EVIDENCE_CONTRACT,
            )
            self.assertEqual([], not_applicable_failures)

            active_body = body.replace(
                "## Disposition",
                "- Recurrence-risk disposition: active; the owner has identified a repeated public encounter risk.\n\n"
                "## Disposition",
            )
            active_failures = INITIALIZER.substantive_body_failures(
                "taste-calibration",
                active_body,
                project=project,
                record_path=state / "taste-calibration.md",
                required_assurance_profiles={"showcase"},
                evidence_contract=INITIALIZER.PROPORTIONAL_EVIDENCE_CONTRACT,
            )
            self.assertTrue(
                any("Project Contrast" in failure for failure in active_failures),
                active_failures,
            )

    def test_direction_challenge_mismatched_final_build_requires_delta(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            state = project / ".design-dna"
            state.mkdir()
            (state / "direction-challenge.json").write_text(
                """{
  "record_status": "reviewed",
  "selection": {"chosen_root_id": "root-a"},
  "proof_slices": [{"root_id": "root-a", "build_id": "proof-build-2"}]
}\n""",
                encoding="utf-8",
            )
            (state / "visual-review.md").write_text(
                "---\nrecord_status: \"complete\"\n---\n"
                "- Build or artifact ID: final-build-7\n",
                encoding="utf-8",
            )
            failures = INITIALIZER.direction_challenge_final_build_binding_failures(
                state,
                project,
            )
            self.assertEqual(1, len(failures))
            self.assertIn("proof-to-build delta", failures[0])

    def test_check_ready_rejects_final_build_drift_after_challenge_is_ready(self) -> None:
        """The bridge must run after, not instead of, the Challenge audit."""

        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            state = project / ".design-dna"
            specification = importlib.util.spec_from_file_location(
                "design_dna_state_gate_direction_challenge_fixture",
                SKILL / "tests" / "test_direction_challenge.py",
            )
            assert specification is not None and specification.loader is not None
            support = importlib.util.module_from_spec(specification)
            specification.loader.exec_module(support)
            challenge = support.prepared_contract(project)
            self.assertTrue(support.AUDITOR.audit_payload(project, challenge)["ready"])
            (state / "direction-challenge.json").write_text(
                json.dumps(challenge, indent=2) + "\n",
                encoding="utf-8",
            )
            (state / "visual-review.md").write_text(
                "---\nrecord_status: \"complete\"\n---\n"
                "- Build or artifact ID: final-build-7\n",
                encoding="utf-8",
            )
            (state / "state.json").write_text(
                INITIALIZER.state_manifest(
                    "test-fixture",
                    ("direction-challenge", "visual-review"),
                    ("direction-challenge",),
                ),
                encoding="utf-8",
            )
            failures = INITIALIZER.readiness_failures(project)
            self.assertTrue(
                any("proof-to-build delta" in failure for failure in failures),
                failures,
            )

    def test_migrate_showcase_adds_new_calibration_only_as_draft(self) -> None:
        """Historical Showcase state gains a task, never invented proof."""

        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            state = project / ".design-dna"
            profiles = INITIALIZER.assurance_profiles_for_request(
                "showcase",
                INITIALIZER.PROFILES["showcase"],
            )
            INITIALIZER.render_new_state(
                SKILL,
                state,
                "test-fixture",
                INITIALIZER.PROFILES["showcase"],
                profiles,
            )
            state_path = state / "state.json"
            legacy_state = json.loads(state_path.read_text(encoding="utf-8"))
            legacy_state["records"].remove("taste-calibration")
            state_path.write_text(
                json.dumps(legacy_state, indent=2) + "\n",
                encoding="utf-8",
            )
            (state / "taste-calibration.md").unlink()

            updated = INITIALIZER.migrate_staged_state(state, "test-fixture")

            migrated_state = json.loads(state_path.read_text(encoding="utf-8"))
            metadata = INITIALIZER.parse_frontmatter(state / "taste-calibration.md")
            self.assertIn("taste-calibration", updated)
            self.assertIn("taste-calibration", migrated_state["records"])
            self.assertEqual("draft", metadata["record_status"])


if __name__ == "__main__":
    unittest.main()
