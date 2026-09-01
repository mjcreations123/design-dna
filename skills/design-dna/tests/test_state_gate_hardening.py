#!/usr/bin/env python3
"""Focused regressions for final Design DNA state/readiness evidence gates."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
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
        "## Artifact credibility and cumulative-pattern review",
        "- Artifact-only reviewer relationship and prior exposure: producer-self; the reviewer created the fixture and cannot claim independence",
        "- Credible public-surface result: the raw fixture cannot establish a credible public surface",
        "- Dominant recurring device or relationship cluster: the raw fixture cannot establish a rendered relationship cluster",
        "- Cumulative intensity and ordinary-work result: the raw fixture cannot establish whole-route intensity or ordinary content behavior",
        "- Business/category completeness result: the raw fixture cannot establish public or category completeness",
        "- Media credibility and synthetic-pattern result: the raw fixture cannot establish media credibility",
        "- Portfolio/process-language result: the raw fixture cannot establish public-copy credibility",
        "- Cross-project visual-grammar result or no-comparator limitation: no authorized comparator exists for the raw fixture",
        "- Container/backplate result: the raw fixture cannot establish whole-route containment logic",
        "- Link/button/underline affordance result: the raw fixture cannot establish whole-route action affordances",
        "- Artifact credibility disposition: blocked",
        "",
        "## Preship and specificity closure",
        "| Closure | Applicability or disposition | Rendered PNG path and SHA-256 | Result or limitation |",
        "| --- | --- | --- | --- |",
        "| Adversarial specificity review | applicable | evidence/raw.png plus sha256:" + ("0" * 64) + " | A raw image must not close the final review. |",
        "| Artifact credibility and cumulative pattern | blocked | evidence/raw.png plus sha256:" + ("0" * 64) + " | A raw image cannot establish whole-artifact public credibility. |",
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
    def test_non_b_bundled_auditor_loading_creates_no_runtime_bytecode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = root / "design-dna"
            shutil.copytree(SKILL, runtime)
            script = runtime / "scripts" / "init_project_state.py"
            probe = "\n".join((
                "import runpy, sys",
                "from pathlib import Path",
                "assert not sys.dont_write_bytecode",
                f"script = Path({str(script)!r})",
                "namespace = runpy.run_path(str(script), run_name='_design_dna_non_b_probe')",
                "loader = namespace['load_bundled_source_module']",
                "for index, name in enumerate((",
                "    'direction_challenge_audit.py',",
                "    'connected_public_experience_audit.py',",
                "    'owner_rejection_audit.py',",
                ")):",
                "    module = loader(f'_design_dna_non_b_{index}', script.with_name(name))",
                "    nested = getattr(module, 'load_render_review_adapter', None)",
                "    if nested is not None:",
                "        nested()",
            ))
            environment = os.environ.copy()
            environment.pop("PYTHONDONTWRITEBYTECODE", None)
            result = subprocess.run(
                [sys.executable, "-c", probe],
                cwd=root,
                env=environment,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
                check=False,
            )
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            residue = sorted(
                path.relative_to(runtime).as_posix()
                for path in runtime.rglob("*")
                if path.name == "__pycache__" or path.suffix.casefold() in {".pyc", ".pyo"}
            )
            self.assertEqual([], residue)

    def material_boundary_body(
        self,
        *,
        physical: str = "yes",
        requested: str = "yes",
        posture: str = "asset-led",
        rationale: str = "Not applicable because bound photography carries the physical subject.",
        basis: str = "Not applicable because no media-light exception is used.",
        approval: str = "Not applicable because this direction is asset-led.",
        evidence: str = "Not applicable because no media-light exception is used.",
        rejection: str = "active; reopen the compressed type, square CTA, hard-rule, fake-package, and photo-free relationship cluster.",
    ) -> str:
        return "\n".join((
            "## Material, media, and public-copy boundary",
            f"- Physical or sensory subject: {physical}",
            f"- Explicit owner request for photos or rich media: {requested}",
            f"- Material and media posture: {posture}",
            "- Project-specific basis: The brief sells a physical consumer product whose scale, use context, and package recognition matter.",
            "- Media roles and truth boundary: Product still life establishes recognition and household photography supplies context without implying clinical efficacy.",
            "- Asset manifest and readiness: .design-dna/assets.yml; selected local concept images are source-bound and crop-planned.",
            f"- Deliberately media-light rationale: {rationale}",
            f"- Media-light exception basis: {basis}",
            f"- Media-light exception approval: {approval}",
            f"- Media-light exception evidence: {evidence}",
            f"- Owner-rejection disposition: {rejection}",
            "- Protected facts and functions: Preserve safe label guidance, product distinctions, navigation, and basket behavior.",
            "- Public-copy boundary: Keep design rationale, backend categories, workflow state, and builder labels out of visitor-facing strings.",
            "",
        ))

    def test_photo_request_requires_asset_led_capability(self) -> None:
        body = self.material_boundary_body()
        failures = INITIALIZER.direction_material_boundary_failures(
            body,
            required_evidence_capabilities={"project-contrast"},
        )
        self.assertTrue(
            any("asset-led evidence capability" in failure for failure in failures),
            failures,
        )
        self.assertEqual(
            [],
            INITIALIZER.direction_material_boundary_failures(
                body,
                required_evidence_capabilities={"asset-led"},
            ),
        )

    def test_missing_supplied_photos_cannot_justify_media_light_physical_work(self) -> None:
        body = self.material_boundary_body(
            requested="no",
            posture="deliberately-media-light",
            rationale=(
                "No photos were supplied or available, so the build will use "
                "typography instead."
            ),
            basis="visitor-task-fit",
            approval="Not approved; this is only a producer convenience.",
        )
        failures = INITIALIZER.direction_material_boundary_failures(
            body,
            required_evidence_capabilities=set(),
        )
        self.assertTrue(
            any("Missing supplied media" in failure for failure in failures),
            failures,
        )

    def test_physical_media_light_exception_requires_specific_approved_authority(self) -> None:
        body = self.material_boundary_body(
            requested="no",
            posture="deliberately-media-light",
            rationale=(
                "The project will use typography and diagrams because that is a "
                "more restrained visual direction for this physical product, "
                "and the team prefers not to introduce photography right now."
            ),
            basis="preference-only",
            approval="Producer preference only.",
        )
        failures = INITIALIZER.direction_material_boundary_failures(
            body,
            required_evidence_capabilities=set(),
        )
        self.assertTrue(any("language-neutral values" in item for item in failures), failures)
        self.assertTrue(any("beginning with 'approved'" in item for item in failures), failures)
        self.assertTrue(any("ISO date" in item for item in failures), failures)

    def test_active_nested_owner_rejection_blocks_media_light_reversal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            state = project / ".design-dna"
            rejection_root = state / "rejections"
            rejection_root.mkdir(parents=True)
            (rejection_root / "owner.json").write_text(
                json.dumps({
                    "schema_version": 1,
                    "classification": "internal",
                    "status": "active-reopen",
                    "replacement_constraints": {
                        "asset_led_required": True,
                    },
                }),
                encoding="utf-8",
            )
            evidence = state / "owner-media-light.txt"
            approval = "approved by Motty 2026-08-23"
            evidence.write_text(
                "authority: owner\n"
                "decision: approved\n"
                f"{approval}\n",
                encoding="utf-8",
            )
            record_path = state / "direction.md"
            record_path.write_text("fixture\n", encoding="utf-8")
            body = self.material_boundary_body(
                requested="no",
                posture="deliberately-media-light",
                rationale="Photography would conflict with the approved visitor task for this particular concept.",
                basis="visitor-task-fit",
                approval=approval,
                evidence=(
                    ".design-dna/owner-media-light.txt plus sha256:"
                    + sha256(evidence)
                ),
                rejection=(
                    "active; reopen the prior type, CTA, edge, rhythm, and copy "
                    "relationship while preserving verified facts."
                ),
            )
            failures = INITIALIZER.direction_material_boundary_failures(
                body,
                required_evidence_capabilities=set(),
                project=project,
                record_path=record_path,
            )
            self.assertTrue(
                any("structured active owner rejection" in item for item in failures),
                failures,
            )
            inherited = self.material_boundary_body(
                requested="no",
                posture="inherited-system",
                rejection=(
                    "active; reopen the prior type, CTA, edge, rhythm, and copy "
                    "relationship while preserving verified facts."
                ),
            )
            inherited_failures = INITIALIZER.direction_material_boundary_failures(
                inherited,
                required_evidence_capabilities=set(),
                project=project,
                record_path=record_path,
            )
            self.assertTrue(
                any("structured active owner rejection" in item for item in inherited_failures),
                inherited_failures,
            )

    def test_standard_draft_direction_cannot_authorize_prebuild(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            state = project / ".design-dna"
            INITIALIZER.render_new_state(
                SKILL,
                state,
                "test-fixture",
                INITIALIZER.PROFILES["standard"],
                ("standard",),
            )
            failures = INITIALIZER.prebuild_failures(project)
            self.assertTrue(
                any("direction.md remains draft" in item for item in failures),
                failures,
            )

    def test_asset_led_only_state_cannot_authorize_prebuild(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            state = project / ".design-dna"
            INITIALIZER.render_new_state(
                SKILL,
                state,
                "test-fixture",
                ("assets",),
                ("asset-led",),
                ("asset-led",),
            )
            failures = INITIALIZER.prebuild_failures(project)
            self.assertTrue(
                any("always requires a selected direction.md" in item for item in failures),
                failures,
            )

    def test_draft_connected_public_experience_cannot_authorize_prebuild(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            state = project / ".design-dna"
            INITIALIZER.render_new_state(
                SKILL,
                state,
                "test-fixture",
                INITIALIZER.PROFILES["connected-public-experience"],
                ("standard", "connected-public-experience"),
                ("connected-public-experience",),
            )
            failures = INITIALIZER.prebuild_failures(project)
            self.assertTrue(
                any(
                    "Connected Public Experience has not authorized" in item
                    and "record-not-direction-ready" in item
                    for item in failures
                ),
                failures,
            )

    def test_range_template_cannot_authorize_prebuild(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            state = project / ".design-dna"
            INITIALIZER.render_new_state(
                SKILL,
                state,
                "test-fixture",
                INITIALIZER.PROFILES["range-study"],
                ("standard", "range-study"),
                ("range-study",),
            )
            failures = INITIALIZER.prebuild_failures(project)
            self.assertTrue(
                any("Route-family prebuild still contains" in item for item in failures),
                failures,
            )
            self.assertTrue(
                any("capture widths" in item for item in failures),
                failures,
            )

    def test_partially_edited_route_family_cannot_leave_packaged_instructions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "route-family.json"
            payload = json.loads(
                (SKILL / "templates" / "route-family-template.json").read_text(
                    encoding="utf-8"
                )
            )
            payload["created_with"] = "design-dna test-fixture"
            payload["study"].update({
                "id": "medicine-routes",
                "title": "Medicine route family",
            })
            for index, route in enumerate(payload["routes"]):
                route.update({
                    "title": f"Resolved route {index + 1}",
                    "user_job": f"Complete the distinct visitor job for route {index + 1}.",
                    "creative_logic": f"A project-specific route logic for body {index + 1}.",
                    "responsive_result": f"Route {index + 1} preserves its task on narrow screens.",
                    "deliberate_differences": [
                        f"Route {index + 1} has a different body operation."
                    ],
                })
                for viewport_index, viewport in enumerate(
                    route["capture_requirements"]["viewports"]
                ):
                    viewport.update({
                        "id": f"route-{index + 1}-viewport-{viewport_index + 1}",
                        "width": 390 if viewport_index else 1366,
                    })
            path.write_text(json.dumps(payload), encoding="utf-8")
            failures = INITIALIZER.route_family_prebuild_failures(path)
            self.assertTrue(
                any("scaffold language" in item for item in failures),
                failures,
            )

    def test_prebuild_blocks_template_inventory_before_full_site(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            state = project / ".design-dna"
            records = (
                "exploration",
                "taste-calibration",
                "direction",
                "direction-proof",
                "project-contrast",
                "direction-challenge",
            )
            profiles = INITIALIZER.normalize_assurance_profiles((
                "showcase",
                "project-contrast",
                "direction-challenge",
            ))
            INITIALIZER.render_new_state(
                SKILL,
                state,
                "test-fixture",
                records,
                profiles,
                ("project-contrast", "direction-challenge"),
                (INITIALIZER.OWNER_RECURRENCE_TRIGGER,),
            )
            failures = INITIALIZER.prebuild_failures(project)
            self.assertTrue(
                any("Prebuild direction.md" in failure for failure in failures),
                failures,
            )
            self.assertTrue(
                any("Project Contrast must reach direction-ready" in failure for failure in failures),
                failures,
            )
            self.assertTrue(
                any("Direction Challenge must be reviewed" in failure for failure in failures),
                failures,
            )

    def test_asset_led_prebuild_rejects_empty_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "assets.yml"
            path.write_text(
                "schema_version: 2\n"
                "created_with: \"design-dna test-fixture\"\n"
                "classification: \"internal\"\n"
                "assets: []\n",
                encoding="utf-8",
            )
            failures = INITIALIZER.asset_prebuild_failures(
                path,
                require_visual=True,
            )
            self.assertEqual(1, len(failures))
            self.assertIn("nonempty assets.yml", failures[0])

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

    def test_enterprise_contract_couples_copy_and_numeric_rhetoric_review(self) -> None:
        """Public-candidate review cannot drop the listicle-framing closure."""

        contract = INITIALIZER.evidence_contract_payload(("enterprise-candidate",))
        self.assertEqual(
            [
                "enterprise-candidate",
                "public-copy-integrity",
                "numeric-rhetoric-integrity",
                "reference-led-direction",
            ],
            contract["applicable_capabilities"],
        )
        self.assertEqual(
            {"direction", "visual-review"},
            INITIALIZER.CAPABILITY_REQUIRED_RECORDS["numeric-rhetoric-integrity"],
        )
        self.assertEqual(
            {
                "Numeric rhetoric integrity closure (required for public candidates)"
            },
            INITIALIZER.CAPABILITY_REQUIRED_SECTIONS[
                "numeric-rhetoric-integrity"
            ]["visual-review"],
        )
        self.assertEqual(
            {"direction", "reference-dossier", "visual-review"},
            INITIALIZER.CAPABILITY_REQUIRED_RECORDS["reference-led-direction"],
        )
        self.assertEqual(
            {"Reference-led direction (required for public candidates)"},
            INITIALIZER.CAPABILITY_REQUIRED_SECTIONS[
                "reference-led-direction"
            ]["direction"],
        )
        self.assertEqual(
            {"Reference-led direction closure (required for public candidates)"},
            INITIALIZER.CAPABILITY_REQUIRED_SECTIONS[
                "reference-led-direction"
            ]["visual-review"],
        )

        malformed = dict(contract)
        malformed["applicable_capabilities"] = [
            "enterprise-candidate",
            "public-copy-integrity",
            "numeric-rhetoric-integrity",
        ]
        with self.assertRaisesRegex(
            INITIALIZER.StateError,
            "requires reference-led-direction",
        ):
            INITIALIZER.validate_evidence_contract(
                malformed,
                ("standard", "enterprise-candidate"),
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
                "## Artifact credibility and cumulative-pattern review",
                "- Artifact-only reviewer relationship and prior exposure: producer-self; the reviewer built the fixture and recorded that limitation",
                "- Credible public-surface result: the final public fixture reads as a coherent task surface within its bounded scenario",
                "- Dominant recurring device or relationship cluster: the task hierarchy is the only recurring relationship and follows the fixture flow",
                "- Cumulative intensity and ordinary-work result: ordinary instructions remain quieter than the primary task and evidence",
                "- Business/category completeness result: the bounded fixture answers the declared task without inventing a broader business operation",
                "- Media credibility and synthetic-pattern result: no illustrative or documentary media is present in this fixture",
                "- Portfolio/process-language result: public copy describes only the task and contains no maker-facing process narration",
                "- Cross-project visual-grammar result or no-comparator limitation: no authorized sibling comparator exists for this isolated fixture",
                "- Container/backplate result: the fixture uses one task boundary for the single state and does not box unrelated content jobs",
                "- Link/button/underline affordance result: the fixture action and navigation treatments follow their distinct semantics",
                "- Artifact credibility disposition: keep",
                "",
                "## Preship and specificity closure",
                "| Closure | Applicability or disposition | Rendered PNG path and SHA-256 | Result or limitation |",
                "| --- | --- | --- | --- |",
                "| Adversarial specificity review | applicable | " + wide_path.relative_to(project).as_posix() + " plus sha256:" + sha256(wide_path) + " | The bounded review records the project-specific encounter and remaining producer-self limitation. |",
                "| Artifact credibility and cumulative pattern | applicable | " + wide_path.relative_to(project).as_posix() + " plus sha256:" + sha256(wide_path) + " | The artifact-only pass found no unexplained intensity or portfolio-facing machinery in this bounded fixture. |",
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

            missing_credibility_row = "\n".join(
                line
                for line in body.splitlines()
                if not line.startswith(
                    "| Artifact credibility and cumulative pattern |"
                )
            )
            failures = INITIALIZER.substantive_body_failures(
                "visual-review",
                missing_credibility_row,
                project=project,
                record_path=state / "visual-review.md",
                required_assurance_profiles={"standard"},
                evidence_contract=INITIALIZER.PROPORTIONAL_EVIDENCE_CONTRACT,
                enforce_final_visual_binding=True,
            )
            self.assertTrue(
                any(
                    "artifact credibility and cumulative pattern" in failure
                    for failure in failures
                ),
                failures,
            )

            missing_credibility_result = body.replace(
                "- Credible public-surface result: the final public fixture "
                "reads as a coherent task surface within its bounded scenario",
                "- Credible public-surface result:",
            )
            failures = INITIALIZER.substantive_body_failures(
                "visual-review",
                missing_credibility_result,
                project=project,
                record_path=state / "visual-review.md",
                required_assurance_profiles={"standard"},
                evidence_contract=INITIALIZER.PROPORTIONAL_EVIDENCE_CONTRACT,
                enforce_final_visual_binding=True,
            )
            self.assertTrue(
                any("Credible public-surface result" in failure for failure in failures),
                failures,
            )

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

    def test_completed_cpe_must_match_the_final_visual_review_build(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            state = project / ".design-dna"
            state.mkdir()
            (state / "visual-review.md").write_text(
                "---\nrecord_status: \"complete\"\n---\n"
                "- Build or artifact ID: final-build-7\n",
                encoding="utf-8",
            )
            connected = {
                "record_status": "reviewed",
                "final_closure": {
                    "status": "complete",
                    "reviewed_build_id": "stale-build-2",
                },
            }
            (state / "connected-public-experience.json").write_text(
                json.dumps(connected, indent=2) + "\n",
                encoding="utf-8",
            )
            failures = INITIALIZER.final_build_evidence_binding_failures(state)
            self.assertEqual(1, len(failures), failures)
            self.assertIn("Final-build evidence drift", failures[0])
            self.assertIn("stale-build-2", failures[0])
            self.assertIn("final-build-7", failures[0])

            connected["final_closure"]["reviewed_build_id"] = "final-build-7"
            (state / "connected-public-experience.json").write_text(
                json.dumps(connected, indent=2) + "\n",
                encoding="utf-8",
            )
            self.assertEqual(
                [],
                INITIALIZER.final_build_evidence_binding_failures(state),
            )

    def test_proof_ready_project_contrast_must_match_final_visual_review_build(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            state = project / ".design-dna"
            state.mkdir()
            (state / "visual-review.md").write_text(
                "---\nrecord_status: \"complete\"\n---\n"
                "- Build or artifact ID: final-build-7\n",
                encoding="utf-8",
            )
            contrast = {
                "record_status": "proof-ready",
                "evidence": {"candidate_build": {"id": "stale-build-3"}},
            }
            (state / "project-contrast.json").write_text(
                json.dumps(contrast, indent=2) + "\n",
                encoding="utf-8",
            )
            failures = INITIALIZER.final_build_evidence_binding_failures(state)
            self.assertEqual(1, len(failures), failures)
            self.assertIn("project-contrast.json", failures[0])
            self.assertIn("stale-build-3", failures[0])

            contrast["evidence"]["candidate_build"]["id"] = "final-build-7"
            (state / "project-contrast.json").write_text(
                json.dumps(contrast, indent=2) + "\n",
                encoding="utf-8",
            )
            self.assertEqual(
                [],
                INITIALIZER.final_build_evidence_binding_failures(state),
            )

    def test_verified_audit_outputs_cannot_hide_final_build_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary) / ".design-dna"
            state.mkdir()
            (state / "visual-review.md").write_text(
                "---\nrecord_status: \"complete\"\n---\n"
                "- Build or artifact ID: final-build-7\n",
                encoding="utf-8",
            )
            connected_report = {
                "evidence": {
                    "verified": [
                        {"id": "home-narrow", "build_id": "stale-build-5"}
                    ]
                }
            }
            contrast_report = {
                "evidence": {
                    "capture_coverage": {
                        "candidate_build_id": "stale-build-6"
                    }
                }
            }
            failures = INITIALIZER.final_build_evidence_binding_failures(
                state,
                project_contrast_report=contrast_report,
                connected_public_experience_report=connected_report,
            )
            self.assertEqual(2, len(failures), failures)
            self.assertTrue(
                any("stale-build-5" in failure for failure in failures),
                failures,
            )
            self.assertTrue(
                any("stale-build-6" in failure for failure in failures),
                failures,
            )

            connected_report["evidence"]["verified"][0]["build_id"] = (
                "final-build-7"
            )
            contrast_report["evidence"]["capture_coverage"][
                "candidate_build_id"
            ] = "final-build-7"
            self.assertEqual(
                [],
                INITIALIZER.final_build_evidence_binding_failures(
                    state,
                    project_contrast_report=contrast_report,
                    connected_public_experience_report=connected_report,
                ),
            )

    def test_readiness_wires_the_cross_record_final_build_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            state = project / ".design-dna"
            state.mkdir()
            (state / "visual-review.md").write_text(
                "---\nrecord_status: \"complete\"\n---\n"
                "- Build or artifact ID: final-build-7\n",
                encoding="utf-8",
            )
            (state / "connected-public-experience.json").write_text(
                json.dumps(
                    {
                        "record_status": "reviewed",
                        "final_closure": {
                            "status": "complete",
                            "reviewed_build_id": "stale-build-4",
                        },
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            (state / "state.json").write_text(
                INITIALIZER.state_manifest(
                    "test-fixture",
                    ("visual-review",),
                    ("quick",),
                ),
                encoding="utf-8",
            )
            failures = INITIALIZER.readiness_failures(project)
            self.assertTrue(
                any("Final-build evidence drift" in failure for failure in failures),
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
